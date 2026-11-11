"""Generated reach-and-hold tasks that are feasible by construction.

Each task samples a left-arm joint configuration near the saved initial, takes
its palm pose (pelvis frame) as the public target, and keeps the sampled
configuration private as the per-task positive control. A sample is rejected
when the left hand or arm touches anything along the straight joint path.
The sampled numbers, not only the seed, are written into every task.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import mujoco
import numpy as np

from .tp01 import ROOT

SOURCE = ROOT / "experiments/t0_agent_v1/tray_astra_20261025_002/episodes/2500_T01_astra"
ARM_JOINTS = ("left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint",
              "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint",
              "left_wrist_yaw_joint")
PATH_CHECKS = 12
# The family contract every artifact authored for these tasks declares (artifact.v2).
FAMILY = {
    "task_family": "reach_hold_fk_v1", "task_node": "B2.1",
    "contract": {
        "pre": ["hand_empty", "hand_open", "guard_clear"],
        "post": ["palm_at_pose"],
        "params": {
            "position_m": {"type": "vec3", "description": "目标掌位，当前骨盆系，米"},
            "quaternion_xyzw": {"type": "quat_xyzw", "description": "目标掌姿，当前骨盆系"},
            "hold_s": {"type": "float", "description": "到位后需保持的秒数"},
        },
        "failure_codes": ["NOT_REACHED", "ORIENTATION", "NOT_HELD", "BUDGET", "UNSAFE"],
    },
}
CONTRACT_DEFAULTS = {
    "effect": "empty_hand_reach_hold", "frame": "current_pelvis",
    "position_tolerance_m": .008, "orientation_tolerance_rad": .15, "hold_s": 1.,
    "contact_max_N": .1, "hand_open_min": .95, "object_displacement_max_m": .005,
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_static(source: Path = SOURCE):
    """Saved model and initial state, forward kinematics only, no physics step."""
    reference = __import__("json").loads((source / "model_reference.json").read_text())
    model = mujoco.MjModel.from_binary_path(str(ROOT / reference["path"]))
    data = mujoco.MjData(model)
    with np.load(source / "initial_state.npz", allow_pickle=False) as saved:
        mujoco.mj_setState(model, data, saved["mujoco_integration_state"],
                           mujoco.mjtState.mjSTATE_INTEGRATION)
    mujoco.mj_forward(model, data)
    return model, data, reference


def _arm_bodies(model):
    """Every body from the left shoulder down, hand included."""
    root = model.body("left_shoulder_pitch_link").id
    bodies = set()
    for body in range(model.nbody):
        ancestor = body
        while ancestor > 0 and ancestor != root:
            ancestor = int(model.body_parentid[ancestor])
        if ancestor == root:
            bodies.add(body)
    return bodies


def palm_pose(model, data):
    pelvis, site = model.body("pelvis").id, model.site("left_palm").id
    rotation = data.xmat[pelvis].reshape(3, 3)
    position = rotation.T @ (data.site_xpos[site] - data.xpos[pelvis])
    quat = np.empty(4)
    mujoco.mju_mat2Quat(quat, (rotation.T @ data.site_xmat[site].reshape(3, 3)).ravel())
    return position, quat[[1, 2, 3, 0]]


def _arm_contacts(model, data, arm):
    count = 0
    for i in range(data.ncon):
        contact = data.contact[i]
        if any(int(model.geom_bodyid[g]) in arm for g in (contact.geom1, contact.geom2)):
            count += 1
    return count


def generate(seed: int, count: int, radius_rad: float, *, source: Path = SOURCE,
             max_draws: int = 2000, min_palm_travel_m: float = .03) -> dict:
    """Draw ``count`` collision-free reach tasks; every draw is counted."""
    model, data, reference = load_static(source)
    arm = _arm_bodies(model)
    adr = {name: int(model.jnt_qposadr[model.joint(name).id]) for name in ARM_JOINTS}
    ranges = {name: model.jnt_range[model.joint(name).id].tolist() for name in ARM_JOINTS}
    initial_q = {name: float(data.qpos[adr[name]]) for name in ARM_JOINTS}
    if _arm_contacts(model, data, arm):
        raise ValueError("saved initial already has left-arm contact")
    initial_pos, _ = palm_pose(model, data)
    base = data.qpos.copy()
    rng = np.random.default_rng(seed)
    tasks, rejected = [], {"joint_range": 0, "path_contact": 0, "short_travel": 0}
    draws = 0
    while len(tasks) < count:
        if draws >= max_draws:
            raise ValueError(f"only {len(tasks)} of {count} tasks after {draws} draws")
        draws += 1
        delta = rng.uniform(-radius_rad, radius_rad, len(ARM_JOINTS))
        goal = {name: initial_q[name] + float(d) for name, d in zip(ARM_JOINTS, delta)}
        if any(not ranges[n][0] + .02 <= goal[n] <= ranges[n][1] - .02 for n in ARM_JOINTS):
            rejected["joint_range"] += 1
            continue
        clear = True
        for k in range(1, PATH_CHECKS + 1):
            data.qpos[:] = base
            for name in ARM_JOINTS:
                data.qpos[adr[name]] = initial_q[name] + (goal[name] - initial_q[name]) * k / PATH_CHECKS
            mujoco.mj_forward(model, data)
            if _arm_contacts(model, data, arm):
                clear = False
                break
        if not clear:
            rejected["path_contact"] += 1
            continue
        position, quat = palm_pose(model, data)
        if np.linalg.norm(position - initial_pos) < min_palm_travel_m:
            rejected["short_travel"] += 1
            continue
        index = len(tasks)
        tasks.append({
            "task_id": f"reach_{seed}_{index:03d}",
            "public": {**CONTRACT_DEFAULTS, "position_m": position.round(6).tolist(),
                       "quaternion_xyzw": quat.round(6).tolist()},
            "private": {"sampled_arm_q": goal, "joint_delta_rad": dict(zip(ARM_JOINTS, delta.round(6).tolist())),
                        "palm_travel_m": float(np.linalg.norm(position - initial_pos)),
                        "draw_index": draws - 1},
        })
    data.qpos[:] = base
    mujoco.mj_forward(model, data)
    return {"generator": FAMILY["task_family"], "family": FAMILY, "seed": seed, "count": count,
            "radius_rad": radius_rad, "min_palm_travel_m": min_palm_travel_m,
            "path_checks": PATH_CHECKS, "draws": draws, "rejected": rejected,
            "source_initial": {"path": str((source / "initial_state.npz").relative_to(ROOT)),
                               "sha256": _sha(source / "initial_state.npz")},
            "plant": {"path": reference["path"], "sha256": _sha(ROOT / reference["path"])},
            "initial_arm_q": initial_q, "initial_palm_position_m": initial_pos.tolist(),
            "tasks": tasks}
