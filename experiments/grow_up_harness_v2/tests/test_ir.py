"""IR compiler: snapshot op index, admission, scope, and repair edges."""

from __future__ import annotations

import unittest

from harness.contracts import (
    ContractError,
    Op,
    PlanMode,
    Predicate,
    Procedure,
    ProgramArtifact,
    ProgramStep,
    Scope,
    Skill,
    Snapshot,
    SnapshotView,
    Status,
    Step,
    TaskProgram,
    TaskSpec,
    Validation,
)
from harness.ir import (
    compile_cached_program,
    compile_chain,
    compile_repair,
    compile_skill,
    op_index,
    validate_program,
    validate_step,
)
from harness.ops import SMALL_OPS, make_builtin_ops, make_op, spec

SHA = "cd" * 32


def cup_scope(task: str = "TP01", assets: tuple[str, ...] = ("cup",)) -> Scope:
    return Scope(task, frozenset(assets), stage="TP01_train_000")


def cup_task(**overrides) -> TaskSpec:
    values = dict(
        id="TP01_train_000",
        template="TP01",
        instruction="pick up the cup",
        assets=frozenset({"cup"}),
        goal=Predicate(
            "HeldLifted",
            (("object", "cup"), ("minimum_lift_m", 0.1), ("stable_s", 1.0)),
        ),
        budget_s=60.0,
        split="train",
    )
    values.update(overrides)
    return TaskSpec(**values)


def worker(
    op_id: str,
    *,
    status: Status = Status.VALIDATED,
    version: int = 1,
    scope: Scope | None = None,
    evidence: tuple[str, ...] = (),
) -> Op:
    return make_op(
        spec(op_id),
        cup_scope() if scope is None else scope,
        status,
        f"code_{op_id}",
        SHA,
        evidence=evidence,
        version=version,
    )


def builtin(op_id: str, *, version: int = 1, scope: Scope | None = None) -> Op:
    return make_op(
        spec(op_id),
        cup_scope() if scope is None else scope,
        Status.VALIDATED,
        version=version,
    )


def make_skill(
    skill_id: str,
    steps,
    *,
    status: Status = Status.VALIDATED,
    scope: Scope | None = None,
    on_failure=(),
    post: tuple[Predicate, ...] = (Predicate("target_stable"),),
) -> Skill:
    validation = Validation.REPAIR_LINEAGE if status is Status.VALIDATED else None
    return Skill(
        id=skill_id,
        version=1,
        scope=cup_scope() if scope is None else scope,
        status=status,
        validation=validation,
        steps=tuple(steps),
        post=post,
        on_failure=on_failure,
    )


def make_procedure(
    proc_id: str,
    *,
    status: Status = Status.VALIDATED,
    scope: Scope | None = None,
) -> Procedure:
    validation = Validation.REPAIR_LINEAGE if status is Status.VALIDATED else None
    return Procedure(
        id=proc_id,
        version=1,
        scope=cup_scope() if scope is None else scope,
        status=status,
        validation=validation,
        skill_ids=("grasp_cup",),
        steps=(Step("check", (("predicate", "target_stable"),)),),
        post=(Predicate("target_stable"),),
    )


def world(*artifacts, snapshot_id: str = "snap_1") -> SnapshotView:
    stored: dict = {}
    for artifact in artifacts:
        if isinstance(artifact, Op):
            base = f"{artifact.op_id}@{artifact.version}@{artifact.status.value}"
            key = base
            n = 2
            while key in stored:
                key = f"{base}#{n}"
                n += 1
        else:
            key = artifact.id
            if key in stored:
                raise RuntimeError(f"duplicate artifact id {key}")
        stored[key] = artifact
    refs = tuple((key, artifact.digest()) for key, artifact in stored.items())
    return SnapshotView(Snapshot(snapshot_id, refs, None, "test"), stored)


def table(scope: Scope | None = None, *, status: Status = Status.VALIDATED, version: int = 1) -> list[Op]:
    scope = cup_scope() if scope is None else scope
    ops = [worker(item.op_id, status=status, version=version, scope=scope) for item in SMALL_OPS]
    ops.extend(make_builtin_ops(scope))
    return ops


