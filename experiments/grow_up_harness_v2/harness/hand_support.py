"""Evaluator hand rule v2 (K2, user decision 2026-11-17): palm contacts count as hand.

The G1 palm mesh (left/right_hand_palm_link) hangs on the *_wrist_yaw_link body, which also
carries the wrist mesh. The frozen snapshot classifies contacts by body name, so a target
cradled on the palm is booked as non-hand support and adds no hand contact, while the plant's
protection rule already treats the palm mesh as hand. v2 re-books palm-mesh contacts under the
mesh name; every other contact, the frozen predicates and their thresholds are unchanged.
Frozen sources are not edited; the v1 reading is kept alongside.
"""
import types
from pathlib import Path

import mujoco
import numpy as np

from experiments.t0_agent_v1 import diversity_predicates as D
from experiments.t0_agent_v1.common import write_new

VERSION = 'palm-hand-v2-20261117'


def palm_geoms(model):
    """Geom id -> mesh name for every geom built from a *_hand_palm_link mesh."""
    return {g: model.mesh(int(model.geom_dataid[g])).name for g in range(model.ngeom)
            if model.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH
            and model.mesh(int(model.geom_dataid[g])).name.endswith('_hand_palm_link')}


def snapshot(model, data, instance, base=None):
    """The frozen snapshot with palm-mesh contacts booked as hand support and hand contact."""
    frame = D.snapshot(model, data, instance, base)
    palms = palm_geoms(model)
    objects = frame['objects']
    doors = {x['name'] + '_door': x['name'] for x in instance['facilities'] if x['asset']['kind'] == 'cabinet'}
    carriers = {int(model.geom_bodyid[g]) for g in palms}
    # (object, carrier body) -> support from the carrier's other geoms, summed in contact order like the frozen loop.
    rest, palm = {}, {}
    for i in range(data.ncon):
        contact = data.contact[i]
        geoms = (contact.geom1, contact.geom2)
        if not any(int(model.geom_bodyid[g]) in carriers for g in geoms):
            continue
        force = np.zeros(6)
        mujoco.mj_contactForce(model, data, i, force)
        upward_world = float((contact.frame.reshape(3, 3).T @ force[:3])[2])
        for j, g in enumerate(geoms):
            raw = model.body(int(model.geom_bodyid[g])).name
            name, other = doors.get(raw, raw), geoms[1 - j]
            if name not in objects or int(model.geom_bodyid[other]) not in carriers:
                continue
            key = (name, model.body(int(model.geom_bodyid[other])).name)
            upward = upward_world * (1 if j else -1)
            if other in palms:
                objects[name]['hand_contact_N'] += abs(float(force[0]))
                if upward > 0:
                    palm.setdefault(key, {}).setdefault(palms[other], 0.)
                    palm[key][palms[other]] += upward
            elif upward > 0:
                rest[key] = rest.get(key, 0.) + upward
    for (name, body), meshes in palm.items():
        support = objects[name]['upward_support_N']
        if (name, body) in rest:
            support[body] = rest[(name, body)]
        else:
            support.pop(body)
        for mesh, value in meshes.items():
            support[mesh] = support.get(mesh, 0.) + value
    return frame


def verify(template, out=None, rule=VERSION):
    """The kernel's verifier for template under rule (VERSION, or None for v1), replayed from saved states.

    Files carry a _v2 or _v1 suffix and go to out, or to the episode folder when out is None, so the
    unsuffixed v1 files the kernel writes and a recorded run's own files are never touched.
    """
    from . import t03_evaluator as E
    from experiments.t0_agent_v1 import tabletop_predicates as P
    from experiments.t0_agent_v1.tabletop_training_plant import independent_verify
    judge = P.evaluate_trace if template == 'TP01' else E.evaluate_trace
    if rule not in (VERSION, None):
        raise ValueError('unknown hand rule: ' + rule)

    def evaluate_trace(*args, **kwargs):
        result = judge(*args, **kwargs)
        if rule:
            result.update(evaluator_version=f"{result['evaluator_version']}+{VERSION}", hand_rule=VERSION)
        return result

    def run(folder, instance, model, initial_valid=True):
        target = Path(out or folder)
        tag = '_v2' if rule else '_v1'
        namespace = dict(independent_verify.__globals__, evaluate_trace=evaluate_trace,
                         snapshot=snapshot if rule else D.snapshot,
                         write_new=lambda path, data: write_new(target / f'{path.stem}{tag}{path.suffix}', data))
        replay = types.FunctionType(independent_verify.__code__, namespace, independent_verify.__name__,
                                    independent_verify.__defaults__)
        return replay(folder, instance, model, initial_valid=initial_valid)
    return run
