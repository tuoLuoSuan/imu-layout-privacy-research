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
from .activity_experiment import contact_targets, route_episode, prefix_episode

SEED = 17031
BUDGETS = (32.0, 96.0)
TOL = 0.5
PAD = 0.20
OBJECTS = ("bed", "desk", "cab", "chair")
ARMS = ("full", "drop", "collapse", "repeat_first", "single")


def median_available(values):
    present=[v for v in values if v is not None]
    return float(np.median(present)) if present else None


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
        others=[e for e in events if e['object']!=obj]
        out['collapse:'+obj]=others+[dict(e,pos=mean.tolist()) for e in mine]
        out['repeat_first:'+obj]=others+[dict(e,pos=list(mine[0]['pos'])) for e in mine]
        out['single:'+obj]=others+[dict(mine[0])]
    return out


def _measure(scene, banks, path, events):
    room = (scene["W"], scene["L"])
    result = ES.infer(room, banks, path, events, True, True, None,
                      padding=PAD, path_margin=0.08)
    rows = {}
    for obj in OBJECTS:
        info = result["objects"].get(obj, {})
        row = {"n_hypotheses": int(info.get("n", 0)), "status": info.get("status"),
               "solver_status":result['status'],
               "support_m": info.get("center_diameter_m"),
               "envelope_m": info.get("center_envelope_m"),
               "center_bounds_m":info.get('center_bounds_m'),
               "point_center_m":None,"radius_upper_m":None,"allow":False,
               "truth_center_in_envelope":False,
               "error_m": None, "hit": False}
        if result.get("boxes") and obj in result["boxes"]:
            true_box = np.asarray(scene["gt"][obj], float)
            got_box = np.asarray(result["boxes"][obj], float)
            row["error_m"] = float(np.linalg.norm(
                (true_box[:2] + true_box[2:]) / 2 - (got_box[:2] + got_box[2:]) / 2))
            point=(got_box[:2]+got_box[2:])/2
            row['point_center_m']=point.tolist()
            cert=ES.envelope_certificate(info.get('center_bounds_m'),point,TOL)
            row.update(radius_upper_m=cert['radius_upper_m'],allow=cert['allow'])
            bounds=info.get('center_bounds_m')
            if bounds is not None:
                tc=(true_box[:2]+true_box[2:])/2;b=np.asarray(bounds)
                row['truth_center_in_envelope']=bool(np.all(tc>=b[:2]-1e-9) and np.all(tc<=b[2:]+1e-9))
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
        for budget in budgets:
            visible,events = prefix_episode(episode,budget)
            coverage = ES.spatial_coverage(visible, room)
            spans = {obj: np.ptp(np.array([e["pos"] for e in events if e["object"] == obj], float),
                                  axis=0).tolist() if sum(e["object"] == obj for e in events) > 1
                     else [0.0, 0.0] for obj in OBJECTS}
            variants = _edits(events)
            for name, variant_events in variants.items():
                status, measured = _measure(scene, banks, visible, variant_events)
                for obj in OBJECTS:
                    points=np.asarray([e['pos'] for e in variant_events if e['object']==obj])
                    rows.append({"scene": scene["scene"], "budget_m": budget, "arm": name.split(":")[0],
                                 "arm_label": name,
                                 "edited": name.split(":")[1] if ":" in name else None,
                                 "object": obj, "coverage": coverage, "n_events": len(variant_events),
                                 "span_m": np.ptp(points,axis=0).tolist() if len(points) else None,
                                 "status": status, **measured[obj]})
        print(scene["scene"], "done", flush=True)

    labels = sorted({r["arm_label"] for r in rows if "object" in r})
    keys = {(a, o) for a in labels for o in OBJECTS}
    summary = _aggregate([r for r in rows if "object" in r], keys)
    reference={(r['scene'],r['budget_m'],r['object']):r for r in rows if r.get('arm_label')=='full'}
    matched={}
    for obj in ['bed','cab','chair']:
        for edit in ['single','collapse','repeat_first','drop']:
            selected=[r for r in rows if r.get('arm_label')==edit+':'+obj and r.get('object')==obj]
            base=[reference[(r['scene'],r['budget_m'],obj)] for r in selected]
            matched[edit+':'+obj]={'n_scene_budgets':len(selected),
                 'n_rooms':len({r['scene'] for r in selected}),
                 'full_successes':sum(r['hit'] for r in base),'edited_successes':sum(r['hit'] for r in selected),
                 'full_rate':float(np.mean([r['hit'] for r in base])) if base else None,
                 'edited_rate':float(np.mean([r['hit'] for r in selected])) if selected else None}
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
    record = {"schema_version":2,
        "scope": "Geometric oracle; one route, route and coverage held fixed across arms",
        "candidate_model": "Known room and sizes; uniform prior (P-U); padding %.2f m; tolerance %.2f m" % (PAD, TOL),
        "budgets_m": list(budgets), "seed": seed, "scene_count": len(scenes),
        "protocol": {"edited_class_at_a_time": True,
                     "coverage_identical_across_arms": True,
                     "support_is_centre_envelope_diagonal_upper_bound": True,
                     "bank_spacing_m": 0.20},
        "summary": summary, "rows": rows,"matched_comparisons":matched,
        "closed_form_reference": {"scope":"Known true orientation, per-axis containment only; not Euclidean output guarantee",
                                  "predicted_envelope": predicted, "observed_envelope": observed},
    }
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def _free_axis(scene, obj):
    box = np.asarray(scene["gt"][obj], float)
    extent = box[2:] - box[:2]
    return 0 if extent[0] >= extent[1] else 1


