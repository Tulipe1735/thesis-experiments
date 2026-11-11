"""Local artifact execution must not bypass the common joint boundary."""

import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

from harness.tp01 import t01_joint_dispatch
from harness.contracts import MemoryNote, Scope, Status
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "calibration"))
from local_artifact_cycle import local_action, prompt


class Robot:
    def __init__(self):
        self.data = SimpleNamespace(time=1.)
        self.calls = []
        self.guard = None

    def state(self):
        return {"simulation_seconds": self.data.time,
                "joints": {"left_elbow_joint": {"q": -.2, "target": .2},
                           "right_elbow_joint": {"q": .2, "target": .2}},
                "palms": {"left": {"position_m": [0., 0., 0.]}},
                "approximate_contact_load_N": {"left": {}}, "controller": {"guard": None}}

    def set_joints(self, targets, duration):
        self.calls.append((targets, duration))
        return {"status": "EXECUTED"}


class LocalJointTests(unittest.TestCase):
    def test_wire_action_requires_op_and_never_translates_type(self):
        with self.assertRaisesRegex(ValueError, "action.op"):
            local_action({"action": {"type": "set_joints", "targets": {}, "duration": .2}, "state": {}})
        self.assertEqual(local_action({"action": {"op": "done"}, "state": {}}), {"op": "done"})

    def test_external_memory_is_exposed_as_unvalidated_prior(self):
        note = MemoryNote("mem_external", "[EXTERNAL PRIOR - NOT LOCALLY VALIDATED] rule",
                          Scope("T01", frozenset({"cup"}), "external_prior"), Status.CANDIDATE,
                          ("https://example.invalid/source",))
        packet = prompt({"local_contract": {}, "body_geometry": {}, "budget": {}}, {}, memories=[note])
        self.assertEqual(packet["external_skill_memory"][0]["status"], "candidate")
        self.assertIn("NOT LOCALLY VALIDATED", packet["external_skill_memory"][0]["text"])
        self.assertIn("unvalidated prior", packet["rules"][-1])

    def test_author_receives_exact_runtime_argument_and_action_shapes(self):
        packet = prompt({"local_contract": {"position_m": [0, 0, 0]},
                         "body_geometry": {"chain_from_pelvis": [], "palm_site": {}},
                         "budget": {}}, {})
        bindings = packet["runtime_bindings"]
        self.assertIn("no task.contract", bindings["task_argument_to_act"])
        self.assertIn("top level", bindings["profile_argument_to_init"])
        for example in bindings["exact_action_examples"]:
            local_action(example)
        self.assertTrue(any("staged state" in rule for rule in packet["rules"]))
        self.assertTrue(any("simulation_seconds" in rule for rule in packet["rules"]))

    def test_delta_is_from_controller_target_not_measured_angle(self):
        robot = Robot()
        # q differs by 0.4 rad from target: a small target adjustment is legal.
        t01_joint_dispatch(robot, {"op": "set_joints", "targets": {"left_elbow_joint": .22},
                                  "duration": .2}, deadline=30.)
        self.assertEqual(len(robot.calls), 1)
        # A command near q but far from the standing target must be refused.
        with self.assertRaisesRegex(ValueError, "DELTA"):
            t01_joint_dispatch(robot, {"op": "set_joints", "targets": {"left_elbow_joint": -.18},
                                      "duration": .2}, deadline=30.)
        self.assertEqual(len(robot.calls), 1)

    def test_hidden_high_level_or_other_side_cannot_execute(self):
        robot = Robot()
        for action in ({"op": "move_ee", "duration": .2},
                       {"op": "set_joints", "targets": {"right_elbow_joint": .22}, "duration": .2}):
            with self.assertRaises(ValueError):
                t01_joint_dispatch(robot, action, deadline=30.)
        self.assertFalse(robot.calls)

    def test_budget_refusal_occurs_before_any_actuation(self):
        robot = Robot()
        with self.assertRaisesRegex(ValueError, "BUDGET"):
            t01_joint_dispatch(robot, {"op": "set_joints", "targets": {"left_elbow_joint": .22},
                                      "duration": .2}, deadline=1.1)
        self.assertFalse(robot.calls)


if __name__ == "__main__":
    unittest.main()
