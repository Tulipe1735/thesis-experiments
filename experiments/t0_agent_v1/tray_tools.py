"""Camera-derived tray pose and bounded repeated cup-to-tray engineering actions."""
import math
import numpy as np
from PIL import Image
from scipy import ndimage

from .common import append_event, write_new
from .skills import CupTools
from .two_cup_tools import cup_hints
from .tray_collision import CupObstaclePlanner
from .tray_perception import separated_cups
from arm_planner import ArmPlanner, yaw_rotation
from rgbd_cup import PerceptionError, from_observation, point_cloud
from run_direct_grasp import ActionFailure
from vision_grasp_v2 import ArmPlannerV2
from diagnose_grasp import write_json


def approach_goals(cup_position, yaw, offset):
    palm = np.asarray(cup_position)-yaw_rotation(yaw) @ np.asarray(offset)
    behind = palm-yaw_rotation(yaw) @ [.13, 0., 0.]
    high = behind.copy()
    high[2] = .30
    forward = np.array([max(.20, high[0]), .34, .30])
    return [('orient_clear', np.array([-.04, .34, .30])), ('forward_clear', forward),
            ('behind_high', high), ('lower_behind', behind), ('approach_open', palm),
            ('test_lift', palm+[0., 0., .02]), ('main_lift', palm+[0., 0., .125])]


class TrayArmPlanner(ArmPlannerV2):
    def select(self, state, cup_position, offset, preferred=.7):
        original = ArmPlannerV2().select(state, cup_position, offset, preferred)
        if original['selected_yaw_rad'] is not None or original['suggested_waist_pitch_rad'] is not None:
            return original
        return super().select(state, cup_position, offset, preferred)

    def path(self, state, cup_position, yaw, offset):
        original = super().path(state, cup_position, yaw, offset)
        if original['reachable']:
            return original
        # A diagonal from the lateral clear pose towards the central cup can
        # cross an unreachable inner-arm region. Move forward before inward.
        data = self.start(state)
        rows = []
        for stage, goal in approach_goals(cup_position, yaw, offset):
            start = data.site_xpos[self.site].copy()
            count = 1 if stage == 'orient_clear' else max(1, int(np.ceil(np.linalg.norm(goal-start)/.025)))
            for step in range(1, count+1):
                previous = data.qpos[self.qids].copy()
                result = self.solve(data, start+(goal-start)*step/count, yaw)
                jump = float(np.max(np.abs(data.qpos[self.qids]-previous)))
                row = dict(stage=stage, step=step, max_joint_delta_rad=jump, **result)
                rows.append(row)
                if not result['reachable'] or (stage != 'orient_clear' and jump > .5):
                    return dict(yaw_rad=yaw, reachable=False, failed_at=row, path=rows,
                                collision_checked=False, route='forward_then_inward')
        return dict(yaw_rad=yaw, reachable=True, path=rows, collision_checked=False,
                    route='forward_then_inward', source='robot_proprioception_and_RGBD_target',
                    max_position_error_m=max(row['position_error_m'] for row in rows))


