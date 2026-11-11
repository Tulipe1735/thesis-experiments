"""Post-hoc, read-only check of response survival through target limiting.

Replay only range/slew projection of the first 15 native action targets, with
right policy outputs masked. No controller, tracking protection, mj_step or
task execution is simulated. FK at the last command is a geometric proxy only.
"""

import argparse
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]

import mujoco
import numpy as np

from experiments.t0_agent_v1.common import read, relative, sha, write_new
from t01_vla_response import NOISE_SEEDS, rmse


def audit(source, output):
    output.mkdir(parents=False, exist_ok=False)
    registration = read(source / "registration.json")
    result = read(source / "result.json")
    observations = read(source / "observations.json")
    initial = ROOT / registration["source"]
    names = read(initial / "vla/policy_runtime.json")["joint_names"]
    ref = read(initial / "episode/model_reference.json")
    model = mujoco.MjModel.from_binary_path(str(ROOT / ref["path"]))
    data = mujoco.MjData(model)
    with np.load(initial / "episode/takeover_state.npz") as state:
        mujoco.mj_setState(model, data, state["mujoco_integration_state"], mujoco.mjtState.mjSTATE_INTEGRATION)
        targets = state["targets"].copy()
    mujoco.mj_forward(model, data)
    initial_q = data.qpos.copy()
    actuator_names = [model.joint(joint).name for joint in model.actuator_trnid[:, 0]]
    indices = np.array([actuator_names.index(name) for name in names])
    joint_ids = model.actuator_trnid[indices, 0]
    qids = model.jnt_qposadr[joint_ids]
    bounds = model.jnt_range[joint_ids]
    profile = read(ROOT / "grasp_optimization/assets/robot_profile.json")["profile"]
    joint_rows = {row[0]: row for row in profile["joints"]}
    caps = np.array([min(joint_rows[name][5], 1.0 if "_hand_" in name else 0.75) for name in names]) / 30.
    left_arm = [i for i, name in enumerate(names) if name.startswith("left_") and "_hand_" not in name]
    right = np.array([name.startswith("right_") for name in names])
    palm_id = model.site("left_palm").id
    initial_palm = data.site_xpos[palm_id].copy()
    commands, rows = {}, []
    for record in result["rows"]:
        native = np.load(ROOT / record["action_file"], allow_pickle=False)[0, :15]
        previous = targets[indices].copy()
        command = []
        for frame in native:
            bounded = np.clip(frame, bounds[:, 0], bounds[:, 1])
            bounded[right] = previous[right]
            previous = previous + np.clip(bounded - previous, -caps, caps)
            command.append(previous.copy())
        command = np.asarray(command)
        commands[record["index"]] = command
        data.qpos[:] = initial_q
        data.qpos[qids] = command[-1]
        mujoco.mj_forward(model, data)
        rows.append({key: record[key] for key in ("index", "seed", "position", "instruction", "kind")}
                    | {"command_endpoint_palm_world_m": data.site_xpos[palm_id].tolist(),
                       "endpoint_palm_shift_from_initial_m": (data.site_xpos[palm_id] - initial_palm).tolist(),
                       "left_arm_command_motion_rmse_rad": rmse(command[:, left_arm], np.broadcast_to(targets[indices][left_arm], (15, 7)))})
    baselines = {row["seed"]: row for row in rows if row["kind"] == "factorial" and row["position"] == "asset_310300" and row["instruction"] == "transfer"}
    effects = []
    for row in rows:
        base = baselines[row["seed"]]
        if row["kind"] == "repeat" or row["index"] == base["index"]:
            continue
        if row["position"] != "asset_310300" and row["instruction"] != "transfer":
            continue
        delta_palm = np.array(row["command_endpoint_palm_world_m"]) - np.array(base["command_endpoint_palm_world_m"])
        effect = {**row,
                  "left_arm_command_delta_rmse_rad": rmse(commands[row["index"]][:, left_arm], commands[base["index"]][:, left_arm]),
                  "endpoint_palm_delta_from_baseline_m": delta_palm.tolist()}
        if row["position"] not in ("asset_310300", "blank"):
            delta_cup = np.array(observations[row["position"]]["cup_world_xyz_m"]) - np.array(observations["asset_310300"]["cup_world_xyz_m"])
            effect["cup_translation_from_baseline_m"] = delta_cup.tolist()
            effect["palm_response_projection_along_cup_translation_m"] = float(delta_palm @ delta_cup / np.linalg.norm(delta_cup))
        effects.append(effect)
    noise = [{"seeds": [a, b], "command_rmse_rad": rmse(commands[baselines[a]["index"]][:, left_arm], commands[baselines[b]["index"]][:, left_arm])}
             for a, b in itertools.combinations(NOISE_SEEDS, 2)]
    findings = {"date": "2026-11-06", "kind": "posthoc_target_limiter_and_FK_diagnostic",
                "training": False, "physics_steps": 0, "motor_execution": False, "outcome_filter": False,
                "source": relative(source), "seed_segments": registration["generator_seed_segments"],
                "method": "first 15 targets, 30 Hz range/slew projection, right outputs held; FK of final command at frozen root",
                "limits": "no dynamics, torque, collision, tracking exit, latency or replan; positive directional projection is not task success",
                "input_sha256": {relative(path): sha(path) for path in (
                    source / "registration.json", source / "result.json", source / "observations.json",
                    initial / "episode/takeover_state.npz", ROOT / ref["path"], Path(__file__))},
                "rows": rows, "one_factor_effects": effects, "different_rng_command_rmse": noise}
    write_new(output / "result.json", findings)
    print(json.dumps({"source": findings["source"], "conditions_audited": len(rows), "physics_steps": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.source.resolve(), args.output.resolve())
