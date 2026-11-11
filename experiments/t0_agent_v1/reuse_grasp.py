"""Sensor adapters around the existing successful cup/orange engineering tools."""
import math
from copy import deepcopy
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.optimize import least_squares

from .training_runtime import ensure_runtime
ensure_runtime()
from .common import ROOT, read, relative, write_new
from .tabletop_training_plant import TabletopPlant, configure_robot, independent_verify
from .tray_tools import TrayCupTools, TrayArmPlanner
from arm_planner import ArmPlanner
from rgbd_cup import PerceptionError, point_cloud
from run_direct_grasp import ActionFailure

PROGRAM = ['locate', 'preflight', 'prepare', 'preflight', 'approach',
           'close_and_test', 'lift_and_hold', 'finish']
BASELINE = dict(program=PROGRAM, parameters=dict(
    preferred_yaw=.7, offset_delta_m=[0., 0., 0.], closure='adaptive'))


def solve_pose(planner, data, position, quaternion=None, position_tolerance=.004, orientation_tolerance=.12):
    """Preserve the legacy full-orientation IK, using its robot-only model."""
    import mujoco
    m = planner.model
    mujoco.mj_kinematics(m, data)
    goal = np.empty(4)
    mujoco.mju_mat2Quat(goal, data.site_xmat[planner.site])
    if quaternion is not None:
        goal = np.asarray(quaternion, float)[[3, 0, 1, 2]]
        goal /= np.linalg.norm(goal)
    jp, jr = np.zeros((3, m.nv)), np.zeros((3, m.nv))
    best = None
    for _ in range(160):
        mujoco.mj_kinematics(m, data)
        mujoco.mj_comPos(m, data)
        error = np.asarray(position)-data.site_xpos[planner.site]
        actual, angular = np.empty(4), np.empty(3)
        mujoco.mju_mat2Quat(actual, data.site_xmat[planner.site])
        mujoco.mju_subQuat(angular, goal, actual)
        angular = data.site_xmat[planner.site].reshape(3, 3)@angular
        p, a = float(np.linalg.norm(error)), float(np.linalg.norm(angular))
        if best is None or p+.12*a < best[0]:
            best = (p+.12*a, data.qpos[planner.qids].copy(), p, a)
        if p < position_tolerance and a < orientation_tolerance:
            break
        mujoco.mj_jacSite(m, data, jp, jr, planner.site)
        J = np.vstack((jp[:, planner.vids], .12*jr[:, planner.vids]))
        step = J.T@np.linalg.solve(J@J.T+np.eye(6)*.008**2, np.r_[error, .12*angular])
        step /= max(1., np.max(abs(step))/.12)
        data.qpos[planner.qids] = np.clip(data.qpos[planner.qids]+step,
            m.jnt_range[planner.ids, 0], m.jnt_range[planner.ids, 1])
    data.qpos[planner.qids] = best[1]
    mujoco.mj_kinematics(m, data)
    return dict(reachable=best[2] <= .006 and best[3] <= .18,
                position_error_m=best[2], orientation_error_rad=best[3])


def prepared_state(planner, state):
    """Preview the two inherited preparation poses without advancing physics."""
    data = planner.start(state)
    rows = []
    for name, position, quaternion in (
        ('raise_front', [-.07, .34, .09], None),
        ('raise_clear', [-.04, .34, .30], [0., 0., 0., 1.]),
    ):
        row = dict(stage=name, **solve_pose(planner, data, position, quaternion))
        rows.append(row)
        if not row['reachable']:
            return None, rows
    result = deepcopy(state)
    for j, q in zip(planner.ids, data.qpos[planner.qids]):
        result['joints'][planner.model.joint(j).name]['q'] = float(q)
    return result, rows


