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
import layout_solver as LS

SESS = "output/layout-recon/s-59d570ee"
NAME = "s-59d570ee"
SHIFTS = (-0.30, -0.20, -0.10, 0.0, 0.10, 0.20, 0.30)


def run(out):
    pred, _ = LS.solve(SESS, save=False)
    room_w = 2.84
    bed_len = 1.525
    base = dict(DOOR.DOOR[NAME])
    rows = []
    for shift in SHIFTS:
        DOOR.DOOR[NAME] = dict(base, centre_x=base["centre_x"] + shift)
        x0, x1, wall = DOOR.opening(NAME)
        iv = DOOR.bed_x_interval(NAME, room_w, bed_len)
        lo, hi = iv["lo"], iv["hi"]
        clr = DOOR.clearance(pred)["objects"]["bed"]
        rows.append({"shift_m": shift, "door_x0": x0, "door_x1": x1,
                     "bed_x_lo": lo, "bed_x_hi": hi, "width_m": hi - lo,
                     "bed_clearance_m": clr["gap_m"], "bed_blocked": clr["blocked"]})
    DOOR.DOOR[NAME] = base
    record = {"scope": "User-annotated door centre, +/-0.30 m sweep, real room s-59d570ee",
              "room_width_m": room_w, "bed_length_m": bed_len,
              "predicted_bed_x": [pred["boxes"]["bed"][0], pred["boxes"]["bed"][2]],
              "rows": rows}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
    print("shift   door x0-x1      bed x interval     width  clearance  blocked")
    for r in rows:
        print("%+.2f   %.3f-%.3f   %.3f-%.3f   %.3f   %+.3f    %s" % (
            r["shift_m"], r["door_x0"], r["door_x1"], r["bed_x_lo"], r["bed_x_hi"],
            r["width_m"], r["bed_clearance_m"], r["bed_blocked"]))
    return record


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "analysis/layout/door_sensitivity.json")
