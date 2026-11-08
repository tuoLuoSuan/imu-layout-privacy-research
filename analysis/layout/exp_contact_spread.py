"""Same route, same count, same coverage: does the *spread* of contacts matter?

exp_diagnose showed that walking further mostly adds floor, not straddling contacts, and
exp_span showed the interval width is set by the span of the anchors rather than by
coverage.  This is the paired version of that statement: the number of contacts per class
is fixed at three, the route and coverage are untouched, and only the way those three
contacts are distributed along the object's own long axis changes -- from three repeats at
one point to three points straddling the whole object.

The dispersion is applied to the mean real anchor of that class, so each class keeps its
own contact convention (an anchor inside the bed, an anchor 0.6 m off a cabinet face).
Geometric oracle study, not raw IMU.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from . import evidence_space as ES
from . import sim_eval as SE
from . import paths
from .activity_experiment import route_episode, prefix_episode

TOL = 0.5
PAD = 0.20
BUDGET = 96.0
COUNT = 3
OBJECTS = ("bed", "desk", "cab", "chair")
FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


def scenes():
    return [s for f in sorted(Path(paths.THOR).glob("FloorPlan*.json")) if (s := SE.load_scene(str(f)))]


def long_axis(box):
    box = np.asarray(box, float)
    w, h = box[2] - box[0], box[3] - box[1]
    if w >= h:
        return np.array([1.0, 0.0]), float(w)
    return np.array([0.0, 1.0]), float(h)


def spread_events(events, obj, box, fraction, count=COUNT):
    mine = [e for e in events if e["object"] == obj]
    if not mine:
        return None, None
    mean = np.mean([np.asarray(e["pos"], float) for e in mine], axis=0)
    axis, length = long_axis(box)
    offsets = np.linspace(-0.5, 0.5, count) * fraction * length
    made = [dict(mine[0], pos=(mean + o * axis).tolist()) for o in offsets]
    return [e for e in events if e["object"] != obj] + made, float(offsets[-1] - offsets[0])


def measure(scene, banks, path, events):
    result = ES.infer((scene["W"], scene["L"]), banks, path, events, True, True, None,
                      padding=PAD, path_margin=0.08)
    out = {}
    for obj in OBJECTS:
        info = result["objects"].get(obj, {})
        row = {"status": info.get("status"), "support_m": info.get("center_diameter_m"),
               "error_m": None, "hit": False}
        if result.get("boxes") and obj in result["boxes"]:
            true_box = np.asarray(scene["gt"][obj], float)
            got = np.asarray(result["boxes"][obj], float)
            row["error_m"] = float(np.linalg.norm((true_box[:2] + true_box[2:]) / 2 - (got[:2] + got[2:]) / 2))
            row["hit"] = bool(row["error_m"] <= TOL)
        out[obj] = row
    return out


def run(out, budget=BUDGET):
    rows = []
    for index, scene in enumerate(scenes()):
        episode = route_episode(scene, "dispersed", 17031 + index)
        dims = {obj: (b[2] - b[0], b[3] - b[1]) for obj, b in scene["gt"].items()}
        banks = ES.make_bank((scene["W"], scene["L"]), dims, spacing=.20)
        path, events = prefix_episode(episode, budget)
        counts = {obj: sum(1 for e in events if e["object"] == obj) for obj in OBJECTS}
        base = measure(scene, banks, path, events)
        for obj in OBJECTS:
            rows.append({"scene": scene["scene"], "object": obj, "arm": "actual",
                         "fraction": None, "span_m": None, "n_events": counts[obj],
                         "status": base[obj]["status"],
                         "support_m": base[obj]["support_m"], "error_m": base[obj]["error_m"],
                         "hit": base[obj]["hit"]})
        for obj in OBJECTS:
            for fraction in FRACTIONS:
                edited, span = spread_events(events, obj, scene["gt"][obj], fraction)
                if edited is None:
                    continue
                got = measure(scene, banks, path, edited)[obj]
                rows.append({"scene": scene["scene"], "object": obj,
                             "arm": "repeat" if fraction == 0 else "spread",
                             "fraction": fraction, "span_m": span, "n_events": COUNT,
                             "status": got["status"],
                             "support_m": got["support_m"], "error_m": got["error_m"],
                             "hit": got["hit"]})
    summary = {}
    for obj in OBJECTS:
        for key in ["actual"] + ["f%g" % f for f in FRACTIONS]:
            sel = [r for r in rows if r["object"] == obj and
                   (r["arm"] == "actual" if key == "actual" else r["fraction"] == float(key[1:]))]
            if not sel:
                continue
            sups = [r["support_m"] for r in sel if r["support_m"] is not None]
            errs = [r["error_m"] for r in sel if r["error_m"] is not None]
            summary["%s:%s" % (obj, key)] = {
                "rooms": len(sel), "hits": int(sum(r["hit"] for r in sel)),
                "hit_rate": float(np.mean([r["hit"] for r in sel])),
                "support_median_m": float(np.median(sups)) if sups else None,
                "error_median_m": float(np.median(errs)) if errs else None,
                "span_median_m": float(np.median([r["span_m"] for r in sel])) if sel[0]["span_m"] else None,
                "conflict": int(sum(1 for r in sel if r["status"] == "conflict")),
                "no_box": int(sum(1 for r in sel if r["error_m"] is None))}
    record = {"scope": "Same route, same count (3 per class), only the spread along the object axis varies; "
                       "geometric oracle, development scenes, 96 m",
              "budget_m": budget, "count_per_class": COUNT, "fractions": list(FRACTIONS),
              "summary": summary, "rows": rows}
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print("%-6s %-8s %-12s %-12s" % ("object", "arm", "hit", "support_med"))
    for obj in OBJECTS:
        for key in ["actual"] + ["f%g" % f for f in FRACTIONS]:
            k = "%s:%s" % (obj, key)
            if k in summary:
                s = summary[k]
                print("%-6s %-8s %2d/%2d %.2f  %s m" % (
                    obj, key, s["hits"], s["rooms"], s["hit_rate"],
                    "--" if s["support_median_m"] is None else "%.2f" % s["support_median_m"]))
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--budget", type=float, default=BUDGET)
    a = p.parse_args()
    run(a.output, a.budget)
