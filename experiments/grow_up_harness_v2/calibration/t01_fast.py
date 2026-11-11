"""Fast path: run the artifact's code projection, with no model in the loop.

The YAML artifact is the only source. This entry refuses when the generated
projections are stale, when the record does not cover the request, or when any
bound hash (plant, evaluator, saved initial state) differs. It never falls back
to the slow path silently.
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
from harness import artifact as artifact_mod  # noqa: E402
from experiments.cordis_t01.worker import SavedInitialRobot  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.runtime import CountedPort  # noqa: E402
from experiments.t0_agent_v1.tray_verify import verify  # noqa: E402

ARTIFACT = PACKAGE / "artifacts/t01_cup_to_tray.yaml"
SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_20261028_001"
MAX_CORRECTIONS = 6


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project(record: artifact_mod.Artifact) -> dict:
    """Verify the generated projections are current, then import the program."""
    manifest_path = ROOT / record.projections.code.path
    manifest = json.loads((manifest_path.parent / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    if manifest["artifact"]["digest"] != artifact_mod.digest(record):
        problems.append("generated projections are stale: recompile the artifact")
    for path, digest in manifest["generated"].items():
        if not (ROOT / path).is_file():
            problems.append(f"missing projection: {path}")
        elif _sha(ROOT / path) != digest:
            problems.append(f"projection changed on disk: {path}")
    if problems:
        return {"route": "refuse", "reasons": problems, "model_requests": 0}
    spec = importlib.util.spec_from_file_location("generated_program", manifest_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {"route": "fast", "program": module, "manifest": manifest, "reasons": []}


def bind(record: artifact_mod.Artifact, case, registration) -> list[str]:
    reasons = []
    if record.scope.task != "T01":
        reasons.append(f"task outside scope: {record.scope.task}")
    missing = {case["cup_asset"], case["tray_asset"]} - set(record.scope.assets)
    if missing:
        reasons.append("assets outside scope: " + ", ".join(sorted(missing)))
    saved = ROOT / case["initial_source"] if case.get("initial_source") else None
    known = {state.sha256 for state in record.scope.initial_states}
    if saved is None or _sha(saved) not in known:
        reasons.append("initial state is not one the record was validated on")
    model = registration["models"][case["model_key"]]
    if model["sha256"] != record.binding.plant_sha256:
        reasons.append("plant differs from the bound plant")
    if _sha(ROOT / "experiments/t0_agent_v1/tray_verify.py") != record.binding.evaluator_sha256:
        reasons.append("evaluator differs from the bound evaluator")
    return reasons


def run(output: Path, case_id: str, suite: Path = SUITE) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    registration = read(suite / "registration.json")
    case = next(row for row in registration["cases"] if row["id"] == case_id)
    record = artifact_mod.load(ARTIFACT)
    projection = project(record)
    reasons = projection["reasons"] + bind(record, case, registration)
    write_new(output / "routing.json", {
        "artifact": relative(ARTIFACT), "artifact_digest": artifact_mod.digest(record),
        "case": case_id, "route": "refuse" if reasons else "fast", "reasons": reasons,
        "model_requests": 0,
    })
    if reasons:
        result = {"route": "refuse", "case": case_id, "reasons": reasons, "model_requests": 0}
        write_new(output / "result.json", result)
        return result

    program = projection["program"]
    if case.get("initial_source") is None:
        raise ValueError("fast path needs a saved initial state in scope")
    episode = output / "episode"
    episode.mkdir()
    write_new(episode / "instance.json", case["instance"])
    model_ref = registration["models"][case["model_key"]]
    robot = SavedInitialRobot(episode, case["instance"],
                              budget=registration["simulation_budget_s"],
                              scene_path=ROOT / model_ref["path"],
                              initial_state=ROOT / case["initial_source"])
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
    except Exception as exc:  # keep the failure; never invent a result
        error = {"type": type(exc).__name__, "message": str(exc)[:600], "phase": phase}
    wall = time.monotonic() - started
    environment = robot.finish()
    verdict = verify(episode, execution_error=error)
    result = {
        "route": "fast", "case": case_id,
        "artifact": {"id": record.id, "version": record.version,
                     "digest": artifact_mod.digest(record)},
        "verified_success": verdict["verified_success"],
        "terminal_stable_s": verdict["terminal_simultaneous_stable_s"],
        "simulation_seconds": environment["simulation_seconds"],
        "wall_seconds": wall, "low_level_command_calls": port.command_calls,
        "corrections": corrections, "rejected_command": rejection, "error": error,
        "model_requests": 0,
        "episode": relative(episode),
        "trajectory_sha256": sha(episode / "trajectory.npz"),
        "verdict_sha256": sha(episode / "independent_verification.json"),
    }
    write_new(output / "result.json", result)
    return result


def main(argv=None) -> int:
    global ARTIFACT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", default=pilot.CASE_ID)
    parser.add_argument("--suite", type=Path, default=SUITE)
    parser.add_argument("--artifact", type=Path, default=ARTIFACT)
    args = parser.parse_args(argv)
    ARTIFACT = args.artifact.resolve()
    result = run(args.output.resolve(), args.case, args.suite.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=1)[:900])
    return 0 if result.get("verified_success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
