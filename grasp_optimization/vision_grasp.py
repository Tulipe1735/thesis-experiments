"""RGB-D-driven grasp primitive with a restricted sensor/action boundary."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

os.environ.setdefault('MUJOCO_GL', 'egl')

import numpy as np

from arm_planner import ArmPlanner, yaw_rotation
from diagnose_grasp import DiagnosticRobot, ROOT, write_json
from rgbd_cup import PerceptionError, from_observation
from run_direct_grasp import ActionFailure


class RobotPort:
    """Expose sensor-like inputs; task truth stays inside the physical evaluator."""
    def __init__(self, robot):
        self.__robot = robot

    def observe(self):
        observation = self.__robot.observe()
        return {key: observation[key] for key in (
            'observation_id', 'simulation_seconds', 'head_rgb_path', 'depth_path',
            'resolution_wh', 'K', 'T_optical_to_pelvis', 'head_camera', 'body_state')}

    def state(self):
        return self.__robot.state()

    def invoke(self, tool, arguments):
        if tool not in ('move_ee', 'set_joints', 'wait'):
            raise ValueError('Not an allowed physical command')
        return getattr(self.__robot, tool)(**arguments)


class VisionGrasp:
    def __init__(self, port, folder, memory_path=None):
        self.port, self.folder = port, Path(folder)
        self.memory_path = memory_path or ROOT/'episodes/final_reference_1000/episode_memory.json'
        memory = json.loads(Path(self.memory_path).read_text())
        if memory['kind'] != 'engineering_memory_candidate' or not memory['independent_verification']['verified_success']:
            raise ValueError('Require a verified engineering parameter memory')
        parameters = memory['reusable_parameters']
        self.offset = np.array(parameters['cup_in_palm_m'], float)
        self.close = parameters['close_angles']
        self.preferred_yaw = parameters['palm_yaw_rad']
        self.memory_reference = dict(source=str(Path(self.memory_path).resolve()),
                                     sha256=hashlib.sha256(Path(self.memory_path).read_bytes()).hexdigest(),
                                     kind='engineering_parameter_reference_not_agent_learned_skill',
                                     parameters=parameters)
        write_json(self.folder/'retrieved_engineering_memory.json', self.memory_reference)
        self.actions, self.estimates, self.plan_history = [], [], []
        self.estimate = self.plan = self.palm = self.yaw = None
        self.phase = 'initial'
        self.initial_visual_cup = None

    def save(self):
        write_json(self.folder/'actions.json', self.actions)
        write_json(self.folder/'visual_estimates.json', self.estimates)

    def action(self, stage, tool, **arguments):
        result = self.port.invoke(tool, arguments)
        self.actions.append(dict(stage=stage, tool=tool, arguments=arguments, result=result))
        print('VISION_ACTION', stage, result.get('status', result.get('guard')), flush=True)
        self.save()
        state = self.port.state()
        if result.get('status') in ('POSE_IK_REJECTED', 'TRACKING_PROTECTION', 'ENDPOINT_TRACKING_ERROR') or state['controller']['guard']:
            raise ActionFailure(stage+': '+str(result.get('status', state['controller']['guard'])))
        return result

    def linear(self, stage, position, duration):
        start = np.asarray(self.port.state()['palms']['left']['position_m'])
        end = np.asarray(position)
        count = max(1, int(np.ceil(np.linalg.norm(end-start)/.025)))
        quaternion = [0., 0., math.sin(self.yaw/2), math.cos(self.yaw/2)]
        for step in range(1, count+1):
            self.action(f'{stage}_{step:02}', 'move_ee', side='left',
                        position=(start+(end-start)*step/count).tolist(),
                        quaternion_xyzw=quaternion, duration=duration/count)

    def locate(self, pixel_hint=None):
        if self.phase not in ('initial', 'ready'):
            raise ActionFailure('Cannot relocalize after entering the grasp')
        observation = self.port.observe()
        result = from_observation(observation, pixel_hint)
        self.estimate = result
        self.estimates.append(result)
        self.save()
        if self.initial_visual_cup is None:
            self.initial_visual_cup = np.array(result['cup_bottom_position_m'])
        return result

    def prepare(self):
        if self.phase != 'initial':
            raise ActionFailure('Prepare is only allowed once')
        self.action('raise_front', 'move_ee', side='left', position=[-.07, .34, .09], duration=1.5)
        self.action('raise_clear', 'move_ee', side='left', position=[-.04, .34, .30],
                    quaternion_xyzw=[0., 0., 0., 1.], duration=2.)
        self.phase = 'ready'
        return self.locate()

    def preflight(self):
        if self.phase != 'ready' or self.estimate is None:
            raise ActionFailure('Prepare and locate before path preflight')
        self.plan = ArmPlanner().select(self.port.state(), self.estimate['cup_bottom_position_m'],
                                       self.offset, self.preferred_yaw)
        self.plan_history.append(dict(observation_id=self.estimate['observation_id'],
                                      simulation_seconds=self.port.state()['simulation_seconds'],
                                      plan=self.plan))
        write_json(self.folder/'kinematic_preflight_history.json', self.plan_history)
        write_json(self.folder/'kinematic_preflight.json', self.plan)
        return dict(selected_yaw_rad=self.plan['selected_yaw_rad'],
                    selected_offset_m=self.plan['selected_offset_m'],
                    suggested_waist_pitch_rad=self.plan['suggested_waist_pitch_rad'],
                    reachable=self.plan['selected_yaw_rad'] is not None,
                    candidates=[dict(yaw_rad=c['yaw_rad'], reachable=c['reachable'],
                                     failed_at=c.get('failed_at')) for c in self.plan['candidates']],
                    collision_checked=False)

    def adjust_reach(self):
        if self.phase != 'ready' or not self.plan or self.plan['suggested_waist_pitch_rad'] is None:
            raise ActionFailure('No bounded reach adjustment was proposed')
        before = self.port.state()['joints']['waist_pitch_joint']['q']
        target = self.plan['suggested_waist_pitch_rad']
        if abs(target-before) > .055:
            raise ActionFailure('Torso adjustment exceeds the bounded 0.055 rad change')
        self.action('bounded_torso_pitch', 'set_joints', targets={'waist_pitch_joint': target}, duration=1.5)
        self.action('restore_clear_palm', 'move_ee', side='left', position=[-.04, .34, .30],
                    quaternion_xyzw=[0., 0., 0., 1.], duration=1.)
        self.plan = None
        return dict(status='REACH_ADJUSTED_REOBSERVED', estimate=self.locate(),
                    note='Head mount calibration unchanged; torso moved, so old visual target was discarded')

    def approach(self):
        if self.phase != 'ready' or not self.plan or self.plan['selected_yaw_rad'] is None:
            raise ActionFailure('No reachable preflight plan')
        if self.port.state()['simulation_seconds']-self.estimate['observation_simulation_seconds'] > 30.:
            raise ActionFailure('Visual target is stale; relocalize before approaching')
        self.yaw = self.plan['selected_yaw_rad']
        self.offset = np.asarray(self.plan['selected_offset_m'])
        rotation = yaw_rotation(self.yaw)
        self.palm = np.asarray(self.estimate['cup_bottom_position_m'])-rotation@self.offset
        self.action('orient_clear', 'move_ee', side='left', position=[-.04, .34, .30],
                    quaternion_xyzw=[0., 0., math.sin(self.yaw/2), math.cos(self.yaw/2)], duration=1.5)
        behind = self.palm-rotation@[.13, 0., 0.]
        high = behind.copy(); high[2] = .30
        self.linear('behind_high', high, 2.)
        self.linear('lower_behind', behind, 2.)
        self.linear('approach_open', self.palm, 2.)
        self.phase = 'approached'
        return dict(status='APPROACHED', actual_palm=self.port.state()['palms']['left'],
                    target_source='head_RGBD_only', selected_yaw_rad=self.yaw)

    def tactile_gate(self, stage):
        state = self.port.state()
        loads = {'thumb': 0., 'index': 0., 'middle': 0.}
        for link, force in state['approximate_contact_load_N']['left'].items():
            for digit in loads:
                if '_hand_'+digit+'_' in link:
                    loads[digit] += force
        passed = loads['thumb'] >= 1. and max(loads['index'], loads['middle']) >= 1.
        row = dict(stage=stage, passed=passed, digit_load_N=loads,
                   source='simulated_hand_tactile_totals_no_object_identity',
                   not_independent_task_success=True)
        self.actions.append(row); self.save()
        if not passed:
            raise ActionFailure('INSUFFICIENT_THUMB_AND_FINGER_LOAD')
        return row

    def close_and_test(self):
        if self.phase != 'approached':
            raise ActionFailure('Approach before closing')
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('close', 'set_joints', targets=dict(zip(names, self.close)), duration=1.5)
        self.action('grip_settle', 'wait', seconds=.5)
        self.tactile_gate('tactile_grip_gate')
        self.linear('test_lift_2cm', self.palm+[0., 0., .02], 1.)
        self.action('test_lift_hold', 'wait', seconds=.5)
        feedback = self.tactile_gate('tactile_test_lift_gate')
        self.phase = 'tested'
        return feedback

    def lift_and_hold(self):
        if self.phase != 'tested':
            raise ActionFailure('Test grip before full lift')
        self.linear('lift_12_5cm', self.palm+[0., 0., .125], 2.)
        self.action('hold', 'wait', seconds=1.5)
        feedback = self.tactile_gate('tactile_final_gate')
        self.phase = 'complete'
        return dict(status='MOTION_COMPLETE_NOT_INDEPENDENT_SUCCESS', tactile=feedback,
                    actual_palm=self.port.state()['palms']['left'])


def run(folder, seed=1000, memory=None):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
    robot = DiagnosticRobot(folder, seed=seed, budget=60.)
    port = RobotPort(robot)
    controller = VisionGrasp(port, folder, memory)
    config = dict(seed=seed, branch='vision-direct-v1', model_requests=0,
                  execution_mode='head_RGBD_and_proprioception_with_simulated_tactile',
                  controller_version='vision-grasp-v1', policy_reads_cup_ground_truth=False,
                  contact_object_identity_used_by_policy=False, VLA_weight_changes=False,
                  formal_task_snapshot=False, memory=controller.memory_reference,
                  source_sha256={n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest()
                                 for n in ('vision_grasp.py', 'rgbd_cup.py', 'arm_planner.py', 'pantry_robot.py')})
    write_json(folder/'run_config.json', config)
    try:
        robot.advance(.75, 'episode_initial_settling')
        controller.locate()
        controller.prepare()
        preflight = controller.preflight()
        if not preflight['reachable'] and preflight['suggested_waist_pitch_rad'] is not None:
            controller.adjust_reach()
            preflight = controller.preflight()
        print('VISION_PREFLIGHT', json.dumps(preflight), flush=True)
        if not preflight['reachable']:
            raise ActionFailure('NO_REACHABLE_VISUAL_TARGET_PATH')
        controller.approach()
        controller.close_and_test()
        controller.lift_and_hold()
        port.observe()
    except (ActionFailure, PerceptionError) as exc:
        robot.stop(str(exc))
        print('VISION_STOP', str(exc), flush=True)
    finally:
        controller.save()
        result = robot.finish()
    print('VISION_RESULT', json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--memory', type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.output, args.seed, args.memory)['independent_success'] else 1)
