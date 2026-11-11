"""Run one artifact code projection on a registered generated T01 instance.

The saved-state entry (`t01_fast.py`) can only bind instances with an
operator-saved `initial_state.npz`. The variation suite also contains
generated instances whose state is built from a frozen instance spec. This
entry runs the same projection and phases there and records the instance hash.
It is development evidence, not a validated-scope binding.
"""

import argparse
import hashlib
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
import t01_fast  # noqa: E402
from experiments.cordis_t01.worker import SavedInitialRobot  # noqa: E402,F401
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot  # noqa: E402
from experiments.t0_agent_v1.tray_verify import verify  # noqa: E402

SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_20261028_001"
MAX_CORRECTIONS = 6


def load_case(case_id, suite):
    registration = read(suite / "registration.json")
    case = next((row for row in registration["cases"] if row["id"] == case_id), None)
    if case is None:
        raise ValueError(f"unknown case: {case_id}")
    if case.get("initial_source"):
        raise ValueError("this entry is for generated instances; use t01_fast.py")
    return registration, case


def run(output: Path, artifact_path: Path, case_id: str, suite: Path = SUITE) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    registration, case = load_case(case_id, suite)
    record = t01_fast.artifact_mod.load(artifact_path)
    projection = t01_fast.project(record)
    reasons = list(projection["reasons"])
    if record.scope.task != "T01":
        reasons.append(f"task outside scope: {record.scope.task}")
    missing = {case["cup_asset"], case["tray_asset"]} - set(record.scope.assets)
    if missing:
        reasons.append("assets outside scope: " + ", ".join(sorted(missing)))
    model_ref = registration["models"][case["model_key"]]
    if model_ref["sha256"] != record.binding.plant_sha256:
        reasons.append("plant differs from the bound plant")
    evaluator = ROOT / "experiments/t0_agent_v1/tray_verify.py"
    if sha(evaluator) != record.binding.evaluator_sha256:
        reasons.append("evaluator differs from the bound evaluator")
    instance_bytes = json.dumps(case["instance"], sort_keys=True, separators=(",", ":")).encode()
    write_new(output / "routing.json", {
        "artifact": relative(artifact_path), "artifact_digest": t01_fast.artifact_mod.digest(record),
        "case": case_id, "instance_sha256": hashlib.sha256(instance_bytes).hexdigest(),
        "scope_binding": "instance_spec_not_saved_state",
        "route": "refuse" if reasons else "development_generated_case",
        "reasons": reasons, "model_requests": 0,
    })
    if reasons:
        result = {"route": "refuse", "case": case_id, "reasons": reasons, "model_requests": 0}
        write_new(output / "result.json", result)
        return result

    program = projection["program"]
    episode = output / "episode"
    episode.mkdir()
    write_new(episode / "instance.json", case["instance"])
    robot = PilotRobot(episode, case["instance"], budget=registration["simulation_budget_s"],
                       scene_path=ROOT / model_ref["path"])
    port = CountedPort(robot)
    session = {}
    rejection = None
    corrections = 0
    error = None
    phase = "plan"
    started = time.monotonic()
    try:
        robot.advance(.75, "initial_settling")
        state = pilot.observe(port, robot)
        params = program.grasp_parameters(state)

        def run_batch(batch, phase_name):
            nonlocal rejection
            for command in batch:
                if command["op"] == "finish":
                    return
                try:
                    pilot.execute(port, command, robot, state.get("tray_floor_center_m"), session)
                except ValueError as exc:
                    rejection = {"phase": phase_name, "command": command, "reason": str(exc)}
                    return

        run_batch(program.plan(state), "plan")
        if rejection is None:
            phase = "lift"
            run_batch(program.lift(pilot.observe(port, robot), params), "lift")
        if rejection is None:
            phase = "correct"
            while corrections < MAX_CORRECTIONS:
                fix = program.correct(pilot.observe(port, robot), params)
                if not fix:
                    break
                corrections += 1
                run_batch(fix, "correct")
                if rejection is not None:
                    break
        if rejection is None:
            phase = "release"
            run_batch(program.release(pilot.observe(port, robot), params), "release")
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:600], "phase": phase}
    wall = time.monotonic() - started
    environment = robot.finish()
    verdict = verify(episode, execution_error=error)
    final = verdict["final"]["cups"]["task_cup"]
    result = {
        "route": "development_generated_case", "case": case_id, "group": case["group"],
        "artifact": {"id": record.id, "version": record.version,
                     "digest": t01_fast.artifact_mod.digest(record)},
        "program_sha256": sha(ROOT / record.projections.code.path),
        "instance_sha256": hashlib.sha256(instance_bytes).hexdigest(),
        "verified_success": verdict["verified_success"],
        "terminal_stable_s": verdict["terminal_simultaneous_stable_s"],
        "footprint_margin_m": final["footprint_margin_m"],
        "cup_tilt_deg": final["cup_tilt_deg"],
        "simulation_seconds": environment["simulation_seconds"],
        "wall_seconds": wall, "low_level_command_calls": port.command_calls,
        "corrections": corrections, "rejected_command": rejection, "error": error,
        "model_requests": 0, "episode": relative(episode),
        "initial_state_sha256": sha(episode / "initial_state.npz"),
        "trajectory_sha256": sha(episode / "trajectory.npz"),
        "verdict_sha256": sha(episode / "independent_verification.json"),
    }
    write_new(output / "result.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--suite", type=Path, default=SUITE)
    args = parser.parse_args(argv)
    result = run(args.output.resolve(), args.artifact.resolve(), args.case, args.suite.resolve())
    print(json.dumps({key: result.get(key) for key in
                      ("case", "verified_success", "terminal_stable_s", "rejected_command")},
                     ensure_ascii=False, indent=1)[:900])
    return 0 if result.get("verified_success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
