"""Independent physical tray membership/support; no controller stage is a verdict."""
import math
from pathlib import Path
import mujoco
import numpy as np

from .common import ROOT, read, sha, write_new
from .verify import cup_contacts


def tray_predicate(row):
    return bool(row['footprint_margin_m'] >= .001 and row['tray_floor_support_N'] >= .5
                and row['hand_contact_N'] < .1 and row['other_object_contact_N'] < .1
                and abs(row['support_height_error_m']) <= .004 and row['cup_tilt_deg'] <= 10.
                and row['linear_speed_m_s'] <= .02 and row['angular_speed_rad_s'] <= .2
                and row['pelvis_tilt_deg'] <= 5. and row['pelvis_drift_m'] <= .03)


def summarize(rows, names, error=None, protection=None, initial_valid=True):
    if not names or len(names) != len(set(names)):
        raise ValueError('Distinct target object identities required')
    starts = dict.fromkeys(names)
    durations = dict.fromkeys(names, 0.)
    together_start, together = None, 0.
    for row in rows:
        if set(row['cups']) != set(names):
            raise ValueError('Incomplete physical target coverage')
        for name, item in row['cups'].items():
            if tray_predicate(item):
                starts[name] = row['time'] if starts[name] is None else starts[name]
                durations[name] = row['time']-starts[name]
            else:
                starts[name], durations[name] = None, 0.
        valid = (all(tray_predicate(item) for item in row['cups'].values())
                 and row['tray_linear_speed_m_s'] <= .02 and row['tray_angular_speed_rad_s'] <= .2
                 and row['tray_tilt_deg'] <= 5. and row['tray_hand_contact_N'] < .1)
        if valid:
            together_start = row['time'] if together_start is None else together_start
            together = row['time']-together_start
        else:
            together_start, together = None, 0.
    return dict(verified_success=bool(together >= 1. and not error and not protection and initial_valid),
                target_count=len(names), terminal_simultaneous_stable_s=together,
                per_cup_terminal_stable_s=durations, final=rows[-1] if rows else None,
                execution_error=error, protection=protection, initial_valid=initial_valid,
                independent_of_controller_result=True, boundary='simulation', formal_skill_promotion=False)


