"""Independent replay and the feedback boundary over saved TP01 evidence."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    import mujoco  # noqa: F401
    from harness import evaluator, tp01
except ImportError as exc:  # pragma: no cover - environment gate
    evaluator = None
    tp01 = None
    SKIP_REASON = f"MuJoCo is unavailable: {exc}"
else:
    SKIP_REASON = ""

RUN = Path(__file__).resolve().parents[1] / "runs/f0v2_engineering_20261103_001"
SUCCESS = "case_01"
BOTTLE = "case_03"


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if evaluator is None:
            raise unittest.SkipTest(SKIP_REASON)
        if not RUN.is_dir():
            raise unittest.SkipTest(f"run directory is unavailable: {RUN}")
        cases = {case.alias: case for case in tp01.load_cases(tp01.REACH_DATASET)}
        missing = [
            alias
            for alias in (SUCCESS, BOTTLE)
            if not (RUN / alias / "integration_states.npz").is_file()
        ]
        if missing:
            raise unittest.SkipTest(f"episodes are unavailable: {missing}")
        cls.cases = cases
        cls.success = evaluator.replay(cases[SUCCESS], RUN / SUCCESS)
        cls.bottle = evaluator.replay(cases[BOTTLE], RUN / BOTTLE)

    def test_replay_reproduces_registered_success(self) -> None:
        saved = json.loads(
            (RUN / SUCCESS / "independent_verification.json").read_text(encoding="utf-8")
        )
        self.assertTrue(self.success.verified_task_success)
        self.assertTrue(self.success.goal_satisfied)
        self.assertEqual(self.success.evaluator_version, "tabletop-predicates-v1")
        self.assertEqual(
            self.success.verified_task_success, saved["verified_task_success"]
        )
        self.assertEqual(self.success.goal_satisfied, saved["goal_satisfied"])
        self.assertEqual(self.success.trajectory_sha256, saved["trajectory_sha256"])

    def test_replay_keeps_bottle_failure(self) -> None:
        self.assertFalse(self.bottle.verified_task_success)
        self.assertFalse(self.bottle.goal_satisfied)
        self.assertEqual(self.bottle.protection, "FORBIDDEN_CONTACT")
        self.assertIsNotNone(self.bottle.execution_error)

    def test_feedback_keeps_evaluator_fields_private(self) -> None:
        case = self.cases[SUCCESS]
        record = evaluator.feedback(
            episode_id="f0v2_case_01",
            task_id=case.task.id,
            verdict=self.success,
            stage="hold_stable",
            sim_time=75.44,
        )
        self.assertEqual(record.verdict, "success")
        self.assertEqual(
            set(record.agent_visible),
            {"verdict", "stage", "failure_code", "task_id", "sim_time", "stable_s"},
        )
        self.assertEqual(
            set(record.evaluator_only),
            {
                "goal_satisfied",
                "verified_task_success",
                "terminal_stable_s",
                "evaluator_version",
                "trajectory_sha256",
            },
        )
        self.assertFalse(set(record.agent_visible) & set(record.evaluator_only))
        self.assertEqual(
            record.agent_visible["stable_s"],
            round(self.success.terminal_stable_s, 1),
        )
        self.assertEqual(record.agent_visible["task_id"], case.task.id)
        self.assertNotIn("goal_satisfied", record.agent_visible)


if __name__ == "__main__":
    unittest.main()