def locate_tray(observation):
    rgb = np.asarray(Image.open(observation['head_rgb_path']).convert('RGB'), dtype=float)
    cloud = point_cloud(np.load(observation['depth_path'], allow_pickle=False),
                        observation['K'], observation['T_optical_to_pelvis'])
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    masks = dict(red=(r > 1.5*g) & (r > 1.5*b) & (r > 60),
                 green=(g > 1.5*r) & (g > 1.5*b) & (g > 60),
                 yellow=(r > 1.6*b) & (g > 1.6*b) & (r > .7*g) & (g > .7*r) & (r > 60),
                 magenta=(r > 1.5*g) & (b > 1.5*g) & (r > .6*b) & (b > .6*r) & (b > 60))
    workspace = (np.isfinite(cloud).all(axis=-1) & (cloud[:, :, 0] > .1) & (cloud[:, :, 0] < .7)
                 & (cloud[:, :, 1] > -.12) & (cloud[:, :, 1] < .7)
                 & (cloud[:, :, 2] > .10) & (cloud[:, :, 2] < .24))
    markers = {}
    for color, mask in masks.items():
        labels, count = ndimage.label(mask & workspace)
        sizes = np.bincount(labels.ravel())
        if count == 0 or sizes[1:].max() < 10:
            raise PerceptionError('Missing visible tray marker: '+color)
        label = 1+int(sizes[1:].argmax())
        markers[color] = np.median(cloud[labels == label], axis=0)
    a, b, c, d = [markers[key] for key in ('red', 'green', 'yellow', 'magenta')]
    long = (b-a+c-d)/2
    short = (d-a+c-b)/2
    if not (.375 < np.linalg.norm(long) < .410 and .055 < np.linalg.norm(short) < .090):
        raise PerceptionError('Tray marker dimensions inconsistent with compatible tray prior')
    long /= np.linalg.norm(long)
    short -= long * (short @ long)
    short /= np.linalg.norm(short)
    normal = np.cross(long, short)
    if normal[2] < .98:
        raise PerceptionError('Tray pose is tilted or marker order invalid')
    center = np.mean([a, b, c, d], axis=0) - normal*.0004
    return dict(center_floor_pelvis_m=center.tolist(), axis_long=long.tolist(), axis_short=short.tolist(),
                normal=normal.tolist(), inner_half_xy_m=[.214, .054],
                observation_id=observation['observation_id'], marker_points={k: v.tolist() for k,v in markers.items()},
                source='head_RGBD_four_visible_colored_markers', ground_truth_used=False,
                limitation='calibrated marked tray; cached pelvis-frame pose under standing control')


def visible_cups(observation, expected_count=None):
    found = []
    for hint in cup_hints(observation):
        try:
            item = from_observation(observation, hint)
        except PerceptionError:
            continue
        position = np.asarray(item['cup_bottom_position_m'])
        if not any(np.linalg.norm(position-np.asarray(old['cup_bottom_position_m'])) < .03 for old in found):
            found.append(item)
    if expected_count is not None and len(found) < expected_count:
        for item in separated_cups(observation):
            if not any(np.linalg.norm(np.asarray(item['cup_bottom_position_m'])-
                                      old['cup_bottom_position_m']) < .03 for old in found):
                found.append(item)
    return sorted(found, key=lambda item: item['cup_bottom_position_m'][1], reverse=True)


def outside_tray(cups, tray):
    center = np.asarray(tray['center_floor_pelvis_m'])
    return [item for item in cups
            if not (abs((np.asarray(item['cup_bottom_position_m'])-center) @ tray['axis_long']) < .22
                    and abs((np.asarray(item['cup_bottom_position_m'])-center) @ tray['axis_short']) < .06)]


def available_cups(observation, tray, expected_count=None):
    return outside_tray(visible_cups(observation, expected_count), tray)


