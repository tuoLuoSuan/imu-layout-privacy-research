#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
imu_env_root="${IMU_ENV_ROOT:-$HOME/imu-research}"
verify_dir="$imu_env_root/verification/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p -- "$verify_dir"

"$imu_env_root/.venv/bin/python" -m pip check | tee "$verify_dir/pip-check.log"
"$imu_env_root/.venv/bin/python" "$script_dir/smoke_test.py" > "$verify_dir/ml-report.json"
cat "$verify_dir/ml-report.json"

set +u
source /opt/ros/humble/setup.bash
set -u
ros2 --help > "$verify_dir/ros2-help.log"
ros2 bag --help > "$verify_dir/rosbag-help.log"
colcon --help > "$verify_dir/colcon-help.log"
ros2 pkg prefix rviz2
ldd /opt/ros/humble/lib/rviz2/rviz2 > "$verify_dir/rviz-ldd.log"
if grep -q 'not found' "$verify_dir/rviz-ldd.log"; then
  echo 'RViz 的动态库依赖不完整。' >&2
  exit 1
fi

# Only synthetic Hello World traffic on this machine; no physical devices.
export ROS_DOMAIN_ID=91
export ROS_LOCALHOST_ONLY=1
listener_pid=''
record_pid=''
cleanup() {
  if [[ -n "$listener_pid" ]]; then kill "$listener_pid" 2>/dev/null || true; fi
  if [[ -n "$record_pid" ]]; then kill "$record_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT

timeout --signal=INT --kill-after=3s 12s ros2 run demo_nodes_cpp listener > "$verify_dir/listener.log" 2>&1 &
listener_pid=$!
timeout --signal=INT --kill-after=3s 10s ros2 bag record /chatter -o "$verify_dir/rosbag-demo" > "$verify_dir/record.log" 2>&1 &
record_pid=$!
sleep 2
talker_status=0
timeout --signal=INT --kill-after=3s 6s ros2 run demo_nodes_cpp talker > "$verify_dir/talker.log" 2>&1 || talker_status=$?
if [[ "$talker_status" != 0 && "$talker_status" != 124 ]]; then
  cat "$verify_dir/talker.log" >&2
  exit "$talker_status"
fi
record_status=0
wait "$record_pid" || record_status=$?
record_pid=''
if [[ "$record_status" != 0 && "$record_status" != 124 ]]; then
  cat "$verify_dir/record.log" >&2
  exit "$record_status"
fi
listener_status=0
wait "$listener_pid" || listener_status=$?
listener_pid=''
if [[ "$listener_status" != 0 && "$listener_status" != 124 ]]; then
  cat "$verify_dir/listener.log" >&2
  exit "$listener_status"
fi
ros2 bag info "$verify_dir/rosbag-demo" > "$verify_dir/rosbag-info.log"

python3 - "$verify_dir" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path
import yaml

root = Path(sys.argv[1])
ml = json.loads((root / 'ml-report.json').read_text())
metadata = yaml.safe_load((root / 'rosbag-demo/metadata.yaml').read_text())
bag_count = metadata['rosbag2_bagfile_information']['message_count']
listener_count = (root / 'listener.log').read_text().count('I heard:')
assert ml['status'] == 'passed', ml
assert listener_count > 0, 'listener did not receive demo messages'
assert bag_count > 0, 'bag did not record demo messages'
report = {
    'kind': 'software_environment_acceptance_not_hardware_or_research_result',
    'status': 'passed',
    'checked_at': datetime.now().astimezone().isoformat(),
    'ml': ml,
    'pip_dependencies': 'passed',
    'ros_distro': 'humble',
    'ros_talker_listener_received_messages': listener_count,
    'rosbag_recorded_demo_messages': bag_count,
    'test_data': 'std_msgs/String Hello World demo',
    'ros_domain_id': 91,
    'ros_localhost_only': True,
    'rviz_binary_libraries': 'resolved',
    'rviz_gui_tested': False,
    'livox_hardware_tested': False,
    'har_training': False,
    'layout_training': False,
    'evidence_directory': str(root),
}
(root / 'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
PY
echo "验收目录：$verify_dir"
