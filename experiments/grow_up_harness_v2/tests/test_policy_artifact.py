"""A policy checkpoint, code view and skill view share one registry record."""

import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from harness import policy_artifact
from harness.contracts import (
    PolicyArtifact, Predicate, Scope, Status, Validation, artifact_from_dict,
)
from harness.registry import Registry


def make_policy(root: Path, *, status=Status.CANDIDATE, validation=None) -> PolicyArtifact:
    checkpoint = root / "model.safetensors"
    checkpoint.write_bytes(b"checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    return PolicyArtifact(
        id="policy_cup_fourview_sft", version=1,
        scope=Scope("P01", frozenset({"DH_2F_mug_06"}), "pregrasp_to_grasp"),
        status=status, validation=validation,
        checkpoint={"path": str(checkpoint), "sha256": digest},
        policy_type="smolvla_flow_matching",
        observation_keys=("observation.state", "observation.images.cam_left_high"),
        action={"joint_names": ("left_hand_thumb_1_joint",), "units": "absolute_rad",
                "horizon": 50, "fps": 30.0},
        training={"dataset_path": "datasets/cup_fourview_v1",
                  "dataset_sha256": "a" * 64, "train_episodes": (0, 1, 2, 3),
                  "validation_episodes": (4, 5), "objective": "flow_matching_il",
                  "optimizer_steps": 700, "selected_step": 300, "seed": 20261024},
        evaluation={"official_evaluator": "verify_grasp.py",
                    "dense_evaluator": "not_available_for_p01",
                    "initial_states": ("episodes/demo_1000/pregrasp_state.npz",),
                    "metrics": ("HeldLifted", "max_lift_m")},
        pre=(Predicate("target_visible"), Predicate("hand_empty"), Predicate("guard_clear")),
        post=(Predicate("target_stable"),),
        failure_codes=("LEFT_PALM_DEPARTURE_CLOSING", "GRIP_LOST"),
        evidence=("training_result.json",), limits=("candidate; 0/4 new positions",),
    )


class PolicyArtifactTests(unittest.TestCase):
    def test_candidate_cannot_claim_validation(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            make_policy(Path(directory), validation=Validation.PAIRED)

    def test_projection_is_one_record_with_checkpoint_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = make_policy(root)
            code = policy_artifact.generate_code(policy)
            card = policy_artifact.generate_skill(policy)
            self.assertIn(policy.checkpoint["sha256"], code)
            self.assertIn("observation.state", code)
            self.assertIn("candidate", card)
            self.assertEqual(artifact_from_dict(policy.to_dict()).digest(), policy.digest())

    def test_code_view_validates_observation_and_delegates(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = make_policy(Path(directory))
            namespace = {}
            exec(compile(policy_artifact.generate_code(policy), "<policy>", "exec"), namespace)
            calls = []

            class Runtime:
                def predict(self, path, observation, names, horizon):
                    calls.append((path, observation, names, horizon))
                    return {"actions": [[0.0]]}

            observation = {"observation.state": [0.0], "observation.images.cam_left_high": "x"}
            self.assertEqual(namespace["act"](Runtime(), observation)["actions"], [[0.0]])
            self.assertEqual(calls[0][2], ("left_hand_thumb_1_joint",))
            with self.assertRaisesRegex(ValueError, "missing observation"):
                namespace["act"](Runtime(), {"observation.state": [0.0]})

    def test_parameterized_controller_projects_its_parameter_file(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = make_policy(Path(directory))
            policy = replace(policy, policy_type="parameterized_visual_tactile_controller",
                             checkpoint={**policy.checkpoint,
                                         "parameters": {"step_m": .015, "closure": "thumb_lead"}})
            code = policy_artifact.generate_code(policy)
            self.assertIn("PARAMS", code)
            self.assertIn("thumb_lead", code)
            self.assertIn("VisionGraspV3", code)

    def test_registry_stores_policy_without_turning_it_into_a_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = Registry(root / "registry")
            policy = make_policy(root)
            snapshot = registry.commit([(policy.id, registry.put(policy))], label="policy")
            frozen = registry.freeze(snapshot.id)
            loaded = registry.get_by_digest(policy.digest())
            self.assertIsInstance(loaded, PolicyArtifact)
            self.assertEqual(loaded.status, Status.CANDIDATE)
            self.assertEqual(registry.op_table(frozen.id, "formal"), {})
            self.assertEqual(registry.skill_graph(frozen.id), {"nodes": [], "edges": []})
            output = root / "projection"
            manifest = policy_artifact.compile_policy(policy, output)
            self.assertEqual(manifest["artifact"]["digest"], policy.digest())
            self.assertTrue((output / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
