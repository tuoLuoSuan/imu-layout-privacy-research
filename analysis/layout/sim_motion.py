# -*- coding: utf-8 -*-
"""场景真值 -> 人体/设备运动 -> 原始六轴 IMU。只生成传感器流，不做任何前端处理。

物理约定：世界系 x 右、y 前、z 上；g=(0,0,-9.81)。
设备系经 R(t) 映射到世界：a_meas = R^T (p'' - g)，omega_meas = vee(R^T R')。
"""
import json, math, os
import numpy as np

G = 9.81
# 房间与家具真值（s-59d570ee 的雷达参考框），仅用于生成器与评价
ROOM = (2.84, 4.045)
FURN = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10),
        'cab': (0.05, 0.0, 0.65, 1.05), 'chair': (1.11, 0.92, 1.55, 1.36)}
START = np.array([0.825, 3.845])

# 活动脚本：(t0, t1, 标签, 目标点或 None, 姿态档位)
# 步速约 0.5–0.8 m/s（室内慢走），不再用 0.2 m/s 那种「走」——那样步态能量与位移严重不匹配
SCRIPT = [
    (0.0, 5.0,  'other',   START,               'stand'),
    (5.0, 8.2,  'walk',    (1.33, 1.78),        'walk'),
    (8.2, 9.0,  'walk',    (1.33, 1.14),        'walk'),
    (9.0, 12.0, 'seated',  (1.33, 1.14),        'sit'),
    (12.0, 13.0, 'walk',   (1.33, 1.14),        'stand'),
    (13.0, 16.4, 'walk',   (1.25, 0.54),        'walk'),
    (16.4, 19.0, 'cabinet', (1.25, 0.54),       'reach'),
    (19.0, 22.2, 'walk',   (1.95, 2.30),        'walk'),
    (22.2, 23.0, 'walk',   (1.95, 2.70),        'walk'),
    (23.0, 24.5, 'lying',  (1.95, 2.75),        'lie'),
    (24.5, 29.0, 'lying',  (1.95, 2.75),        'lie'),
    (29.0, 30.2, 'walk',   (1.95, 2.70),        'stand'),
    (30.2, 33.4, 'walk',   START,               'walk'),
    (33.4, 36.0, 'other',  START,               'stand'),
]
H_BODY = {'stand': 1.60, 'walk': 1.60, 'sit': 0.95, 'reach': 1.60, 'lie': 0.32}
PITCH = {'stand': -35.0, 'walk': -35.0, 'sit': -12.0, 'reach': -20.0, 'lie': 58.0}
HAND_FWD = {'stand': 0.34, 'walk': 0.36, 'sit': 0.30, 'reach': 0.44, 'lie': 0.16}
HAND_UP = {'stand': -0.55, 'walk': -0.55, 'sit': -0.32, 'reach': -0.50, 'lie': -0.18}
F_STEP = 1.85


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def smooth_d(u, d):
    u = min(max(u, 0.0), 1.0)
    return 6 * u * (1 - u) / d


def smooth_dd(u, d):
    u = min(max(u, 0.0), 1.0)
    return (6 - 12 * u) / (d * d)


