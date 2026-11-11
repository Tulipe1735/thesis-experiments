"""Independent trajectory replay for explicit-pose, empty-hand local effects.

No policy imports this evaluator. The target is a public task input; object
truth is used only here to reject contact or displacement during the reach.
"""

import json
from pathlib import Path

import mujoco
import numpy as np

from .tp01 import HAND_JOINTS, CLOSED_ANGLES, ROOT


def hold_timing(rows, hold_s, max_gap_s=.051):
    """A missing sample breaks the held-pose window, not earlier travel."""
    since = first = previous = None
    for row in rows:
        gap = previous is not None and row["time"] - previous > max_gap_s
        if row["at_pose"]:
            if since is None or gap:
                since = row["time"]
            if first is None and row["time"] - since >= hold_s - 1e-8:
                first = row["time"]
        else:
            since = None
        previous = row["time"]
    terminal = 0. if since is None or not rows else rows[-1]["time"] - since
    return first, terminal


def evaluate(episode: Path, contract: dict, *, start_s=0.0, end_s=None,
             execution_error=None) -> dict:
    reference = json.loads((episode / "model_reference.json").read_text())
    model = mujoco.MjModel.from_binary_path(str(ROOT / reference["path"]))
    data = mujoco.MjData(model)
    pelvis, palm, cup = (model.body("pelvis").id, model.site("left_palm").id,
                         model.body("task_cup").id)
    # The saved pantry model uses stateless affine position servos. Recover
    # their input from f = gain * ctrl + bias(length, velocity); never mistake
    # actuator_force for the servo position command.
    if not (np.all(model.actuator_gaintype == mujoco.mjtGain.mjGAIN_FIXED)
            and np.all(model.actuator_gainprm[:, 0] > 0.)
            and np.all(model.actuator_biastype == mujoco.mjtBias.mjBIAS_AFFINE)
            and np.all(model.actuator_dyntype == mujoco.mjtDyn.mjDYN_NONE)
            and not np.any(model.actuator_ctrllimited)):
        raise ValueError("local contact replay requires the saved stateless affine servo model")
    wrist = model.body("left_wrist_yaw_link").id
    hand_bodies = set()
    for body in range(model.nbody):
        ancestor = body
        while ancestor > 0 and ancestor != wrist:
            ancestor = int(model.body_parentid[ancestor])
        if ancestor == wrist:
            hand_bodies.add(body)
    rows = []
    with np.load(episode / "initial_state.npz", allow_pickle=False) as saved:
        mujoco.mj_setState(model, data, saved["mujoco_integration_state"],
                          mujoco.mjtState.mjSTATE_INTEGRATION)
        mujoco.mj_forward(model, data)
        initial_cup = data.xpos[cup].copy()
    with np.load(episode / "trajectory.npz", allow_pickle=False) as trace:
        for t, q, v, force in zip(trace["time"], trace["qpos"], trace["qvel"], trace["actuator_force"]):
            if t < start_s - 1e-8 or (end_s is not None and t > end_s + 1e-8):
                continue
            data.qpos[:], data.qvel[:] = q, v
            mujoco.mj_fwdPosition(model, data)
            mujoco.mj_fwdVelocity(model, data)
            bias = (model.actuator_biasprm[:, 0] + model.actuator_biasprm[:, 1] * data.actuator_length
                    + model.actuator_biasprm[:, 2] * data.actuator_velocity)
            data.ctrl[:] = (force - bias) / model.actuator_gainprm[:, 0]
            mujoco.mj_forward(model, data)
            if not np.allclose(data.actuator_force, force, rtol=1e-8, atol=1e-8):
                raise ValueError("recorded actuator forces were not reconstructed")
            rotation = data.xmat[pelvis].reshape(3, 3)
            pos = rotation.T @ (data.site_xpos[palm] - data.xpos[pelvis])
            quat = np.empty(4)
            mujoco.mju_mat2Quat(quat, (rotation.T @ data.site_xmat[palm].reshape(3, 3)).ravel())
            wanted = np.array(contract["quaternion_xyzw"])[[3, 0, 1, 2]]
            angle = 2 * np.arccos(np.clip(abs(np.dot(quat, wanted)), 0, 1))
            contact = 0.0
            for i in range(data.ncon):
                c = data.contact[i]
                bodies = [int(model.geom_bodyid[g]) for g in (c.geom1, c.geom2)]
                # All left hand contact is excluded, including contact with a table.
                if any(b in hand_bodies for b in bodies):
                    force = np.empty(6)
                    mujoco.mj_contactForce(model, data, i, force)
                    contact += max(0., float(force[0]))
            fractions = []
            for name, closed in zip(HAND_JOINTS, CLOSED_ANGLES):
                if closed:
                    qvalue = data.qpos[model.jnt_qposadr[model.joint(name).id]]
                    fractions.append(1 - np.clip(qvalue / closed, 0, 1))
            error = float(np.linalg.norm(pos - contract["position_m"]))
            displacement = float(np.linalg.norm(data.xpos[cup] - initial_cup))
            safe = (contact < contract["contact_max_N"]
                    and min(fractions) >= contract["hand_open_min"]
                    and displacement <= contract["object_displacement_max_m"])
            rows.append({"time": float(t), "position_m": pos.tolist(),
                         "position_error_m": error, "orientation_error_rad": float(angle),
                         "contact_N": contact, "hand_open_fraction": float(min(fractions)),
                         "object_displacement_m": displacement, "safe": bool(safe),
                         "at_pose": bool(safe and error <= contract["position_tolerance_m"]
                                         and angle <= contract["orientation_tolerance_rad"])})
    first, terminal_hold = hold_timing(rows, contract["hold_s"])
    environment = json.loads((episode / "environment_result.json").read_text())
    success = bool(rows and terminal_hold >= contract["hold_s"] - 1e-8
                   and all(r["safe"] for r in rows) and not execution_error
                   and not environment["protection"])
    return {"verified_local_success": success, "first_stable_s": first,
            "terminal_hold_s": terminal_hold, "all_frames_safe": all(r["safe"] for r in rows),
            "final_position_error_m": rows[-1]["position_error_m"] if rows else None,
            "final_orientation_error_rad": rows[-1]["orientation_error_rad"] if rows else None,
            "execution_error": execution_error, "guard": environment["protection"],
            "evaluator_version": "explicit-pose-replay-v2", "sample_gap_max_s": .051,
            "contact_replay": "all wrist-yaw descendants; inverted affine servo input and checked actuator_force reconstruction",
            "rows": rows, "start_s": start_s, "end_s": end_s,
            "full_task_success": "separately_evaluated_by_official_tray_verifier"}
