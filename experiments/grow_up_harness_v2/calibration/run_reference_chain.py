"""Run the seven-step chain with the five reference runners.

This is the V2.3 scaffold: the chain executes through ``Runtime.run`` with the
registered V2.3 op budgets, the runtime enforces total and per-step budgets, and
each step's postcondition is recorded. ``strict_posts`` is off so one run exposes
every predicate mismatch instead of stopping at the first one. The independent
evaluator still decides the task verdict; successes here are calibration.
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
if str(ROOT / "experiments/grow_up_harness_v2") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_runners as rr  # noqa: E402
from harness import predicates, tp01  # noqa: E402
from harness.ops import TP01_INITIAL  # noqa: E402
from harness.runtime import Runtime, builtin_runner  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import set_left_hand_impedance  # noqa: E402

SOURCE = ROOT / "experiments/grow_up_harness_v2/runs/f0v2_engineering_20261103_001/case_01"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default=str(SOURCE))
    parser.add_argument("--strict-posts", action="store_true")
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    output = output_root / "case_01"
    output.mkdir()

    case = tp01.load_cases()[0]
    model = tp01.build_scene(case, output / "scene.xml")
    plant = tp01.make_plant(case, model, output, budget=120.0)
    impedance = read(source / "left_hand_impedance.json")
    applied = set_left_hand_impedance(model, impedance["kp"], impedance["kd"])
    if applied != impedance:
        raise ValueError("recorded hand impedance differs")
    for name in applied["joints"]:
        index = plant.ai[name]
        plant.kp[index] = impedance["kp"]
        plant.kd[index] = impedance["kd"]
    write_new(output / "left_hand_impedance.json", applied)

    slices = rr.stage_slices(source)
    reference = rr.reference_runner(case, slices)
    builtin = builtin_runner(case)

    def runner(step, *, plant, blackboard, budget):
        if step.op_id in ("open_hand", "check"):
            return builtin(step, plant=plant, blackboard=blackboard, budget=budget)
        return reference(step, plant=plant, blackboard=blackboard, budget=budget)

    implementation_sha = sha(Path(__file__).resolve().parent / "reference_runners.py")
    program, view, artifacts = rr.chain(case, implementation_sha)
    result = Runtime(plant, case, output).run(
        program,
        runner,
        view=view,
        task=case.task,
        initial=TP01_INITIAL,
        admission="formal",
        verify=True,
        strict_posts=args.strict_posts,
    )
    saved = read(source / "independent_verification.json")
    summary = {
        "date": "2026-11-03",
        "boundary": "simulation",
        "kind": "V2.3_reference_chain",
        "source": relative(source),
        "episode": relative(output),
        "program": program.id,
        "program_sha256": program.digest(),
        "program_budget_s": program.budget_s,
        "budgets_s": rr.BUDGETS,
        "strict_posts": args.strict_posts,
        "predicate_version": predicates.VERSION,
        "palm_constants": {
            "horizontal_m": predicates.THRESHOLDS["palm_horizontal_m"],
            "vertical_m": predicates.THRESHOLDS["palm_vertical_m"],
        },
        "implementation_sha256": implementation_sha,
        "slice_requests": {name: len(records) for name, records in slices.items()},
        "steps": [
            dict(
                index=index,
                op_id=outcome.op_id,
                status=outcome.status,
                post_ok=outcome.detail.get("post_ok"),
                post_code=outcome.detail.get("post_code"),
                actions=outcome.actions,
                sim_time=outcome.sim_time,
            )
            for index, outcome in enumerate(result.steps)
        ],
        "post_failures": result.post_failures,
        "failure_code": result.failure_code,
        "replans": result.replans,
        "verified_task_success": result.verdict.verified_task_success,
        "saved_verified_task_success": saved["verified_task_success"],
        "goal_satisfied": result.verdict.goal_satisfied,
        "terminal_stable_s": result.verdict.terminal_stable_s,
        "simulation_seconds": read(output / "execution.json")["simulation_seconds"],
        "guard": read(output / "execution.json")["guard"],
        "evaluator_version": result.verdict.evaluator_version,
        "counted_as_agent_success": False,
    }
    summary["all_steps_executed"] = len(result.steps) == 7 and all(
        outcome.status == "executed" for outcome in result.steps
    )
    summary["verdict_match"] = bool(
        result.verdict.verified_task_success == saved["verified_task_success"]
        and result.verdict.goal_satisfied == saved["goal_satisfied"]
    )
    summary["passed"] = bool(
        summary["all_steps_executed"]
        and summary["verdict_match"]
        and result.failure_code is None
    )
    write_new(output_root / "results.json", summary)
    print(
        "CHAIN_SUMMARY",
        json.dumps(
            {
                "steps": len(result.steps),
                "all_executed": summary["all_steps_executed"],
                "post_failures": [item["predicate"] for item in result.post_failures],
                "verified": summary["verified_task_success"],
                "verdict_match": summary["verdict_match"],
                "passed": summary["passed"],
            }
        ),
        flush=True,
    )
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
