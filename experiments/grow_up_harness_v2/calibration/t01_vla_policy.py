"""Closed-loop SmolVLA on a generated T01 initial state.

Branch B of the 2026-11-05 split: 50-frame native absolute joint chunks, a prefix
executed with joint-range projection and a slew limit, then reobserve. Physics
advances during inference by the measured wall time.

Two deployment variants are registered, not tuned silently:
  --views head   one head image mapped to cam_left_high (the 2026-11-05 setup)
  --views four   mass-free stereo + wrist cameras from `fourview_camera`, with the
                 camera-only dynamics audit written next to the episode
  --hold-right   the checkpoint's right-arm/hand outputs are ignored; targets stay
                 where they were. The checkpoint natively drives both arms.

Success is only the independent evaluator's verdict.
"""

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
for entry in (str(ROOT), str(ROOT / "grasp_optimization"), str(ROOT / "experiments/grow_up_harness_v2")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from experiments.grow_up_harness_v2.vla_runtime import SmolVLAClient  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot  # noqa: E402
from experiments.t0_agent_v1.tray_verify import verify  # noqa: E402

SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_repl3_20261105_001"
SIM_BUDGET_S = 180.0
WALL_CAP_S = 900.0
FRAMES_PER_CHUNK = 15
INSTRUCTION = "Pick up the cup and place it on the tray."
PREDICTION = ("Expect failure. The checkpoint was trained on real-G1 toasted-bread episodes with four "
              "cameras and never saw a cup or tray. Falsified by a verified success, or by zero applied "
              "action frames (interface failure, not a policy result).")


def joint_targets(robot, names, native, start_frame, count, fps, hold_right=False):
    """Execute `count` native frames at `fps` with range projection and slew caps."""
    indices = np.array([robot.ai[name] for name in names])
    bounds = robot.model.jnt_range[robot.joint_ids[indices]]
    velocities = np.array([min(robot.joint_rows[name][5], 1.0 if "_hand_" in name else 0.75)
                           for name in names])
    hold = np.array([name.startswith("right_") for name in names]) if hold_right else np.zeros(len(names), bool)
    applied, projections, slews = 0, 0, 0
    tracking = None
    top = []
    rows = []
    for frame in range(start_frame, start_frame + count):
        target_raw = native[0, frame].astype(float)
        in_range = np.clip(target_raw, bounds[:, 0], bounds[:, 1])
        previous = robot.targets[indices].copy()
        in_range[hold] = previous[hold]
        end = robot.data.time + 1.0 / fps
        duration = max(float(robot.model.opt.timestep), end - robot.data.time)
        limited = previous + np.clip(in_range - previous, -velocities * duration, velocities * duration)
        projections += int(np.count_nonzero(np.abs(in_range - target_raw) > 1e-7))
        slews += int(np.count_nonzero(np.abs(limited - in_range) > 1e-7))
        frame_start = float(robot.data.time)
        while robot.data.time < end - 1e-9 and not robot.guard:
            fraction = min(1.0, (float(robot.data.time) - frame_start + robot.model.opt.timestep) / duration)
            robot.targets[indices] = previous + (limited - previous) * fraction
            robot._step()
        actual = robot.data.qpos[robot.qids[indices]].copy()
        rows.append((float(robot.data.time), target_raw.copy(), limited.copy(), actual))
        applied += 1
        arms = [i for i, name in enumerate(names) if "_hand_" not in name]
        if arms:
            error = np.abs(actual[arms] - robot.targets[indices][arms])
            tracking = float(np.max(error))
            top = [(names[arms[i]], round(float(error[i]), 3))
                   for i in np.argsort(-error)[:3]]
        if robot.guard or (tracking is not None and tracking > 0.45):
            if tracking is not None and tracking > 0.45 and not robot.guard:
                # A held arm keeps its registered targets even on tracking exit.
                robot.targets[indices[~hold]] = actual[~hold]
            break
        if robot.data.time >= robot.budget - 1e-9:
            break
    return {"applied_frames": applied, "projection_count": projections,
            "slew_limit_count": slews, "tracking_error_rad": tracking,
            "tracking_worst_joints": top, "applied_rows": rows}


def fourview_paths(robot, episode: Path, observation_id: str) -> dict:
    """Render the four training camera slots on the current state without stepping."""
    from fourview_camera import render_views
    frames = render_views(robot)
    paths = {}
    for key, pixels in frames.items():
        name = key.rsplit(".", 1)[-1]
        path = episode / f"{observation_id}_{name}.jpg"
        Image.fromarray(pixels).save(path, quality=95)
        paths[key] = str(path.resolve())
    return paths


def proximity_metrics(robot, episode: Path) -> dict:
    """Graded task progress even when the binary verdict is failure."""
    import mujoco
    with np.load(episode / "trajectory.npz") as trajectory:
        qpos = trajectory["qpos"]
        times = trajectory["time"]
    model = robot.model
    data = mujoco.MjData(model)
    cup, palm, tray = model.body("task_cup").id, model.site("left_palm").id, model.body("task_tray").id
    cup0 = None
    closest, lift, displacement = float("inf"), 0.0, 0.0
    for frame in qpos[::4]:
        data.qpos[:] = frame
        mujoco.mj_forward(model, data)
        position = data.xpos[cup].copy()
        if cup0 is None:
            cup0 = position
        closest = min(closest, float(np.linalg.norm(data.site_xpos[palm] - position)))
        lift = max(lift, float(position[2] - cup0[2]))
        displacement = max(displacement, float(np.linalg.norm(position[:2] - cup0[:2])))
    return {"min_left_palm_to_cup_m": round(closest, 4), "max_cup_lift_m": round(lift, 4),
            "max_cup_planar_displacement_m": round(displacement, 4),
            "samples": int(len(qpos[::4])), "first_time_s": float(times[0]),
            "last_time_s": float(times[-1])}


def run(output: Path, case_id: str, *, seconds: float = SIM_BUDGET_S,
        frames: int = FRAMES_PER_CHUNK, rate_hz: int = 30, views: str = "head",
        hold_right: bool = False, prepose: str = "none", instruction: str = INSTRUCTION,
        prediction: str = PREDICTION) -> dict:
    if views not in ("head", "four"):
        raise ValueError("views must be head or four")
    output.mkdir(parents=False, exist_ok=False)
    registration = read(SUITE / "registration.json")
    case = next(row for row in registration["cases"] if row["id"] == case_id)
    model_ref = registration["models"][case["model_key"]]
    camera_variant = ("four simulated views from the mass-free engineering rig"
                      if views == "four" else
                      "one simulated head view mapped to cam_left_high; three training views omitted")
    episode = output / "episode"
    episode.mkdir()
    write_new(episode / "instance.json", case["instance"])
    write_new(output / "registration.json", {
        "date": "2026-11-06", "boundary": "simulation", "kind": "t01_vla_policy",
        "suite": relative(SUITE), "case_id": case_id,
        "instruction": instruction, "camera_variant": camera_variant, "views": views,
        "hold_right": hold_right, "prepose": prepose,
        "frames_per_chunk": frames, "native_fps": 30, "execution_hz": rate_hz, "native_chunk": 50,
        "simulation_budget_s": seconds, "wall_cap_s": WALL_CAP_S,
        "plant_sha256": model_ref["sha256"],
        "evaluator_sha256": sha(ROOT / "experiments/t0_agent_v1/tray_verify.py"),
        "policy": "kiteml/G1-ego-test-smolvla", "revision": "cf2f88ba6d5db3f3647b453438a0a1904e07919f",
        "training_task": "toasted bread; cup transfer unverified",
        "physics_during_latency": "post-hoc advance by measured request wall time, capped at the budget",
        "sample_note": ("inference wall time advances physics, so two runs of the same case are not deterministic "
                        "replays of each other; latency is recorded per chunk"),
        "prediction": prediction,
        "changed_after_previous_run": None,
        "model_requests": 0,
    })
    robot = PilotRobot(episode, case["instance"], budget=seconds,
                       scene_path=ROOT / model_ref["path"])
    port = CountedPort(robot)
    robot.advance(0.75, "initial_settling")
    if views == "four":
        from fourview_camera import attach_cameras
        robot.scene_path = (ROOT / model_ref["path"]).with_name(
            (ROOT / model_ref["path"]).name.replace("_model.mjb", "_scene.xml"))
        rig = attach_cameras(robot)
        write_new(output / "fourview_rig.json", rig)
    wall = time.monotonic()
    error = None
    client = None
    chunks = []
    prepose_result = None
    try:
        client = SmolVLAClient(output / "vla")
        names = client.info["joint_names"]
        if len(names) != 28 or any(name not in robot.ai for name in names):
            raise ValueError("The 28 checkpoint joints do not match the plant")
        if int(client.info["policy_fps"]) != 30:
            raise ValueError("This adapter is configured for the audited 30 Hz checkpoint")
        if prepose == "mean":
            metadata = json.loads((ROOT / "grasp_optimization/assets/vla_checkpoint_metadata/"
                                   "kiteml_g1_smolvla/normalization_decoded.json").read_text(encoding="utf-8"))
            means = metadata["action.mean"]["values"]
            targets = {name: float(value) for name, value in zip(names, means)
                       if name.startswith("left_") and "_hand_" not in name}
            prepose_result = port.invoke("set_joints", {"targets": targets, "duration": 2.0})
            print(json.dumps({"prepose": targets, "status": prepose_result.get("status", "EXECUTED")},
                             ensure_ascii=False), flush=True)
        index = 0
        while robot.data.time < robot.budget - 1e-9 and not robot.guard:
            if time.monotonic() - wall > WALL_CAP_S:
                error = {"type": "WallCapReached", "message": f"{WALL_CAP_S:.0f} s wall cap"}
                break
            index += 1
            observation = port.observe()
            native_path = episode / f"chunk_{index:03}_native.npy"
            state = port.state()
            request = {"joints_q_rad": {name: state["joints"][name]["q"] for name in names}}
            if views == "four":
                request["cameras"] = fourview_paths(robot, episode, observation["observation_id"])
            else:
                request["head_rgb_path"] = observation["head_rgb_path"]
            response = client.predict(request, instruction, native_path)
            robot.advance(response["request_wall_seconds"], "vla_inference_wait")
            native = np.load(native_path, allow_pickle=False)
            if native.shape != (1, 50, 28) or not np.isfinite(native).all():
                raise ValueError(f"Native actions are not finite (1,50,28): {native.shape}")
            record = {"chunk": index, "observation_id": observation["observation_id"],
                      "simulation_seconds_before": observation["simulation_seconds"],
                      "inference_seconds": response["result"]["inference_seconds"],
                      "request_wall_seconds": response["request_wall_seconds"],
                      "camera_keys": response["result"].get("camera_keys"),
                      "native_file": relative(native_path)}
            executed = joint_targets(robot, names, native, 0, min(frames, 50), rate_hz, hold_right)
            applied_path = episode / f"chunk_{index:03}_applied.npz"
            rows = executed.pop("applied_rows")
            np.savez_compressed(applied_path, time=[row[0] for row in rows],
                                raw_target=[row[1] for row in rows],
                                command_target=[row[2] for row in rows],
                                actual_q=[row[3] for row in rows])
            record.update(executed)
            record["applied_file"] = relative(applied_path)
            record["simulation_seconds_after"] = float(robot.data.time)
            chunks.append(record)
            write_new(episode / f"chunk_{index:03}.json", record)
            print(json.dumps({key: record[key] for key in ("chunk", "applied_frames", "tracking_error_rad")},
                             ensure_ascii=False), flush=True)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        error = {"type": type(exc).__name__, "message": str(exc)[:600]}
    finally:
        if client is not None:
            client.close()
    runtime = robot.finish()
    verdict = verify(episode, execution_error=error)
    result = {
        "case": case_id, "instruction": instruction, "camera_variant": camera_variant,
        "views": views, "hold_right": hold_right,
        "verified_success": verdict["verified_success"],
        "terminal_stable_s": verdict["terminal_simultaneous_stable_s"],
        "simulation_seconds": runtime["simulation_seconds"],
        "low_level_commands": port.command_calls,
        "vla_chunks": len(chunks), "vla_frames": sum(c["applied_frames"] for c in chunks),
        "projection_count": sum(c["projection_count"] for c in chunks),
        "slew_limit_count": sum(c["slew_limit_count"] for c in chunks),
        "guard": robot.guard, "wall_seconds": round(time.monotonic() - wall, 1),
        "prepose": prepose, "prepose_result": prepose_result,
        "task_progress": proximity_metrics(robot, episode),
        "chunks": chunks, "error": error, "episode": relative(episode),
    }
    write_new(output / "result.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", default="asset_310300")
    parser.add_argument("--seconds", type=float, default=SIM_BUDGET_S)
    parser.add_argument("--frames", type=int, default=FRAMES_PER_CHUNK)
    parser.add_argument("--rate-hz", type=int, default=30)
    parser.add_argument("--views", choices=["head", "four"], default="head")
    parser.add_argument("--hold-right", action="store_true")
    parser.add_argument("--prepose", choices=["none", "mean"], default="none")
    parser.add_argument("--prediction", default=PREDICTION)
    parser.add_argument("--instruction", default=INSTRUCTION)
    args = parser.parse_args(argv)
    result = run(args.output.resolve(), args.case, seconds=args.seconds,
                 frames=args.frames, rate_hz=args.rate_hz, views=args.views,
                 hold_right=args.hold_right, prepose=args.prepose, instruction=args.instruction,
                 prediction=args.prediction)
    print(json.dumps({key: result[key] for key in ("case", "verified_success", "vla_chunks",
                                                   "vla_frames", "simulation_seconds", "guard")},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
