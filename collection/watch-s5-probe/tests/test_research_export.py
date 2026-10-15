import importlib.util
import json
from pathlib import Path
import unittest
import zlib

MODULE = Path(__file__).resolve().parents[1] / 'tools/decode_research_export.py'
spec = importlib.util.spec_from_file_location('research_export', MODULE)
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)
SID = '1000_abcdef'
PREFIX = f's5r_{SID}_'


def packets(value, part):
    text = json.dumps(value, separators=(',', ':'))
    pieces = [text[i:i+300] for i in range(0, len(text), 300)]
    crc = f'{zlib.crc32(text.encode("ascii")):08x}'
    return [f'IMUS5|2|{SID}|{part}|{i+1}|{len(pieces)}|{crc}|{piece}' for i, piece in enumerate(pieces)]


def example(tail=True):
    names = [PREFIX + 'head.json', PREFIX + 'b0000.json'] + ([PREFIX + 'tail.json'] if tail else [])
    objects = [dict(kind='manifest', schema_version=2, session_id=SID, files=names),
        dict(kind='head', schema_version=2, session_id=SID, started_epoch_ms=1000, row_fields=decoder.FIELDS,
             metadata=dict(time_source='Date.now_callback_arrival', hardware_timestamp=False,requested_interval='game')),
        dict(kind='block', schema_version=2, session_id=SID,index=0, rows=[[0,1000,1.234567890123,2,3,'visible'],[1,1020,4,5,6,'hidden']], events=[])]
    if tail:
        objects.append(dict(kind='tail',schema_version=2,session_id=SID,count=2,persisted=2,blocks=1,stopped_epoch_ms=1040,stop_reason='manual',quality={'warnings':[]}))
    return objects


def encode(objects):
    return [line for i, obj in enumerate(objects) for line in packets(obj, i)]


class ExportTests(unittest.TestCase):
    def test_raw_values_and_callback_rate(self):
        obj = decoder.decode_packets(encode(example()))
        self.assertEqual(obj['rows'][0][2],1.234567890123)
        self.assertEqual(obj['report']['callback_hz'],50)
        self.assertIsNone(obj['report']['hardware_sampling_hz'])
        self.assertEqual(obj['report']['hidden_samples'],1)

    def test_duplicate_identical_frames_are_harmless(self):
        lines = encode(example())
        self.assertEqual(decoder.decode_packets(lines+lines)['report']['samples'],2)

    def test_missing_page_and_corruption_refused(self):
        lines = encode(example())
        with self.assertRaises(ValueError):decoder.decode_packets(lines[1:])
        with self.assertRaises(ValueError):decoder.decode_packets(lines[:-1])
        lines[0] = lines[0][:-1] + 'X'
        with self.assertRaisesRegex(ValueError,'CRC'):decoder.decode_packets(lines)

    def test_sequence_tampering_refused_even_with_recalculated_crc(self):
        objects=example();objects[2]['rows'][1][0]=2
        with self.assertRaisesRegex(ValueError,'序号'):decoder.decode_packets(encode(objects))

    def test_count_tampering_refused(self):
        objects=example();objects[-1]['persisted']=3
        with self.assertRaisesRegex(ValueError,'尾文件'):decoder.decode_packets(encode(objects))

    def test_missing_tail_is_interrupted_not_passed(self):
        obj=decoder.decode_packets(encode(example(False)))
        self.assertEqual(obj['report']['session_status'],'interrupted')
        self.assertIn('missing_tail_unknown_interruption',obj['report']['warnings'])

    def test_path_traversal_and_missing_block_refused(self):
        objects=example();objects[0]['files'][1]='../../private.pem'
        with self.assertRaisesRegex(ValueError,'路径'):decoder.decode_packets(encode(objects))
        objects=example();objects[0]['files'][1]=PREFIX+'b0001.json'
        with self.assertRaisesRegex(ValueError,'连续性'):decoder.decode_packets(encode(objects))

    def test_empty_sealed_record_warns(self):
        objects=example();objects[2]['rows']=[];objects[-1]['count']=objects[-1]['persisted']=0
        self.assertIn('no_samples',decoder.decode_packets(encode(objects))['report']['warnings'])


if __name__=='__main__': unittest.main()