def grasp_steps() -> tuple[Step, ...]:
    return (
        Step("locate_target", label="locate"),
        Step("reach_target"),
        Step("close_hand", label="close"),
        Step("lift_target"),
        Step("hold_stable"),
        Step("check", (("predicate", "target_stable"),)),
    )


class OpIndexTests(unittest.TestCase):
    def test_latest_version_and_admission_filter(self):
        reach_v1 = worker("reach_target", version=1)
        reach_v2 = worker("reach_target", version=2)
        locate_validated = worker("locate_target", version=2)
        locate_candidate = worker("locate_target", status=Status.CANDIDATE, version=1)
        lift_validated = worker("lift_target", version=1)
        lift_candidate = worker("lift_target", status=Status.CANDIDATE, version=4)
        hold_rejected = worker("hold_stable", status=Status.REJECTED, version=9)
        hold_validated = worker("hold_stable", version=1)
        close_retired = worker("close_hand", status=Status.RETIRED, version=3)
        skill = make_skill("grasp_cup", [Step("reach_target")])
        view = world(
            reach_v2,
            reach_v1,
            locate_candidate,
            locate_validated,
            lift_candidate,
            lift_validated,
            hold_rejected,
            hold_validated,
            close_retired,
            skill,
        )
        formal = op_index(view, "formal")
        practice = op_index(view, "practice")
        self.assertEqual(formal["reach_target"].version, 2)
        self.assertEqual(formal["locate_target"].version, 2)
        self.assertEqual(formal["lift_target"].version, 1)
        self.assertEqual(formal["hold_stable"].version, 1)
        self.assertNotIn("close_hand", formal)
        self.assertEqual(practice["reach_target"].version, 2)
        self.assertEqual(practice["locate_target"].version, 2)
        self.assertEqual(practice["lift_target"].version, 4)
        self.assertEqual(practice["lift_target"].status, Status.CANDIDATE)
        self.assertEqual(practice["hold_stable"].version, 1)
        self.assertNotIn("close_hand", practice)
        self.assertNotIn("grasp_cup", formal)
        self.assertNotIn("grasp_cup", practice)
        with self.assertRaises(ContractError):
            op_index(view, "slow")

    def test_same_version_digest_conflict_follows_admission(self):
        left = worker("reach_target", evidence=("left",))
        right = worker("reach_target", evidence=("right",))
        self.assertNotEqual(left.digest(), right.digest())
        conflicted = world(left, right)
        with self.assertRaises(ContractError):
            op_index(conflicted, "formal")
        with self.assertRaises(ContractError):
            op_index(conflicted, "practice")
        candidate = worker("reach_target", status=Status.CANDIDATE, evidence=("candidate",))
        validated = worker("reach_target", evidence=("validated",))
        mixed = world(candidate, validated)
        self.assertEqual(op_index(mixed, "formal")["reach_target"].status, Status.VALIDATED)
        with self.assertRaises(ContractError):
            op_index(mixed, "practice")
        same = worker("locate_target", version=3)
        again = worker("locate_target", version=3)
        self.assertEqual(same.digest(), again.digest())
        indexed = op_index(world(same, again), "formal")
        self.assertEqual(indexed["locate_target"].version, 3)

    def test_index_is_the_snapshot_not_a_whitelist(self):
        custom = Op(
            op_id="nudge",
            version=2,
            scope=cup_scope(),
            status=Status.VALIDATED,
            pre=(),
            post=(Predicate("guard_clear"),),
            budget_s=0.5,
            failure_codes=("NUDGE_FAILED",),
            implementation="code_nudge",
            implementation_sha256=SHA,
        )
        view = world(custom)
        self.assertEqual(op_index(view, "formal")["nudge"].version, 2)
        self.assertNotIn("reach_target", op_index(view, "formal"))


