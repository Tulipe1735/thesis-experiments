"""Trusted v2 plant; isolated skills receive explicit observations, never this object.

No user program is evaluated here. Model/state objects stay inside the plant;
only the explicit observation projection crosses the action boundary.
"""
import hashlib
import json
import math
import os
import errno
import shutil
from pathlib import Path
import sys

os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
ENGINEERING = PROJECT / "grasp_optimization"
sys.path.insert(0, str(ENGINEERING))
from pantry_robot import PantryRobot  # Only its unchanged standing controller is used.

ARM = tuple(f"left_{part}_joint" for part in (
    "shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
    "wrist_roll", "wrist_pitch", "wrist_yaw"))
HAND = tuple(f"left_hand_{part}_joint" for part in (
    "thumb_0", "thumb_1", "thumb_2", "middle_0", "middle_1", "index_0", "index_1"))
ALLOWED = frozenset(ARM + HAND)


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_request(request, targets, limits, velocities):
    """Validate the complete request before any state or target can change."""
    if type(request) is not dict:
        raise ValueError("REQUEST_OBJECT_REQUIRED")
    op = request.get("op")
    if op == "state" and set(request) == {"op"}:
        return op, {}, 0.0
    if op not in ("wait", "set_joints"):
        raise ValueError("OPERATION_NOT_ALLOWED")
    expected = {"op", "duration"} | ({"targets"} if op == "set_joints" else set())
    if set(request) != expected:
        raise ValueError("UNEXPECTED_FIELDS")
    duration = request["duration"]
    if not finite_number(duration) or not .02 <= duration <= .20:
        raise ValueError("DURATION_LIMIT")
    # Align action boundaries to complete physical steps; do not silently round.
    if abs(duration / .002 - round(duration / .002)) > 1e-8:
        raise ValueError("DURATION_NOT_STEP_ALIGNED")
    values = request.get("targets", {})
    if type(values) is not dict or (op == "set_joints" and not 1 <= len(values) <= 14):
        raise ValueError("TARGET_OBJECT_REQUIRED")
    for name, value in values.items():
        if name not in ALLOWED:
            raise ValueError("JOINT_NOT_ALLOWED")
        if not finite_number(value):
            raise ValueError("NONFINITE_TARGET")
        lo, hi = limits[name]
        if not lo <= value <= hi:
            raise ValueError("JOINT_RANGE")
        is_hand = name in HAND
        delta = abs(value - targets[name])
        if delta > (.05 if is_hand else .03) + 1e-12:
            raise ValueError("TARGET_INCREMENT")
        speed = min(velocities[name], .50 if is_hand else .30)
        if 1.5 * delta / duration > speed + 1e-12:
            raise ValueError("TARGET_SPEED")
    return op, values, float(duration)


class TrackingMonitor:
    def __init__(self, count):
        self.elapsed = np.zeros(count)

    def check(self, errors, dt):
        self.elapsed = np.where(np.abs(errors) > .45, self.elapsed + dt, 0.0)
        return bool(np.any(self.elapsed >= .15 - 1e-10))


