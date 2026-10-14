import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from check_export import verify


class ValidatorTests(unittest.TestCase):
    def fixture(self, gap=0, tamper=False, bad_count=False):
        start = 10_000_000_000
        rows = []
        for i in range(3000):
            t = start + i * 20_000_000 + (gap if i >= 1500 else 0)
            rows.append(f"{i+1},{t},{t},{t},0,0,9.8,3\n")
        data = ("sequence,sensor_timestamp_ns,received_elapsed_realtime_ns,writer_dequeued_elapsed_realtime_ns,x,y,z,accuracy\n" + "".join(rows)).encode()
        meta = dict(format_version=1, session_id="synthetic", completion_state="complete", collection_start_elapsed_ns=start,
                    stop_elapsed_ns=start+60_000_000_000+gap, states=[dict(elapsed_ns=start, state="foreground")],
                    received=[2999 if bad_count else 3000,3000], enqueued=[3000,3000], written=[3000,3000], confirmed=[3000,3000], dropped=[0,0])
        files = {"accelerometer.csv": data, "gyroscope.csv": data, "metadata.json": json.dumps(meta).encode(),
                 "anchors.csv": b"planned_elapsed_ns,elapsed_before_ns,wall_ms,elapsed_after_ns\n", "integrity_report.json": b'{}'}
        manifest = dict(format_version=1, files=[dict(path=n, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), **({"rows":3000} if n in ("accelerometer.csv","gyroscope.csv") else {})) for n,b in files.items()])
        files["manifest.json"] = json.dumps(manifest).encode()
        if tamper:
            files["accelerometer.csv"] += b"changed\n"
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name)/"synthetic.zip"
        with zipfile.ZipFile(path,"w") as z:
            for n,b in files.items():z.writestr(n,b)
        return path

    def test_hash_changes_are_rejected(self):
        self.assertTrue(any("checksum" in x for x in verify(self.fixture(tamper=True))["failures"]))

    def test_a_large_gap_is_not_hidden_by_median(self):
        self.assertTrue(any("over_1s" in x for x in verify(self.fixture(gap=1_100_000_000))["failures"]))

    def test_metadata_count_must_match_raw_rows(self):
        self.assertTrue(any("count" in x for x in verify(self.fixture(bad_count=True))["failures"]))

    def test_external_review_is_required_even_for_continuous_data(self):
        r=verify(self.fixture())
        self.assertFalse(r["failures"])
        self.assertEqual("pending_external_review",r["overall"])

if __name__ == "__main__":
    unittest.main()
