
"""Candidate-limit probe on the 16 frozen long recordings.

Truth-pose breakdown at the declared 0.30 m pad: 5/16 exact, 6/16 miss exactly
one object, 5/16 are proposal conflicts.  This probes whether the 64-candidate
cap is what creates those conflicts/misses, by forcing a larger cap inside the
worker (monkeypatch survives spawn because it runs in the child).
"""
import argparse, concurrent.futures, json, sys
from pathlib import Path
sys.path.insert(0, r"D:/Project/imu环境重建")
from analysis.layout import multi_raw010 as MR

def episode_cap(task):
    source, out, model, cap = task
    original = MR.M.decode_instances
    def wrapped(*a, **kw):
        kw["candidate_limit"] = int(cap)
        return original(*a, **kw)
    MR.M.decode_instances = wrapped
    try:
        return MR.episode((source, out, model))
    finally:
        MR.M.decode_instances = original

def main(native, out, model, start, count, caps, workers):
    native, out, model = map(Path, (native, out, model))
    out.mkdir(parents=True, exist_ok=True)
    ids = list(range(start, start + count))
    summary = {}
    for cap in caps:
        dest = out / ("cap_%d" % cap); dest.mkdir(parents=True, exist_ok=True)
        tasks = [(str(native / ("multi-%05d.json" % i)), str(dest / ("multi-%05d" % i)), str(model), cap) for i in ids]
        records = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            for r in pool.map(episode_cap, tasks):
                records.append(r)
        raw = sum(1 for d in records for r in d["rows"] if r["arm"] == "raw_joint" and r["score"]["all_instances_hit"])
        truth = sum(1 for d in records for r in d["rows"] if r["arm"] == "truth_pose_truth_actions" and r["score"]["all_instances_hit"])
        conf = sum(1 for d in records for r in d["rows"] if r["arm"] == "truth_pose_truth_actions" and r["prediction"].get("status") != "ok")
        summary[str(cap)] = {"n": len(records), "raw_whole": raw, "truth_pose_whole": truth, "truth_conflicts": conf}
        print("cap %d -> raw %d/%d, truth %d/%d, conflicts %d" % (cap, raw, len(records), truth, len(records), conf), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True); ap.add_argument("--start", type=int, default=11008)
    ap.add_argument("--count", type=int, default=16); ap.add_argument("--caps", nargs="+", type=int, default=[64, 128])
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    main(a.native, a.out, a.model, a.start, a.count, a.caps, a.workers)
