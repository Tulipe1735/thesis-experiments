"""Register a bounded development extension before any robot outcome is observed."""
import argparse
from copy import deepcopy
import itertools
import math
import os
from pathlib import Path
import random
import xml.etree.ElementTree as ET

from experiments.t0_agent_v1.common import ROOT, read, relative, sha, source_hashes, write_new
from experiments.t0_agent_v1.diversity_assets import add_body
from .worker import SOURCE, REGISTRY
from experiments.t0_agent_v1.runtime import mujoco, np

VERSION = 'cordis-t01-variation-dev-v1'
SCENE = ROOT/'experiments/t0_agent_v1/tray_20261025_001/T01_scene.xml'
CUPS = ['DH_2F_mug_06', 'white_tumbler_r41_h115_v1']
TRAYS = ['rectangular_low_rim_v1', 'marked_long_tray_v1']


def quaternion(yaw):
    return [math.cos(yaw/2), 0., 0., math.sin(yaw/2)]


def case(group, seed, cup=CUPS[0], tray=TRAYS[0], random_pose=False):
    rng = random.Random(f'{VERSION}:{group}:{seed}')
    instance = deepcopy(read(SOURCE/'instance.json'))
    instance.update(seed=seed, split='development_extension')
    item, container = instance['cups'][0], instance['tray']
    item['asset'], container['asset'] = cup, tray
    # Common center for the new groups leaves room for +/-0.1 rad tray yaw.
    container.update(xy_m=[.22378, .375], yaw_rad=0., quaternion_wxyz=quaternion(0.))
    if tray == TRAYS[1]:
        container.update(half_size_xy_m=[.24, .06], rim_height_m=.022, mass_kg=.70)
    if group in ('position', 'joint') or random_pose:
        extent = .02 if group == 'position' else .015
        item['cup_table_xy_m'] = [x+rng.uniform(-extent, extent) for x in item['cup_table_xy_m']]
        container['xy_m'] = [x+rng.uniform(-.008, .008) for x in container['xy_m']]
    if group in ('orientation', 'joint'):
        item['cup_yaw_rad'] = rng.uniform(-math.pi, math.pi)
        item['cup_quaternion_wxyz'] = quaternion(item['cup_yaw_rad'])
        limit = .10 if group == 'orientation' else .05
        container['yaw_rad'] = rng.uniform(-limit, limit)
        container['quaternion_wxyz'] = quaternion(container['yaw_rad'])
    instance.update(cup_table_xy_m=item['cup_table_xy_m'],
                    cup_quaternion_wxyz=item['cup_quaternion_wxyz'])
    instance['sampling'] = dict(version=VERSION, group=group,
        namespace=f'{VERSION}:{group}:{seed}', outcome_filter=False, resampled=0,
        held_out=False, robot_joint_offsets_rad={}, actual_pose_saved=True)
    return dict(id=f'{group}_{seed}', group=group, cup_asset=cup, tray_asset=tray, instance=instance,
                initial_source=None, model_key=f'{cup}__{tray}')


def roster():
    control = dict(id='control_2500', group='control', cup_asset=CUPS[0], tray_asset=TRAYS[0],
        instance=read(SOURCE/'instance.json'), initial_source=relative(SOURCE/'initial_state.npz'),
        model_key=f'{CUPS[0]}__{TRAYS[0]}')
    cases = [case(group, start+i) for group, start in [('position', 280100), ('orientation', 280200)] for i in range(4)]
    for i, (cup, tray) in enumerate(itertools.product(CUPS, TRAYS)):
        cases.append(case('asset', 280300+i, cup, tray))
        cases.append(case('joint', 280400+i, cup, tray))
    random.Random(VERSION+':schedule').shuffle(cases)
    return [control]+cases


def variant_xml(cup, tray, output):
    tree = ET.parse(SCENE)
    root, world = tree.getroot(), tree.getroot().find('worldbody')
    for element in root.iter():
        if 'file' in element.attrib:
            element.set('file', os.path.relpath((SCENE.parent/element.get('file')).resolve(), output))
    if cup != CUPS[0]:
        original = world.find("body[@name='task_cup']")
        position, rotation = [float(v) for v in original.get('pos').split()], [float(v) for v in original.get('quat').split()]
        world.remove(original)
        definition = dict(id=CUPS[1], kind='cup', radius_m=.041, height_m=.115, mass_kg=.19,
                          footprint_radius_m=.041, handle=False, rgba=[.9, .9, .9, 1.])
        add_body(world, dict(name='task_cup', asset=definition, position_m=position, quaternion_wxyz=rotation))
        for geom in world.find("body[@name='task_cup']").iter('geom'):
            geom.attrib.update(contype='4', conaffinity='15', group='2', friction='1 .01 .0001',
                               solref='.008 1', solimp='.95 .99 .001')
    if tray != TRAYS[0]:
        body = world.find("body[@name='task_tray']")
        body.find("geom[@name='tray_floor']").attrib.update(size='.24 .06 .003', mass='.62')
        for side, sign in [('left', 1), ('right', -1)]:
            body.find(f"geom[@name='tray_rim_{side}']").attrib.update(
                size='.003 .06 .011', pos=f'{sign*.237} 0 .011')
        for side, sign in [('near', 1), ('far', -1)]:
            body.find(f"geom[@name='tray_rim_{side}']").attrib.update(
                size='.234 .003 .011', pos=f'0 {sign*.057} .011')
    return tree


