"""Paired frozen-VLA input-response diagnostic; rendering and inference, no mj_step.

One consumed generator case supplies the robot takeover state. Other consumed
position samples supply cup XY only, so these are counterfactual sensor probes,
not physically qualified new episodes. Common RNG seeds separate input response
from flow-sampling noise. Repeated inputs measure reproducibility.
"""

import argparse
import itertools
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import mujoco
import numpy as np
from PIL import Image

from experiments.grow_up_harness_v2.vla_runtime import SmolVLAClient
from experiments.t0_agent_v1.common import read, relative, sha, write_new

SOURCE = ROOT / "experiments/grow_up_harness_v2/runs/t01_vla_overhead_takeover_20261106_001"
SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_repl3_20261105_001"
METADATA = ROOT / "grasp_optimization/assets/vla_checkpoint_metadata/kiteml_g1_smolvla"
CHECKPOINT = Path.home() / "vla-work/models/g1-smolvla"
POSITIONS = ("asset_310300", "position_310100", "position_310101", "position_310102", "position_310103")
INSTRUCTIONS = {
    "transfer": "Pick up the cup and place it on the tray.",
    "still": "Keep both hands still. Do not touch the cup.",
    "left_grasp": "Pick up the cup with your left hand.",
    "source_task": "Place bread in toaster; after toasting hand toast to human",
}
NOISE_SEEDS = (610600, 610601, 610602)
SCHEDULE_SEED = 20261106
NUMERICAL_FLOOR_RAD = 1e-5


def rmse(a, b):
    return float(np.sqrt(np.mean((a.astype(float) - b.astype(float)) ** 2)))


