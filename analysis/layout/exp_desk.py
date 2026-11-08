"""Does a desk channel (bounds from the seated anchors) rescue the desk axis?"""
import json
from pathlib import Path
import numpy as np

from . import evidence_space as ES
from . import sim_eval as SE
from . import paths
from .activity_experiment import contact_targets, route_episode

TOL = 0.5
PAD = 0.20
REACHES = (None, 1.0, 1.5, 2.0, 3.0)


def scenes():
    return [s for f in sorted(Path(paths.THOR).glob("FloorPlan*.json")) if (s := SE.load_scene(str(f)))]


def _dist(box, point):
    outside = np.maximum(np.asarray(box[:2], float) - point, point - np.asarray(box[2:], float)).clip(min=0)
    return float(np.linalg.norm(outside))


def run(out):
    rows = []
    for index, scene in enumerate(scenes()):
        episode = route_episode(scene, "dispersed", 17031 + index)
        room = (scene["W"], scene["L"])
        dimensions = {obj: (b[2] - b[0], b[3] - b[1]) for obj, b in scene["gt"].items()}
        banks = ES.make_bank(room, dimensions, spacing=.20)
        truth = np.asarray(scene["gt"]["desk"], float)
        seated = [e for e in episode["events"] if e["object"] == "chair"]
        survives = all(_dist(truth, np.asarray(e["pos"], float)) <= 2.0 for e in seated) if seated else None
        for reach in REACHES:
            result = ES.infer((scene["W"], scene["L"]), banks, episode["points"], episode["events"],
                              True, True, None, padding=PAD, reach=.60, path_margin=.08,
                              desk_reach=reach)
            info = result["objects"]["desk"]
            row = {"scene": scene["scene"], "desk_reach_m": reach,
                   "support_m": info.get("center_diameter_m"), "status": info.get("status"),
                   "truth_within_2m_of_seated": survives, "error_m": None, "hit": False}
            if result.get("boxes") and "desk" in result["boxes"]:
                got = np.asarray(result["boxes"]["desk"], float)
                row["error_m"] = float(np.linalg.norm((truth[:2] + truth[2:]) / 2 - (got[:2] + got[2:]) / 2))
                row["hit"] = bool(row["error_m"] <= TOL)
            rows.append(row)
    summary = {}
    for reach in REACHES:
        sel = [r for r in rows if r["desk_reach_m"] == reach]
        ok = [r for r in sel if r["support_m"] is not None]
        summary[str(reach)] = {
            "n": len(sel),
            "resolved": len(ok),
            "hit_rate": float(np.mean([r["hit"] for r in sel])) if sel else None,
            "support_median_m": float(np.median([r["support_m"] for r in ok])) if ok else None,
            "error_median_m": float(np.median([r["error_m"] for r in ok if r["error_m"] is not None])) if ok else None,
        }
    payload = {"tolerance_m": TOL, "padding_m": PAD, "reaches_m": list(REACHES),
               "truth_survives_2m": float(np.mean([r["truth_within_2m_of_seated"] for r in rows
                                                   if r["desk_reach_m"] is None])),
               "summary": summary, "rows": rows}
    Path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("truth_survives_2m", "summary")}, ensure_ascii=False, indent=1))
    return payload


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "analysis/layout/desk_channel.json")