class CompileSkillTests(unittest.TestCase):
    def test_compile_skill_binds_versions_and_validates(self):
        versions = {
            "locate_target": 2,
            "reach_target": 3,
            "close_hand": 1,
            "lift_target": 4,
            "hold_stable": 5,
        }
        ops = [worker(op_id, version=version) for op_id, version in versions.items()]
        ops.extend(make_builtin_ops(cup_scope()))
        regrasp = make_skill(
            "regrasp",
            (
                Step("open_hand"),
                Step("reach_target", (("offset_x", 0.02), ("offset_z", -0.01))),
                Step("close_hand"),
            ),
            post=(Predicate("grasp_contact"),),
        )
        skill = make_skill(
            "grasp_cup",
            grasp_steps(),
            on_failure=(("GRASP_MISS", "regrasp"),),
        )
        task = cup_task(budget_s=31.1)
        view = world(*ops, skill, regrasp)
        program = compile_skill(skill, task, view, PlanMode.REUSE)
        self.assertEqual(program.id, "prog_grasp_cup_TP01_train_000")
        self.assertEqual(program.task_id, task.id)
        self.assertEqual(program.snapshot_id, "snap_1")
        self.assertIs(program.mode, PlanMode.REUSE)
        self.assertEqual(program.artifact_ids, ("grasp_cup",))
        self.assertEqual(program.on_failure, (("GRASP_MISS", "regrasp"),))
        self.assertEqual(program.budget_s, 31.1)
        self.assertEqual([step.op_id for step in program.steps], [step.op_id for step in skill.steps])
        self.assertEqual([step.op_version for step in program.steps], [2, 3, 1, 4, 5, 1])
        self.assertTrue(all(step.source_skill == "grasp_cup" for step in program.steps))
        self.assertEqual(program.steps[0].label, "locate")
        self.assertEqual(program.steps[2].label, "close")
        self.assertEqual(program.steps[5].args, (("predicate", "target_stable"),))
        named = compile_skill(skill, task, view, PlanMode.COMPOSE, program_id="prog_custom")
        self.assertEqual(named.id, "prog_custom")
        self.assertIs(named.mode, PlanMode.COMPOSE)
        validate_program(program, view, "formal", task)
        with self.assertRaises(ContractError):
            compile_skill(skill, task, view, PlanMode.SYNTHESIZE)
        with self.assertRaises(ContractError):
            compile_skill(skill, task, view, PlanMode.REFUSE)

    def test_formal_rejects_candidate_op_practice_accepts(self):
        candidate = worker("locate_target", status=Status.CANDIDATE, version=4)
        skill = make_skill(
            "locate_only",
            [Step("locate_target")],
            post=(Predicate("target_localized"),),
        )
        view = world(candidate, skill)
        with self.assertRaises(ContractError):
            compile_skill(skill, cup_task(), view, PlanMode.REUSE, admission="formal")
        program = compile_skill(skill, cup_task(), view, PlanMode.REUSE, admission="practice")
        self.assertEqual(program.steps[0].op_version, 4)
        self.assertEqual(program.steps[0].source_skill, "locate_only")
        self.assertEqual(validate_step(program.steps[0], view, "practice", cup_task()).status, Status.CANDIDATE)

    def test_formal_rejects_candidate_skill_and_accepts_validated(self):
        ops = table()
        candidate = make_skill("grasp_cup", grasp_steps(), status=Status.CANDIDATE)
        validated = make_skill("grasp_cup", grasp_steps())
        task = cup_task()
        with self.assertRaises(ContractError):
            compile_skill(candidate, task, world(*ops, candidate), PlanMode.REUSE, admission="formal")
        practiced = compile_skill(
            candidate,
            task,
            world(*ops, candidate),
            PlanMode.REUSE,
            admission="practice",
        )
        self.assertEqual(practiced.artifact_ids, ("grasp_cup",))
        accepted = compile_skill(validated, task, world(*ops, validated), PlanMode.REUSE)
        self.assertEqual(accepted.artifact_ids, ("grasp_cup",))
        procedure = make_procedure("pick_proc", status=Status.CANDIDATE)
        hand = builtin("open_hand")
        open_skill = make_skill("open_only", [Step("open_hand")], post=(Predicate("hand_open"),))
        program = TaskProgram(
            id="prog_proc",
            task_id=task.id,
            snapshot_id="snap_1",
            mode=PlanMode.COMPOSE,
            steps=(ProgramStep(0, "open_hand", 1, source_skill="open_only"),),
            artifact_ids=("pick_proc",),
            budget_s=task.budget_s,
        )
        candidate_view = world(hand, open_skill, procedure)
        with self.assertRaises(ContractError):
            validate_program(program, candidate_view, "formal", task)
        validate_program(program, candidate_view, "practice", task)
        validated_proc = make_procedure("pick_proc")
        validate_program(program, world(hand, open_skill, validated_proc), "formal", task)

    def test_scope_uses_exact_cover(self):
        task = cup_task()
        good_skill = make_skill("open_only", [Step("open_hand")], post=(Predicate("hand_open"),))
        # A shared underscore prefix is not cover. v1 treated that as a match.
        prefix_op = builtin("open_hand", scope=cup_scope("TP01_train"))
        with self.assertRaises(ContractError):
            compile_skill(good_skill, task, world(prefix_op, good_skill), PlanMode.REUSE)
        orange_skill = make_skill(
            "open_only",
            [Step("open_hand")],
            scope=cup_scope(assets=("cup", "orange")),
            post=(Predicate("hand_open"),),
        )
        with self.assertRaises(ContractError):
            compile_skill(orange_skill, task, world(builtin("open_hand"), orange_skill), PlanMode.REUSE)
        id_scope = cup_scope("TP01_train_000")
        id_task = cup_task(template="pick_cup")
        id_skill = make_skill(
            "open_only",
            [Step("open_hand")],
            scope=id_scope,
            post=(Predicate("hand_open"),),
        )
        bound = compile_skill(id_skill, id_task, world(builtin("open_hand", scope=id_scope), id_skill), PlanMode.REUSE)
        self.assertEqual(bound.task_id, "TP01_train_000")
        wider = cup_task(assets=frozenset({"cup", "table"}))
        subset = compile_skill(good_skill, wider, world(builtin("open_hand"), good_skill), PlanMode.REUSE)
        self.assertEqual(subset.task_id, wider.id)

    def test_unknown_op_version_and_args_reject(self):
        ops = table()
        task = cup_task()
        missing = make_skill("missing", [Step("nudge")], post=(Predicate("guard_clear"),))
        with self.assertRaises(ContractError):
            compile_skill(missing, task, world(*ops, missing), PlanMode.REUSE)
        hand = builtin("open_hand")
        step = ProgramStep(0, "open_hand", 2, source_skill="open_only")
        with self.assertRaises(ContractError):
            validate_step(step, world(hand), "formal", task)
        both = world(hand, builtin("open_hand", version=2))
        self.assertEqual(op_index(both, "formal")["open_hand"].version, 2)
        with self.assertRaises(ContractError):
            validate_step(ProgramStep(0, "open_hand", 1), both, "formal", task)
        tilted = make_skill(
            "tilted",
            [Step("reach_target", (("tilt", 1.0),))],
            post=(Predicate("palm_near_target"),),
        )
        with self.assertRaises(ContractError):
            compile_skill(tilted, task, world(*ops, tilted), PlanMode.REUSE)
        offset = make_skill(
            "offset",
            [Step("reach_target", (("offset_y", 0.01),))],
            post=(Predicate("palm_near_target"),),
        )
        compiled = compile_skill(offset, task, world(*ops, offset), PlanMode.REUSE)
        self.assertEqual(compiled.steps[0].args, (("offset_y", 0.01),))
        unchecked = make_skill("unchecked", [Step("check")], post=(Predicate("target_stable"),))
        with self.assertRaises(ContractError):
            compile_skill(unchecked, task, world(*ops, unchecked), PlanMode.REUSE)


