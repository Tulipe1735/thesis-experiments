"""Search parameters of the existing v2 visual-tactile grasp policy.

This is a new version; frozen vision_grasp_v2.py and arm_planner.py are not
edited. The parameters are path discretisation and clearance knobs, evaluated
by the existing independent grasp verifier. No VLA, no model requests.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from arm_planner import ArmPlanner, yaw_rotation
from diagnose_grasp import DiagnosticRobot, ROOT, write_json
from vision_grasp import ActionFailure, PerceptionError, RobotPort
from vision_grasp_v2 import ArmPlannerV2, PITCHES, VisionGraspV2, YAWS
from verify_grasp import verify

DEFAULT = {"step_m": .025, "behind_m": .13, "high_z": .30}


class ArmPlannerV3(ArmPlannerV2):
    """v2 candidate order with explicit path discretisation parameters."""

    def __init__(self, step_m=.025, behind_m=.13, high_z=.30):
        super().__init__()
        self.step_m = float(step_m)
        self.behind_m = float(behind_m)
        self.high_z = float(high_z)

    def path(self, state, cup_position, yaw, offset):
        data = self.start(state)
        palm = np.asarray(cup_position) - yaw_rotation(yaw) @ np.asarray(offset)
        behind = palm - yaw_rotation(yaw) @ [self.behind_m, 0., 0.]
        high = behind.copy()
        high[2] = self.high_z
        goals = [('orient_clear', np.array([-.04, .34, .30])), ('behind_high', high),
                 ('lower_behind', behind), ('approach_open', palm),
                 ('test_lift', palm + [0., 0., .02]), ('main_lift', palm + [0., 0., .125])]
        rows = []
        for stage, goal in goals:
            start = data.site_xpos[self.site].copy()
            count = 1 if stage == 'orient_clear' else max(
                1, int(np.ceil(np.linalg.norm(goal - start) / self.step_m)))
            for step in range(1, count + 1):
                previous = data.qpos[self.qids].copy()
                result = self.solve(data, start + (goal - start) * step / count, yaw)
                jump = float(np.max(np.abs(data.qpos[self.qids] - previous)))
                row = dict(stage=stage, step=step, max_joint_delta_rad=jump, **result)
                rows.append(row)
                if not result['reachable'] or (stage != 'orient_clear' and jump > .5):
                    return dict(yaw_rad=yaw, reachable=False, failed_at=row,
                                path=rows, collision_checked=False,
                                source='robot_proprioception_and_RGBD_target')
        return dict(yaw_rad=yaw, reachable=True, path=rows, collision_checked=False,
                    source='robot_proprioception_and_RGBD_target',
                    max_position_error_m=max(r['position_error_m'] for r in rows))

    def select(self, state, cup_position, offset, preferred=.7):
        trials = []
        current = state['joints']['waist_pitch_joint']['q']
        candidates = [current] + [p for p in PITCHES if p > current + .025]
        for pitch in candidates:
            trial_state = deepcopy(state)
            trial_state['joints']['waist_pitch_joint']['q'] = pitch
            for yaw in dict.fromkeys([preferred] + YAWS):
                path = self.path(trial_state, cup_position, yaw, offset)
                trials.append(dict(torso_pitch_rad=pitch, yaw_rad=yaw,
                                   reachable=path['reachable'], failed_at=path.get('failed_at'),
                                   max_position_error_m=path.get('max_position_error_m')))
                if path['reachable']:
                    return dict(selected_yaw_rad=yaw if abs(pitch - current) < .025 else None,
                                selected_offset_m=list(offset),
                                suggested_waist_pitch_rad=pitch if abs(pitch - current) >= .025 else None,
                                candidates=trials, path=path,
                                policy='v3 parameterized path; smallest bounded torso pitch then fixed yaw order',
                                collision_checked=False)
        return dict(selected_yaw_rad=None, selected_offset_m=None,
                    suggested_waist_pitch_rad=None, candidates=trials, collision_checked=False,
                    policy='no safe continuous kinematic candidate; stop')


class VisionGraspV3(VisionGraspV2):
    def __init__(self, port, folder, memory_path=None, closure='adaptive', params=None):
        super().__init__(port, folder, memory_path=memory_path, closure=closure)
        self.params = dict(DEFAULT if params is None else params)
        if 'closure' in self.params:
            self.closure = self.params['closure']
        if 'preferred_yaw' in self.params:
            self.preferred_yaw = float(self.params['preferred_yaw'])
        if 'offset' in self.params:
            self.offset = np.asarray(self.params['offset'], float)
            if self.offset.shape != (3,):
                raise ValueError('offset must have three components')

    def preflight(self):
        if self.phase != 'ready' or self.estimate is None:
            raise ActionFailure('Prepare and locate before v3 planning')
        path_params = {key: self.params[key] for key in ('step_m', 'behind_m', 'high_z')}
        self.plan = ArmPlannerV3(**path_params).select(
            self.port.state(), self.estimate['cup_bottom_position_m'],
            self.offset, self.preferred_yaw)
        self.plan_history.append(dict(observation_id=self.estimate['observation_id'],
                                      simulation_seconds=self.port.state()['simulation_seconds'],
                                      plan=self.plan, params=dict(self.params)))
        write_json(self.folder / 'kinematic_preflight_history.json', self.plan_history)
        write_json(self.folder / 'kinematic_preflight.json', self.plan)
        return dict(reachable=self.plan['selected_yaw_rad'] is not None,
                    selected_yaw_rad=self.plan['selected_yaw_rad'],
                    suggested_waist_pitch_rad=self.plan['suggested_waist_pitch_rad'],
                    collision_checked=False)


class VisionGraspV4(VisionGraspV3):
    """Adaptive closure that continues only when lift feedback loses retention."""

    def __init__(self, port, folder, memory_path=None, params=None):
        base = dict(DEFAULT if params is None else params)
        base['closure'] = 'adaptive'
        super().__init__(port, folder, memory_path=memory_path, closure='adaptive', params=base)
        self.fraction = 0.0

    def _loads(self):
        loads = {'thumb': 0., 'index': 0., 'middle': 0.}
        for link, force in self.port.state()['approximate_contact_load_N']['left'].items():
            for digit in loads:
                if '_hand_' + digit + '_' in link:
                    loads[digit] += force
        return loads

    def _retained(self):
        loads = self._loads()
        return loads['thumb'] >= 1. and max(loads['index'], loads['middle']) >= 1.

    def _set_fraction(self, fraction):
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        targets = dict(zip(names[3:], np.asarray(self.close[3:]) * fraction))
        self.action('v4_close_fraction_' + str(fraction), 'set_joints', targets=targets, duration=.3)
        self.fraction = float(fraction)

    def close_and_test(self):
        if self.phase != 'approached':
            raise ActionFailure('Approach before v4 closure')
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('v4_thumb_lead', 'set_joints', targets=dict(zip(names[:3], self.close[:3])), duration=.7)
        for fraction in (.15, .3, .45, .6, .75, .9, 1.):
            self._set_fraction(fraction)
            loads = self._loads()
            self.actions.append(dict(stage='v4_closure_feedback', fraction=fraction,
                                     digit_load_N=loads))
            self.save()
            if loads['thumb'] >= 3. and min(loads['index'], loads['middle']) >= 2.:
                break
        self.action('grip_settle', 'wait', seconds=.5)
        self.tactile_gate('tactile_grip_gate')
        self.linear('test_lift_2cm', self.palm + [0., 0., .02], 1.)
        self.action('test_lift_hold', 'wait', seconds=.5)
        self.tactile_gate('tactile_test_lift_gate')
        pre_lift = float(self.params.get('pre_lift_fraction', 0.))
        if pre_lift > self.fraction:
            self._set_fraction(min(1., pre_lift))
            self.action('v4_pre_lift_reinforce', 'wait', seconds=.3)
            if not self._retained():
                raise ActionFailure('PRE_LIFT_RETENTION_LOST')
        self.phase = 'tested'
        return dict(status='TESTED', fraction=self.fraction)

    def lift_and_hold(self):
        if self.phase != 'tested':
            raise ActionFailure('Test grip before v4 full lift')
        target_z = float(self.palm[2]) + .125
        for _ in range(12):
            current = np.asarray(self.port.state()['palms']['left']['position_m'])
            if current[2] >= target_z - 1e-4:
                break
            step = min(.025, target_z - current[2])
            self.linear('v4_lift', [current[0], current[1], current[2] + step], .5)
            if not self._retained():
                if self.fraction >= 1.:
                    raise ActionFailure('RETENTION_LOST')
                self._set_fraction(min(1., self.fraction + .15))
                self.action('v4_retention_settle', 'wait', seconds=.3)
                if not self._retained():
                    raise ActionFailure('RETENTION_LOST_AFTER_CLOSE')
        self.action('hold', 'wait', seconds=1.5)
        self.tactile_gate('tactile_final_gate')
        self.phase = 'complete'
        return dict(status='MOTION_COMPLETE_NOT_INDEPENDENT_SUCCESS', fraction=self.fraction,
                    actual_palm=self.port.state()['palms']['left'])


class VisionGraspV5(VisionGraspV4):
    """Select adaptive vs full closure from public tactile evidence after test lift."""

    def close_and_test(self):
        VisionGraspV2.close_and_test(self)
        loads = self._loads()
        self.selector_index_N = loads['index']
        threshold = float(self.params.get('selector_index_N', 4.0))
        if loads['index'] < threshold:
            self._set_fraction(1.0)
            self.action('v5_selector_full_close', 'wait', seconds=.3)
            self.skill_used = 'full_close'
        else:
            self.skill_used = 'adaptive'
        return dict(status='TESTED', fraction=self.fraction, selector_index_N=loads['index'],
                    skill_used=self.skill_used)

    def lift_and_hold(self):
        return VisionGraspV2.lift_and_hold(self)


class VisionGraspV6(VisionGraspV5):
    """Recovery skill: reopen, retreat, re-approach, and close fully from the start."""

    def close_and_test(self):
        VisionGraspV2.close_and_test(self)
        loads = self._loads()
        self.selector_index_N = loads['index']
        threshold = float(self.params.get('selector_index_N', 4.0))
        if loads['index'] < threshold:
            names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                    'middle_0', 'middle_1', 'index_0', 'index_1')]
            self.action('v6_reopen', 'set_joints', targets={name: 0.0 for name in names}, duration=.5)
            behind = self.palm - yaw_rotation(self.yaw) @ [.13, 0., 0.]
            self.linear('v6_retreat', behind, 1.)
            self.linear('v6_reapproach', self.palm, 1.)
            self.action('v6_full_close', 'set_joints', targets=dict(zip(names, self.close)), duration=1.5)
            self.action('v6_settle', 'wait', seconds=.5)
            self.tactile_gate('v6_grip_gate')
            self.linear('v6_test_lift', self.palm + [0., 0., .02], 1.)
            self.action('v6_test_hold', 'wait', seconds=.5)
            self.tactile_gate('v6_test_gate')
            self.skill_used = 'recover_full_close'
        else:
            self.skill_used = 'adaptive'
        self.phase = 'tested'
        return dict(status='TESTED', fraction=self.fraction, selector_index_N=loads['index'],
                    skill_used=self.skill_used)

    def lift_and_hold(self):
        return VisionGraspV2.lift_and_hold(self)


class VisionGraspV7(VisionGraspV6):
    """Recover from a failed adaptive grip gate with a full-close retry."""

    def _recover_full_close(self):
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('v7_reopen', 'set_joints', targets={name: 0.0 for name in names}, duration=.5)
        behind = self.palm - yaw_rotation(self.yaw) @ [.13, 0., 0.]
        self.linear('v7_retreat', behind, 1.)
        self.linear('v7_reapproach', self.palm, 1.)
        self.action('v7_full_close', 'set_joints', targets=dict(zip(names, self.close)), duration=1.5)
        self.action('v7_settle', 'wait', seconds=.5)
        self.tactile_gate('v7_grip_gate')
        self.linear('v7_test_lift', self.palm + [0., 0., .02], 1.)
        self.action('v7_test_hold', 'wait', seconds=.5)
        self.tactile_gate('v7_test_gate')
        self.phase = 'tested'
        self.skill_used = 'grip_failure_recovery'

    def close_and_test(self):
        try:
            return VisionGraspV6.close_and_test(self)
        except ActionFailure as error:
            if 'INSUFFICIENT' not in str(error):
                raise
            self._recover_full_close()
            return dict(status='TESTED', skill_used=self.skill_used)


class ArmPlannerV8(ArmPlannerV3):
    """Fallback yaw coverage when the v2/v3 candidate list has no path."""

    FALLBACK_YAWS = (.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7,
                     -.4, -.6, -.8, -1.0, -1.2)

    def select(self, state, cup_position, offset, preferred=.7):
        plan = super().select(state, cup_position, offset, preferred)
        if plan['selected_yaw_rad'] is not None:
            return plan
        current = state['joints']['waist_pitch_joint']['q']
        for pitch in (current, -.15, .10):
            trial_state = deepcopy(state)
            trial_state['joints']['waist_pitch_joint']['q'] = pitch
            for yaw in self.FALLBACK_YAWS:
                path = self.path(trial_state, cup_position, yaw, offset)
                plan['candidates'].append(dict(torso_pitch_rad=pitch, yaw_rad=yaw,
                                               reachable=path['reachable'],
                                               failed_at=path.get('failed_at'),
                                               max_position_error_m=path.get('max_position_error_m'),
                                               fallback=True))
                if path['reachable']:
                    plan.update(selected_yaw_rad=yaw if abs(pitch - current) < .025 else None,
                                selected_offset_m=list(offset),
                                suggested_waist_pitch_rad=pitch if abs(pitch - current) >= .025 else None,
                                path=path, fallback=True)
                    return plan
        return plan


class VisionGraspV8(VisionGraspV7):
    def preflight(self):
        if self.phase != 'ready' or self.estimate is None:
            raise ActionFailure('Prepare and locate before v8 planning')
        path_params = {key: self.params[key] for key in ('step_m', 'behind_m', 'high_z')}
        self.plan = ArmPlannerV8(**path_params).select(
            self.port.state(), self.estimate['cup_bottom_position_m'],
            self.offset, self.preferred_yaw)
        self.plan_history.append(dict(observation_id=self.estimate['observation_id'],
                                      simulation_seconds=self.port.state()['simulation_seconds'],
                                      plan=self.plan, params=dict(self.params)))
        write_json(self.folder / 'kinematic_preflight_history.json', self.plan_history)
        write_json(self.folder / 'kinematic_preflight.json', self.plan)
        return dict(reachable=self.plan['selected_yaw_rad'] is not None,
                    selected_yaw_rad=self.plan['selected_yaw_rad'],
                    suggested_waist_pitch_rad=self.plan['suggested_waist_pitch_rad'],
                    fallback=bool(self.plan.get('fallback')),
                    collision_checked=False)


class VisionGraspV9(VisionGraspV7):
    """C4: after an adaptive grip failure, regrasp with a recovered yaw/offset."""

    def _regrasp_recovery(self):
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('v9_reopen', 'set_joints', targets={name: 0.0 for name in names}, duration=.5)
        self.action('v9_retreat_clear', 'move_ee', side='left',
                    position=[-.04, .34, .30], quaternion_xyzw=[0., 0., 0., 1.], duration=2.)
        self.phase = 'ready'
        self.locate()
        self.preferred_yaw = float(self.params.get('recovery_yaw', .2))
        self.offset = np.asarray(self.params.get('recovery_offset', [.03, -.07, -.052]), float)
        self.phase = 'ready'
        path_params = {key: self.params[key] for key in ('step_m', 'behind_m', 'high_z')}
        plan = ArmPlannerV3(**path_params).select(
            self.port.state(), self.estimate['cup_bottom_position_m'],
            self.offset, self.preferred_yaw)
        if plan['selected_yaw_rad'] is None:
            raise ActionFailure('REGRASP_UNREACHABLE')
        self.plan = plan
        self.approach()
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('v9_full_close', 'set_joints', targets=dict(zip(names, self.close)), duration=1.5)
        self.action('v9_settle', 'wait', seconds=.5)
        self.tactile_gate('v9_grip_gate')
        self.linear('v9_test_lift', self.palm + [0., 0., .02], 1.)
        self.action('v9_test_hold', 'wait', seconds=.5)
        self.tactile_gate('v9_test_gate')
        self.phase = 'tested'
        self.skill_used = 'c4_regrasp_yaw_offset'

    def close_and_test(self):
        try:
            return VisionGraspV7.close_and_test(self)
        except ActionFailure as error:
            if 'INSUFFICIENT' not in str(error) and 'REGRASP' not in str(error):
                raise
            self._regrasp_recovery()
            return dict(status='TESTED', skill_used=self.skill_used)


class VisionGraspV10(VisionGraspV9):
    """C4 selector: low tactile engagement at 15% triggers an early regrasp."""

    def _retreat_for_regrasp(self, names):
        self.action('v10_reopen', 'set_joints', targets={name: 0.0 for name in names}, duration=.5)
        behind = self.palm - yaw_rotation(self.yaw) @ [.13, 0., 0.]
        self.linear('v10_retreat', behind, 1.)

    def _c4_early_regrasp(self):
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self._retreat_for_regrasp(names)
        self.phase = 'ready'
        self.preferred_yaw = float(self.params.get('recovery_yaw', .2))
        self.offset = np.asarray(self.params.get('recovery_offset', [.03, -.07, -.052]), float)
        self.phase = 'ready'
        path_params = {key: self.params[key] for key in ('step_m', 'behind_m', 'high_z')}
        plan = ArmPlannerV3(**path_params).select(
            self.port.state(), self.estimate['cup_bottom_position_m'],
            self.offset, self.preferred_yaw)
        if plan['selected_yaw_rad'] is None:
            raise ActionFailure('C4_REGRASP_UNREACHABLE')
        self.plan = plan
        self.approach()
        self.action('v10_full_close', 'set_joints', targets=dict(zip(names, self.close)), duration=1.5)
        self.action('v10_settle', 'wait', seconds=.5)
        self.tactile_gate('v10_grip_gate')
        self.linear('v10_test_lift', self.palm + [0., 0., .02], 1.)
        self.action('v10_test_hold', 'wait', seconds=.5)
        self.tactile_gate('v10_test_gate')
        self.phase = 'tested'
        self.skill_used = 'c4_early_regrasp'

    def close_and_test(self):
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('v10_thumb_lead', 'set_joints',
                    targets=dict(zip(names[:3], self.close[:3])), duration=.7)
        self._set_fraction(.15)
        loads = self._loads()
        if loads['thumb'] < 3. or min(loads['index'], loads['middle']) < 2.:
            self._c4_early_regrasp()
            return dict(status='TESTED', skill_used=self.skill_used)
        if not (loads['thumb'] >= 3. and min(loads['index'], loads['middle']) >= 2.):
            for fraction in (.3, .45, .6, .75, .9, 1.):
                self._set_fraction(fraction)
                loads = self._loads()
                self.actions.append(dict(stage='v10_closure_feedback', fraction=fraction,
                                         digit_load_N=loads))
                self.save()
                if loads['thumb'] >= 3. and min(loads['index'], loads['middle']) >= 2.:
                    break
        self.action('v10_grip_settle', 'wait', seconds=.5)
        self.tactile_gate('v10_grip_gate')
        self.linear('v10_test_lift', self.palm + [0., 0., .02], 1.)
        self.action('v10_test_hold', 'wait', seconds=.5)
        self.tactile_gate('v10_test_gate')
        loads = self._loads()
        if loads['index'] < float(self.params.get('selector_index_N', 4.0)):
            self._recover_full_close()
            return dict(status='TESTED', skill_used='c3_recovery')
        self.phase = 'tested'
        self.skill_used = 'adaptive'
        return dict(status='TESTED', skill_used=self.skill_used)


class VisionGraspV11(VisionGraspV10):
    """Return along the approach corridor before changing the recovery yaw.

    V10's direct orient_clear solve fails from the retreated joint posture on
    development instance 1400. Preserve the old yaw while reversing the two
    approach segments; only then plan and execute the existing C4 grasp.
    This moves the robot in the same episode and never restores simulator state.
    """

    def _retreat_for_regrasp(self, names):
        super()._retreat_for_regrasp(names)
        high = self.palm - yaw_rotation(self.yaw) @ [.13, 0., 0.]
        high[2] = .30
        self.linear('v11_reverse_lower', high, 2.)
        self.linear('v11_reverse_high', [-.04, .34, .30], 2.)


def run_trial(folder, seed, params, memory_path=None):
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    robot = DiagnosticRobot(folder, seed=seed, budget=90.)
    policy_version = params.get('policy', 'v3')
    closure = 'adaptive' if policy_version == 'v4' else params.get('closure', 'adaptive')
    if policy_version == 'v2':
        controller = VisionGraspV2(RobotPort(robot), folder, memory_path=memory_path, closure=closure)
    elif policy_version == 'v11':
        controller = VisionGraspV11(RobotPort(robot), folder, memory_path=memory_path, params=params)
    elif policy_version == 'v10':
        controller = VisionGraspV10(RobotPort(robot), folder, memory_path=memory_path, params=params)
    elif policy_version == 'v9':
        controller = VisionGraspV9(RobotPort(robot), folder, memory_path=memory_path, params=params)
    elif policy_version == 'v8':
        controller = VisionGraspV8(RobotPort(robot), folder, memory_path=memory_path, params=params)
    elif policy_version == 'v7':
        controller = VisionGraspV7(RobotPort(robot), folder, memory_path=memory_path, params=params)
    elif policy_version == 'v6':
        controller = VisionGraspV6(RobotPort(robot), folder, memory_path=memory_path, params=params)
    elif policy_version == 'v5':
        controller = VisionGraspV5(RobotPort(robot), folder, memory_path=memory_path, params=params)
    elif policy_version == 'v4':
        controller = VisionGraspV4(RobotPort(robot), folder, memory_path=memory_path, params=params)
    else:
        controller = VisionGraspV3(RobotPort(robot), folder, memory_path=memory_path,
                                   closure=closure, params=params)
    config = dict(seed=seed, branch='grasp-policy-search-v1',
                  controller_version='vision-v2-parameterized-' + policy_version,
                  execution_mode='head_RGBD_and_proprioception_with_simulated_tactile',
                  policy_reads_cup_ground_truth=False, contact_object_identity_used_by_policy=False,
                  model_requests=0, VLA_weight_changes=False, closure=closure,
                  policy=policy_version, params=dict(params),
                  source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in ('vision_grasp.py', 'vision_grasp_v2.py',
                                              'arm_planner.py', 'rgbd_cup.py', 'pantry_robot.py',
                                              'grasp_policy_search.py')})
    write_json(folder / 'run_config.json', config)
    error = None
    try:
        robot.advance(.75, 'episode_initial_settling')
        controller.locate()
        controller.prepare()
        preflight = controller.preflight()
        while not preflight['reachable'] and preflight['suggested_waist_pitch_rad'] is not None:
            controller.adjust_reach()
            preflight = controller.preflight()
        if not preflight['reachable']:
            raise ActionFailure('NO_REACHABLE_VISUAL_TARGET_PATH_V3')
        controller.approach()
        controller.close_and_test()
        controller.lift_and_hold()
        controller.port.observe()
    except (ActionFailure, PerceptionError) as exc:
        error = str(exc)
        robot.stop(error)
    finally:
        controller.save()
        environment = robot.finish()
    verification = verify(folder)
    result = {
        "seed": seed, "params": dict(params), "error": error,
        "independent_success": bool(verification["verified_success"]),
        "max_lift_m": verification["max_lift_m"],
        "longest_hold_s": verification["longest_strict_hold_s"],
        "stop_reason": environment.get("agent_stop_reason"),
        "verification": str((folder / "independent_verification.json").relative_to(ROOT.parent)),
    }
    write_json(folder / 'search_trial.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=1206)
    parser.add_argument('--search', action='store_true')
    parser.add_argument('--params', default=None, help='JSON dict for one trial')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if args.search:
        configs = [
            dict(DEFAULT),
            dict(DEFAULT, step_m=.020), dict(DEFAULT, step_m=.015), dict(DEFAULT, step_m=.0125),
            dict(DEFAULT, step_m=.015, behind_m=.10), dict(DEFAULT, step_m=.015, behind_m=.16),
            dict(DEFAULT, step_m=.015, high_z=.26), dict(DEFAULT, step_m=.015, high_z=.34),
            dict(DEFAULT, step_m=.020, behind_m=.10), dict(DEFAULT, step_m=.020, behind_m=.16),
            dict(DEFAULT, step_m=.0125, behind_m=.10), dict(DEFAULT, step_m=.0125, behind_m=.16),
        ]
        write_json(output / 'registration.json', {
            "date": "2026-11-06", "kind": "grasp_policy_v2_parameter_search",
            "status": "registered_before_trials", "boundary": "MuJoCo simulation",
            "seed": args.seed, "configs": configs, "trials": len(configs),
            "budget": {"simulation_s_per_trial": 90., "retries": 0, "model_requests": 0},
            "prediction": "smaller path steps or shorter behind distance may remove the >0.5 rad continuity failure on seed 1206; if none reach approach_open, the failure is not only discretisation",
            "falsification": "any trial that changes the frozen official verifier or needs a retry is invalid",
            "baseline": "frozen vision-v2 adaptive, seed 1206, no reachable path",
            "evaluation": "verify_grasp.py independent_verification.json",
        })
        rows = []
        for index, params in enumerate(configs):
            trial = output / f"trial_{index:02d}"
            try:
                row = run_trial(trial, args.seed, params)
            except Exception as error:
                row = {"seed": args.seed, "params": params, "error": f"{type(error).__name__}: {error}",
                       "independent_success": False}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        write_json(output / 'results.json', {
            "seed": args.seed, "rows": rows,
            "successes": sum(bool(row.get('independent_success')) for row in rows),
            "reachable_any": any(row.get('error') is None for row in rows),
            "best": next((row for row in rows if row.get('independent_success')), None),
        })
    else:
        params = dict(DEFAULT) if args.params is None else json.loads(args.params)
        row = run_trial(output / 'trial', args.seed, params)
        print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
