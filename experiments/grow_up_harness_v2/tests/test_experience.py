"""Experience building writes candidates and reads only legal feedback."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness import experience
from harness.agent import AgentSchemaError
from harness.contracts import Scope, Status
from harness.ops import SMALL_OPS, TP01_CHAIN

SOURCE = """import math

def act(observation, task, state):
    return {"action": {"op": "done"}, "state": state, "blackboard": {}}
"""


def payload() -> dict:
    return {
        "ops": {item.op_id: SOURCE for item in SMALL_OPS},
        "explanation": "bounded candidate",
        "memory": ["close later"],
    }


class DiagnosisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="experience-")
        self.root = Path(self.temp.name)
        (self.root / "feedback.json").write_text(
            json.dumps(
                {
                    "agent_visible": {
                        "verdict": "failure",
                        "failure_code": "CONTACT_LOST",
                        "failed_op": "close_hand",
                        "failed_step": 3,
                        "sim_time": 12.0,
                    },
                    "evaluator_only": {"threshold": 0.1, "raw_frames": [1, 2]},
                }
            ),
            encoding="utf-8",
        )
        (self.root / "attempts.json").write_text(
            json.dumps(
                [
                    {
                        "status": "failed",
                        "op_id": "close_hand",
                        "index": 3,
                        "failure_code": "CONTACT_LOST",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (self.root / "blackboard.jsonl").write_text(
            json.dumps({"step": 3, "op_id": "close_hand", "blackboard": {"grasp_offset": 0.02}}) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_diagnosis_uses_only_agent_visible(self) -> None:
        task = experience.TaskSpec(
            id="TP01_reach_train_000",
            template="TP01",
            instruction="lift",
            assets=frozenset({"cup"}),
            goal=experience.Predicate("HeldLifted"),
            budget_s=60.0,
        )
        diagnosis = experience.diagnose(self.root, task, mechanism="contact loss", repair_boundary="offset")
        self.assertEqual(diagnosis.failed_op, "close_hand")
        self.assertEqual(diagnosis.failure_code, "CONTACT_LOST")
        self.assertTrue(diagnosis.legal_only)
        self.assertEqual(diagnosis.blackboard, {"grasp_offset": 0.02})
        self.assertNotIn("threshold", json.dumps(diagnosis.agent_visible))
        self.assertNotIn("raw_frames", json.dumps(diagnosis.agent_visible))


class CandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = Scope("TP01", frozenset({"cup"}))

    def test_candidate_memory_is_candidate(self) -> None:
        diagnosis = experience.FailureDiagnosis(
            episode="ep",
            task_id="TP01_reach_train_000",
            failed_op="close_hand",
            failed_step=3,
            failure_code="CONTACT_LOST",
            agent_visible={"verdict": "failure"},
            blackboard={},
            mechanism="contact loss",
            repair_boundary="offset",
            legal_only=True,
        )
        note = experience.candidate_memory(diagnosis, self.scope)
        self.assertIs(note.status, Status.CANDIDATE)
        self.assertIn("CONTACT_LOST", note.text)

    def test_candidate_code_and_ops(self) -> None:
        modules = experience.candidate_code(payload(), self.scope)
        self.assertEqual(len(modules), 5)
        self.assertTrue(all(module.status is Status.CANDIDATE for module in modules))
        ops = experience.candidate_ops(modules, self.scope, "ep")
        self.assertEqual([op.op_id for op in ops], [item.op_id for item in SMALL_OPS])
        self.assertTrue(all(op.status is Status.CANDIDATE for op in ops))

    def test_bad_source_is_rejected(self) -> None:
        bad = payload()
        bad["ops"]["locate_target"] = "import os\ndef act(observation, task, state):\n    return {}\n"
        with self.assertRaises(AgentSchemaError):
            experience.candidate_code(bad, self.scope)

    def test_candidate_skill_uses_registered_chain(self) -> None:
        task = experience.TaskSpec(
            id="TP01_reach_train_000",
            template="TP01",
            instruction="lift",
            assets=frozenset({"cup"}),
            goal=experience.Predicate("HeldLifted"),
            budget_s=60.0,
        )
        skill = experience.candidate_skill(self.scope, task, ("ep",))
        self.assertIs(skill.status, Status.CANDIDATE)
        self.assertIsNone(skill.validation)
        self.assertEqual([step.op_id for step in skill.steps], [step.op_id for step in TP01_CHAIN])


if __name__ == "__main__":
    unittest.main()
