"""Controlled ablation on the contact evidence, with route and coverage held fixed.

The interval model says the residual support of an object is fixed by the *geometry*
of its contact constraint and by the span of its anchors, not by how much floor the
walker covered.  This module keeps one measured route fixed, then edits exactly one
class of contact evidence at a time: remove it, collapse its anchors onto their mean
(span -> 0, event count preserved), or keep a single anchor.  Coverage is identical
across arms by construction.

Everything here is the geometric oracle study, not raw IMU.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from . import evidence_space as ES
from . import sim_eval as SE
from . import paths
from .activity_experiment import contact_targets, route_episode

SEED = 17031
BUDGETS = (32.0, 96.0)
TOL = 0.5
PAD = 0.20
OBJECTS = ("bed", "desk", "cab", "chair")
ARMS = ("full", "drop", "collapse", "single")


def _scenes():
    return [s for f in sorted(Path(paths.THOR).glob("FloorPlan*.json")) if (s := SE.load_scene(str(f)))]


def _edits(events):
    """Evidence variants that keep the route (hence the coverage) identical."""
    out = {"full": list(events)}
    for obj in OBJECTS:
        mine = [e for e in events if e["object"] == obj]
        if not mine:
            continue
        out["drop:" + obj] = [e for e in events if e["object"] != obj]
        mean = np.mean([np.asarray(e["pos"], float) for e in mine], axis=0)
        out["collapse:" + obj] = [e for e in events if e["object"] != obj] + [
            {"object": obj, "pos": mean.tolist(),
             "available_distance_m": mine[-1]["available_distance_m"],
             "copies": len(mine), "span_m": 0.0}
        ]
    return out


def _measure(scene, banks, path, events):
    room = (scene["W"], scene["L"])
    result = ES.infer(room, banks, path, events, True, True, None,
                      padding=PAD, path_margin=0.08)
    rows = {}
    for obj in OBJECTS:
        info = result["objects"].get(obj, {})
        row = {"n_hypotheses": int(info.get("n", 0)), "status": info.get("status"),
               "support_m": info.get("center_diameter_m"),
               "envelope_m": info.get("center_envelope_m"),
               "error_m": None, "hit": False}
        if result.get("boxes") and obj in result["boxes"]:
            true_box = np.asarray(scene["gt"][obj], float)
            got_box = np.asarray(result["boxes"][obj], float)
            row["error_m"] = float(np.linalg.norm(
                (true_box[:2] + true_box[2:]) / 2 - (got_box[:2] + got_box[2:]) / 2))
        row["hit"] = bool(row["error_m"] is not None and row["error_m"] <= TOL)
        rows[obj] = row
    return result["status"], rows


def _aggregate(rows, key):
    out = {}
    for arm, obj in key:
        sel = [r for r in rows if r["arm_label"] == arm and r["object"] == obj]
        if not sel:
            continue
        support = [v["support_m"] for v in sel if v["support_m"] is not None]
        errors = [v["error_m"] for v in sel if v["error_m"] is not None]
        out[arm + ":" + obj] = {
            "n": len(sel),
            "median_support_m": float(np.median(support)) if support else None,
            "median_error_m": float(np.median(errors)) if errors else None,
            "hit_rate": float(np.mean([v["hit"] for v in sel])),
            "conflict_rate": float(np.mean([v["status"] == "conflict" for v in sel])),
        }
    return out


def run(out, seed=SEED, budgets=BUDGETS):
    scenes = _scenes()
    rows = []
    for index, scene in enumerate(scenes):
        room = (scene["W"], scene["L"])
        dimensions = {obj: (b[2] - b[0], b[3] - b[1]) for obj, b in scene["gt"].items()}
        banks = ES.make_bank(room, dimensions, spacing=.20)
        try:
            episode = route_episode(scene, "dispersed", seed + index)
        except ValueError as exc:
            rows.append({"scene": scene["scene"], "error": str(exc)})
            continue
        rng = np.random.default_rng(seed * 1000 + index)
        base, _ = contact_targets(scene, rng)
        for budget in budgets:
            visible = episode["points"][episode["arc"] <= budget]
            coverage = ES.spatial_coverage(visible, room)
            events = [dict(e, pos=np.asarray(e["pos"], float).tolist())
                      for e in episode["events"] if e["available_distance_m"] <= budget]
            spans = {obj: np.ptp(np.array([e["pos"] for e in events if e["object"] == obj], float),
                                  axis=0).tolist() if sum(e["object"] == obj for e in events) > 1
                     else [0.0, 0.0] for obj in OBJECTS}
            variants = _edits(events)
            for name, variant_events in variants.items():
                status, measured = _measure(scene, banks, visible, variant_events)
                for obj in OBJECTS:
                    rows.append({"scene": scene["scene"], "budget_m": budget, "arm": name.split(":")[0],
                                 "arm_label": name,
                                 "edited": name.split(":")[1] if ":" in name else None,
                                 "object": obj, "coverage": coverage, "n_events": len(variant_events),
                                 "span_m": ([0.0, 0.0] if name == "collapse:" + obj else
                                            None if name == "drop:" + obj else spans[obj]),
                                 "status": status, **measured[obj]})
            # One anchor only, same support question with span undefined.
            for obj in OBJECTS:
                if base.get(obj) is None:
                    continue
                single = [e for e in events if e["object"] == obj][:1]
                if not single:
                    continue
                _, measured = _measure(scene, banks, visible, single)
                rows.append({"scene": scene["scene"], "budget_m": budget, "arm": "single",
                             "arm_label": "single",
                             "edited": obj, "object": obj, "coverage": coverage,
                             "n_events": 1, "span_m": [0.0, 0.0],
                             "status": "ok", **measured[obj]})
        print(scene["scene"], "done", flush=True)

    labels = sorted({r["arm_label"] for r in rows if "object" in r})
    keys = {(a, o) for a in labels for o in OBJECTS}
    summary = _aggregate([r for r in rows if "object" in r], keys)
    # Closed form for the one class whose constraint really is an interval cartesian product.
    bed = [r for r in rows if "object" in r and r["object"] == "bed" and r["arm"] == "full"]
    predicted, observed = [], []
    for r in bed:
        if r["envelope_m"] is None or r["span_m"] is None:
            continue
        scene = next(s for s in scenes if s["scene"] == r["scene"])
        box = np.asarray(scene["gt"]["bed"], float)
        extent = box[2:] - box[:2]
        span = np.asarray(r["span_m"], float)
        predicted.append(np.maximum(0.0, extent + 2 * PAD - span).tolist())
        observed.append([float(v) for v in r["envelope_m"]])
    record = {
        "scope": "Geometric oracle; one route, route and coverage held fixed across arms",
        "candidate_model": "Known room and sizes; uniform prior (P-U); padding %.2f m; tolerance %.2f m" % (PAD, TOL),
        "budgets_m": list(budgets), "seed": seed, "scene_count": len(scenes),
        "protocol": {"edited_class_at_a_time": True,
                     "coverage_identical_across_arms": True,
                     "support_is_centre_envelope_diagonal_upper_bound": True,
                     "bank_spacing_m": 0.20},
        "summary": summary, "rows": rows,
        "closed_form_reference": {"predicted_envelope": predicted, "observed_envelope": observed},
    }
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def _free_axis(scene, obj):
    box = np.asarray(scene["gt"][obj], float)
    extent = box[2:] - box[:2]
    return 0 if extent[0] >= extent[1] else 1


def span_sweep(out, seed=SEED, spans=(0.0, 0.25, 0.5, 0.75, 1.0, 1.5), copies=3):
    """Counterfactual anchor placement: how much span would pin this object?

    Not a measured route.  The other classes keep their measured events so the
    coupling stays realistic; only the target class is re-placed, symmetrically,
    along its own long axis.
    """
    scenes = _scenes()
    rows = []
    for index, scene in enumerate(scenes):
        room = (scene["W"], scene["L"])
        dimensions = {obj: (b[2] - b[0], b[3] - b[1]) for obj, b in scene["gt"].items()}
        banks = ES.make_bank(room, dimensions, spacing=.20)
        try:
            episode = route_episode(scene, "dispersed", seed + index)
        except ValueError:
            continue
        measured = [dict(e, pos=np.asarray(e["pos"], float).tolist())
                    for e in episode["events"] if e["available_distance_m"] <= episode["walk_length_m"]]
        rng = np.random.default_rng(seed * 1000 + index)
        base, _ = contact_targets(scene, rng)
        for obj in ("bed", "cab"):
            if base.get(obj) is None:
                continue
            axis = _free_axis(scene, obj)
            origin = np.asarray(base[obj], float)
            for span in spans:
                offsets = np.linspace(-span / 2, span / 2, copies)
                placed = []
                for value in offsets:
                    point = origin.copy()
                    point[axis] += value
                    if not (0.0 <= point[0] <= scene["W"] and 0.0 <= point[1] <= scene["L"]):
                        placed = []
                        break
                    if any(scene["gt"][other][0] < point[0] < scene["gt"][other][2] and
                           scene["gt"][other][1] < point[1] < scene["gt"][other][3]
                           for other in ("desk", "cab")):
                        placed = []
                        break
                    placed.append(point.tolist())
                if not placed:
                    continue
                events = [e for e in measured if e["object"] != obj] + [
                    {"object": obj, "pos": point, "available_distance_m": 0.0} for point in placed]
                _, result = _measure(scene, banks, episode["points"], events)
                row = result[obj]
                extent = np.asarray(scene["gt"][obj], float)[2:] - np.asarray(scene["gt"][obj], float)[:2]
                predicted = float(np.max(np.maximum(0.0, extent + 2 * PAD - span)))
                rows.append({"scene": scene["scene"], "object": obj, "span_m": span,
                             "axis": axis, "extent_m": extent.tolist(),
                             "predicted_max_width_m": predicted,
                             "support_m": row["support_m"], "envelope_m": row["envelope_m"],
                             "error_m": row["error_m"], "hit": row["hit"]})
        print(scene["scene"], "sweep done", flush=True)
    summary = {}
    for obj in ("bed", "cab"):
        for span in spans:
            sel = [r for r in rows if r["object"] == obj and r["span_m"] == span]
            if not sel:
                continue
            envelope = [max(r["envelope_m"]) for r in sel if r["envelope_m"]]
            summary["%s:%.2f" % (obj, span)] = {
                "n": len(sel),
                "median_support_m": float(np.median([r["support_m"] for r in sel if r["support_m"]])),
                "median_max_envelope_m": float(np.median(envelope)) if envelope else None,
                "median_error_m": float(np.median([r["error_m"] for r in sel if r["error_m"] is not None])),
                "hit_rate": float(np.mean([r["hit"] for r in sel]))}
    record = {"scope": "Counterfactual anchor placement, not a measured route",
              "protocol": {"copies_per_axis": copies, "padding_m": PAD, "tolerance_m": TOL,
                           "bank_spacing_m": 0.20, "other_classes": "measured events at the full route"},
              "summary": summary, "rows": rows}
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def requirement_report(frontier_path, delta=TOL):
    """Achieved anchor span versus the span that the closed form says is needed."""
    scenes = {s["scene"]: s for s in _scenes()}
    data = json.loads(Path(frontier_path).read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r["arm"] == "TA-U"]
    top = max(r["budget_m"] for r in rows)
    rows = [r for r in rows if r["budget_m"] == top]
    out = {"budget_m": top, "tolerance_m": delta, "padding_m": PAD, "classes": {}}
    for obj in OBJECTS:
        achieved, required, met, n_axis = [], [], 0, 0
        met_positive, n_positive = 0, 0
        for row in rows:
            spans = row["event_span_per_axis_m"].get(obj)
            if spans is None:
                continue
            scene = scenes.get(row["scene"])
            if scene is None:
                continue
            box = np.asarray(scene["gt"][obj], float)
            extent = box[2:] - box[:2]
            need_axis = np.maximum(0.0, extent + 2 * PAD - 2 * delta)
            got = np.asarray(spans, float)
            for axis in (0, 1):
                achieved.append(float(got[axis]))
                required.append(float(need_axis[axis]))
                n_axis += 1
                if got[axis] >= need_axis[axis]:
                    met += 1
                if need_axis[axis] > 0.05:
                    n_positive += 1
                    if got[axis] >= need_axis[axis]:
                        met_positive += 1
        if n_axis:
            out["classes"][obj] = {
                "n_axis": n_axis,
                "median_achieved_span_m": float(np.median(achieved)),
                "median_required_span_m": float(np.median(required)),
                "axes_meeting_requirement": met,
                "share_meeting": float(met / n_axis),
                "axes_with_positive_requirement": n_positive,
                "axes_meeting_where_requirement_positive": met_positive,
                "share_meeting_where_requirement_positive": (float(met_positive / n_positive)
                                                             if n_positive else None)}
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--sweep-output")
    parser.add_argument("--requirement-from")
    args = parser.parse_args()
    if args.requirement_from:
        print(json.dumps(requirement_report(args.requirement_from), ensure_ascii=False, indent=1))
        raise SystemExit(0)
    if args.sweep_output:
        rec = span_sweep(args.sweep_output)
        for key in sorted(rec["summary"]):
            row = rec["summary"][key]
            print("%-10s n=%2d support=%.2f env=%.2f err=%.2f hit=%.2f" % (
                key, row["n"], row["median_support_m"], row["median_max_envelope_m"] or -1,
                row["median_error_m"] or -1, row["hit_rate"]))
        raise SystemExit(0)
    rec = run(args.output, args.seed)
    for obj in OBJECTS:
        print("--", obj)
        for key, row in rec["summary"].items():
            if key.endswith(":" + obj) and row["n"]:
                print("   %-14s n=%3d support=%.2f hit=%.2f" % (
                    key[: -len(obj) - 1], row["n"], row["median_support_m"] or -1, row["hit_rate"]))
