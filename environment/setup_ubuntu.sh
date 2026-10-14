#!/usr/bin/env bash
set -euo pipefail

# Run as the normal Ubuntu account, so the Python environment stays user-owned.
if [[ "$(id -u)" == 0 ]]; then
  echo '请用普通账号运行 bash setup_ubuntu.sh，不要在整条命令前加 sudo。' >&2
  exit 1
fi
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 22.04 ]]; then
  echo "需要 Ubuntu 22.04，当前系统：$PRETTY_NAME" >&2
  exit 1
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
imu_env_root="${IMU_ENV_ROOT:-$HOME/imu-research}"
mkdir -p -- "$imu_env_root"
log_file="$imu_env_root/setup-$(date +%Y%m%d-%H%M%S).log"
ln -sfn -- "$(basename -- "$log_file")" "$imu_env_root/setup-latest.log"

echo '此脚本安装 CPU 版 XGBoost/分析库，以及 ROS 2 Humble 桌面和开发工具。'
echo '管理员密码只在本机终端输入；接下来仅运行环境自检，不采集设备数据。'
sudo -v

install_and_check() {
  echo "=== $(date -Is) 开始 ML 环境安装 ==="
  bash "$script_dir/bootstrap_ml.sh" || return $?
  echo "=== $(date -Is) 开始 ROS 2 Humble 安装 ==="
  bash "$script_dir/bootstrap_ros_humble.sh" || return $?
  # ROS setup files can reference unset optional variables.
  set +u
  source /opt/ros/humble/setup.bash || return $?
  set -u
  ros2 --help >/dev/null || return $?
  ros2 pkg prefix rclpy || return $?
  ros2 pkg prefix rviz2 || return $?
  echo "=== $(date -Is) ML/ROS 安装与基础命令自检通过 ==="
  echo '这是环境检查；尚未连接 MID-360，也未训练 HAR 或布局模型。'
}

# sudo reads the password from the user's terminal, never from this log pipeline.
install_and_check 2>&1 | tee "$log_file"
echo "安装日志：$log_file"
