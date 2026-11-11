"""Numerical task relations, with one simultaneous terminal stability window."""
import math

import mujoco
import numpy as np

VERSION = 't0-diversity-predicates-v1'
LIMITS = dict(margin_m=.001, height_error_m=.004, hand_force_N=.1,
              linear_speed_m_s=.02, angular_speed_rad_s=.2,
              object_tilt_deg=10., container_tilt_deg=5.,
              door_closed_rad=.035, door_speed_rad_s=.05,
              stable_s=1., max_sample_gap_s=.051)


def rotation(quaternion):
    matrix = np.empty(9)
    mujoco.mju_quat2Mat(matrix, np.asarray(quaternion, dtype=float))
    return matrix.reshape(3, 3)


def snapshot(model, data, instance, base=None):
    """Read simulator geometry/forces; these privileged fields are evaluator-only."""
    objects = {}
    for item in instance['objects']+instance['facilities']:
        name = item['name']
        bid = model.body(name).id
        linear = angular = 0.
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name+'_free')
        if jid >= 0:
            dof = model.jnt_dofadr[jid]
            linear = float(np.linalg.norm(data.qvel[dof:dof+3]))
            angular = float(np.linalg.norm(data.qvel[dof+3:dof+6]))
        objects[name] = dict(position_m=data.xpos[bid].tolist(),
                             quaternion_wxyz=data.xquat[bid].tolist(),
                             linear_speed_m_s=linear, angular_speed_rad_s=angular,
                             upward_support_N={}, hand_contact_N=0.)
    # Facility door contacts belong to the cabinet for the release predicate.
    door_owners = {x['name']+'_door': x['name'] for x in instance['facilities']
                   if x['asset']['kind'] == 'cabinet'}
    for region in instance['regions']:
        objects[region['name']] = dict(position_m=region['position_m'],
            quaternion_wxyz=region['quaternion_wxyz'], linear_speed_m_s=0.,
            angular_speed_rad_s=0., upward_support_N={}, hand_contact_N=0.)
    penetrations = []
    for i in range(data.ncon):
        contact = data.contact[i]
        names = [model.body(int(model.geom_bodyid[g])).name for g in (contact.geom1, contact.geom2)]
        geoms = [model.geom(g).name for g in (contact.geom1, contact.geom2)]
        force = np.zeros(6)
        mujoco.mj_contactForce(model, data, i, force)
        world_force = contact.frame.reshape(3, 3).T @ force[:3]
        for j, raw_name in enumerate(names):
            name = door_owners.get(raw_name, raw_name)
            if name not in objects:
                continue
            other = names[1-j]
            if '_hand_' in other:
                objects[name]['hand_contact_N'] += abs(float(force[0]))
            upward = float(world_force[2])*(1 if j else -1)
            if upward > 0:
                support = objects[name]['upward_support_N']
                # Container walls and floor must remain distinguishable.
                key = geoms[1-j] if other in objects and any(
                    x['name'] == other and x['asset']['kind'] in ('tray', 'platter')
                    for x in instance['objects']) else other
                support[key] = support.get(key, 0.)+upward
        if contact.dist < -.001 and any(n in objects for n in names):
            penetrations.append(dict(bodies=names, geoms=geoms, depth_m=-float(contact.dist)))
    joints = {}
    for item in instance['facilities']:
        if item['asset']['kind'] == 'cabinet':
            jid = model.joint(item['name']+'_hinge').id
            joints[item['name']] = dict(position_rad=float(data.qpos[model.jnt_qposadr[jid]]),
                                       speed_rad_s=float(data.qvel[model.jnt_dofadr[jid]]))
    robot = None
    if base is not None:
        pelvis = model.body('pelvis').id
        robot = dict(tilt_deg=float(np.degrees(np.arccos(np.clip(data.xmat[pelvis, 8], -1, 1)))),
                     drift_m=float(np.linalg.norm(data.xpos[pelvis, :2]-np.asarray(base)[:2])))
    return dict(time=float(data.time), objects=objects, joints=joints, robot=robot,
                external_forces=bool(np.any(data.qfrc_applied) or np.any(data.xfrc_applied)),
                equality_constraints=int(model.neq), penetrations=penetrations)


def footprint(item, state, target_rotation):
    a = item['asset']
    relative_rotation = target_rotation.T @ rotation(state['quaternion_wxyz'])
    if a['kind'] == 'fruit':
        # Exact orthographic ellipse extent, including a tilted ellipsoid.
        radii = np.asarray(a['radii_m'])
        extent = np.sqrt(np.sum((relative_rotation[:2]*radii)**2, axis=1))
        offset = relative_rotation @ np.array([0., 0., radii[2]])
        return extent, offset
    if a['kind'] in ('tray', 'platter'):
        extent = np.abs(relative_rotation[:2, :2]) @ np.asarray(a['half_xy_m'])
        extent += np.abs(relative_rotation[:2, 2])*a['height_m']
        return extent, np.zeros(3)
    # The complete circular cup base, not its centre and not its handle.
    return np.array([a['radius_m']]*2), np.zeros(3)


