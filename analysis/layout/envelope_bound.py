"""Actual-output radius audit. An envelope width alone is not an error bound."""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TOL = 0.5
THRESHOLDS = (0.5, 1.0, 1.5, 2.0)


def _rows(name):
    data = json.loads(Path(name).read_text(encoding="utf-8"))
    out = []
    for row in data["rows"]:
        envelope, error = row.get("envelope_m"), row.get("error_m")
        out.append(dict(row,envelope=None if envelope is None else float(max(envelope)),error=error))
    return out


def summarize(rows):
    table = []
    for limit in THRESHOLDS:
        inside = [r for r in rows if r['error'] is not None and r['envelope'] is not None and r["envelope"] <= limit]
        if not inside:
            continue
        ok = sum(1 for r in inside if r["error"] <= TOL)
        table.append({"envelope_limit_m": limit, "n": len(inside),
                      "share_within_half_m": ok / len(inside),
                      "median_error_m": float(np.median([r["error"] for r in inside]))})
    emitted=[r for r in rows if r['error'] is not None]
    allowed=[r for r in emitted if r.get('radius_upper_m') is not None and r['radius_upper_m']<=TOL]
    wrong=[r for r in allowed if r['error']>TOL+1e-9]
    violations=[r for r in emitted if r.get('truth_center_in_envelope') and r.get('radius_upper_m') is not None
                and r['error']>r['radius_upper_m']+1e-8]
    if violations:raise AssertionError('Farthest-envelope conditional inequality violated')
    return {'n':len(rows),'n_rooms':len({r['scene'] for r in rows}),
            'n_emitted':len(emitted),'missing_or_ineligible':len(rows)-len(emitted),
            'accepted':len(allowed),'accepted_wrong':len(wrong),'accepted_share_all':len(allowed)/len(rows) if rows else None,
            'accepted_wrong_rate':len(wrong)/len(allowed) if allowed else None,
            'accepted_truth_outside_envelope':sum(not r.get('truth_center_in_envelope',False) for r in allowed),
            'conditional_inequality_violations':len(violations),
            'legacy_max_axis_width_screen':table,'unit':'scene-budget-arm-object; repeated, not independent samples'}


def run(out,ablation=None,sweep=None):
    payload = {"tolerance_m": TOL,
               'rule':'Actual output farthest centre-envelope radius <=0.5m',
               'condition':'True centre belongs to the reported centre envelope; not runtime verified',
               "ablation": summarize(_rows(ablation or HERE/"span_ablation.json")),
               "sweep": summarize(_rows(sweep or HERE/"span_sweep.json"))}
    Path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for key in ("ablation", "sweep"):
        block = payload[key]
        print(key, "rows", block["n"])
        for row in block["legacy_max_axis_width_screen"]:
            print("  envelope<=%.1f m: n=%3d within0.5=%5.1f%% median_err=%.2f" %
                  (row["envelope_limit_m"], row["n"], 100 * row["share_within_half_m"],
                   row["median_error_m"]))
        print('  radius rule accepted',block['accepted'],'wrong',block['accepted_wrong'],
              'of',block['n'],'including missing/ineligible')


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default=str(HERE/'envelope_bound.json'))
    p.add_argument('--ablation');p.add_argument('--sweep');a=p.parse_args();run(a.output,a.ablation,a.sweep)
