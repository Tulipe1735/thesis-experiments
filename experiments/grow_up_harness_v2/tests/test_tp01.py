"""TP01 case loading, the public observation and the runtime-only state."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness import predicates
from harness.contracts import EVALUATOR_ONLY_KEYS, OBSERVATION_KEYS, Observation

try:
    import mujoco  # noqa: F401
    from harness import tp01
except ImportError as exc:  # pragma: no cover - environment gate
    tp01 = None
    SKIP_REASON = f"MuJoCo is unavailable: {exc}"
else:
    SKIP_REASON = ""

HAND_JOINTS = (
    "left_hand_thumb_0_joint",
    "left_hand_thumb_1_joint",
    "left_hand_thumb_2_joint",
    "left_hand_middle_0_joint",
    "left_hand_middle_1_joint",
    "left_hand_index_0_joint",
    "left_hand_index_1_joint",
)
OPEN_ANGLES = (0.0,) * 7
CLOSED_ANGLES = (0.0, 0.65, 0.65, -0.8, -0.6, -0.8, -0.6)

PERCEPTION = {
    "target_depth_valid": True,
    "target_points": 100,
    "target_estimate": [0.3, 0.2, 0.96],
    "confidence": 0.9,
}


def require_tp01(test: unittest.TestCase) -> None:
    if tp01 is None:
        raise unittest.SkipTest(SKIP_REASON)


class JointPlant:
    """Minimal plant surface for the pure hand-aperture calculation."""

    def __init__(self, angles):
        self.angles = tuple(angles)

    def observation(self) -> dict:
        return {
            "joints": {
                name: {"q": angle}
                for name, angle in zip(HAND_JOINTS, self.angles)
            }
        }


class ReachCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        require_tp01(cls)
        cls.cases = tp01.load_cases(tp01.REACH_DATASET)

    def test_four_frozen_reach_cases(self) -> None:
        self.assertEqual(len(self.cases), 4)
        self.assertEqual(
            [case.instance_id for case in self.cases],
            [f"TP01_reach_train_{index:03d}" for index in range(4)],
        )
        for case in self.cases:
            with self.subTest(case=case.alias):
                self.assertEqual(case.task.id, case.instance_id)
                self.assertEqual(case.task.template, "TP01")
                self.assertEqual(case.task.split, "train")
                self.assertEqual(case.task.budget_s, 60.0)
                self.assertEqual(case.task.goal.name, "HeldLifted")
                self.assertEqual(dict(case.task.goal.params)["object"], case.target)
                self.assertIn(case.target_category, {"cup", "fruit", "bottle"})

    def test_case_hashes_match_frozen_manifest(self) -> None:
        dataset = tp01.REACH_DATASET
        manifest = json.loads(
            (dataset / "training_manifest.json").read_text(encoding="utf-8")
        )
        frozen = json.loads(
            (dataset / "freeze_manifest.json").read_text(encoding="utf-8")
        )
        rows = {row["id"]: row for row in manifest["instances"]}
        for case in self.cases:
            with self.subTest(case=case.alias):
                row = rows[case.instance_id]
                self.assertEqual(case.initial_state_sha256, row["initial_state_sha256"])
                self.assertEqual(case.valid_initial_fixture, row["valid_initial_fixture"])
                self.assertEqual(
                    case.qualification_sha256,
                    frozen["artifacts"][f"train/{case.instance_id}/qualification.xml"],
                )


class HandApertureTests(unittest.TestCase):
    def test_reference_open_state_is_one(self) -> None:
        require_tp01(self)
        self.assertEqual(tp01.hand_open_fraction(JointPlant(OPEN_ANGLES)), 1.0)

    def test_reference_closed_pose_is_zero(self) -> None:
        require_tp01(self)
        self.assertEqual(tp01.hand_open_fraction(JointPlant(CLOSED_ANGLES)), 0.0)

    def test_half_closed_joint_sets_the_minimum(self) -> None:
        require_tp01(self)
        angles = list(OPEN_ANGLES)
        angles[3] = -0.4  # middle_0 is half of its -0.8 reference closure
        self.assertAlmostEqual(tp01.hand_open_fraction(JointPlant(angles)), 0.5)

    def test_wider_open_than_rest_still_reads_fully_open(self) -> None:
        require_tp01(self)
        # thumb_1 legally travels to -0.611; that is more open than rest, not
        # less, so it must clamp at 1.0 rather than lower the minimum.
        angles = list(OPEN_ANGLES)
        angles[1] = -0.45
        self.assertEqual(tp01.hand_open_fraction(JointPlant(angles)), 1.0)

    def test_past_the_closed_pose_is_not_negative(self) -> None:
        require_tp01(self)
        angles = list(CLOSED_ANGLES)
        angles[4] = -0.9  # beyond middle_1's -0.6 reference closure
        self.assertEqual(tp01.hand_open_fraction(JointPlant(angles)), 0.0)


class LivePlantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        require_tp01(cls)
        cls.case = tp01.load_cases(tp01.REACH_DATASET)[0]

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="tp01-plant-")
        root = Path(self.temp.name)
        output = root / "episode"
        output.mkdir()
        self.output = output
        model = tp01.build_scene(self.case, root / "scene.xml")
        self.plant = tp01.make_plant(self.case, model, output)

    def tearDown(self) -> None:
        renderer = getattr(self.plant, "renderer", None)
        if renderer is not None:
            renderer.close()
        self.temp.cleanup()

    def test_observation_carries_only_public_keys(self) -> None:
        observation = tp01.observation(self.plant)
        self.assertIsInstance(observation, Observation)
        self.assertEqual(observation.time, 0.0)
        self.assertLessEqual(set(observation.payload), OBSERVATION_KEYS)
        self.assertFalse(set(observation.payload) & EVALUATOR_ONLY_KEYS)
        self.assertEqual(observation.payload["simulation_seconds"], observation.time)
        self.assertIn("rgbd", observation.payload)

    def test_step_state_is_clear_open_and_empty(self) -> None:
        state = tp01.step_state(self.plant, self.case, PERCEPTION)
        self.assertTrue(predicates.evaluate("guard_clear", state))
        self.assertTrue(predicates.evaluate("hand_empty", state))
        self.assertTrue(predicates.evaluate("hand_open", state))
        self.assertIn("palm", state)
        self.assertIn("objects", state)
        self.assertEqual(state["target"], self.case.target)
        self.assertEqual(state["protection"], self.plant.guard)
        self.assertEqual(state["perception"], PERCEPTION)
        self.assertEqual(state["palm"]["frame"], "current_pelvis")
        target = state["objects"][self.case.target]
        self.assertEqual(target["frame"], "current_pelvis")
        self.assertEqual(len(target["pelvis_position_m"]), 3)
        self.assertFalse(predicates.evaluate("palm_near_target", state))

    def test_step_state_mixed_frame_raises(self) -> None:
        state = tp01.step_state(self.plant, self.case, PERCEPTION)
        state["objects"][self.case.target]["frame"] = "world"
        with self.assertRaises(predicates.PredicateUnavailable):
            predicates.evaluate("palm_near_target", state)

    def test_state_hash_matches_saved_last_frame(self) -> None:
        import hashlib

        import numpy as np

        from harness.runtime import state_hash

        self.plant.dispatch({"op": "wait", "duration": 0.2})
        self.plant.save(None, None, None, 0)
        self.plant.renderer = None
        with np.load(self.output / "integration_states.npz") as trace:
            last = trace["integration_state"][-1]
        expected = hashlib.sha256(np.ascontiguousarray(last).tobytes()).hexdigest()
        self.assertEqual(state_hash(self.plant), expected)


if __name__ == "__main__":
    unittest.main()
