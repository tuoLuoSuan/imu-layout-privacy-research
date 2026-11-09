"""Wall-adjacency prior for desks: a measurable property of this room family.

Every desk in the 5,000-room native set sits within 0.15 m of a wall (median gap
0.104 m; beds 100%, cabinets 99.5%, chairs 0%).  That is a declared property of
the controlled generator, like the rectangular room and the known inventory --
not a measured interaction.  This module tests whether adding it as a hard
filter on the desk candidate pool moves the desk recall that currently caps the
whole-room endpoint.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M
from .selection_diagnostics import rerank_pools
from .exp_walk_range import coverage_route, survey_prefixes

TOL = 0.5


def wall_gap(boxes, room):
    w, l = room
    gap = np.minimum(np.minimum(boxes[:, 0], w - boxes[:, 2]),
                     np.minimum(boxes[:, 1], l - boxes[:, 3]))
    return gap


def _filter_pool(pools, room, tol):
    out = {}
    for name, (boxes, masks, energy) in pools.items():
        if M.category(name) == "desk" and tol is not None:
            gap = wall_gap(boxes, room)
            keep = (gap <= tol) & (gap >= -0.05)
            if keep.any():
                boxes, masks, energy = boxes[keep], masks[keep], energy[keep]
        out[name] = (boxes, masks, energy)
    return out


def one(task):
    native, observations, out = map(Path, task)
    scene = M.load_native(native)
    rec = json.loads(observations.read_text(encoding="utf-8"))
    row = next(r for r in rec["rows"] if r["method"] == "generic"
               and r["coverage"] == 1.0 and r["visits"] == 14)
    ep = coverage_route(scene)
    ratio = len(ep["reachable_ids"]) / len(ep["free_ids"])
    path = survey_prefixes(ep, [1 / ratio])[0]["path"]
    cache = {}
    original = M._constraint_search
    arms = [("none", None), ("wall_0.15", 0.15), ("wall_0.30", 0.30)]
    rows = []
    for name, tol in arms:
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
        rows.append({"arm": name, "status": r["status"], "score": M.score_instances(r["boxes"], scene["gt"])})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"scene": scene["scene"], "rows": rows}), encoding="utf-8")
    return rows


def run(native, observations, out, workers=10, limit=None):
    native, observations, out = map(Path, (native, observations, out))
    files = sorted(native.glob("*.json"))
    if limit:
        files = files[:limit]
    allrows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for rows in pool.map(one, [(str(f), str(observations / f.name), str(out / "rooms" / f.name)) for f in files]):
            allrows.extend(rows)
    summary = {}
    for arm in sorted({r["arm"] for r in allrows}):
        rr = [r for r in allrows if r["arm"] == arm]
        summary[arm] = {
            "n_rooms": len(rr),
            "whole_hits": sum(bool(r["score"]["all_instances_hit"]) for r in rr),
            "f1": float(np.mean([r["score"]["f1"] for r in rr])),
            "desk_recall": sum(r["score"]["per_class"]["desk"]["tp"] for r in rr)
                           / max(1, sum(r["score"]["per_class"]["desk"]["n_truth"] for r in rr)),
        }
    result = {"scope": __doc__, "condition": "100% coverage / 14 visits on historical 1000 rooms",
              "arms": summary}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True)
    ap.add_argument("--observations", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    print(json.dumps(run(Path(a.native), Path(a.observations), Path(a.out), a.workers, a.limit), indent=1))
