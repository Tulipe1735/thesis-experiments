"""The T01 adapter must keep candidate code isolated and commands bounded."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/grow_up_harness_v2/calibration'))

from harness import artifact, t01_episode as T
from harness.grow_loop import Worker


class AdapterTests(unittest.TestCase):
    def test_current_projection_runs_in_seccomp_worker_with_public_observation(self):
        record = artifact.load(ROOT / 'experiments/grow_up_harness_v2/artifacts/t01_cup_to_tray.yaml')
        names = list(record.ir.close_angles) + ['waist_pitch_joint']
        observation = {
            'left_palm': {'position_m': [-.1, .3, .08]},
            'grasp_probe': {'yaws': [{'palm_yaw_rad': 0., 'waist_pitch_rad': -.1,
                                     'grasp_xyz_m': [.05, .3, .1], 'approach_start_xyz_m': [.02, .3, .1]}],
                            'cup_in_palm_m': [.045, -.055, -.052]},
            'tray_floor_center_m': [-.05, .4, .05], 'cup_bottoms_m': [[.05, .3, .02]],
            'joints': {n: {'q': 0., 'target': 0., 'range_rad': [-3., 3.]} for n in names}}
        gate = T.dry_run(artifact.generate_code(record), observation)
        self.assertTrue(gate['passed'])
        self.assertTrue(gate['security']['seccomp'])
        name = names[0]
        source = f'''
def grasp_parameters(o): return {{}}
def plan(o):
    q = o['joints'][{name!r}]['target']
    return [{{'op':'set_joints','targets':{{{name!r}:q+.02}},'duration':.2}},
            {{'op':'set_joints','targets':{{{name!r}:q+.04}},'duration':.2}}]
def lift(o,p): return [{{'op':'wait','duration':.02}}]
def correct(o,p): return []
def release(o,p): return []
'''
        gate = T.dry_run(source, observation, joint_commands=True)
        self.assertTrue(gate['passed'], gate)
        self.assertEqual(gate['worker_calls'], 4)
        self.assertTrue(gate['security']['seccomp'])
        bad = [
            {'op': 'move_linear'}, {'op': 'finish'},
            {'op': 'wait', 'seconds': .02}, {'op': 'wait', 'duration': .202},
            {'op': 'wait', 'duration': .021},
            {'op': 'set_joints', 'targets': {'waist_pitch_joint': .01}, 'duration': .2},
            {'op': 'set_joints', 'targets': {name: .06}, 'duration': .2},
            {'op': 'set_joints', 'targets': {name: .02}, 'duration': .02},
        ]
        for command in bad:
            with self.subTest(command=command), self.assertRaises(ValueError):
                T.validate_joint_commands([command], observation['joints'])

    def test_forbidden_import_and_bad_phase_interface_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'must define'):
            T.phase_source('def act(o,t,s): return {}')
        record = artifact.load(ROOT / 'experiments/grow_up_harness_v2/artifacts/t01_cup_to_tray.yaml')
        with self.assertRaisesRegex(ValueError, 'import not allowed'):
            T.phase_source('import os\n' + artifact.generate_code(record))

    def test_commands_cannot_continue_after_finish(self):
        with self.assertRaisesRegex(ValueError, 'finish must be last'):
            T.validate_commands([{'op': 'finish'}, {'op': 'wait', 'seconds': 1.}], {})
        with self.assertRaisesRegex(ValueError, 'at most 256'):
            T.validate_commands([{'op': 'finish'}] * 257, {})