def locate_target(sensor, task):
    """Reuse calibrated RGB-D projection and support fitting, adapt target colour."""
    rgb = np.asarray(sensor['rgb'], float)/255.
    cloud = point_cloud(sensor['depth_m'], sensor['K'], sensor['T_optical_to_pelvis'])
    workspace = (np.isfinite(cloud).all(axis=-1) & (cloud[..., 0] > .1)
        & (cloud[..., 0] < 1.5) & (abs(cloud[..., 1]) < .85)
        & (cloud[..., 2] > -.05) & (cloud[..., 2] < .5))
    heights = cloud[..., 2][workspace]
    if len(heights) < 100:
        raise PerceptionError('Insufficient visible depth')
    hist, edges = np.histogram(heights, bins=np.arange(-.05, .4, .002))
    support = edges[int(hist.argmax())]+.001
    table = workspace & (abs(cloud[..., 2]-support) < .004)
    points = cloud[table]
    plane = np.linalg.lstsq(np.c_[points[:, :2], np.ones(len(points))], points[:, 2], rcond=None)[0]
    if np.linalg.norm(plane[:2]) > .12:
        raise PerceptionError('Visible support plane too tilted')
    height = cloud[..., 2] - (cloud[..., :2]@plane[:2]+plane[2])
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    nominal = np.asarray(task['nominal_rgba'][:3])
    if task['target_category'] == 'fruit':
        colour = (r > 1.25*g) & (g > 1.5*b) & (g > .1) & (r > .25)
    elif task['target_category'] == 'bottle':
        colour = (g > 1.4*r) & (g > 1.2*b) & (g > .12)
    elif np.ptp(nominal) > .15:
        colour = (r > 1.5*g) & (r > 1.5*b) & (r > .18)
    else:
        colour = (rgb.min(axis=-1) > .52) & (np.ptp(rgb, axis=-1) < .22)
    mask = workspace & colour & (height > .012) & (height < .25)
    labels, count = ndimage.label(mask)
    candidates = []
    for label in range(1, count+1):
        selected = labels == label
        if selected.sum() < 25:
            continue
        xyz = cloud[selected]
        lo, hi = np.percentile(xyz, [3, 97], axis=0)
        if not (.012 < hi[2]-lo[2] < .26 and max(hi[:2]-lo[:2]) < .2):
            continue
        candidates.append((float(rgb[selected].mean()), selected, xyz))
    candidates.sort(key=lambda item: item[0], reverse=True)
    if not candidates or len(candidates) > 1 and candidates[0][0]-candidates[1][0] < .07:
        raise PerceptionError('Target colour components absent or ambiguous')
    _, selected, points = candidates[0]
    lo, hi = np.percentile(points, [3, 97], axis=0)
    center = (lo+hi)/2
    radius = .04
    rms = None
    if task['target_category'] == 'fruit':
        # The same visible-surface sphere fit as the successful T03 adapter;
        # radius is estimated within a public class range for scaled specimens.
        seed = np.linalg.lstsq(np.c_[2*points, np.ones(len(points))],
                              np.sum(points**2, axis=1), rcond=None)[0]
        radius = float(np.sqrt(max(.0004, seed[3]+seed[:3]@seed[:3])))
        fit = least_squares(lambda values: np.linalg.norm(points-values[:3], axis=1)-values[3],
            np.r_[seed[:3], np.clip(radius, .025, .065)],
            bounds=(np.r_[lo-.1, .025], np.r_[hi+.1, .065]), loss='soft_l1', f_scale=.001)
        center, radius = fit.x[:3], float(fit.x[3])
        rms = float(np.sqrt(np.mean((np.linalg.norm(points-center, axis=1)-radius)**2)))
        if rms > .003:
            raise PerceptionError('Visible sphere fit confidence insufficient')
    else:
        # Retain the legacy cylinder fit. Handles/top rims are rejected as
        # residuals by the robust loss; this is an unvalidated asset adaptation.
        wall = points[(points[:, 2] > plane[2]+.016) & (points[:, 2] < plane[2]+.075), :2]
        if len(wall) < 25:
            raise PerceptionError('Insufficient visible cylindrical wall points')
        fits = []
        for forward in (0., .03, .06):
            start = np.r_[np.median(wall, axis=0)+[forward, 0.], .04]
            fit = least_squares(lambda values: np.linalg.norm(wall-values[:2], axis=1)-values[2],
                start, bounds=(np.r_[lo[:2]-.1, .02], np.r_[hi[:2]+.1, .075]),
                loss='soft_l1', f_scale=.001)
            error = abs(np.linalg.norm(wall-fit.x[:2], axis=1)-fit.x[2])
            fits.append((float(np.median(error)), fit.x, float(np.mean(error < .003))))
        residual, values, inliers = min(fits, key=lambda row: row[0])
        if residual > .004 or inliers < .5:
            raise PerceptionError('Cylindrical wall fit confidence insufficient')
        center[:2], radius = values[:2], float(values[2])
        if radius<.0205 or radius>.0745:
            raise PerceptionError('Cylindrical radius at class bound; occluded arc cannot locate center reliably')
    bottom = np.r_[center[:2], plane@np.r_[center[:2], 1.]]
    return dict(cup_bottom_position_m=bottom.tolist(), visible_center_pelvis_m=center.tolist(),
        radius_estimate_m=radius, fit_rms_m=rms, table_plane=plane.tolist(),
        observation_id=f"head_{sensor['timestamp_s']:.3f}",
        observation_simulation_seconds=sensor['timestamp_s'], source='head_RGBD_fit_adapter',
        target_category=task['target_category'], ground_truth_used=False,
        limitation='Colour and shape fit adapted from prior engineering tools; new asset grasp unvalidated')