def prepare(output):
    suite = read(SUITE / "registration.json")
    cases = {row["id"]: row for row in suite["cases"]}
    ref = read(SOURCE / "episode/model_reference.json")
    if sha(ROOT / ref["path"]) != ref["sha256"]:
        raise ValueError("Source plant hash changed")
    contract = read(METADATA / "contract.json")
    weights = sha(CHECKPOINT / "model.safetensors")
    if weights != contract["weights"]["lfs_sha256_reported_by_hf"]:
        raise ValueError("Weights differ from pinned original")
    bundle = {}
    for filename in contract["required_bundle_files"]:
        bundle[filename] = weights if filename == "model.safetensors" else sha(CHECKPOINT / filename)
        if filename != "model.safetensors" and bundle[filename] != sha(METADATA / filename):
            raise ValueError("Checkpoint processor/config differs from audited metadata: " + filename)
    names = read(SOURCE / "vla/policy_runtime.json")["joint_names"]
    schedule = []
    for seed in NOISE_SEEDS:
        block = [{"seed": seed, "position": position, "instruction": instruction, "kind": "factorial"}
                 for position, instruction in itertools.product(POSITIONS, INSTRUCTIONS)]
        block += [{"seed": seed, "position": "asset_310300", "instruction": "transfer", "kind": "repeat"},
                  {"seed": seed, "position": "blank", "instruction": "transfer", "kind": "blank_image"}]
        random.Random(SCHEDULE_SEED + seed).shuffle(block)
        schedule.extend(block)
    source_paths = [Path(__file__), SOURCE / "episode/model_reference.json", SOURCE / "episode/takeover_state.npz",
                    SOURCE / "episode/obs_001.json", SOURCE / "vla/policy_runtime.json", SUITE / "registration.json",
                    ROOT / "grasp_optimization/smolvla_preview.py", ROOT / "grasp_optimization/smolvla_worker.py",
                    ROOT / "experiments/grow_up_harness_v2/vla_runtime.py"]
    write_new(output / "registration.json", {
        "date": "2026-11-06", "boundary": "simulation_sensor_snapshots_only", "training": False,
        "physics_steps": 0, "motor_execution": False, "outcome_filter": False,
        "generator_seed_segments": [[310100, 310103], [310300, 310300]],
        "split": "consumed_generator_development_counterfactual_probe",
        "source": relative(SOURCE), "actual_samples": {key: cases[key] for key in POSITIONS},
        "intervention": "Only cup world XY replaced by existing generator position samples; robot, cup orientation, tray and all other state fixed. No physics qualification.",
        "instructions": INSTRUCTIONS, "noise_seeds": NOISE_SEEDS, "schedule_seed": SCHEDULE_SEED,
        "schedule": schedule, "calls_cap": len(schedule), "source_sha256": {relative(p): sha(p) for p in source_paths},
        "checkpoint_bundle_sha256_before": bundle,
        "camera_variant": "single simulated g1_head view mapped to cam_left_high; other views absent",
        "visibility_gate": "each position must render >=25 visible cup pixels; report input failure if any fail, no replacement samples",
        "prediction": "Expect repeated identical inputs to agree within 1e-5 rad RMSE. Position effects on left-arm actions are expected to be below 0.01 rad RMSE and smaller than changing the inference noise seed. Falsified if a position contrast exceeds either criterion. Instruction response is measured without predicting task competence.",
        "analysis": {"negative": "same state/image/instruction/RNG repeated once per block",
                     "diagnostic_control": "all-black image with unchanged joints and instruction",
                     "detection": "paired delta RMSE > max(1e-5 rad, 10 * maximum repeat RMSE); descriptive only",
                     "practical_reference_rad": 0.01, "noise_reference": "baseline action RMSE across the three different RNG seeds",
                     "units": "native absolute radians after original postprocessor",
                     "primary": "left-arm seven joints, first 15 frames; also report full chunk and all 28 dimensions",
                     "replication": "one robot handover state; RNG blocks are computational repeats, not independent task episodes"},
    })
    model = mujoco.MjModel.from_binary_path(str(ROOT / ref["path"]))
    data = mujoco.MjData(model)
    with np.load(SOURCE / "episode/takeover_state.npz") as state:
        integration = state["mujoco_integration_state"].copy()
    mujoco.mj_setState(model, data, integration, mujoco.mjtState.mjSTATE_INTEGRATION)
    mujoco.mj_forward(model, data)
    joints = {name: float(data.qpos[model.jnt_qposadr[model.joint(name).id]]) for name in names}
    obsdir = output / "observations"
    obsdir.mkdir()
    options = mujoco.MjvOption()
    options.geomgroup[:] = [0, 1, 1, 0, 0, 0]
    renderer = mujoco.Renderer(model, height=720, width=1280, max_geom=4000)
    cup_id = model.body("task_cup").id
    cup_geoms = np.flatnonzero(model.geom_bodyid == cup_id)
    cup_q = model.jnt_qposadr[model.joint("task_cup_free").id]
    observations = {}
    try:
        for position in POSITIONS:
            mujoco.mj_setState(model, data, integration, mujoco.mjtState.mjSTATE_INTEGRATION)
            data.qpos[cup_q:cup_q + 2] = cases[position]["instance"]["cup_table_xy_m"]
            mujoco.mj_forward(model, data)
            renderer.update_scene(data, camera="g1_head", scene_option=options)
            rgb = renderer.render().copy()
            renderer.enable_segmentation_rendering()
            segmentation = renderer.render().copy()
            renderer.disable_segmentation_rendering()
            pixels = int(np.count_nonzero(np.isin(segmentation[:, :, 0], cup_geoms)
                                         & (segmentation[:, :, 1] == int(mujoco.mjtObj.mjOBJ_GEOM))))
            path = obsdir / f"{position}.jpg"
            Image.fromarray(rgb).save(path, quality=90)
            observations[position] = {"head_rgb_path": str(path.resolve()), "joints_q_rad": joints,
                                      "cup_world_xyz_m": data.qpos[cup_q:cup_q + 3].tolist(),
                                      "visible_cup_pixels": pixels, "image_sha256": sha(path),
                                      "simulation_seconds": float(data.time)}
        path = obsdir / "blank.jpg"
        Image.fromarray(np.zeros((720, 1280, 3), dtype=np.uint8)).save(path, quality=90)
        observations["blank"] = {"head_rgb_path": str(path.resolve()), "joints_q_rad": joints,
                                 "image_sha256": sha(path), "synthetic_ablation": True,
                                 "simulation_seconds": float(data.time)}
    finally:
        renderer.close()
    write_new(output / "observations.json", observations)
    return schedule, observations, names, bundle


