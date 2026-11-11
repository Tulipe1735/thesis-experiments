"""Read-only kinematic probes of the already observed tray collision."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import mujoco
import numpy as np

from experiments.t0_agent_v1.common import read, relative, sha, write_new


def probe(source):
    episode = source / "episode"
    model = mujoco.MjModel.from_binary_path(str(ROOT / read(episode / "model_reference.json")["path"]))
    data = mujoco.MjData(model)
    commands = read(source / "preposition.json")["steps"]
    last_clear_time = [row["reply"]["simulation_seconds"] for row in commands if row["stage"] == "clear"][-1]
    with np.load(episode / "trajectory.npz") as trace:
        index = int(np.argmin(abs(trace["time"] - last_clear_time)))
        start = trace["qpos"][index].copy()
        sampled_time = float(trace["time"][index])
    target = start.copy()
    for name, value in commands[-1]["targets_rad"].items():
        target[model.jnt_qposadr[model.joint(name).id]] = value
    tray = model.body("task_tray").id
    fingers = [g for g in range(model.ngeom)
               if (model.body(model.geom_bodyid[g]).name or "").startswith(("left_hand", "left_wrist"))
               and (model.geom_contype[g] or model.geom_conaffinity[g])]
    tray_geoms = [g for g in range(model.ngeom) if model.geom_bodyid[g] == tray]

    def clearance(qpos):
        data.qpos[:] = qpos
        mujoco.mj_forward(model, data)
        return min(mujoco.mj_geomDistance(model, data, first, second, 0.05, None)
                   for first in fingers for second in tray_geoms)

    def segment(a, b):
        return min(clearance(a + (b - a) * alpha) for alpha in np.linspace(0., 1., 41))

    rows = []
    for offset in (-0.2, -0.4, 0.2, 0.4):
        for part in ("shoulder_pitch", "elbow", "wrist_pitch"):
            joint = f"left_{part}_joint"
            via = target.copy()
            via[model.jnt_qposadr[model.joint(joint).id]] += offset
            rows.append({"joint": joint, "offset_rad": offset,
                         "minimum_sampled_clearance_m": min(segment(start, via), segment(via, target))})
    return {"source_run": relative(source), "last_clear_command_time_s": last_clear_time,
            "nearest_saved_time_s": sampled_time, "samples_per_segment": 41,
            "method": "mj_forward and mj_geomDistance; fixed source pelvis, fingers and tray; no physics stepping",
            "distance_cap_m": 0.05, "start_clearance_m": clearance(start),
            "unchanged_mean_endpoint_clearance_m": clearance(target),
            "direct_minimum_sampled_clearance_m": segment(start, target), "candidates": rows,
            "chosen": {"joint": "left_shoulder_pitch_joint", "offset_rad": -0.2,
                       "reason": "smallest tested shoulder offset clearing the known tray collision; must still pass dynamic gate"},
            "limits": "kinematic probe of left hand/wrist vs tray only; not a collision-free dynamics certificate",
            "input_sha256": {relative(path): sha(path) for path in (
                source / "preposition.json", episode / "trajectory.npz", episode / "model_reference.json")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=False, exist_ok=False)
    result = probe(args.source)
    write_new(args.output / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