class TrayCupTools(CupTools):
    def __init__(self, port, folder, tray, target, subsequent, select_rightmost=False, expected_obstacles=0):
        super().__init__(port, folder, 'place_cup', [-.06, 0., 0.])
        self.tray, self.target = tray, np.asarray(target)
        self.subsequent = subsequent
        self.select_rightmost = select_rightmost
        self.place_palm = None
        self.obstacles = []
        self.expected_obstacles = expected_obstacles

    def linear(self, stage, position, duration):
        if self.obstacles:
            carried = self.offset if self.phase in ('tested', 'complete', 'transferred') else None
            planner = CupObstaclePlanner(self.obstacles, carried)
            plan = planner.checked_path(self.port.state(), [(stage, position)], self.yaw)
            append_event(self.folder/'motion_collision_checks.jsonl', dict(stage=stage, plan=plan))
            if not plan['reachable']:
                raise ActionFailure('VISUAL_OBSTACLE_MOTION_REJECTED: '+stage)
        return super().linear(stage, position, duration)

    def locate(self, pixel_hint=None):
        if self.phase not in ('initial', 'ready'):
            raise ActionFailure('Cannot relocalize during grasp')
        observation = self.port.observe()
        all_cups = visible_cups(observation, self.expected_obstacles+1)
        found = outside_tray(all_cups, self.tray)
        if not found:
            raise PerceptionError('No uncollected cup visible outside tray')
        if self.initial_visual_cup is None:
            result = found[-1] if self.select_rightmost else found[0]
            self.initial_visual_cup = np.asarray(result['cup_bottom_position_m'])
        else:
            result = min(found, key=lambda item: np.linalg.norm(np.asarray(item['cup_bottom_position_m'])-self.initial_visual_cup))
            if np.linalg.norm(np.asarray(result['cup_bottom_position_m'])-self.initial_visual_cup) > .04:
                raise PerceptionError('Lost selected cup during preparation')
        self.estimate = result
        self.obstacles = [item for item in all_cups
                          if np.linalg.norm(np.asarray(item['cup_bottom_position_m'])-
                                            np.asarray(result['cup_bottom_position_m'])) > .06]
        if len(self.obstacles) != self.expected_obstacles:
            raise PerceptionError('Incomplete non-target cup observation; do not plan through unseen cups')
        for item in self.obstacles:
            pos = np.asarray(item['cup_bottom_position_m'])
            delta = pos-np.asarray(self.tray['center_floor_pelvis_m'])
            if abs(delta @ self.tray['axis_long']) < .22 and abs(delta @ self.tray['axis_short']) < .06:
                # Frozen cup fitting estimates the table plane. Raised support is
                # obtained from the visible tray markers, not the scene state.
                pos -= (delta @ self.tray['normal'])*np.asarray(self.tray['normal'])
                item['cup_bottom_position_m'] = pos.tolist()
                item['support_height_source'] = self.tray['source']
        write_json(self.folder/'visual_obstacles.json', self.obstacles)
        self.estimates.append(result)
        self.save()
        return result

    def prepare(self):
        if not self.subsequent:
            return super().prepare()
        if self.phase != 'initial':
            raise ActionFailure('Prepare only once per cup')
        current = self.port.state()['palms']['left']['position_m']
        self.action('return_raise_vertical', 'move_ee', side='left',
                    position=[current[0], current[1], .30], duration=1.5)
        self.action('return_clear', 'move_ee', side='left', position=[-.04, .34, .30],
                    quaternion_xyzw=[0., 0., 0., 1.], duration=2.)
        self.phase = 'ready'
        return self.locate()

    def preflight(self):
        if self.phase != 'ready' or self.estimate is None:
            raise ActionFailure('Prepare and locate before tray-task planning')
        planner = CupObstaclePlanner(self.obstacles) if self.obstacles else TrayArmPlanner()
        self.plan = planner.select(self.port.state(), self.estimate['cup_bottom_position_m'],
                                            self.offset, self.preferred_yaw)
        self.plan_history.append(dict(observation_id=self.estimate['observation_id'],
                                      simulation_seconds=self.port.state()['simulation_seconds'], plan=self.plan))
        write_json(self.folder/'kinematic_preflight_history.json', self.plan_history)
        write_json(self.folder/'kinematic_preflight.json', self.plan)
        return dict(reachable=self.plan['selected_yaw_rad'] is not None,
                    selected_yaw_rad=self.plan['selected_yaw_rad'],
                    suggested_waist_pitch_rad=self.plan['suggested_waist_pitch_rad'],
                    route=self.plan.get('path', {}).get('route', 'original'),
                    collision_checked=self.plan.get('collision_checked', False))

    def approach(self):
        if self.plan and self.plan.get('path', {}).get('route') == 'visual_obstacle_checked':
            if self.phase != 'ready' or self.plan['selected_yaw_rad'] is None:
                raise ActionFailure('No collision-checked approach')
            self.yaw = self.plan['selected_yaw_rad']
            self.offset = np.asarray(self.plan['selected_offset_m'])
            self.palm = np.asarray(self.estimate['cup_bottom_position_m'])-yaw_rotation(self.yaw)@self.offset
            for stage, goal in self.plan['path']['goals']:
                if stage in ('test_lift', 'main_lift'):
                    break
                if stage == 'orient_clear':
                    self.action(stage, 'move_ee', side='left', position=goal,
                                quaternion_xyzw=[0., 0., math.sin(self.yaw/2), math.cos(self.yaw/2)], duration=1.5)
                else:
                    self.linear(stage, goal, 2.)
            self.phase = 'approached'
            return dict(status='APPROACHED', route='visual_obstacle_checked', target_source='head_RGBD_only')
        if not self.plan or self.plan.get('path', {}).get('route') != 'forward_then_inward':
            return super().approach()
        if self.phase != 'ready' or self.plan['selected_yaw_rad'] is None:
            raise ActionFailure('No reachable tray-task approach')
        if self.port.state()['simulation_seconds']-self.estimate['observation_simulation_seconds'] > 30.:
            raise ActionFailure('Stale visual target')
        self.yaw = self.plan['selected_yaw_rad']
        self.offset = np.asarray(self.plan['selected_offset_m'])
        goals = approach_goals(self.estimate['cup_bottom_position_m'], self.yaw, self.offset)
        self.palm = goals[4][1]
        self.action('orient_clear', 'move_ee', side='left', position=goals[0][1].tolist(),
                    quaternion_xyzw=[0., 0., math.sin(self.yaw/2), math.cos(self.yaw/2)], duration=1.5)
        for stage, goal in goals[1:5]:
            self.linear(stage, goal, 2.)
        self.phase = 'approached'
        return dict(status='APPROACHED', route='forward_then_inward', target_source='head_RGBD_only')

    def transfer(self):
        if self.phase != 'complete':
            raise ActionFailure('Lift before moving to tray')
        self.tactile_gate('before_tray_transfer')
        selected = None
        # The single-cup central slot has less inward/high reach margin.
        # Keep transport 12cm above the floor; T02 retains its validated 14cm.
        height = .12 if self.expected_obstacles == 0 else .14
        trials = []
        for yaw in dict.fromkeys([self.yaw, .7, .6, .4, .25, 0., -.2]):
            planner = ArmPlanner()
            state = planner.start(self.port.state())
            palm = self.target-yaw_rotation(yaw) @ self.offset
            if self.expected_obstacles == 0:
                path = CupObstaclePlanner([]).checked_path(self.port.state(),
                    [('transfer', palm+[0., 0., height]), ('lower', palm+[0., 0., .004])], yaw)
                reachable = path['reachable']
                trials.append(dict(yaw=yaw, height=height, path=path))
            else:
                reachable = all(planner.solve(state, palm+[0., 0., z], yaw)['reachable'] for z in (height, .004))
                trials.append(dict(yaw=yaw, height=height, reachable=reachable))
            if reachable:
                selected = yaw, palm
                break
        write_new(self.folder/'transfer_preflight.json', dict(trials=trials,
                  single_cup_height_repair=self.expected_obstacles == 0))
        if selected is None:
            raise ActionFailure('TRAY_TRANSFER_IK_REJECTED')
        self.yaw, self.place_palm = selected
        self.linear('transfer_above_tray', self.place_palm+[0., 0., height], 3.)
        self.tactile_gate('after_tray_transfer')
        self.phase = 'transferred'
        return dict(status='ABOVE_TRAY_NOT_VERIFIED', target_source=self.tray['source'], yaw=self.yaw)

    def lower(self):
        if self.phase != 'transferred':
            raise ActionFailure('Transfer before lowering into tray')
        self.linear('lower_into_tray', self.place_palm+[0., 0., .004], 2.5)
        self.phase = 'lowered'
        return dict(status='LOWERED_INTO_TRAY_NOT_VERIFIED')

    def release_and_retreat(self):
        if self.phase != 'lowered':
            raise ActionFailure('Lower into tray before release')
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('release', 'set_joints', targets=dict.fromkeys(names, 0.), duration=1.5)
        self.action('release_settle', 'wait', seconds=.5)
        current = np.asarray(self.port.state()['palms']['left']['position_m'])
        # Tray targets are nearer the torso. Retract along pelvis -x while
        # preserving the lateral reach, instead of the old palm-yaw direction.
        retreat = None
        trials = []
        for lateral in (0., .04, .08):
            candidate = current+[-.08, lateral, 0.]
            planner = ArmPlanner()
            trial = planner.start(self.port.state())
            reachable = True
            for goal in (candidate, candidate+[0., 0., .08]):
                start = trial.site_xpos[planner.site].copy()
                steps = max(1, int(np.ceil(np.linalg.norm(goal-start)/.025)))
                for step in range(1, steps+1):
                    if not planner.solve(trial, start+(goal-start)*step/steps, self.yaw)['reachable']:
                        reachable = False
                        break
                if not reachable:
                    break
            trials.append(dict(backward_m=.08, lateral_left_m=lateral, reachable=reachable))
            if reachable:
                retreat = candidate
                break
        write_new(self.folder/'retreat_preflight.json', dict(trials=trials, collision_checked=False))
        if retreat is None:
            raise ActionFailure('TRAY_RETREAT_PREFLIGHT_REJECTED')
        self.linear('pelvis_backward_tray_retreat', retreat, 2.)
        self.linear('raise_clear_of_tray', retreat+[0., 0., .08], 2.)
        self.action('tray_placement_settle', 'wait', seconds=2.)
        self.phase = 'placed'
        return dict(status='TRAY_MOTION_ENDED_AWAIT_INDEPENDENT_EVALUATION')


