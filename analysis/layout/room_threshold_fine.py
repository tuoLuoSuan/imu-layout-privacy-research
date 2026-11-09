
"""Fine threshold: generated events at 100% coverage, wall prior on the desk pool."""
import argparse, concurrent.futures, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, r"D:/Project/imu环境重建")
from analysis.layout import multi_instance as M
from analysis.layout.selection_diagnostics import rerank_pools
from analysis.layout.exp_walk_range import coverage_route, survey_prefixes
from analysis.layout.desk_wall_audit import _filter_pool

def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)

def one(task):
    f, out, counts, tol = task
    scene = M.load_native(f)
    ep = coverage_route(scene); ratio = len(ep["reachable_ids"]) / len(ep["free_ids"])
    path = survey_prefixes(ep, [1.0 / ratio])[0]["path"]
    cache = {}; rows = []
    for count in counts:
        events = M.event_sequence(scene, path, count)
        original = M._constraint_search
        def select(inventory, pools, targets, c, tol=tol):
            ranked = rerank_pools(pools, [scene["W"], scene["L"]], path, "outline")
            ranked = _filter_pool(ranked, (scene["W"], scene["L"]), tol)
            return original(inventory, ranked, targets, c)
        M._constraint_search = select
        try:
            r = M.decode_instances([scene["W"], scene["L"]], scene["inventory"], events, path, proposal_cache=cache)
        finally:
            M._constraint_search = original
        s = M.score_instances(r["boxes"], scene["gt"])
        rows.append({"count": count, "whole": bool(s["all_instances_hit"]), "f1": float(s["f1"]),
                     "desk_tp": s["per_class"]["desk"]["tp"], "desk_n": s["per_class"]["desk"]["n_truth"]})
    return rows

def main(native, out, counts, limit, workers, tol):
    files = sorted(Path(native).glob("*.json"))
    if limit: files = files[:limit]
    allrows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for rows in pool.map(one, [(str(f), None, counts, tol) for f in files]):
            allrows.extend(rows)
    res = []
    for c in counts:
        rr = [r for r in allrows if r["count"] == c]
        k = sum(r["whole"] for r in rr); lo, hi = wilson(k, len(rr))
        res.append({"visits": c, "whole": k, "n": len(rr), "rate": k / len(rr), "wilson95": [lo, hi],
                    "f1": float(np.mean([r["f1"] for r in rr])),
                    "desk": sum(r["desk_tp"] for r in rr) / max(1, sum(r["desk_n"] for r in rr))})
        print("vis %2d: %d/%d = %.1f%% [%.1f, %.1f]  F1 %.2f  desk %.1f%%" % (
            c, k, len(rr), 100 * k / len(rr), 100 * lo, 100 * hi, 100 * res[-1]["f1"], 100 * res[-1]["desk"]))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({"counts": res, "tol": tol, "n_rooms": len(files)}, indent=1), encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--counts", nargs="+", type=int, default=[12, 13, 15, 20])
    ap.add_argument("--limit", type=int, default=None); ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--tol", type=float, default=0.15)
    a = ap.parse_args()
    main(a.native, a.out, a.counts, a.limit, a.workers, a.tol)
