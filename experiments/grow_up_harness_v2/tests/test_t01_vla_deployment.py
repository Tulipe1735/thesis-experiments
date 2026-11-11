"""Deployment exits must preserve held targets and stop rejected prepositioning."""

from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "calibration"))
from t01_vla_policy import joint_targets
from t01_vla_prepose import ClearanceRobot, preposition
from check_vla_prepose_clearance import check


class DeploymentContractTests(unittest.TestCase):
    def test_clearance_report_is_json_serializable_when_all_gates_pass(self):
        robot = ClearanceRobot.__new__(ClearanceRobot)
        robot.model = SimpleNamespace(opt=SimpleNamespace(timestep=0.002))
        robot.max_tray_contact = robot.max_tray_translation = robot.max_tray_yaw = 0.0
        robot.peak_contact_time = None
        report = robot.clearance_report()
        encoded = json.dumps(report, allow_nan=False)
        self.assertIs(json.loads(encoded)["passed"], True)

    def test_recorded_ready_posture_is_rejected_for_pushing_the_tray(self):
        root = Path(__file__).resolve().parents[3]
        run = root / "experiments/grow_up_harness_v2/runs/t01_vla_safe_prepose_20261106_001"
        result = check(run)
        self.assertTrue(result["prepose_ready"], "fixture must isolate tray disturbance from pose failure")
        self.assertFalse(result["passed"])
        self.assertGreater(result["max_sampled_tray_hand_contact_N"], 9.)
        self.assertGreater(result["tray_planar_displacement_m"], 0.01)

    def test_tracking_exit_keeps_right_target_despite_actual_joint_error(self):
        names = ["left_wrist_pitch_joint", "right_wrist_pitch_joint"]
        model = SimpleNamespace(jnt_range=np.array([[-2., 2.], [-2., 2.]]),
                                opt=SimpleNamespace(timestep=0.04))
        data = SimpleNamespace(time=0., qpos=np.array([1., 0.2]))
        robot = SimpleNamespace(ai=dict(zip(names, range(2))), model=model, data=data,
                                joint_ids=np.arange(2), qids=np.arange(2),
                                targets=np.zeros(2), guard=None, budget=180.,
                                joint_rows={name: [None] * 5 + [22.] for name in names})

        def step():
            data.time += 0.04

        robot._step = step
        result = joint_targets(robot, names, np.ones((1, 50, 2)), 0, 1, 30, hold_right=True)
        self.assertGreater(result["tracking_error_rad"], 0.45)
        self.assertEqual(robot.targets[0], 1.)
        self.assertEqual(robot.targets[1], 0., "tracking exit changed the held target to measured q")

    def test_rejected_clear_step_never_attempts_the_mean_posture(self):
        calls = []
        robot = SimpleNamespace(fk=lambda side: {"position_m": [0., 0., 0.]}, guard=None)

        def invoke(tool, args):
            calls.append(tool)
            return {"status": "POSE_IK_REJECTED"}

        with tempfile.TemporaryDirectory() as folder:
            result = preposition(robot, SimpleNamespace(invoke=invoke), Path(folder))
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "CLEAR_PATH_REJECTED")
        self.assertEqual(calls, ["move_ee"])


if __name__ == "__main__":
    unittest.main()
