#!/usr/bin/env bash
set -uo pipefail
echo '[account]'
id
echo '[system]'
cat /etc/os-release
echo '[resources]'
nproc
free -h
df -h /
echo '[time]'
date -Is
timedatectl status
echo '[network]'
ip -br addr
ip route
echo '[packages]'
dpkg-query -W python3-venv python3-pip python3.10-venv build-essential cmake git curl locales software-properties-common open-vm-tools-desktop 2>/dev/null || true
echo '[python]'
python3 --version
echo '[privileges]'
if sudo -n true 2>/dev/null; then
  echo 'noninteractive_sudo=available'
else
  echo 'noninteractive_sudo=requires_local_password'
fi
echo '[download_sources]'
python3 - <<'PY'
import json
from urllib.request import Request, urlopen
sources = (
    ('xgboost_cpu_pin', 'https://pypi.org/pypi/xgboost-cpu/3.1.2/json'),
    ('ros_apt_source_release', 'https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest'),
)
for name, url in sources:
    try:
        with urlopen(Request(url, headers={'User-Agent': 'imu-research-environment-check'}), timeout=8) as response:
            data = json.load(response)
            version = data.get('tag_name') or data.get('info', {}).get('version')
            print(f'{name}: HTTP {response.status}, version={version}')
    except Exception as exc:
        print(f'{name}: {type(exc).__name__}: {exc}')
PY
