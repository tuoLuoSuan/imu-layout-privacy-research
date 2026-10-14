#!/usr/bin/env bash
set -euo pipefail
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 22.04 ]]; then
  echo "此脚本为 Ubuntu 22.04 准备。当前：$PRETTY_NAME" >&2; exit 1
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
imu_env_root="${IMU_ENV_ROOT:-$HOME/imu-research}"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip build-essential cmake git curl ca-certificates openssh-server
sudo systemctl enable --now ssh
mkdir -p -- "$imu_env_root"
python3 -m venv "$imu_env_root/.venv"
"$imu_env_root/.venv/bin/python" -m pip install --upgrade pip
"$imu_env_root/.venv/bin/python" -m pip install -r "$script_dir/requirements-cpu.txt"
"$imu_env_root/.venv/bin/python" "$script_dir/smoke_test.py" > "$imu_env_root/environment_report.json"
"$imu_env_root/.venv/bin/python" -m pip freeze > "$imu_env_root/requirements-installed.txt"
echo "基础 ML 环境已安装；验收报告：$imu_env_root/environment_report.json"
echo "进入环境：source $imu_env_root/.venv/bin/activate"
