"""Independent replay of saved physics; no controller phase is a success signal."""
import argparse
import math
import sys
from pathlib import Path
import numpy as np
import mujoco

from .common import ROOT, read, sha, write_new
sys.path.insert(0, str(ROOT / 'grasp_optimization'))


def cup_contacts(model, data, cup_name):
    """All contacts for the selected body, including cup 2 against the table."""
    for index in range(data.ncon):
        contact = data.contact[index]
        geoms = [int(contact.geom1), int(contact.geom2)]
        bodies = [model.body(int(model.geom_bodyid[g])).name or 'world' for g in geoms]
        if cup_name not in bodies:
            continue
        force = np.empty(6)
        mujoco.mj_contactForce(model, data, index, force)
        if force[0] >= .001:
            yield dict(bodies=bodies, geom_ids=geoms, normal_force_N=float(force[0]),
                       normal=contact.frame[:3].tolist())


def placement_predicate(row):
    return bool(row['target_error_m'] <= .020 and row['cup_tilt_deg'] <= 10.
                and abs(row['table_height_error_m']) <= .005
                and row['table_support_N'] >= .5 and row['hand_contact_N'] < .1
                and row['linear_speed_m_s'] <= .02 and row['angular_speed_rad_s'] <= .2
                and row['pelvis_tilt_deg'] <= 5. and row['pelvis_drift_m'] <= .03)


def summarize(rows, task, protection=None, error=None):
    hold_start = place_start = None
    longest_hold = final_place = 0.
    for row in rows:
        if row['held']:
            hold_start = row['time'] if hold_start is None else hold_start
            longest_hold = max(longest_hold, row['time'] - hold_start)
        else:
            hold_start = None
        if longest_hold >= 1. and placement_predicate(row):
            place_start = row['time'] if place_start is None else place_start
            final_place = row['time'] - place_start
        else:
            place_start = None
            final_place = 0.
    acquired = longest_hold >= 1.
    completed = acquired and (task == 'pick_cup' or final_place >= 1.)
    return dict(verified_success=bool(completed and not protection and not error),
                grasp_passed=acquired, placement_passed=final_place >= 1.,
                longest_strict_hold_s=longest_hold, terminal_stable_placement_s=final_place,
                protection=protection, execution_error=error, samples=len(rows),
                final=rows[-1] if rows else None)


def lowest_cup(model, data, geoms):
    lowest = math.inf
    for geom in geoms:
        rot = data.geom_xmat[geom].reshape(3, 3)
        size, kind = model.geom_size[geom], model.geom_type[geom]
        if kind == mujoco.mjtGeom.mjGEOM_BOX:
            half = float(np.abs(rot[2]) @ size)
        elif kind == mujoco.mjtGeom.mjGEOM_CYLINDER:
            half = float(abs(rot[2, 2]) * size[1] + np.linalg.norm(rot[2, :2]) * size[0])
        elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
            half = float(abs(rot[2, 2]) * size[1] + size[0])
        else:
            raise ValueError('Unexpected cup collision geometry')
        lowest = min(lowest, float(data.geom_xpos[geom, 2]) - half)
    return lowest