class Motion(object):
    """分段 C2 运动：位置用 smoothstep 插值；朝向在段起点 0.8 s 内平滑转过去。"""

    def __init__(self, script=SCRIPT):
        self.script = script
        self.t_end = script[-1][1]
        self.targets = [np.array(s[3], float) for s in script]
        self.psi = []
        carry = 0.0
        for i in range(len(script)):
            prev = self.targets[i - 1] if i else START.astype(float)
            d = self.targets[i] - prev
            if np.linalg.norm(d) > 1e-6:
                want = math.atan2(d[1], d[0])
                while want - carry > math.pi:
                    want -= 2 * math.pi
                while want - carry < -math.pi:
                    want += 2 * math.pi
                carry = want
            self.psi.append(carry)

    def _seg(self, t):
        for s in self.script:
            if s[0] <= t < s[1]:
                return s
        return self.script[-1]

    def _idx(self, t):
        for k, s in enumerate(self.script):
            if s[0] <= t < s[1]:
                return k
        return len(self.script) - 1

    def state(self, t):
        """返回 (p, p', p'', h, dh, psi, pose, moving)。"""
        i = self._idx(t)
        s = self.script[i]
        target = self.targets[i]
        prev = self.targets[i - 1] if i else START.astype(float)
        dur = max(s[1] - s[0], 1e-6)
        u = (t - s[0]) / dur
        p = prev + (target - prev) * smooth(u)
        dp = (target - prev) * smooth_d(u, dur)
        ddp = (target - prev) * smooth_dd(u, dur)
        prev_pose = self.script[i - 1][4] if i else s[4]
        cur_pose = s[4]
        if prev_pose != cur_pose:
            blend = smooth(min(1.0, (t - s[0]) / 0.8))
            dh = (H_BODY[cur_pose] - H_BODY[prev_pose]) * smooth_d(min(1.0, (t - s[0]) / 0.8), 0.8)
        else:
            blend, dh = 1.0, 0.0
        h = H_BODY[prev_pose] + (H_BODY[cur_pose] - H_BODY[prev_pose]) * blend
        psi_prev = self.psi[i - 1] if i else self.psi[0]
        psi_cur = self.psi[i]
        if i == 0 or abs(psi_cur - psi_prev) < 1e-9:
            psi = psi_cur
        else:
            psi = psi_prev + (psi_cur - psi_prev) * smooth(min(1.0, (t - s[0]) / 0.8))
        # 步态权重在走/停之间平滑过渡，否则位置的硬阶跃会在二阶差分里炸掉
        if s[2] == 'walk':
            moving = min(smooth((t - s[0]) / 0.5), smooth((s[1] - t) / 0.5))
        else:
            moving = 0.0
        return p, dp, ddp, h, dh, psi, cur_pose, moving, blend, prev_pose


# 设备系里「上」的方向，直接取自真实录音的加速度均值（不是猜的）：
# 走 [6.70,-6.83,-0.57]/9.8、坐 [8.51,-2.93,-0.65]/9.8、躺 [1.40,-1.25,-8.76]/9.8、开柜 [5.70,-7.97,0]/9.8
U_UP = {'stand': (0.68, -0.70, -0.06), 'walk': (0.68, -0.70, -0.06),
        'sit': (0.94, -0.32, -0.07), 'reach': (0.58, -0.81, 0.0),
        'lie': (0.16, -0.14, -0.97)}


def basis_from_up(u):
    """给定设备系里的「上」向量，构造姿态 R（行向量为设备三轴在世界系的方向）。"""
    u = np.asarray(u, float); u = u / np.linalg.norm(u)
    h = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    r1 = np.cross(h, u); r1 /= np.linalg.norm(r1)
    r2 = np.cross(u, r1)
    return np.vstack([r1, r2, u])


def device_pose(t, st):
    """人体状态 -> 设备位置与姿态（含步态摆动）。"""
    p, dp, ddp, h, dh, psi, pose, moving, blend, prev_pose = st
    ph = 2 * math.pi * F_STEP * t
    # 步态摆幅必须跟真实步速成比例：位移小、摆动大，网络就以为在快走（这一步曾让路程高估 4.3 倍）
    speed = float(np.linalg.norm(dp))
    swing = moving * min(speed / 0.8, 1.5)
    # 手在身体右前方；换姿势时手的前伸/高度也要连续过渡
    fwd = HAND_FWD[prev_pose] + (HAND_FWD[pose] - HAND_FWD[prev_pose]) * blend
    up = HAND_UP[prev_pose] + (HAND_UP[pose] - HAND_UP[prev_pose]) * blend
    pbase = PITCH[prev_pose] + (PITCH[pose] - PITCH[prev_pose]) * blend
    off = np.array([0.18 + 0.010 * swing * math.sin(ph), fwd, 0.0])
    c, s = math.cos(psi), math.sin(psi)
    hand_world = p + np.array([c * off[0] - s * off[1], s * off[0] + c * off[1]])
    # 脚跟着地：每步一个周期光滑的窄脉冲（周期函数，避免跨步边界出现位置跳变）
    frac = (t * F_STEP) % 1.0
    step = 0.5 * (1.0 + math.cos(2.0 * math.pi * (frac - 0.10))) ** 4 if swing > 1e-6 else 0.0
    hz = h + up + 0.012 * swing * math.sin(2 * ph) - 0.008 * swing * step
    pos = np.array([hand_world[0], hand_world[1], hz])
    # 姿态：先按实测量出的「上」方向定俯仰，再绕世界竖轴转到人体朝向，最后叠小摆幅
    u = (1 - blend) * np.array(U_UP[prev_pose]) + blend * np.array(U_UP[pose])
    yaw = psi + math.radians(2.5) * swing * math.sin(ph + 0.7)
    psw = math.radians(3.0) * swing * math.sin(2 * ph + 0.3)
    rsw = math.radians(1.5) * swing * math.sin(ph + 1.1)
    R = rot(yaw, 0.0, 0.0) @ basis_from_up(u) @ rot(0.0, psw, rsw)
    return pos, R, yaw


