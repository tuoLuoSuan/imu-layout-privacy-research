"""Recover actual callback records from IMU9P QR frames; never fill missing data."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
import statistics
import sys
import zlib


def validate_record(record):
    if record.get('schema_version') != 1:
        raise ValueError('不支持的记录格式')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', record.get('session_id', '')):
        raise ValueError('会话编号无效')
    if not isinstance(record.get('started_epoch_ms'), (int, float)):
        raise ValueError('记录缺少回调时基')
    if not math.isfinite(record['started_epoch_ms']):
        raise ValueError('回调时基非有限数')
    rows = record.get('rows')
    if not isinstance(rows, list) or not rows or len(rows) > 2000:
        raise ValueError('记录样本数不合法')
    for row in rows:
        if not isinstance(row, list) or len(row) != 5:
            raise ValueError('样本字段不完整')
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
               for x in row[:4]):
            raise ValueError('样本包含无效数字；未自动补值')
        if row[4] not in ('visible', 'hidden'):
            raise ValueError('页面状态不合法')
    if not isinstance(record.get('metadata'), dict):
        raise ValueError('记录缺少元数据')
    return record


def decode_packets(packets):
    sessions = {}
    for packet in packets:
        packet = packet.strip()
        if not packet.startswith('IMU9P|'):
            continue
        parts = packet.split('|', 6)
        if len(parts) != 7 or parts[1] != '1':
            raise ValueError('二维码协议头不完整')
        _, _, session_id, index, total, checksum, payload = parts
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', session_id):
            raise ValueError('二维码会话编号无效')
        try:
            index, total = int(index), int(total)
        except ValueError:
            raise ValueError('二维码分片编号无效') from None
        if not 1 <= index <= total <= 5000 or len(payload) > 4096:
            raise ValueError('二维码分片范围无效')
        if not re.fullmatch(r'[0-9a-f]{8}', checksum):
            raise ValueError('二维码校验字段无效')
        group = sessions.setdefault(session_id, {'total': total, 'checksum': checksum, 'parts': {}})
        if group['total'] != total or group['checksum'] != checksum:
            raise ValueError('同一会话的导出信息冲突')
        if index in group['parts'] and group['parts'][index] != payload:
            raise ValueError('同一分片内容冲突')
        group['parts'][index] = payload
    if not sessions:
        raise ValueError('没有识别到 IMU9P 数据二维码')
    records = []
    for session_id, group in sessions.items():
        missing = [i for i in range(1, group['total'] + 1) if i not in group['parts']]
        if missing:
            raise ValueError(f'会话 {session_id} 缺少二维码页 {missing[:20]}；请补拍，未生成完整 CSV')
        body = ''.join(group['parts'][i] for i in range(1, group['total'] + 1))
        try:
            actual_crc = f'{zlib.crc32(body.encode("ascii")) & 0xffffffff:08x}'
        except UnicodeEncodeError:
            raise ValueError('二维码内容编码或校验不正确') from None
        if actual_crc != group['checksum']:
            raise ValueError(f'会话 {session_id} 校验不通过；未补值或生成完整 CSV')
        try:
            record = json.loads(body)
        except json.JSONDecodeError:
            raise ValueError('二维码 JSON 内容不完整') from None
        if record.get('session_id') != session_id:
            raise ValueError('会话内容与二维码头冲突')
        records.append(validate_record(record))
    return records


def quality_report(record):
    times = [row[0] for row in record['rows']]
    deltas = [b - a for a, b in zip(times, times[1:])]
    positive = sorted(x for x in deltas if x > 0)
    reversed_count = sum(x < 0 for x in deltas)
    span = times[-1] - times[0]
    meta = record['metadata']
    return {
        'session_id': record['session_id'], 'samples': len(times),
        'callback_span_ms': span,
        'callback_hz': (len(times) - 1) * 1000 / span if span > 0 and not reversed_count else None,
        'callback_hz_definition': '(samples - 1) / (last callback time - first callback time)',
        'hardware_sampling_hz': None,
        'acceleration_unit': meta.get('acceleration_unit', 'unknown'),
        'clock_regressions': reversed_count,
        'zero_intervals': sum(x == 0 for x in deltas),
        'median_positive_gap_ms': statistics.median(positive) if positive else None,
        'p95_positive_gap_ms': positive[max(0, math.ceil(len(positive) * .95) - 1)] if positive else None,
        'max_positive_gap_ms': max(positive) if positive else None,
        'gaps_over_1s': sum(x > 1000 for x in deltas),
        'visible_samples': sum(row[4] == 'visible' for row in record['rows']),
        'hidden_samples': sum(row[4] == 'hidden' for row in record['rows']),
        'activity_instruction': meta.get('activity_instruction'),
        'label_source': meta.get('label_source', 'manual_instruction'),
        'interpretation': '回调到达间隔，不是硬件采样率；未计算不可验证的丢样率。'
    }


def qr_strings(frame, detector):
    import cv2
    import numpy as np

    results = []
    value, points, _ = detector.detectAndDecode(frame)
    if value.startswith('IMU9P|'):
        results.append(value)
    if not results:
        success, values, _, _ = detector.detectAndDecodeMulti(frame)
        if success:
            results.extend(value for value in values if value.startswith('IMU9P|'))
    if not results and points is None and hasattr(cv2, 'QRCodeDetectorAruco'):
        alternate = cv2.QRCodeDetectorAruco()
        value, alternate_points, _ = alternate.detectAndDecode(frame)
        if value.startswith('IMU9P|'):
            return [value]
        if alternate_points is not None:
            points = alternate_points
            detector = alternate
    if results or points is None:
        return results

    # Real compressed footage may contain a detectable but small dense QR.
    # Enlarge only its observed region; never reconstruct or infer QR modules.
    coords = points.reshape(-1, 2)
    if not np.isfinite(coords).all():
        return results
    low = np.floor(coords.min(axis=0) - 40).astype(int)
    high = np.ceil(coords.max(axis=0) + 40).astype(int)
    left, top = max(0, low[0]), max(0, low[1])
    right, bottom = min(frame.shape[1], high[0]), min(frame.shape[0], high[1])
    if right <= left or bottom <= top:
        return results
    crop = frame[top:bottom, left:right]
    for scale in (2, 3, 4):
        enlarged = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        value, _, _ = detector.detectAndDecode(enlarged)
        if value.startswith('IMU9P|'):
            return [value]
        gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY) if enlarged.ndim == 3 else enlarged
        thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        value, _, _ = detector.detectAndDecode(thresholded)
        if value.startswith('IMU9P|'):
            return [value]
    return results


def scan_media(paths):
    packets = set()
    cv2 = None
    detector = None
    for source in paths:
        path = Path(source)
        if path.suffix.lower() in ('.txt', '.log'):
            packets.update(line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
                           if line.strip().startswith('IMU9P|'))
            continue
        if cv2 is None:
            try:
                import cv2 as cv2_module
                cv2 = cv2_module
            except ImportError:
                raise ValueError('当前 Python 没有 OpenCV，暂时可以输入扫码得到的文本文件。') from None
            detector = cv2.QRCodeDetector()
        if path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
            import numpy as np
            frame = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError(f'图片无法读取：{path.name}')
            packets.update(qr_strings(frame, detector))
            continue
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise ValueError(f'视频无法读取：{path.name}；可改用 PNG 图片或扫码文本')
        fps = capture.get(cv2.CAP_PROP_FPS) or 30
        stride = max(1, round(fps * .2))
        index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if index % stride == 0:
                    packets.update(qr_strings(frame, detector))
                index += 1
        finally:
            capture.release()
    return sorted(packets)


def write_records(records, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    targets = [(record, output / record['session_id']) for record in records]
    for _, base in targets:
        if any(base.with_suffix(suffix).exists() for suffix in ('.json', '.csv', '.quality.json')):
            raise ValueError(f'输出已存在，未覆盖：{base.name}；请选择另一个输出目录')
    for record, base in targets:
        base.with_suffix('.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        base.with_suffix('.quality.json').write_text(
            json.dumps(quality_report(record), ensure_ascii=False, indent=2), encoding='utf-8')
        with base.with_suffix('.csv').open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.writer(handle)
            writer.writerow(['session_id', 'sequence', 'callback_elapsed_ms', 'callback_epoch_ms',
                             'x', 'y', 'z', 'page_state', 'activity_instruction'])
            for sequence, row in enumerate(record['rows']):
                writer.writerow([record['session_id'], sequence, row[0], record['started_epoch_ms'] + row[0],
                                 *row[1:], record['metadata'].get('activity_instruction', '')])
        print(f'已导出 {len(record["rows"])} 条回调数据：{base.with_suffix(".csv")}')


def main():
    parser = argparse.ArgumentParser(description='把手环 IMU9P 二维码视频/图片/文本恢复成 CSV')
    parser.add_argument('inputs', nargs='*')
    parser.add_argument('--output', default=str(Path(__file__).resolve().parents[1] / 'recordings'))
    parser.add_argument('--from-stdin', action='store_true')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    try:
        if args.from_stdin:
            packets = sys.stdin.read().splitlines()
        else:
            paths = args.inputs
            if not paths:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                paths = filedialog.askopenfilenames(title='选择拍摄手环二维码的视频、图片或扫码文本')
                root.destroy()
            if not paths:
                return 0
            packets = scan_media(paths)
        records = decode_packets(packets)
        if args.check_only:
            print(json.dumps({'records': records, 'quality': [quality_report(x) for x in records]},
                             ensure_ascii=True))
        else:
            write_records(records, args.output)
        return 0
    except (ValueError, OSError) as error:
        print(f'导出未完成：{error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
