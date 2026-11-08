"""Does the desk direction channel survive a different tie-break?

exp_tiebreak showed the desk point hit at the same observation moves 1/14 (centroid
preference) -> 9/14 (no preference) -> 4.8/14 (random) purely by changing which of the
equally-supported candidates is returned.  So neither the 0.07-0.14 figures of
exp_desk_dir nor the oracle-bearing 12/14 of exp_desk can be read as "the channel
decides" until the arm is re-run under more than one tie-break.

This re-runs the generated-route heading arm without touching exp_desk_dir: the only
change is what infer() does when several candidates share the best score.
"""
import json
import time
from pathlib import Path

import numpy as np

from . import evidence_space as ES
from . import sim_eval as SE, paths
from .activity_experiment import route_episode, prefix_episode
from .exp_desk_dir import heading_at, cone_keep

PAD = 0.20
REACH = 1.0
BUDGET = 96.0
TOL = 0.5
LOOKBACK = 1.0
CONES = (30.0, 45.0, 60.0, 90.0)
DRAWS = 4
SEED = 9031


_ORIG_INFER = ES.infer
_STATE = {"tie": "centroid", "rng": None}


def _patched_infer(*args, **kwargs):
    kwargs.setdefault("tie_break", _STATE["tie"])
    if kwargs.get("rng") is None:
        kwargs["rng"] = _STATE["rng"]
    return _ORIG_INFER(*args, **kwargs)


def scenes():
    root = Path(paths.THOR)
    return [s for f in sorted(root.glob("FloorPlan*.json")) if (s := SE.load_scene(str(f)))]


def _measure(scene, banks, path, events, control, cone):
    seated = [e for e in events if e["object"] == "chair"]
    selected = dict(banks)
    if cone is not None:
        keep = np.ones(len(banks["desk"]), bool)
        for event in seated:
            head = heading_at(path, event["pos"], LOOKBACK, event["available_distance_m"])
            keep &= cone_keep(banks["desk"], np.asarray(event["pos"], float), head, cone)
        selected["desk"] = banks["desk"][keep]
    if not len(selected["desk"]):
        return None, None
    truth = np.asarray(scene["gt"]["desk"], float)
    result = ES.infer((scene["W"], scene["L"]), selected, path, events, True, True, None,
                      padding=PAD, reach=.60, path_margin=.08,
                      desk_reach=(None if control == "no_channel" else REACH))
    info = result["objects"]["desk"]
    err = None
    if result.get("boxes") and "desk" in result["boxes"]:
        got = np.asarray(result["boxes"]["desk"], float)
        err = float(np.linalg.norm((truth[:2] + truth[2:]) / 2 - (got[:2] + got[2:]) / 2))
    return info.get("center_diameter_m"), err


def run(out, draws=DRAWS):
    head = [("no_channel", None), ("distance_only", None)] + [("direction", c) for c in CONES]
    cells = []
    ES.infer = _patched_infer
    started = time.time()
    for index, scene in enumerate(scenes()):
        episode = route_episode(scene, "dispersed", 17031 + index)
        room = (scene["W"], scene["L"])
        dims = {obj: (b[2] - b[0], b[3] - b[1]) for obj, b in scene["gt"].items()}
        banks = ES.make_bank(room, dims, spacing=.20)
        path, events = prefix_episode(episode, BUDGET)
        for control, cone in head:
            for kind in ("centroid", "none", "random"):
                draws_n = draws if kind == "random" else 1
                for draw in range(draws_n):
                    _STATE["tie"] = kind
                    _STATE["rng"] = SEED + 101 * draw + index
                    support, err = _measure(scene, banks, path, events, control, cone)
                    cells.append({"scene": scene["scene"], "control": control, "cone_deg": cone,
                                  "tie_break": kind, "draw": draw,
                                  "support_m": support, "error_m": err,
                                  "hit": bool(err is not None and err <= TOL)})
    ES.infer = _ORIG_INFER
    summary = {}
    for control, cone in head:
        key = control if cone is None else "cone%g" % cone
        sel = [c for c in cells if c["control"] == control and c["cone_deg"] == cone]
        entry = {}
        for kind in ("centroid", "none", "random"):
            part = [c for c in sel if c["tie_break"] == kind]
            if kind == "random":
                per_draw = {}
                for c in part:
                    per_draw.setdefault(c["draw"], []).append(c)
                rates = [float(np.mean([c["hit"] for c in v])) for v in per_draw.values()]
                entry[kind] = {"hits_mean": float(np.mean([r * 14 for r in rates])),
                               "hits_std": float(np.std([r * 14 for r in rates])),
                               "hit_rate_mean": float(np.mean(rates))}
            else:
                entry[kind] = {"hits": int(sum(c["hit"] for c in part)),
                               "n": len(part),
                               "hit_rate": float(np.mean([c["hit"] for c in part]))}
        summary[key] = entry
    record = {"scope": "Geometric generated-route heading; development scenes; 96 m; "
                       "only the tie-break among equally supported candidates varies",
              "lookback_m": LOOKBACK, "padding_m": PAD, "reach_m": REACH, "draws": draws,
              "seconds": round(time.time() - started, 1),
              "summary": summary, "rows": cells}
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    for key in summary:
        e = summary[key]
        print("%-14s centroid %2d/14  none %2d/14  random %4.1f+-%3.1f" % (
            key, e["centroid"]["hits"], e["none"]["hits"],
            e["random"]["hits_mean"], e["random"]["hits_std"]))
    return record


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "analysis/layout/desk_control.json")
