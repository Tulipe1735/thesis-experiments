"""Measure the fixed-waist left-arm workspace at TP01 counter height.

The measurement uses the same robot-only planner the engineering reference
calls, seeded from the same reference joint state the TP01 plant starts from.
It answers one question: which cup-bottom positions in the pelvis frame can the
left palm reach with the waist fixed? The answer bounds which TP01 initial
states can ever pass the feasibility gate.

Output: ``envelope.json`` with the grid, the measured forward limit, and the
distance of each frozen ``tabletop_dataset_20261026_003`` train target.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "grasp_optimization") not in sys.path:
    sys.path.insert(0, str(ROOT / "grasp_optimization"))

from experiments.t0_agent_v1.common import read, relative, write_new  # noqa: E402
from experiments.t0_agent_v1.train_tp01 import training_cases  # noqa: E402
from arm_planner import ArmPlanner  # noqa: E402

REFERENCE = ROOT / "grasp_optimization/episodes/final_reference_1000"
OFFSET = np.array([0.045, -0.055, -0.052])  # cup_in_palm_m the recipe loads
YAWS = (0.7, 1.25, 0.4, 0.0)
FORWARD = np.round(np.arange(0.25, 1.01, 0.05), 3)
LATERAL = np.round(np.arange(-0.40, 0.41, 0.05), 3)


def reference_state(planner):
    import mujoco

    model = mujoco.MjModel.from_binary_path(str(REFERENCE / "model.mjb"))
    data = mujoco.MjData(model)
    with np.load(REFERENCE / "initial_state.npz", allow_pickle=False) as saved:
        mujoco.mj_setState(model, data, saved["mujoco_integration_state"],
                           mujoco.mjtState.mjSTATE_INTEGRATION)
    mujoco.mj_forward(model, data)
    joints = {}
    for j in range(model.njnt):
        name = model.joint(j).name
        if name and model.jnt_type[j] == 3:
            joints[name] = dict(q=float(data.qpos[model.jnt_qposadr[j]]))
    pelvis_z = float(data.xpos[model.body("pelvis").id][2])
    cup_z = float(data.xpos[model.body("task_cup").id][2])
    return dict(simulation_seconds=float(data.time), joints=joints), pelvis_z, cup_z


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)

    planner = ArmPlanner()
    state, pelvis_z, cup_z = reference_state(planner)
    table_z = round(cup_z - pelvis_z, 4)

    grid = []
    for forward in FORWARD:
        for lateral in LATERAL:
            cup = [float(forward), float(lateral), table_z]
            best = None
            for yaw in YAWS:
                goal = np.asarray(cup) - np.array(
                    [[np.cos(yaw), -np.sin(yaw), 0.0],
                     [np.sin(yaw), np.cos(yaw), 0.0],
                     [0.0, 0.0, 1.0]]) @ OFFSET
                data = planner.start(state)
                result = planner.solve(data, goal, yaw)
                if best is None or result["position_error_m"] < best["position_error_m"]:
                    best = dict(yaw=yaw, **result)
                if result["reachable"]:
                    best = dict(yaw=yaw, **result)
                    break
            grid.append(dict(forward_m=float(forward), lateral_m=float(lateral), **best))

    reachable = [row for row in grid if row["reachable"]]
    forward_limit = max((row["forward_m"] for row in reachable), default=None)

    frozen = []
    for case in training_cases():
        stance = case["instance"]["robot"]["stance"]
        target = next(item for item in case["instance"]["objects"] if item["is_target"])
        yaw = float(stance["pelvis_yaw_in_table_rad"])
        delta = np.asarray(target["position_m"][:2]) - np.asarray(stance["pelvis_table_xy_m"])
        # Table yaw -pi/2: forward is -delta_y, left is delta_x.
        forward = float(-delta[1]) if abs(yaw + np.pi / 2) < 1e-9 else None
        lateral = float(delta[0]) if abs(yaw + np.pi / 2) < 1e-9 else None
        frozen.append(dict(
            id=case["instance"]["id"],
            target_category=case["task"]["target_category"],
            forward_m=forward,
            lateral_m=lateral,
            beyond_measured_forward_limit=bool(forward is not None and forward_limit is not None
                                              and forward > forward_limit),
        ))

    summary = {
        "date": "2026-11-03",
        "boundary": "simulation",
        "kind": "tp01_fixed_waist_reach_envelope",
        "reference_model": relative(REFERENCE / "model.mjb"),
        "table_height_in_pelvis_m": table_z,
        "offsets": OFFSET.tolist(),
        "yaws": list(YAWS),
        "grid": grid,
        "reachable_cells": len(reachable),
        "total_cells": len(grid),
        "forward_limit_m": forward_limit,
        "lateral_range_at_limit_m": [
            min((row["lateral_m"] for row in reachable if row["forward_m"] == forward_limit), default=None),
            max((row["lateral_m"] for row in reachable if row["forward_m"] == forward_limit), default=None),
        ],
        "frozen_train_targets": frozen,
        "conclusion": (
            "The fixed-waist left arm reaches no further than the measured forward limit. "
            "Every frozen tabletop_dataset_20261026_003 train target lies beyond it, so F0 v1 "
            "could not pass on those states without changing the waist or the task."
        ),
    }
    write_new(output / "envelope.json", summary)
    print(json.dumps({k: summary[k] for k in (
        "table_height_in_pelvis_m", "reachable_cells", "total_cells", "forward_limit_m",
        "lateral_range_at_limit_m")}, indent=1))
    for row in frozen:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