class TrayTaskTools:
    def __init__(self, port, folder, count):
        self.port, self.folder, self.count = port, folder, count
        self.tray = None
        self.completed = 0
        self.tool_steps = 0

    def inspect(self):
        observation = self.port.observe()
        self.tray = locate_tray(observation)
        cups = available_cups(observation, self.tray, self.count)
        if len(cups) != self.count:
            raise PerceptionError(f'Expected {self.count} uncollected cup(s), detected {len(cups)}')
        write_new(self.folder/'visual_initial_task.json', dict(tray=self.tray, cups=cups))
        return dict(tray=self.tray, visible_uncollected_cups=len(cups))

    def collect_next(self):
        if self.tray is None or self.completed >= self.count:
            raise ActionFailure('Inspect first and collect each cup only once')
        slot = 0. if self.count == 1 else [-.15, 0., .15][self.completed]
        target = np.asarray(self.tray['center_floor_pelvis_m'])+slot*np.asarray(self.tray['axis_long'])
        folder = self.folder/f'cup_attempt_{self.completed+1:02}'
        folder.mkdir(exist_ok=False)
        controller = TrayCupTools(self.port, folder, self.tray, target, self.completed > 0,
                                  self.count > 1, self.count-1)
        write_new(folder/'visual_target.json', dict(target_pelvis_m=target.tolist(), tray_observation=self.tray['observation_id'],
                  allocation='rightmost remaining visual cup to next right-to-left tray slot', hidden_truth=False))
        def invoke(name):
            value = getattr(controller, name)()
            self.tool_steps += 1
            append_event(self.folder/'tool_steps.jsonl', dict(cup_attempt=self.completed+1, tool=name,
                         result=value, phase=controller.phase))
            return value
        try:
            invoke('locate')
            invoke('prepare')
            plan = invoke('preflight')
            while not plan['reachable'] and plan['suggested_waist_pitch_rad'] is not None:
                invoke('adjust_reach')
                plan = invoke('preflight')
            if not plan['reachable']:
                raise ActionFailure('CUP_APPROACH_UNREACHABLE')
            for operation in ('approach', 'close_and_test', 'lift_and_hold', 'transfer', 'lower', 'release_and_retreat'):
                invoke(operation)
            self.completed += 1
            return dict(status='CUP_MOTION_COMPLETED_AWAIT_VERIFICATION', motion_completed=self.completed, total=self.count)
        finally:
            controller.save()

    def finish(self):
        if self.completed != self.count:
            raise ActionFailure('All requested cup motions must finish')
        return dict(status='ENDED_FOR_INDEPENDENT_TRAY_VERIFICATION')
