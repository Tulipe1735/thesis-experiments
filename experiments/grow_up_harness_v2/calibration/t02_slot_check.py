"""Run one T02 slot placement and report the per-cup landing metrics.

T02 needs three cups in one tray, so the whole-task verdict stays false until
all three are in. This entry runs a single cup into a designated slot and
reports that cup's footprint margin, support and contact loads.
"""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PACKAGE = ROOT / "experiments/grow_up_harness_v2"
if str(PACKAGE / "calibration") not in sys.path:
    sys.path.insert(0, str(PACKAGE / "calibration"))

from t02_execution import bind_slot, execute_batch, stable_slot
import t01_agent_pilot as pilot  # noqa: E402
from harness import artifact as artifact_mod  # noqa: E402
from experiments.cordis_t01.worker import SavedInitialRobot  # noqa: E402
from harness.tp01 import TickRecordedRobot  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new, append_event  # noqa: E402
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot  # noqa: E402
from experiments.t0_agent_v1.tray_verify import verify  # noqa: E402

SUITE = ROOT / "experiments/t0_agent_v1/tray_20261025_001"
ARTIFACT = PACKAGE / "artifacts/t02_slot_place.yaml"


def load_program(record: artifact_mod.Artifact):
    path = ROOT / record.projections.code.path
    spec = importlib.util.spec_from_file_location("t02_program", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(output: Path, seed: int, cup_body: str, slot: str = "slot_0",
        suite: Path | None = None, case_id: str | None = None,
        saved_initial: Path | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    if suite is not None:
        registration = read(suite / "registration.json")
        case = next(row for row in registration["cases"] if row["id"] == case_id)
        instance = case["instance"]
        plant_path = ROOT / registration["models"][case["model_key"]]["path"]
        saved = None
    else:
        instance = next(row for row in read(SUITE / "instances.json")
                        if row.get("task") == "T02" and row.get("seed") == seed)
        plant_path = SUITE / "T02_model.mjb"
        saved = SUITE / f"episodes/{seed}_T02_scripted/initial_state.npz"
    if saved_initial is not None:
        saved = saved_initial
    seed = instance["seed"]
    if cup_body != "task_cup":
        raise ValueError("non-default object identity is not bound to the visual selector; refusing misleading --cup")
    record = bind_slot(artifact_mod.load(ARTIFACT), slot)
    code = output / "bound_program.py"
    with code.open("x") as handle:
        handle.write(artifact_mod.generate_code(record))
    spec = importlib.util.spec_from_file_location("t02_bound_program", code)
    program = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(program)
    write_new(output / "registration.json", {
        "date": "2026-11-07", "boundary": "simulation", "kind": "t02_slot_placement",
        "slot": slot, "bound_code_sha256": sha(code),
        "prediction": "requested slot is bound; non-success motion stops all later phases",
        "falsification": "executing release after rejected motion, or a different slot in the bound code",
        "artifact": relative(ARTIFACT), "artifact_digest": artifact_mod.digest(record),
        "suite": relative(suite) if suite is not None else relative(SUITE),
        "case_id": case_id, "seed": seed, "cup_body": cup_body,
        "plant_sha256": sha(plant_path),
        "evaluator_sha256": sha(ROOT / "experiments/t0_agent_v1/tray_verify.py"),
        "model_requests": 0, "classification": "engineering slot calibration; not Agent practice",
        "saved_initial": relative(saved) if saved is not None else None,
        "saved_initial_sha256": sha(saved) if saved is not None else None,
    })
    episode = output / "episode"
    episode.mkdir()
    write_new(episode / "instance.json", instance)
    if saved is None:
        robot = PilotRobot(episode, instance, budget=180., scene_path=plant_path)
    else:
        robot = TickRecordedRobot(episode, instance, budget=180.,
                                  scene_path=plant_path, initial_state=saved)
    port = CountedPort(robot)
    session = {}
    rejection = None
    error = None
    started = time.monotonic()
    try:
        robot.advance(.75, "initial_settling")
        state = pilot.observe(port, robot)
        params = program.grasp_parameters(state)

        def run_batch(batch, phase):
            nonlocal rejection
            try:
                rejection = execute_batch(batch,
                    lambda command: pilot.execute(port, command, robot, state.get("tray_floor_center_m"), session),
                    phase=phase, log=lambda row: append_event(output / "execution.jsonl", row))
            except ValueError as exc:
                rejection = {"phase": phase, "reason": str(exc)}

        run_batch(program.plan(state), "plan")
        if rejection is None:
            run_batch(program.lift(pilot.observe(port, robot), params), "lift")
        if rejection is None:
            run_batch(program.release(pilot.observe(port, robot), params), "release")
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:600]}
    wall = time.monotonic() - started
    environment = robot.finish()
    verdict = verify(episode, execution_error=error or rejection)
    cup = verdict["final"]["cups"][cup_body]
    slot_xy = record.ir.slots[slot]
    slot_error = ((cup["cup_position_tray_m"][0] - slot_xy[0]) ** 2
                  + (cup["cup_position_tray_m"][1] - slot_xy[1]) ** 2) ** 0.5
    stability = stable_slot(read(episode / "verified_samples.json"), cup_body, slot_xy)
    result = {
        "artifact": record.id, "seed": seed, "cup_body": cup_body,
        "whole_task_success": verdict["verified_success"],
        "cup": {"margin_m": round(cup["footprint_margin_m"], 5),
                "support_N": round(cup["tray_floor_support_N"], 3),
                "hand_contact_N": round(cup["hand_contact_N"], 3),
                "other_contact_N": round(cup["other_object_contact_N"], 3),
                "tilt_deg": round(cup["cup_tilt_deg"], 2),
                "tray_xy_m": [round(v, 4) for v in cup["cup_position_tray_m"][:2]]},
        "slot": slot,
        "slot_target_m": [round(v, 4) for v in slot_xy],
        "slot_error_m": round(slot_error, 4),
        **stability,
        "slot_success": bool(verdict["initial_valid"] and verdict["no_external_forces"]
                             and verdict["equality_constraints"] == 0
                             and stability["stable_slot_success"] and slot_error <= 0.015 and not error and not rejection and not environment["protection"]),
        "single_cup_success": bool(verdict["initial_valid"] and verdict["no_external_forces"]
                                   and verdict["equality_constraints"] == 0
                                   and verdict["per_cup_terminal_stable_s"][cup_body] >= 1.
                                   and not error and not rejection and not environment["protection"]
                                   and cup["footprint_margin_m"] >= 0.001
                                   and cup["tray_floor_support_N"] >= 0.5
                                   and cup["hand_contact_N"] < 0.1
                                   and cup["other_object_contact_N"] < 0.1
                                   and cup["cup_tilt_deg"] <= 5.0),
        "commands": port.command_calls, "simulation_s": round(environment["simulation_seconds"], 2),
        "wall_s": round(wall, 1), "rejection": rejection, "error": error,
        "episode": relative(episode),
    }
    write_new(output / "result.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2400)
    parser.add_argument("--cup", default="task_cup")
    parser.add_argument("--slot", default="slot_0")
    parser.add_argument("--saved-initial", type=Path, default=None)
    parser.add_argument("--suite", type=Path, default=None)
    parser.add_argument("--case", default=None)
    args = parser.parse_args(argv)
    result = run(args.output.resolve(), args.seed, args.cup, args.slot,
                 args.suite.resolve() if args.suite else None, args.case,
                 args.saved_initial.resolve() if args.saved_initial else None)
    print(json.dumps(result, ensure_ascii=False, indent=1)[:800])
    return 0 if result["slot_success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
