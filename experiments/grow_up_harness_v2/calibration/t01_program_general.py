"""Run the distilled T01 program on TP03 cases from the general task generator.

TP03 is the generator's "cup into tray" template. These instances are sampled
by `tabletop_dataset.py`, not by the T01 variation suite, and they use a
different cup asset (radius 0.044 m), a different tray and a different
evaluator (`tabletop_predicates`). Zero model requests.
"""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PACKAGE = ROOT / "experiments/grow_up_harness_v2"
if str(PACKAGE / "calibration") not in sys.path:
    sys.path.insert(0, str(PACKAGE / "calibration"))

import t01_agent_pilot as pilot  # noqa: E402
import t01_motion  # noqa: E402
import mujoco  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant, independent_verify  # noqa: E402

MANIFEST_DATASET = ROOT / "experiments/t0_agent_v1/tabletop_dataset_20261026_003"
PROGRAM = PACKAGE / "artifacts/generated/t01_cup_to_tray/program.py"
MAX_CORRECTIONS = 6


def load_program():
    spec = importlib.util.spec_from_file_location("t01_program", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pelvis_frame(plant, world):
    pelvis = plant.data.xpos[plant.pelvis_id]
    rotation = plant.data.xmat[plant.pelvis_id].reshape(3, 3)
    return rotation.T @ (np.asarray(world) - pelvis)


class PlantProbe:
    """What move_ee() needs: model, data, pelvis site, and a joint sink."""

    def __init__(self, plant):
        self.plant = plant
        self.model = plant.model
        self.data = plant.data
        self.pelvis_id = plant.pelvis_id
        self.targets = plant.targets
        self.ai = plant.ai
        self.joint_rows = plant.joint_rows
        self.minimum_seconds = None

    def set_joints(self, targets, duration):
        result = self.plant.dispatch({"op": "set_joints", "targets": targets,
                                      "duration": float(duration)})
        self.minimum_seconds = float(duration)
        return result

    def fk(self, side):
        return self.plant.observation()["left_palm"]


def observe(plant, probe, cup_in_palm):
    body = plant.observation()
    cup = pelvis_frame(plant, plant.data.xpos[plant.cup_id])
    floor = pelvis_frame(plant, plant.data.geom_xpos[plant.model.geom("tray_floor").id])
    return {
        "frame": "current_pelvis",
        "cup_bottoms_m": [[float(v) for v in cup]],
        "tray_floor_center_m": [float(v) for v in floor],
        "left_palm": body["left_palm"],
        "grasp_probe": t01_motion.grasp_probe(probe, cup.tolist(), cup_in_palm),
        "place_probe": t01_motion.place_probe(floor.tolist(), cup_in_palm),
        "joints": {name: dict(q=row["q"], target=row["target"])
                   for name, row in body["joints"].items() if pilot.controllable(name)},
    }


def execute(plant, probe, command, tray_floor, session):
    op = command["op"]
    if op == "wait":
        return plant.dispatch({"op": "wait", "seconds": float(command["seconds"])})
    if op == "joints":
        return plant.dispatch({"op": "set_joints",
                               "targets": {item["joint"]: item["radians"] for item in command["targets"]},
                               "duration": float(command["seconds"])})
    if op == "move":
        palm = plant.observation()["left_palm"]["position_m"]
        target = [command[key] for key in "xyz"]
        if float(np.linalg.norm(np.asarray(palm) - np.asarray(target))) > pilot.MAX_MOVE_M + 1e-9:
            raise ValueError("move exceeds the 5 cm single-command limit")
        return mujoco_probe_move(probe, target, command)
    raise ValueError(f"unsupported command {op}")


def mujoco_probe_move(probe, target, command):
    from experiments.t0_agent_v1.runtime import PilotRobot
    quaternion = t01_motion.quaternion_for(command)
    return PilotRobot.move_ee(probe, "left", target, quaternion, float(command["seconds"]))


def run_case(case_dir, instance, program, output):
    output.mkdir(parents=True, exist_ok=True)
    model = mujoco.MjModel.from_xml_path(str(case_dir / "pantry_G1.xml"))
    plant = TabletopPlant(instance, case_dir, model, output, budget=180.)
    probe = PlantProbe(plant)
    session = {}
    corrections = 0
    rejection = None
    phase = "plan"
    error = None
    started = time.monotonic()
    try:
        state = observe(plant, probe, pilot.CUP_IN_PALM_M)
        params = program.grasp_parameters(state)
        tray = state["tray_floor_center_m"]

        def run_batch(batch):
            nonlocal rejection
            for command in batch:
                if command["op"] == "finish":
                    return
                try:
                    reply = execute(plant, probe, command, tray, session)
                except ValueError as exc:
                    rejection = {"phase": phase, "command": command, "reason": str(exc)}
                    return
                if reply.get("status") not in ("EXECUTED", None):
                    rejection = {"phase": phase, "command": command, "reason": reply.get("status")}
                    return
                if plant.guard:
                    rejection = {"phase": phase, "command": command, "reason": plant.guard}
                    return

        run_batch(program.plan(state))
        if rejection is None:
            phase = "lift"
            state = observe(plant, probe, pilot.CUP_IN_PALM_M)
            run_batch(program.lift(state, params))
        if rejection is None:
            phase = "correct"
            while corrections < MAX_CORRECTIONS:
                state = observe(plant, probe, pilot.CUP_IN_PALM_M)
                fix = program.correct(state, params)
                if not fix:
                    break
                corrections += 1
                run_batch(fix)
                if rejection is not None:
                    break
        if rejection is None:
            phase = "release"
            state = observe(plant, probe, pilot.CUP_IN_PALM_M)
            run_batch(program.release(state, params))
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:600], "phase": phase}
    wall = time.monotonic() - started
    runtime = plant.save(error)
    verdict = independent_verify(output, instance, model, initial_valid=True)
    return {
        "case": instance["id"], "split": instance.get("split"),
        "verified_success": verdict["verified_task_success"],
        "stable_s": round(verdict["terminal_simultaneous_stable_s"], 3),
        "simulation_s": round(runtime["simulation_seconds"], 2),
        "commands": runtime["low_level_commands"],
        "corrections": corrections, "phase": phase,
        "rejection": rejection, "error": error, "wall_s": round(wall, 1),
        "cup_radius_m": instance["objects"][1]["asset"].get("radius_m"),
        "folder": relative(output),
    }


