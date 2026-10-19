import csv,json,tempfile,unittest
from pathlib import Path
from analysis.phone_pdr.session import load_session,write_diagnostic,validated_output

class SessionSafety(unittest.TestCase):
    def fixture(self,root,times=(1000000000,1010000000,1020000000)):
        metadata={'app_version':'synthetic','units':{'accelerometer':'m/s^2 including gravity','gyroscope':'rad/s'},'written':[len(times),len(times)]}
        (root/'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
        for name in ['accelerometer','gyroscope']:
            with (root/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
                w=csv.writer(f);w.writerow(['sequence','sensor_timestamp_ns','x','y','z'])
                for i,t in enumerate(times,1):w.writerow([i,t,0,0,9.80665 if name=='accelerometer' else 0])

    def test_native_sequence_is_one_based(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p)
            a,g,source=load_session(p)
            self.assertEqual((len(a),len(g)),(3,3))
            self.assertEqual(source['app_version'],'synthetic')

    def test_missing_native_sequence_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p)
            f=p/'accelerometer.csv';f.write_text(f.read_text().replace('2,1010000000','4,1010000000'))
            with self.assertRaisesRegex(ValueError,'sequence'):load_session(p)

    def test_duplicate_event_time_is_rejected_not_sorted_or_repaired(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p,(100,100,200))
            with self.assertRaisesRegex(ValueError,'timestamp'):load_session(p)

    def test_nan_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p)
            f=p/'accelerometer.csv';f.write_text(f.read_text().replace('9.80665','nan'))
            with self.assertRaisesRegex(ValueError,'finite'):load_session(p)

    def test_missing_units_are_not_inferred_from_gravity_magnitude(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p);m=p/'metadata.json';v=json.loads(m.read_text());v['units']={};m.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,'units'):load_session(p)

    def test_existing_directory_and_accident_carrier_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);e=p/'existing';e.mkdir();f=e/'original.txt';f.write_bytes(b'ORIGINAL')
            with self.assertRaises(FileExistsError):write_diagnostic(e,{}, {})
            self.assertEqual(f.read_bytes(),b'ORIGINAL')
            with self.assertRaises(FileExistsError):write_diagnostic(f,{}, {})
            self.assertEqual(f.read_bytes(),b'ORIGINAL')

    def test_parent_traversal_cannot_escape_output_root(self):
        with tempfile.TemporaryDirectory() as d:
            allowed=Path(d)/'output'
            with self.assertRaisesRegex(ValueError,'output root'):
                validated_output(allowed/'..'/'raw'/'new',allowed)
            self.assertFalse((Path(d)/'raw').exists())

if __name__=='__main__':unittest.main()
