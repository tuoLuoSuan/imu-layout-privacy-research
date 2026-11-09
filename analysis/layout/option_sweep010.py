
"""Sweep one declared decoder option on the 16 held-out long recordings.

Same frozen pipeline as multi_raw010; only the named OPTIONS key changes, and it
is set inside the worker (Windows spawn re-imports the module, so a parent-side
mutation would be a no-op).
"""
import argparse, concurrent.futures, json, sys
from pathlib import Path
sys.path.insert(0, r"D:/Project/imu环境重建")
from analysis.layout import multi_raw010 as MR

def episode_opt(task):
    source, out, model, key, value = task
    MR.OPTIONS[key] = float(value) if key != "walk_excluded_objects" else value
    return MR.episode((source, out, model))

def main(native, out, model, start, count, key, values, workers):
    native, out, model = map(Path, (native, out, model))
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for value in values:
        dest = out / ("%s_%s" % (key, str(value).replace(".", "p")))
        dest.mkdir(parents=True, exist_ok=True)
        tasks = [(str(native / ("multi-%05d.json" % i)), str(dest / ("multi-%05d" % i)), str(model), key, value) for i in range(start, start + count)]
        records = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            for r in pool.map(episode_opt, tasks):
                records.append(r)
        raw = [r for d in records for r in d["rows"] if r["arm"] == "raw_joint"]
        truth = [r for d in records for r in d["rows"] if r["arm"] == "truth_pose_truth_actions"]
        whole = sum(1 for r in raw if r["score"]["all_instances_hit"])
        ok = sum(1 for r in raw if r["prediction"].get("status") == "ok")
        twhole = sum(1 for r in truth if r["score"]["all_instances_hit"])
        summary[str(value)] = {"n": len(raw), "raw_whole": whole, "raw_ok": ok, "truth_whole": twhole}
        print("%s=%s -> raw %d/%d (ok %d), truth %d/%d" % (key, value, whole, len(raw), ok, twhole, len(truth)), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True); ap.add_argument("--key", required=True)
    ap.add_argument("--values", nargs="+", type=float, required=True)
    ap.add_argument("--start", type=int, default=11008); ap.add_argument("--count", type=int, default=16)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    main(a.native, a.out, a.model, a.start, a.count, a.key, a.values, a.workers)
