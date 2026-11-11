"""Read saved trajectories; separate engineering approach from VLA takeover."""

import argparse
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import mujoco
import numpy as np

from experiments.t0_agent_v1.common import read, relative, sha, write_new


def audit(run):
    takeover = read(run / "takeover.json")
    registration = read(run / "registration.json")
    result = read(run / "result.json")
    episode = run / "episode"
    ref = read(episode / "model_reference.json")
    model = mujoco.MjModel.from_binary_path(str(ROOT / ref["path"]))
    data = mujoco.MjData(model)
    cup, palm = model.body("task_cup").id, model.site("left_palm").id
    tray = model.body("task_tray").id
    with np.load(episode / "initial_state.npz") as state:
        mujoco.mj_setState(model, data, state["mujoco_integration_state"], mujoco.mjtState.mjSTATE_INTEGRATION)
    mujoco.mj_forward(model, data)
    tray_start = data.xpos[tray].copy()
    with np.load(episode / "takeover_state.npz") as state:
        mujoco.mj_setState(model, data, state["mujoco_integration_state"], mujoco.mjtState.mjSTATE_INTEGRATION)
    mujoco.mj_forward(model, data)
    tray_at_takeover = data.xpos[tray].copy()
    tray_rotation = data.xmat[tray].reshape(3, 3)
    exact_takeover_distance = float(np.linalg.norm(data.site_xpos[palm] - data.xpos[cup]))
    with np.load(episode / "trajectory.npz") as trajectory:
        indices = np.flatnonzero(trajectory["time"] >= takeover["simulation_seconds"] - 1e-8)
        distances, positions = [], []
        for index in indices:
            data.qpos[:] = trajectory["qpos"][index]
            mujoco.mj_forward(model, data)
            positions.append(data.xpos[cup].copy())
            distances.append(float(np.linalg.norm(data.site_xpos[palm] - data.xpos[cup])))
        times = trajectory["time"][indices]
    positions = np.asarray(positions)
    samples = read(episode / "verified_samples.json")
    prefix = [row for row in samples if row["time"] < takeover["simulation_seconds"]]
    policy = [row for row in samples if row["time"] >= takeover["simulation_seconds"]]
    events = read(episode / "physics_events.json")
    paths = [run / "registration.json", run / "result.json", run / "takeover.json",
             episode / "trajectory.npz", episode / "takeover_state.npz",
             episode / "independent_verification.json", episode / "verified_samples.json",
             episode / "physics_events.json"]
    return {"run": relative(run), "arm": result["arm"],
            "input_sha256": {relative(path): sha(path) for path in paths},
            "takeover_state_sha256": takeover["state_sha256"],
            "phase_seconds": float(times[-1] - takeover["simulation_seconds"]),
            "first_saved_phase_time_s": float(times[0]),
            "exact_takeover_palm_to_cup_m": exact_takeover_distance,
            "initial_palm_to_cup_m": distances[0], "final_palm_to_cup_m": distances[-1],
            "min_palm_to_cup_m": min(distances),
            "max_cup_displacement_m": float(np.linalg.norm(positions - positions[0], axis=1).max()),
            "verified_success": result["verified_success"], "guard": result["runtime"]["protection"],
            "error": result["error"], "right_targets_unchanged": result["right_targets_unchanged"],
            "vla_inference_calls": result["vla_inference_calls"],
            "vla_applied_frames": result["vla_applied_frames"],
            "weights_unchanged": result["weights_unchanged"],
            "engineering_prefix_effect": {
                "tray_initial_xyz_m": tray_start.tolist(), "tray_takeover_xyz_m": tray_at_takeover.tolist(),
                "tray_planar_displacement_m": float(np.linalg.norm((tray_at_takeover - tray_start)[:2])),
                "tray_takeover_yaw_rad": math.atan2(tray_rotation[1, 0], tray_rotation[0, 0]),
                "max_sampled_tray_hand_contact_N": max(row["tray_hand_contact_N"] for row in prefix)},
            "max_sampled_policy_cup_hand_contact_N": max(row["cups"]["task_cup"]["hand_contact_N"] for row in policy),
            "inference_physics_wait_seconds": sum(row["advanced_seconds"] for row in events
                                                   if row["category"] == "vla_inference_wait"),
            "source_hashes_match_current": all(sha(ROOT / path) == expected for path, expected
                                               in registration["source_sha256"].items())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=False, exist_ok=False)
    rows = [audit(path) for path in args.runs]
    report = {"date": "2026-11-06", "boundary": "simulation", "kind": "read_only_trajectory_audit",
              "seed_range": [310300, 310300], "outcome_filter": False,
              "split": "consumed_generator_development", "training": False,
              "method": "mj_forward on every saved qpos at or after takeover; no physics stepping; distance to cup body origin",
              "audit_source_sha256": sha(Path(__file__)),
              "identical_takeover_state": len({row["takeover_state_sha256"] for row in rows}) == 1,
              "rows": rows}
    write_new(args.output / "result.json", report)
    import json
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
