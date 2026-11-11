"""Independently inspect saved physics states, not controller success claims."""
import argparse
import hashlib
import json
from pathlib import Path

import mujoco
import numpy as np

from diagnose_grasp import contacts, write_json


def verify(folder):
    folder = Path(folder)
    model = mujoco.MjModel.from_binary_path(str(folder/'model.mjb'))
    data = mujoco.MjData(model)
    initial = np.load(folder/'initial_state.npz', allow_pickle=False)
    mujoco.mj_setState(model, data, initial['mujoco_integration_state'], mujoco.mjtState.mjSTATE_INTEGRATION)
    mujoco.mj_forward(model, data)
    cup = model.body('task_cup').id
    pelvis = model.body('pelvis').id
    initial_z = float(data.xpos[cup, 2])
    base_reference = initial['base_reference']
    kp, kd = initial['kp'], initial['kd']
    joints = model.actuator_trnid[:, 0]
    qids, vids = model.jnt_qposadr[joints], model.jnt_dofadr[joints]
    cup_geoms = np.flatnonzero((model.geom_bodyid == cup) & (model.geom_contype != 0))
    context = json.loads((folder/'runtime_context.json').read_text())
    trace = np.load(folder/'trajectory.npz', allow_pickle=False)
    rows = []
    for i, t in enumerate(trace['time']):
        data.qpos[:] = trace['qpos'][i]
        data.qvel[:] = trace['qvel'][i]
        data.time = t
        # Recover effective controls from recorded motor forces; do not re-run the controller.
        data.ctrl[:] = data.qpos[qids] + (trace['actuator_force'][i]+kd*data.qvel[vids])/kp
        mujoco.mj_forward(model, data)
        cs = contacts(model, data, context)
        cup_contacts = [c for c in cs if 'task_cup' in c['bodies']]
        hand_load = {}
        normals = {}
        other_load = 0.
        for c in cup_contacts:
            body = next(b for b in c['bodies'] if b != 'task_cup')
            if '_hand_' not in body:
                other_load += c['normal_force_N']
                continue
            digit = body.split('_hand_')[1].split('_')[0]
            side = body.split('_hand_')[0]
            key = side + '_' + digit
            hand_load[key] = hand_load.get(key, 0.) + c['normal_force_N']
            normal = np.asarray(c['normal']) * (1 if c['bodies'][0] == 'task_cup' else -1)
            normals[key] = normals.get(key, np.zeros(3)) + c['normal_force_N']*normal
        opposed = False
        for side in ('left', 'right'):
            thumb = normals.get(side+'_thumb')
            for digit in ('index', 'middle'):
                finger = normals.get(side+'_'+digit)
                if (thumb is not None and finger is not None
                        and hand_load[side+'_thumb'] >= .1 and hand_load[side+'_'+digit] >= .1):
                    opposed |= float(thumb@finger/(np.linalg.norm(thumb)*np.linalg.norm(finger))) < -.5
        lowest = float('inf')
        for g in cup_geoms:
            rot = data.geom_xmat[g].reshape(3, 3)
            size = model.geom_size[g]
            kind = model.geom_type[g]
            if kind == mujoco.mjtGeom.mjGEOM_BOX:
                half_z = float(np.abs(rot[2])@size)
            elif kind == mujoco.mjtGeom.mjGEOM_CYLINDER:
                half_z = float(abs(rot[2, 2])*size[1]+np.linalg.norm(rot[2, :2])*size[0])
            elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
                half_z = float(abs(rot[2, 2])*size[1]+size[0])
            else:
                raise ValueError('Unexpected cup collision primitive')
            lowest = min(lowest, float(data.geom_xpos[g, 2])-half_z)
        clearance = lowest-context['table_height_m']
        lift = float(data.xpos[cup, 2]-initial_z)
        tilt = float(np.degrees(np.arccos(np.clip(data.xmat[pelvis, 8], -1, 1))))
        drift = float(np.linalg.norm(data.qpos[:2]-base_reference[:2]))
        held = bool(lift >= .1 and clearance >= .09 and opposed and other_load < .1
                    and tilt <= 5 and drift <= .03)
        rows.append(dict(time=float(t), lift_m=lift, cup_lowest_clearance_m=clearance,
                         cup_tilt_deg=float(np.degrees(np.arccos(np.clip(data.xmat[cup, 8], -1, 1)))),
                         pelvis_tilt_deg=tilt, pelvis_drift_m=drift,
                         digit_normal_load_N=hand_load, opposing_contacts=bool(opposed),
                         non_hand_support_load_N=other_load, held=held,
                         max_penetration_m=max([c['penetration_m'] for c in cup_contacts], default=0.)))
    longest, start = 0., None
    for row in rows:
        if row['held']:
            if start is None:
                start = row['time']
            longest = max(longest, row['time']-start)
        else:
            start = None
    initial_sha = hashlib.sha256(initial['mujoco_integration_state'].tobytes()).hexdigest()
    result = dict(verified_success=longest >= 1., independent_of_controller_result=True,
                  method='recompute geometry and contact forces from saved physical states and recorded motor forces',
                  sample_interval_s=.05, duration_rule='last minus first qualifying sample; no interpolation',
                  max_lift_m=max(r['lift_m'] for r in rows), longest_strict_hold_s=longest,
                  max_pelvis_tilt_deg=max(r['pelvis_tilt_deg'] for r in rows),
                  max_pelvis_drift_m=max(r['pelvis_drift_m'] for r in rows),
                  max_cup_contact_penetration_m=max(r['max_penetration_m'] for r in rows),
                  equality_constraints=int(model.neq), initial_integration_state_sha256=initial_sha,
                  no_external_base_force=not bool(np.any(data.xfrc_applied) or np.any(data.qfrc_applied)),
                  final=rows[-1], frames=len(rows))
    write_json(folder/'independent_verification.json', result)
    write_json(folder/'verified_samples.json', rows)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode', type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.episode)['verified_success'] else 1)
