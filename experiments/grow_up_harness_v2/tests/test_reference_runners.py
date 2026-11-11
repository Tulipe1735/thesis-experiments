"""Reference-runner stage slices and the V2.3 chain binding."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "calibration"))

import reference_runners as rr  # noqa: E402
from harness import tp01  # noqa: E402
from harness.ir import validate_program, validate_sequence  # noqa: E402
from harness.ops import TP01_INITIAL  # noqa: E402
from experiments.t0_agent_v1.common import sha  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SOURCE = (
    ROOT
    / "experiments/grow_up_harness_v2/runs/f0v2_engineering_20261103_001/case_01"
)


class StageSliceTests(unittest.TestCase):
    def test_slices_partition_every_request_once(self) -> None:
        slices = rr.stage_slices(SOURCE)
        self.assertEqual(sum(len(records) for records in slices.values()), 1874)
        self.assertEqual(len(slices["locate_target"]), 3)
        self.assertEqual(slices["open_hand"], [])
        self.assertEqual(slices["check"], [])
        for name in ("reach_target", "close_hand", "lift_target", "hold_stable"):
            self.assertGreater(len(slices[name]), 0, name)


class ChainTests(unittest.TestCase):
    def test_chain_binds_v2_budgets(self) -> None:
        case = tp01.load_cases()[0]
        program, view, artifacts = rr.chain(
            case, sha(ROOT / "experiments/grow_up_harness_v2/calibration/reference_runners.py")
        )
        self.assertEqual(len(program.steps), 7)
        self.assertEqual({step.op_version for step in program.steps}, {2})
        self.assertEqual(program.budget_s, 87.1)
        self.assertEqual(
            [artifact.budget_s for artifact in artifacts],
            [2.0, 2.0, 48.0, 13.0, 13.0, 9.0, 0.1],
        )
        validate_program(program, view, "formal", case.task)
        validate_sequence(program, view, "formal", case.task, TP01_INITIAL)


if __name__ == "__main__":
    unittest.main()
