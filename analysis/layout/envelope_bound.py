"""Is the support envelope a usable bound on the point error?

The envelope is computed from the *supported* boxes only, so it bounds the error
only while the truth stays feasible.  This module measures that conditional
statement on the ablation rows (constraints taken from the route) and on the
counterfactual span sweep (anchors placed by hand, so the truth can fall out).
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TOL = 0.5
THRESHOLDS = (0.5, 1.0, 1.5, 2.0)


def _rows(name):
    data = json.loads((HERE / name).read_text(encoding="utf-8"))
    out = []
    for row in data["rows"]:
        envelope, error = row.get("envelope_m"), row.get("error_m")
        if envelope is None or error is None:
            continue
        out.append({"envelope": float(max(envelope)), "error": float(error),
                    "object": row.get("object"), "arm": row.get("arm")})
    return out


def summarize(rows):
    table = []
    for limit in THRESHOLDS:
        inside = [r for r in rows if r["envelope"] <= limit]
        if not inside:
            continue
        ok = sum(1 for r in inside if r["error"] <= TOL)
        table.append({"envelope_limit_m": limit, "n": len(inside),
                      "share_within_half_m": ok / len(inside),
                      "median_error_m": float(np.median([r["error"] for r in inside]))})
    loose = sum(1 for r in rows if r["envelope"] > 1.0 and r["error"] <= TOL)
    bad = sum(1 for r in rows if r["envelope"] <= 1.0 and r["error"] > TOL)
    return {"n": len(rows), "table": table,
            "envelope_gt_1m_but_ok": loose, "envelope_le_1m_but_wrong": bad}


def run(out):
    payload = {"tolerance_m": TOL,
               "ablation": summarize(_rows("span_ablation.json")),
               "sweep": summarize(_rows("span_sweep.json"))}
    Path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for key in ("ablation", "sweep"):
        block = payload[key]
        print(key, "rows", block["n"])
        for row in block["table"]:
            print("  envelope<=%.1f m: n=%3d within0.5=%5.1f%% median_err=%.2f" %
                  (row["envelope_limit_m"], row["n"], 100 * row["share_within_half_m"],
                   row["median_error_m"]))
        print("  envelope>1.0 but ok: %d   envelope<=1.0 but wrong: %d" %
              (block["envelope_gt_1m_but_ok"], block["envelope_le_1m_but_wrong"]))


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else str(HERE / "envelope_bound.json"))
