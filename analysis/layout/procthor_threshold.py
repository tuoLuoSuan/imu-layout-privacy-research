"""External-room test of the frozen activity threshold on ProcTHOR houses.

The eleven-room threshold was measured on AI2-THOR exports.  This module asks
whether it survives a different generator: the ProcTHOR houses that were
natively created on the Ubuntu box (see procthor_scale.py).  Nothing about the
protocol changes; only the rooms do.

Conversion notes, all of them load-bearing:
  * sim_eval.load_scene only knows Bed / Desk / Chair / Cabinet-Shelf.  ProcTHOR
    storage here is a Dresser, so it is emitted as Cabinet: the role is the same
    ("storage with an operating face"), the asset class is not.  Any claim from
    these runs must say "ideal storage-face contact", not "opened a cabinet".
  * The room frame is the room polygon's axis-aligned bounds, shifted so the
    minimum corner is the origin.  Rectangular houses only: the decoder assumes
    a rectangle.
  * The start point is the reachable position nearest the room centroid.  This
    rule is fixed before any result is seen; it is not chosen per house.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from analysis.layout import activity_surface as AS, paths

ROLES = {"bed": "Bed", "desk": "Desk", "chair": "Chair", "cab": "Cabinet"}
DEFAULT_CELLS = ((0.94, 5), (0.95, 4), (0.95, 5), (0.95, 6), (0.98, 2))
TOL = 0.5
POLICY = "dispersed"


def _box(obj):
    b = obj.get("box_xz")
    if b:
        return [float(v) for v in b]
    pts = np.asarray(obj["axisAlignedBoundingBox"]["cornerPoints"], float)
    return [pts[:, 0].min(), pts[:, 2].min(), pts[:, 0].max(), pts[:, 2].max()]


def convert(manifest, native, out, limit=None, splits=None):
    """Write iTHOR-shaped FloorPlan files for the rectangular ProcTHOR houses."""
    rec = json.load(open(manifest, encoding="utf-8"))
    rows = [r for r in rec["rows"] if r.get("rectangular")]
    if splits:
        rows = [r for r in rows if r.get("source_split") in splits]
    if limit:
        rows = rows[:limit]
    os.makedirs(out, exist_ok=True)
    kept = []
    for r in rows:
        src = os.path.join(native, r["house_id"] + ".json")
        if not os.path.exists(src):
            continue
        d = json.load(open(src, encoding="utf-8"))
        idx = {o["id"]: o for o in d["objects"]}
        poly = np.asarray(r["floor_polygon_xz"], float)
        x0, x1 = float(poly[:, 0].min()), float(poly[:, 0].max())
        z0, z1 = float(poly[:, 1].min()), float(poly[:, 1].max())
        W, L = x1 - x0, z1 - z0
        objects = []
        ok = True
        for role, typ in ROLES.items():
            oid = r["selected_object_ids"].get(role)
            o = idx.get(oid)
            if o is None:
                ok = False
                break
            bx0, bz0, bx1, bz1 = _box(o)
            objects.append({"type": typ,
                            "center": {"x": (bx0 + bx1) / 2 - x0, "z": (bz0 + bz1) / 2 - z0},
                            "size": {"x": bx1 - bx0, "z": bz1 - bz0}})
        if not ok:
            continue
        reach = np.asarray([[p["x"], p["z"]] for p in d["reachable_positions"]], float)
        if not len(reach):
            continue
        centre = np.array([(x0 + x1) / 2, (z0 + z1) / 2])
        s = reach[int(np.argmin(np.linalg.norm(reach - centre, axis=1)))]
        scene = {"floor": [W / 2, L / 2, W, L], "objects": objects,
                 "agent": {"x": float(s[0] - x0), "z": float(s[1] - z0)}}
        with open(os.path.join(out, "FloorPlan_%s.json" % r["house_id"]), "w", encoding="utf-8") as fh:
            json.dump(scene, fh, ensure_ascii=False)
        kept.append({"house_id": r["house_id"], "split": r["source_split"],
                     "room_type": r.get("room_type"), "W": W, "L": L, "S": scene["agent"]})
    return kept


def _hit(row):
    if not row.get("executable"):
        return False
    return all(o["joint_error_m"] is not None and o["joint_error_m"] <= TOL
               for o in row["objects"].values())


def run(manifest, native, work, out, cells=DEFAULT_CELLS, limit=None, splits=None, policy=POLICY):
    kept = convert(manifest, native, os.path.join(work, "scenes"), limit=limit, splits=splits)
    old_thor, old_cov, old_vis = paths.THOR, AS.COVERAGES, AS.VISITS
    paths.THOR = os.path.join(work, "scenes")
    AS.COVERAGES = tuple(sorted({c for c, _ in cells}))
    AS.VISITS = tuple(sorted({v for _, v in cells}))
    raw = os.path.join(work, "surface-raw.json")
    try:
        AS.run(raw)
    finally:
        paths.THOR, AS.COVERAGES, AS.VISITS = old_thor, old_cov, old_vis
    rows = [r for r in json.load(open(raw, encoding="utf-8"))["rows"]
            if r.get("status") != "invalid_geometry"]
    summary = []
    for cov, vis in cells:
        part = [r for r in rows if r["policy"] == policy and r["visits"] == vis
                and r["coverage_target"] == cov]
        ex = [r for r in part if r.get("executable")]
        summary.append({"coverage": cov, "visits": vis,
                        "hits": sum(1 for r in part if _hit(r)),
                        "rooms": len(part), "executable": len(ex),
                        "rate": (sum(1 for r in part if _hit(r)) / len(part)) if part else None})
    by_house = {}
    for r in rows:
        if r["policy"] != policy:
            continue
        by_house.setdefault(r["scene"], {})["%0.2f|%d" % (r["coverage_target"], r["visits"])] = _hit(r)
    record = {"scope": "Frozen activity threshold replayed on ProcTHOR rectangular houses",
              "cells": [list(c) for c in cells], "policy": policy, "tolerance_m": TOL,
              "conversion": {"roles": ROLES, "storage": "Dresser emitted as Cabinet role",
                             "start": "reachable position nearest the room centroid",
                             "frame": "room polygon axis-aligned bounds, min corner at origin"},
              "houses": len(kept), "house_meta": kept,
              "summary": summary, "per_house": by_house, "raw_path": raw}
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
    return record


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--native", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--splits", nargs="*", default=None)
    a = ap.parse_args()
    rec = run(a.manifest, a.native, a.work, a.output, limit=a.limit, splits=a.splits)
    print("houses", rec["houses"])
    for s in rec["summary"]:
        print("cov %.2f vis %d : %d/%d (exec %d)" % (s["coverage"], s["visits"], s["hits"], s["rooms"], s["executable"]))
