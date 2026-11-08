"""门位置：用户 2026-11-08 给出的参考布局（上墙 y = L，紧贴床左侧，左沿离左角 0.390 m，宽 0.775 m）。

门洞是可选侧信息。它画在我们自己的稠密图上，与输出同坐标系：是外部事实，不是独立验证。
仅在床位于门右侧并邻接该墙时，床 x 可写成 [门右沿, 房间宽 - 床宽]。
早前两种推算（门心取起点 x、卷尺 0.33 m 角距）由敏感性脚本同时保留，不自动合并。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 用户 2026-11-08 给出的参考布局：门洞左沿距左墙角 0.39 m、门宽 0.775 m，
# 于是门心 = 0.39 + 0.775/2 = 0.7775，门洞 x = [0.390, 1.165]。
# 这取代了此前「门心取起点 x」的推算（0.4375–1.2125）与更早的卷尺角距情景（0.33–1.105）。
DOOR = {"s-59d570ee": {"wall": "y_hi", "centre_x": 0.7775, "width_m": 0.775,
                       "left_offset_m": 0.39,
                       "source": "user reference layout 2026-11-08: left edge 0.390 m from the left wall, width 0.775 m"}}


def opening(sess,door_spec=None):
    d = DOOR.get(sess) if door_spec is None else door_spec
    if not d:
        return None
    half = d["width_m"] / 2.0
    return (d["centre_x"] - half, d["centre_x"] + half, d["wall"])


def clearance(pred,door_spec=None):
    """Projected consistency near the wall, not a door-swing collision test."""
    op = opening(pred.get("session"),door_spec)
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
        out[k] = {"gap_m": float(gap), "touches_door_wall": True,
                  "blocked": bool(gap < 0)}
    return {"opening_m": [x0, x1], "wall": wall, "objects": out}


def bed_x_interval(sess, room_w, bed_len,door_spec=None):
    """Conditional on bed to the right of the opening and adjoining that wall."""
    op = opening(sess,door_spec)
    if not op:
        return None
    lo, hi = op[1], room_w - bed_len
    signed=hi-lo
    return {'status':'conflict' if signed<0 else 'singleton' if signed==0 else 'interval',
            'lo':lo,'hi':hi,'signed_width_m':signed,'width_m':None if signed<0 else signed}


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
