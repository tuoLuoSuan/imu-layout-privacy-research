"""Can the trajectory itself supply the desk direction that truth was supplying?

exp_desk.py already showed: a distance-only desk channel (|seated -> desk| <= 1 m)
takes the desk from 2/14 to 3/14, while an ORACLE bearing to the true desk centre
takes it to 12/14.  This script replaces the oracle bearing with the heading the
generated approach direction, temporally associated with each event. These
geometric routes are not raw IMU and this proxy is not measured body facing.
"""
import json
from pathlib import Path

import numpy as np

from . import evidence_space as ES
from . import sim_eval as SE, paths
from .activity_experiment import route_episode, prefix_episode

TOL = 0.5
PAD = 0.20
REACH = 1.0
CONES = (30.0, 45.0, 60.0, 90.0)
LOOKBACKS = (0.5, 1.0, 1.5)
BUDGET = 96.0


def scenes():
    root = Path(paths.THOR)
    return [s for f in sorted(root.glob("FloorPlan*.json")) if (s := SE.load_scene(str(f)))]


def _dist(box, point):
    outside = np.maximum(np.asarray(box[:2], float) - point, point - np.asarray(box[2:], float)).clip(min=0)
    return float(np.linalg.norm(outside))

def heading_at(path, anchor, lookback, event_distance=None):
    """Causal approach direction, associated by event arclength, never spatial nearest.

    Without event_distance the caller must already have truncated the path to the event.
    The anchor is retained for API compatibility; a phone contact need not be on the walk.
    """
    path = np.asarray(path, float)
    if len(path)<2:
        return None
    arc = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    end=arc[-1] if event_distance is None else min(float(event_distance),arc[-1])
    if end<=0:return None
    def at(distance):
        return np.array([np.interp(distance,arc,path[:,axis]) for axis in [0,1]])
    v = at(end)-at(max(0.,end-lookback))
    n = np.linalg.norm(v)
    return None if n < 1e-6 else v / n


def cone_keep(boxes, point, heading, cone_deg):
    if heading is None:
        return np.ones(len(boxes), bool)
    c = ES.centres(np.asarray(boxes))
    v = c - np.asarray(point, float)
    norm = np.linalg.norm(v, axis=1)
    cosang = np.divide(v @ heading, norm, out=np.ones(len(v)), where=norm > 1e-9)
    ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    return (ang <= cone_deg) | (norm <= PAD)

def run(out):
    rows = []
    for index, scene in enumerate(scenes()):
        episode = route_episode(scene, "dispersed", 17031 + index)
        room = (scene["W"], scene["L"])
        dims = {obj: (b[2] - b[0], b[3] - b[1]) for obj, b in scene["gt"].items()}
        banks = ES.make_bank(room, dims, spacing=.20)
        truth = np.asarray(scene["gt"]["desk"], float)
        path, events = prefix_episode(episode, BUDGET)
        seated = [e for e in events if e["object"] == "chair"]
        settings=[('no_channel',None,None),('distance_only',None,None)]+[
            ('direction',lb,cone) for lb in LOOKBACKS for cone in CONES]
        for control,lookback,cone in settings:
            heads = [heading_at(path,e['pos'],lookback,e['available_distance_m']) for e in seated] if lookback else []
            selected = dict(banks)
            if cone is not None:
                keep = np.ones(len(banks["desk"]), bool)
                for event, h in zip(seated, heads):
                    keep &= cone_keep(banks["desk"], np.asarray(event["pos"], float), h, cone)
                selected["desk"] = banks["desk"][keep]
            row = {"scene": scene["scene"], "control":control,"lookback_m": lookback, "cone_deg": cone,
                   "heading_error_deg":[float(np.degrees(np.arccos(np.clip(h @ ((truth[:2]+truth[2:])/2-np.asarray(e['pos']))/
                     max(1e-9,np.linalg.norm((truth[:2]+truth[2:])/2-np.asarray(e['pos']))),-1,1))))
                     for h,e in zip(heads,seated) if h is not None],
                   "observed_heading": bool(any(h is not None for h in heads)),
                   "status": "empty", "support_m": None, "error_m": None, "hit": False}
            if len(selected["desk"]):
                result = ES.infer(room, selected, path, events, True, True, None,
                                  padding=PAD, reach=.60, path_margin=.08,
                                  desk_reach=(None if control=='no_channel' else REACH))
                info = result["objects"]["desk"]
                row["status"] = info.get("status")
                row["support_m"] = info.get("center_diameter_m")
                if result.get("boxes") and "desk" in result["boxes"]:
                    got = np.asarray(result["boxes"]["desk"], float)
                    row["error_m"] = float(np.linalg.norm(
                        (truth[:2] + truth[2:]) / 2 - (got[:2] + got[2:]) / 2))
                    row["hit"] = bool(row["error_m"] <= TOL)
            rows.append(row)
    summary = {}
    for control,lookback,cone in settings:
        sel = [r for r in rows if r['control']==control and r["lookback_m"] == lookback and r["cone_deg"] == cone]
        errs = [r["error_m"] for r in sel if r["error_m"] is not None]
        sups = [r["support_m"] for r in sel if r["support_m"] is not None]
        summary[control if lookback is None else "lookback%g_cone%s" % (lookback, cone)] = {
            "n": len(sel), "hits": sum(r["hit"] for r in sel),
            "hit_rate": float(np.mean([r["hit"] for r in sel])),
            "error_median_m": float(np.median(errs)) if errs else None,
            "support_median_m": float(np.median(sups)) if sups else None,
            "missing":sum(r['error_m'] is None for r in sel),
            "conflict": sum(1 for r in sel if r["status"] == "conflict")}
    record = {"scope": "Geometric generated-route heading, not raw IMU or measured body facing; development scenes, 96 m",
              "reach_m": REACH, "padding_m": PAD, "lookbacks_m": list(LOOKBACKS),
              "cones_deg": list(CONES), "summary": summary, "rows": rows}
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    for key in sorted(summary):
        s = summary[key]
        print("%-22s hit %2d/%2d = %.2f  err %s  sup %s  conflict %d" % (
            key, s["hits"], s["n"], s["hit_rate"],
            "--" if s["error_median_m"] is None else "%.2f" % s["error_median_m"],
            "--" if s["support_median_m"] is None else "%.2f" % s["support_median_m"],
            s["conflict"]))
    return record


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "analysis/layout/desk_direction.json")


