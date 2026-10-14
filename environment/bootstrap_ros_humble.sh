#!/usr/bin/env bash
set -euo pipefail
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 22.04 ]]; then echo '需要 Ubuntu 22.04' >&2; exit 1; fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
sudo apt-get update
sudo apt-get install -y locales software-properties-common curl ca-certificates
sudo locale-gen en_US en_US.UTF-8
export LANG=en_US.UTF-8
sudo add-apt-repository -y universe
ros_source_file="$script_dir/vendor/ros2-apt-source_1.3.0.jammy_all.deb"
if [[ -f "$ros_source_file" ]]; then
  # Official release package transferred from Windows; see vendor/source.json.
  # This avoids depending on the GitHub API when it is rate-limited or unreachable.
  (cd "$script_dir/vendor" && sha256sum -c ros2-apt-source_1.3.0.jammy_all.deb.sha256)
else
  ros_source_version="$(curl --connect-timeout 10 --max-time 30 -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')"
  ros_source_file="$(mktemp --suffix=.deb)"
  curl --connect-timeout 10 --max-time 60 -fL "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ros_source_version}/ros2-apt-source_${ros_source_version}.jammy_all.deb" -o "$ros_source_file"
fi
if [[ "$(dpkg-deb -f "$ros_source_file" Package)" != ros2-apt-source ]]; then
  echo 'ROS 官方仓库配置包名称不符，停止安装。' >&2
  exit 1
fi
sudo dpkg -i "$ros_source_file"
sudo apt-get update
sudo apt-get install -y ros-humble-desktop ros-dev-tools python3-colcon-common-extensions
echo 'ROS 已安装。新终端运行 source /opt/ros/humble/setup.bash'
echo '尚未安装或启动 Livox 驱动；不代表雷达连接成功。'
