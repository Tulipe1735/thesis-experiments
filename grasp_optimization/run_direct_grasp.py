"""Cup-relative engineering controller for physical P01 grasp development."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from diagnose_grasp import DiagnosticRobot, ROOT, snapshot, write_json


class ActionFailure(RuntimeError):
    pass


def run(folder, offset=(.045, -.055, -.052), close=(0., .65, .65, -.8, -.6, -.8, -.6),
        seed=1000, images=False, yaw=.7, memory=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    robot = DiagnosticRobot(folder, seed=seed, budget=45.)
    actions = []
    config = dict(seed=seed, branch='direct-grasp-diagnostic', model_requests=0,
                  execution_mode='privileged_cup_relative_engineering_controller',
                  formal_task_snapshot=False, cup_in_palm_m=list(offset), close_angles=list(close),
                  palm_yaw_rad=yaw,
                  camera_version=robot.context['head_camera']['version'], cup_binding=False)
    config['controller_version'] = 'cup-relative-direct-v1'
    config['source_sha256'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                               for name in ('run_direct_grasp.py', 'pantry_robot.py', 'pantry_scene.py',
                                            'diagnose_grasp.py', 'verify_grasp.py')}
    config['initial_state_sha256'] = hashlib.sha256((folder/'initial_state.npz').read_bytes()).hexdigest()
    if memory:
        config['memory_retrieval'] = dict(path=str(Path(memory).resolve()),
                                         sha256=hashlib.sha256(Path(memory).read_bytes()).hexdigest(),
                                         usage='explicit parameter reuse by engineering controller, not Astra')
    write_json(folder / 'run_config.json', config)

    def action(stage, tool, **kwargs):
        robot.stage = stage
        result = getattr(robot, tool)(**kwargs)
        actions.append(dict(stage=stage, tool=tool, arguments=kwargs, result=result))
        print('ACTION', stage, result.get('status', result.get('guard')), flush=True)
        robot.checkpoint(stage, images=images)
        if result.get('status') in ('POSE_IK_REJECTED', 'TRACKING_PROTECTION', 'ENDPOINT_TRACKING_ERROR') or robot.guard:
            raise ActionFailure(stage + ': ' + str(result.get('status', robot.guard)))
        return result

    def linear(stage, position, quaternion, duration):
        start = np.asarray(robot.fk('left')['position_m'])
        end = np.asarray(position)
        count = max(1, int(np.ceil(np.linalg.norm(end-start)/.025)))
        for i in range(1, count+1):
            action(f'{stage}_{i:02}', 'move_ee', side='left',
                   position=(start+(end-start)*i/count).tolist(),
                   quaternion_xyzw=quaternion, duration=duration/count)

    def require_grip(lifted=False):
        state = snapshot(robot, 'grip_gate')
        digits, normals, loads, support_load = set(), {}, {}, 0.
        for c in state['contacts']:
            if 'task_cup' not in c['bodies']:
                continue
            other = next(b for b in c['bodies'] if b != 'task_cup')
            if not other.startswith('left_hand_'):
                support_load += c['normal_force_N']
                continue
            digit = other.split('_hand_')[1].split('_')[0]
            digits.add(digit)
            loads[digit] = loads.get(digit, 0.) + c['normal_force_N']
            normal = np.asarray(c['normal'])*(1 if c['bodies'][0] == 'task_cup' else -1)
            normals[digit] = normals.get(digit, np.zeros(3))+c['normal_force_N']*normal
        opposing = False
        if 'thumb' in normals:
            for digit in ('middle', 'index'):
                if digit in normals and loads['thumb'] >= .1 and loads[digit] >= .1:
                    a, b = normals['thumb'], normals[digit]
                    opposing |= float(a@b)/(np.linalg.norm(a)*np.linalg.norm(b)) < -.5
        passed = opposing and (not lifted or (support_load < .1 and state['lift_m'] >= .005))
        actions.append(dict(stage='test_lift_gate' if lifted else 'grip_gate',
                            passed=bool(passed), opposing_contacts=bool(opposing),
                            digits=sorted(digits), support_load_N=support_load,
                            lift_m=state['lift_m']))
        if not passed:
            raise ActionFailure('NO_OPPOSING_GRIP_OR_FAILED_TEST_LIFT')

    try:
        robot.advance(.75, 'episode_initial_settling')
        robot.checkpoint('settled', images=images)
        # Use cup truth only for this explicitly privileged control diagnostic.
        base = robot.data.xmat[robot.pelvis_id].reshape(3, 3)
        cup = base.T @ (robot.data.xpos[robot.cup_id]-robot.data.xpos[robot.pelvis_id])
        rotation = np.array([[math.cos(yaw), -math.sin(yaw), 0.],
                             [math.sin(yaw), math.cos(yaw), 0.], [0., 0., 1.]])
        quaternion = [0., 0., math.sin(yaw/2), math.cos(yaw/2)]
        palm = cup-rotation @ np.asarray(offset)
        action('raise_front', 'move_ee', side='left', position=[-.07, .34, .09], duration=1.5)
        action('raise_clear', 'move_ee', side='left', position=[-.04, .34, .30],
               quaternion_xyzw=[0., 0., 0., 1.], duration=2.)
        action('orient_clear', 'move_ee', side='left', position=[-.04, .34, .30],
               quaternion_xyzw=quaternion, duration=1.5)
        behind = palm-rotation @ [.13, 0., 0.]
        high = behind.copy(); high[2] = .30
        linear('behind_high', high, quaternion, 2.)
        linear('lower_behind', behind, quaternion, 2.)
        linear('approach_open', palm, quaternion, 2.)
        names = [f'left_hand_{name}_joint' for name in robot.profile['finger_order']]
        action('close', 'set_joints', targets=dict(zip(names, close)), duration=1.5)
        action('grip_settle', 'wait', seconds=.5)
        require_grip()
        target = palm.copy(); target[2] += .02
        linear('test_lift_2cm', target, quaternion, 1.)
        action('test_lift_hold', 'wait', seconds=.5)
        require_grip(lifted=True)
        target[2] += .105
        linear('lift_12_5cm', target, quaternion, 2.)
        action('hold', 'wait', seconds=1.5)
    except ActionFailure as exc:
        robot.stop(str(exc))
    finally:
        write_json(folder / 'actions.json', actions)
        result = robot.finish()
    print('DIRECT_RESULT', json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offset', nargs=3, type=float, default=[.045, -.055, -.052])
    parser.add_argument('--close', nargs=7, type=float, default=[0., .65, .65, -.8, -.6, -.8, -.6])
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--yaw', type=float, default=.7)
    parser.add_argument('--images', action='store_true')
    parser.add_argument('--memory', type=Path, help='Reuse verified engineering parameters; does not call Astra')
    args = parser.parse_args()
    if args.memory:
        memory = json.loads(args.memory.read_text())
        if memory.get('kind') != 'engineering_memory_candidate' or not memory['independent_verification']['verified_success']:
            parser.error('Expected a physically verified engineering memory')
        parameters = memory['reusable_parameters']
        args.offset, args.close, args.yaw = (parameters['cup_in_palm_m'], parameters['close_angles'],
                                           parameters['palm_yaw_rad'])
    result = run(args.output, args.offset, args.close, args.seed, args.images, args.yaw, args.memory)
    raise SystemExit(0 if result['independent_success'] else 1)
