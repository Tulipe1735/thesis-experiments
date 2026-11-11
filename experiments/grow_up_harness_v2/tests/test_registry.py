"""Registry: content addressing, snapshot chain, promotion, and projections."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from harness.contracts import (
    CodeModule,
    ContractError,
    MemoryNote,
    Op,
    Predicate,
    Procedure,
    Scope,
    Skill,
    Status,
    Step,
    Validation,
    ValidationReport,
)
from harness.ops import SMALL_OPS, make_builtin_ops, make_candidate_ops, make_op, spec
from harness.registry import Registry

SHA = "ab" * 32
OTHER_SHA = "cd" * 32


def scope() -> Scope:
    return Scope("TP01", frozenset({"cup"}))


def ref_id(artifact) -> str:
    if isinstance(artifact, Op):
        return artifact.op_id
    return artifact.id


def module(source: str = "def act(observation, task, state):\n    return {}\n", **overrides) -> CodeModule:
    values = dict(
        id="reach_v1",
        version=1,
        scope=scope(),
        status=Status.CANDIDATE,
        source=source,
        allowed_imports=("math",),
    )
    values.update(overrides)
    return CodeModule(**values)


def reach(version: int = 1, status: Status = Status.CANDIDATE, evidence: tuple[str, ...] = (), **overrides) -> Op:
    code = module()
    values = dict(
        spec=spec("reach_target"),
        scope=scope(),
        status=status,
        implementation=code.id,
        implementation_sha256=code.source_sha256,
        evidence=evidence,
        version=version,
    )
    values.update(overrides)
    return make_op(**values)


def skill(**overrides) -> Skill:
    values = dict(
        id="grasp",
        version=1,
        scope=scope(),
        status=Status.CANDIDATE,
        validation=None,
        steps=(Step("close_hand"),),
        pre=(Predicate("palm_near_target"), Predicate("hand_open")),
        post=(Predicate("grasp_contact"), Predicate("hand_open")),
        on_failure=(("GRASP_MISS", "regrasp"), ("CHECK_FAILED", "check")),
        evidence=("ep_fail",),
    )
    values.update(overrides)
    return Skill(**values)


def report_for(artifact, decision: str = "promote", report_id: str = "val_1", **overrides) -> ValidationReport:
    values = dict(
        id=report_id,
        candidate_id=ref_id(artifact),
        candidate_digest=artifact.digest(),
        validation=Validation.REPAIR_LINEAGE,
        protocol="repair_lineage_v1",
        baseline_episode="ep_fail",
        treatment_episode="ep_fix",
        initial_state_sha256=OTHER_SHA,
        metrics=(("stable_s", 1.2),),
        contract_tests=(("pre", True), ("post", True), ("failure_codes", True)),
        regression=(("audit", True),),
        decision=decision,
        evidence=("ep_fail", "ep_fix"),
        created_at="2026-11-03T00:00:00Z",
    )
    values.update(overrides)
    return ValidationReport(**values)


def snapshot_id(refs, label: str, parent: str | None = None, frozen: bool = False) -> str:
    ordered = tuple(sorted(refs))
    payload = {
        "refs": [[artifact_id, digest] for artifact_id, digest in ordered],
        "parent": parent,
        "label": label,
        "frozen": frozen,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "snap_" + hashlib.sha256(raw).hexdigest()[:16]


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.registry = Registry(self.root)

    def seal(self, artifacts, label: str = "base", parent: str | None = None):
        refs = []
        for artifact in artifacts:
            refs.append((ref_id(artifact), self.registry.put(artifact)))
        return self.registry.commit(refs, label=label, parent=parent)

    def test_put_get_latest_and_content_address(self):
        code = module()
        op_v1 = reach(version=1, evidence=("ep_v1",))
        op_v3 = reach(version=3, evidence=("ep_v3",))
        digest = self.registry.put(op_v1)
        self.assertEqual(digest, op_v1.digest())
        self.assertEqual(self.registry.put(code), code.digest())
        self.assertEqual(self.registry.put(op_v3), op_v3.digest())

        path = self.root / "artifacts" / "op" / f"{digest}.json"
        payload = op_v1.to_dict()
        payload["sha256"] = digest
        self.assertEqual(path.read_text(encoding="utf-8"), json.dumps(payload, sort_keys=True, indent=2) + "\n")
        self.assertEqual(self.registry.get_by_digest(digest).to_dict(), op_v1.to_dict())
        self.assertEqual(self.registry.get(op_v1.op_id, 1).to_dict(), op_v1.to_dict())
        self.assertEqual(self.registry.get(op_v1.op_id, 3).version, 3)
        self.assertEqual(self.registry.get(code.id, 1).source_sha256, code.source_sha256)
        self.assertEqual(self.registry.latest(op_v1.op_id).version, 3)
        with self.assertRaises(KeyError):
            self.registry.get(op_v1.op_id, 2)
        with self.assertRaises(KeyError):
            self.registry.get_by_digest(SHA)
        with self.assertRaises(KeyError):
            self.registry.latest("missing_op")

        again = self.registry.put(op_v1)
        self.assertEqual(again, digest)
        # Two versions were put above, so two content-addressed files exist.
        self.assertEqual(
            {item.name for item in (self.root / "artifacts" / "op").glob("*.json")},
            {f"{digest}.json", f"{op_v3.digest()}.json"},
        )

        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace('"candidate"', '"validated"', 1), encoding="utf-8")
        with self.assertRaises(ContractError):
            self.registry.put(op_v1)
        path.write_text(original, encoding="utf-8")

        copied = self.root / "artifacts" / "skill" / f"{digest}.json"
        copied.parent.mkdir()
        copied.write_text(original, encoding="utf-8")
        with self.assertRaises(ContractError) as ambiguous:
            self.registry.get_by_digest(digest)
        self.assertIn("ambiguous digest", str(ambiguous.exception))

    def test_same_id_and_version_is_ambiguous(self):
        first = reach(evidence=("ep_a",))
        second = reach(evidence=("ep_b",))
        self.assertEqual(first.op_id, second.op_id)
        self.assertEqual(first.version, second.version)
        self.assertNotEqual(first.digest(), second.digest())
        self.registry.put(first)
        self.registry.put(second)
        with self.assertRaises(ContractError) as got:
            self.registry.get(first.op_id, 1)
        self.assertIn("ambiguous", str(got.exception))
        with self.assertRaises(ContractError):
            self.registry.latest(first.op_id)
        self.assertEqual(self.registry.get_by_digest(first.digest()).evidence, ("ep_a",))
        self.assertEqual(self.registry.get_by_digest(second.digest()).evidence, ("ep_b",))

    def test_commit_load_parent_and_identity(self):
        op = reach()
        code = module()
        first = self.registry.put(op)
        second = self.registry.put(code)
        refs = [(code.id, second), (op.op_id, first), (op.op_id, first)]
        snap = self.registry.commit(refs, label="base")
        self.assertEqual(snap.id, snapshot_id([(op.op_id, first), (code.id, second)], "base"))
        self.assertEqual(snap.refs, tuple(sorted([(op.op_id, first), (code.id, second)])))
        self.assertIsNone(snap.parent)
        self.assertFalse(snap.frozen)
        loaded = self.registry.load(snap.id)
        self.assertEqual(loaded.artifacts[op.op_id].digest(), first)
        self.assertEqual(loaded.artifacts[code.id].digest(), second)
        self.assertIsNone(self.registry.head())

        with self.assertRaises(ContractError) as conflict:
            self.registry.commit([(op.op_id, first), (op.op_id, second)], label="conflict")
        self.assertIn("conflicting digests", str(conflict.exception))
        with self.assertRaises(KeyError):
            self.registry.commit([(op.op_id, first)], label="orphan", parent="snap_missing")

        child = self.registry.commit([(op.op_id, first)], label="child", parent=snap.id)
        self.assertEqual(child.parent, snap.id)
        self.assertEqual(child.id, snapshot_id([(op.op_id, first)], "child", parent=snap.id))

        alias = self.registry.commit([("not_the_op", first)], label="alias")
        with self.assertRaises(ContractError) as mismatch:
            self.registry.load(alias.id)
        self.assertIn("not_the_op", str(mismatch.exception))
        with self.assertRaises(KeyError):
            self.registry.load("snap_missing")

    def test_freeze_writes_head_and_rejects_a_second_freeze(self):
        op = reach()
        snap = self.seal([op])
        before = (self.root / "snapshots" / f"{snap.id}.json").read_bytes()
        frozen = self.registry.freeze(snap.id)
        self.assertEqual((self.root / "snapshots" / f"{snap.id}.json").read_bytes(), before)
        self.assertFalse(self.registry.load(snap.id).snapshot.frozen)
        self.assertTrue(frozen.frozen)
        self.assertEqual(frozen.parent, snap.id)
        self.assertEqual(frozen.label, f"freeze:{snap.id}")
        self.assertEqual(frozen.refs, snap.refs)
        self.assertEqual(frozen.id, snapshot_id(snap.refs, f"freeze:{snap.id}", parent=snap.id, frozen=True))

        head = json.loads(self.registry.head_path.read_text(encoding="utf-8"))
        frozen_path = self.root / "snapshots" / f"{frozen.id}.json"
        self.assertEqual(head["snapshot_id"], frozen.id)
        self.assertEqual(head["sha256"], hashlib.sha256(frozen_path.read_bytes()).hexdigest())
        self.assertFalse(self.registry.head_path.with_suffix(".json.tmp").exists())
        self.assertEqual(self.registry.head().id, frozen.id)
        self.assertTrue(self.registry.head().frozen)

        with self.assertRaises(ContractError) as again:
            self.registry.freeze(frozen.id)
        self.assertIn("frozen", str(again.exception))
        repeated = self.registry.freeze(snap.id)
        self.assertEqual(repeated.id, frozen.id)
        self.assertEqual(self.registry.head().id, frozen.id)

        other = self.registry.commit(snap.refs, label="other", parent=snap.id)
        moved = self.registry.freeze(other.id)
        self.assertEqual(self.registry.head().id, moved.id)
        self.assertNotEqual(moved.id, frozen.id)

    def test_frozen_snapshot_rejects_status_changes(self):
        op = reach(evidence=("ep_fail",))
        validation = report_for(op)
        snap = self.seal([op, validation])
        frozen = self.registry.freeze(snap.id)
        revised = reach(version=2, evidence=("ep_v2",))
        snapshots_before = {path.name for path in self.registry.snapshots_dir.glob("*.json")}
        artifacts_before = {path.name for path in self.registry.artifacts_dir.rglob("*.json")}
        with self.assertRaises(ContractError) as promoted:
            self.registry.promote(frozen.id, op.op_id, validation.id)
        with self.assertRaises(ContractError) as demoted:
            self.registry.demote(frozen.id, op.op_id, validation.id)
        with self.assertRaises(ContractError) as retired:
            self.registry.retire(frozen.id, op.op_id, validation.id)
        with self.assertRaises(ContractError) as revision:
            self.registry.add_revision(frozen.id, revised)
        for caught in (promoted, demoted, retired, revision):
            self.assertIn("frozen", str(caught.exception))
        self.assertEqual({path.name for path in self.registry.snapshots_dir.glob("*.json")}, snapshots_before)
        self.assertEqual({path.name for path in self.registry.artifacts_dir.rglob("*.json")}, artifacts_before)

    def test_promote_op_skill_and_memory_keeps_parent(self):
        op = reach(evidence=("ep_fail",))
        chosen = skill(evidence=("ep_fail",))
        note = MemoryNote(id="note_1", text="闭合前确认掌心附近", scope=scope(), status=Status.CANDIDATE, evidence=("ep_fail",))
        op_report = report_for(op, report_id="val_op", validation=Validation.REPAIR_LINEAGE)
        skill_report = report_for(chosen, report_id="val_skill", validation=Validation.PAIRED)
        note_report = report_for(note, report_id="val_note", validation=Validation.REPAIR_LINEAGE)
        snap = self.seal([op, chosen, note, op_report, skill_report, note_report])
        parent_bytes = (self.root / "snapshots" / f"{snap.id}.json").read_bytes()

        promoted_op = self.registry.promote(snap.id, op.op_id, op_report.id)
        self.assertEqual(parent_bytes, (self.root / "snapshots" / f"{snap.id}.json").read_bytes())
        self.assertEqual(promoted_op.parent, snap.id)
        self.assertEqual(promoted_op.label, "promote:reach_target:repair_lineage")
        op_view = self.registry.load(promoted_op.id)
        self.assertEqual(op_view.artifacts[op.op_id].status, Status.VALIDATED)
        self.assertEqual(op_view.artifacts[op.op_id].evidence, ("ep_fail", op_report.id))
        self.assertNotIn("validation", op_view.artifacts[op.op_id].to_dict())
        self.assertEqual(op_view.artifacts[chosen.id].status, Status.CANDIDATE)
        self.assertEqual(self.registry.load(snap.id).artifacts[op.op_id].status, Status.CANDIDATE)
        self.assertIsNone(self.registry.head())
        with self.assertRaises(ContractError):
            self.registry.get(op.op_id, 1)

        promoted_skill = self.registry.promote(promoted_op.id, chosen.id, skill_report.id)
        skill_view = self.registry.load(promoted_skill.id)
        self.assertEqual(promoted_skill.label, "promote:grasp:paired")
        self.assertEqual(skill_view.artifacts[chosen.id].status, Status.VALIDATED)
        self.assertEqual(skill_view.artifacts[chosen.id].validation, Validation.PAIRED)
        self.assertEqual(skill_view.artifacts[chosen.id].evidence, ("ep_fail", skill_report.id))
        self.assertEqual(skill_view.artifacts[op.op_id].status, Status.VALIDATED)

        promoted_note = self.registry.promote(snap.id, note.id, note_report.id)
        note_view = self.registry.load(promoted_note.id)
        self.assertEqual(note_view.artifacts[note.id].status, Status.VALIDATED)
        self.assertEqual(note_view.artifacts[note.id].evidence, ("ep_fail", note_report.id))
        self.assertNotIn("validation", note_view.artifacts[note.id].to_dict())
        self.assertEqual(self.registry.load(snap.id).artifacts[note.id].status, Status.CANDIDATE)

    def test_promote_rejects_missing_or_mismatched_reports(self):
        op = reach(evidence=("ep_fail",))
        good = report_for(op, report_id="val_good")
        wrong_decision = report_for(op, report_id="val_reject", decision="reject")
        wrong_id = report_for(op, report_id="val_id")
        wrong_id = replace(wrong_id, candidate_id="other_op")
        wrong_digest = report_for(op, report_id="val_digest")
        wrong_digest = replace(wrong_digest, candidate_digest=SHA)
        code = module()
        code_report = report_for(code, report_id="val_code")
        # A snapshot holds one version per artifact id, so the already-validated
        # case uses a different op instead of a second reach_target revision.
        validated = make_op(spec("hold_stable"), scope(), Status.VALIDATED, "reach_v1", module().source_sha256)
        validated_report = report_for(validated, report_id="val_done")
        snap = self.seal([op, good, wrong_decision, wrong_id, wrong_digest, code, code_report, validated, validated_report])

        cases = (
            ("missing", op.op_id, "val_missing", "report"),
            ("decision", op.op_id, wrong_decision.id, "decision"),
            ("candidate_id", op.op_id, wrong_id.id, "candidate_id"),
            ("digest", op.op_id, wrong_digest.id, "candidate_digest"),
            ("code", code.id, code_report.id, "code module"),
            ("status", validated.op_id, validated_report.id, "not a candidate"),
        )
        for name, candidate_id, report_id, needle in cases:
            with self.subTest(name=name):
                with self.assertRaises(ContractError) as caught:
                    self.registry.promote(snap.id, candidate_id, report_id)
                self.assertIn(needle, str(caught.exception))
        self.assertEqual((self.root / "snapshots" / f"{snap.id}.json").read_bytes(), (self.root / "snapshots" / f"{snap.id}.json").read_bytes())
        bare = self.seal([op], label="bare")
        with self.assertRaises(ContractError) as missing:
            self.registry.promote(bare.id, op.op_id, good.id)
        self.assertIn("report", str(missing.exception))

    def test_demote_and_retire(self):
        chosen = skill(evidence=("ep_fail",))
        promote_report = report_for(chosen, report_id="val_promote", validation=Validation.REPAIR_LINEAGE)
        snap = self.seal([chosen, promote_report])
        promoted = self.registry.promote(snap.id, chosen.id, promote_report.id)
        validated = self.registry.load(promoted.id).artifacts[chosen.id]
        demote_report = report_for(validated, decision="demote", report_id="val_demote")
        with_report = self.registry.add_revision(promoted.id, demote_report)
        with self.assertRaises(ContractError):
            self.registry.demote(with_report.id, chosen.id, promote_report.id)
        parent_bytes = (self.root / "snapshots" / f"{with_report.id}.json").read_bytes()
        demoted = self.registry.demote(with_report.id, chosen.id, demote_report.id)
        self.assertEqual(parent_bytes, (self.root / "snapshots" / f"{with_report.id}.json").read_bytes())
        self.assertEqual(demoted.parent, with_report.id)
        self.assertEqual(demoted.label, "demote:grasp")
        demoted_skill = self.registry.load(demoted.id).artifacts[chosen.id]
        self.assertEqual(demoted_skill.status, Status.CANDIDATE)
        self.assertIsNone(demoted_skill.validation)
        self.assertEqual(demoted_skill.evidence, ("ep_fail", promote_report.id, demote_report.id))

        op = reach(evidence=("ep_fail",))
        op_promote = report_for(op, report_id="val_op")
        op_snap = self.seal([op, op_promote], label="op")
        op_promoted = self.registry.promote(op_snap.id, op.op_id, op_promote.id)
        validated_op = self.registry.load(op_promoted.id).artifacts[op.op_id]
        retire_report = report_for(validated_op, decision="retire", report_id="val_retire")
        op_with_report = self.registry.add_revision(op_promoted.id, retire_report)
        retired = self.registry.retire(op_with_report.id, op.op_id, retire_report.id)
        retired_op = self.registry.load(retired.id).artifacts[op.op_id]
        self.assertEqual(retired.label, "retire:reach_target")
        self.assertEqual(retired_op.status, Status.RETIRED)
        self.assertEqual(retired_op.evidence, ("ep_fail", op_promote.id, retire_report.id))
        self.assertNotIn("validation", retired_op.to_dict())

        kept = skill(id="hold", evidence=("ep_fail",))
        kept_promote = report_for(kept, report_id="val_hold", validation=Validation.PAIRED)
        kept_snap = self.seal([kept, kept_promote], label="hold")
        kept_promoted = self.registry.promote(kept_snap.id, kept.id, kept_promote.id)
        validated_skill = self.registry.load(kept_promoted.id).artifacts[kept.id]
        kept_retire = report_for(validated_skill, decision="retire", report_id="val_hold_retire")
        kept_with_report = self.registry.add_revision(kept_promoted.id, kept_retire)
        retired_skill_snap = self.registry.retire(kept_with_report.id, kept.id, kept_retire.id)
        retired_skill = self.registry.load(retired_skill_snap.id).artifacts[kept.id]
        self.assertEqual(retired_skill.status, Status.RETIRED)
        self.assertEqual(retired_skill.validation, Validation.PAIRED)
        with self.assertRaises(ContractError):
            self.registry.demote(kept_snap.id, kept.id, kept_promote.id)

    def test_add_revision_replaces_by_id(self):
        op = reach(version=1, evidence=("v1",))
        builtin = make_builtin_ops(scope())[0]
        snap = self.seal([op, builtin])
        revised_op = reach(version=2, evidence=("v2",))
        revised = self.registry.add_revision(snap.id, revised_op)
        self.assertEqual(revised.parent, snap.id)
        self.assertEqual(revised.label, "revise:reach_target")
        self.assertEqual(self.registry.load(revised.id).artifacts[op.op_id].to_dict(), revised_op.to_dict())
        self.assertEqual(self.registry.load(revised.id).artifacts[builtin.op_id].digest(), builtin.digest())
        self.assertEqual(self.registry.load(snap.id).artifacts[op.op_id].version, 1)
        self.assertEqual(self.registry.latest(op.op_id).version, 2)

    def test_op_table_formal_practice_and_latest_version(self):
        candidate = reach(version=1)
        builtins = make_builtin_ops(scope())
        retired = make_op(
            spec("lift_target"),
            scope(),
            Status.RETIRED,
            implementation="code_lift",
            implementation_sha256=SHA,
        )
        snap = self.seal([candidate, retired, *builtins])
        formal = self.registry.op_table(snap.id)
        practice = self.registry.op_table(snap.id, mode="practice")
        self.assertEqual(set(formal), {"open_hand", "check"})
        self.assertTrue(all(op.status is Status.VALIDATED for op in formal.values()))
        self.assertEqual(set(practice), {"open_hand", "check", "reach_target"})
        self.assertEqual(practice["reach_target"].version, 1)
        self.assertNotIn("lift_target", formal)
        self.assertNotIn("lift_target", practice)
        with self.assertRaises(ContractError):
            self.registry.op_table(snap.id, mode="draft")

        revised = reach(version=3, evidence=("later",))
        updated = self.registry.add_revision(snap.id, revised)
        self.assertEqual(self.registry.op_table(updated.id, mode="practice")["reach_target"].version, 3)
        self.assertEqual(self.registry.op_table(snap.id, mode="practice")["reach_target"].version, 1)
        self.assertEqual(self.registry.latest("reach_target").version, 3)
        self.assertNotIn("reach_target", self.registry.op_table(snap.id))

    def test_code_projection_resolves_by_source_hash(self):
        modules = []
        implementations = {}
        for item in SMALL_OPS:
            code = module(
                source=f"def act(observation, task, state):\n    return {{'name': '{item.op_id}'}}\n",
                id=f"code_{item.op_id}",
            )
            modules.append(code)
            implementations[item.op_id] = (code.id, code.source_sha256)
        ops = make_candidate_ops(SMALL_OPS, scope(), implementations)
        builtins = make_builtin_ops(scope())
        snap = self.seal([*modules, *ops, *builtins])
        projection = self.registry.code_projection(snap.id)
        self.assertEqual(set(projection), {item.op_id for item in SMALL_OPS})
        for op in ops:
            self.assertIsInstance(projection[op.op_id], CodeModule)
            self.assertEqual(projection[op.op_id].id, op.implementation)
            self.assertEqual(projection[op.op_id].source_sha256, op.implementation_sha256)
        self.assertNotIn("open_hand", projection)
        self.assertNotIn("check", projection)

        orphan = make_op(spec("close_hand"), scope(), Status.CANDIDATE, "missing_module", SHA)
        missing = self.seal([orphan], label="missing")
        with self.assertRaises(KeyError):
            self.registry.code_projection(missing.id)

        hashed = modules[0]
        self.assertNotEqual(hashed.source_sha256, SHA)
        mismatched = make_op(spec("locate_target"), scope(), Status.CANDIDATE, hashed.id, SHA)
        wrong_hash = self.seal([hashed, mismatched], label="hash")
        with self.assertRaises(KeyError):
            self.registry.code_projection(wrong_hash.id)

    def test_skill_graph_pre_post_and_repair_edges(self):
        grasp = skill()
        regrasp = skill(
            id="regrasp",
            pre=(Predicate("hand_empty"),),
            post=(Predicate("grasp_contact"),),
            on_failure=(),
            evidence=(),
        )
        lift = Procedure(
            id="lift",
            version=1,
            scope=scope(),
            status=Status.CANDIDATE,
            validation=None,
            skill_ids=("grasp",),
            steps=(Step("lift_target"),),
            pre=(Predicate("grasp_contact"), Predicate("hand_open")),
            post=(Predicate("target_lifted"),),
        )
        check = make_builtin_ops(scope())[1]
        self.assertEqual(check.op_id, "check")
        snap = self.seal([grasp, regrasp, lift, check])
        self.assertEqual(
            self.registry.skill_graph(snap.id),
            {
                "nodes": [
                    {"id": "grasp", "kind": "skill"},
                    {"id": "lift", "kind": "procedure"},
                    {"id": "regrasp", "kind": "skill"},
                ],
                "edges": [
                    {"from": "grasp", "to": "lift", "kind": "pre_post", "predicate": "grasp_contact"},
                    {"from": "grasp", "to": "lift", "kind": "pre_post", "predicate": "hand_open"},
                    {"from": "regrasp", "to": "lift", "kind": "pre_post", "predicate": "grasp_contact"},
                    {"from": "grasp", "to": "regrasp", "kind": "repair", "failure_code": "GRASP_MISS"},
                ],
            },
        )

    def test_verify_catches_tamper_missing_snapshot_and_head(self):
        op = reach()
        snap = self.seal([op])
        self.assertEqual(self.registry.verify(snap.id), {"ok": True, "problems": []})
        frozen = self.registry.freeze(snap.id)
        self.assertEqual(self.registry.verify(frozen.id), {"ok": True, "problems": []})

        artifact_path = self.root / "artifacts" / "op" / f"{op.digest()}.json"
        original = artifact_path.read_text(encoding="utf-8")
        artifact_path.write_text(original.replace('"candidate"', '"validated"', 1), encoding="utf-8")
        tampered = self.registry.verify(snap.id)
        self.assertFalse(tampered["ok"])
        self.assertTrue(any("digest" in problem for problem in tampered["problems"]))
        with self.assertRaises(ContractError):
            self.registry.load(snap.id)
        artifact_path.write_text(original, encoding="utf-8")
        self.assertTrue(self.registry.verify(snap.id)["ok"])

        head_text = self.registry.head_path.read_text(encoding="utf-8")
        self.registry.head_path.write_text(head_text.replace(frozen.id, "snap_" + "0" * 16, 1), encoding="utf-8")
        # Replacing the id also makes the stored file hash point at a different name.
        bad_head = self.registry.verify(snap.id)
        self.assertFalse(bad_head["ok"])
        self.assertTrue(any("head" in problem for problem in bad_head["problems"]))
        with self.assertRaises(ContractError):
            self.registry.head()
        self.registry.head_path.write_text(head_text, encoding="utf-8")

        missing = self.registry.verify("snap_missing")
        self.assertEqual(missing, {"ok": False, "problems": ["missing snapshot: snap_missing"]})

        child = self.registry.commit(snap.refs, label="child", parent=snap.id)
        (self.root / "snapshots" / f"{snap.id}.json").unlink()
        orphaned = self.registry.verify(child.id)
        self.assertFalse(orphaned["ok"])
        self.assertTrue(any("missing parent" in problem for problem in orphaned["problems"]))

        cycle_a = self.root / "snapshots" / "snap_cycle_a.json"
        cycle_b = self.root / "snapshots" / "snap_cycle_b.json"
        cycle_a.write_text(json.dumps({"id": "snap_cycle_a", "refs": [], "parent": "snap_cycle_b", "label": "cycle", "frozen": False}))
        cycle_b.write_text(json.dumps({"id": "snap_cycle_b", "refs": [], "parent": "snap_cycle_a", "label": "cycle", "frozen": False}))
        cycled = self.registry.verify("snap_cycle_a")
        self.assertFalse(cycled["ok"])
        self.assertTrue(any("cycle" in problem for problem in cycled["problems"]))
