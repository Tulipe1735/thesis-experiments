"""Run the distilled T01 program on the generated variation cases.

The generator is the registered T01 variation suite: each non-control case is
a sampled initial state (position, orientation, asset, joint variation) that
the program never saw. Zero model requests; same plant, commands and evaluator
as the agent episodes.
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
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot  # noqa: E402
from experiments.t0_agent_v1.tray_verify import verify  # noqa: E402

SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_20261028_001"
PROGRAM = PACKAGE / "artifacts/generated/t01_cup_to_tray/program.py"
MAX_CORRECTIONS = 6


def load_program():
    spec = importlib.util.spec_from_file_location("t01_program", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_case(case, registration, program, output):
    output.mkdir(parents=True, exist_ok=True)
    episode = output / "episode"
    episode.mkdir()
    instance = case["instance"]
    model = registration["models"][case["model_key"]]
    budget = registration["simulation_budget_s"]
    write_new(episode / "instance.json", instance)
    kwargs = dict(scene_path=ROOT / model["path"], budget=budget)
    if case.get("initial_source"):
        robot = SavedInitialRobot(episode, instance, initial_state=ROOT / case["initial_source"], **kwargs)
    else:
        robot = PilotRobot(episode, instance, **kwargs)
    port = CountedPort(robot)
    session = {}
    started = time.monotonic()
    error = None
    rejection = None
    corrections = 0
    phase = "plan"
    try:
        robot.advance(.75, "initial_settling")
        state = pilot.observe(port, robot)
        commands = program.plan(state)
        params = program.grasp_parameters(state)

        def run_batch(batch):
            nonlocal rejection
            for index, command in enumerate(batch):
                if command["op"] == "finish":
                    return
                try:
                    pilot.execute(port, command, robot, state.get("tray_floor_center_m"), session)
                except ValueError as exc:
                    rejection = {"phase": phase, "index": index, "command": command,
                                 "reason": str(exc)}
                    return

        run_batch(commands)
        if rejection is None:
            phase = "lift"
            state = pilot.observe(port, robot)
            lift_commands = program.lift(state, params)
            commands = commands + lift_commands
            run_batch(lift_commands)
        if rejection is None:
            phase = "correct"
            while corrections < MAX_CORRECTIONS:
                state = pilot.observe(port, robot)
                fix = program.correct(state, params)
                if not fix:
                    break
                corrections += 1
                run_batch(fix)
                if rejection is not None:
                    break
        if rejection is None:
            phase = "release"
            state = pilot.observe(port, robot)
            run_batch(program.release(state, params))
    except Exception as exc:  # keep the failure; never invent a result
        error = {"type": type(exc).__name__, "message": str(exc)[:600], "phase": phase}
    wall = time.monotonic() - started
    environment = robot.finish()
    verdict = verify(episode, execution_error=error)
    cup = verdict["final"]["cups"]["task_cup"]
    return {
        "case": case["id"], "group": case.get("group"), "seed": instance.get("seed"),
        "verified_success": verdict["verified_success"],
        "footprint_margin_m": round(cup["footprint_margin_m"], 5),
        "stable_s": round(verdict["terminal_simultaneous_stable_s"], 3),
        "cup_tilt_deg": round(cup["cup_tilt_deg"], 2),
        "commands": port.command_calls, "corrections": corrections,
        "simulation_s": round(environment["simulation_seconds"], 2),
        "wall_s": round(wall, 1), "phase": phase,
        "rejection": rejection, "error": error,
        "episode": relative(episode),
        "trajectory_sha256": sha(episode / "trajectory.npz"),
        "verdict_sha256": sha(episode / "independent_verification.json"),
    }


def run(output: Path, case_ids=None, suite: Path = SUITE) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    registration = read(suite / "registration.json")
    program = load_program()
    cases = [c for c in registration["cases"] if not case_ids or c["id"] in case_ids]
    write_new(output / "registration.json", {
        "date": "2026-11-05", "boundary": "simulation", "kind": "program_transfer_on_generated_cases",
        "suite": relative(suite), "suite_sha256": sha(suite / "registration.json"),
        "cases": [c["id"] for c in cases],
        "program_sha256": sha(PROGRAM),
        "evaluator_sha256": sha(ROOT / "experiments/t0_agent_v1/tray_verify.py"),
        "model_requests": 0,
        "note": "Cases without initial_source are sampled by the registered generator and were never used to write the program.",
    })
    rows = []
    for case in cases:
        row = run_case(case, registration, program, output / case["id"])
        rows.append(row)
        success = sum(1 for item in rows if item["verified_success"])
        print(f"{row['case']:20s} ok={row['verified_success']!s:5s} margin={row['footprint_margin_m']:+.4f} "
              f"stable={row['stable_s']:.2f} phase={row['phase']} ({success}/{len(rows)})", flush=True)
    summary = {
        "episodes": len(rows), "successes": sum(1 for r in rows if r["verified_success"]),
        "by_group": {}, "rows": rows,
    }
    for row in rows:
        bucket = summary["by_group"].setdefault(row["group"] or "control", {"episodes": 0, "successes": 0})
        bucket["episodes"] += 1
        bucket["successes"] += int(row["verified_success"])
    write_new(output / "results.json", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", default=None)
    parser.add_argument("--suite", type=Path, default=SUITE)
    args = parser.parse_args(argv)
    summary = run(args.output.resolve(), args.case, args.suite.resolve())
    print(json.dumps({k: summary[k] for k in ("episodes", "successes", "by_group")}, ensure_ascii=False, indent=1))
    return 0 if summary["successes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