class ReusePort:
    """Only approved observations and validated left-joint commands reach tools."""
    def __init__(self, plant):
        self.plant = plant
        self.kinematics = ArmPlanner()

    def state(self):
        obs = self.plant.observation()
        return dict(simulation_seconds=obs['simulation_seconds'], joints=obs['joints'],
            palms=dict(left=obs['left_palm']), controller=dict(guard=obs['guard']),
            approximate_contact_load_N=dict(left={n.removesuffix('_joint')+'_link': v
                for n, v in obs['tactile_joint_load_N'].items()}))

    def invoke(self, tool, arguments):
        if tool == 'wait':
            count = max(1, math.ceil(float(arguments['seconds'])/.2))
            result = None
            for _ in range(count):
                result = self.plant.dispatch(dict(op='wait', duration=.2))
                if result['status'] != 'EXECUTED':
                    break
            return result
        targets = arguments.get('targets')
        if tool == 'move_ee':
            if arguments['side'] != 'left':
                raise ActionFailure('Only left hand allowed')
            current = self.state()
            data = self.kinematics.start(current)
            plan = solve_pose(self.kinematics, data, arguments['position'], arguments.get('quaternion_xyzw'))
            if not plan['reachable']:
                return dict(status='POSE_IK_REJECTED', **plan)
            targets = {self.kinematics.model.joint(j).name: float(value)
                for j, value in zip(self.kinematics.ids, data.qpos[self.kinematics.qids])}
        elif tool != 'set_joints':
            raise ActionFailure('Unknown physical tool')
        from experiments.grow_up_v2.plant import ALLOWED, HAND
        if not set(targets) <= ALLOWED:
            raise ActionFailure('Reuse attempted a non-left joint')
        first = {n: float(self.plant.targets[self.plant.ai[n]]) for n in targets}
        count = max(1, math.ceil(float(arguments.get('duration', .2))/.2),
            max(math.ceil(abs(v-first[n])/(.04 if n in HAND else .025)) for n, v in targets.items()))
        result = None
        for step in range(1, count+1):
            values = {n: first[n]+(value-first[n])*step/count for n, value in targets.items()}
            result = self.plant.dispatch(dict(op='set_joints', targets=values, duration=.2))
            if result['status'] != 'EXECUTED':
                break
        return result


class ReuseGrasp(TrayCupTools):
    def __init__(self, port, folder, task, parameters):
        super().__init__(port, folder, {}, [0., 0., 0.], False)
        self.public_task, self.parameters = task, parameters
        self.offset += np.asarray(parameters['offset_delta_m'])
        self.preferred_yaw = parameters['preferred_yaw']
        self.closure = parameters['closure']
        self.obstacles = []

    def action(self, stage, tool, **arguments):
        result = super().action(stage, tool, **arguments)
        if result.get('status') != 'EXECUTED':
            raise ActionFailure(stage+': '+str(result.get('status')))
        return result

    def locate(self, pixel_hint=None):
        if self.phase not in ('initial', 'ready'):
            raise ActionFailure('Relocalization not allowed during grasp')
        estimate = locate_target(self.port.plant.rgbd(), self.public_task)
        if self.initial_visual_cup is not None and np.linalg.norm(
            np.asarray(estimate['cup_bottom_position_m'])-self.initial_visual_cup) > .04:
            raise PerceptionError('Selected target moved during preparation')
        self.initial_visual_cup = np.asarray(estimate['cup_bottom_position_m'])
        self.estimate = estimate
        self.estimates.append(estimate)
        self.save()
        return estimate

    def preflight(self):
        if self.estimate is None or self.phase not in ('initial', 'ready'):
            raise ActionFailure('Locate before preflight')
        planner, trials = TrayArmPlanner(), []
        state = self.port.state()
        preparation = []
        if self.phase == 'initial':
            state, preparation = prepared_state(planner, state)
            if state is None:
                self.plan = dict(selected_yaw_rad=None, selected_offset_m=None,
                    suggested_waist_pitch_rad=None, candidates=[], preparation_preview=preparation)
                return dict(reachable=False, reason='inherited preparation IK failed', preparation_preview=preparation)
        for yaw in dict.fromkeys([self.preferred_yaw, .7, .6, .55, .4, .25, 0., -.2]):
            path = planner.path(state, self.estimate['cup_bottom_position_m'], yaw, self.offset)
            trials.append(dict(yaw=yaw, **path))
            if path['reachable']:
                self.plan = dict(selected_yaw_rad=yaw, selected_offset_m=self.offset.tolist(), path=path,
                                 suggested_waist_pitch_rad=None, candidates=trials)
                break
        else:
            self.plan = dict(selected_yaw_rad=None, selected_offset_m=None,
                             suggested_waist_pitch_rad=None, candidates=trials)
        self.plan_history.append(self.plan)
        # Legacy tools write only inside a fresh episode directory.
        from diagnose_grasp import write_json
        write_json(self.folder/'kinematic_preflight.json', self.plan)
        return dict(reachable=self.plan['selected_yaw_rad'] is not None,
            selected_yaw_rad=self.plan['selected_yaw_rad'], fixed_waist=True,
            source='prior_TrayArmPlanner_robot_only_IK_with_legal_visual_target', collision_checked=False)


