import importlib.util
import json
from pathlib import Path
import unittest
import zlib

source = Path(__file__).resolve().parents[1] / 'tools' / 'decode_export.py'
decoder = None
if source.exists():
    spec = importlib.util.spec_from_file_location('probe_decoder', source)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)


def packets():
    record = {
        'schema_version': 1, 'session_id': 'test_fixture', 'started_epoch_ms': 10000,
        'metadata': {'acceleration_unit': 'unknown', 'hardware_timestamp': False,
                     'time_source': 'Date.now_callback_arrival',
                     'activity_instruction': 'walk', 'evidence': 'synthetic_software_test'},
        'rows': [[20, 1.2, -2, 3, 'visible'], [40, 1.3, -2, 3, 'visible'],
                 [10, 1.4, -2, 3, 'hidden']],
    }
    body = json.dumps(record, ensure_ascii=True, separators=(',', ':'))
    checksum = f'{zlib.crc32(body.encode("ascii")) & 0xffffffff:08x}'
    pieces = [body[i:i + 90] for i in range(0, len(body), 90)]
    return [f'IMU9P|1|test_fixture|{i+1}|{len(pieces)}|{checksum}|{piece}'
            for i, piece in enumerate(pieces)]


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(decoder, '数据恢复工具尚未实现')

    def test_unordered_duplicate_packets_restore_exact_values(self):
        frames = packets()
        record = decoder.decode_packets(list(reversed(frames)) + [frames[0]])[0]
        self.assertEqual(record['rows'][0][1], 1.2)
        self.assertEqual(record['metadata']['evidence'], 'synthetic_software_test')

    def test_missing_packet_is_an_error(self):
        with self.assertRaisesRegex(ValueError, '缺少'):
            decoder.decode_packets(packets()[1:])

    def test_corruption_is_an_error(self):
        frames = packets()
        frames[-1] = frames[-1][:-1] + '!'
        with self.assertRaisesRegex(ValueError, '校验'):
            decoder.decode_packets(frames)

    def test_conflicting_duplicate_is_an_error(self):
        frames = packets()
        with self.assertRaisesRegex(ValueError, '冲突'):
            decoder.decode_packets(frames + [frames[0] + 'x'])

    def test_quality_report_does_not_hide_clock_reversal(self):
        record = decoder.decode_packets(packets())[0]
        report = decoder.quality_report(record)
        self.assertEqual(report['clock_regressions'], 1)
        self.assertIsNone(report['callback_hz'])
        self.assertEqual(report['acceleration_unit'], 'unknown')


if __name__ == '__main__':
    unittest.main()
