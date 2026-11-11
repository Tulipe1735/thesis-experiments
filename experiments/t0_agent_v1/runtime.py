"""Reuse the frozen physical model in place; expose sensors through RobotPort."""
import math
import os
import sys

os.environ.setdefault('MUJOCO_GL', 'egl')
from .common import REFERENCE, ROOT, read, relative, sha, write_new

sys.path.insert(0, str(ROOT / 'grasp_optimization'))
import mujoco
import numpy as np
from pantry_robot import PantryRobot
from vision_grasp import RobotPort


class PilotRobot(PantryRobot):
    """Only initialization/persistence differ; standing, commands and guards are reused."""
    def __init__(self, folder, instance, budget=180., scene_path=None):
        self.folder = folder
        self.vla = None
        self.vla_tool_calls = self.vla_applied_frames = 0
        self.scene_path = scene_path or REFERENCE / 'model.mjb'
        self.model = mujoco.MjModel.from_binary_path(str(self.scene_path))
        self.data = mujoco.MjData(self.model)
        self.context = read(REFERENCE / 'runtime_context.json')
        self.context['candidate'] = instance
        self.profile = read(ROOT / 'grasp_optimization/assets/robot_profile.json')['profile']
        self.joint_rows = {row[0]: row for row in self.profile['joints']}
        self.joint_ids = self.model.actuator_trnid[:, 0].copy()
        self.qids = self.model.jnt_qposadr[self.joint_ids]
        self.vids = self.model.jnt_dofadr[self.joint_ids]
        self.names = [self.model.joint(i).name for i in self.joint_ids]
        self.ai = {name: index for index, name in enumerate(self.names)}
        with np.load(REFERENCE / 'initial_state.npz', allow_pickle=False) as initial:
            if scene_path is None:
                mujoco.mj_setState(self.model, self.data, initial['mujoco_integration_state'],
                                   mujoco.mjtState.mjSTATE_INTEGRATION)
            else:
                # A changed object count changes state dimensions. Transfer named joints,
                # never reinterpret the old integration-state vector in the new model.
                reference_model = mujoco.MjModel.from_binary_path(str(REFERENCE / 'model.mjb'))
                reference_data = mujoco.MjData(reference_model)
                mujoco.mj_setState(reference_model, reference_data, initial['mujoco_integration_state'],
                                   mujoco.mjtState.mjSTATE_INTEGRATION)
                for joint in range(reference_model.njnt):
                    name = reference_model.joint(joint).name
                    target_joint = self.model.joint(name).id
                    kind = int(reference_model.jnt_type[joint])
                    nq, nv = (7, 6) if kind == 0 else (4, 3) if kind == 1 else (1, 1)
                    q, v = reference_model.jnt_qposadr[joint], reference_model.jnt_dofadr[joint]
                    tq, tv = self.model.jnt_qposadr[target_joint], self.model.jnt_dofadr[target_joint]
                    self.data.qpos[tq:tq+nq] = reference_data.qpos[q:q+nq]
                    self.data.qvel[tv:tv+nv] = reference_data.qvel[v:v+nv]
                self.data.ctrl[:] = reference_data.ctrl
            self.targets = initial['targets'].copy()
            self.base_reference = initial['base_reference'].copy()
            self.kp, self.kd = initial['kp'].copy(), initial['kd'].copy()
            self.limits = initial['torque_limits'].copy()
        self.feedforward = np.zeros(self.model.nu)
        cup_q = self.model.jnt_qposadr[self.model.joint('task_cup_free').id]
        self.data.qpos[cup_q:cup_q + 2] = instance['cup_table_xy_m']
        self.data.qpos[cup_q + 3:cup_q + 7] = instance['cup_quaternion_wxyz']
        for item in instance.get('cups', []):
            q = self.model.jnt_qposadr[self.model.joint(item['body'] + '_free').id]
            self.data.qpos[q:q+2] = item['cup_table_xy_m']
            self.data.qpos[q+3:q+7] = item['cup_quaternion_wxyz']
        if instance.get('tray'):
            tray = instance['tray']
            q = self.model.jnt_qposadr[self.model.joint(tray['body'] + '_free').id]
            self.data.qpos[q:q+2] = tray['xy_m']
            self.data.qpos[q+3:q+7] = tray['quaternion_wxyz']
        self.data.time = 0.
        mujoco.mj_forward(self.model, self.data)
        self.pelvis_id = self.model.body('pelvis').id
        self.cup_id = self.model.body('task_cup').id
        feet = {self.model.body(side + '_ankle_roll_link').id for side in ('left', 'right')}
        self.foot_geoms = [g for g in range(self.model.ngeom) if self.model.geom_bodyid[g] in feet
                           and self.model.geom_type[g] == int(mujoco.mjtGeom.mjGEOM_SPHERE)]
        self.cup_initial_z = float(self.data.xpos[self.cup_id, 2])
        self.guard, self.declared_done, self.stop_reason = None, False, None
        self.budget, self.hold_time, self.max_hold_time = float(budget), 0., 0.
        self.max_lift = self.max_tilt = self.max_drift = 0.
        self.renderer = mujoco.Renderer(self.model, height=720, width=1280, max_geom=4000)
        self.render_options = mujoco.MjvOption()
        self.render_options.geomgroup[:] = [0, 1, 1, 0, 0, 0]
        self.observation_count = 0
        self.latest_observation = self.latest_depth = None
        self.trace, self.events = [], []
        self.next_record = 0.
        self._mass = np.zeros((self.model.nv, self.model.nv))
        self._jac = np.zeros((3, self.model.nv))
        self._jac_contacts = np.zeros((len(self.foot_geoms) * 3, self.model.nv))
        self._save_state('initial_state')
        base_rotation = self.data.xmat[self.pelvis_id].reshape(3, 3)
        if instance.get('target_region') != 'tray_support':
            target = self.data.xpos[self.cup_id] + base_rotation @ instance['target_offset_initial_pelvis_m']
            target[2] = self.context['table_height_m']
            write_new(folder / 'evaluator_target.json', dict(target_position_sim_m=target.tolist(),
                      policy_access=False, resolution='initial cup truth plus public relative task displacement'))
        if instance.get('cups') and instance.get('target_region') != 'tray_support':
            targets = {}
            for item in instance['cups']:
                point = self.data.xpos[self.model.body(item['body']).id] + base_rotation @ instance['target_offset_initial_pelvis_m']
                point[2] = self.context['table_height_m']
                targets[item['body']] = point.tolist()
            write_new(folder / 'evaluator_targets.json', dict(targets=targets, policy_access=False,
                      assignment='each distinct physical cup to its own displaced target'))
        write_new(folder / 'runtime_context.json', self.context)
        write_new(folder / 'model_reference.json', dict(path=relative(self.scene_path), sha256=sha(self.scene_path),
                  copied=False, initial_state_sha256=sha(folder / 'initial_state.npz')))
        write_new(folder / 'initial_pose.json', dict(qpos=self.data.qpos.tolist(), qvel=self.data.qvel.tolist(),
                  joint_targets=dict(zip(self.names, self.targets.tolist())), seed=instance['seed'],
                  policy_access=False, cup_position_sim_m=self.data.xpos[self.cup_id].tolist()))

    def finish(self):
        self._save_state('final_state')
        if not self.trace or self.trace[-1][0] != float(self.data.time):
            self.trace.append((float(self.data.time), self.data.qpos.copy(), self.data.qvel.copy(),
                               self.targets.copy(), self.data.actuator_force.copy()))
        np.savez_compressed(self.folder / 'trajectory.npz', time=[x[0] for x in self.trace],
                            qpos=[x[1] for x in self.trace], qvel=[x[2] for x in self.trace],
                            joint_targets=[x[3] for x in self.trace], actuator_force=[x[4] for x in self.trace])
        result = dict(simulation_seconds=float(self.data.time), protection=self.guard,
                      stop_reason=self.stop_reason, evaluator_required=True,
                      max_pelvis_tilt_deg=self.max_tilt, max_pelvis_drift_m=self.max_drift,
                      vla_inference_calls=0, vla_action_frames=0)
        write_new(self.folder / 'environment_result.json', result)
        write_new(self.folder / 'physics_events.json', self.events)
        self.renderer.close()
        return result


class CountedPort(RobotPort):
    def __init__(self, robot):
        super().__init__(robot)
        self.command_calls = 0

    def invoke(self, tool, arguments):
        self.command_calls += 1
        return super().invoke(tool, arguments)
