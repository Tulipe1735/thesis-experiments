"""Robot geometry against RGB-D cup proxies; never loads the task physics model."""
from copy import deepcopy
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from .runtime import CountedPort  # initializes the frozen controller import path
from arm_planner import ArmPlanner, yaw_rotation
from vision_grasp_v2 import PITCHES, YAWS


class CupObstaclePlanner(ArmPlanner):
    def __init__(self, obstacles, carried_offset=None):
        super().__init__()
        # Export only the robot-only kinematic model, then append perceived proxies.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'robot.xml'
            mujoco.mj_saveLastXML(str(path), self.model)
            root = ET.parse(path).getroot()
        world = root.find('worldbody')
        if carried_offset is not None:
            wrist = root.find(".//body[@name='left_wrist_yaw_link']")
            ET.SubElement(wrist, 'geom', name='carried_cup_proxy', type='cylinder',
                          pos=' '.join(map(str, np.asarray(carried_offset)+[.09, 0., .049])),
                          size='.045 .053', contype='0', conaffinity='0')
        for i, obstacle in enumerate(obstacles):
            bottom = np.asarray(obstacle['cup_bottom_position_m'])
            ET.SubElement(world, 'geom', name=f'visual_obstacle_{i}', type='cylinder',
                          pos=' '.join(map(str, bottom+[0., 0., .049])), size='.045 .053',
                          contype='0', conaffinity='0')
        self.model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
        self.site = self.model.site('left_palm').id
        self.obstacles = [self.model.geom(f'visual_obstacle_{i}').id for i in range(len(obstacles))]
        self.arm_geoms = [i for i in range(self.model.ngeom)
                          if self.model.geom_contype[i] and
                          self.model.body(int(self.model.geom_bodyid[i])).name.startswith(
                              ('left_shoulder', 'left_elbow', 'left_wrist', 'left_hand'))]
        if carried_offset is not None:
            self.arm_geoms.append(self.model.geom('carried_cup_proxy').id)

    def clearance(self, data):
        worst = dict(distance_m=.1, robot_body=None, obstacle=None)
        for obstacle in self.obstacles:
            for geom in self.arm_geoms:
                distance = mujoco.mj_geomDistance(self.model, data, geom, obstacle, .1, None)
                if distance < worst['distance_m']:
                    worst = dict(distance_m=float(distance),
                                 robot_body=self.model.body(int(self.model.geom_bodyid[geom])).name,
                                 obstacle=self.model.geom(obstacle).name)
        return worst

    def checked_path(self, state, goals, yaw):
        data = self.start(state)
        rows = []
        for stage, goal in goals:
            goal = np.asarray(goal)
            start = data.site_xpos[self.site].copy()
            count = 1 if stage == 'orient_clear' else max(1, int(np.ceil(np.linalg.norm(goal-start)/.025)))
            for step in range(1, count+1):
                before = data.qpos.copy()
                result = self.solve(data, start+(goal-start)*step/count, yaw)
                after = data.qpos.copy()
                jump = float(np.max(np.abs(after[self.qids]-before[self.qids])))
                # Check intermediate joint configurations, including wrist rotation.
                samples = max(2, int(np.ceil(jump/.025)))
                clearance = dict(distance_m=.1, robot_body=None, obstacle=None)
                for fraction in np.linspace(0., 1., samples+1):
                    data.qpos[:] = before+(after-before)*fraction
                    mujoco.mj_kinematics(self.model, data)
                    current = self.clearance(data)
                    if current['distance_m'] < clearance['distance_m']:
                        clearance = current
                data.qpos[:] = after
                mujoco.mj_kinematics(self.model, data)
                row = dict(stage=stage, step=step, max_joint_delta_rad=jump,
                           clearance=clearance, **result)
                rows.append(row)
                if not result['reachable'] or (stage != 'orient_clear' and jump > .5) or clearance['distance_m'] < .003:
                    return dict(reachable=False, failed_at=row, path=rows, collision_checked=True)
        return dict(reachable=True, path=rows, collision_checked=True,
                    goals=[(stage, np.asarray(goal).tolist()) for stage, goal in goals],
                    min_clearance_m=min(row['clearance']['distance_m'] for row in rows))

    def select(self, state, cup_position, offset, preferred=.7):
        trials = []
        current = state['joints']['waist_pitch_joint']['q']
        for pitch in [current]+[p for p in PITCHES if p > current+.025]:
            trial_state = deepcopy(state)
            trial_state['joints']['waist_pitch_joint']['q'] = pitch
            for backoff, forward in [(b, f) for f in (False, True) for b in (.13, .07, .045)]:
                for yaw in dict.fromkeys([preferred]+YAWS):
                    palm = np.asarray(cup_position)-yaw_rotation(yaw)@np.asarray(offset)
                    behind = palm-yaw_rotation(yaw)@[backoff, 0., 0.]
                    high = behind.copy()
                    high[2] = .30
                    goals = [('orient_clear', [-.04, .34, .30])]
                    if forward:
                        goals.append(('forward_clear', [max(.20, high[0]), .34, .30]))
                    goals += [('behind_high', high), ('lower_behind', behind), ('approach_open', palm),
                              ('test_lift', palm+[0., 0., .02]), ('main_lift', palm+[0., 0., .125])]
                    path = self.checked_path(trial_state, goals, yaw)
                    trials.append(dict(torso_pitch_rad=pitch, yaw_rad=yaw, backoff_m=backoff,
                                       forward=forward, reachable=path['reachable'], failed_at=path.get('failed_at')))
                    if path['reachable']:
                        path['route'] = 'visual_obstacle_checked'
                        return dict(selected_yaw_rad=yaw if abs(pitch-current)<.025 else None,
                                    selected_offset_m=list(offset),
                                    suggested_waist_pitch_rad=pitch if abs(pitch-current)>=.025 else None,
                                    candidates=trials, path=path, collision_checked=True,
                                    policy='RGBD non-target cup proxies, 4mm inflation, 3mm clearance, joint interpolation')
        return dict(selected_yaw_rad=None, selected_offset_m=None, suggested_waist_pitch_rad=None,
                    candidates=trials, collision_checked=True)