def span_requirement(obj,extent,spans,padding,delta):
    """Only the bed containment model has this known-orientation axial formula."""
    if obj!='bed':return {'status':'not_applicable','reason':'Contact model is not independent axial containment'}
    width=np.asarray(extent,float)+2*padding-np.asarray(spans,float)
    return {'status':'conflict' if np.any(width<0) else 'conditional',
            'event_width_m':width.tolist(),
            'required_span_m':np.maximum(0,np.asarray(extent)+2*padding-2*delta).tolist(),
            'target':'Per-coordinate midpoint error, conditional on known orientation and valid bounds'}


def span_positions(box,axis,span,fractions,copies=3):
    box=np.asarray(box,float);extent=box[2:]-box[:2]
    if span>extent[axis]+1e-9:return None
    centre=box[:2]+np.asarray(fractions)*extent
    centre[axis]=box[axis]+span/2+fractions[axis]*(extent[axis]-span)
    points=np.tile(centre,(copies,1));points[:,axis]+=np.linspace(-span/2,span/2,copies)
    return points


def span_sweep(out, seed=SEED, spans=(0.0, 0.25, 0.5, 0.75, 1.0, 1.5), copies=3,position_mode='central'):
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
        base, cab_axis = contact_targets(scene, rng)
        for obj in ("bed", "cab"):
            if base.get(obj) is None:
                rows.extend({'scene':scene['scene'],'object':obj,'span_m':v,'eligible':False,
                             'reason':'No in-room storage operation face at the nominal reach',
                             'support_m':None,'envelope_m':None,'error_m':None,'hit':False} for v in spans)
                continue
            axis = _free_axis(scene,obj) if obj=='bed' else cab_axis
            box=np.asarray(scene['gt'][obj],float);extent=box[2:]-box[:2]
            origin = (box[:2]+box[2:])/2 if obj=='bed' else np.asarray(base[obj],float).copy()
            origin[axis]=(box[axis]+box[axis+2])/2
            fractions=rng.uniform(.1,.9,2) if position_mode=='offset' else np.array([.5,.5])
            for span in spans:
                template={'scene':scene['scene'],'object':obj,'span_m':span,'axis':axis,
                          'extent_m':extent.tolist(),'eligible':False,'support_m':None,
                          'envelope_m':None,'error_m':None,'hit':False}
                if span>extent[axis]+1e-9:
                    rows.append(dict(template,reason='Requested span exceeds the fixed object contact extent'))
                    continue
                offsets = np.linspace(-span / 2, span / 2, copies)
                if position_mode=='offset':
                    adjusted=span_positions(box,axis,span,fractions,copies)
                    origin[axis]=float(adjusted[:,axis].mean())
                    if obj=='bed':origin[1-axis]=adjusted[0,1-axis]
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
                    rows.append(dict(template,reason='Counterfactual contact is outside free interaction floor'))
                    continue
                if not all(ES._contact(np.asarray([box]),{'object':obj,'pos':point},PAD,.6)[0][0] for point in placed):
                    rows.append(dict(template,reason='Counterfactual violates its own true-object contact model'))
                    continue
                events = [e for e in measured if e["object"] != obj] + [
                    {"object": obj, "pos": point, "available_distance_m": 0.0} for point in placed]
                _, result = _measure(scene, banks, episode["points"], events)
                row = result[obj]
                extent = np.asarray(scene["gt"][obj], float)[2:] - np.asarray(scene["gt"][obj], float)[:2]
                span_vector=np.zeros(2);span_vector[axis]=span
                analytic=span_requirement(obj,extent,span_vector,PAD,TOL)
                rows.append(dict(template,**row,eligible=True,reason=None,analytic_reference=analytic))
        print(scene["scene"], "sweep done", flush=True)
    summary = {}
    for obj in ("bed", "cab"):
        for span in spans:
            all_rows = [r for r in rows if r["object"] == obj and r["span_m"] == span]
            sel=[r for r in all_rows if r['eligible']]
            if not sel:
                continue
            envelope = [max(r["envelope_m"]) for r in sel if r["envelope_m"]]
            summary["%s:%.2f" % (obj, span)] = {
                "n": len(sel),"total_rooms":len(scenes),"ineligible":len(all_rows)-len(sel),
                "median_support_m": median_available([r['support_m'] for r in sel]),
                "median_max_envelope_m": float(np.median(envelope)) if envelope else None,
                "median_error_m": median_available([r['error_m'] for r in sel]),
                "hit_rate": float(np.mean([r["hit"] for r in sel])),
                "certificate_allowed":sum(bool(r.get('allow',False)) for r in sel),
                "certificate_allowed_share_all_rooms":sum(bool(r.get('allow',False)) for r in sel)/len(scenes),
                "success_fraction_bounds_all_rooms":[sum(r['hit'] for r in sel)/len(scenes),
                         (sum(r['hit'] for r in sel)+len(scenes)-len(sel))/len(scenes)]}
    record = {"schema_version":2,"scope": "Truth-contact-valid counterfactual placement; not a measured route",
              'position_mode':position_mode,'seed':seed,
              "protocol": {"copies_per_axis": copies, "padding_m": PAD, "tolerance_m": TOL,
                           "bank_spacing_m": 0.20, "other_classes": "measured events at the full route"},
              "summary": summary, "rows": rows}
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def requirement_report(frontier_path, delta=TOL, padding=PAD):
    """Achieved anchor span versus the span that the closed form says is needed."""
    scenes = {s["scene"]: s for s in _scenes()}
    data = json.loads(Path(frontier_path).read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r["arm"] == "TA-U"]
    top = max(r["budget_m"] for r in rows)
    rows = [r for r in rows if r["budget_m"] == top]
    out = {"budget_m": top, "tolerance_m": delta, "padding_m": padding, "classes": {}}
    for obj in OBJECTS:
        if obj!='bed':
            out['classes'][obj]={'status':'not_applicable','reason':'Use the actual circular/face/no-contact model; do not apply bed containment formula'}
            continue
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
            # Coordinate accuracy delta/sqrt(2) is sufficient for 2D error delta
            # at the interval midpoint, conditional on a known true orientation.
            need_axis=np.asarray(span_requirement(obj,extent,spans,padding,delta/np.sqrt(2))['required_span_m'])
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
    out['scope']='Oracle known-orientation bed containment; coordinate tolerance=Euclidean target/sqrt(2); not actual selected-point guarantee'
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--sweep-output")
    parser.add_argument("--requirement-from")
    parser.add_argument('--sweep-position-mode',choices=['central','offset'],default='central')
    args = parser.parse_args()
    if args.requirement_from:
        print(json.dumps(requirement_report(args.requirement_from), ensure_ascii=False, indent=1))
        raise SystemExit(0)
    if args.sweep_output:
        rec = span_sweep(args.sweep_output,seed=args.seed,position_mode=args.sweep_position_mode)
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
