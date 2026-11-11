"""Small op table: specs, builtins, and candidate binding."""

from __future__ import annotations

import unittest

from harness.contracts import Scope, Status
from harness.ops import (
    BUILTIN_OPS,
    SMALL_OPS,
    make_builtin_ops,
    make_candidate_ops,
    make_op,
    spec,
)

SHA = "cd" * 32


def cup_scope() -> Scope:
    return Scope("TP01", frozenset({"cup"}), stage="TP01_train_000")


class OpSpecTests(unittest.TestCase):

    def test_make_op_copies_the_spec_contract(self):
        reach = spec("reach_target")
        op = make_op(reach, cup_scope(), Status.CANDIDATE, "code_reach", SHA, evidence=("ep1",))
        self.assertEqual(op.op_id, reach.op_id)
        self.assertEqual(op.version, 1)
        self.assertEqual(op.pre, reach.pre)
        self.assertEqual(op.post, reach.post)
        self.assertEqual(op.budget_s, reach.budget_s)
        self.assertEqual(op.failure_codes, reach.failure_codes)
        self.assertEqual(op.arg_keys, reach.arg_keys)
        self.assertEqual(op.required_arg_keys, reach.required_arg_keys)
        self.assertFalse(op.builtin)
        self.assertEqual(op.implementation, "code_reach")
        self.assertEqual(op.implementation_sha256, SHA)
        self.assertEqual(op.evidence, ("ep1",))
        with self.assertRaises(ValueError):
            make_op(reach, cup_scope(), Status.CANDIDATE)
        with self.assertRaises(ValueError):
            make_op(spec("check"), cup_scope(), Status.VALIDATED, "code_check", SHA)
        check = make_op(spec("check"), cup_scope(), Status.VALIDATED)
        self.assertTrue(check.builtin)
        self.assertIsNone(check.implementation)
        self.assertIsNone(check.implementation_sha256)
        self.assertEqual(check.required_arg_keys, ("predicate",))

    def test_candidate_versions_are_explicit(self):
        implementations = {item.op_id: (f"code_{item.op_id}", SHA) for item in SMALL_OPS}
        ops = make_candidate_ops(SMALL_OPS, cup_scope(), implementations, version=3)
        self.assertTrue(all(op.version == 3 for op in ops))
        single = make_op(
            spec("reach_target"),
            cup_scope(),
            Status.CANDIDATE,
            "code_reach",
            SHA,
            version=2,
        )
        self.assertEqual(single.version, 2)

    def test_candidate_ops_bind_implementations_and_stay_candidates(self):
        # Formal-mode rejection belongs to ir.py. The artifact only records status.
        implementations = {item.op_id: (f"code_{item.op_id}", SHA) for item in SMALL_OPS}
        ops = make_candidate_ops(SMALL_OPS, cup_scope(), implementations, evidence=("ep_practice",))
        self.assertEqual(len(ops), 5)
        for op, item in zip(ops, SMALL_OPS):
            self.assertEqual(op.status, Status.CANDIDATE)
            self.assertFalse(op.builtin)
            self.assertEqual(op.implementation, f"code_{item.op_id}")
            self.assertEqual(op.implementation_sha256, SHA)
            self.assertEqual(op.pre, item.pre)
            self.assertEqual(op.post, item.post)
            self.assertEqual(op.failure_codes, item.failure_codes)
            self.assertEqual(op.evidence, ("ep_practice",))
            self.assertNotEqual(op.status, Status.VALIDATED)
        builtins = make_builtin_ops(cup_scope())
        self.assertEqual(tuple(op.op_id for op in builtins), ("open_hand", "check"))
        for op in builtins:
            self.assertTrue(op.builtin)
            self.assertEqual(op.status, Status.VALIDATED)
            self.assertIsNone(op.implementation)
            self.assertIsNone(op.implementation_sha256)
        missing = dict(implementations)
        del missing["lift_target"]
        with self.assertRaises(ValueError):
            make_candidate_ops(SMALL_OPS, cup_scope(), missing)
        with self.assertRaises(ValueError):
            make_candidate_ops(BUILTIN_OPS, cup_scope(), {})


if __name__ == "__main__":
    unittest.main()
