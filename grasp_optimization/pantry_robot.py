"""Physical G1 tools in the native pantry; observations never include cup ground truth."""
from datetime import datetime
import json
import math
from pathlib import Path
import time

import mujoco
import numpy as np
from PIL import Image

from experiment_log import ROOT
from pantry_scene import build_scene

ARM_SUFFIXES = ['shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow', 'wrist_roll', 'wrist_pitch', 'wrist_yaw']


class PantryRobot:
    def __init__(self, folder, seed=1000, budget=180., vla=None):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.vla=vla
        self.vla_tool_calls=0
        self.vla_applied_frames=0
        self.scene_path, self.context = build_scene(seed)
        print('LOADING_NATIVE_PANTRY', flush=True)
        self.model = mujoco.MjModel.from_xml_path(str(self.scene_path))
        self.data = mujoco.MjData(self.model)
        self.profile = json.loads((ROOT / 'assets/robot_profile.json').read_text(encoding='utf-8'))['profile']
        self.joint_rows = {row[0]: row for row in self.profile['joints']}
        self.joint_ids = self.model.actuator_trnid[:, 0].copy()
        self.qids = self.model.jnt_qposadr[self.joint_ids]
        self.vids = self.model.jnt_dofadr[self.joint_ids]
        self.names = [self.model.joint(i).name for i in self.joint_ids]
        self.ai = {name: index for index, name in enumerate(self.names)}
        self.kp = np.array([4 if '_hand_' in n else 350 if any(s in n for s in ('hip_', 'knee', 'ankle'))
                            else 180 if 'waist' in n else 80 for n in self.names], float)
        self.kd = np.array([.12 if '_hand_' in n else 12 if any(s in n for s in ('hip_', 'knee', 'ankle', 'waist'))
                            else 4 for n in self.names], float)
        self.limits = np.array([self.joint_rows[name][4] for name in self.names])
        self.feedforward = np.zeros(self.model.nu)
        for i, (name, jid) in enumerate(zip(self.names, self.joint_ids)):
            row = self.joint_rows[name]
            self.model.jnt_range[jid] = [max(self.model.jnt_range[jid, 0], row[3][0]),
                                       min(self.model.jnt_range[jid, 1], row[3][1])]
            self.model.jnt_actfrcrange[jid] = [-row[4], row[4]]
            self.model.actuator_ctrllimited[i] = False
            self.model.actuator_forcelimited[i] = True
            self.model.actuator_forcerange[i] = [-row[4], row[4]]
        self.model.actuator_gainprm[:, 0] = self.kp
        self.model.actuator_biastype[:] = int(mujoco.mjtBias.mjBIAS_AFFINE)
        self.model.actuator_biasprm[:, 1] = -self.kp
        self.model.actuator_biasprm[:, 2] = -self.kd
        for side in ('left', 'right'):
            for suffix, value in [('shoulder_pitch', .35), ('shoulder_roll', .45 if side == 'left' else -.45), ('elbow', 1.)]:
                self.data.qpos[self.qids[self.ai[f'{side}_{suffix}_joint']]] = value
        self.data.qpos[self.qids[self.ai['waist_pitch_joint']]] = -.15
        self.data.qpos[self.qids[self.ai['waist_yaw_joint']]] = .25
        mujoco.mj_forward(self.model, self.data)
        self.pelvis_id = self.model.body('pelvis').id
        feet = {self.model.body(side+'_ankle_roll_link').id for side in ('left', 'right')}
        self.foot_geoms = [i for i in range(self.model.ngeom) if self.model.geom_bodyid[i] in feet
                           and self.model.geom_type[i] == int(mujoco.mjtGeom.mjGEOM_SPHERE)]
        bottom = min(self.data.geom_xpos[g, 2]-self.model.geom_size[g, 0] for g in self.foot_geoms)
        self.data.qpos[2] += self.context['floor_at_robot_m']-bottom-.0001
        mujoco.mj_forward(self.model, self.data)
        self.targets = self.data.qpos[self.qids].copy()
        self.base_reference = self.data.qpos[:7].copy()
        self.cup_id = self.model.body('task_cup').id
        self.cup_initial_z = float(self.data.xpos[self.cup_id, 2])
        self.guard, self.declared_done, self.stop_reason = None, False, None
        self.budget, self.hold_time, self.max_hold_time = float(budget), 0., 0.
        self.max_lift, self.max_tilt, self.max_drift = 0., 0., 0.
        self.renderer = mujoco.Renderer(self.model, height=720, width=1280, max_geom=4000)
        self.render_options = mujoco.MjvOption()
        self.render_options.geomgroup[:] = [0, 1, 1, 0, 0, 0]
        self.observation_count = 0
        self.latest_observation = None
        self.latest_depth = None
        self.trace, self.events = [], []
        self.next_record = 0.
        self._mass = np.zeros((self.model.nv, self.model.nv))
        self._jac = np.zeros((3, self.model.nv))
        self._jac_contacts = np.zeros((len(self.foot_geoms)*3, self.model.nv))
        self._save_state('initial_state')
        mujoco.mj_saveModel(self.model, str(self.folder/'model.mjb'), None)
        (self.folder / 'runtime_context.json').write_text(json.dumps(self.context, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('NATIVE_PANTRY_READY', '43 motors; native room + head RGB-D; free base', flush=True)

    def _controller(self):
        m, d = self.model, self.data
        # Contact wrench allocation acts through joint torques only, never a force on the base.
        for i, geom in enumerate(self.foot_geoms):
            point = d.geom_xpos[geom].copy()
            point[2] -= m.geom_size[geom, 0]
            mujoco.mj_jac(m, d, self._jac, None, point, int(m.geom_bodyid[geom]))
            self._jac_contacts[3*i:3*i+3] = self._jac
        mujoco.mj_fullM(m, d, self._mass)
        rotation_error = np.empty(3)
        mujoco.mju_subQuat(rotation_error, self.base_reference[3:7], d.qpos[3:7])
        linear_acc = 55*(self.base_reference[:3]-d.qpos[:3])-14*d.qvel[:3]
        angular_acc = 90*rotation_error-18*d.qvel[3:6]
        accel = np.concatenate((np.clip(linear_acc, -3, 3), np.clip(angular_acc, -8, 8)))
        wrench = d.qfrc_bias[:6] + self._mass[:6, :6] @ accel
        a = self._jac_contacts[:, :6].T
        force = a.T @ np.linalg.solve(a@a.T + np.eye(6)*1e-5, wrench)
        force = force.reshape(-1, 3)
        force[:, 2] = np.maximum(force[:, 2], 0)
        force[:, :2] = np.clip(force[:, :2], -.8*force[:, 2:3], .8*force[:, 2:3])
        compensation = d.qfrc_bias[self.vids] - self._jac_contacts[:, self.vids].T @ force.ravel()
        d.ctrl[:] = self.targets + np.clip(compensation+self.feedforward, -self.limits, self.limits)/self.kp

    def _goal(self):
        d, m = self.data, self.model
        rotation = d.xmat[self.pelvis_id].reshape(3, 3)
        tilt = float(np.degrees(np.arccos(np.clip(rotation[2, 2], -1, 1))))
        drift = float(np.linalg.norm(d.qpos[:2]-self.base_reference[:2]))
        lift = float(d.xpos[self.cup_id, 2]-self.cup_initial_z)
        support_load, contact_normals, digit_loads = 0., {}, {}
        for i in range(d.ncon):
            c = d.contact[i]
            g1, g2 = int(c.geom1), int(c.geom2)
            b1, b2 = int(m.geom_bodyid[g1]), int(m.geom_bodyid[g2])
            if self.cup_id not in (b1, b2):
                continue
            force = np.empty(6)
            mujoco.mj_contactForce(m, d, i, force)
            if force[0] <= 0:
                continue
            other = b2 if b1 == self.cup_id else b1
            name = m.body(other).name or ''
            if '_hand_' in name:
                side, digit_link = name.split('_hand_', 1)
                digit = side + '_' + digit_link.split('_')[0]
                digit_loads[digit] = digit_loads.get(digit, 0.) + force[0]
                normal = c.frame[:3] * (1 if b1 == self.cup_id else -1)
                contact_normals[digit] = contact_normals.get(digit, np.zeros(3)) + force[0]*normal
            else:
                support_load += force[0]
        opposing_grip = False
        for side in ('left', 'right'):
            thumb = contact_normals.get(side+'_thumb')
            for digit in ('index', 'middle'):
                finger = contact_normals.get(side+'_'+digit)
                if (thumb is not None and finger is not None
                        and digit_loads[side+'_thumb'] >= .1 and digit_loads[side+'_'+digit] >= .1):
                    denominator = np.linalg.norm(thumb)*np.linalg.norm(finger)
                    opposing_grip |= denominator > 1e-10 and float(thumb@finger)/denominator < -.5
        held = opposing_grip and support_load < .1 and lift >= .10 and tilt <= 5 and drift <= .03
        self.hold_time = self.hold_time+m.opt.timestep if held else 0.
        self.max_hold_time = max(self.max_hold_time, self.hold_time)
        self.max_lift, self.max_tilt, self.max_drift = max(self.max_lift, lift), max(self.max_tilt, tilt), max(self.max_drift, drift)
        if tilt > 12 or d.qpos[2] < self.context['floor_at_robot_m']+.62:
            self.guard = 'BASE_TILT_OR_HEIGHT_PROTECTION'
        if drift > .12:
            self.guard = 'BASE_DRIFT_PROTECTION'
        if not np.isfinite(d.qpos).all() or not np.isfinite(d.qvel).all():
            self.guard = 'NONFINITE_PHYSICS_PROTECTION'
        if d.time >= self.budget:
            self.guard = 'SIMULATION_BUDGET_EXHAUSTED'

    def _step(self):
        self._controller()
        mujoco.mj_step(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        self._goal()
        if self.data.time >= self.next_record:
            self.trace.append((float(self.data.time), self.data.qpos.copy(), self.data.qvel.copy(),
                               self.targets.copy(), self.data.actuator_force.copy()))
            self.next_record += .05

    def advance(self, seconds, category='wait'):
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0 or seconds > 1800:
            raise ValueError('Invalid duration')
        start = float(self.data.time)
        end = min(start+seconds, self.budget)
        while self.data.time < end-1e-9 and not self.guard:
            self._step()
        self.events.append(dict(category=category, requested_seconds=float(seconds), advanced_seconds=float(self.data.time)-start,
                                simulation_seconds=float(self.data.time), guard=self.guard))
        return dict(simulation_seconds=float(self.data.time), guard=self.guard,
                    advanced_seconds=float(self.data.time)-start)

    def fk(self, side='left'):
        if side not in ('left', 'right'):
            raise ValueError('side must be left or right')
        site = self.model.site(side+'_palm').id
        rotation = self.data.xmat[self.pelvis_id].reshape(3, 3)
        position = rotation.T @ (self.data.site_xpos[site]-self.data.xpos[self.pelvis_id])
        local_rotation = rotation.T @ self.data.site_xmat[site].reshape(3, 3)
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, local_rotation.ravel())
        return dict(frame='current_pelvis', side=side, position_m=position.tolist(), quaternion_xyzw=quat[[1, 2, 3, 0]].tolist())

    def state(self):
        tactile = {'left': {}, 'right': {}}
        for i in range(self.data.ncon):
            contact = self.data.contact[i]
            force = np.empty(6)
            mujoco.mj_contactForce(self.model, self.data, i, force)
            for geom in (contact.geom1, contact.geom2):
                name = self.model.body(int(self.model.geom_bodyid[geom])).name or ''
                for side in tactile:
                    if name.startswith(side+'_hand_'):
                        tactile[side][name] = tactile[side].get(name, 0.) + max(float(force[0]), 0.)
        return dict(simulation_seconds=float(self.data.time),
                    joints={n:dict(q=float(self.data.qpos[q]), dq=float(self.data.qvel[v]),
                                   torque_Nm=float(self.data.actuator_force[i]), target=float(self.targets[i]))
                            for i, (n, q, v) in enumerate(zip(self.names, self.qids, self.vids))},
                    palms={side:self.fk(side) for side in ('left', 'right')},
                    approximate_contact_load_N=tactile,
                    imu=dict(pelvis_quaternion_xyzw=self.data.qpos[[4, 5, 6, 3]].tolist(),
                             angular_velocity=self.data.qvel[3:6].tolist()),
                    controller=dict(base_mode='free_floating_contact_wrench_joint_control',
                                    external_base_assistance=False, guard=self.guard,
                                    max_tilt_deg=self.max_tilt, max_drift_m=self.max_drift),
                    capabilities=dict(rgbd=True, joints=True, numerical_pose_ik=True,
                                      vla=bool(self.vla and self.vla.ready)))

    def observe(self):
        self.observation_count += 1
        prefix = f'obs_{self.observation_count:03}'
        self.renderer.disable_depth_rendering()
        self.renderer.update_scene(self.data, camera='g1_head', scene_option=self.render_options)
        rgb = self.renderer.render().copy()
        self.renderer.enable_depth_rendering()
        depth = self.renderer.render().copy()
        self.renderer.disable_depth_rendering()
        depth[(depth < .28) | (depth > 3.)] = np.nan
        depth = np.round(depth*1000)/1000
        Image.fromarray(rgb).save(self.folder / (prefix+'_head.jpg'), quality=90)
        np.save(self.folder / (prefix+'_depth_m.npy'), depth)
        self.renderer.update_scene(self.data, camera='task_observer', scene_option=self.render_options)
        Image.fromarray(self.renderer.render().copy()).save(self.folder / (prefix+'_room.jpg'), quality=88)
        cid = self.model.camera('g1_head').id
        base = self.data.xmat[self.pelvis_id].reshape(3, 3)
        optical_to_world = self.data.cam_xmat[cid].reshape(3, 3) @ np.diag([1., -1., -1.])
        optical_to_pelvis = np.eye(4)
        optical_to_pelvis[:3, :3] = base.T @ optical_to_world
        optical_to_pelvis[:3, 3] = base.T @ (self.data.cam_xpos[cid]-self.data.xpos[self.pelvis_id])
        f = 720/(2*math.tan(math.radians(float(self.model.cam_fovy[cid])/2)))
        obs = dict(observation_id=prefix, simulation_seconds=float(self.data.time),
                   head_rgb_path=str(self.folder / (prefix+'_head.jpg')),
                   depth_path=str(self.folder / (prefix+'_depth_m.npy')),
                   room_rgb_path=str(self.folder / (prefix+'_room.jpg')),
                   resolution_wh=[1280, 720], K=[[f, 0, 640], [0, f, 360], [0, 0, 1]],
                   head_camera=self.context['head_camera'],spectator_camera='task_observer',
                   depth_definition='optical_z_metres_0.28_to_3m_quantized_1mm_NaN_invalid',
                   T_optical_to_pelvis=optical_to_pelvis.tolist(), body_state=self.state())
        (self.folder / (prefix+'.json')).write_text(json.dumps(obs, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        self.latest_observation, self.latest_depth = obs, depth
        return obs

    def pixel_to_pelvis(self, u, v, radius=2, observation_id=None):
        if self.latest_observation is None:
            raise ValueError('Call observe first')
        if observation_id and observation_id != self.latest_observation['observation_id']:
            raise ValueError('The requested observation is not the cached depth frame')
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (u, v)):
            raise ValueError('Pixel coordinates must be finite')
        u, v, radius = int(u), int(v), int(radius)
        if not (0 <= u < 1280 and 0 <= v < 720 and 0 <= radius <= 12):
            raise ValueError('Pixel or radius outside image')
        values = self.latest_depth[max(0,v-radius):v+radius+1, max(0,u-radius):u+radius+1]
        valid = values[np.isfinite(values)]
        if not len(valid):
            return dict(valid=False, reason='No valid measured depth at this pixel')
        z = float(np.median(valid))
        k = np.asarray(self.latest_observation['K'])
        optical = np.array([(u-k[0,2])*z/k[0,0], (v-k[1,2])*z/k[1,1], z, 1])
        point = np.asarray(self.latest_observation['T_optical_to_pelvis']) @ optical
        return dict(valid=True, surface_position_pelvis_m=point[:3].tolist(), optical_depth_m=z,
                    observation_id=self.latest_observation['observation_id'],
                    observation_simulation_seconds=self.latest_observation['simulation_seconds'],
                    note='Measured visible surface, not object center; coordinates at observation time')

    def set_joints(self, targets, duration=1.):
        if not isinstance(targets, dict) or not targets or len(targets)>29:
            raise ValueError('targets must be a nonempty joint-name dictionary')
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or not .02 <= duration <= 15:
            raise ValueError('duration must be 0.02 to 15 seconds')
        final, start = self.targets.copy(), self.targets.copy()
        for name, value in targets.items():
            if name not in self.ai or not any(x in name for x in ('shoulder', 'elbow', 'wrist', '_hand_', 'waist')):
                raise ValueError('Only arms, hands and waist are agent-commandable')
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Angles must be finite numbers')
            ai = self.ai[name]
            low, high = self.model.jnt_range[self.joint_ids[ai]]
            if not low <= value <= high:
                raise ValueError(f'{name} exceeds [{low:.4f}, {high:.4f}]')
            if abs(value-start[ai])/duration*1.5 > self.joint_rows[name][5]:
                raise ValueError(f'{name} interpolation exceeds the velocity limit')
            final[ai] = value
        t0 = float(self.data.time)
        while self.data.time-t0 < duration-1e-9 and not self.guard:
            fraction = min(1., (self.data.time-t0+self.model.opt.timestep)/duration)
            alpha = fraction*fraction*(3-2*fraction)
            self.targets = start+(final-start)*alpha
            self._step()
            if self.data.time-t0 > .15:
                commanded = [self.ai[name] for name in targets if '_hand_' not in name]
                if commanded and max(abs(self.data.qpos[self.qids[i]]-self.targets[i]) for i in commanded) > .45:
                    self.targets = self.data.qpos[self.qids].copy()
                    return dict(status='TRACKING_PROTECTION', simulation_seconds=float(self.data.time), state=self.state())
        self.events.append(dict(category='action', simulation_seconds=float(self.data.time),
                                advanced_seconds=float(self.data.time)-t0, joints=targets, guard=self.guard))
        return dict(status=self.guard or 'EXECUTED', simulation_seconds=float(self.data.time), palms=self.state()['palms'])

    def move_ee(self, side, position, quaternion_xyzw=None, duration=1.):
        if side not in ('left', 'right'):
            raise ValueError('side must be left or right')
        target_local = np.asarray(position, float)
        if target_local.shape != (3,) or not np.isfinite(target_local).all():
            raise ValueError('Position must contain three finite metres')
        m = self.model
        trial = mujoco.MjData(m)
        trial.qpos[:] = self.data.qpos
        mujoco.mj_forward(m, trial)
        rotation = self.data.xmat[self.pelvis_id].reshape(3, 3)
        target = self.data.xpos[self.pelvis_id]+rotation@target_local
        site = m.site(side+'_palm').id
        current_quat = np.empty(4)
        mujoco.mju_mat2Quat(current_quat, trial.site_xmat[site])
        if quaternion_xyzw is not None:
            q = np.asarray(quaternion_xyzw, float)
            if q.shape != (4,) or not np.isfinite(q).all() or np.linalg.norm(q)<1e-6:
                raise ValueError('Quaternion must be four finite xyzw components')
            q = q/np.linalg.norm(q)
            local_rotation = np.empty(9)
            mujoco.mju_quat2Mat(local_rotation, q[[3,0,1,2]])
            mujoco.mju_mat2Quat(current_quat, (rotation@local_rotation.reshape(3,3)).ravel())
        ids = [m.joint(f'{side}_{suffix}_joint').id for suffix in ARM_SUFFIXES]
        qids, vids = m.jnt_qposadr[ids], m.jnt_dofadr[ids]
        jp, jr = np.zeros((3, m.nv)), np.zeros((3,m.nv))
        orientation_error = np.empty(3)
        best = None
        for iteration in range(160):
            mujoco.mj_forward(m, trial)
            error = target-trial.site_xpos[site]
            actual_quat = np.empty(4)
            mujoco.mju_mat2Quat(actual_quat, trial.site_xmat[site])
            mujoco.mju_subQuat(orientation_error, current_quat, actual_quat)
            # Quaternion difference is expressed in the current site frame; Jacobian is world-aligned.
            orientation_world = trial.site_xmat[site].reshape(3,3) @ orientation_error
            residual = float(np.linalg.norm(error)+.12*np.linalg.norm(orientation_world))
            if best is None or residual < best[0]:
                best = (residual, trial.qpos[qids].copy(), float(np.linalg.norm(error)), float(np.linalg.norm(orientation_world)))
            if np.linalg.norm(error)<.004 and np.linalg.norm(orientation_world)<.12:
                break
            mujoco.mj_jacSite(m, trial, jp, jr, site)
            jac = np.vstack((jp[:,vids], .12*jr[:,vids]))
            rhs = np.concatenate((error, .12*orientation_world))
            delta = jac.T@np.linalg.solve(jac@jac.T+np.eye(6)*.008**2, rhs)
            delta /= max(1., np.max(np.abs(delta))/.12)
            trial.qpos[qids] = np.clip(trial.qpos[qids]+delta, m.jnt_range[ids,0], m.jnt_range[ids,1])
        if best[2]>.006 or best[3]>.18:
            return dict(status='POSE_IK_REJECTED', position_error_m=best[2], orientation_error_rad=best[3], executed=False)
        output = self.set_joints({m.joint(jid).name:float(value) for jid,value in zip(ids,best[1])}, duration)
        actual_position=np.asarray(self.fk(side)['position_m'])
        actual_error=float(np.linalg.norm(actual_position-target_local))
        if output['status']=='EXECUTED' and actual_error>.015:
            output['status']='ENDPOINT_TRACKING_ERROR'
        return dict(**output, ik_position_error_m=best[2], ik_orientation_error_rad=best[3],
                    actual_position_error_m=actual_error, requested_position_pelvis_m=target_local.tolist())

    def hand_config(self, side, kp=None, kd=None, torque_limit=None):
        if side not in ('left', 'right'):
            raise ValueError('side must be left or right')
        indices = [self.ai[f'{side}_hand_{name}_joint'] for name in self.profile['finger_order']]
        for values, destination, low, high in ((kp,self.kp,.5,8.), (kd,self.kd,.03,.5), (torque_limit,self.limits,0.,None)):
            if values is None:
                continue
            array = np.broadcast_to(np.asarray(values,float), (7,)).copy()
            ceiling = np.array([self.joint_rows[self.names[i]][4] for i in indices]) if high is None else high
            if not np.isfinite(array).all() or np.any(array<low) or np.any(array>ceiling):
                raise ValueError('Hand impedance values outside documented limits')
            destination[indices] = array
        self.model.actuator_gainprm[indices,0] = self.kp[indices]
        self.model.actuator_biasprm[indices,1] = -self.kp[indices]
        self.model.actuator_biasprm[indices,2] = -self.kd[indices]
        self.model.actuator_forcerange[indices] = np.column_stack((-self.limits[indices],self.limits[indices]))
        return dict(status='HAND_CONFIGURED', side=side)

    def wait(self, seconds):
        if not .02 <= seconds <= 15:
            raise ValueError('wait duration must be 0.02 to 15 seconds')
        return self.advance(seconds)

    def done(self):
        self.declared_done = True
        return dict(status='AGENT_DECLARED_DONE', independently_verified=False)

    def stop(self, reason):
        if not isinstance(reason,str) or not reason.strip() or len(reason)>800:
            raise ValueError('Give a short reason for stopping')
        self.stop_reason=reason.strip()
        return dict(status='AGENT_STOPPED_WITHOUT_COMPLETION',reason=self.stop_reason)

    def run_vla(self, subgoal, max_seconds=.5):
        from smolvla_runtime import run_vla_motion
        return run_vla_motion(self,subgoal,max_seconds)

    def _save_state(self, name):
        specification = mujoco.mjtState.mjSTATE_INTEGRATION
        array = np.empty(mujoco.mj_stateSize(self.model, specification))
        mujoco.mj_getState(self.model,self.data,array,specification)
        np.savez_compressed(self.folder/(name+'.npz'), mujoco_integration_state=array,
                            targets=self.targets, base_reference=self.base_reference, kp=self.kp, kd=self.kd, torque_limits=self.limits)

    def finish(self):
        self._save_state('final_state')
        if self.trace:
            np.savez_compressed(self.folder/'trajectory.npz', time=[row[0] for row in self.trace],
                                qpos=[row[1] for row in self.trace], qvel=[row[2] for row in self.trace],
                                joint_targets=[row[3] for row in self.trace], actuator_force=[row[4] for row in self.trace])
        result = dict(independent_success=self.max_hold_time>=1., agent_declared_done=self.declared_done,
                      simulation_seconds=float(self.data.time), max_lift_m=self.max_lift,
                      longest_held_lifted_seconds=self.max_hold_time, max_pelvis_tilt_deg=self.max_tilt,
                      max_pelvis_drift_m=self.max_drift, protection=self.guard,
                      agent_stop_reason=self.stop_reason,
                      vla_connected=bool(self.vla and self.vla.ready),
                      vla_tool_calls=self.vla_tool_calls,vla_applied_action_frames=self.vla_applied_frames,
                      vla_inference_calls=self.vla.calls if self.vla else 0,
                      controller='free base, normal/friction wrench allocation, implicit joint PD; no external base force',
                      scene_source=self.context['native_source'], native_geometry_objects=self.context['native_geometry_objects'],
                      task_snapshot_accepted=False, runtime_version=self.context['runtime_version'])
        result['grasp_criterion'] = 'same-hand thumb and another digit, opposing normals, no non-hand support'
        (self.folder/'environment_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (self.folder/'physics_events.json').write_text(json.dumps(self.events,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.renderer.close()
        return result
