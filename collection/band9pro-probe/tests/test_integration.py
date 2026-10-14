"""Software fixtures only: these are not sensor or device test results."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('decode_export', ROOT / 'tools/decode_export.py')
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


class ExportIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = """
const {createRecorder,encodeChunks}=require('./src/common/recorder.js');
let clock=1700000000000;
const r=createRecorder({now:()=>clock,label:'synthetic_software_fixture'});
r.start();
for(let i=0;i<8;i++){clock+=20;r.append({x:i*0.123456789,y:-i*2,z:9.123456789});}
r.event('synthetic_fixture','软件生成，非真机');
const record=r.stop('manual'); record.metadata.evidence_origin='software_generated_fixture';
console.log(JSON.stringify({record,frames:encodeChunks(record)}));
"""
        result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True,
                                text=True, encoding='utf-8', check=True)
        cls.fixture = json.loads(result.stdout)

    def test_js_frames_to_python_to_csv_preserve_original_values(self):
        records = decoder.decode_packets(self.fixture['frames'][::-1])
        self.assertEqual(records, [self.fixture['record']])
        with tempfile.TemporaryDirectory(prefix='imu9p-synthetic-') as folder:
            decoder.write_records(records, folder)
            base = Path(folder) / records[0]['session_id']
            self.assertEqual(json.loads(base.with_suffix('.json').read_text(encoding='utf-8')), records[0])
            self.assertIn('0.123456789', base.with_suffix('.csv').read_text(encoding='utf-8-sig'))
            quality = json.loads(base.with_suffix('.quality.json').read_text(encoding='utf-8'))
            self.assertEqual(quality['callback_hz'], 50)
            self.assertIsNone(quality['hardware_sampling_hz'])

    def test_qr_images_and_video_recover_all_js_frames(self):
        import cv2
        params = cv2.QRCodeEncoder_Params()
        params.correction_level = cv2.QRCodeEncoder_CORRECT_LEVEL_M
        encoder = cv2.QRCodeEncoder_create(params)
        with tempfile.TemporaryDirectory(prefix='imu9p-synthetic-') as folder:
            paths = []
            video = Path(folder) / 'synthetic_qr.avi'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 5, (640, 640))
            self.assertTrue(writer.isOpened())
            try:
                for index, value in enumerate(self.fixture['frames']):
                    qr = encoder.encode(value)
                    qr = cv2.copyMakeBorder(qr, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=255)
                    qr = cv2.resize(qr, (640, 640), interpolation=cv2.INTER_NEAREST)
                    p = Path(folder) / f'synthetic_{index}.png'
                    cv2.imwrite(str(p), qr); paths.append(p)
                    for _ in range(5): writer.write(cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR))
            finally:
                writer.release()
            self.assertEqual(decoder.decode_packets(decoder.scan_media(paths)), [self.fixture['record']])
            self.assertEqual(decoder.decode_packets(decoder.scan_media([video])), [self.fixture['record']])


if __name__ == '__main__':
    unittest.main()
