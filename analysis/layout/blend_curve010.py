
"""Trajectory-accuracy requirement curve for the long raw chain.

Blend the frozen front-end path with the truth path by alpha and reuse the same
events/decoder, so the only variable is trajectory error.  The curve answers how
accurate the front-end must be before the long chain becomes feasible at all.
"""
import argparse, concurrent.futures, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, r"D:/Project/imu环境重建")
from analysis.layout import multi_raw010 as MR

_LAST = {}
_ORIG_GENERATE = MR.generate
_ORIG_REPLAY = MR.replay
_ALPHA = 0.0

def _generate(*a, **k):
    phone = _ORIG_GENERATE(*a, **k)
    _LAST["truth"] = phone.get("truth")
    return phone

def _replay(t, A, G):
    path, R, info = _ORIG_REPLAY(t, A, G)
    truth = _LAST.get("truth")
    if truth is None or _ALPHA <= 0.0:
        return path, R, info
    from scipy.spatial.transform import Rotation
    truth_xy = np.asarray(truth["pos"])[:, :2]
    n = min(len(path), len(truth_xy), len(R))
    mixed = (1.0 - _ALPHA) * np.asarray(path[:n]) + _ALPHA * truth_xy[:n]
    # Rotations must be blended too: the body axis drives the cabinet yaw hypotheses,
    # so a truth path with predicted rotations is not a truth-pose arm.
    rv_pred = Rotation.from_matrix(np.asarray(R[:n])).as_rotvec()
    rv_truth = Rotation.from_matrix(np.asarray(truth["R"])[:n]).as_rotvec()
    mixed_R = Rotation.from_rotvec((1.0 - _ALPHA) * rv_pred + _ALPHA * rv_truth).as_matrix()
    return mixed, mixed_R, info

def episode_blend(task):
    source, out, model, alpha, cap = task
    global _ALPHA
    _ALPHA = float(alpha)
    MR.generate = _generate
    MR.replay = _replay
    original = MR.M.decode_instances
    def wrapped(*a, **kw):
        kw["candidate_limit"] = int(cap)
        return original(*a, **kw)
    MR.M.decode_instances = wrapped
    try:
        return MR.episode((source, out, model))
    finally:
        MR.M.decode_instances = original

def main(native, out, model, start, count, alphas, workers, cap=128):
    native, out, model = map(Path, (native, out, model))
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for alpha in alphas:
        dest = out / ("alpha_%s" % str(alpha).replace(".", "p"))
        dest.mkdir(parents=True, exist_ok=True)
        tasks = [(str(native / ("multi-%05d.json" % i)), str(dest / ("multi-%05d" % i)), str(model), alpha, cap) for i in range(start, start + count)]
        records = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            for r in pool.map(episode_blend, tasks):
                records.append(r)
        raw = [r for d in records for r in d["rows"] if r["arm"] == "raw_joint"]
        whole = sum(1 for r in raw if r["score"]["all_instances_hit"])
        ok = sum(1 for r in raw if r["prediction"].get("status") == "ok")
        f1 = float(np.mean([r["score"]["f1"] for r in raw]))
        summary[str(alpha)] = {"n": len(raw), "whole": whole, "ok": ok, "f1": f1}
        print("alpha %.2f -> whole %d/%d, ok %d, f1 %.3f" % (alpha, whole, len(raw), ok, f1), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True); ap.add_argument("--alphas", nargs="+", type=float, default=[0.0, 0.25, 0.5, 0.75, 1.0])
    ap.add_argument("--start", type=int, default=11008); ap.add_argument("--count", type=int, default=16)
    ap.add_argument("--workers", type=int, default=3); ap.add_argument("--cap", type=int, default=128)
    a = ap.parse_args()
    main(a.native, a.out, a.model, a.start, a.count, a.alphas, a.workers, getattr(a, "cap", 128))
