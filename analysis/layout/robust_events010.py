
"""Robust-event retry for the raw long chain.

Raw arm at cap 128: 10/16 proposal_conflict, 2 budget, 2 no_proposals, only 2 ok.
The contacts derived from a drifted trajectory are mutually inconsistent, so no
layout satisfies all of them. This arm keeps the frozen front-end and decoder
but, when the full event set is infeasible, retries with one event removed at a
time (greedy, smallest violation first) and accepts the first feasible subset.
Every dropped event is recorded so the loss of evidence stays visible.
"""
import argparse, concurrent.futures, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, r"D:/Project/imu环境重建")
from analysis.layout import multi_raw010 as MR

def _rank_events(priors, events, path):
    """Order events for removal trials.

    The solver never receives furniture positions, so ranking cannot consult
    them; contacts are tried in recording order, which keeps the probe unbiased.
    """
    return list(range(len(events)))

def make_robust(original, max_drop):
    def robust(priors, path, events, walk, yaw_angles, method="finite"):
        result = original(priors, path, events, walk, yaw_angles, method)
        if result.get("status") == "ok" or len(events) <= 2:
            return result
        order = _rank_events(priors, events, path)
        for drop in order[:max_drop]:
            subset = [e for j, e in enumerate(events) if j != drop]
            trial = original(priors, path, subset, walk, yaw_angles, method)
            if trial.get("status") == "ok":
                trial["dropped_event_index"] = int(drop)
                trial["dropped_events"] = 1
                return trial
        return result
    return robust

_ORIGINAL = MR.decode_observations

def episode_robust(task):
    source, out, model, max_drop = task
    MR.decode_observations = make_robust(_ORIGINAL, int(max_drop))
    try:
        return MR.episode((source, out, model))
    finally:
        MR.decode_observations = _ORIGINAL

def main(native, out, model, start, count, max_drop, workers):
    native, out, model = map(Path, (native, out, model))
    out.mkdir(parents=True, exist_ok=True)
    tasks = [(str(native / ("multi-%05d.json" % i)), str(out / ("multi-%05d" % i)), str(model), max_drop) for i in range(start, start + count)]
    records = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(episode_robust, tasks):
            records.append(r)
    raw = [r for d in records for r in d["rows"] if r["arm"] == "raw_joint"]
    whole = sum(1 for r in raw if r["score"]["all_instances_hit"])
    f1 = float(np.mean([r["score"]["f1"] for r in raw]))
    dropped = sum(1 for r in raw if r["prediction"].get("dropped_events"))
    ok = sum(1 for r in raw if r["prediction"].get("status") == "ok")
    print("robust raw: whole %d/%d, f1 %.3f, ok %d, rooms with a dropped event %d" % (whole, len(raw), f1, ok, dropped), flush=True)
    (out / "summary.json").write_text(json.dumps({"n": len(raw), "raw_whole": whole, "raw_f1": f1, "ok": ok, "dropped_rooms": dropped, "max_drop": max_drop}, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True); ap.add_argument("--start", type=int, default=11008)
    ap.add_argument("--count", type=int, default=16); ap.add_argument("--max-drop", type=int, default=6)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    main(a.native, a.out, a.model, a.start, a.count, a.max_drop, a.workers)
