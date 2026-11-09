
"""Out-of-sample confirmation: wall prior on 009 new-5000 rooms (batch tar members)."""
import concurrent.futures, json, sys, tarfile
from pathlib import Path
import numpy as np
sys.path.insert(0, r"D:/Project/imu环境重建")
from analysis.layout import multi_instance as M
from analysis.layout.selection_diagnostics import rerank_pools
from analysis.layout.exp_walk_range import coverage_route, survey_prefixes
from analysis.layout.desk_wall_audit import _filter_pool

BASE = Path(r"D:/Project/imu环境重建/output/research-sync/2026-11-09-expansion-imu-009/new5000")
OUT = Path(r"D:/Download/new5000-confirm"); OUT.mkdir(parents=True, exist_ok=True)

def extract(n_batches, per_batch):
    files = []
    for i in range(n_batches):
        p = BASE / ("batch-%02d.tar.gz" % i)
        if not p.exists(): continue
        with tarfile.open(p) as tf:
            members = [m for m in tf.getmembers() if m.name.endswith(".json")][:per_batch]
            for m in members:
                dst = OUT / Path(m.name).name
                if not dst.exists():
                    dst.write_bytes(tf.extractfile(m).read())
                files.append(dst)
    return files

def arm(scene, path, events, tol, cache):
    original = M._constraint_search
    def select(inventory, pools, targets, counts, tol=tol):
        ranked = rerank_pools(pools, [scene["W"], scene["L"]], path, "outline")
        ranked = _filter_pool(ranked, (scene["W"], scene["L"]), tol)
        return original(inventory, ranked, targets, counts)
    M._constraint_search = select
    try:
        r = M.decode_instances([scene["W"], scene["L"]], scene["inventory"], events, path, proposal_cache=cache)
    finally:
        M._constraint_search = original
    return M.score_instances(r["boxes"], scene["gt"])

def one(f):
    scene = M.load_native(f)
    ep = coverage_route(scene); ratio = len(ep["reachable_ids"]) / len(ep["free_ids"])
    path = survey_prefixes(ep, [1.0 / ratio])[0]["path"]
    events = M.event_sequence(scene, path, 14)
    out = {}
    for name, tol in (("none", None), ("wall", 0.15)):
        s = arm(scene, path, events, tol, {})
        out[name] = {"whole": bool(s["all_instances_hit"]), "f1": float(s["f1"]),
                     "desk_tp": s["per_class"]["desk"]["tp"], "desk_n": s["per_class"]["desk"]["n_truth"]}
    return out

if __name__ == "__main__":
    files = extract(3, 100)
    print("rooms", len(files))
    res = {"none": [], "wall": []}
    with concurrent.futures.ProcessPoolExecutor(max_workers=10) as pool:
        for r in pool.map(one, [str(f) for f in files]):
            for k in res: res[k].append(r[k])
    summary = {}
    for k, v in res.items():
        n = len(v); w = sum(x["whole"] for x in v)
        summary[k] = {"n": n, "whole": w, "rate": w / n, "f1": float(np.mean([x["f1"] for x in v])),
                      "desk": sum(x["desk_tp"] for x in v) / max(1, sum(x["desk_n"] for x in v))}
        print("%-5s %d/%d = %.1f%%  F1 %.3f  desk %.1f%%" % (k, w, n, 100 * w / n, 100 * summary[k]["f1"], 100 * summary[k]["desk"]))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
