"""Fine-grained re-test of the activity threshold around the reported 95%/6 cell.

The published surface sampled independent visits at 0/1/2/3/6/9/12/18 and walk
coverage at 0/10/25/40/55/70/85/90/95/98/100%.  Two consecutive samples are far
apart exactly where the boundary lies, so "six visits" was never compared against
four or five.  This module re-runs the same benchmark on a grid that resolves
that gap and reports, per room, which visit count first resolves all four
furniture centres.

It reuses analysis.layout.activity_surface with an explicit grid argument.
The protocol, contact rules and decoder stay identical; no global mutation.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from analysis.layout import activity_surface as AS, paths

COVERAGES = (0.85, 0.88, 0.90, 0.92, 0.94, 0.95, 0.96, 0.98, 1.00)
VISITS = (2, 3, 4, 5, 6)
NORMAL = ("FloorPlan301", "FloorPlan302", "FloorPlan304", "FloorPlan305", "FloorPlan307",
          "FloorPlan308", "FloorPlan310", "FloorPlan312", "FloorPlan313", "FloorPlan318",
          "FloorPlan320")
EXTENDED = NORMAL + ("FloorPlan303", "FloorPlan316")
TOL = 0.5


def _hit(row):
    if not row.get("executable"):
        return False
    objects=row.get('objects',{})
    return set(objects)=={'bed','desk','cab','chair'} and all(
        o.get('joint_error_m') is not None and np.isfinite(o['joint_error_m'])
        and o['joint_error_m'] <= TOL for o in objects.values())


def summarise(rows, rooms):
    """Per-cell hits over an explicit room list; the denominator is the room list."""
    grid = {}
    for policy in AS.POLICIES:
        for vis in VISITS:
            for cov in COVERAGES:
                part = [r for r in rows if r["policy"] == policy and r["visits"] == vis
                        and r["coverage_target"] == cov and r["scene"] in rooms]
                if len({r['scene'] for r in part})!=len(part):
                    raise ValueError('Duplicate room in activity cell')
                grid["%s|%.2f|%d" % (policy, cov, vis)] = {
                    "hits": sum(1 for r in part if _hit(r)),
                    "rooms": len(rooms),
                    "missing": len(rooms)-len(part),
                    "censored": sum(not r.get('executable',False) for r in part),
                    "executable": sum(1 for r in part if r.get("executable")),
                }
    return grid


def per_room(rows, rooms):
    out = []
    for name in rooms:
        rec = {"scene": name}
        for policy in AS.POLICIES:
            first = None
            for vis in VISITS:
                part = [r for r in rows if r["policy"] == policy and r["visits"] == vis
                        and r["coverage_target"] == 0.95 and r["scene"] == name]
                if part and _hit(part[0]):
                    first = vis
                    break
            rec[policy] = first
        out.append(rec)
    return out


def cabinet_mechanism(rows, rooms):
    """Which contact made the difference: cabinet error at four versus five visits."""
    out = []
    for name in rooms:
        rec = {"scene": name}
        for vis in (4, 5):
            part = [r for r in rows if r["policy"] == "dispersed" and r["visits"] == vis
                    and r["coverage_target"] == 0.95 and r["scene"] == name]
            if not part:
                rec[str(vis)] = None
                continue
            row = part[0]
            span = row["contact_span_xy"].get("cab")
            rec[str(vis)] = {
                "cab_error_m": row["objects"]["cab"]["joint_error_m"],
                "cab_contact_span_m": span,
                "n_cab_contacts": event_count(row, 'cab'),
                "count_source": 'recorded' if 'event_counts' in row else 'reconstructed from archived fixed class cycle',
                "executable": bool(row.get("executable")),
            }
        out.append(rec)
    return out


def event_count(row, obj):
    if 'event_counts' in row:return row['event_counts'].get(obj,0)
    available=[o for o in ['chair','cab','bed'] if o in row['contact_classes']]
    return sum(available[i%len(available)]==obj for i in range(row['visits'])) if available else 0


def frontier(grid, rooms_count, target=0.8):
    """First passing cell per visit count, and the Pareto set of passing cells."""
    first = {}
    passing = []
    for vis in VISITS:
        for cov in COVERAGES:
            cell = grid["dispersed|%.2f|%d" % (cov, vis)]
            if cell['rooms']!=rooms_count:raise ValueError('Cohort denominator changed')
            if cell["rooms"] and not cell.get('missing',0) and cell["hits"] / cell["rooms"] >= target:
                first[str(vis)] = cov
                passing.append({"coverage": cov, "visits": vis,
                                "hits": cell["hits"], "rooms": cell["rooms"]})
                break
    pareto = [p for p in passing
              if not any(q["coverage"] <= p["coverage"] and q["visits"] <= p["visits"] and q != p
                         for q in passing)]
    for p in pareto:
        p['status']='tested_grid_only'
        p['higher_coverage_samples']=sum(c>p['coverage'] for c in COVERAGES)
        p['higher_visit_samples']=sum(n>p['visits'] for n in VISITS)
        p['upper_grid_edge']=p['coverage']==max(COVERAGES) or p['visits']==max(VISITS)
    return {"first_pass_per_visit_count": first, "passing_cells": passing, "pareto": pareto,
            'interpretation':'Empirical minima on sampled grid only; no between-sample or larger-budget guarantee'}


def run(output, workdir=None):
    workdir = workdir or os.path.join(paths.DATA, "layout-recon", "threshold-fine-raw")
    os.makedirs(workdir, exist_ok=True)
    raw = os.path.join(workdir, "activity-surface-fine-raw.json")
    AS.run(raw,coverages=COVERAGES,visits=VISITS)
    with open(raw, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = [r for r in data["rows"] if r.get("status") != "invalid_geometry"]
    record = {
        "scope": "Fine re-test of the activity threshold around the reported 95%/6 cell",
        "protocol": {"coverages": list(COVERAGES), "visits": list(VISITS),
                     "policies": list(AS.POLICIES), "tolerance_m": TOL,
                     "note": "Same protocol as activity_surface; only the sampled grid changed."},
        "grid_normal": summarise(rows, NORMAL),
        "grid_extended": summarise(rows, EXTENDED),
        "frontier_normal_at_80pct": frontier(summarise(rows, NORMAL), len(NORMAL)),
        "per_room_first_pass_at_95pct": per_room(rows, EXTENDED),
        "cabinet_at_4_vs_5_visits": cabinet_mechanism(rows, NORMAL),
        "raw_path": raw,
    }
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
    return record


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="analysis/layout/threshold_fine.json")
    ap.add_argument("--workdir")
    args = ap.parse_args()
    rec = run(args.output, args.workdir)
    g = rec["grid_normal"]
    print("coverage " + " ".join("%6.2f" % c for c in COVERAGES))
    for vis in VISITS:
        cells = [g["dispersed|%.2f|%d" % (c, vis)] for c in COVERAGES]
        print("vis %2d   " % vis + " ".join("%4d/%d" % (x["hits"], x["rooms"]) for x in cells))
    print("frontier:", rec["frontier_normal_at_80pct"]["first_pass_per_visit_count"])
    print("pareto:", rec["frontier_normal_at_80pct"]["pareto"])
