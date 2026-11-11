"""The demo checklist: 26 keys, honest pending values, no Agent success."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from harness import demo


def evidence() -> dict:
    return dict(
        reference={"verified_task_success": True, "passed": True, "verdict_match": True},
        b1={"verdict": {"verified_task_success": False}, "label": "B1_fallback"},
        f0={"status": "FEASIBILITY_GATE_PASSED"},
        b2={"verdict": {"verified_task_success": False}},
        audit={"all_match": True},
        gateway={"passed": True},
        predicate_check={"passed": True},
        unit_tests="127 passed",
        hashes_ok=True,
        diagnosis_legal=True,
        test_split=True,
    )


class ChecklistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="demo-")
        self.episode = Path(self.temp.name)
        (self.episode / "blackboard.jsonl").write_text('{"step":0}\n', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, **overrides):
        rows = evidence()
        rows.update(overrides)
        return demo.build_checks(episode=self.episode, **rows)

    def test_exactly_the_registered_keys(self) -> None:
        checks, _notes = self.build()
        self.assertEqual(set(checks), set(demo.CHECKS))
        self.assertEqual(len(checks), 26)

    def test_agent_dependent_checks_stay_false(self) -> None:
        checks, notes = self.build()
        for key in (
            "candidate_ops_execute_in_worker",
            "candidate_ops_run_in_practice",
            "verified_task_success",
            "repair_same_initial_state_script_passes",
            "repair_same_initial_state_agent_passes",
            "fallback_pairing_recomputed",
            "promotion_writes_new_snapshot",
            "ops_promoted_are_used",
            "formal_reuse_selects_promoted_skill",
        ):
            self.assertFalse(checks[key], key)
        self.assertIn("not an Agent success", notes["verified_task_success"])

    def test_reference_and_baseline_checks(self) -> None:
        checks, _notes = self.build()
        self.assertTrue(checks["baseline_failure_preserved"])
        self.assertTrue(checks["baseline_lineage_root_declared"])
        self.assertTrue(checks["feasibility_gate_recorded"])
        self.assertTrue(checks["negative_control_not_credited"])
        self.assertTrue(checks["evaluator_positive_control_passes"])
        self.assertTrue(checks["regression_passes"])
        self.assertTrue(checks["evidence_hashes_verify"])
        self.assertTrue(checks["test_split_untouched"])
        self.assertTrue(checks["gateway_smoke_passed"])

    def test_b1_success_would_break_the_baseline_checks(self) -> None:
        checks, _notes = self.build(b1={"verdict": {"verified_task_success": True}, "label": "B1_fallback"})
        self.assertFalse(checks["baseline_failure_preserved"])

    def test_failed_hashes_break_the_hash_check(self) -> None:
        checks, _notes = self.build(hashes_ok=False)
        self.assertFalse(checks["evidence_hashes_verify"])

    def test_missing_blackboard_breaks_the_check(self) -> None:
        (self.episode / "blackboard.jsonl").unlink()
        checks, _notes = self.build()
        self.assertFalse(checks["blackboard_recorded"])

    def test_f0_failure_breaks_regression(self) -> None:
        checks, _notes = self.build(f0={"status": "FEASIBILITY_GATE_FAILED"})
        self.assertFalse(checks["feasibility_gate_recorded"])
        self.assertFalse(checks["regression_passes"])


if __name__ == "__main__":
    unittest.main()
