
"""Truth-pose + predicted-actions arm: separate action errors from selection.

The frozen long-chain has raw 1/16 and truth-pose+truth-actions 7/16 (cap 128).
This arm feeds the *truth device trajectory* but keeps the *predicted* action
stream (phone five-class fused with the watch cabinet head), so the only
remaining error source is action recognition + joint selection.
"""
import argparse, concurrent.futures, json, sys
from pathlib import Path
sys.path.insert(0, r"D:/Project/imu环境重建")
from analysis.layout import multi_raw010 as MR

_LAST = {}
_ORIG_GENERATE = MR.generate
_ORIG_REPLAY = MR.replay

def _generate(*a, **k):
    phone = _ORIG_GENERATE(*a, **k)
    _LAST["truth"] = phone.get("truth")
    return phone

def _replay(t, A, G):
    path, R, info = _ORIG_REPLAY(t, A, G)
    truth = _LAST.get("truth")
    if truth is None:
        return path, R, info
    return truth["pos"][:, :2], truth["R"], info

def episode_truthpose(task):
    source, out, model, cap = task
    MR.generate = _generate
    MR.replay = _replay
    MR._LAST = _LAST
    original = MR.M.decode_instances
    def wrapped(*a, **kw):
        kw["candidate_limit"] = int(cap)
        return original(*a, **kw)
    MR.M.decode_instances = wrapped
    try:
        return MR.episode((source, out, model))
    finally:
        MR.M.decode_instances = original

def main(native, out, model, start, count, cap, workers):
    native, out, model = map(Path, (native, out, model))
    out.mkdir(parents=True, exist_ok=True)
    ids = list(range(start, start + count))
    tasks = [(str(native / ("multi-%05d.json" % i)), str(out / ("multi-%05d" % i)), str(model), cap) for i in ids]
    records = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(episode_truthpose, tasks):
            records.append(r)
    raw = sum(1 for d in records for r in d["rows"] if r["arm"] == "raw_joint" and r["score"]["all_instances_hit"])
    truth = sum(1 for d in records for r in d["rows"] if r["arm"] == "truth_pose_truth_actions" and r["score"]["all_instances_hit"])
    print("truth-pose + predicted-actions: %d/%d (truth+truth arm in same run: %d/%d)" % (raw, len(records), truth, len(records)), flush=True)
    (out / "summary.json").write_text(json.dumps({"n": len(records), "truth_pose_predicted_actions_whole": raw, "truth_pose_truth_actions_whole": truth, "cap": cap}, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True); ap.add_argument("--start", type=int, default=11008)
    ap.add_argument("--count", type=int, default=16); ap.add_argument("--cap", type=int, default=128)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    main(a.native, a.out, a.model, a.start, a.count, a.cap, a.workers)
