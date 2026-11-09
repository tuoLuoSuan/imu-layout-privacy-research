
"""Drift-aware contact-padding sweep on the 16 held-out long recordings.

010 declares contact_padding=0.30 m, but the parent process never passes it to
the worker that decodes (Windows spawn re-imports multi_raw010), so a plain
monkeypatch of MR.OPTIONS is a no-op.  This driver sets the padding *inside*
each worker before calling the frozen episode function, so the declared decoder
option actually reaches M.decode_instances.
"""
import argparse, concurrent.futures, json, sys
from pathlib import Path
sys.path.insert(0, r"D:/Project/imu环境重建")
from analysis.layout import multi_raw010 as MR

def episode_pad(task):
    source, out, model, pad = task
    MR.OPTIONS["contact_padding"] = float(pad)
    return MR.episode((source, out, model))

def main(native, out, model, start, count, pads, workers):
    native, out, model = map(Path, (native, out, model))
    out.mkdir(parents=True, exist_ok=True)
    ids = list(range(start, start + count))
    summary = {}
    for pad in pads:
        dest = out / ("pad_%.2f" % pad)
        dest.mkdir(parents=True, exist_ok=True)
        tasks = [(str(native / ("multi-%05d.json" % i)), str(dest / ("multi-%05d" % i)), str(model), pad) for i in ids]
        records = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            for r in pool.map(episode_pad, tasks):
                records.append(r)
        raw = sum(1 for d in records for r in d["rows"] if r["arm"] == "raw_joint" and r["score"]["all_instances_hit"])
        truth = sum(1 for d in records for r in d["rows"] if r["arm"] == "truth_pose_truth_actions" and r["score"]["all_instances_hit"])
        f1 = sum(r["score"]["f1"] for d in records for r in d["rows"] if r["arm"] == "raw_joint") / max(1, len(records))
        summary["%.2f" % pad] = {"n": len(records), "raw_whole": raw, "truth_pose_whole": truth, "raw_f1": f1}
        print("pad %.2f -> raw %d/%d, truth %d/%d, f1 %.3f" % (pad, raw, len(records), truth, len(records), f1), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--start", type=int, default=11008)
    ap.add_argument("--count", type=int, default=16)
    ap.add_argument("--pads", nargs="+", type=float, default=[0.30, 0.45, 0.60])
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    main(a.native, a.out, a.model, a.start, a.count, a.pads, a.workers)
