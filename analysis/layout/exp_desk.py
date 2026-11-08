"""Does a desk channel (bounds from the seated anchors) rescue the desk axis?"""
import json
from pathlib import Path
import numpy as np

from . import evidence_space as ES
from . import sim_eval as SE
from . import paths
from .activity_experiment import contact_targets, route_episode, prefix_episode

TOL = 0.5
PAD = 0.20
REACHES = (None, 1.0, 1.5, 2.0, 3.0)


def scenes():
    return [s for f in sorted(Path(paths.THOR).glob("FloorPlan*.json")) if (s := SE.load_scene(str(f)))]


def _dist(box, point):
    outside = np.maximum(np.asarray(box[:2], float) - point, point - np.asarray(box[2:], float)).clip(min=0)
    return float(np.linalg.norm(outside))


def forward_support(boxes,point,direction,halfwidth=.20):
    """Diagnostic bearing corridor; it does not specify object distance."""
    direction=np.asarray(direction,float);norm=np.linalg.norm(direction)
    if norm<1e-9:return np.ones(len(boxes),bool)
    v=direction/norm;offset=ES.centres(np.asarray(boxes))-np.asarray(point)
    along=offset@v;across=abs(offset[:,0]*v[1]-offset[:,1]*v[0])
    return (along>=-halfwidth)&(across<=halfwidth)


def run(out,budget=96.,oracle_direction=False):
    rows = []
    for index, scene in enumerate(scenes()):
        episode = route_episode(scene, "dispersed", 17031 + index)
        room = (scene["W"], scene["L"])
        dimensions = {obj: (b[2] - b[0], b[3] - b[1]) for obj, b in scene["gt"].items()}
        banks = ES.make_bank(room, dimensions, spacing=.20)
        truth = np.asarray(scene["gt"]["desk"], float)
        path,events=prefix_episode(episode,budget)
        seated = [e for e in events if e["object"] == "chair"]
        survives = all(_dist(truth, np.asarray(e["pos"], float)) <= 2.0 for e in seated) if seated else None
        variants=[(r,False) for r in REACHES]+([(None,True),(1.,True),(2.,True)] if oracle_direction else [])
        for reach,with_direction in variants:
            selected_banks=dict(banks)
            if with_direction:
                keep=np.ones(len(banks['desk']),bool)
                true_center=(truth[:2]+truth[2:])/2
                for event in seated:
                    p=np.asarray(event['pos']);keep&=forward_support(banks['desk'],p,true_center-p)
                selected_banks['desk']=banks['desk'][keep]
            result = ES.infer((scene["W"], scene["L"]), selected_banks, path, events,
                              True, True, None, padding=PAD, reach=.60, path_margin=.08,
                              desk_reach=reach)
            info = result["objects"]["desk"]
            row = {"scene": scene["scene"], "desk_reach_m": reach,
                   "oracle_center_bearing":with_direction,"budget_m":budget,
                   "true_desk_satisfies_reach":all(_dist(truth,np.asarray(e['pos']))<=reach for e in seated) if reach is not None else True,
                   "support_m": info.get("center_diameter_m"), "status": info.get("status"),
                   "truth_within_2m_of_seated": survives, "error_m": None, "hit": False}
            if result.get("boxes") and "desk" in result["boxes"]:
                got = np.asarray(result["boxes"]["desk"], float)
                row["error_m"] = float(np.linalg.norm((truth[:2] + truth[2:]) / 2 - (got[:2] + got[2:]) / 2))
                row["hit"] = bool(row["error_m"] <= TOL)
            rows.append(row)
    summary = {}
    for reach,with_direction in [(r,False) for r in REACHES]+([(None,True),(1.,True),(2.,True)] if oracle_direction else []):
        sel = [r for r in rows if r["desk_reach_m"] == reach and r['oracle_center_bearing']==with_direction]
        ok = [r for r in sel if r["support_m"] is not None]
        summary[str(reach)+(':oracle_bearing' if with_direction else '')] = {
            "n": len(sel),
            "resolved": len(ok),
            "truth_satisfies_reach_n":sum(r['true_desk_satisfies_reach'] for r in sel),
            "hit_rate": float(np.mean([r["hit"] for r in sel])) if sel else None,
            "support_median_m": float(np.median([r["support_m"] for r in ok])) if ok else None,
            "error_median_m": float(np.median([r["error_m"] for r in ok if r["error_m"] is not None])) if ok else None,
        }
    payload = {"tolerance_m": TOL, "padding_m": PAD, "reaches_m": list(REACHES),
               'budget_m':budget,'oracle_bearing_scope':'Reference direction to true desk centre, not observed body facing; diagnostic side information only',
               "truth_survives_2m": float(np.mean([r["truth_within_2m_of_seated"] for r in rows
                                                   if r["desk_reach_m"] is None])),
               "summary": summary, "rows": rows}
    Path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("truth_survives_2m", "summary")}, ensure_ascii=False, indent=1))
    return payload


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default='analysis/layout/desk_channel.json')
    p.add_argument('--budget',type=float,default=96.);p.add_argument('--oracle-direction',action='store_true')
    a=p.parse_args();run(a.output,a.budget,a.oracle_direction)
