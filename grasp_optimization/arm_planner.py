"""Robot-only kinematic path preflight; the planner cannot load cup scene state."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parent
SUFFIXES = ['shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow',
            'wrist_roll', 'wrist_pitch', 'wrist_yaw']


def yaw_rotation(yaw):
    return np.array([[math.cos(yaw), -math.sin(yaw), 0.],
                     [math.sin(yaw), math.cos(yaw), 0.], [0., 0., 1.]])


class ArmPlanner:
    def __init__(self):
        xml = ET.parse(ROOT/'assets/g1/upstream_model.xml').getroot()
        xml.find('compiler').set('meshdir', str(ROOT/'assets/g1/meshes'))
        for duplicate in xml.findall('worldbody')[1:]+xml.findall('asset')[1:]:
            xml.remove(duplicate)
        pelvis = xml.find(".//body[@name='pelvis']")
        pelvis.set('pos', '0 0 0')
        pelvis.set('quat', '1 0 0 0')
        wrist = xml.find(".//body[@name='left_wrist_yaw_link']")
        ET.SubElement(wrist, 'site', name='left_palm', pos='.09 0 0', size='.004')
        self.model = mujoco.MjModel.from_xml_string(ET.tostring(xml, encoding='unicode'))
        profile = json.loads((ROOT/'assets/robot_profile.json').read_text())['profile']
        for row in profile['joints']:
            jid = self.model.joint(row[0]).id
            self.model.jnt_range[jid] = [max(self.model.jnt_range[jid, 0], row[3][0]),
                                       min(self.model.jnt_range[jid, 1], row[3][1])]
        self.ids = [self.model.joint(f'left_{s}_joint').id for s in SUFFIXES]
        self.qids = self.model.jnt_qposadr[self.ids]
        self.vids = self.model.jnt_dofadr[self.ids]
        self.site = self.model.site('left_palm').id

    def start(self, state):
        d = mujoco.MjData(self.model)
        d.qpos[:7] = [0., 0., 0., 1., 0., 0., 0.]
        for name, row in state['joints'].items():
            d.qpos[self.model.jnt_qposadr[self.model.joint(name).id]] = row['q']
        mujoco.mj_kinematics(self.model, d)
        return d

    def solve(self, data, position, yaw):
        m = self.model
        goal_rotation = yaw_rotation(yaw)
        goal_quat = np.empty(4)
        mujoco.mju_mat2Quat(goal_quat, goal_rotation.ravel())
        jp, jr = np.zeros((3, m.nv)), np.zeros((3, m.nv))
        best = None
        for iteration in range(160):
            mujoco.mj_kinematics(m, data)
            mujoco.mj_comPos(m, data)
            error = np.asarray(position)-data.site_xpos[self.site]
            actual = np.empty(4); angular = np.empty(3)
            mujoco.mju_mat2Quat(actual, data.site_xmat[self.site])
            mujoco.mju_subQuat(angular, goal_quat, actual)
            world_error = data.site_xmat[self.site].reshape(3, 3)@angular
            p, a = float(np.linalg.norm(error)), float(np.linalg.norm(world_error))
            score = p+.12*a
            if best is None or score < best[0]:
                best = score, data.qpos[self.qids].copy(), p, a
            if p < .004 and a < .12:
                break
            mujoco.mj_jacSite(m, data, jp, jr, self.site)
            jac = np.vstack((jp[:, self.vids], .12*jr[:, self.vids]))
            delta = jac.T@np.linalg.solve(jac@jac.T+np.eye(6)*.008**2, np.r_[error, .12*world_error])
            delta /= max(1., np.max(np.abs(delta))/.12)
            data.qpos[self.qids] = np.clip(data.qpos[self.qids]+delta,
                                           m.jnt_range[self.ids, 0], m.jnt_range[self.ids, 1])
        data.qpos[self.qids] = best[1]
        mujoco.mj_kinematics(m, data)
        return dict(position_error_m=best[2], orientation_error_rad=best[3],
                    reachable=best[2] <= .006 and best[3] <= .18)

    def path(self, state, cup_position, yaw, offset):
        data = self.start(state)
        palm = np.asarray(cup_position)-yaw_rotation(yaw)@np.asarray(offset)
        behind = palm-yaw_rotation(yaw)@[.13, 0., 0.]
        high = behind.copy(); high[2] = .30
        goals = [('orient_clear', np.array([-.04, .34, .30])), ('behind_high', high),
                 ('lower_behind', behind), ('approach_open', palm),
                 ('test_lift', palm+[0., 0., .02]), ('main_lift', palm+[0., 0., .125])]
        rows = []
        for stage, goal in goals:
            start = data.site_xpos[self.site].copy()
            count = 1 if stage == 'orient_clear' else max(1, int(np.ceil(np.linalg.norm(goal-start)/.025)))
            for step in range(1, count+1):
                previous = data.qpos[self.qids].copy()
                result = self.solve(data, start+(goal-start)*step/count, yaw)
                jump = float(np.max(np.abs(data.qpos[self.qids]-previous)))
                row = dict(stage=stage, step=step, max_joint_delta_rad=jump, **result)
                rows.append(row)
                if not result['reachable'] or (stage != 'orient_clear' and jump > .5):
                    return dict(yaw_rad=yaw, reachable=False, failed_at=row,
                                path=rows, collision_checked=False, source='robot_proprioception_and_RGBD_target')
        return dict(yaw_rad=yaw, reachable=True, path=rows, collision_checked=False,
                    source='robot_proprioception_and_RGBD_target',
                    max_position_error_m=max(r['position_error_m'] for r in rows))

    def select(self, state, cup_position, offset, preferred=.7):
        candidates = []
        # Preserve demonstrated grasp geometry; shortening reach lost thumb opposition.
        for yaw in dict.fromkeys([preferred, .6, .85, 1., .55]):
            candidate = self.path(state, cup_position, yaw, offset)
            candidate['cup_in_palm_m'] = list(offset)
            candidates.append(candidate)
            if candidate['reachable']:
                return dict(selected_yaw_rad=yaw, selected_offset_m=list(offset),
                            suggested_waist_pitch_rad=None, candidates=candidates,
                            policy='fixed yaw list with original grasp geometry')
        current_pitch = state['joints']['waist_pitch_joint']['q']
        if current_pitch < -.125:
            from copy import deepcopy
            trial_state = deepcopy(state)
            trial_state['joints']['waist_pitch_joint']['q'] = -.10
            candidate = self.path(trial_state, cup_position, preferred, offset)
            candidate.update(cup_in_palm_m=list(offset), hypothetical_waist_pitch_rad=-.10)
            candidates.append(candidate)
            if candidate['reachable']:
                return dict(selected_yaw_rad=None, selected_offset_m=None,
                            suggested_waist_pitch_rad=-.10, candidates=candidates,
                            policy='small torso pitch proposal; must reobserve and replan after physical execution')
        return dict(selected_yaw_rad=None, selected_offset_m=None, suggested_waist_pitch_rad=None, candidates=candidates,
                    policy='no reachable continuous path; do not execute')