def verify(folder, execution_error=None, output=None):
    folder = Path(folder)
    output = Path(output) if output is not None else folder
    ref, instance = read(folder/'model_reference.json'), read(folder/'instance.json')
    path = ROOT/ref['path']
    if sha(path) != ref['sha256']:
        raise ValueError('Physical model changed')
    model = mujoco.MjModel.from_binary_path(str(path))
    data = mujoco.MjData(model)
    with np.load(folder/'initial_state.npz', allow_pickle=False) as initial:
        mujoco.mj_setState(model, data, initial['mujoco_integration_state'], mujoco.mjtState.mjSTATE_INTEGRATION)
        base, kp, kd = initial['base_reference'].copy(), initial['kp'].copy(), initial['kd'].copy()
    mujoco.mj_forward(model, data)
    names = [item['body'] for item in instance['cups']]
    if len(names) != instance['assets']['count'] or len(set(names)) != len(names):
        raise ValueError('Target count does not match distinct physical objects')
    tray = model.body('task_tray').id
    floor = model.geom('tray_floor').id
    tray_dof = model.jnt_dofadr[model.joint('task_tray_free').id]
    pelvis = model.body('pelvis').id
    inner = np.asarray(instance['tray']['half_size_xy_m'])-instance['tray']['rim_thickness_m']
    initial_positions = {name: data.xpos[model.body(name).id].copy() for name in names}
    table_z = read(folder/'runtime_context.json')['table_height_m']
    # Legal initial placements: on table, not initially in tray, distinct and no
    # penetrating target contacts. This is checked before any outcome is known.
    initial_checks = {}
    for name, position in initial_positions.items():
        local = data.xmat[tray].reshape(3,3).T @ (position-data.xpos[tray])
        initial_checks[name] = dict(on_table_height=bool(abs(position[2]-table_z) <= .002),
                                   starts_outside_tray=bool(np.any(np.abs(local[:2]) > inner)),
                                   position_sim_m=position.tolist())
    penetrations = []
    for i in range(data.ncon):
        contact = data.contact[i]
        bodies = [model.body(int(model.geom_bodyid[g])).name for g in (contact.geom1, contact.geom2)]
        if any(name in bodies for name in names+['task_tray']) and contact.dist < -.001:
            penetrations.append(dict(bodies=bodies, penetration_m=-float(contact.dist)))
    initial_valid = all(row['on_table_height'] and row['starts_outside_tray'] for row in initial_checks.values()) and not penetrations
    qids = model.jnt_qposadr[model.actuator_trnid[:,0]]
    vids = model.jnt_dofadr[model.actuator_trnid[:,0]]
    cups = {}
    for name in names:
        body = model.body(name).id
        geoms = np.flatnonzero((model.geom_bodyid == body) & (model.geom_type == mujoco.mjtGeom.mjGEOM_CYLINDER)
                              & (model.geom_contype != 0))
        if len(geoms) != 1:
            raise ValueError('Expected one physical cup base cylinder')
        cups[name] = (body, int(geoms[0]), model.jnt_dofadr[model.joint(name+'_free').id])
    rows = []
    with np.load(folder/'trajectory.npz', allow_pickle=False) as trace:
        for i, time in enumerate(trace['time']):
            data.qpos[:], data.qvel[:], data.time = trace['qpos'][i], trace['qvel'][i], time
            data.ctrl[:] = data.qpos[qids]+(trace['actuator_force'][i]+kd*data.qvel[vids])/kp
            mujoco.mj_forward(model, data)
            rotation = data.xmat[tray].reshape(3,3)
            tilt = float(np.degrees(np.arccos(np.clip(data.xmat[pelvis,8], -1, 1))))
            drift = float(np.linalg.norm(data.qpos[:2]-base[:2]))
            row = dict(time=float(time), cups={}, tray_linear_speed_m_s=float(np.linalg.norm(data.qvel[tray_dof:tray_dof+3])),
                       tray_angular_speed_rad_s=float(np.linalg.norm(data.qvel[tray_dof+3:tray_dof+6])),
                       tray_tilt_deg=float(np.degrees(np.arccos(np.clip(data.xmat[tray,8], -1, 1)))), tray_hand_contact_N=0.)
            for contact in cup_contacts(model, data, 'task_tray'):
                if any('_hand_' in body for body in contact['bodies']):
                    row['tray_hand_contact_N'] += contact['normal_force_N']
            for name, (body, bottom, dof) in cups.items():
                center = rotation.T @ (data.geom_xpos[bottom]-data.xpos[tray])
                bottom_rotation = rotation.T @ data.geom_xmat[bottom].reshape(3,3)
                radius, halfheight = model.geom_size[bottom,:2]
                extent = radius*np.linalg.norm(bottom_rotation[:2,:2], axis=1)+halfheight*np.abs(bottom_rotation[:2,2])
                margin = float(np.min(inner-np.abs(center[:2])-extent))
                root_local = rotation.T @ (data.xpos[body]-data.xpos[tray])
                floor_load = hand_load = other_load = 0.
                for contact in cup_contacts(model, data, name):
                    other = 1 if contact['bodies'][0] == name else 0
                    if contact['geom_ids'][other] == floor:
                        floor_load += contact['normal_force_N']
                    elif '_hand_' in contact['bodies'][other]:
                        hand_load += contact['normal_force_N']
                    else:
                        other_load += contact['normal_force_N']
                row['cups'][name] = dict(footprint_margin_m=margin, tray_floor_support_N=floor_load,
                    hand_contact_N=hand_load, other_object_contact_N=other_load,
                    support_height_error_m=float(root_local[2]-instance['tray']['floor_thickness_m']),
                    cup_tilt_deg=float(np.degrees(np.arccos(np.clip(data.xmat[body,8], -1, 1)))),
                    linear_speed_m_s=float(np.linalg.norm(data.qvel[dof:dof+3])),
                    angular_speed_rad_s=float(np.linalg.norm(data.qvel[dof+3:dof+6])),
                    pelvis_tilt_deg=tilt, pelvis_drift_m=drift,
                    cup_position_tray_m=root_local.tolist(), lift_m=float(data.xpos[body,2]-initial_positions[name][2]))
            rows.append(row)
    env = read(folder/'environment_result.json')
    result = summarize(rows, names, execution_error, env['protection'], initial_valid)
    result.update(task=instance['task'], initial_checks=initial_checks, initial_penetrations=penetrations,
                  sample_interval_s=.05, no_external_forces=not bool(np.any(data.qfrc_applied) or np.any(data.xfrc_applied)),
                  equality_constraints=int(model.neq), trajectory_sha256=sha(folder/'trajectory.npz'),
                  max_lift_m={name:max(row['cups'][name]['lift_m'] for row in rows) for name in names})
    if not result['no_external_forces'] or model.neq:
        result['verified_success'] = False
    write_new(output/'independent_verification.json', result)
    write_new(output/'verified_samples.json', rows)
    return result
