"""Control semantics must survive both projections of the same IR."""

import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from harness import artifact as a
from harness.contracts import CodeModule, Op, Predicate, Scope, Skill, Status, Step
from harness.registry import Registry


class ProjectionTests(unittest.TestCase):
    def test_local_submission_projects_exact_pinned_source_without_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = Registry(Path(os.path.relpath(root / "registry")))
            registration = root / "registration.json"
            registration.write_text(json.dumps({"local_contract": {"hold_s": 1.}, "dependencies": {}}))
            scope = Scope("T01_LOCAL_CLEARANCE", frozenset({"cup"}), "initial_sha256:" + "a" * 64)
            code = CodeModule("local_code", 1, scope, Status.CANDIDATE,
                              'def act(observation, task, state):\n    return {"action": {"op": "done"}, "state": state}\n',
                              ("math", "numpy"))
            op = Op("local_clearance", 1, scope, Status.CANDIDATE,
                    (Predicate("hand_empty"), Predicate("hand_open"), Predicate("guard_clear")),
                    (Predicate("ExplicitPoseHeld"),), 30., ("POSE_NOT_REACHED",),
                    implementation=code.id, implementation_sha256=code.source_sha256,
                    dependencies=("registration:" + a._sha(registration),))
            skill = Skill("local_skill", 1, scope, Status.CANDIDATE, None, (Step(op.op_id),),
                          op.pre, op.post)
            snap = registry.commit([(code.id, registry.put(code)), (op.op_id, registry.put(op)),
                                    (skill.id, registry.put(skill))], label="candidate")
            with patch.object(a, "ROOT", root):
                # Generator itself is outside the temporary root, but local
                # projection only hashes it; no runtime path is fabricated.
                manifest = a.compile_local_skill(registry, snap.id, skill.id,
                                                  root / "projection", registration)
            self.assertEqual((root / "projection/program.py").read_text(), code.source)
            self.assertEqual(manifest["artifact"]["digest"], skill.digest())
            self.assertIn("ExplicitPoseHeld", (root / "projection/SKILL.md").read_text())
            self.assertEqual(registry.op_table(snap.id, "formal"), {})
            registration.write_text(json.dumps({"local_contract": {"hold_s": 2.}, "dependencies": {}}))
            with patch.object(a, "ROOT", root), self.assertRaisesRegex(ValueError, "bound physical contract"):
                a.compile_local_skill(registry, snap.id, skill.id, root / "wrong_contract", registration)
            self.assertFalse((root / "wrong_contract").exists())

    def test_orientation_is_distinguishable_for_every_motion(self):
        for cls, op, extra in ((a.WalkTo, "walk_to", {}), (a.MoveTo, "move_to", {}),
                               (a.LineTo, "line_to", {"seconds": 2.0})):
            keep = cls(op=op, to=a.LiteralPoint(literal=(-.07, .34, .09)),
                       yaw=a.YawLiteral(literal=0), orientation="keep", **extra)
            yaw = keep.model_copy(update={"orientation": "yaw"})
            with self.subTest(op=keep.op):
                self.assertNotEqual(a._emit(keep, ""), a._emit(yaw, ""))
                self.assertNotEqual(a._describe(keep), a._describe(yaw))
                self.assertIn("keep", a._describe(keep))
                self.assertIn("yaw", a._describe(yaw))

    def test_required_parameters_are_rejected_at_load(self):
        record = a.load(Path(a.ROOT) / "experiments/grow_up_harness_v2/artifacts/t01_cup_to_tray.yaml")
        for key in ("step_m", "place_above_m", "place_lower_m"):
            data = record.model_dump(mode="json")
            del data["ir"]["parameters"][key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                a.Artifact.model_validate(data)

    def test_checked_in_projection_matches_generator_and_manifest(self):
        artifact_path = Path(a.ROOT) / "experiments/grow_up_harness_v2/artifacts/t01_cup_to_tray.yaml"
        record = a.load(artifact_path)
        code_path = Path(a.ROOT) / record.projections.code.path
        self.assertEqual(code_path.read_text(encoding="utf-8"), a.generate_code(record))
        manifest = json.loads((code_path.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["artifact"]["digest"], a.digest(record))
        for path, digest in manifest["generated"].items():
            self.assertEqual(a._sha(Path(a.ROOT) / path), digest, path)

    def test_line_to_projects_to_move_linear_from_actual_palm(self):
        step = a.LineTo(op="line_to", to=a.LiteralPoint(literal=(.1, .2, .3)),
                        yaw=a.YawLiteral(literal=.7), seconds=2.0)
        emitted = "\n".join(a._emit(step, ""))
        self.assertIn("'op': 'move_linear'", emitted)
        self.assertNotIn("_walk", emitted)

    def test_linear_execution_uses_move_linear_for_lift_and_descent(self):
        steps = (
            a.RaiseClear(op="raise_clear", clearance_m=a.ParamRef(param="vertical_clear_m"),
                         yaw=a.YawGrasp(grasp=True), execution="linear"),
            a.DescendToLower(op="descend_to_lower", height_m=a.ParamRef(param="place_lower_m"),
                             yaw=a.YawGrasp(grasp=True), execution="linear"),
            a.WalkTo(op="walk_to", to=a.PlacePoint(place="above"),
                     yaw=a.YawGrasp(grasp=True), execution="linear"),
        )
        for step in steps:
            with self.subTest(op=step.op):
                emitted = "\n".join(a._emit(step, ""))
                self.assertIn("move_linear", emitted)
                self.assertNotIn("_walk", emitted)
        default = a.RaiseClear(op="raise_clear", clearance_m=a.ParamRef(param="vertical_clear_m"),
                               yaw=a.YawGrasp(grasp=True))
        self.assertIn("_walk", "\n".join(a._emit(default, "")))

    def test_card_defines_runtime_bindings_and_resolved_parameters(self):
        record = a.load(Path(a.ROOT) / "experiments/grow_up_harness_v2/artifacts/t01_cup_to_tray.yaml")
        card = a.generate_skill(record)
        for text in ("grasp =", "params =", "P =", "CLOSE =", "OPEN =", "SLOTS =",
                     "grasp_xyz_m", "approach_start_xyz_m", "cup_in_palm_m", "tray_floor_m"):
            self.assertIn(text, card)
        for key, value in record.ir.parameters.items():
            self.assertIn(f"'{key}': {value!r}", card)


if __name__ == "__main__":
    unittest.main()
