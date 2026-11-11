"""Fail on tray disturbance in saved engineering prepositioning evidence."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import mujoco
import numpy as np

from experiments.t0_agent_v1.common import read, relative, sha, write_new

CONTACT_LIMIT_N = 0.10
TRANSLATION_LIMIT_M = 0.001
YAW_LIMIT_RAD = np.deg2rad(0.5)


def check(run):
    episode = run / "episode"
    ref = read(episode / "model_reference.json")
    model = mujoco.MjModel.from_binary_path(str(ROOT / ref["path"]))
    data = mujoco.MjData(model)
    tray = model.body("task_tray").id
    poses = []
    end_name = "takeover_state" if (episode / "takeover_state.npz").exists() else "final_state"
    for name in ("initial_state", end_name):
        with np.load(episode / f"{name}.npz") as state:
            mujoco.mj_setState(model, data, state["mujoco_integration_state"], mujoco.mjtState.mjSTATE_INTEGRATION)
        mujoco.mj_forward(model, data)
        rotation = data.xmat[tray].reshape(3, 3)
        poses.append((data.xpos[tray].copy(), np.arctan2(rotation[1, 0], rotation[0, 0])))
    prepose = read(run / "preposition.json")
    if "simulation_seconds" in prepose:
        end = prepose["simulation_seconds"]
    else:
        end = read(run / "result.json")["runtime"]["simulation_seconds"]
    samples = [row for row in read(episode / "verified_samples.json") if row["time"] <= end + 1e-8]
    peak = max(samples, key=lambda row: row["tray_hand_contact_N"])
    translation = float(np.linalg.norm((poses[1][0] - poses[0][0])[:2]))
    yaw = float(abs(np.arctan2(np.sin(poses[1][1] - poses[0][1]), np.cos(poses[1][1] - poses[0][1]))))
    passed = prepose["ready"] and peak["tray_hand_contact_N"] <= CONTACT_LIMIT_N and translation <= TRANSLATION_LIMIT_M and yaw <= YAW_LIMIT_RAD
    return {"run": relative(run), "passed": bool(passed), "prepose_ready": prepose["ready"],
            "max_sampled_tray_hand_contact_N": peak["tray_hand_contact_N"], "peak_time_s": peak["time"],
            "tray_planar_displacement_m": translation, "tray_yaw_change_rad": yaw,
            "thresholds": {"contact_N": CONTACT_LIMIT_N, "translation_m": TRANSLATION_LIMIT_M,
                           "yaw_rad": float(YAW_LIMIT_RAD)},
            "method": "saved evaluator samples for prefix hand-contact; initial and prefix-end integration state for tray pose",
            "input_sha256": {relative(path): sha(path) for path in (
                episode / "initial_state.npz", episode / f"{end_name}.npz", episode / "verified_samples.json", run / "preposition.json")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=False, exist_ok=False)
    result = check(args.run)
    write_new(args.output / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
