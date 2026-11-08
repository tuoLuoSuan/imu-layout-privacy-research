
"""Turn the activity-frontier sweep into (a) a walking-budget curve and (b) the
P/T/A/TA x U/K ablation, both read straight from the stored rows (no re-solving)."""
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FRONTIER = os.path.join(REPO, "output", "research-sync",
                        "2026-11-08-activity-frontier-001", "frontier-development.json")
OUT = os.path.join(HERE, "budget_curve.json")

OBJECTS = ("bed", "desk", "cab", "chair")
ARMS = ("P-U", "P-K", "T-U", "A-U", "TA-U", "TA-K")
POLICIES = ("local_repeat", "dispersed")
TOL = "0.5"
HIT_M = 0.5


def load(path=FRONTIER):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cell(rows, arm, policy, budget):
    """One (arm, policy, budget) bucket -> per-object hit rate, envelope, coverage."""
    picked = [r for r in rows
              if r["arm"] == arm and r["policy"] == policy and r["budget_m"] == budget]
    if not picked:
        return None
    out = {"n": len(picked), "coverage": st.mean(r["coverage"] for r in picked)}
    hit = {}
    env = {}
    err = {}
    for obj in OBJECTS:
        hits = []
        envs = []
        errs = []
        for r in picked:
            sc = r.get("scores", {}).get(TOL)
            if not sc:
                continue
            e = sc["center_error_m"].get(obj)
            d = sc["center_diameter_upper_m"].get(obj)
            if e is None:
                continue
            hits.append(1.0 if e <= HIT_M else 0.0)
            errs.append(e)
            if d is not None:
                envs.append(d)
        hit[obj] = st.mean(hits) if hits else None
        env[obj] = st.median(envs) if envs else None
        err[obj] = st.median(errs) if errs else None
    out.update({"hit": hit, "envelope_med": env, "error_med": err})
    return out


def curve(rows, arm="TA-U", policy="dispersed"):
    budgets = sorted({r["budget_m"] for r in rows})
    return [dict(cell(rows, arm, policy, b) or {}, budget_m=b, arm=arm, policy=policy)
            for b in budgets]


def ablation(rows, budget=96.0, policy="dispersed"):
    """P/T/A/TA x U/K at one budget, plus the two policy rows."""
    table = {}
    for arm in ARMS:
        c = cell(rows, arm, policy, budget)
        if c:
            table[arm] = c
    return table


def policy_gap(rows, arm="TA-U", budget=96.0):
    return {p: cell(rows, arm, p, budget) for p in POLICIES}


def summarize(rows):
    out = {"arms": {}, "curves": {}}
    for arm in ARMS:
        for policy in POLICIES:
            key = "%s/%s" % (arm, policy)
            out["curves"][key] = curve(rows, arm, policy)
        out["arms"][arm] = {
            "budget96_local_repeat": cell(rows, arm, "local_repeat", 96.0),
            "budget96_dispersed": cell(rows, arm, "dispersed", 96.0),
            "budget32_dispersed": cell(rows, arm, "dispersed", 32.0),
        }
    out["ablation_at_96_dispersed"] = ablation(rows, 96.0, "dispersed")
    out["policy_gap_TA-U_96"] = policy_gap(rows, "TA-U", 96.0)
    return out


def report(res):
    def fmt(d):
        if not d:
            return "-"
        return " ".join("%s %.2f" % (o, d["hit"][o]) if d["hit"][o] is not None else "%s -" % o
                        for o in OBJECTS)
    print("== P/T/A/TA x U/K, 96 m, dispersed ==")
    for arm in ARMS:
        d = res["ablation_at_96_dispersed"].get(arm)
        if not d:
            continue
        print("%-6s coverage %.3f  hit %s  env %s" % (
            arm, d["coverage"], fmt(d),
            " ".join("%s %.2f" % (o, d["envelope_med"][o]) for o in OBJECTS)))
    print("== TA-U budget curve, dispersed ==")
    for row in res["curves"]["TA-U/dispersed"]:
        d = row
        print("%5.1f m  coverage %.3f  hit %s" % (d["budget_m"], d["coverage"], fmt(d)))
    print("== TA-U vs TA-K, 96 m ==")
    for policy in POLICIES:
        a = res["arms"]["TA-U"][("budget96_%s" % policy)]
        b = res["arms"]["TA-K"][("budget96_%s" % policy)]
        print("%-12s U %s | K %s" % (policy, fmt(a), fmt(b)))


def run(out=OUT):
    rows = load()["rows"]
    res = summarize(rows)
    res["source"] = os.path.relpath(FRONTIER, REPO).replace(os.sep, "/")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    report(res)
    print("written", out)
    return res


if __name__ == "__main__":
    run()
