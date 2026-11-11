"""A sample gap must break a claimed hold, while allowing later valid holds."""

import unittest

from harness.local_reach import hold_timing


class HoldWindowTests(unittest.TestCase):
    def test_early_travel_gap_does_not_invalidate_a_later_complete_hold(self):
        rows = [{"time": 0., "at_pose": False}, {"time": .052, "at_pose": False}]
        rows += [{"time": 1. + i * .05, "at_pose": True} for i in range(21)]
        first, terminal = hold_timing(rows, 1.)
        self.assertAlmostEqual(first, 2.)
        self.assertAlmostEqual(terminal, 1.)

    def test_missing_sample_inside_hold_cannot_bridge_the_window(self):
        rows = [{"time": i * .05, "at_pose": True} for i in range(21) if i != 10]
        first, terminal = hold_timing(rows, 1.)
        self.assertIsNone(first)
        self.assertLess(terminal, 1.)


if __name__ == "__main__":
    unittest.main()
