"""Validation for candidate artifacts and the scaffold acceptance.

The validator is an independent entry point: it reads registry artifacts and
episode directories, never the live plant, and it writes a ``ValidationReport``.
Promotion is a registry action after the report, not this module's side effect.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from . import predicates
from .contracts import (
    ContractError,
    Op,
    TaskSpec,
    Validation,
    ValidationReport,
)


def contract_tests(ops: Sequence[Op]) -> tuple[tuple[str, bool], ...]:
    """Structural contract checks for every op and every step predicate."""
    rows: list[tuple[str, bool]] = []
    for op in ops:
        names = [item.name for item in (*op.pre, *op.post)]
        known = all(name in predicates.SPECS for name in names)
        codes = all(isinstance(code, str) and code for code in op.failure_codes)
        rows.append((f"{op.op_id}:scope", bool(op.scope.assets)))
        rows.append((f"{op.op_id}:budget", op.budget_s > 0))
        rows.append((f"{op.op_id}:post", bool(op.post)))
        rows.append((f"{op.op_id}:failure_codes", bool(op.failure_codes) and codes))
        rows.append((f"{op.op_id}:predicate_names", known))
    rows.append(
        (
            "predicates:ten_specs",
            len(predicates.STEP_PREDICATES) == 10
            and all(name in predicates.SPECS and predicates.SPECS[name].definition for name in predicates.STEP_PREDICATES),
        )
    )
    return tuple(rows)


def repair_lineage(
    baseline: Mapping,
    treatment: Mapping,
    initial_state_sha256: str,
    *,
    script_passes: bool,
    agent_passes: bool,
) -> dict:
    same = (
        baseline.get("initial_state_sha256") == treatment.get("initial_state_sha256") == initial_state_sha256
    )
    return {
        "baseline_failure": baseline.get("verified_task_success") is False,
        "treatment_success": treatment.get("verified_task_success") is True,
        "same_initial_state": same,
        "script_passes": bool(script_passes),
        "agent_passes": bool(agent_passes),
    }


def paired(baseline: Mapping, treatment: Mapping) -> dict:
    """Fallback pairing metrics; never a single-factor Skill claim."""
    def metric(row: Mapping, key: str):
        return row.get(key)

    better = (
        (treatment.get("verified_task_success") is True and baseline.get("verified_task_success") is not True)
        or (metric(treatment, "retries") is not None and metric(baseline, "retries") is not None and metric(treatment, "retries") < metric(baseline, "retries"))
        or (metric(treatment, "stable_s") is not None and metric(baseline, "stable_s") is not None and metric(treatment, "stable_s") > metric(baseline, "stable_s"))
    )
    return {
        "protocol": "fallback_pairing",
        "treatment_better": bool(better),
        "baseline_success": baseline.get("verified_task_success"),
        "treatment_success": treatment.get("verified_task_success"),
        "baseline_retries": baseline.get("retries"),
        "treatment_retries": treatment.get("retries"),
        "baseline_stable_s": baseline.get("stable_s"),
        "treatment_stable_s": treatment.get("stable_s"),
    }


def regression(evidence: Mapping[str, Mapping]) -> tuple[tuple[str, bool], ...]:
    b2 = evidence.get("b2", {})
    b2_failed = b2.get("verified_task_success", b2.get("verdict", {}).get("verified_task_success")) is False
    return (
        ("audit_16_reproduced", bool(evidence.get("audit", {}).get("all_match"))),
        ("b2_not_credited", b2_failed),
        ("f0_gate_passed", evidence.get("f0", {}).get("status") == "FEASIBILITY_GATE_PASSED"),
        ("reference_chain_strict", bool(evidence.get("reference", {}).get("passed"))),
        ("test_split_untouched", bool(evidence.get("test_split", {}).get("untouched"))),
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_report(
    *,
    report_id: str,
    candidate_id: str,
    candidate_digest: str,
    validation: Validation,
    protocol: str,
    baseline_episode: str | None,
    treatment_episode: str | None,
    initial_state_sha256: str,
    metrics: Sequence[tuple[str, float]],
    ops: Sequence[Op],
    evidence: Mapping[str, Mapping],
    decision: str = "reject",
    evidence_paths: Sequence[str] = (),
) -> ValidationReport:
    checks = contract_tests(ops)
    regressions = regression(evidence)
    if decision == "promote" and not all(flag for _name, flag in checks):
        raise ContractError("promote requires every contract test to pass")
    if decision == "promote" and not all(flag for _name, flag in regressions):
        raise ContractError("promote requires every regression check to pass")
    return ValidationReport(
        id=report_id,
        candidate_id=candidate_id,
        candidate_digest=candidate_digest,
        validation=validation,
        protocol=protocol,
        baseline_episode=baseline_episode,
        treatment_episode=treatment_episode,
        initial_state_sha256=initial_state_sha256,
        metrics=tuple((key, float(value)) for key, value in metrics),
        contract_tests=checks,
        regression=regressions,
        decision=decision,
        evidence=tuple(evidence_paths),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
