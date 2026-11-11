"""Step-to-step precondition chain: open_hand must be inside the chain."""

from __future__ import annotations

import unittest

from harness.contracts import (
    ContractError,
    PlanMode,
    ProgramStep,
    Scope,
    Skill,
    Snapshot,
    SnapshotView,
    Status,
    Step,
    TaskProgram,
    TaskSpec,
)
from harness.ir import compile_chain, validate_program, validate_sequence
from harness.ops import ALL_SPECS, TP01_CHAIN, TP01_CHAIN_BUDGET_S, TP01_INITIAL, make_op, spec

SHA = "cd" * 32


def cup_scope() -> Scope:
    return Scope("TP01", frozenset({"cup"}), stage="TP01_train_000")


def build_view(extra=()):
    artifacts = []
    for step in TP01_CHAIN:
        item = spec(step.op_id)
        if item.builtin:
            op = make_op(item, cup_scope(), Status.VALIDATED)
        else:
            op = make_op(item, cup_scope(), Status.VALIDATED, f"code_{item.op_id}", SHA)
        artifacts.append(op)
    artifacts.extend(extra)
    refs = tuple((getattr(op, "op_id", getattr(op, "id", "")), op.digest()) for op in artifacts)
    snapshot = Snapshot(id="snap_sequence", refs=refs, parent=None, label="test", frozen=False)
    return SnapshotView(snapshot, {ref: op for (ref, _digest), op in zip(refs, artifacts)})


def build_program(steps) -> TaskProgram:
    view = build_view()
    return TaskProgram(
        id="prog_sequence",
        task_id="TP01_train_000",
        snapshot_id=view.snapshot.id,
        mode=PlanMode.REUSE,
        steps=tuple(
            ProgramStep(index=index, op_id=step.op_id, op_version=1, args=step.args, label=step.label)
            for index, step in enumerate(steps)
        ),
        artifact_ids=(),
        budget_s=60.0,
    )


def task() -> TaskSpec:
    from harness.contracts import Predicate

    return TaskSpec(
        id="TP01_train_000",
        template="TP01",
        instruction="lift the cup",
        assets=frozenset({"cup"}),
        goal=Predicate("HeldLifted"),
        budget_s=60.0,
    )


class ChainTests(unittest.TestCase):

    def test_chain_satisfies_every_precondition(self):
        view = build_view()
        program = build_program(TP01_CHAIN)
        validate_program(program, view, "formal", task())
        established = validate_sequence(program, view, "formal", task(), TP01_INITIAL)
        self.assertEqual(set(established), {str(index) for index in range(len(TP01_CHAIN))})
        self.assertEqual(established["1"], {"guard_clear"})
        self.assertEqual(established["3"], {"hand_open", "palm_near_target", "guard_clear"})

    def test_missing_open_hand_is_rejected(self):
        steps = tuple(step for step in TP01_CHAIN if step.op_id != "open_hand")
        program = build_program(steps)
        view = build_view()
        validate_program(program, view, "formal", task())
        with self.assertRaises(ContractError) as caught:
            validate_sequence(program, view, "formal", task(), TP01_INITIAL)
        self.assertIn("hand_open", str(caught.exception))

    def test_missing_initial_predicate_is_rejected(self):
        program = build_program(TP01_CHAIN)
        view = build_view()
        with self.assertRaises(ContractError) as caught:
            validate_sequence(program, view, "formal", task(), ())
        self.assertIn("target_visible", str(caught.exception))

    def test_compile_chain_runs_the_sequence_check_when_initial_is_given(self):
        from harness.contracts import Predicate

        good_skill = Skill(
            id="skill_tp01",
            version=1,
            scope=cup_scope(),
            status=Status.CANDIDATE,
            validation=None,
            steps=tuple(Step(step.op_id, step.args, step.label) for step in TP01_CHAIN),
            post=(Predicate("target_stable"),),
            evidence=("practice",),
        )
        bad_skill = Skill(
            id="skill_bad",
            version=1,
            scope=cup_scope(),
            status=Status.CANDIDATE,
            validation=None,
            steps=tuple(
                Step(step.op_id, step.args, step.label)
                for step in TP01_CHAIN
                if step.op_id != "open_hand"
            ),
            post=(Predicate("target_stable"),),
            evidence=("practice",),
        )
        view = build_view([good_skill, bad_skill])
        program = compile_chain([good_skill], task(), view, PlanMode.REUSE, "practice", initial=TP01_INITIAL)
        self.assertEqual(len(program.steps), 7)
        with self.assertRaises(ContractError):
            compile_chain([bad_skill], task(), view, PlanMode.REUSE, "practice", initial=TP01_INITIAL)


if __name__ == "__main__":
    unittest.main()
