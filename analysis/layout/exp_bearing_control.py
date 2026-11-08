"""Does the oracle-bearing threshold survive a different tie-break?

exp_tiebreak showed that, with a wide desk support, which of the equally supported
candidates is returned moves the desk hit rate by several rooms.  If the bearing channel
worked only by shrinking the support until one candidate is left, the threshold reported
by exp_desk_bearing would be a property of that one candidate rather than of the channel.
This re-runs exp_desk_bearing unchanged and only varies what infer() does with ties.
"""
import json
from pathlib import Path

from . import evidence_space as ES
from . import exp_desk_bearing as EB

CELLS = (("independent", 10.0, 45.0), ("independent", 20.0, 60.0), ("independent", 30.0, 60.0),
         ("independent", 45.0, 60.0), ("common", 30.0, 60.0))
SETTINGS = (("centroid", None), ("none", None),
            ("random", 5001), ("random", 5002), ("random", 5003))

_ORIG = ES.infer
_STATE = {"tie": "centroid", "rng": None}


def _patched(*args, **kwargs):
    kwargs.setdefault("tie_break", _STATE["tie"])
    if kwargs.get("rng") is None:
        kwargs["rng"] = _STATE["rng"]
    return _ORIG(*args, **kwargs)


def run(out, scratch="analysis/layout/_bearing_scratch.json"):
    table = {}
    for tie, rng in SETTINGS:
        _STATE["tie"] = tie
        _STATE["rng"] = rng
        ES.infer = _patched
        record = EB.run(scratch)
        key = tie if rng is None else "%s%d" % (tie, rng)
        table[key] = {"%s_sigma%g_cone%g" % c: record["summary"]["%s_sigma%g_cone%g" % c]["hit_rate"]
                      for c in CELLS}
    ES.infer = _ORIG
    Path(scratch).unlink(missing_ok=True)
    names = ["%s_sigma%g_cone%g" % c for c in CELLS]
    spread = {name: [table[k][name] for k in table] for name in names}
    record = {"scope": "Oracle desk-centre bearing with the tie-break varied; development scenes, 96 m",
              "cells": ["%s_sigma%g_cone%g" % c for c in CELLS],
              "settings": list(table), "hit_rate": table,
              "range_per_cell": {k: [min(v), max(v)] for k, v in spread.items()}}
    Path(out).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    for name in names:
        print("%-26s %s  spread %s" % (name, " ".join("%.2f" % table[k][name] for k in table),
                                       spread[name] if len(set(spread[name])) > 1 else "invariant"))
    return record


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "analysis/layout/bearing_control.json")
