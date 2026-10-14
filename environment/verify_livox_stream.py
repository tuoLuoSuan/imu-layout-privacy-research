"""Read-only ROS topic probe; reports reception, not calibration or map accuracy."""

import argparse
import csv
import json
import math
import statistics
import struct
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, PointCloud2


def interval_summary(arrivals):
    gaps = [(b - a) / 1e6 for a, b in zip(arrivals, arrivals[1:])]
    if not gaps:
        return {"intervals": 0}
    ordered = sorted(gaps)
    return {
        "intervals": len(gaps),
        "arrival_rate_hz": (len(arrivals) - 1) * 1e9 / (arrivals[-1] - arrivals[0]),
        "arrival_gap_median_ms": statistics.median(gaps),
        "arrival_gap_p95_ms_nearest_rank": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "arrival_gap_max_ms": max(gaps),
    }


class Probe(Node):
    def __init__(self):
        super().__init__("imu_research_livox_probe")
        self.cloud_arrivals = []
        self.imu_arrivals = []
        self.cloud_headers = []
        self.imu_headers = []
        self.point_counts = []
        self.points = []
        self.fields = []
        self.frames = set()
        self.imu_example = None
        self.subscriptions_owned = [
            self.create_subscription(PointCloud2, "/livox/lidar", self.cloud, qos_profile_sensor_data),
            self.create_subscription(Imu, "/livox/imu", self.imu, qos_profile_sensor_data),
        ]

    @staticmethod
    def header_ns(message):
        return message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec

    def cloud(self, message):
        self.cloud_arrivals.append(time.monotonic_ns())
        self.cloud_headers.append(self.header_ns(message))
        self.point_counts.append(message.width * message.height)
        self.frames.add(message.header.frame_id)
        if self.fields or not message.width:
            return
        self.fields = [
            {"name": field.name, "offset": field.offset, "datatype": field.datatype, "count": field.count}
            for field in message.fields
        ]
        fields = {field.name: field for field in message.fields}
        if any(name not in fields or fields[name].datatype != 7 for name in ("x", "y", "z")):
            return
        endian = ">" if message.is_bigendian else "<"
        count = message.width * message.height
        stride = max(1, math.ceil(count / 5000))
        for index in range(0, count, stride):
            row, column = divmod(index, message.width)
            base = row * message.row_step + column * message.point_step
            values = [struct.unpack_from(endian + "f", message.data, base + fields[name].offset)[0]
                      for name in ("x", "y", "z")]
            if all(math.isfinite(value) for value in values) and sum(value * value for value in values) > 1e-12:
                self.points.append(values)

    def imu(self, message):
        self.imu_arrivals.append(time.monotonic_ns())
        self.imu_headers.append(self.header_ns(message))
        if self.imu_example is None:
            self.imu_example = {
                "frame_id": message.header.frame_id,
                "linear_acceleration": [message.linear_acceleration.x, message.linear_acceleration.y,
                                        message.linear_acceleration.z],
                "angular_velocity": [message.angular_velocity.x, message.angular_velocity.y,
                                     message.angular_velocity.z],
            }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=15)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.duration <= 60:
        parser.error("Probe duration must be between 1 and 60 seconds")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = Probe()
    try:
        begin = time.monotonic()
        while time.monotonic() - begin < args.duration:
            rclpy.spin_once(node, timeout_sec=0.1)
        usable = len(node.cloud_arrivals) >= 10 and len(node.imu_arrivals) >= 10 and len(node.points) >= 100
        result = {
            "kind": "hardware_topic_reception_not_map_or_clock_calibration",
            "status": "passed" if usable else "incomplete",
            "requested_probe_duration_s": args.duration,
            "elapsed_probe_duration_s": time.monotonic() - begin,
            "cloud_messages": len(node.cloud_arrivals),
            "imu_messages": len(node.imu_arrivals),
            "cloud_frames": sorted(node.frames),
            "cloud_point_count_min": min(node.point_counts) if node.point_counts else None,
            "cloud_point_count_max": max(node.point_counts) if node.point_counts else None,
            "cloud_fields": node.fields,
            "cloud_callback_timing": interval_summary(node.cloud_arrivals),
            "imu_callback_timing": interval_summary(node.imu_arrivals),
            "cloud_header_first_ns": node.cloud_headers[0] if node.cloud_headers else None,
            "cloud_header_last_ns": node.cloud_headers[-1] if node.cloud_headers else None,
            "cloud_header_regressions": sum(b < a for a, b in zip(node.cloud_headers, node.cloud_headers[1:])),
            "imu_example": node.imu_example,
            "preview_points_from_first_cloud": len(node.points),
            "preview_sampling": "stride sample, finite nonzero XYZ, at most 5000 points from one received cloud",
            "clock_semantics_confirmed": False,
            "packet_loss_measured": False,
            "rviz_gui_tested": False,
            "map_reconstruction_tested": False,
        }
        (args.output_dir / "reception.json").write_text(json.dumps(result, indent=2) + "\n")
        with (args.output_dir / "first-cloud-preview.csv").open("w", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(["x_m", "y_m", "z_m"])
            writer.writerows(node.points)
        print(json.dumps(result, indent=2), flush=True)
        return 0 if usable else 2
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