def rot(yaw, pitch, roll):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def vee(M):
    return np.array([M[2, 1] - M[1, 2], M[0, 2] - M[2, 0], M[1, 0] - M[0, 1]]) / 2.0


def generate(fs=120.0, seed=7, seconds=None):
    """生成原生六轴：返回 dict(t, acc, gyro, truth)。"""
    m = Motion()
    T = m.t_end if seconds is None else min(seconds, m.t_end)
    rng = np.random.default_rng(seed)
    n = int(round(T * fs))
    t = np.arange(n) / fs
    acc = np.zeros((n, 3))
    gyro = np.zeros((n, 3))
    truth = {'pos': [], 'yaw': [], 'pitch': [], 'h': [], 'label': [], 'R': []}
    eps = 1e-4
    for k, tk in enumerate(t):
        st = m.state(tk)
        pos, R, yaw = device_pose(tk, st)
        # 设备位置二阶导：用解析步态做中心差分（步态项无解析式）
        lo = max(tk - eps, 0.0)
        hi = min(tk + eps, T - 1e-9)
        h = hi - lo
        p_f = device_pose(hi, m.state(hi))[0]
        p_c = device_pose(tk, m.state(tk))[0]
        p_b = device_pose(lo, m.state(lo))[0]
        if h >= 2 * eps - 1e-12:  # 内部点：标准三点二阶差分
            a_world = (p_f - 2 * p_c + p_b) / (eps * eps)
        else:                     # 端点：一阶前向二阶差分
            p2 = device_pose(min(tk + 2 * eps, T - 1e-9), m.state(min(tk + 2 * eps, T - 1e-9)))[0]
            a_world = (p_f - 2 * p_c + p2) / (eps * eps)
        acc[k] = R.T @ (a_world - np.array([0.0, 0.0, -G]))
        R2 = device_pose(tk + eps, m.state(tk + eps))[1]
        gyro[k] = vee(R.T @ R2) / eps
        s = m._seg(tk)
        truth['pos'].append(pos); truth['yaw'].append(yaw); truth['pitch'].append(0.0)
        truth['R'].append(R)
        truth['h'].append(st[3]); truth['label'].append(s[2])
    acc += rng.normal(0, 0.055, acc.shape) + np.array([0.04, -0.03, 0.05])
    gyro += rng.normal(0, 0.008, gyro.shape) + np.array([0.004, -0.003, 0.002])
    ts = np.round((t + 1e-6 * rng.normal(0, 1, n)) * 1e9).astype(np.int64) + 1700000000000000000
    for name, A in (('pos', np.array(truth['pos'])), ('yaw', np.array(truth['yaw'])),
                    ('pitch', np.array(truth['pitch'])), ('h', np.array(truth['h'])),
                    ('R', np.array(truth['R']))):
        truth[name] = A
    truth['segments'] = [[s[0], s[1], s[2]] for s in m.script]
    return {'t': t, 'ts_ns': ts, 'acc': acc, 'gyro': gyro, 'truth': truth, 'fs': fs}
