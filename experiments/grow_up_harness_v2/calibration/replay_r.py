"""V2.2 first acceptance: replay R's recorded action program.

R is the F0 v2 positive control, the engineering reference episode on S*. This
script re-executes its recorded requests through a fresh plant with the new
runtime, applies the recorded hand impedance after plant construction, writes a
self-contained episode, and recomputes the verdict with the harness evaluator.

A success is calibration, not an agent achievement: the recorded program came
from the engineering reference, not from the Agent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "grasp_optimization") not in sys.path:
    sys.path.insert(0, str(ROOT / "grasp_optimization"))

from experiments.grow_up_harness_v2.harness import evaluator, runtime, tp01  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402

SOURCE = ROOT / "experiments/grow_up_harness_v2/runs/f0v2_engineering_20261103_001/case_01"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default=str(SOURCE))
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    output = output_root / "case_01"
    output.mkdir()

    case = tp01.load_cases()[0]
    actions = read(source / "actions.json")
    impedance = read(source / "left_hand_impedance.json")
    result = runtime.replay_recorded(
        case,
        actions,
        output,
        impedance=impedance,
        budget_s=120.0,
        source=relative(source),
    )
    saved = read(source / "independent_verification.json")
    replayed_pose = read(output / "initial_pose.json")
    source_pose = read(source / "initial_pose.json")
    initial_pose_match = replayed_pose["qpos"] == source_pose["qpos"]
    summary = {
        "date": "2026-11-03",
        "boundary": "simulation",
        "kind": "V2.2_recorded_program_replay",
        "source": relative(source),
        "source_actions_sha256": sha(source / "actions.json"),
        "source_verdict_sha256": sha(source / "independent_verification.json"),
        "runtime_sha256": sha(ROOT / "experiments/grow_up_harness_v2/harness/runtime.py"),
        "evaluator_sha256": sha(ROOT / "experiments/grow_up_harness_v2/harness/evaluator.py"),
        "tp01_sha256": sha(ROOT / "experiments/grow_up_harness_v2/harness/tp01.py"),
        "script_sha256": sha(Path(__file__)),
        "episode": relative(output),
        "requests": len(actions),
        "executed": read(output / "replay.json")["executed"],
        "initial_pose_match": initial_pose_match,
        "replay_verified_task_success": result.verdict.verified_task_success,
        "saved_verified_task_success": saved["verified_task_success"],
        "replay_goal_satisfied": result.verdict.goal_satisfied,
        "saved_goal_satisfied": saved["goal_satisfied"],
        "terminal_stable_s": result.verdict.terminal_stable_s,
        "simulation_seconds": read(output / "execution.json")["simulation_seconds"],
        "guard": read(output / "execution.json")["guard"],
        "evaluator_version": result.verdict.evaluator_version,
        "verdict_match": bool(
            result.verdict.verified_task_success == saved["verified_task_success"]
            and result.verdict.goal_satisfied == saved["goal_satisfied"]
        ),
        "counted_as_agent_success": False,
    }
    summary["passed"] = bool(
        summary["executed"] == summary["requests"]
        and summary["initial_pose_match"]
        and summary["verdict_match"]
        and summary["guard"] is None
    )
    write_new(output_root / "results.json", summary)
    print("REPLAY_SUMMARY", json.dumps({k: summary[k] for k in (
        "requests", "executed", "initial_pose_match", "verdict_match", "passed")}), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
