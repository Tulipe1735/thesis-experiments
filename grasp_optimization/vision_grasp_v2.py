"""Separate v2: bounded torso search and thumb-leading grasp, preserving frozen v1."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from vision_grasp import VisionGrasp, RobotPort, DiagnosticRobot, ActionFailure, PerceptionError, ROOT, write_json
from arm_planner import ArmPlanner
from frozen_validation import check_frozen

YAWS = [.7, .6, .55, .4, .25, 0., -.2]
PITCHES = [-.15, -.10, -.05, 0., .05, .10]


class ArmPlannerV2(ArmPlanner):
    def select(self, state, cup_position, offset, preferred=.7):
        trials = []
        current = state['joints']['waist_pitch_joint']['q']
        candidates = [current]+[p for p in PITCHES if p > current+.025]
        for pitch in candidates:
            trial_state = deepcopy(state)
            trial_state['joints']['waist_pitch_joint']['q'] = pitch
            for yaw in dict.fromkeys([preferred]+YAWS):
                path = self.path(trial_state, cup_position, yaw, offset)
                trials.append(dict(torso_pitch_rad=pitch, yaw_rad=yaw,
                                   reachable=path['reachable'], failed_at=path.get('failed_at'),
                                   max_position_error_m=path.get('max_position_error_m')))
                if path['reachable']:
                    return dict(selected_yaw_rad=yaw if abs(pitch-current)<.025 else None,
                                selected_offset_m=list(offset),
                                suggested_waist_pitch_rad=pitch if abs(pitch-current)>=.025 else None,
                                candidates=trials, path=path,
                                policy='smallest bounded torso pitch then fixed yaw order; no IK restarts',
                                collision_checked=False)
        return dict(selected_yaw_rad=None, selected_offset_m=None,
                    suggested_waist_pitch_rad=None, candidates=trials, collision_checked=False,
                    policy='no safe continuous kinematic candidate; stop')


class VisionGraspV2(VisionGrasp):
    def __init__(self, port, folder, memory_path=None, closure='adaptive'):
        super().__init__(port, folder, memory_path)
        self.closure = closure
        self.initial_pitch = self.port.state()['joints']['waist_pitch_joint']['q']
        self.adjustments = 0

    def preflight(self):
        if self.phase != 'ready' or self.estimate is None:
            raise ActionFailure('Prepare and locate before v2 planning')
        self.plan = ArmPlannerV2().select(self.port.state(), self.estimate['cup_bottom_position_m'],
                                         self.offset, self.preferred_yaw)
        self.plan_history.append(dict(observation_id=self.estimate['observation_id'],
                                      simulation_seconds=self.port.state()['simulation_seconds'], plan=self.plan))
        write_json(self.folder/'kinematic_preflight_history.json', self.plan_history)
        write_json(self.folder/'kinematic_preflight.json', self.plan)
        return dict(reachable=self.plan['selected_yaw_rad'] is not None,
                    selected_yaw_rad=self.plan['selected_yaw_rad'],
                    suggested_waist_pitch_rad=self.plan['suggested_waist_pitch_rad'],
                    collision_checked=False)

    def adjust_reach(self):
        if self.phase != 'ready' or self.plan is None:
            raise ActionFailure('No v2 reach adjustment is available')
        target = self.plan['suggested_waist_pitch_rad']
        if target is None or not -.16 <= target <= .10001 or target-self.initial_pitch > .255:
            raise ActionFailure('V2 torso range exceeded')
        if self.adjustments >= 6:
            raise ActionFailure('V2 torso adjustment budget exhausted')
        current = self.port.state()['joints']['waist_pitch_joint']['q']
        step_target = min(target, current+.05)
        self.action('v2_torso_pitch', 'set_joints', targets={'waist_pitch_joint': step_target}, duration=1.)
        self.action('v2_restore_clear_palm', 'move_ee', side='left', position=[-.04, .34, .30],
                    quaternion_xyzw=[0., 0., 0., 1.], duration=1.)
        self.adjustments += 1
        self.plan = None
        return self.locate()

    def close_and_test(self):
        if self.closure == 'simultaneous':
            return super().close_and_test()
        if self.phase != 'approached':
            raise ActionFailure('Approach before v2 closure')
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('v2_thumb_lead', 'set_joints', targets=dict(zip(names[:3], self.close[:3])), duration=.7)
        if self.closure == 'adaptive':
            for fraction in [.15, .3, .45, .6, .75, .9, 1.]:
                targets = dict(zip(names[3:], np.asarray(self.close[3:])*fraction))
                self.action('v2_close_fraction_'+str(fraction), 'set_joints', targets=targets, duration=.3)
                loads = {'thumb':0., 'index':0., 'middle':0.}
                for link, force in self.port.state()['approximate_contact_load_N']['left'].items():
                    for digit in loads:
                        if '_hand_'+digit+'_' in link: loads[digit] += force
                self.actions.append(dict(stage='v2_closure_feedback', fraction=fraction, digit_load_N=loads))
                self.save()
                if loads['thumb'] >= 3. and min(loads['index'],loads['middle']) >= 2.:
                    break
        else:
            self.action('v2_close_fingers', 'set_joints', targets=dict(zip(names, self.close)), duration=1.5)
        self.action('grip_settle', 'wait', seconds=.5)
        self.tactile_gate('tactile_grip_gate')
        self.linear('test_lift_2cm', self.palm+[0., 0., .02], 1.)
        self.action('test_lift_hold', 'wait', seconds=.5)
        feedback = self.tactile_gate('tactile_test_lift_gate')
        self.phase = 'tested'
        return feedback


def run(folder, seed=1000, closure='adaptive'):
    check_frozen()
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
    robot = DiagnosticRobot(folder, seed=seed, budget=90.)
    controller = VisionGraspV2(RobotPort(robot), folder, closure=closure)
    config = dict(seed=seed, branch='vision-v2-'+closure, controller_version='vision-v2-development',
                  execution_mode='head_RGBD_and_proprioception_with_simulated_tactile',
                  policy_reads_cup_ground_truth=False, contact_object_identity_used_by_policy=False,
                  model_requests=0, VLA_weight_changes=False, closure=closure,
                  source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                                 ('vision_grasp_v2.py','vision_grasp.py','arm_planner.py','rgbd_cup.py','pantry_robot.py')},
                  formal_task_snapshot=False)
    write_json(folder/'run_config.json', config)
    try:
        robot.advance(.75, 'episode_initial_settling')
        controller.locate(); controller.prepare()
        preflight = controller.preflight()
        while not preflight['reachable'] and preflight['suggested_waist_pitch_rad'] is not None:
            controller.adjust_reach()
            preflight = controller.preflight()
        print('V2_PREFLIGHT', json.dumps(preflight), flush=True)
        if not preflight['reachable']:
            raise ActionFailure('NO_REACHABLE_VISUAL_TARGET_PATH_V2')
        controller.approach(); controller.close_and_test(); controller.lift_and_hold()
        controller.port.observe()
    except (ActionFailure, PerceptionError) as exc:
        robot.stop(str(exc)); print('V2_STOP', str(exc), flush=True)
    finally:
        controller.save(); result = robot.finish()
    print('V2_RESULT', json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--closure', choices=['simultaneous','thumb_lead','adaptive'], default='adaptive')
    args=parser.parse_args()
    raise SystemExit(0 if run(args.output,args.seed,args.closure)['independent_success'] else 1)