def build_model(output, cup, tray, baseline):
    if (cup, tray) == (CUPS[0], TRAYS[0]):
        return read(SOURCE/'model_reference.json')
    name = f'{cup}__{tray}'
    xml, binary = output/(name+'.xml'), output/(name+'.mjb')
    with xml.open('xb') as stream:
        variant_xml(cup, tray, output).write(stream, encoding='utf-8', xml_declaration=True)
    model = mujoco.MjModel.from_xml_path(str(xml))
    for field in ('actuator_gainprm', 'actuator_biastype', 'actuator_biasprm',
                  'actuator_ctrllimited', 'actuator_forcelimited', 'actuator_forcerange'):
        getattr(model, field)[:] = getattr(baseline, field)
    for joint in range(baseline.njnt):
        target = model.joint(baseline.joint(joint).name).id
        for field in ('jnt_range', 'jnt_actfrcrange', 'jnt_actfrclimited'):
            getattr(model, field)[target] = getattr(baseline, field)[joint]
    assert model.neq == 0 and model.nu == baseline.nu
    for body in range(baseline.nbody):
        name_ = baseline.body(body).name
        if name_ in ('task_cup', 'task_tray'):
            continue
        target = model.body(name_).id
        assert np.array_equal(model.body_mass[target], baseline.body_mass[body]), name_
        assert np.array_equal(model.body_inertia[target], baseline.body_inertia[body]), name_
    mujoco.mj_saveModel(model, str(binary), None)
    return dict(path=relative(binary), sha256=sha(binary), xml=relative(xml), xml_sha256=sha(xml),
                copied=False, unique_asset_variant=True, robot_and_room_physics_preserved=True)


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    cases = roster()
    write_new(output/'planned_cases.json', cases)
    write_new(output/'design.json', dict(date='2026-10-28', status='registered_before_robot_execution',
        version=VERSION, boundary='simulation', max_episodes=17, control=1, new_development_cases=16,
        per_group=dict(position=4, orientation=4, asset=4, joint=4),
        schedule=[c['id'] for c in cases], same_controller_for_all=True, no_outcome_resampling=True,
        controller_and_evaluator_revision=False, models_requested=0,
        cup_variants=dict(native='DH_2F_mug_06', proxy='white handleless cylinder, r41mm, h115mm, mass0.19kg'),
        tray_variants=dict(native='440x120mm, rim18mm, mass0.60kg', proxy='480x120mm, rim22mm, mass0.70kg'),
        fixed_asset_compatibility=['upright white cup of known 41mm radius class',
            'four existing tray marker positions retained', '6mm tray floor; conservative original planning region'],
        pose_ranges=dict(cup_position_delta_m=.02, tray_position_delta_m=.008,
            cup_yaw_rad=[-math.pi, math.pi], tray_yaw_rad=[-.10, .10],
            joint_cup_delta_m=.015, joint_tray_yaw_rad=[-.05, .05]),
        no_claims=['no random population success estimate', 'no new learning', 'no full color or unmarked tray coverage'],
        media_selection='first joint case in registered order; also first failure if any'))
    models_dir = output/'models'
    models_dir.mkdir()
    baseline = mujoco.MjModel.from_binary_path(str(ROOT/read(SOURCE/'model_reference.json')['path']))
    models = {f'{cup}__{tray}': build_model(models_dir, cup, tray, baseline)
              for cup, tray in itertools.product(CUPS, TRAYS)}
    inputs = {relative(path): sha(path) for path in [REGISTRY, SCENE, SOURCE/'instance.json',
              SOURCE/'initial_state.npz', SOURCE/'model_reference.json']}
    inputs.update({ref['path']:ref['sha256'] for ref in models.values()})
    sources = source_hashes()
    sources.update({relative(p):sha(p) for p in Path(__file__).parent.glob('*.py')})
    write_new(output/'registration.json', dict(date='2026-10-28', boundary='simulation', version=VERSION,
        status='frozen_before_robot_execution', cases=cases, models=models, input_sha256=inputs,
        source_sha256=sources, expected_program=['inspect_scene', 'grasp_cup', 'place_in_tray', 'verify_task'],
        max_physical_episodes=17, simulation_budget_s=180., no_tuning_during_suite=True,
        old_runs_immutable=True, model_requests=0, formal_skill_promotions=0))
    print(relative(output), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output)