class RepairAndProgramTests(unittest.TestCase):
    def _repair_view(self, target, *, code: str = "GRASP_MISS", steps=None):
        ops = table()
        skill = make_skill(
            "grasp_cup",
            steps or (Step("close_hand"),),
            on_failure=((code, target.id),),
            post=(Predicate("grasp_contact"),),
        )
        return skill, world(*ops, skill, target)

    def test_repair_code_target_and_scope(self):
        task = cup_task()
        regrasp = make_skill("regrasp", [Step("open_hand")], post=(Predicate("hand_open"),))
        skill, view = self._repair_view(regrasp)
        program = compile_skill(skill, task, view, PlanMode.REUSE)
        self.assertEqual(program.on_failure, (("GRASP_MISS", "regrasp"),))
        undeclared, bad_view = self._repair_view(regrasp, code="NOT_STABLE", steps=(Step("locate_target"),))
        with self.assertRaises(ContractError):
            compile_skill(undeclared, task, bad_view, PlanMode.REUSE)
        procedure = make_procedure("regrasp_proc")
        procedural, proc_view = self._repair_view(procedure)
        with self.assertRaises(ContractError):
            compile_skill(procedural, task, proc_view, PlanMode.REUSE)
        # Prefix of the task id is not a scope match.
        outside = make_skill(
            "regrasp",
            [Step("open_hand")],
            scope=cup_scope("TP01_train"),
            post=(Predicate("hand_open"),),
        )
        scoped, scope_view = self._repair_view(outside)
        with self.assertRaises(ContractError):
            compile_skill(scoped, task, scope_view, PlanMode.REUSE)
        candidate = make_skill(
            "regrasp",
            [Step("open_hand")],
            status=Status.CANDIDATE,
            post=(Predicate("hand_open"),),
        )
        pending, pending_view = self._repair_view(candidate)
        with self.assertRaises(ContractError):
            compile_skill(pending, task, pending_view, PlanMode.REUSE, admission="formal")
        practiced = compile_skill(pending, task, pending_view, PlanMode.REUSE, admission="practice")
        self.assertEqual(practiced.on_failure, (("GRASP_MISS", "regrasp"),))

    def test_validate_program_rejects_snapshot_and_task_mismatch_without_mutation(self):
        ops = table()
        skill = make_skill("open_only", [Step("open_hand")], post=(Predicate("hand_open"),))
        task = cup_task()
        view = world(*ops, skill)
        program = compile_skill(skill, task, view, PlanMode.REUSE)
        before = program.to_dict()
        validate_program(program, view, "formal", task)
        other = SnapshotView(Snapshot("snap_other", view.snapshot.refs, None, "test"), dict(view.artifacts))
        with self.assertRaises(ContractError):
            validate_program(program, other, "formal", task)
        with self.assertRaises(ContractError):
            validate_program(program, view, "formal", cup_task(id="TP01_train_003"))
        self.assertEqual(program.to_dict(), before)
        keyed = world(builtin("open_hand"), worker("reach_target"))
        op_key = next(
            key
            for key, artifact in keyed.artifacts.items()
            if isinstance(artifact, Op) and artifact.op_id == "reach_target"
        )
        not_a_skill = TaskProgram(
            id="prog_op",
            task_id=task.id,
            snapshot_id="snap_1",
            mode=PlanMode.REUSE,
            steps=(ProgramStep(0, "open_hand", 1),),
            artifact_ids=(op_key,),
            budget_s=60.0,
        )
        with self.assertRaises(ContractError):
            validate_program(not_a_skill, keyed, "formal", task)

    def test_compile_chain_concatenates_steps_and_artifact_ids(self):
        ops = [
            worker("locate_target", version=2),
            worker("reach_target", version=3),
            worker("close_hand", version=1),
            worker("lift_target", version=4),
        ]
        first = make_skill(
            "locate_reach",
            (Step("locate_target", label="locate"), Step("reach_target")),
            post=(Predicate("palm_near_target"),),
        )
        second = make_skill(
            "close_lift",
            (Step("close_hand"), Step("lift_target", label="lift")),
            post=(Predicate("target_lifted"),),
        )
        task = cup_task()
        view = world(*ops, first, second)
        program = compile_chain([first, second], task, view)
        self.assertEqual(program.id, "prog_locate_reach__close_lift_TP01_train_000")
        self.assertIs(program.mode, PlanMode.COMPOSE)
        self.assertEqual(program.artifact_ids, ("locate_reach", "close_lift"))
        self.assertEqual(program.on_failure, ())
        self.assertEqual([step.op_id for step in program.steps], ["locate_target", "reach_target", "close_hand", "lift_target"])
        self.assertEqual([step.op_version for step in program.steps], [2, 3, 1, 4])
        self.assertEqual([step.source_skill for step in program.steps], ["locate_reach", "locate_reach", "close_lift", "close_lift"])
        self.assertEqual([step.index for step in program.steps], [0, 1, 2, 3])
        self.assertEqual(program.steps[0].label, "locate")
        self.assertEqual(program.steps[3].label, "lift")
        named = compile_chain((first, second), task, view, mode=PlanMode.REUSE, program_id="prog_chain")
        self.assertEqual(named.id, "prog_chain")
        self.assertIs(named.mode, PlanMode.REUSE)
        candidate = make_skill(
            "close_lift",
            (Step("close_hand"),),
            status=Status.CANDIDATE,
            post=(Predicate("grasp_contact"),),
        )
        with self.assertRaises(ContractError):
            compile_chain([first, candidate], task, world(*ops, first, candidate), PlanMode.COMPOSE)

    def test_cached_program_rebinds_and_rejects_a_missing_version(self):
        old_task = cup_task()
        hand = builtin("open_hand")
        skill = make_skill("open_only", [Step("open_hand")], post=(Predicate("hand_open"),))
        cached = TaskProgram(
            id="prog_old",
            task_id=old_task.id,
            snapshot_id="snap_old",
            mode=PlanMode.REUSE,
            steps=(ProgramStep(0, "open_hand", 1, source_skill="open_only"),),
            artifact_ids=("open_only",),
            budget_s=45.0,
        )
        artifact = ProgramArtifact(
            id="cached_open",
            version=1,
            task_id=old_task.id,
            scope=cup_scope(),
            status=Status.VALIDATED,
            validation=Validation.REPAIR_LINEAGE,
            program=cached,
        )
        new_task = cup_task(id="TP01_train_003", budget_s=12.0)
        rebound = compile_cached_program(artifact, new_task, world(hand, skill))
        self.assertEqual(rebound.id, "prog_cached_open_TP01_train_003")
        self.assertEqual(rebound.task_id, "TP01_train_003")
        self.assertEqual(rebound.snapshot_id, "snap_1")
        self.assertEqual(rebound.steps, cached.steps)
        self.assertEqual(rebound.budget_s, 45.0)
        self.assertIs(rebound.mode, PlanMode.REUSE)
        self.assertEqual(artifact.program.snapshot_id, "snap_old")
        self.assertEqual(artifact.program.task_id, old_task.id)
        stale = world(builtin("open_hand", version=2), skill)
        with self.assertRaises(ContractError):
            compile_cached_program(artifact, new_task, stale)
        self.assertEqual(artifact.program.to_dict(), cached.to_dict())

    def test_compile_repair_uses_reuse(self):
        hand = builtin("open_hand")
        skill = make_skill("regrasp", [Step("open_hand")], post=(Predicate("hand_open"),))
        task = cup_task()
        view = world(hand, skill)
        program = compile_repair(skill, task, view)
        self.assertIs(program.mode, PlanMode.REUSE)
        self.assertEqual(program, compile_skill(skill, task, view, PlanMode.REUSE))
        candidate = make_skill(
            "regrasp",
            [Step("open_hand")],
            status=Status.CANDIDATE,
            post=(Predicate("hand_open"),),
        )
        candidate_view = world(hand, candidate)
        with self.assertRaises(ContractError):
            compile_repair(candidate, task, candidate_view, admission="formal")
        practiced = compile_repair(candidate, task, candidate_view, admission="practice")
        self.assertIs(practiced.mode, PlanMode.REUSE)


if __name__ == "__main__":
    unittest.main()
