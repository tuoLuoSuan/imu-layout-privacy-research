"""门位置：用户 2026-11-08 在稠密图上标注（贴 y = L 那面墙，紧挨床的左侧）。

门不是装饰：门洞占掉上墙的一段，家具不能压在上面。这给出一个**外部**约束——
它不来自「床贴着右墙」这类假设，而来自用户在图上指出的事实。床的 x 区间因此可以被
夹到 [门右沿, 房间宽 - 床长]，宽度与「床靠右墙」几乎一样，但证据来源不同。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 起点 S=(0.825, 3.845) 就在门口，门宽 77.5 cm（用户早前给过），故门洞 = S 两侧各半宽。
DOOR = {"s-59d570ee": {"wall": "y_hi", "centre_x": 0.825, "width_m": 0.775,
                       "source": "user annotation on the dense map, 2026-11-08"}}


def opening(sess):
    d = DOOR.get(sess)
    if not d:
        return None
    half = d["width_m"] / 2.0
    return (d["centre_x"] - half, d["centre_x"] + half, d["wall"])


def clearance(pred):
    op = opening(pred.get("session"))
    if not op:
        return None
    x0, x1, wall = op
    L = pred["room"][1]
    out = {}
    for k, b in pred["boxes"].items():
        touches = b[3] > L - 0.30 if wall == "y_hi" else b[1] < 0.30
        if not touches:
            out[k] = {"gap_m": None, "touches_door_wall": False}
            continue
        gap = max(x0 - b[2], b[0] - x1)
        out[k] = {"gap_m": round(float(gap), 3), "touches_door_wall": True,
                  "blocked": bool(gap < 0)}
    return {"opening_m": [round(x0, 3), round(x1, 3)], "wall": wall, "objects": out}


def bed_x_interval(sess, room_w, bed_len):
    op = opening(sess)
    if not op:
        return None
    lo, hi = op[1], room_w - bed_len
    return {"lo": round(lo, 3), "hi": round(hi, 3), "width_m": round(max(0.0, hi - lo), 3)}


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sess = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "output", "layout-recon", "s-59d570ee")
    with open(os.path.join(sess, "prediction.json"), encoding="utf-8") as fh:
        pred = json.load(fh)
    op = opening(pred["session"])
    print("门洞 x %.3f-%.3f m，在 %s 墙，宽 %.3f m" % (op[0], op[1], op[2], op[1] - op[0]))
    for k, v in clearance(pred)["objects"].items():
        if v["touches_door_wall"]:
            print("  %-5s 净距 %+.3f m%s" % (k, v["gap_m"], "  压住门洞" if v["blocked"] else ""))
    bed = pred["boxes"]["bed"]
    iv = bed_x_interval(pred["session"], pred["room"][0], bed[2] - bed[0])
    print("床 x 允许区间 [%.3f, %.3f]，宽 %.3f m；预测 %.3f-%.3f"
          % (iv["lo"], iv["hi"], iv["width_m"], bed[0], bed[2]))
