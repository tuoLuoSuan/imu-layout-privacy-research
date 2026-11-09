"""Room-recovery threshold: whole-room success versus the activity budget.

Coverage and visits are both swept.  The desk pool is filtered by the declared
wall-adjacency property of this room family (every desk sits within 0.15 m of a
wall; beds 100%, cabinets 99.5%, chairs 0%), which is a property of the
generator, not a measured interaction and not truth.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M
from .selection_diagnostics import rerank_pools
from .exp_walk_range import coverage_route, survey_prefixes
from .desk_wall_audit import _filter_pool

WALL_TOL = 0.15


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def one(task):
    native, observations, out, cells, tol = task
    native, observations, out = map(Path, (native, observations, out))
    scene = M.load_native(native)
    rec = json.loads(observations.read_text(encoding="utf-8"))
    ep = coverage_route(scene)
    ratio = len(ep["reachable_ids"]) / len(ep["free_ids"])
    cache = {}
    rows = []
    for cov, vis in cells:
        row = next((r for r in rec["rows"] if r["method"] == "generic"
                    and abs(r["coverage"] - cov) < 1e-9 and r["visits"] == vis), None)
        if row is None:
            continue
        path = survey_prefixes(ep, [cov / ratio])[0]["path"]
        original = M._constraint_search

        def select(inventory, pools, targets, counts, tol=tol):
            ranked = rerank_pools(pools, [scene["W"], scene["L"]], path, "outline")
            ranked = _filter_pool(ranked, (scene["W"], scene["L"]), tol)
            return original(inventory, ranked, targets, counts)

        M._constraint_search = select
        try:
            r = M.decode_instances([scene["W"], scene["L"]], scene["inventory"],
                                   row["events"], path, proposal_cache=cache)
        finally:
            M._constraint_search = original
        rows.append({"coverage": cov, "visits": vis, "status": r["status"],
                     "score": M.score_instances(r["boxes"], scene["gt"])})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"scene": scene["scene"], "rows": rows}), encoding="utf-8")
    return rows


def run(native, observations, out, cells, limit=None, workers=10, tol=WALL_TOL):
    native, observations, out = map(Path, (native, observations, out))
    files = sorted(native.glob("*.json"))
    if limit:
        files = files[:limit]
    allrows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for rows in pool.map(one, [(str(f), str(observations / f.name), str(out / "rooms" / f.name), cells, tol) for f in files]):
            allrows.extend(rows)
    summary = []
    for cov, vis in cells:
        rr = [r for r in allrows if abs(r["coverage"] - cov) < 1e-9 and r["visits"] == vis]
        if not rr:
            continue
        hits = sum(bool(r["score"]["all_instances_hit"]) for r in rr)
        lo, hi = wilson(hits, len(rr))
        summary.append({
            "coverage": cov, "visits": vis, "n_rooms": len(rr), "whole_hits": hits,
            "whole_rate": hits / len(rr), "wilson95": [lo, hi],
            "f1": float(np.mean([r["score"]["f1"] for r in rr])),
            "desk_recall": sum(r["score"]["per_class"]["desk"]["tp"] for r in rr)
                           / max(1, sum(r["score"]["per_class"]["desk"]["n_truth"] for r in rr)),
        })
    result = {"scope": __doc__, "wall_tol_m": tol, "n_rooms": len(files), "summary": summary}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True)
    ap.add_argument("--observations", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cells", nargs="+", default=["1.0:8", "1.0:11", "1.0:12", "1.0:13", "1.0:14", "0.95:14"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--tol", type=float, default=WALL_TOL)
    a = ap.parse_args()
    cells = []
    for item in a.cells:
        c, v = item.split(":")
        cells.append((float(c), int(v)))
    res = run(Path(a.native), Path(a.observations), Path(a.out), cells, a.limit, a.workers, a.tol)
    for s in res["summary"]:
        print("cov %.2f vis %2d: %d/%d = %.1f%% [%.1f, %.1f]  F1 %.2f  desk %.1f%%" % (
            s["coverage"], s["visits"], s["whole_hits"], s["n_rooms"], 100 * s["whole_rate"],
            100 * s["wilson95"][0], 100 * s["wilson95"][1], 100 * s["f1"], 100 * s["desk_recall"]))
