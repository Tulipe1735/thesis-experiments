"""Run the registered T01 program with no model, on the saved control initial state.

This is the acceptance check for a distilled skill: the program module must
reproduce the episode through the same public port, guards and evaluator the
agent used. Zero model requests.
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

import t01_agent_pilot as pilot  # noqa: E402
from experiments.cordis_t01.worker import SavedInitialRobot  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.runtime import CountedPort  # noqa: E402
from experiments.t0_agent_v1.tray_verify import verify  # noqa: E402

PROGRAM = PACKAGE / "artifacts/generated/t01_cup_to_tray/program.py"


def load_program():
    spec = importlib.util.spec_from_file_location("t01_program", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MAX_CORRECTIONS = 6


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    episode = output / "episode"
    episode.mkdir()
    registration = read(pilot.SUITE / "registration.json")
    case = next(row for row in registration["cases"] if row["id"] == pilot.CASE_ID)
    saved = ROOT / case["initial_source"]
    model_ref = registration["models"][case["model_key"]]
    budget = registration["simulation_budget_s"]
    write_new(output / "registration.json", {
        "date": "2026-11-05", "boundary": "simulation", "task": "T01",
        "kind": "program_acceptance_no_model",
        "case": case["id"], "initial_state_sha256": sha(saved),
        "plant_sha256": model_ref["sha256"], "simulation_budget_s": budget,
        "evaluator_sha256": sha(ROOT / "experiments/t0_agent_v1/tray_verify.py"),
        "source_hashes": {relative(p): sha(p) for p in (
            Path(__file__), PROGRAM, Path(pilot.__file__),
            ROOT / "experiments/grow_up_harness_v2/calibration/t01_motion.py")},
        "model_requests": 0,
    })
    write_new(episode / "instance.json", case["instance"])
    robot = SavedInitialRobot(episode, case["instance"], budget=budget,
                              scene_path=ROOT / model_ref["path"], initial_state=saved)
    port = CountedPort(robot)
    session = {}
    started = time.monotonic()
    error = None
    rejection = None
    try:
        robot.advance(.75, "initial_settling")
        program = load_program()
        state = pilot.observe(port, robot)
        commands = program.plan(state)
        params = program.grasp_parameters(state)
        corrections = 0

        def run_batch(batch, phase):
            nonlocal rejection
            for index, command in enumerate(batch):
                if command["op"] == "finish":
                    return
                try:
                    pilot.execute(port, command, robot, state.get("tray_floor_center_m"), session)
                except ValueError as exc:
                    rejection = {"phase": phase, "index": index,
                                 "command": command, "reason": str(exc)}
                    return

        run_batch(commands, "plan")
        if rejection is None:
            state = pilot.observe(port, robot)
            lift_commands = program.lift(state, params)
            commands = commands + lift_commands
            run_batch(lift_commands, "lift")
        if rejection is None:
            while corrections < MAX_CORRECTIONS:
                state = pilot.observe(port, robot)
                fix = program.correct(state, params)
                if not fix:
                    break
                corrections += 1
                run_batch(fix, "correct")
                if rejection is not None:
                    break
        if rejection is None:
            state = pilot.observe(port, robot)
            release_commands = program.release(state, params)
            commands = commands + release_commands
            run_batch(release_commands, "release")
        write_new(output / "corrections.json", {"iterations": corrections})
    except Exception as exc:  # keep the failure; never invent a result
        error = {"type": type(exc).__name__, "message": str(exc)[:800]}
    wall = time.monotonic() - started
    environment = robot.finish()
    verdict = verify(episode, execution_error=error)
    result = {
        "verified_success": verdict["verified_success"],
        "execution_error": error, "rejected_command": rejection,
        "commands": len(commands) + corrections, "corrections": corrections,
        "low_level_command_calls": port.command_calls,
        "simulation_seconds": environment["simulation_seconds"], "wall_seconds": wall,
        "terminal_stable_s": verdict["terminal_simultaneous_stable_s"],
        "protection": verdict["protection"],
        "episode": relative(episode),
        "trajectory_sha256": sha(episode / "trajectory.npz"),
        "verdict_sha256": sha(episode / "independent_verification.json"),
    }
    write_new(output / "result.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(args.output.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["verified_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