class Plant:
    def __init__(self, scene, instance, output, kind="engineering", budget=2.0):
        self.kind, self.budget = kind, budget
        self.renderer = None
        self.full_states = []
        self.safety_maxima = dict(tilt_deg=0.0, drift_m=0.0, tracking_error_rad=0.0)
        self.output = Path(output)
        self.output.mkdir(exist_ok=False)
        self.model = mujoco.MjModel.from_xml_path(str(scene))
        self.data = mujoco.MjData(self.model)
        m, d = self.model, self.data
        if abs(m.opt.timestep - .002) > 1e-12:
            raise ValueError("Unexpected simulation timestep")
        profile_path = ENGINEERING / "assets/robot_profile.json"
        self.profile = json.loads(profile_path.read_text())["profile"]
        self.joint_rows = {row[0]: row for row in self.profile["joints"]}
        self.joint_ids = m.actuator_trnid[:, 0].copy()
        self.qids = m.jnt_qposadr[self.joint_ids]
        self.vids = m.jnt_dofadr[self.joint_ids]
        self.names = [m.joint(j).name for j in self.joint_ids]
        self.ai = {name: i for i, name in enumerate(self.names)}
        self.kp = np.array([4 if "_hand_" in n else 350 if any(
            part in n for part in ("hip_", "knee", "ankle")) else
            180 if "waist" in n else 80 for n in self.names], float)
        self.kd = np.array([.12 if "_hand_" in n else 12 if any(
            part in n for part in ("hip_", "knee", "ankle", "waist"))
            else 4 for n in self.names], float)
        self.limits = np.array([self.joint_rows[n][4] for n in self.names])
        self.feedforward = np.zeros(m.nu)
        for i, (name, jid) in enumerate(zip(self.names, self.joint_ids)):
            row = self.joint_rows[name]
            m.jnt_range[jid] = [max(m.jnt_range[jid, 0], row[3][0]),
                                min(m.jnt_range[jid, 1], row[3][1])]
            m.jnt_actfrcrange[jid] = [-row[4], row[4]]
            m.actuator_ctrllimited[i] = False
            m.actuator_forcelimited[i] = True
            m.actuator_forcerange[i] = [-row[4], row[4]]
        m.actuator_gainprm[:, 0] = self.kp
        m.actuator_biastype[:] = int(mujoco.mjtBias.mjBIAS_AFFINE)
        m.actuator_biasprm[:, 1] = -self.kp
        m.actuator_biasprm[:, 2] = -self.kd
        for side in ("left", "right"):
            for suffix, angle in (("shoulder_pitch", .35),
                                  ("shoulder_roll", .45 if side == "left" else -.45),
                                  ("elbow", 1.0)):
                d.qpos[self.qids[self.ai[f"{side}_{suffix}_joint"]]] = angle
        for suffix, angle in (("pitch", -.15), ("yaw", .25)):
            d.qpos[self.qids[self.ai[f"waist_{suffix}_joint"]]] = angle
        d.qpos[self.qids[self.ai["left_shoulder_roll_joint"]]] += instance.get("shoulder_roll_offset_rad", 0.0)
        for name, offset in instance.get("joint_offsets_rad", {}).items():
            if name not in ALLOWED:
                raise ValueError("Initial state contains a nonleft joint")
            qid = self.qids[self.ai[name]]
            d.qpos[qid] = np.clip(d.qpos[qid] + offset, *m.jnt_range[self.joint_ids[self.ai[name]]])
        cup_qid = m.jnt_qposadr[m.joint("task_cup_free").id]
        d.qpos[cup_qid:cup_qid + 2] = instance["cup_table_xy_m"]
        # A constant orientation removes the legacy position-specific yaw factor.
        d.qpos[cup_qid + 3:cup_qid + 7] = [1.0, 0.0, 0.0, 0.0]
        self.pelvis_id = m.body("pelvis").id
        self.cup_id = m.body("task_cup").id
        self.left_contact_geoms = set()
        for geom in range(m.ngeom):
            body_name = m.body(int(m.geom_bodyid[geom])).name or ""
            mesh = int(m.geom_dataid[geom])
            mesh_name = m.mesh(mesh).name if mesh >= 0 and m.geom_type[geom] == mujoco.mjtGeom.mjGEOM_MESH else ""
            if body_name.startswith("left_hand_") or mesh_name == "left_hand_palm_link":
                self.left_contact_geoms.add(geom)
        self.robot_bodies = set()
        for body in range(m.nbody):
            ancestor = body
            while ancestor and ancestor != self.pelvis_id:
                ancestor = int(m.body_parentid[ancestor])
            if ancestor == self.pelvis_id:
                self.robot_bodies.add(body)
        feet = {m.body(side + "_ankle_roll_link").id for side in ("left", "right")}
        self.foot_geoms = [g for g in range(m.ngeom) if m.geom_bodyid[g] in feet
                           and m.geom_type[g] == int(mujoco.mjtGeom.mjGEOM_SPHERE)]
        mujoco.mj_forward(m, d)
        self.floor = 0.0
        self.floor_geoms = set()
        for g in range(m.ngeom):
            if not (m.geom(g).name or "").startswith("room_contact_"):
                continue
            top = d.geom_xpos[g, 2] + m.geom_size[g, 2]
            if -.1 < top < .15 and np.all(np.abs(
                    d.qpos[:2] - d.geom_xpos[g, :2]) < m.geom_size[g, :2]):
                self.floor = max(self.floor, float(top))
                self.floor_geoms.add(g)
        bottom = min(d.geom_xpos[g, 2] - m.geom_size[g, 0] for g in self.foot_geoms)
        d.qpos[2] += self.floor - bottom - .0001
        mujoco.mj_forward(m, d)
        self.targets = d.qpos[self.qids].copy()
        self.base_reference = d.qpos[:7].copy()
        self.fixed_indices = [i for i, n in enumerate(self.names) if n not in ALLOWED]
        self.fixed_targets = self.targets[self.fixed_indices].copy()
        self._mass = np.zeros((m.nv, m.nv))
        self._jac = np.zeros((3, m.nv))
        self._jac_contacts = np.zeros((len(self.foot_geoms) * 3, m.nv))
        self.tracking = TrackingMonitor(len(self.names))
        self.guard = None
        self.events = []
        self.trace = []
        self.initial_hash = hashlib.sha256(d.qpos.tobytes() + d.qvel.tobytes()
                                           + self.targets.tobytes()).hexdigest()
        self.initial_qpos = d.qpos.copy()
        self.initial_qvel = d.qvel.copy()
        self.cup_initial_z = float(d.xpos[self.cup_id, 2])
        self.table_height = float(d.qpos[cup_qid + 2] - .0005)
        # Instance changes are qpos only; reuse identical immutable binary assets.
        shared_model = ROOT / "assets/model.mjb"
        shared_model.parent.mkdir(exist_ok=True)
        if not shared_model.exists():
            mujoco.mj_saveModel(m, str(shared_model), None)
        try:
            os.link(shared_model, self.output / "model.mjb")
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            shutil.copyfile(shared_model, self.output / "model.mjb")
        self.monitor(advance_tracking=False)
        self.record()

    def rgbd(self):
        if self.renderer is None:
            self.renderer = mujoco.Renderer(self.model, height=180, width=320, max_geom=4000)
        options = mujoco.MjvOption()
        options.geomgroup[:] = [0, 1, 1, 0, 0, 0]
        self.renderer.disable_depth_rendering()
        self.renderer.update_scene(self.data, camera="g1_head", scene_option=options)
        rgb = self.renderer.render().copy()
        self.renderer.enable_depth_rendering()
        depth = self.renderer.render().copy()
        self.renderer.disable_depth_rendering()
        valid = np.isfinite(depth) & (depth >= .28) & (depth <= 3.0)
        depth = np.round(depth * 1000) / 1000
        values = depth.astype(object)
        values[~valid] = None
        camera = self.model.camera("g1_head").id
        base = self.data.xmat[self.pelvis_id].reshape(3, 3)
        transform = np.eye(4)
        transform[:3, :3] = base.T @ self.data.cam_xmat[camera].reshape(3, 3) @ np.diag([1., -1., -1.])
        transform[:3, 3] = base.T @ (self.data.cam_xpos[camera] - self.data.xpos[self.pelvis_id])
        focal = 180 / (2 * math.tan(math.radians(float(self.model.cam_fovy[camera]) / 2)))
        return dict(rgb=rgb.tolist(), depth_m=values.tolist(),
                    K=[[focal, 0, 160], [0, focal, 90], [0, 0, 1]],
                    T_optical_to_pelvis=transform.tolist(), timestamp_s=float(self.data.time))

    def observation(self):
        m, d = self.model, self.data
        rotation = d.xmat[self.pelvis_id].reshape(3, 3)
        site = m.site("left_palm").id
        local_rotation = rotation.T @ d.site_xmat[site].reshape(3, 3)
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, local_rotation.ravel())
        tactile = {n: 0.0 for n in HAND}
        for c_index in range(d.ncon):
            contact = d.contact[c_index]
            force = np.empty(6)
            mujoco.mj_contactForce(m, d, c_index, force)
            for geom in (contact.geom1, contact.geom2):
                name = m.body(int(m.geom_bodyid[geom])).name or ""
                joint = name.removesuffix("_link") + "_joint"
                if joint in tactile:
                    tactile[joint] += max(0.0, float(force[0]))
        return dict(simulation_seconds=float(d.time),
                    joints={name: dict(q=float(d.qpos[self.qids[i]]),
                                       dq=float(d.qvel[self.vids[i]]),
                                       target=float(self.targets[i]),
                                       torque_Nm=float(d.actuator_force[i]))
                            for i, name in enumerate(self.names)},
                    left_palm=dict(frame="current_pelvis", position_m=(rotation.T @ (
                        d.site_xpos[site] - d.xpos[self.pelvis_id])).tolist(),
                                   quaternion_xyzw=quat[[1, 2, 3, 0]].tolist()),
                    tactile_joint_load_N=tactile,
                    guard=self.guard)

    def monitor(self, advance_tracking=True):
        m, d = self.model, self.data
        faults = []
        forbidden_contacts = []
        if not all(np.isfinite(a).all() for a in (d.qpos, d.qvel, d.actuator_force)):
            faults.append("NONFINITE_STATE")
        rotation = d.xmat[self.pelvis_id].reshape(3, 3)
        tilt = float(np.degrees(np.arccos(np.clip(rotation[2, 2], -1, 1))))
        drift = float(np.linalg.norm(d.qpos[:2] - self.base_reference[:2]))
        if tilt > 12 or d.qpos[2] < self.floor + .62:
            faults.append("BASE_TILT_OR_HEIGHT")
        if drift > .12:
            faults.append("BASE_DRIFT")
        q = d.qpos[self.qids]
        ranges = m.jnt_range[self.joint_ids]
        if np.any(q < ranges[:, 0] - .02) or np.any(q > ranges[:, 1] + .02):
            faults.append("MEASURED_JOINT_RANGE")
        if np.any(np.abs(d.actuator_force) > self.limits + 1e-6):
            faults.append("TORQUE_LIMIT")
        speed_faults = []
        for name in ARM + HAND:
            speed = abs(float(d.qvel[self.vids[self.ai[name]]]))
            limit = .60 if name in ARM else 1.0
            if speed > limit:
                speed_faults.append(dict(joint=name, measured_rad_s=speed, limit_rad_s=limit))
        if speed_faults:
            faults.append("MEASURED_SPEED")
        if advance_tracking and self.tracking.check(q - self.targets, m.opt.timestep):
            faults.append("CUMULATIVE_TRACKING")
        if not np.array_equal(self.targets[self.fixed_indices], self.fixed_targets):
            faults.append("NONLEFT_TARGET_CHANGED")
        for index in range(d.ncon):
            contact = d.contact[index]
            geoms = (int(contact.geom1), int(contact.geom2))
            bodies = tuple(int(m.geom_bodyid[g]) for g in geoms)
            if not any(b in self.robot_bodies for b in bodies):
                continue
            support = ((geoms[0] in self.foot_geoms and geoms[1] in self.floor_geoms)
                       or (geoms[1] in self.foot_geoms and geoms[0] in self.floor_geoms))
            if support:
                continue
            force = np.empty(6)
            mujoco.mj_contactForce(m, d, index, force)
            hand_cup = self.kind == "grasp" and self.cup_id in bodies and any(
                g in self.left_contact_geoms for g in geoms)
            limit_force, limit_penetration = (20., .006) if hand_cup else (.1, .002)
            if force[0] > limit_force or contact.dist < -limit_penetration:
                forbidden_contacts.append(dict(
                    geoms=[m.geom(g).name or str(g) for g in geoms],
                    bodies=[m.body(b).name or "world" for b in bodies],
                    normal_load_N=float(force[0]), separation_m=float(contact.dist)))
        if forbidden_contacts:
            faults.append("FORBIDDEN_CONTACT")
        if d.time > self.budget + 1e-9:
            faults.append("SIMULATION_TIME_BUDGET")
        self.diagnostics = dict(time=float(d.time), tilt_deg=tilt, drift_m=drift,
                                faults=faults, forbidden_contacts=forbidden_contacts,
                                speed_faults=speed_faults,
                                max_tracking_error_rad=float(np.max(np.abs(q - self.targets))))
        self.safety_maxima["tilt_deg"] = max(self.safety_maxima["tilt_deg"], tilt)
        self.safety_maxima["drift_m"] = max(self.safety_maxima["drift_m"], drift)
        self.safety_maxima["tracking_error_rad"] = max(self.safety_maxima["tracking_error_rad"], self.diagnostics["max_tracking_error_rad"])
        if faults and self.guard is None:
            self.guard = faults[0]
            self.first_failure = self.diagnostics.copy()

    def record(self):
        self.trace.append((float(self.data.time), self.data.qpos.copy(),
                           self.data.qvel.copy(), self.targets.copy(),
                           self.data.actuator_force.copy()))
        if (len(self.trace) - 1) % 25 == 0:
            full = np.empty(mujoco.mj_stateSize(self.model, mujoco.mjtState.mjSTATE_INTEGRATION))
            mujoco.mj_getState(self.model, self.data, full, mujoco.mjtState.mjSTATE_INTEGRATION)
            self.full_states.append((float(self.data.time), full))

    def dispatch(self, request):
        starts = {n: float(self.targets[self.ai[n]]) for n in ALLOWED}
        ranges = {n: self.model.jnt_range[self.joint_ids[self.ai[n]]] for n in ALLOWED}
        velocities = {n: self.joint_rows[n][5] for n in ALLOWED}
        try:
            op, values, duration = validate_request(request, starts, ranges, velocities)
        except (ValueError, TypeError) as error:
            result = dict(status="REJECTED", reason=str(error), observation=self.observation())
            self.events.append(dict(request=request, result=result))
            return result
        if op == "state":
            return dict(status="OBSERVED", observation=self.observation())
        if self.guard:
            return dict(status="STOPPED", reason=self.guard, observation=self.observation())
        if self.data.time + duration > self.budget + 1e-9:
            return dict(status="BUDGET_EXHAUSTED", reason="SIMULATION_TIME_BUDGET", observation=self.observation())
        first = self.targets.copy()
        final = first.copy()
        for name, value in values.items():
            final[self.ai[name]] = value
        count = round(duration / self.model.opt.timestep)
        for step in range(1, count + 1):
            fraction = step / count
            alpha = fraction * fraction * (3 - 2 * fraction)
            self.targets[:] = first + (final - first) * alpha
            PantryRobot._controller(self)
            mujoco.mj_step(self.model, self.data)
            mujoco.mj_forward(self.model, self.data)
            self.monitor()
            self.record()
            if self.guard:
                break
        result = dict(status="STOPPED" if self.guard else "EXECUTED",
                      reason=self.guard, observation=self.observation())
        self.events.append(dict(request=request, result=result))
        return result

    def dispatch_json(self, text):
        if not isinstance(text, str) or len(text.encode()) > 8192:
            return dict(status="REJECTED", reason="REQUEST_SIZE")
        try:
            request = json.loads(text)
        except (ValueError, TypeError):
            return dict(status="REJECTED", reason="INVALID_JSON")
        return self.dispatch(request)

    def save(self, instance, extra=None):
        np.savez_compressed(self.output / "trajectory.npz",
                            time=[r[0] for r in self.trace], qpos=[r[1] for r in self.trace],
                            qvel=[r[2] for r in self.trace], targets=[r[3] for r in self.trace],
                            actuator_force=[r[4] for r in self.trace],
                            initial_qpos=self.initial_qpos, initial_qvel=self.initial_qvel)
        np.savez_compressed(self.output / "integration_states.npz",
                            time=[r[0] for r in self.full_states],
                            integration_state=[r[1] for r in self.full_states],
                            base_reference=self.base_reference, cup_initial_z=self.cup_initial_z,
                            table_height_m=self.table_height)
        result = dict(instance=instance, initial_state_sha256=self.initial_hash,
                      completed=self.guard is None, protection=self.guard,
                      startup_failure=bool(self.guard and self.data.time == 0),
                      simulation_seconds=float(self.data.time), physical_steps=len(self.trace) - 1,
                      first_failure=getattr(self, "first_failure", None),
                      last_diagnostics=self.diagnostics,
                      safety_maxima=self.safety_maxima, kind=self.kind,
                      interpretation="Candidate diagnostic; see independent verification", **(extra or {}))
        (self.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        (self.output / "actions.json").write_text(json.dumps(self.events, indent=2) + "\n")
        if self.renderer is not None:
            self.renderer.close()
        return result
