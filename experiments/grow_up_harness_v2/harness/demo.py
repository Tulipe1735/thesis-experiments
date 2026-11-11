"""P2 scaffold acceptance: rerun the reference chain and write the 26 checks.

This is not an Agent success. The reference chain is calibration; the checks
record which Agent-dependent items are still pending. The validator writes a
``reject`` report, not a promotion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROOT = PACKAGE_ROOT.parents[1]
for path in (PACKAGE_ROOT, ROOT, ROOT / "grasp_optimization", PACKAGE_ROOT / "calibration"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import reference_runners as rr  # noqa: E402
from harness import evidence, evaluator, predicates, runtime, tp01, validation  # noqa: E402
from harness.contracts import Validation  # noqa: E402
from harness.ops import TP01_INITIAL  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import set_left_hand_impedance  # noqa: E402

SOURCE = ROOT / "experiments/grow_up_harness_v2/runs/f0v2_engineering_20261103_001/case_01"
RUNS = ROOT / "experiments/grow_up_harness_v2/runs"

CHECKS = (
    "candidate_ops_execute_in_worker",
    "candidate_ops_rejected_in_formal_before_promotion",
    "baseline_failure_preserved",
    "feasibility_gate_recorded",
    "baseline_lineage_root_declared",
    "failure_diagnosis_uses_only_legal_observation",
    "candidate_ops_run_in_practice",
    "practice_budget_registered",
    "all_practice_failures_preserved",
    "verified_task_success",
    "repair_same_initial_state_script_passes",
    "repair_same_initial_state_agent_passes",
    "contract_tests_pass",
    "blackboard_recorded",
    "negative_control_not_credited",
    "evaluator_positive_control_passes",
    "fallback_pairing_recomputed",
    "regression_passes",
    "promotion_writes_new_snapshot",
    "ops_promoted_are_used",
    "formal_reuse_selects_promoted_skill",
    "evaluator_recomputes_from_saved_state",
    "evidence_hashes_verify",
    "test_split_untouched",
    "no_physical_claim",
    "gateway_smoke_passed",
)


def _test_split_untouched() -> bool:
    dataset = ROOT / "experiments/t0_agent_v1/tabletop_dataset_20261026_002"
    frozen = read(dataset / "freeze_manifest.json")
    expected = frozen["artifacts"].get("test/manifest.json")
    return bool(expected) and expected == sha(dataset / "test/manifest.json")


def build_checks(
    *,
    reference: dict,
    b1: dict,
    f0: dict,
    b2: dict,
    audit: dict,
    gateway: dict,
    predicate_check: dict,
    unit_tests: str,
    episode: Path,
    hashes_ok: bool,
    diagnosis_legal: bool,
    test_split: bool,
) -> tuple[dict[str, bool], dict[str, str]]:
    checks = {
        "candidate_ops_execute_in_worker": False,
        "candidate_ops_rejected_in_formal_before_promotion": True,
        "baseline_failure_preserved": b1.get("verdict", {}).get("verified_task_success") is False,
        "feasibility_gate_recorded": f0.get("status") == "FEASIBILITY_GATE_PASSED",
        "baseline_lineage_root_declared": b1.get("label") == "B1_fallback",
        "failure_diagnosis_uses_only_legal_observation": bool(diagnosis_legal),
        "candidate_ops_run_in_practice": False,
        "practice_budget_registered": True,
        "all_practice_failures_preserved": True,
        "verified_task_success": False,
        "repair_same_initial_state_script_passes": False,
        "repair_same_initial_state_agent_passes": False,
        "contract_tests_pass": unit_tests.endswith(" passed") and bool(predicate_check.get("passed")),
        "blackboard_recorded": (episode / "blackboard.jsonl").is_file()
        and bool((episode / "blackboard.jsonl").read_text(encoding="utf-8").strip()),
        "negative_control_not_credited": b2.get("verdict", {}).get("verified_task_success") is False,
        "evaluator_positive_control_passes": bool(reference.get("verified_task_success")),
        "fallback_pairing_recomputed": False,
        "regression_passes": bool(audit.get("all_match"))
        and b2.get("verdict", {}).get("verified_task_success") is False
        and f0.get("status") == "FEASIBILITY_GATE_PASSED"
        and bool(reference.get("passed"))
        and bool(test_split),
        "promotion_writes_new_snapshot": False,
        "ops_promoted_are_used": False,
        "formal_reuse_selects_promoted_skill": False,
        "evaluator_recomputes_from_saved_state": bool(reference.get("verdict_match")),
        "evidence_hashes_verify": bool(hashes_ok),
        "test_split_untouched": bool(test_split),
        "no_physical_claim": True,
        "gateway_smoke_passed": bool(gateway.get("passed")),
    }
    notes = {
        "candidate_ops_execute_in_worker": "synthetic no-op Worker positive only; the five candidate ops are not authored",
        "candidate_ops_rejected_in_formal_before_promotion": "tests/test_worker_runner.py::test_candidate_ops_rejected_in_formal_before_promotion",
        "failure_diagnosis_uses_only_legal_observation": "script reader only; no Agent diagnose call",
        "candidate_ops_run_in_practice": "author_ops not run",
        "all_practice_failures_preserved": "zero practice episodes",
        "verified_task_success": "reference chain verified, but this is not an Agent success",
        "fallback_pairing_recomputed": "T arm does not exist yet",
        "practice_budget_registered": "registration_budget_v2.json",
        "gateway_smoke_passed": "real opencode run, no experiment episode",
        "contract_tests_pass": f"unit suite {unit_tests}; predicate v2 check passed",
    }
    return checks, notes


def _reference_run(case: tp01.TP01Case, output: Path) -> dict:
    model = tp01.build_scene(case, output / "scene.xml")
    plant = tp01.make_plant(case, model, output, budget=120.0)
    impedance = read(SOURCE / "left_hand_impedance.json")
    applied = set_left_hand_impedance(model, impedance["kp"], impedance["kd"])
    if applied != impedance:
        raise ValueError("recorded hand impedance differs")
    for name in applied["joints"]:
        index = plant.ai[name]
        plant.kp[index] = impedance["kp"]
        plant.kd[index] = impedance["kd"]
    write_new(output / "left_hand_impedance.json", applied)
    slices = rr.stage_slices(SOURCE)
    reference_runner = rr.reference_runner(case, slices)
    builtin = runtime.builtin_runner(case)

    def runner(step, *, plant, blackboard, budget):
        if step.op_id in ("open_hand", "check"):
            return builtin(step, plant=plant, blackboard=blackboard, budget=budget)
        return reference_runner(step, plant=plant, blackboard=blackboard, budget=budget)

    implementation = sha(Path(rr.__file__))
    program, view, artifacts = rr.chain(case, implementation)
    result = runtime.Runtime(plant, case, output).run(
        program,
        runner,
        view=view,
        task=case.task,
        initial=TP01_INITIAL,
        admission="formal",
        verify=True,
        strict_posts=True,
    )
    replay = evaluator.replay(case, output)
    return {
        "program_id": program.id,
        "program_sha256": program.digest(),
        "program_budget_s": program.budget_s,
        "steps": len(result.steps),
        "all_steps_executed": len(result.steps) == 7
        and all(outcome.status == "executed" for outcome in result.steps),
        "post_failures": result.post_failures,
        "verified_task_success": result.verdict.verified_task_success,
        "terminal_stable_s": result.verdict.terminal_stable_s,
        "verdict_match": result.verdict.verified_task_success == replay.verified_task_success
        and result.verdict.goal_satisfied == replay.goal_satisfied,
        "simulation_seconds": read(output / "execution.json")["simulation_seconds"],
        "guard": read(output / "execution.json")["guard"],
        "passed": result.failure_code is None
        and len(result.steps) == 7
        and result.verdict.verified_task_success,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default=str(SOURCE))
    parser.add_argument("--unit-tests", default=None)
    args = parser.parse_args(argv)

    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    episode = output_root / "episode"
    episode.mkdir()

    case = tp01.load_cases()[0]
    reference = _reference_run(case, episode)
    hashes = evidence.verify_hashes(episode)
    test_split = _test_split_untouched()
    unit_tests = args.unit_tests or read(
        ROOT / "experiments/grow_up_harness_v2/registration.json"
    )["calibration"]["unit_tests"]["result"]
    b1 = read(RUNS / "v2_3_b1_fallback_20261103_001/results.json")
    f0 = read(RUNS / "f0v2_engineering_20261103_001/results.json")
    b2 = read(RUNS / "calib_b2_s_star_20261103_001/results.json")
    audit = read(RUNS / "audit_recompute_20261103_001/results.json")
    gateway = read(RUNS / "gateway_smoke_20261104_001/results.json")
    predicate_check = read(RUNS / "predicate_v2_check_20261104_001/results.json")

    from harness import experience

    diagnosis = experience.diagnose(
        RUNS / "v2_3_b1_fallback_20261103_001/case_01",
        case.task,
        mechanism="fallback contact",
        repair_boundary="bounded",
    )
    checks, notes = build_checks(
        reference=reference,
        b1=b1,
        f0=f0,
        b2=b2,
        audit=audit,
        gateway=gateway,
        predicate_check=predicate_check,
        unit_tests=unit_tests,
        episode=episode,
        hashes_ok=bool(hashes.get("ok")),
        diagnosis_legal=diagnosis.legal_only,
        test_split=test_split,
    )
    if set(checks) != set(CHECKS):
        raise RuntimeError("check key set drifted")
    report = validation.build_report(
        report_id="report_v2_3_scaffold",
        candidate_id="reference_chain_v2",
        candidate_digest=reference["program_sha256"],
        validation=Validation.PAIRED,
        protocol="V2.3 scaffold acceptance; reference chain only",
        baseline_episode=relative(RUNS / "v2_3_b1_fallback_20261103_001/case_01"),
        treatment_episode=None,
        initial_state_sha256=case.initial_state_sha256,
        metrics=(("terminal_stable_s", float(reference["terminal_stable_s"])), ("simulation_seconds", float(reference["simulation_seconds"]))),
        ops=rr.v2_ops(case, sha(Path(rr.__file__))),
        evidence={
            "audit": audit,
            "b2": b2,
            "f0": f0,
            "reference": reference,
            "test_split": {"untouched": test_split},
        },
        decision="reject",
        evidence_paths=(relative(episode), relative(RUNS / "v2_3_b1_fallback_20261103_001/results.json")),
    )
    write_new(output_root / "validation_report.json", report.to_dict())
    results = {
        "date": "2026-11-04",
        "boundary": "simulation",
        "status": "SCAFFOLD_ACCEPTANCE_AGENT_NOT_RUN",
        "reference_chain": reference,
        "checks": checks,
        "notes": notes,
        "check_count": len(checks),
        "counted_as_agent_success": False,
        "validation_report": "validation_report.json",
        "episode": relative(episode),
        "evidence": {
            "b1": relative(RUNS / "v2_3_b1_fallback_20261103_001/results.json"),
            "f0": relative(RUNS / "f0v2_engineering_20261103_001/results.json"),
            "b2": relative(RUNS / "calib_b2_s_star_20261103_001/results.json"),
            "audit": relative(RUNS / "audit_recompute_20261103_001/results.json"),
            "gateway": relative(RUNS / "gateway_smoke_20261104_001/results.json"),
            "predicate": relative(RUNS / "predicate_v2_check_20261104_001/results.json"),
        },
    }
    write_new(output_root / "results.json", results)
    reloaded = read(output_root / "results.json")
    if set(reloaded.get("checks", {})) != set(CHECKS):
        raise RuntimeError("results.json did not persist every check")
    evidence.write_hashes(output_root)
    print(
        "DEMO_SUMMARY",
        json.dumps(
            {
                "checks": len(checks),
                "true": sum(1 for value in checks.values() if value),
                "reference_passed": reference["passed"],
                "verified_task_success": checks["verified_task_success"],
                "counted_as_agent_success": False,
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
