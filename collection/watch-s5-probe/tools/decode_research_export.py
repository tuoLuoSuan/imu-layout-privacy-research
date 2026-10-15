"""Validate IMUS5 v2 exports. CRC checks transfer errors, not authenticity or encryption."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import zlib

ID = re.compile(r'[0-9]{1,16}_[a-f0-9]{6}')
FIELDS = ['sequence', 'callback_epoch_ms', 'x', 'y', 'z', 'page_state']


def number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def json_object(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('重复 JSON 字段')
            out[key] = value
        return out
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('非有限 JSON 数字')))
    if not isinstance(value, dict):
        raise ValueError('JSON 必须为对象')
    return value


def decode_packets(packets):
    groups = {}
    session = None
    for packet in packets:
        packet = packet.rstrip('\r\n')
        if not packet.startswith('IMUS5|'):
            continue
        parts = packet.split('|', 7)
        if len(parts) != 8 or parts[1] != '2' or not ID.fullmatch(parts[2]):
            raise ValueError('无效协议头或会话 ID')
        _, _, sid, part, page, total, checksum, payload = parts
        if session is not None and session != sid:
            raise ValueError('混有多个会话，请分开解码')
        session = sid
        try:
            part, page, total = int(part), int(page), int(total)
        except ValueError:
            raise ValueError('无效二维码序号') from None
        if not 0 <= part <= 401 or not 1 <= page <= total <= 219 or len(payload) > 300:
            raise ValueError('二维码范围超限')
        if not re.fullmatch('[a-f0-9]{8}', checksum) or not payload.isascii():
            raise ValueError('编码或 CRC 字段无效')
        group = groups.setdefault(part, {'total': total, 'crc': checksum, 'pages': {}})
        if group['total'] != total or group['crc'] != checksum:
            raise ValueError('同一段校验信息冲突')
        if page in group['pages'] and group['pages'][page] != payload:
            raise ValueError('同一页内容冲突')
        group['pages'][page] = payload
    if not groups or 0 not in groups:
        raise ValueError('缺少第 1 段清单二维码')
    bodies = {}
    for part, group in groups.items():
        missing = sorted(set(range(1, group['total'] + 1)) - group['pages'].keys())
        if missing:
            raise ValueError(f'第 {part + 1} 段缺页 {missing[:20]}，请补拍')
        text = ''.join(group['pages'][i] for i in range(1, group['total'] + 1))
        if len(text) > 65536 or f'{zlib.crc32(text.encode("ascii")):08x}' != group['crc']:
            raise ValueError('CRC 校验失败')
        bodies[part] = text
    manifest = json_object(bodies[0])
    if manifest.get('kind') != 'manifest' or manifest.get('schema_version') != 2 or manifest.get('session_id') != session:
        raise ValueError('清单身份冲突')
    names = manifest.get('files')
    if not isinstance(names, list) or not 1 <= len(names) <= 401:
        raise ValueError('文件清单不合法')
    prefix = f's5r_{session}_'
    if any(not isinstance(n, str) or not re.fullmatch(re.escape(prefix) + r'(head|tail|b[0-9]{4})\.json', n) for n in names):
        raise ValueError('文件清单含越界路径')
    has_tail = names[-1] == prefix + 'tail.json'
    block_count = len(names) - 1 - int(has_tail)
    expected = [prefix + 'head.json'] + [prefix + f'b{i:04d}.json' for i in range(block_count)]
    if has_tail:
        expected.append(prefix + 'tail.json')
    if names != expected:
        raise ValueError('块顺序、数量或连续性不合法')
    if set(bodies) != set(range(len(names) + 1)):
        raise ValueError('缺少整段数据或混入额外段，请核对段号')
    raw = dict(zip(names, (bodies[i + 1] for i in range(len(names)))))
    objects = [json_object(raw[n]) for n in names]
    if any(o.get('schema_version') != 2 or o.get('session_id') != session for o in objects):
        raise ValueError('数据文件身份冲突')
    head = objects[0]
    if head.get('kind') != 'head' or head.get('row_fields') != FIELDS or not number(head.get('started_epoch_ms')):
        raise ValueError('元数据结构错误')
    meta = head.get('metadata')
    if not isinstance(meta, dict) or meta.get('time_source') != 'Date.now_callback_arrival' or meta.get('hardware_timestamp') is not False:
        raise ValueError('时间语义不符合本版合同')
    rows, events = [], []
    for index, block in enumerate(objects[1:1 + block_count]):
        if block.get('kind') != 'block' or block.get('index') != index:
            raise ValueError('块编号冲突')
        batch, marks = block.get('rows'), block.get('events')
        if not isinstance(batch, list) or len(batch) > 128 or not isinstance(marks, list) or len(marks) > 32:
            raise ValueError('块数据超过边界')
        for row in batch:
            if not isinstance(row, list) or len(row) != 6 or any(not number(x) for x in row[:5]) or row[0] != len(rows):
                raise ValueError('序号不连续或样本格式错误')
            if row[5] not in ('visible', 'hidden') or row[1] < head['started_epoch_ms']:
                raise ValueError('样本状态或时间无效')
            rows.append(row)
        for event in marks:
            if not isinstance(event, dict) or not number(event.get('callback_epoch_ms')) or not isinstance(event.get('type'), str):
                raise ValueError('事件格式错误')
            events.append(event)
    if len(rows) > 40000:
        raise ValueError('超过会话样本上限')
    tail = objects[-1] if has_tail else None
    if tail is not None:
        if tail.get('kind') != 'tail' or tail.get('count') != len(rows) or tail.get('persisted') != len(rows) or tail.get('blocks') != block_count:
            raise ValueError('尾文件样本数/块数与实际文件不符')
        if not number(tail.get('stopped_epoch_ms')):
            raise ValueError('停止时刻无效')
        if (tail['stopped_epoch_ms'] < head['started_epoch_ms'] or (rows and rows[-1][1] > tail['stopped_epoch_ms'])) and tail.get('stop_reason') != 'clock_regression':
            raise ValueError('停止时刻早于末样本')
        if not isinstance(tail.get('quality'), dict) or not isinstance(tail['quality'].get('warnings'), list):
            raise ValueError('质量字段无效')
    times = [r[1] for r in rows]
    deltas = [b - a for a, b in zip(times, times[1:])]
    positive = sorted(d for d in deltas if d > 0)
    warnings = list(tail['quality']['warnings']) if tail else ['missing_tail_unknown_interruption']
    if not rows:
        warnings.append('no_samples')
    if any(d < 0 for d in deltas):
        warnings.append('clock_regression')
    if any(d == 0 for d in deltas):
        warnings.append('zero_callback_intervals')
    if any(d > 1000 for d in deltas):
        warnings.append('callback_gap_over_1s')
    stop_reason = tail.get('stop_reason') if tail else 'unknown_interruption'
    if tail and stop_reason not in ('manual', 'duration'):
        warnings.append('abnormal_stop')
    span = times[-1] - times[0] if len(times) > 1 else None
    report = {
        'session_id': session, 'transfer_status': 'complete',
        'session_status': 'interrupted' if tail is None else 'sealed_with_warnings' if warnings else 'sealed',
        'samples': len(rows), 'blocks': block_count, 'events': len(events), 'stop_reason': stop_reason,
        'callback_span_ms': span, 'callback_hz': (len(times) - 1) * 1000 / span if span and span > 0 and all(d >= 0 for d in deltas) else None,
        'requested_interval': meta.get('requested_interval'), 'hardware_sampling_hz': None,
        'median_positive_gap_ms': statistics.median(positive) if positive else None,
        'p95_positive_gap_ms': positive[math.ceil(.95 * len(positive)) - 1] if positive else None,
        'max_positive_gap_ms': max(positive) if positive else None,
        'clock_regressions': sum(d < 0 for d in deltas), 'zero_intervals': deltas.count(0),
        'gaps_over_100ms': sum(d > 100 for d in deltas), 'gaps_over_1s': sum(d > 1000 for d in deltas),
        'hidden_samples': sum(r[5] == 'hidden' for r in rows),
        'warnings': sorted(set(warnings)), 'hardware_validation': 'not_established_by_this_report',
        'meaning': '回调墙钟到达率；非传感器采样率，非手机同步，非单位标定。缺失未补值。',
        'files': {n: {'sha256': hashlib.sha256(t.encode('ascii')).hexdigest(), 'bytes': len(t)} for n, t in raw.items()}
    }
    return {'session_id': session, 'raw': raw, 'metadata': head, 'tail': tail, 'rows': rows, 'events': events, 'report': report, 'manifest_text': bodies[0]}


def scan_media(paths):
    """Optional OpenCV, ordinary optical decoding only; never infer missing QR modules."""
    for path in paths:
        path = Path(path)
        if path.suffix.lower() in ('.txt', '.log'):
            yield from path.read_text(encoding='utf-8-sig').splitlines()
            continue
        try:
            import cv2
        except ImportError:
            raise ValueError('视频/图片解码需要 OpenCV；也可输入扫码文本 .txt') from None
        detector = cv2.QRCodeDetector()
        def strings(frame):
            value, _, _ = detector.detectAndDecode(frame)
            if value.startswith('IMUS5|'):
                yield value
            else:
                ok, values, _, _ = detector.detectAndDecodeMulti(frame)
                if ok:
                    yield from (v for v in values if v.startswith('IMUS5|'))
        if path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError('无法读取图片')
            yield from strings(image)
        else:
            video = cv2.VideoCapture(str(path))
            try:
                if not video.isOpened():
                    raise ValueError('无法打开视频')
                while True:
                    ok, frame = video.read()
                    if not ok:
                        break
                    yield from strings(frame)
            finally:
                video.release()


def save_export(record, target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    raw_dir = target / 'raw'
    raw_dir.mkdir()
    for name, text in record['raw'].items():
        (raw_dir / name).write_bytes(text.encode('ascii'))
    (target / 'transfer-manifest.json').write_bytes(record['manifest_text'].encode('ascii'))
    with (target / 'accelerometer.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        writer.writerows(record['rows'])
    for name, value in [('metadata.json', record['metadata']), ('integrity_report.json', record['report']), ('events.json', record['events'])]:
        (target / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', help='QR text files, videos or screenshots from ONE session')
    parser.add_argument('--output', required=True, help='A new private output directory; existing directories are refused')
    args = parser.parse_args()
    try:
        record = decode_packets(scan_media(args.inputs))
        save_export(record, args.output)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(record['report'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