def relation(instance, frame, obj_name, target_name, inside):
    by_name = {x['name']: x for x in instance['objects']+instance['facilities']+instance['regions']}
    item, target = by_name[obj_name], by_name[target_name]
    state, dest = frame['objects'][obj_name], frame['objects'][target_name]
    r = rotation(dest['quaternion_wxyz'])
    local = r.T @ (np.asarray(state['position_m'])-np.asarray(dest['position_m']))
    extent, offset = footprint(item, state, r)
    a = target.get('asset')
    inner = np.asarray(a['half_xy_m'])-a.get('rim_m', 0.) if a else np.asarray(target['half_xy_m'])
    margin = float(np.min(inner-np.abs(local[:2]+offset[:2])-extent))
    if not inside:
        return margin >= LIMITS['margin_m']
    floor = a.get('floor_m', 0.) if a else 0.
    support_name = target_name+'_floor' if a and a['kind'] in ('tray', 'platter') else target.get('support_body', target_name)
    support = state['upward_support_N'].get(support_name, 0.)
    min_force = .25*item['asset']['mass_kg']*9.81
    return bool(margin >= LIMITS['margin_m'] and abs(local[2]-floor) <= LIMITS['height_error_m']
                and support >= min_force and state['hand_contact_N'] < LIMITS['hand_force_N'])


def frame_predicates(instance, frame):
    # Missing objects, contacts or joint evidence raise; they never default to true.
    conditions, involved = [], set()
    for goal in instance['goals']:
        op = goal['predicate']
        if op in ('SupportedIn', 'OnRegion'):
            obj, target = goal['object'], goal['target']
            conditions.append(relation(instance, frame, obj, target, True))
            involved.update((obj, target))
        elif op == 'DistinctSeats':
            import itertools
            objects, targets = goal['objects'], goal['targets']
            conditions.append(any(all(relation(instance, frame, obj, target, True)
                                      for obj, target in zip(objects, order))
                                  for order in itertools.permutations(targets, len(objects))))
            involved.update(objects+targets)
        elif op == 'Closed':
            joint = frame['joints'][goal['object']]
            conditions.append(abs(joint['position_rad']) <= LIMITS['door_closed_rad']
                              and abs(joint['speed_rad_s']) <= LIMITS['door_speed_rad_s'])
            involved.add(goal['object'])
        else:
            raise ValueError(f'Unknown predicate: {op}')
    all_items = {x['name']: x for x in instance['objects']}
    for name in involved:
        state = frame['objects'][name]
        conditions.extend([state['linear_speed_m_s'] <= LIMITS['linear_speed_m_s'],
                           state['angular_speed_rad_s'] <= LIMITS['angular_speed_rad_s'],
                           state['hand_contact_N'] < LIMITS['hand_force_N']])
        if name in all_items:
            kind = all_items[name]['asset']['kind']
            if kind in ('cup', 'bottle', 'tray', 'platter'):
                tilt = math.degrees(math.acos(float(np.clip(rotation(state['quaternion_wxyz'])[2, 2], -1, 1))))
                limit = LIMITS['container_tilt_deg'] if kind in ('tray', 'platter') else LIMITS['object_tilt_deg']
                conditions.append(tilt <= limit)
    # Also exclude a held distractor at completion.
    conditions.extend(frame['objects'][x['name']]['hand_contact_N'] < LIMITS['hand_force_N']
                      for x in instance['objects'])
    return bool(conditions and all(conditions))


def evaluate_trace(instance, frames, *, initial_valid=False, execution_error=None, protection=None):
    if not frames:
        raise ValueError('Empty independent evidence')
    previous, start, stable = None, None, 0.
    retained, robot_valid, complete_process_evidence = True, True, True
    for frame in frames:
        time = frame['time']
        if not math.isfinite(time) or previous is not None and time <= previous:
            raise ValueError('Evidence time must be finite and strictly increasing')
        gap = previous is not None and time-previous > LIMITS['max_sample_gap_s']
        if gap and instance['process_constraints']:
            complete_process_evidence = False
        for constraint in instance['process_constraints']:
            retained = retained and relation(instance, frame, constraint['object'], constraint['target'], False)
        valid = frame_predicates(instance, frame) and retained
        if valid:
            start = time if start is None or gap else start
            stable = time-start
        else:
            start, stable = None, 0.
        robot = frame['robot']
        robot_valid = (robot_valid and robot is not None and robot['tilt_deg'] <= 5.
                       and robot['drift_m'] <= .03 and not frame['external_forces']
                       and frame['equality_constraints'] == 0)
        previous = time
    goal_satisfied = bool(stable+1e-9 >= LIMITS['stable_s'] and retained and complete_process_evidence)
    return dict(goal_satisfied=goal_satisfied, terminal_simultaneous_stable_s=stable,
                process_constraints_satisfied=retained, robot_evidence_valid=bool(robot_valid),
                initial_valid=bool(initial_valid), execution_error=execution_error, protection=protection,
                verified_task_success=bool(goal_satisfied and robot_valid and initial_valid
                                           and not execution_error and not protection),
                evaluator_version=VERSION, sampled_evidence=True,
                scope='numeric relations only; task execution additionally requires a qualified robot trace')