def verify_cup(folder, execution_error=None, cup_name='task_cup', target=None):
    folder = Path(folder)
    reference = read(folder / 'model_reference.json')
    path = ROOT / reference['path']
    if sha(path) != reference['sha256']:
        raise ValueError('Referenced physical model changed')
    model = mujoco.MjModel.from_binary_path(str(path))
    data = mujoco.MjData(model)
    with np.load(folder / 'initial_state.npz', allow_pickle=False) as initial:
        mujoco.mj_setState(model, data, initial['mujoco_integration_state'], mujoco.mjtState.mjSTATE_INTEGRATION)
        mujoco.mj_forward(model, data)
        base, kp, kd = initial['base_reference'].copy(), initial['kp'].copy(), initial['kd'].copy()
    cup, pelvis = model.body(cup_name).id, model.body('pelvis').id
    initial_z = float(data.xpos[cup, 2])
    cup_dof = model.jnt_dofadr[model.joint(cup_name + '_free').id]
    geoms = np.flatnonzero((model.geom_bodyid == cup) & (model.geom_contype != 0))
    joints = model.actuator_trnid[:, 0]
    qids, vids = model.jnt_qposadr[joints], model.jnt_dofadr[joints]
    context = read(folder / 'runtime_context.json')
    target = np.asarray(target if target is not None else read(folder / 'evaluator_target.json')['target_position_sim_m'])
    env = read(folder / 'environment_result.json')
    task = read(folder / 'instance.json')['task']
    rows = []
    with np.load(folder / 'trajectory.npz', allow_pickle=False) as trace:
        for i, time in enumerate(trace['time']):
            data.qpos[:], data.qvel[:], data.time = trace['qpos'][i], trace['qvel'][i], time
            data.ctrl[:] = data.qpos[qids] + (trace['actuator_force'][i] + kd * data.qvel[vids]) / kp
            mujoco.mj_forward(model, data)
            loads, normals, other_load, table_load = {}, {}, 0., 0.
            for contact in cup_contacts(model, data, cup_name):
                other_index = 1 if contact['bodies'][0] == cup_name else 0
                name = contact['bodies'][other_index]
                force = contact['normal_force_N']
                if '_hand_' in name:
                    side, rest = name.split('_hand_', 1)
                    key = side + '_' + rest.split('_')[0]
                    loads[key] = loads.get(key, 0.) + force
                    normal = np.asarray(contact['normal']) * (1 if other_index == 1 else -1)
                    normals[key] = normals.get(key, np.zeros(3)) + force * normal
                else:
                    other_load += force
                    gid = contact['geom_ids'][other_index]
                    top = float(data.geom_xpos[gid, 2] + model.geom_size[gid, 2])
                    if (name == 'world' and model.geom_type[gid] == mujoco.mjtGeom.mjGEOM_BOX
                            and abs(top - context['table_height_m']) < .01):
                        table_load += force
            opposed = False
            for side in ('left', 'right'):
                for digit in ('index', 'middle'):
                    thumb, finger = side + '_thumb', side + '_' + digit
                    if loads.get(thumb, 0.) >= .1 and loads.get(finger, 0.) >= .1:
                        denominator = np.linalg.norm(normals[thumb]) * np.linalg.norm(normals[finger])
                        opposed |= denominator > 1e-10 and float(normals[thumb] @ normals[finger] / denominator) < -.5
            tilt = float(np.degrees(np.arccos(np.clip(data.xmat[pelvis, 8], -1., 1.))))
            drift = float(np.linalg.norm(data.qpos[:2] - base[:2]))
            lift = float(data.xpos[cup, 2] - initial_z)
            clearance = lowest_cup(model, data, geoms) - context['table_height_m']
            row = dict(time=float(time), lift_m=lift, clearance_m=clearance,
                       held=bool(lift >= .10 and clearance >= .09 and opposed and other_load < .1
                                 and tilt <= 5. and drift <= .03),
                       target_error_m=float(np.linalg.norm(data.xpos[cup, :2] - target[:2])),
                       cup_tilt_deg=float(np.degrees(np.arccos(np.clip(data.xmat[cup, 8], -1., 1.)))),
                       table_height_error_m=float(data.xpos[cup, 2] - context['table_height_m']),
                       table_support_N=table_load, hand_contact_N=sum(loads.values()),
                       linear_speed_m_s=float(np.linalg.norm(data.qvel[cup_dof:cup_dof + 3])),
                       angular_speed_rad_s=float(np.linalg.norm(data.qvel[cup_dof + 3:cup_dof + 6])),
                       pelvis_tilt_deg=tilt, pelvis_drift_m=drift)
            rows.append(row)
    result = summarize(rows, task, env['protection'], execution_error)
    result.update(independent_of_controller_result=True, method='saved state and force replay at 20Hz',
                  task=task, boundary='simulation', formal_skill_promotion=False,
                  no_external_forces=not bool(np.any(data.qfrc_applied) or np.any(data.xfrc_applied)),
                  equality_constraints=int(model.neq), trajectory_sha256=sha(folder / 'trajectory.npz'))
    if not result['no_external_forces'] or model.neq:
        result['verified_success'] = False
    return result, rows


def summarize_two(samples, cup_results):
    if set(cup_results) != {'task_cup', 'task_cup_2'}:
        raise ValueError('Two distinct physical cup identities are required')
    start, duration = None, 0.
    for row in samples:
        if set(row['cups']) != set(cup_results):
            raise ValueError('Missing a physical cup in saved replay')
        if all(placement_predicate(item) for item in row['cups'].values()):
            start = row['time'] if start is None else start
            duration = row['time'] - start
        else:
            start, duration = None, 0.
    return dict(verified_success=all(r['verified_success'] for r in cup_results.values()) and duration >= 1.,
                grasp_passed=all(r['grasp_passed'] for r in cup_results.values()),
                placement_passed=all(r['placement_passed'] for r in cup_results.values()) and duration >= 1.,
                terminal_simultaneous_stable_s=duration, cups=cup_results,
                independent_of_controller_result=True, formal_skill_promotion=False, boundary='simulation')


def verify(folder, execution_error=None):
    folder = Path(folder)
    if (folder / 'evaluator_targets.json').exists():
        targets = read(folder / 'evaluator_targets.json')['targets']
        if set(targets) != {'task_cup', 'task_cup_2'}:
            raise ValueError('Expected two distinct cup assignments')
        if np.linalg.norm(np.asarray(targets['task_cup'])[:2]-np.asarray(targets['task_cup_2'])[:2]) <= .04:
            raise ValueError('Goal regions must be disjoint')
        cups, samples = {}, {}
        for name, target in targets.items():
            cups[name], samples[name] = verify_cup(folder, execution_error, name, target)
        if [r['time'] for r in samples['task_cup']] != [r['time'] for r in samples['task_cup_2']]:
            raise ValueError('Cup replays are not time aligned')
        rows = [dict(time=row['time'], cups={name: samples[name][i] for name in targets})
                for i, row in enumerate(samples['task_cup'])]
        result = summarize_two(rows, cups)
    else:
        result, rows = verify_cup(folder, execution_error)
    write_new(folder / 'independent_verification.json', result)
    write_new(folder / 'verified_samples.json', rows)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode', type=Path)
    args = parser.parse_args()
    print(verify(args.episode))
