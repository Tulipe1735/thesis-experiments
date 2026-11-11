"""Contract invariants for v2 artifacts."""

from __future__ import annotations

import hashlib
import json
import unittest

from harness.contracts import (
    CodeModule,
    ContractError,
    EpisodeResult,
    Feedback,
    MemoryNote,
    Observation,
    Op,
    Outcome,
    PlanMode,
    Predicate,
    Procedure,
    ProgramArtifact,
    ProgramStep,
    Scope,
    Skill,
    Status,
    Step,
    TaskProgram,
    TaskSpec,
    Validation,
    ValidationReport,
    artifact_from_dict,
    scope_covers,
)

SHA = "ab" * 32


def goal() -> Predicate:
    return Predicate(
        "HeldLifted",
        (("object", "cup"), ("minimum_lift_m", 0.1), ("stable_s", 1.0)),
    )


def scope() -> Scope:
    return Scope("TP01", frozenset({"cup"}))


def task(**overrides) -> TaskSpec:
    values = dict(
        id="TP01_train_000",
        template="TP01",
        instruction="pick up the cup",
        assets=frozenset({"cup"}),
        goal=goal(),
    )
    values.update(overrides)
    return TaskSpec(**values)


def code_module(source: str = "def act(observation, task, state):\n    return {}\n") -> CodeModule:
    return CodeModule(
        id="reach_v1",
        version=1,
        scope=scope(),
        status=Status.CANDIDATE,
        source=source,
        allowed_imports=("math", "numpy"),
        tests=("test_reach",),
        evidence=("ep_fail",),
    )


def candidate_op(**overrides) -> Op:
    values = dict(
        op_id="reach_target",
        version=1,
        scope=scope(),
        status=Status.CANDIDATE,
        pre=(Predicate("target_localized"), Predicate("hand_empty"), Predicate("guard_clear")),
        post=(Predicate("palm_near_target"),),
        budget_s=12.0,
        failure_codes=("REACH_UNREACHABLE", "JOINT_LIMIT"),
        implementation="reach_v1",
        implementation_sha256=SHA,
        arg_keys=("offset_x", "offset_y", "offset_z"),
    )
    values.update(overrides)
    return Op(**values)


def skill(**overrides) -> Skill:
    values = dict(
        id="grasp_cup",
        version=1,
        scope=scope(),
        status=Status.VALIDATED,
        validation=Validation.REPAIR_LINEAGE,
        steps=(Step("close_hand", label="close"),),
        post=(Predicate("grasp_contact"),),
        on_failure=(("GRASP_MISS", "regrasp"),),
        evidence=("ep_repair",),
    )
    values.update(overrides)
    return Skill(**values)


def procedure(**overrides) -> Procedure:
    values = dict(
        id="pick_cup",
        version=1,
        scope=scope(),
        status=Status.CANDIDATE,
        validation=None,
        skill_ids=("grasp_cup",),
        steps=(Step("lift_target"),),
        post=(Predicate("target_lifted"),),
    )
    values.update(overrides)
    return Procedure(**values)


def program(**overrides) -> TaskProgram:
    values = dict(
        id="prog_pick",
        task_id="TP01_train_000",
        snapshot_id="snap_1",
        mode=PlanMode.REUSE,
        steps=(
            ProgramStep(0, "locate_target", 1, source_skill="grasp_cup"),
            ProgramStep(1, "check", 1, (("predicate", "target_stable"),)),
        ),
        artifact_ids=("grasp_cup",),
        on_failure=(("GRASP_MISS", "regrasp"),),
        budget_s=60.0,
    )
    values.update(overrides)
    return TaskProgram(**values)


def report(**overrides) -> ValidationReport:
    values = dict(
        id="val_1",
        candidate_id="reach_target",
        candidate_digest=SHA,
        validation=Validation.REPAIR_LINEAGE,
        protocol="repair_lineage_v1",
        baseline_episode="ep_fail",
        treatment_episode="ep_fix",
        initial_state_sha256=SHA,
        metrics=(("stable_s", 1.2),),
        contract_tests=(("pre", True), ("post", True)),
        regression=(("audit", True),),
        decision="promote",
        evidence=("ep_fail", "ep_fix"),
        created_at="2026-11-03T00:00:00Z",
    )
    values.update(overrides)
    return ValidationReport(**values)


