import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from harness import tp01, local_reach_v3
from experiments.cordis_t01.worker import SavedInitialRobot


class RecordingTests(unittest.TestCase):
    def record(self, method):
        robot = SimpleNamespace(data=SimpleNamespace(time=0., qpos=np.zeros(1), qvel=np.zeros(1),
            actuator_force=np.zeros(1)), model=None, targets=np.zeros(1), trace=[], next_record=0.,
            _record_tick=0, _record_stride=25, _controller=lambda:None, _goal=lambda:None)
        def step(model, data):
            data.time += .002
        with patch('mujoco.mj_step', step), patch('mujoco.mj_forward'):
            for _ in range(15000):
                method(robot)
        return [r[0] for r in robot.trace]

    def test_real_recording_path_old_fails_new_obeys_gap_rule(self):
        old = local_reach_v3.timing_quality(self.record(SavedInitialRobot._step))
        new = local_reach_v3.timing_quality(self.record(tp01.TickRecordedRobot._step))
        self.assertEqual(len(old['gaps']), 2)
        self.assertEqual(new['gaps'], [])
        self.assertAlmostEqual(new['max_observed_gap_s'], .05)

    def test_bad_times_are_rejected(self):
        for times in ([0., 0.], [1., .5], [0., float('nan')]):
            with self.assertRaises(ValueError):
                local_reach_v3.timing_quality(times)

    def test_missing_sample_stays_missing(self):
        quality = local_reach_v3.timing_quality([0., .05, .15, .2])
        self.assertEqual(len(quality['gaps']), 1)
