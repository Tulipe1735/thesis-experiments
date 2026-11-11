"""Frozen-weight deployment diagnostic on a consumed generator development case.

Keep engineering prepositioning and subsequent policy action evidence separate.
The target posture must be reached before a wait or VLA arm can start.
"""

import argparse
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]

import numpy as np

from experiments.t0_agent_v1.common import read, relative, sha, write_new
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot
from experiments.t0_agent_v1.tray_verify import verify
from experiments.grow_up_harness_v2.vla_runtime import SmolVLAClient
from t01_vla_policy import SUITE, INSTRUCTION, joint_targets, proximity_metrics
from check_vla_prepose_clearance import CONTACT_LIMIT_N, TRANSLATION_LIMIT_M, YAW_LIMIT_RAD

METADATA = ROOT / "grasp_optimization/assets/vla_checkpoint_metadata/kiteml_g1_smolvla"
WEIGHTS = Path.home() / "vla-work/models/g1-smolvla/model.safetensors"
CLEAR_POINTS = ((-0.07, 0.34, 0.09), (-0.04, 0.34, 0.30))
JOINT_TOLERANCE = 0.10


class ClearanceRobot(PilotRobot):
    """Private deployment gate; contact truth is never an input to the VLA."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tray_id = self.model.body("task_tray").id
        self.tray_initial_xy = self.data.xpos[self.tray_id, :2].copy()
        matrix = self.data.xmat[self.tray_id].reshape(3, 3)
        self.tray_initial_yaw = math.atan2(matrix[1, 0], matrix[0, 0])
        self.monitor_prepose = True
        self.max_tray_contact = self.max_tray_translation = self.max_tray_yaw = 0.0
        self.peak_contact_time = None

    def _step(self):
        super()._step()
        if not self.monitor_prepose:
            return
        from experiments.t0_agent_v1.runtime import mujoco
        load = 0.0
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            bodies = self.model.geom_bodyid[[contact.geom1, contact.geom2]]
            if self.tray_id not in bodies:
                continue
            other = int(bodies[1] if bodies[0] == self.tray_id else bodies[0])
            if (self.model.body(other).name or "").startswith(("left_", "right_")):
                force = np.zeros(6)
                mujoco.mj_contactForce(self.model, self.data, index, force)
                load += max(float(force[0]), 0.0)
        if load > self.max_tray_contact:
            self.max_tray_contact = load
            self.peak_contact_time = float(self.data.time)
        self.max_tray_translation = max(self.max_tray_translation, float(
            np.linalg.norm(self.data.xpos[self.tray_id, :2] - self.tray_initial_xy)))
        rotation = self.data.xmat[self.tray_id].reshape(3, 3)
        delta = math.atan2(rotation[1, 0], rotation[0, 0]) - self.tray_initial_yaw
        self.max_tray_yaw = max(self.max_tray_yaw, abs(math.atan2(math.sin(delta), math.cos(delta))))
        if not self.guard and load > CONTACT_LIMIT_N:
            self.guard = "PREPOSE_TRAY_CONTACT"
        if not self.guard and (self.max_tray_translation > TRANSLATION_LIMIT_M or self.max_tray_yaw > YAW_LIMIT_RAD):
            self.guard = "PREPOSE_TRAY_MOVEMENT"

    def clearance_report(self):
        return {"sample_interval_s": float(self.model.opt.timestep),
                "max_robot_tray_contact_N": self.max_tray_contact,
                "peak_contact_time_s": self.peak_contact_time,
                "max_tray_planar_displacement_m": self.max_tray_translation,
                "max_tray_yaw_change_rad": self.max_tray_yaw,
                "passed": bool(self.max_tray_contact <= CONTACT_LIMIT_N
                and self.max_tray_translation <= TRANSLATION_LIMIT_M and self.max_tray_yaw <= YAW_LIMIT_RAD)}


def posture_targets(robot):
    # Contract order: left arm seven, right arm seven, then the two hands.
    names = [f"left_{part}_joint" for part in (
        "shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
        "wrist_roll", "wrist_pitch", "wrist_yaw")]
    means = read(METADATA / "normalization_decoded.json")["action.mean"]["values"]
    return dict(zip(names, means[:7]))


def preposition(robot, port, folder, path_variant="direct"):
    log = []
    for leg, point in enumerate(CLEAR_POINTS):
        start = robot.fk("left")["position_m"]
        steps = max(1, math.ceil(math.dist(start, point) / 0.035))
        for step in range(1, steps + 1):
            target = [start[i] + (point[i] - start[i]) * step / steps for i in range(3)]
            reply = port.invoke("move_ee", {
                "side": "left", "position": target,
                "quaternion_xyzw": None if leg == 0 else [0., 0., 0., 1.],
                "duration": 2.0,
            })
            log.append({"stage": "clear", "leg": leg, "target_m": target, "reply": reply})
            if reply.get("status") != "EXECUTED" or robot.guard:
                result = {"ready": False, "reason": "CLEAR_PATH_REJECTED", "steps": log}
                write_new(folder / "preposition.json", result)
                return result
    targets = posture_targets(robot)
    if path_variant == "overhead":
        overhead = {**targets, "left_shoulder_pitch_joint": targets["left_shoulder_pitch_joint"] - 0.20}
        reply = port.invoke("set_joints", {"targets": overhead, "duration": 4.0})
        log.append({"stage": "overhead_mean", "targets_rad": overhead, "reply": reply})
        if reply.get("status") != "EXECUTED" or robot.guard:
            result = {"ready": False, "reason": "OVERHEAD_POSTURE_NOT_REACHED", "steps": log}
            write_new(folder / "preposition.json", result)
            return result
    duration = 2.0 if path_variant == "overhead" else 4.0
    reply = port.invoke("set_joints", {"targets": targets, "duration": duration})
    log.append({"stage": "mean_posture", "targets_rad": targets, "reply": reply})
    if reply.get("status") == "EXECUTED" and not robot.guard:
        port.invoke("wait", {"seconds": 0.5})
    state = port.state()
    error = max(abs(state["joints"][name]["q"] - value) for name, value in targets.items())
    ready = reply.get("status") == "EXECUTED" and not robot.guard and error <= JOINT_TOLERANCE
    result = {"ready": bool(ready), "reason": "READY" if ready else "MEAN_POSTURE_NOT_REACHED",
              "max_joint_error_rad": error, "tolerance_rad": JOINT_TOLERANCE,
              "simulation_seconds": float(robot.data.time), "left_palm": robot.fk("left"),
              "steps": log}
    write_new(folder / "preposition.json", result)
    return result


def run(output, arm, path_variant="overhead"):
    output.mkdir(parents=False, exist_ok=False)
    suite = read(SUITE / "registration.json")
    case = next(row for row in suite["cases"] if row["id"] == "asset_310300")
    model = suite["models"][case["model_key"]]
    expected_weights = read(METADATA / "contract.json")["weights"]["lfs_sha256_reported_by_hf"]
    weight_hash = sha(WEIGHTS)
    if weight_hash != expected_weights:
        raise ValueError("Checkpoint hash differs from the pinned original")
    sources = [Path(__file__), Path(__file__).with_name("t01_vla_policy.py"),
               ROOT / "grasp_optimization/smolvla_preview.py",
               ROOT / "grasp_optimization/smolvla_worker.py",
               ROOT / "experiments/grow_up_harness_v2/vla_runtime.py",
               Path(__file__).with_name("check_vla_prepose_clearance.py")]
    write_new(output / "registration.json", {
        "date": "2026-11-06", "boundary": "simulation", "arm": arm,
        "path_variant": path_variant,
        "case_id": case["id"], "suite": relative(SUITE), "seed_range": [310300, 310300],
        "outcome_filter": False, "split": "consumed_generator_development",
        "actual_sample": case, "plant_sha256": model["sha256"],
        "weight_sha256_before": weight_hash, "training": False,
        "source_sha256": {relative(path): sha(path) for path in sources},
        "evaluator_sha256": sha(ROOT / "experiments/t0_agent_v1/tray_verify.py"),
        "prediction": "A mean-posture waypoint with shoulder pitch 0.20 rad higher (more negative), then descent to the unchanged mean endpoint, will reach all seven joints within 0.10 rad with robot-tray contact <=0.10 N, tray translation <=1 mm and yaw <=0.5 deg at every physics step. Falsified by any rejected step, guard or threshold breach. If ready, expect no independent T01 success in a 30 s takeover; verified success falsifies that prediction.",
        "baseline_family": {"original_failure": "runs/t01_vla_safe_prepose_20261106_001/result.json",
                            "negative": "same preposition then wait", "treatment": "same preposition then frozen VLA",
                            "positive": "preposition readiness only; no claim of a task-positive control"},
        "autonomous_decisions": {"waypoint_step_m": 0.035, "move_seconds": 2.0,
                                 "mean_interpolation_seconds": 6.0 if path_variant == "overhead" else 4.0,
                                 "overhead_offset_rad": -0.20, "clear_points": CLEAR_POINTS,
                                 "contact_limit_N": CONTACT_LIMIT_N, "translation_limit_m": TRANSLATION_LIMIT_M,
                                 "yaw_limit_rad": float(YAW_LIMIT_RAD),
                                 "joint_tolerance_rad": JOINT_TOLERANCE,
                                 "takeover_seconds": 30.0, "retry_count": 0,
                                 "skipped": "no policy execution if preposition gate fails"},
        "scope": "engineering preposition plus frozen policy; not autonomous full-task VLA or skill promotion",
    })
    episode = output / "episode"
    episode.mkdir()
    write_new(episode / "instance.json", case["instance"])
    if sha(ROOT / model["path"]) != model["sha256"]:
        raise ValueError("Plant hash differs from generator registration")
    robot = ClearanceRobot(episode, case["instance"], budget=180.0, scene_path=ROOT / model["path"])
    port = CountedPort(robot)
    error, client, prepose = None, None, None
    chunks = []
    started = time.monotonic()
    right = np.array([i for i, name in enumerate(robot.names) if name.startswith("right_")])
    initial_right = robot.targets[right].copy()
    try:
        robot.advance(0.75, "initial_settling")
        prepose = preposition(robot, port, output, path_variant=path_variant)
        if prepose["ready"]:
            robot.monitor_prepose = False
            robot._save_state("takeover_state")
            write_new(output / "takeover.json", {
                "simulation_seconds": float(robot.data.time), "state_sha256": sha(episode / "takeover_state.npz"),
                "engineering_commands": port.command_calls,
                "right_targets_unchanged": bool(np.array_equal(robot.targets[right], initial_right)),
            })
            end = min(robot.budget, float(robot.data.time) + 30.0)
            if arm == "wait":
                robot.advance(end - float(robot.data.time), "negative_wait")
            elif arm == "vla":
                client = SmolVLAClient(output / "vla")
                names = client.info["joint_names"]
                while robot.data.time < end - 1e-9 and not robot.guard:
                    observation = port.observe()
                    state = port.state()
                    path = episode / f"chunk_{len(chunks) + 1:03}_native.npy"
                    response = client.predict({"head_rgb_path": observation["head_rgb_path"],
                        "joints_q_rad": {name: state["joints"][name]["q"] for name in names}},
                        INSTRUCTION, path, rng_seed=310300 + len(chunks))
                    robot.advance(min(response["request_wall_seconds"], end - float(robot.data.time)), "vla_inference_wait")
                    if robot.data.time >= end - 1e-9 or robot.guard:
                        break
                    native = np.load(path, allow_pickle=False)
                    if native.shape != (1, 50, 28) or not np.isfinite(native).all():
                        raise ValueError("Invalid native action chunk")
                    frames = min(15, int((end - float(robot.data.time)) * 30))
                    if frames < 1:
                        break
                    executed = joint_targets(robot, names, native, 0, frames, 30, hold_right=True)
                    rows = executed.pop("applied_rows")
                    applied = path.with_name(path.stem.replace("native", "applied") + ".npz")
                    np.savez_compressed(applied, time=[row[0] for row in rows], raw_target=[row[1] for row in rows],
                                        command_target=[row[2] for row in rows], actual_q=[row[3] for row in rows])
                    chunks.append({**executed, "inference": response, "applied_file": relative(applied)})
                    if not np.array_equal(robot.targets[right], initial_right):
                        raise ValueError("Right-arm hold contract changed during VLA execution")
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if client is not None:
            client.close()
    runtime = robot.finish()
    verdict = verify(episode, execution_error=error)
    weight_after = sha(WEIGHTS)
    result = {"arm": arm, "path_variant": path_variant,
              "prepose_ready": bool(prepose and prepose["ready"]), "error": error,
              "prepose_clearance": robot.clearance_report(),
              "training": False, "weight_sha256_after": weight_after,
              "weights_unchanged": weight_after == weight_hash, "runtime": runtime,
              "verified_success": verdict["verified_success"],
              "engineering_commands": port.command_calls,
              "vla_inference_calls": client.calls if client else 0,
              "vla_applied_frames": sum(row["applied_frames"] for row in chunks), "chunks": chunks,
              "right_targets_unchanged": bool(np.array_equal(robot.targets[right], initial_right)),
              "progress": proximity_metrics(robot, episode), "wall_seconds": time.monotonic() - started}
    write_new(output / "result.json", result)
    print(json.dumps({key: result[key] for key in ("arm", "prepose_ready", "verified_success", "error", "weights_unchanged")}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm", choices=("preflight", "wait", "vla"), default="preflight")
    parser.add_argument("--path-variant", choices=("direct", "overhead"), default="overhead")
    args = parser.parse_args()
    run(args.output.resolve(), args.arm, path_variant=args.path_variant)