def run(output: Path, split="train", limit=None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    program = load_program()
    manifest = read(MANIFEST_DATASET / split / "manifest.json")
    cases = [row for row in manifest["instances"] if row["template_id"] == "TP03"]
    if limit:
        cases = cases[:limit]
    write_new(output / "registration.json", {
        "date": "2026-11-05", "boundary": "simulation", "kind": "program_transfer_general_generator",
        "dataset": relative(MANIFEST_DATASET / split), "template": "TP03",
        "cases": [row["id"] for row in cases],
        "program_sha256": sha(PROGRAM), "model_requests": 0,
        "note": "TP03 cup-to-tray cases sampled by tabletop_dataset.py; evaluator is tabletop_predicates, not tray_verify.",
    })
    rows = []
    for row in cases:
        case_dir = (MANIFEST_DATASET / row["evaluator_instance"]).resolve().parent
        instance = read(case_dir / "instance.json")
        case_output = output / row["id"]
        result = run_case(case_dir, instance, program, case_output)
        rows.append(result)
        print(f"{row['id']:20s} ok={result['verified_success']!s:5s} "
              f"stable={result['stable_s']:.2f} phase={result['phase']} "
              f"cmd={result['commands']} ({sum(1 for r in rows if r['verified_success'])}/{len(rows)})",
              flush=True)
    summary = {"episodes": len(rows), "successes": sum(1 for r in rows if r["verified_success"]),
               "rows": rows}
    write_new(output / "results.json", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", default="train", choices=("train", "test"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    summary = run(args.output.resolve(), args.split, args.limit)
    print(json.dumps({k: summary[k] for k in ("episodes", "successes")}, indent=1))
    return 0 if summary["successes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
