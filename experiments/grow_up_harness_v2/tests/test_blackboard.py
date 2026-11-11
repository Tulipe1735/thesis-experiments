"""Blackboard: legal values, merge semantics, and JSONL evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness.blackboard import Blackboard, BlackboardError, normalize


class ContractTests(unittest.TestCase):
    def test_numbers_become_floats_so_1_and_1_0_do_not_fork(self):
        self.assertEqual(normalize({"gain": 1}), normalize({"gain": 1.0}))
        self.assertEqual(Blackboard.from_dict({"gain": 1}).get("gain"), 1.0)

    def test_keys_and_values_are_closed(self):
        for bad in ({"Bad": 1.0}, {"_x": 1.0}, {"9x": 1.0}, {"": 1.0}):
            with self.assertRaises(BlackboardError):
                normalize(bad)
        for bad in ({"x": True}, {"x": None}, {"x": float("inf")}, {"x": {"nested": 1.0}}):
            with self.assertRaises(BlackboardError):
                normalize(bad)
        with self.assertRaises(BlackboardError):
            normalize({"x": ["a"] * 65})
        with self.assertRaises(BlackboardError):
            normalize({f"k{i}": 0.0 for i in range(33)})

    def test_flat_lists_are_allowed(self):
        board = Blackboard.from_dict({"palm_offset": [0.01, -0.02, 0.0]})
        self.assertEqual(board.get("palm_offset"), (0.01, -0.02, 0.0))
        self.assertEqual(board.to_dict()["palm_offset"], [0.01, -0.02, 0.0])


class MergeTests(unittest.TestCase):
    def test_merge_overrides_and_keeps_the_rest(self):
        first = Blackboard.from_dict({"confidence": 0.4, "grasp_offset": 0.01})
        second = Blackboard.from_dict({"confidence": 0.8})
        merged = first.merge(second)
        self.assertEqual(merged.get("confidence"), 0.8)
        self.assertEqual(merged.get("grasp_offset"), 0.01)

    def test_merge_accepts_a_plain_dict(self):
        merged = Blackboard.from_dict({"a": 1.0}).merge({"b": "x"})
        self.assertEqual(merged.to_dict(), {"a": 1.0, "b": "x"})

    def test_merge_rejects_an_illegal_update(self):
        with self.assertRaises(BlackboardError):
            Blackboard.from_dict({"a": 1.0}).merge({"A": 2.0})

    def test_blackboard_is_immutable(self):
        board = Blackboard.from_dict({"a": 1.0})
        with self.assertRaises(Exception):
            board.entries = ()  # type: ignore[misc]


class EvidenceTests(unittest.TestCase):
    def test_jsonl_record_is_one_sorted_line(self):
        board = Blackboard.from_dict({"b": 2.0, "a": 1.0})
        line = board.jsonl_record(step=3, op_id="reach_target")
        self.assertTrue(line.endswith("\n"))
        payload = json.loads(line)
        self.assertEqual(payload["step"], 3)
        self.assertEqual(payload["op_id"], "reach_target")
        self.assertEqual(payload["blackboard"], {"a": 1.0, "b": 2.0})
        self.assertNotIn(" ", line)

    def test_records_survive_a_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "blackboard.jsonl"
            board = Blackboard.from_dict({"confidence": 0.9})
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(board.jsonl_record(step=0, op_id="locate_target"))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(Blackboard.from_dict(payload["blackboard"]), board)


if __name__ == "__main__":
    unittest.main()