def summarize(rows, names):
    primary = [i for i, name in enumerate(names) if name.startswith("left_") and "_hand_" not in name]
    metrics = {}
    subsets = {"left_arm_first15": (slice(0, 15), primary),
               "left_arm_full50": (slice(None), primary), "all28_full50": (slice(None), list(range(28)))}
    arrays = {row["index"]: np.load(ROOT / row["action_file"], allow_pickle=False)[0] for row in rows}
    baselines = {row["seed"]: row for row in rows if row["kind"] == "factorial"
                 and row["position"] == "asset_310300" and row["instruction"] == "transfer"}
    for label, (frames, columns) in subsets.items():
        def values(row):
            return arrays[row["index"]][frames][:, columns]
        repeats = [{"seed": row["seed"], "rmse_rad": rmse(values(row), values(baselines[row["seed"]]))}
                   for row in rows if row["kind"] == "repeat"]
        repeat_max = max(row["rmse_rad"] for row in repeats)
        threshold = max(NUMERICAL_FLOOR_RAD, 10 * repeat_max)
        noise = [{"seeds": [first, second], "rmse_rad": rmse(values(baselines[first]), values(baselines[second]))}
                 for first, second in itertools.combinations(NOISE_SEEDS, 2)]
        noise_median = float(np.median([row["rmse_rad"] for row in noise]))
        effects = []
        for row in rows:
            if row["kind"] == "repeat" or row["index"] == baselines[row["seed"]]["index"]:
                continue
            # One-factor comparisons: position at transfer; instruction at original position.
            if row["instruction"] != "transfer" and row["position"] != "asset_310300":
                continue
            delta = rmse(values(row), values(baselines[row["seed"]]))
            effects.append({"seed": row["seed"], "position": row["position"], "instruction": row["instruction"],
                            "kind": row["kind"], "rmse_rad": delta, "above_repeat_floor": delta > threshold,
                            "ratio_to_median_noise_delta": delta / noise_median if noise_median > 0 else None})
        metrics[label] = {"repeat_rmse": repeats, "response_threshold_rad": threshold,
                          "baseline_different_rng_rmse": noise, "one_factor_effects": effects}
    return metrics


def run(output):
    output.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    schedule, observations, names, bundle = prepare(output)
    rows, client, error = [], None, None
    visibility_valid = all(observations[key]["visible_cup_pixels"] >= 25 for key in POSITIONS)
    try:
        if not visibility_valid:
            raise ValueError("Cup visibility gate failed; no inputs replaced and no inference executed")
        client = SmolVLAClient(output / "vla")
        if client.info["joint_names"] != names:
            raise ValueError("Worker joint order changed")
        actions = output / "actions"
        actions.mkdir()
        for index, condition in enumerate(schedule, 1):
            source = observations[condition["position"]]
            path = actions / f"{index:03}.npy"
            response = client.predict({"head_rgb_path": source["head_rgb_path"], "joints_q_rad": source["joints_q_rad"]},
                                      INSTRUCTIONS[condition["instruction"]], path, rng_seed=condition["seed"])
            row = {"index": index, **condition, "action_file": relative(path), "response": response}
            write_new(actions / f"{index:03}.json", row)
            rows.append(row)
            if index % 11 == 0:
                print(json.dumps({"completed_predictions": index, "total": len(schedule)}), flush=True)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if client is not None:
            client.close()
    after = {filename: sha(CHECKPOINT / filename) for filename in bundle}
    result = {"date": "2026-11-06", "status": "COMPLETE" if error is None else "INPUT_OR_INFERENCE_ERROR",
              "training": False, "physics_steps": 0, "motor_execution": False,
              "generator_seed_segments": [[310100, 310103], [310300, 310300]], "outcome_filter": False,
              "visibility_valid": visibility_valid, "inference_calls": client.calls if client else 0,
              "checkpoint_bundle_unchanged": after == bundle, "checkpoint_bundle_sha256_after": after,
              "error": error, "rows": rows, "wall_seconds": time.monotonic() - started}
    if error is None:
        result["response_metrics"] = summarize(rows, names)
        result["rng_hash_equal_within_seed"] = all(len({row["response"]["rng_cuda_sha256_before"] for row in rows
                                                       if row["seed"] == seed}) == 1 for seed in NOISE_SEEDS)
    write_new(output / "result.json", result)
    print(json.dumps({key: result[key] for key in ("status", "inference_calls", "visibility_valid", "checkpoint_bundle_unchanged", "error")}))
    return 0 if error is None else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output.resolve()))
