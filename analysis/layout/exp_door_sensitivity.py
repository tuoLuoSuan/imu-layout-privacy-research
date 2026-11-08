"""How much does the layout conclusion depend on where exactly the door is?

The door centre came from the user's annotation: it was read off a dense map and
back-computed from the start point S=(0.825, 3.845).  This script sweeps the centre
across the wall and reports what the bed axis is allowed to do under each shift.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import door as DOOR
from pathlib import Path

SESS = "output/layout-recon/s-59d570ee"
NAME = "s-59d570ee"
SHIFTS = (-0.30, -0.20, -0.10, 0.0, 0.10, 0.20, 0.30)


def run(out,session=SESS):
    # Read the explicitly selected replay, rather than silently solving old cached IMU.
    pred=json.loads((Path(session)/'prediction.json').read_text(encoding='utf-8'))
    room_w = pred['room'][0]
    bed_len = 1.525
    base = dict(DOOR.DOOR[NAME])
    rows = []
    for shift in SHIFTS:
        spec=dict(base, centre_x=base["centre_x"] + shift)
        x0, x1, wall = DOOR.opening(NAME,spec)
        iv = DOOR.bed_x_interval(NAME, room_w, bed_len,spec)
        lo, hi = iv["lo"], iv["hi"]
        clr = DOOR.clearance(pred,spec)["objects"]["bed"]
        rows.append({"shift_m": shift, "door_x0": x0, "door_x1": x1,
                     "bed_x_lo": lo, "bed_x_hi": hi,"status":iv['status'],
                     "width_m":iv['width_m'],'signed_width_m':iv['signed_width_m'],
                     "bed_clearance_m": clr["gap_m"], "bed_blocked": clr["blocked"]})
    # User previously reported corner offset 0.33m. Its equivalence to this frame is
    # unresolved, so retain a provenance alternative rather than choose a favourable door.
    variants=[]
    for source,centre in [('start_inferred',base['centre_x']),('earlier_tape_same_frame_if_valid',.33+.775/2)]:
        spec=dict(base,centre_x=centre)
        x0,x1,_=DOOR.opening(NAME,spec)
        variants.append({'source':source,'opening_m':[x0,x1],
                         'reference_bed_projection_gap_m':1.17-x1,
                         'prediction_gap_m':DOOR.clearance(pred,spec)['objects']['bed']['gap_m']})
    record = {"scope": "User-annotated door centre, +/-0.30 m sweep, real room s-59d570ee",
              "room_width_m": room_w, "bed_length_m": bed_len,
              'input_prediction':str(Path(session)/'prediction.json'),
              'door_source_variants':variants,
              'limitation':'Same-frame provenance unresolved; start x need not equal door centre; no door swing model or independent validation',
              "predicted_bed_x": [pred["boxes"]["bed"][0], pred["boxes"]["bed"][2]],
              "rows": rows}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
    print("shift   door x0-x1      bed x interval     width  clearance  blocked")
    for r in rows:
        print("%+.2f   %.3f-%.3f   %.3f-%.3f   %.3f   %+.3f    %s" % (
            r["shift_m"], r["door_x0"], r["door_x1"], r["bed_x_lo"], r["bed_x_hi"],
            r["signed_width_m"], r["bed_clearance_m"], r["bed_blocked"]))
    return record


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "analysis/layout/door_sensitivity.json",
        sys.argv[2] if len(sys.argv)>2 else SESS)
