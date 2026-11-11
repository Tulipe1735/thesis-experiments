"""A refused move must stop policy code before stale waypoints or hand closure."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "calibration"))

import t01_code_policy as policy


class RejectingPort:
    def __init__(self):
        self.commands = []

    def state(self):
        return {"palms": {"left": {"position_m": [0., 0., 0.]}}}

    def invoke(self, tool, arguments):
        self.commands.append((tool, arguments))
        return {"status": "POSE_IK_REJECTED", "executed": False,
                "position_error_m": 0.012, "orientation_error_rad": 0.24}


class RejectedMoveTests(unittest.TestCase):
    def test_refusal_interrupts_waypoints_and_preserves_namespace(self):
        for distance, status, commands in (
            (0.02, "POSE_IK_REJECTED", 1),
            (0.10, "MOVE_TOO_LONG", 0),
        ):
            with self.subTest(status=status):
                port = RejectingPort()
                robot = policy.RobotSession(None, port)
                namespace = {"robot": robot}
                result = policy.run_code(
                    f"before = 1\n"
                    f"for _ in range(3):\n"
                    f"    robot.move_ee('left', [{distance}, 0, 0], duration=0.5)\n"
                    f"robot.set_joints({{'left_hand_thumb_1_joint': 0.65}}, 2)\n"
                    f"after = 1\n", namespace)
                self.assertIsNotNone(result["error"], "refusal was silently ignored")
                self.assertIn("MoveRejected", result["error"])
                self.assertIn(status, result["error"])
                self.assertIn("requested_position_m", result["error"])
                self.assertEqual(len(port.commands), commands)
                self.assertEqual(len(robot.log), 1)
                self.assertEqual(namespace["before"], 1)
                self.assertNotIn("after", namespace)
                if status == "POSE_IK_REJECTED":
                    self.assertIn('"position_error_m": 0.012', result["error"])
                    self.assertIn('"orientation_error_rad": 0.24', result["error"])
                resumed = policy.run_code("resumed = before + 1", namespace)
                self.assertIsNone(resumed["error"])
                self.assertEqual(namespace["resumed"], 2)


if __name__ == "__main__":
    unittest.main()
