"""数据与权重的解析位置。全部可用环境变量覆盖，便于在别处复现。"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 原始录音、点云、AI2-THOR 导出都放这里（不入库）
DATA = os.environ.get('IMU_LAYOUT_DATA', os.path.join(REPO, 'output', 'lidar', '2026-11-05-static-scan-002'))
# RoNIN 的模型结构与权重（不入库，见 README）
RONIN_ARCH = os.environ.get('IMU_LAYOUT_RONIN_ARCH', os.path.join(REPO, 'docs', 'reviews', 'evidence', '2026-10-17-ds056-baseline-625a270a', 'ronin-model.py'))
RONIN_CKPT = os.environ.get('IMU_LAYOUT_RONIN_CKPT', os.path.join(REPO, 'docs', 'reviews', 'evidence', '2026-10-17-ds056-baseline-625a270a', 'checkpoint_gsn_latest.pt'))
# AI2-THOR 场景导出
THOR = os.environ.get('IMU_LAYOUT_THOR', os.path.join(REPO, 'output', 'thor'))
