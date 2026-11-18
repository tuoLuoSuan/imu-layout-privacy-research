"""Replay the registered-observation route used for the paper dorm example."""

import argparse
from pathlib import Path

from roomtrace.cli import digest, read, write

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", required=True, type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Choose a new output path.")

    import torch
    from analysis.layout.recovery076_eval import score
    from analysis.layout.recovery078_runtime import load_checkpoint, predict

    torch.set_num_threads(args.threads)
    lock = read(ROOT / "reproducibility/frozen088-lock.json")["D_checkpoint_sha256"]
    assets = ROOT / "output/layout-recon"
    checkpoint = assets / "recovery078/main400-k2all-7801/best.pt"
    teacher = assets / "recovery077/main400-calibration/calibrated.pt"
    for path, key in ((checkpoint, "k2"), (teacher, "teacher")):
        if digest(path) != lock[key]:
            raise ValueError(f"Checkpoint does not match the paper release: {path.name}")

    rules = {"walk_density_threshold": 1.5, "chair_contact_tol": 0.2, "solid_walk_scale": 4.0}
    observation = read(args.observation)
    result = predict(observation, *load_checkpoint(checkpoint, teacher), rules=rules)
    output = {
        "route": result["route"],
        "boxes": result["boxes"],
        "rules": rules,
        "registered_walk_samples": len(observation["walk"]),
        "contacts": len(observation["events"]),
        "observation_sha256": digest(args.observation),
    }
    if args.reference is not None:
        scores = score(result["boxes"], read(args.reference))
        errors = {match["truth"]: match["error_m"] for match in scores["matches"]}
        output["evaluation"] = {
            "complete_room": bool(scores["whole_room"]),
            "instance_f1": scores["f1"],
            "matched_center_errors_m": errors,
            "mean_matched_center_error_m": sum(errors.values()) / len(errors) if errors else None,
        }
    write(args.out, output)
    print(args.out)


if __name__ == "__main__":
    main()
