"""How accurate would a facing-direction estimate have to be for the desk channel to work?

This injects the true desk-centre bearing with artificial error. It does not
measure phone orientation or body facing. Common and independent errors are separate.
"""
import json
from pathlib import Path

import numpy as np

from . import evidence_space as ES
from . import sim_eval as SE
from .activity_experiment import route_episode, prefix_episode
from .exp_desk_dir import scenes, cone_keep

TOL = 0.5
PAD = 0.20
REACH = 1.0
CONES = (30.0, 45.0, 60.0)
SIGMAS = (10.0, 20.0, 30.0, 45.0)
DRAWS = 3
BUDGET = 96.0


def rotate(v, deg):
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])


def run(out):
    rows = []
    for index, scene in enumerate(scenes()):
        episode = route_episode(scene, "dispersed", 17031 + index)
        room = (scene["W"], scene["L"])
        dims = {obj: (b[2] - b[0], b[3] - b[1]) for obj, b in scene["gt"].items()}
        banks = ES.make_bank(room, dims, spacing=.20)
        truth = np.asarray(scene["gt"]["desk"], float)
        centre = (truth[:2] + truth[2:]) / 2
        path, events = prefix_episode(episode, BUDGET)
        seated = [e for e in events if e["object"] == "chair"]
        if not seated:
            continue
        rng = np.random.default_rng(90210 + index)
        # Matched draws across sigma; the common mode must not average down on revisits.
        normals={'independent':rng.normal(size=(DRAWS,len(seated))),
                 'common':np.repeat(rng.normal(size=(DRAWS,1)),len(seated),axis=1)}
        for mode in ('independent','common'):
            for sigma in SIGMAS:
                for draw in range(DRAWS):
                    heads = []
                    for j,event in enumerate(seated):
                        v = centre - np.asarray(event["pos"], float)
                        n = np.linalg.norm(v)
                        h = v / n if n > 1e-9 else np.array([1.0, 0.0])
                        heads.append(rotate(h, normals[mode][draw,j]*sigma))
                    for cone in CONES:
                        keep = np.ones(len(banks["desk"]), bool)
                        for event, h in zip(seated, heads):
                            keep &= cone_keep(banks["desk"], np.asarray(event["pos"], float), h, cone)
                        selected = dict(banks)
                        selected["desk"] = banks["desk"][keep]
                        row = {"scene": scene["scene"], "error_mode":mode,"sigma_deg": sigma, "draw": draw, "cone_deg": cone,
                               'true_desk_within_reach':all(np.linalg.norm(np.maximum(truth[:2]-np.asarray(e['pos']),
                                  np.asarray(e['pos'])-truth[2:]).clip(min=0))<=REACH for e in seated),
                               "status": "empty", "error_m": None, "hit": False}
                        if len(selected["desk"]):
                            result = ES.infer(room, selected, path, events, True, True, None,
                                              padding=PAD, reach=.60, path_margin=.08, desk_reach=REACH)
                            info = result["objects"]["desk"]
                            row["status"] = info.get("status")
                            if result.get("boxes") and "desk" in result["boxes"]:
                                got = np.asarray(result["boxes"]["desk"], float)
                                row["error_m"] = float(np.linalg.norm(centre - (got[:2] + got[2:]) / 2))
                                row["hit"] = bool(row["error_m"] <= TOL)
                        rows.append(row)
    summary = {}
    for mode in ('independent','common'):
        for sigma in SIGMAS:
            for cone in CONES:
                sel = [r for r in rows if r['error_mode']==mode and r["sigma_deg"] == sigma and r["cone_deg"] == cone]
                errs = [r["error_m"] for r in sel if r["error_m"] is not None]
                summary["%s_sigma%g_cone%g" % (mode,sigma, cone)] = {
                    'n_rooms':len(set(r['scene'] for r in sel)),
                    "instances": len(sel), "hit_rate": float(np.mean([r["hit"] for r in sel])),
                    'missing':sum(r['error_m'] is None for r in sel),
                    'reach_excluded_rooms':len(set(r['scene'] for r in sel if not r['true_desk_within_reach'])),
                    "conflict": sum(1 for r in sel if r["status"] == "conflict"),
                    "error_median_m": float(np.median(errs)) if errs else None}
    record = {"scope": "Oracle desk-centre bearing sensitivity, not measured body facing; matched Gaussian draws, development scenes",
              'independent_unit':'14 scenes; three noise draws are repetitions, not 42 rooms',
              'baseline':'Compare desk-direction-causal distance_only, which uses the identical 1m distance assumption',
              'threshold':'No accuracy requirement is declared achieved merely from the best setting',
              "reach_m": REACH, "padding_m": PAD, "sigmas_deg": list(SIGMAS),
              "cones_deg": list(CONES), "draws": DRAWS, "summary": summary, "rows": rows}
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    for key in sorted(summary):
        s = summary[key]
        print("%-18s hit %.2f  conflict %2d  err %s" % (
            key, s["hit_rate"], s["conflict"],
            "--" if s["error_median_m"] is None else "%.2f" % s["error_median_m"]))
    return record


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "analysis/layout/desk_bearing.json")
