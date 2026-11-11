"""Qualify the T01 tray evaluator on one saved development initial state."""

import argparse
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from experiments.cordis_t01.variation_worker import Session
from experiments.t0_agent_v1.common import read, relative, sha, write_new
from experiments.t0_agent_v1.tray_verify import verify


SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_20261028_001"
CASE_ID = "control_2500"


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    registration = read(SUITE / "registration.json")
    case = next(row for row in registration["cases"] if row["id"] == CASE_ID)
    initial_sha = sha(ROOT / case["initial_source"])
    evaluator = ROOT / "experiments/t0_agent_v1/tray_verify.py"
    write_new(output / "registration.json", {
        "task": "T01", "split": "known_development_control", "case": case,
        "purpose": "positive and negative evaluator calibration; no Agent or ablation results",
        "source_registration_sha256": sha(SUITE / "registration.json"),
        "actual_initial_state_sha256": initial_sha,
        "simulation_budget_s": registration["simulation_budget_s"],
        "model": registration["models"][case["model_key"]],
        "evaluator_sha256": sha(evaluator), "driver_sha256": sha(Path(__file__)),
        "model_requests": 0, "max_episodes": 2,
        "order": ["B2_wait", "R_engineering"],
        "stop": "B2 must physically fail without execution error; R must pass on same initial state",
    })
    rows = []
    for arm in ("B2_wait", "R_engineering"):
        folder = output / arm
        folder.mkdir()
        row = {"arm": arm, "episode": relative(folder / "episode")}
        session = None
        try:
            session = Session(folder, SUITE, CASE_ID)
            if arm == "B2_wait":
                session.initialize()
                session.robot.advance(2.0, "negative_control_wait")
                session.robot.finish()
                session.closed = True
                verdict = verify(session.folder)
            else:
                for tool in registration["expected_program"]:
                    session.call(tool, {})
                verdict = read(session.folder / "independent_verification.json")
            row.update(
                verified_success=verdict["verified_success"],
                valid_initial=verdict["initial_valid"],
                stable_s=verdict["terminal_simultaneous_stable_s"],
                actual_initial_state_sha256=sha(session.folder / "initial_state.npz"),
                trajectory_sha256=sha(session.folder / "trajectory.npz"),
                verdict_sha256=sha(session.folder / "independent_verification.json"),
                simulation_seconds=read(session.folder / "environment_result.json")["simulation_seconds"],
                execution_error=verdict["execution_error"],
                protection=verdict["protection"],
            )
            row["passed"] = (
                row["verified_success"] is (arm == "R_engineering")
                and row["valid_initial"] and row["actual_initial_state_sha256"] == initial_sha
                and not row["execution_error"] and not row["protection"]
                and session.unchanged()
            )
        except Exception as error:
            row.update(passed=False, harness_error=f"{type(error).__name__}: {error}")
            write_new(folder / "error.json", {"traceback": traceback.format_exc()})
            if session and session.robot and not session.closed:
                session.finalize()
        write_new(folder / "control.json", row)
        rows.append(row)
        if not row["passed"]:
            break
    result = {"passed": len(rows) == 2 and all(row["passed"] for row in rows),
              "controls": rows, "model_requests": 0}
    write_new(output / "results.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(0 if run(parser.parse_args().output.resolve())["passed"] else 1)