def validate_recipe(value):
    if type(value) is not dict or set(value) != {'program', 'parameters'} or value['program'] != PROGRAM:
        raise ValueError('Require the fixed safe stage sequence')
    p = value['parameters']
    if type(p) is not dict or set(p) != {'preferred_yaw', 'offset_delta_m', 'closure'}:
        raise ValueError('Unknown skill parameters')
    if type(p['preferred_yaw']) not in (int, float) or not -.2 <= p['preferred_yaw'] <= .9:
        raise ValueError('Yaw outside inherited envelope')
    if type(p['offset_delta_m']) is not list or len(p['offset_delta_m']) != 3 or any(
        type(v) not in (int, float) or not math.isfinite(v) or abs(v) > .025 for v in p['offset_delta_m']):
        raise ValueError('Offset repair outside bounded envelope')
    if p['closure'] not in ('adaptive', 'simultaneous'):
        raise ValueError('Unknown inherited closure')
    return value


def execute(scene, case, output, recipe, budget=60.):
    import mujoco
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    model = mujoco.MjModel.from_xml_path(str(scene))
    plant = TabletopPlant(case['instance'], case['case_path'], model, output, budget=budget)
    plant.head_image(output/'initial_head.jpg')
    port = ReusePort(plant)
    folder = output/'tools'
    folder.mkdir(exist_ok=False)
    controller = ReuseGrasp(port, folder, case['task'], validate_recipe(recipe)['parameters'])
    error, state, calls, feedback = None, None, 0, []
    try:
        port.invoke('wait', dict(seconds=.6))
        for tool in recipe['program']:
            calls += 1
            if tool == 'finish':
                if controller.phase != 'complete':
                    raise ActionFailure('Finish requires completed lift/hold')
                result = dict(status='ENDED_AWAITING_INDEPENDENT_VERIFICATION')
            else:
                result = getattr(controller, tool)()
            feedback.append(dict(tool=tool, result=result, phase=controller.phase))
            if tool == 'preflight' and not result['reachable']:
                raise ActionFailure('PRIOR_SKILL_APPROACH_PATH_UNREACHABLE')
            if plant.guard:
                raise ActionFailure('ROBOT_GUARD: '+plant.guard)
    except Exception as exc:
        error = dict(type=type(exc).__name__, message=str(exc)[:500])
    finally:
        state = dict(phase=controller.phase)
        runtime = plant.save(error, state, dict(execution='validated_declarative_recipe_no_arbitrary_model_code'), calls)
    verdict = independent_verify(output, case['instance'], model, initial_valid=True)
    write_new(output/'tool_feedback.json', feedback)
    return dict(alias=case['alias'], verified_task_success=verdict['verified_task_success'],
        simulation_seconds=runtime['simulation_seconds'], high_level_tool_calls=calls,
        low_level_commands=runtime['low_level_commands'], error=error, guard=plant.guard,
        legal_tool_feedback=feedback, folder=relative(output), initial_hash=plant.initial_hash)
