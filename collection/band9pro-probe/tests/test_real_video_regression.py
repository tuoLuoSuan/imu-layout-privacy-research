"""Regression against a user-supplied real export video, kept in local evidence.

This fixture is distinct from the synthetic acquisition/export tests.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT.parents[1] / 'docs/evidence/2026-10-13-band9pro-video-d6d28b48'
spec = importlib.util.spec_from_file_location('decoder', ROOT / 'tools/decode_export.py')
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


@unittest.skipUnless((EVIDENCE / 'source_video.mp4').exists(), '本地用户视频未提供')
class RealVideoRecovery(unittest.TestCase):
    def test_real_photo_region_can_be_decoded_without_manual_crop(self):
        import cv2
        import numpy as np
        p = EVIDENCE / 'frame_5s.jpg'
        frame = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
        values = decoder.qr_strings(frame, cv2.QRCodeDetector())
        self.assertTrue(any(value.startswith('IMU9P|1|1791866158764_fddc8d|3|9|d58d7603|')
                            for value in values), '清晰帧需要自动区域放大才能解出')

    def test_real_compressed_video_restores_all_nine_packets(self):
        packets = decoder.scan_media([EVIDENCE / 'source_video.mp4'])
        self.assertEqual(len(packets), 9, '必须恢复全部分片，不能补值')
        record = decoder.decode_packets(packets)[0]
        self.assertEqual(record['session_id'], '1791866158764_fddc8d')
        self.assertEqual(len(record['rows']), 30)
        self.assertEqual(record['rows'][0], [46, 0.481234550476074, 1.98958158493042,
                                           9.80904483795166, 'visible'])


if __name__ == '__main__':
    unittest.main()