def artifacts() -> list:
    builtin = Op(
        op_id="check",
        version=1,
        scope=scope(),
        status=Status.VALIDATED,
        pre=(),
        post=(Predicate("target_stable"),),
        budget_s=0.1,
        failure_codes=("CHECK_FAILED",),
        implementation=None,
        implementation_sha256=None,
        builtin=True,
        arg_keys=("predicate",),
        required_arg_keys=("predicate",),
    )
    note = MemoryNote(
        id="m1",
        text="杯子在左手掌附近时再闭合",
        scope=scope(),
        status=Status.CANDIDATE,
        evidence=("ep_fail",),
        supersedes=None,
    )
    cached = ProgramArtifact(
        id="prog_art",
        version=1,
        task_id="TP01_train_000",
        scope=scope(),
        status=Status.CANDIDATE,
        validation=None,
        program=program(),
        evidence=("ep_practice",),
    )
    return [
        candidate_op(),
        builtin,
        code_module(),
        skill(),
        procedure(),
        cached,
        note,
        report(),
    ]


class ContractTests(unittest.TestCase):
    def test_scope_cover_is_exact(self):
        covered = task()
        self.assertTrue(scope_covers(Scope("TP01", frozenset({"cup"})), covered))
        self.assertTrue(scope_covers(Scope("TP01_train_000", frozenset({"cup"})), covered))
        # v1 would accept these by splitting on "_" or by substring.
        self.assertFalse(scope_covers(Scope("TP01_train", frozenset({"cup"})), covered))
        self.assertFalse(scope_covers(Scope("train", frozenset({"cup"})), covered))
        self.assertFalse(scope_covers(Scope("TP", frozenset({"cup"})), covered))
        pick = task(template="pick_cup")
        self.assertFalse(scope_covers(Scope("TP01", frozenset({"cup"})), pick))
        self.assertTrue(scope_covers(Scope("pick_cup", frozenset({"cup"})), pick))
        self.assertFalse(scope_covers(Scope("TP01", frozenset({"cup", "orange"})), covered))
        wider = task(assets=frozenset({"cup", "table"}))
        self.assertTrue(scope_covers(Scope("TP01", frozenset({"cup"})), wider))

    def test_scope_rejects_empty_task_or_assets(self):
        with self.assertRaises(ValueError):
            Scope("", frozenset({"cup"}))
        with self.assertRaises(ValueError):
            Scope("TP01", frozenset())
        with self.assertRaises(ValueError):
            Scope("TP01", frozenset({""}))

    def test_task_goal_is_a_predicate(self):
        with self.assertRaises(ValueError):
            TaskSpec(
                id="t",
                template="t",
                instruction="pick up the cup",
                assets=frozenset({"cup"}),
                goal="HeldLifted",
            )
        with self.assertRaises(ValueError):
            task(budget_s=0)

    def test_predicate_closed_set_and_params(self):
        names = (
            "target_visible",
            "hand_empty",
            "hand_open",
            "target_localized",
            "palm_near_target",
            "grasp_contact",
            "holding_target",
            "target_lifted",
            "target_stable",
            "guard_clear",
            "HeldLifted",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(Predicate(name).name, name)
        for name in ("at_target", "held", "Held", "TARGET_VISIBLE", ""):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    Predicate(name)
        with self.assertRaises(ValueError):
            Predicate("HeldLifted", (("object", "cup"), ("object", "orange")))
        with self.assertRaises(ValueError):
            Predicate("target_lifted", (("height_m", float("nan")),))
        with self.assertRaises(ValueError):
            Predicate("target_lifted", (("height_m", float("inf")),))
        with self.assertRaises(ValueError):
            Predicate("HeldLifted", (("object", ""),))
        with self.assertRaises(ValueError):
            Predicate("HeldLifted", (("", "cup"),))
        lifted = Predicate("HeldLifted", (("object", "cup"), ("minimum_lift_m", 1)))
        self.assertEqual(lifted.params[1][1], 1.0)
        self.assertEqual(lifted, Predicate.from_dict(lifted.to_dict()))
        self.assertNotEqual(lifted.key(), Predicate("HeldLifted", (("object", "orange"),)).key())

    def test_code_module_hashes_exact_source_and_rejects_unsafe_imports(self):
        source = "def act(observation, task, state):\n    return {}\n"
        module = code_module(source)
        self.assertEqual(module.source_sha256, hashlib.sha256(source.encode("utf-8")).hexdigest())
        changed = code_module(source + "\n")
        self.assertNotEqual(module.source_sha256, changed.source_sha256)
        self.assertNotEqual(module.digest(), changed.digest())
        with self.assertRaises(TypeError):
            CodeModule(
                id="c",
                version=1,
                scope=scope(),
                status=Status.CANDIDATE,
                source=source,
                allowed_imports=("math",),
                source_sha256="0" * 64,
            )
        for name in ("os", "sys", "subprocess", "mujoco", "numpy.core"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    code_module_with_imports((name,))
        with self.assertRaises(ValueError):
            code_module_with_imports(())
        allowed = code_module_with_imports(("math", "numpy", "numpy.linalg", "numpy.random", "numpy.fft"))
        self.assertEqual(allowed.allowed_imports[0], "math")
        left = CodeModule(
            id="reach_v1",
            version=1,
            scope=Scope("TP01", frozenset({"table", "cup"})),
            status=Status.CANDIDATE,
            source=source,
            allowed_imports=("math",),
        )
        right = CodeModule(
            id="reach_v1",
            version=1,
            scope=Scope("TP01", frozenset({"cup", "table"})),
            status=Status.CANDIDATE,
            source=source,
            allowed_imports=("math",),
        )
        self.assertEqual(left.digest(), right.digest())

    def test_op_implementation_and_contract_rules(self):
        builtin = Op(
            op_id="open_hand",
            version=1,
            scope=scope(),
            status=Status.VALIDATED,
            pre=(Predicate("guard_clear"),),
            post=(Predicate("hand_open"),),
            budget_s=2.0,
            failure_codes=("HAND_NOT_OPEN",),
            implementation=None,
            implementation_sha256=None,
            builtin=True,
        )
        self.assertIsNone(builtin.implementation)
        self.assertTrue(builtin.builtin)
        with self.assertRaises(ValueError):
            candidate_op(builtin=True, implementation="reach_v1", implementation_sha256=SHA)
        with self.assertRaises(ValueError):
            candidate_op(implementation=None, implementation_sha256=None)
        with self.assertRaises(ValueError):
            candidate_op(implementation="", implementation_sha256=SHA)
        with self.assertRaises(ValueError):
            candidate_op(implementation_sha256="A" * 64)
        with self.assertRaises(ValueError):
            candidate_op(implementation_sha256="g" * 64)
        with self.assertRaises(ValueError):
            candidate_op(failure_codes=("COLLISION", "COLLISION"))
        with self.assertRaises(ValueError):
            candidate_op(failure_codes=())
        with self.assertRaises(ValueError):
            candidate_op(failure_codes=("",))
        with self.assertRaises(ValueError):
            candidate_op(post=())
        with self.assertRaises(ValueError):
            candidate_op(
                pre=(Predicate("guard_clear"), Predicate("guard_clear")),
            )
        with self.assertRaises(ValueError):
            candidate_op(arg_keys=("offset_x",), required_arg_keys=("offset_y",))
        with self.assertRaises(ValueError):
            candidate_op(arg_keys=("offset_x", "offset_x"))
        kept = candidate_op(required_arg_keys=("offset_x",))
        self.assertEqual(kept.required_arg_keys, ("offset_x",))

    def test_skill_and_procedure_status_rules(self):
        with self.assertRaises(ValueError):
            skill(status=Status.CANDIDATE, validation=Validation.PAIRED)
        with self.assertRaises(ValueError):
            skill(status=Status.VALIDATED, validation=None)
        self.assertIsNone(skill(status=Status.REJECTED, validation=None).validation)
        self.assertEqual(
            skill(status=Status.RETIRED, validation=Validation.EXPANDED).validation,
            Validation.EXPANDED,
        )
        with self.assertRaises(ValueError):
            skill(steps=())
        with self.assertRaises(ValueError):
            skill(post=())
        with self.assertRaises(ValueError):
            skill(on_failure=(("GRASP_MISS", "regrasp"), ("GRASP_MISS", "other")))
        with self.assertRaises(ValueError):
            skill(on_failure=(("", "regrasp"),))
        with self.assertRaises(ValueError):
            skill(on_failure=(("GRASP_MISS", ""),))
        with self.assertRaises(ValueError):
            procedure(status=Status.CANDIDATE, validation=Validation.PAIRED)
        with self.assertRaises(ValueError):
            procedure(status=Status.VALIDATED, validation=None)
        self.assertIsNotNone(procedure(status=Status.REJECTED, validation=Validation.PAIRED).validation)
        with self.assertRaises(ValueError):
            procedure(steps=())
        with self.assertRaises(ValueError):
            procedure(skill_ids=())
        with self.assertRaises(ValueError):
            procedure(post=())

    def test_program_indices_and_repair_codes(self):
        self.assertEqual([step.index for step in program().steps], [0, 1])
        self.assertNotIn("kind", program().to_dict())
        with self.assertRaises(ValueError):
            program(steps=())
        with self.assertRaises(ValueError):
            program(steps=(ProgramStep(1, "check", 1),))
        with self.assertRaises(ValueError):
            program(steps=(ProgramStep(0, "check", 1), ProgramStep(2, "hold_stable", 1)))
        with self.assertRaises(ValueError):
            program(steps=(ProgramStep(1, "check", 1), ProgramStep(0, "hold_stable", 1)))
        with self.assertRaises(ValueError):
            program(on_failure=(("GRASP_MISS", "regrasp"), ("GRASP_MISS", "other")))
        with self.assertRaises(ValueError):
            program(on_failure=(("GRASP_MISS", ""),))
        with self.assertRaises(ValueError):
            program(budget_s=0)
        with self.assertRaises(ValueError):
            ProgramArtifact(
                id="prog_art",
                version=1,
                task_id="other",
                scope=scope(),
                status=Status.CANDIDATE,
                validation=None,
                program=program(),
            )

    def test_feedback_boundary_and_failure_step(self):
        ok = Feedback(
            episode_id="ep",
            verdict="failure",
            stage="close_hand",
            failure_code="GRASP_MISS",
            failed_op="close_hand",
            failed_step=2,
            agent_visible={"sim_time": 1.0},
            evaluator_only={"contact_load_N": 0.2},
        )
        self.assertEqual(ok.to_dict()["failed_step"], 2)
        with self.assertRaises(ValueError):
            Feedback(
                episode_id="ep",
                verdict="failure",
                stage="close_hand",
                failure_code="GRASP_MISS",
                failed_op=None,
                failed_step=None,
                agent_visible={"sim_time": 1.0},
                evaluator_only={"sim_time": 1.0},
            )
        with self.assertRaises(ValueError):
            Feedback(
                episode_id="ep",
                verdict="failure",
                stage="close_hand",
                failure_code="GRASP_MISS",
                failed_op="close_hand",
                failed_step=None,
                agent_visible={},
                evaluator_only={},
            )
        with self.assertRaises(ValueError):
            Feedback(
                episode_id="ep",
                verdict="success",
                stage=None,
                failure_code=None,
                failed_op=None,
                failed_step=0,
                agent_visible={},
                evaluator_only={},
            )
        with self.assertRaises(ValueError):
            Feedback(
                episode_id="ep",
                verdict="succeeded",
                stage=None,
                failure_code=None,
                failed_op=None,
                failed_step=None,
                agent_visible={},
                evaluator_only={},
            )

    def test_validation_report_promote_and_episode_gates(self):
        self.assertEqual(report().decision, "promote")
        with self.assertRaises(ValueError):
            report(contract_tests=(("pre", True), ("post", False)))
        with self.assertRaises(ValueError):
            report(regression=(("audit", False),))
        with self.assertRaises(ValueError):
            report(decision="accept")
        paired = report(
            validation=Validation.PAIRED,
            decision="reject",
            contract_tests=(("pre", False),),
            treatment_episode=None,
        )
        self.assertEqual(paired.baseline_episode, "ep_fail")
        self.assertIsNone(paired.treatment_episode)
        with self.assertRaises(ValueError):
            report(
                validation=Validation.PAIRED,
                decision="reject",
                baseline_episode=None,
                treatment_episode=None,
            )
        treatment_only = report(
            validation=Validation.PAIRED,
            decision="reject",
            baseline_episode=None,
            treatment_episode="ep_fix",
        )
        self.assertEqual(treatment_only.treatment_episode, "ep_fix")
        with self.assertRaises(ValueError):
            report(validation=Validation.REPAIR_LINEAGE, baseline_episode=None)
        with self.assertRaises(ValueError):
            report(validation=Validation.REPAIR_LINEAGE, treatment_episode=None)
        expanded = report(
            validation=Validation.EXPANDED,
            decision="reject",
            baseline_episode=None,
            treatment_episode=None,
            contract_tests=(("pre", False),),
        )
        self.assertIsNone(expanded.baseline_episode)

    def test_observation_rejects_unknown_and_evaluator_keys(self):
        obs = Observation(
            0.0,
            {
                "simulation_seconds": 0.0,
                "joints": {},
                "left_palm": {},
                "tactile_joint_load_N": {},
                "guard": {},
                "rgbd": {},
            },
        )
        self.assertEqual(set(obs.agent_view()), set(obs.payload))
        payload = {"simulation_seconds": 0.0, "guard": {"clear": True}}
        copied = Observation(1, payload)
        payload["simulation_seconds"] = 9.0
        self.assertEqual(copied.payload["simulation_seconds"], 0.0)
        view = copied.agent_view()
        view["simulation_seconds"] = 3.0
        self.assertEqual(copied.payload["simulation_seconds"], 0.0)
        view["guard"]["clear"] = False
        self.assertFalse(copied.payload["guard"]["clear"])
        with self.assertRaises(ValueError):
            Observation(0.0, {"simulation_seconds": 0.0, "secret": 1})
        with self.assertRaises(ValueError):
            Observation(0.0, {"simulation_seconds": 0.0, "target_pose": {}})
        with self.assertRaises(ValueError):
            Observation(0.0, {"simulation_seconds": 0.0, "contact_load_N": 0.2})
        with self.assertRaises(ValueError):
            Observation(0.0, {"joints": {}})
        with self.assertRaises(ValueError):
            Observation(-0.1, {"simulation_seconds": 0.0})
        with self.assertRaises(ValueError):
            Observation(float("nan"), {"simulation_seconds": 0.0})

    def test_artifact_round_trip(self):
        for artifact in artifacts():
            with self.subTest(kind=artifact.kind):
                data = artifact.to_dict()
                raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
                restored = artifact_from_dict(json.loads(raw))
                self.assertIsInstance(restored, type(artifact))
                self.assertEqual(restored, artifact)
                self.assertEqual(restored.to_dict(), data)
                self.assertEqual(restored.digest(), artifact.digest())
                self.assertEqual(restored.kind, data["kind"])
                expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                self.assertEqual(artifact.digest(), expected)
        with self.assertRaises(ValueError):
            artifact_from_dict({"kind": "advisor", "id": "x"})
        tampered = code_module().to_dict()
        tampered["source_sha256"] = "0" * 64
        with self.assertRaises(ContractError):
            artifact_from_dict(tampered)

    def test_episode_result_records_outcome(self):
        episode = EpisodeResult(
            episode_id="ep",
            outcome=Outcome.FAILED,
            program_id="prog_pick",
            program_sha256=SHA,
            snapshot_id="snap_1",
            initial_state_sha256=SHA,
            final_state_sha256="cd" * 32,
            failure_code="GRASP_MISS",
            failed_op="close_hand",
            failed_step=2,
            replans=1,
            events=[{"code": "GRASP_MISS"}],
            attempts=[{"index": 0}],
            degraded=False,
            agent_usage={"calls": 1},
        )
        self.assertEqual(episode.to_dict()["outcome"], "failed")
        self.assertEqual(episode.to_dict()["failed_step"], 2)


def code_module_with_imports(imports: tuple[str, ...]) -> CodeModule:
    return CodeModule(
        id="reach_v1",
        version=1,
        scope=scope(),
        status=Status.CANDIDATE,
        source="def act(observation, task, state):\n    return {}\n",
        allowed_imports=imports,
    )


if __name__ == "__main__":
    unittest.main()
