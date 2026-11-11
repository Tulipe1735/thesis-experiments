"""Validation: contract tests, lineage, pairing, regression and report."""

from __future__ import annotations

import unittest

from harness import validation
from harness.contracts import (
    ContractError,
    Op,
    Predicate,
    Scope,
    Status,
    Validation,
)
from harness.ops import TP01_CHAIN, make_op, spec

SHA = "cd" * 32


def ops() -> list[Op]:
    scope = Scope("TP01", frozenset({"cup"}))
    rows = []
    for step in TP01_CHAIN:
        item = spec(step.op_id)
        if item.builtin:
            rows.append(make_op(item, scope, Status.VALIDATED))
        else:
            rows.append(make_op(item, scope, Status.VALIDATED, "code", SHA))
    return rows


class ContractTests(unittest.TestCase):
    def test_reference_ops_pass(self) -> None:
        checks = validation.contract_tests(ops())
        self.assertTrue(all(flag for _name, flag in checks))
        self.assertIn(("predicates:ten_specs", True), checks)

    def test_held_lifted_post_is_not_a_step_predicate(self) -> None:
        scope = Scope("TP01", frozenset({"cup"}))
        bad = Op(
            op_id="bad",
            version=1,
            scope=scope,
            status=Status.VALIDATED,
            pre=(),
            post=(Predicate("HeldLifted"),),
            budget_s=1.0,
            failure_codes=("X",),
            implementation="code",
            implementation_sha256=SHA,
        )
        checks = dict(validation.contract_tests([bad]))
        self.assertFalse(checks["bad:predicate_names"])


class LineageTests(unittest.TestCase):
    def test_lineage_flags(self) -> None:
        baseline = {"verified_task_success": False, "initial_state_sha256": SHA}
        treatment = {"verified_task_success": True, "initial_state_sha256": SHA}
        result = validation.repair_lineage(
            baseline, treatment, SHA, script_passes=True, agent_passes=True
        )
        self.assertTrue(all(result.values()))
        result = validation.repair_lineage(
            baseline, treatment, "ef" * 32, script_passes=True, agent_passes=True
        )
        self.assertFalse(result["same_initial_state"])

    def test_paired_metrics(self) -> None:
        baseline = {"verified_task_success": False, "retries": 3, "stable_s": None}
        treatment = {"verified_task_success": True, "retries": 1, "stable_s": 1.2}
        result = validation.paired(baseline, treatment)
        self.assertTrue(result["treatment_better"])
        self.assertEqual(result["protocol"], "fallback_pairing")


class RegressionTests(unittest.TestCase):
    def evidence(self, **overrides) -> dict:
        rows = {
            "audit": {"all_match": True},
            "b2": {"verdict": {"verified_task_success": False}},
            "f0": {"status": "FEASIBILITY_GATE_PASSED"},
            "reference": {"passed": True},
            "test_split": {"untouched": True},
        }
        rows.update(overrides)
        return rows

    def test_all_regression_checks(self) -> None:
        checks = validation.regression(self.evidence())
        self.assertTrue(all(flag for _name, flag in checks))

    def test_reference_failure_fails_regression(self) -> None:
        checks = dict(validation.regression(self.evidence(reference={"passed": False})))
        self.assertFalse(checks["reference_chain_strict"])


class ReportTests(unittest.TestCase):
    def report(self, decision: str, rows: list[Op]):
        return validation.build_report(
            report_id="report_test",
            candidate_id="candidate_test",
            candidate_digest=SHA,
            validation=Validation.PAIRED,
            protocol="test",
            baseline_episode="b1",
            treatment_episode=None,
            initial_state_sha256=SHA,
            metrics=(("stable_s", 1.0),),
            ops=rows,
            evidence={
                "audit": {"all_match": True},
                "b2": {"verdict": {"verified_task_success": False}},
                "f0": {"status": "FEASIBILITY_GATE_PASSED"},
                "reference": {"passed": True},
                "test_split": {"untouched": True},
            },
            decision=decision,
        )

    def test_reject_report(self) -> None:
        report = self.report("reject", ops())
        self.assertEqual(report.decision, "reject")
        self.assertTrue(all(flag for _name, flag in report.contract_tests))

    def test_promote_requires_every_contract(self) -> None:
        scope = Scope("TP01", frozenset({"cup"}))
        bad = Op(
            op_id="bad",
            version=1,
            scope=scope,
            status=Status.VALIDATED,
            pre=(),
            post=(Predicate("HeldLifted"),),
            budget_s=1.0,
            failure_codes=("X",),
            implementation="code",
            implementation_sha256=SHA,
        )
        with self.assertRaises(ContractError):
            self.report("promote", [bad])


if __name__ == "__main__":
    unittest.main()
