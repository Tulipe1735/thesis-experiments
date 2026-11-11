"""Generate immutable T01–T07 development instances and qualify their initial physics.

Run from the repository root with G1_PYTHON; no policy or model gateway is called.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from .common import ROOT, REFERENCE, read, relative, sha, write_new
from .diversity_assets import (VERSION as ASSET_VERSION, add_body, add_facility,
                               add_vendor_bottle, catalog, geom, values)
from .diversity_predicates import (VERSION as EVALUATOR_VERSION, LIMITS,
                                   evaluate_trace, frame_predicates, relation, snapshot)

VERSION = 't0-diversity-generator-v3'
SAMPLING_NAMESPACE = 't0-diversity-generator-v1'
TASKS = {
    'T01': dict(label='单杯放入托盘', classification='指定物取放', cups=1),
    'T02': dict(label='多杯归集', classification='多物归集', cups=3),
    'T03': dict(label='指定水果放入果盘', classification='指定物取放', fruits=1),
    'T04': dict(label='杯子、水果分类收纳', classification='分类收纳'),
    'T05': dict(label='水瓶从货架送到桌面', classification='点到点取送', bottles=1),
    'T06': dict(label='开柜取杯、送达并关柜', classification='复合任务：存取与设施复原', cups=1),
    'T07': dict(label='两人茶歇布置', classification='复合任务：分发与空间布置', cups=2, fruits=2),
}
SOURCE = ROOT/'grasp_optimization/scenes/pantry/mujoco_native_v01/P01_seed_1000.xml'


def rng_for(seed, task, axis):
    # Keep pose proposals identical when correcting an asset's physical model.
    return random.Random(f'{SAMPLING_NAMESPACE}:{task}:{seed}:{axis}')


def quaternion(yaw):
    return [math.cos(yaw/2), 0., 0., math.sin(yaw/2)]


def radius(item):
    a = item['asset']
    return a.get('footprint_radius_m', math.hypot(*a.get('half_xy_m', [0, 0])))


def object_row(name, a, xyz, yaw=0., support='worktable', target=True):
    return dict(name=name, asset=deepcopy(a), position_m=list(xyz), yaw_rad=yaw,
                quaternion_wxyz=quaternion(yaw), initial_support=support, is_target=target)


def collision_free(item, others, margin=.006):
    for other in others:
        if item['initial_support'] != other['initial_support']:
            continue
        if math.dist(item['position_m'][:2], other['position_m'][:2]) < radius(item)+radius(other)+margin:
            return False
    return True


def pack(container, objects):
    """A conservative static capacity witness, never an executed robot solution."""
    if not objects:
        return []
    a = container['asset']
    inner = np.asarray(a['half_xy_m'])-a['rim_m']-.003
    r = max(radius(x) for x in objects)
    axes = []
    for half in inner:
        count = max(0, int((2*half+.008)//(2*r+.008)))
        axes.append(np.linspace(-half+r, half-r, count).tolist() if count else [])
    slots = [[x, y, a['floor_m']] for y in axes[1] for x in axes[0]]
    if len(slots) < len(objects):
        raise ValueError('container_capacity')
    return [dict(object=obj['name'], target=container['name'], local_bottom_xyz_m=slot)
            for obj, slot in zip(objects, slots)]


def geometry_rejections(instance):
    from .diversity_predicates import rotation
    failures = []
    for item in instance['objects']:
        a, support = item['asset'], item['initial_support']
        if support != 'worktable':
            continue
        extent = (np.abs(rotation(item['quaternion_wxyz'])[:2, :2]) @ np.asarray(a['half_xy_m'])
                  if 'half_xy_m' in a else np.array([radius(item)]*2))
        if np.any(np.abs(item['position_m'][:2])+extent+.002 > np.array([.66, .46])):
            failures.append('full_initial_footprint_outside_worktable:'+item['name'])
    return failures


def sample(task, seed, variation='joint'):
    if task not in TASKS or type(seed) is not int or seed < 0 or variation not in ('joint', 'position', 'asset'):
        raise ValueError('Expected T01–T07, a nonnegative integer seed and a known variation axis')
    assets = catalog()
    arng = rng_for(seed if variation != 'position' else 0, task, 'asset')
    prng = rng_for(seed if variation != 'asset' else 0, task, 'pose')
    crng = rng_for(seed if variation != 'position' else 0, task, 'count')
    z = read(REFERENCE/'runtime_context.json')['table_height_m']
    counts = dict(cups=TASKS[task].get('cups', 0), fruits=TASKS[task].get('fruits', 0),
                  bottles=TASKS[task].get('bottles', 0), distractors=0)
    if task == 'T04':
        counts.update(cups=crng.randint(1, 3), fruits=crng.randint(1, 2), distractors=crng.randint(0, 2))
    instance = dict(id=f'{task}_{seed}_{variation}', task=task, seed=seed, split='development',
        boundary='simulation', label=TASKS[task]['label'], classification=TASKS[task]['classification'],
        frame='existing pantry table axes, metres, Z up; facilities in qualification fixtures are synthetic',
        scene_id='pantry' if task in ('T01', 'T02', 'T03', 'T04') else 'synthetic_asset_qualification',
        generator_version=VERSION, asset_version=ASSET_VERSION, evaluator_version=EVALUATOR_VERSION,
        counts=counts, objects=[], facilities=[], regions=[], goals=[], process_constraints=[],
        sampling=dict(variation=variation, pose_seed=seed if variation != 'asset' else 0,
            asset_seed=seed if variation != 'position' else 0, attempts=[], outcome_filter=False,
            random_namespace=SAMPLING_NAMESPACE,
            asset_axis_semantics='fixed pose proposals; accepted poses may depend on geometry rejection',
            max_pose_attempts_per_object=64, held_out=False,
            rejection_basis='geometry before any policy execution; no failed seed replaced'),
        robot=dict(stance=read(ROOT/'grasp_optimization/scenes/pantry/p01_zones_v01/candidates/P01_native_v01_practice_1000.json')['robot_stance'],
                   joint_offsets_rad={}, source='grasp_optimization/episodes/final_reference_1000',
                   reachability='not_checked', motion_tools_qualified=False),
        readiness=dict(qualification_fixture=True, native_G1_scene=task in ('T01', 'T02', 'T03', 'T04'),
            robot_task_executed=False, reference_solution_verified=False,
            blockers=['新资产与位置的感知、可达性、扫掠碰撞和操控验收'] if task in ('T01', 'T02', 'T03', 'T04')
                     else ['真实房间货架/柜体绑定', 'G1移动接口与通路验证']+
                          (['柜门接触开合与取物规划'] if task in ('T06', 'T07') else [])))

    def choose(kind):
        return arng.choice([a for a in assets.values() if a['kind'] == kind])

    def add_region(name, xyz, half, support):
        instance['regions'].append(dict(name=name, position_m=list(xyz), half_xy_m=list(half),
            quaternion_wxyz=quaternion(0), support_body=support))

    containers = {}
    if task in ('T01', 'T02', 'T04'):
        containers['tray'] = object_row('tray', choose('tray'),
            [(-.34 if task == 'T04' else 0.)+prng.uniform(-.015, .015), .30+prng.uniform(-.01, .01), z+.0005],
            prng.uniform(-.10, .10), target=False)
    if task in ('T03', 'T04', 'T07'):
        containers['platter'] = object_row('platter', choose('platter'),
            [(.34 if task == 'T04' else 0.)+prng.uniform(-.015, .015), .30+prng.uniform(-.01, .01), z+.0005],
            prng.uniform(-.10, .10), target=task == 'T07')
    instance['objects'].extend(containers.values())
    if task in ('T05', 'T06', 'T07'):
        kind = 'shelf' if task == 'T05' else 'cabinet'
        facility = object_row(kind, choose(kind), [-1.30, 0., z+.20 if task == 'T05' else z], target=False)
        instance['facilities'].append(facility)
        add_region('delivery', [prng.uniform(-.20, .20), prng.uniform(-.16, .12), z], [.13, .12], 'worktable')
    if task == 'T07':
        instance['regions'] = []
        for name, x in [('seat_left', 1.08), ('seat_right', 1.72), ('shared', 1.40)]:
            add_region(name, [x+prng.uniform(-.02, .02), -.12 if name != 'shared' else .30, z],
                       [.13, .12] if name != 'shared' else [.24, .15], 'destination_table')

    for kind, plural in [('cup', 'cups'), ('fruit', 'fruits'), ('bottle', 'bottles'), ('distractor', 'distractors')]:
        for index in range(counts[plural]):
            a, name = choose(kind), f'{kind}_{index+1}'
            support = ('shelf' if task == 'T05' else 'cabinet') if kind in ('cup', 'bottle') and task in ('T05', 'T06', 'T07') else 'worktable'
            if task == 'T07' and kind == 'fruit':
                support = 'platter'
            placed = None
            for attempt in range(64):
                yaw = prng.uniform(-math.pi, math.pi)
                if support == 'platter':
                    local = np.array([(-.065 if index == 0 else .065)+prng.uniform(-.01, .01), prng.uniform(-.012, .012),
                                      containers['platter']['asset']['floor_m']+.0005])
                    from .diversity_predicates import rotation
                    xyz = np.asarray(containers['platter']['position_m'])+rotation(containers['platter']['quaternion_wxyz']) @ local
                elif support in ('cabinet', 'shelf'):
                    facility = instance['facilities'][0]
                    xyz = [facility['position_m'][0]+prng.uniform(-.16, .16), prng.uniform(-.10, .10), facility['position_m'][2]+.0005]
                else:
                    xyz = [prng.uniform(-.48, .48), prng.uniform(-.23, .12), z+.0005]
                item = object_row(name, a, xyz, yaw, support, kind != 'distractor')
                valid = collision_free(item, instance['objects'])
                instance['sampling']['attempts'].append(dict(object=name, attempt=attempt,
                    asset=a['id'], position_m=list(xyz), quaternion_wxyz=item['quaternion_wxyz'],
                    accepted=valid, rejection=None if valid else 'conservative_initial_footprints_overlap'))
                if valid:
                    placed = item
                    break
            if placed is None:
                instance['sampling']['generation_rejection'] = 'pose_budget_exhausted:'+name
                return instance
            instance['objects'].append(placed)

    targets = [x for x in instance['objects'] if x['is_target']]
    for obj in targets:
        kind, name = obj['asset']['kind'], obj['name']
        if kind == 'cup' and task == 'T07':
            continue
        if kind in ('cup', 'fruit') and task in ('T01', 'T02', 'T03', 'T04', 'T07'):
            target = 'tray' if kind == 'cup' else 'platter'
            instance['goals'].append(dict(predicate='SupportedIn', object=name, target=target))
        elif task == 'T07' and kind == 'platter':
            instance['goals'].append(dict(predicate='OnRegion', object=name, target='shared'))
        else:
            instance['goals'].append(dict(predicate='OnRegion', object=name, target='delivery'))
    if task in ('T06', 'T07'):
        instance['goals'].append(dict(predicate='Closed', object='cabinet'))
    if task == 'T07':
        instance['goals'].append(dict(predicate='DistinctSeats', objects=['cup_1', 'cup_2'], targets=['seat_left', 'seat_right']))
        instance['process_constraints'] = [dict(predicate='RetainedIn', object=x['name'], target='platter')
                                           for x in targets if x['asset']['kind'] == 'fruit']
    witness = []
    try:
        for name, container in containers.items():
            relevant = [x for x in targets if x['asset']['kind'] == ('cup' if name == 'tray' else 'fruit')]
            witness.extend(pack(container, relevant))
    except ValueError as error:
        instance['sampling']['generation_rejection'] = str(error)
    instance['static_capacity_witness'] = dict(placements=witness, robot_solution=False,
        meaning='conservative non-overlapping final object placements; no path or grasp claim')
    instance['initial_predicates'] = ['AllTargetsPresent', 'OnDeclaredSupport', 'NoInitialInterpenetration',
        'InitialObjectsStable', 'GoalNotAlreadySatisfied']+(['CabinetClosed'] if task in ('T06', 'T07') else [])
    geometry_errors = geometry_rejections(instance)
    if geometry_errors:
        instance['sampling']['generation_rejection'] = geometry_errors
    return instance


def build_scene(instance, path, native=False):
    if native:
        if not instance['readiness']['native_G1_scene']:
            raise ValueError('No actual-room integration for this task')
        root = ET.parse(SOURCE).getroot()
        for node in root.iter():
            if node.get('file'):
                node.set('file', os.path.relpath((SOURCE.parent/node.get('file')).resolve(), path.parent))
        world = root.find('worldbody')
        for body in list(world.findall('body')):
            if body.get('name', '').startswith('task_cup'):
                world.remove(body)
    else:
        root = ET.Element('mujoco', model='T0_asset_qualification_'+instance['id'])
        ET.SubElement(root, 'compiler', angle='radian')
        ET.SubElement(root, 'option', timestep='.002', integrator='implicitfast', gravity='0 0 -9.81')
        ET.SubElement(root, 'visual')
        ET.SubElement(root.find('visual'), 'global', offwidth='960', offheight='640')
        world = ET.SubElement(root, 'worldbody')
        geom(world, 'ground', 'plane', [4, 2, .1], [0, 0, 0], rgba='.18 .20 .23 1')
        z = read(REFERENCE/'runtime_context.json')['table_height_m']
        for name, x in [('worktable', 0.)]+([('destination_table', 1.4)] if instance['task'] == 'T07' else []):
            table = ET.SubElement(world, 'body', name=name, pos=values([x, 0, z]))
            geom(table, name+'_surface', 'box', [.66, .46, .025], [0, 0, -.025], rgba='.55 .55 .50 1')
        ET.SubElement(world, 'light', pos='0 -1 4', dir='0 0 -1', diffuse='.8 .8 .8')
    for item in instance['facilities']:
        add_facility(world, item)
    for item in instance['objects']:
        body = add_body(world, item)
        if item['asset']['id'] == 'robosuite_bottle':
            add_vendor_bottle(root, body, item, path.parent)
        if native:
            for node in body.findall('geom'):
                if node.get('contype', '1') != '0':
                    node.set('contype', '4')
                    node.set('conaffinity', '15')
    for region in instance['regions']:
        # Targets are visual annotations with no collision or invented physical support.
        ET.SubElement(world, 'site', name=region['name'], type='box',
                      size=values(region['half_xy_m']+[.0003]), pos=values(region['position_m']),
                      rgba='.1 .9 .2 .35')
    ET.indent(root)
    with path.open('xb') as stream:
        ET.ElementTree(root).write(stream, encoding='utf-8', xml_declaration=True)
    return mujoco.MjModel.from_xml_path(str(path))


def qualify(instance, model):
    """2 s settling is initial-state qualification, never a task attempt."""
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    sampled_qpos, sampled_qvel = data.qpos.copy().tolist(), data.qvel.copy().tolist()
    first = snapshot(model, data, instance)
    frames = []
    for step in range(1000):
        mujoco.mj_step(model, data)
        if (step+1) % 25 == 0:
            frames.append(snapshot(model, data, instance))
    failures = []
    if first['penetrations']:
        failures.append('initial_penetration')
    for item in instance['objects']:
        name = item['name']
        # Each object needs its declared support, not just any upward force.
        support = item['initial_support']
        for frame in frames[-21:]:
            state = frame['objects'][name]
            supported = (relation(instance, frame, name, support, True) if support in ('platter', 'tray') else
                         state['upward_support_N'].get(support, 0.) >= .25*item['asset']['mass_kg']*9.81)
            if not supported:
                failures.append('initial_support:'+name)
                break
            if state['linear_speed_m_s'] > .02 or state['angular_speed_rad_s'] > .2:
                failures.append('initial_unstable:'+name)
                break
    if frames[-1]['penetrations']:
        failures.append('settled_penetration')
    if frame_predicates(instance, frames[-1]):
        failures.append('goal_already_satisfied')
    for name, joint in frames[-1]['joints'].items():
        if abs(joint['position_rad']) > LIMITS['door_closed_rad']:
            failures.append('initial_door_not_closed:'+name)
    report = evaluate_trace(instance, frames)
    return dict(valid_initial_fixture=not failures, rejection_reasons=failures,
                sampled_qpos=sampled_qpos, sampled_qvel=sampled_qvel,
                settled_qpos=data.qpos.tolist(), settled_qvel=data.qvel.tolist(),
                initial_snapshot=first, settled_snapshot=frames[-1], settle_s=float(data.time),
                independent_initial_check=True, goal_check=report,
                robot_task_attempts=0, gateway_requests=0, low_level_policy_calls=0)


def initialize(output, seeds, tasks=tuple(TASKS), variation='joint', native=True):
    output = Path(output)
    if not output.is_absolute():
        output = ROOT/output
    output.resolve().relative_to(ROOT)
    output.mkdir(parents=True, exist_ok=False)
    source_files = [Path(__file__), Path(__file__).with_name('diversity_assets.py'),
                    Path(__file__).with_name('diversity_predicates.py')]
    source_files += [ROOT/'grasp_optimization/episodes/final_reference_1000/runtime_context.json',
                     ROOT/'grasp_optimization/scenes/pantry/p01_zones_v01/candidates/P01_native_v01_practice_1000.json']
    if native:
        source_files.append(SOURCE)
    # Register the complete schedule before sampling or simulating anything.
    write_new(output/'registration.json', dict(date='2026-10-26', boundary='simulation',
        status='registered_before_sampling', tasks=list(tasks), seeds=list(seeds), variation=variation,
        version=VERSION, sources={relative(p): sha(p) for p in source_files},
        runtime=dict(python=sys.version, mujoco=mujoco.__version__, numpy=np.__version__),
        stages=['sample', 'geometric_rejection', 'fixture_initial_physics', 'optional_native_G1_compile'],
        max_robot_task_attempts=0, max_gateway_requests=0, no_outcome_based_resampling=True,
        split='development_only', stable_window_s=1, predicate_limits=LIMITS))
    frozen = output/'frozen_sources'
    frozen.mkdir(exist_ok=False)
    for path in source_files[:3]:
        with (frozen/path.name).open('xb') as stream:
            stream.write(path.read_bytes())
    write_new(output/'assets.json', catalog())
    write_new(output/'templates.json', TASKS)
    results, instances = [], []
    native_tasks = set()
    for task in tasks:
        for seed in seeds:
            instance = sample(task, seed, variation)
            folder = output/instance['id']
            folder.mkdir(exist_ok=False)
            write_new(folder/'instance.json', instance)
            instances.append(instance)
            report = dict(id=instance['id'], task=task, seed=seed, geometry_accepted=False,
                          fixture_valid=False, native_G1_compiled=False, task_executed=False)
            rejection = instance['sampling'].get('generation_rejection')
            if rejection:
                report['generation_rejection'] = rejection
            else:
                report['geometry_accepted'] = True
                try:
                    model = build_scene(instance, folder/'qualification.xml')
                    qualification = qualify(instance, model)
                    write_new(folder/'qualification.json', qualification)
                    report['fixture_valid'] = qualification['valid_initial_fixture']
                    report['rejection_reasons'] = qualification['rejection_reasons']
                    report['fixture_xml_sha256'] = sha(folder/'qualification.xml')
                    del model
                    if native and task not in native_tasks and instance['readiness']['native_G1_scene']:
                        native_model = build_scene(instance, folder/'pantry_G1.xml', native=True)
                        # This compile checks bindings; it does not step or qualify G1 dynamics.
                        report['native_G1_compiled'] = True
                        report['native_dimensions'] = dict(nq=native_model.nq, nv=native_model.nv, ngeom=native_model.ngeom)
                        report['native_xml_sha256'] = sha(folder/'pantry_G1.xml')
                        native_tasks.add(task)
                        del native_model
                except Exception as error:
                    report['qualification_error'] = f'{type(error).__name__}: {error}'
            write_new(folder/'result.json', report)
            results.append(report)
            print(json.dumps(report, ensure_ascii=False), flush=True)
    write_new(output/'instances.json', instances)
    diversity = {}
    for task in tasks:
        rows = [x for x in instances if x['task'] == task]
        outcomes = [x for x in results if x['task'] == task]
        by_kind = {}
        for item in [i for row in rows for i in row['objects']+row['facilities']]:
            by_kind.setdefault(item['asset']['kind'], set()).add(item['asset']['id'])
        diversity[task] = dict(scheduled=len(rows), geometry_accepted=sum(x['geometry_accepted'] for x in outcomes),
            valid_initial_fixtures=sum(x['fixture_valid'] for x in outcomes),
            native_G1_compiled=sum(x['native_G1_compiled'] for x in outcomes),
            distinct_assets={kind:sorted(ids) for kind, ids in by_kind.items()},
            distinct_asset_assignments=len({tuple(i['asset']['id'] for i in row['objects']+row['facilities']) for row in rows}),
            distinct_asset_combinations=len({tuple(sorted((i['asset']['kind'], i['asset']['id'], i['is_target'])
                                                         for i in row['objects']+row['facilities'])) for row in rows}),
            unique_sampled_initial_states=len({hashlib.sha256(json.dumps(row['objects'], sort_keys=True).encode()).hexdigest() for row in rows}),
            rejected_pose_candidates=sum(not a['accepted'] for row in rows for a in row['sampling']['attempts']))
        positions = [x['position_m'] for row in rows for x in row['objects']
                     if x['asset']['kind'] in ('cup', 'fruit', 'bottle')]
        diversity[task]['sampled_object_xy_range_m'] = [np.min(np.asarray(positions)[:, :2], axis=0).tolist(),
                                                       np.max(np.asarray(positions)[:, :2], axis=0).tolist()]
    summary = dict(date='2026-10-26', status='sampling_and_initial_qualification_executed', boundary='simulation',
        scheduled=len(results), generated_task_templates=len(tasks), assets_in_catalog=len(catalog()),
        geometric_accepted=sum(x['geometry_accepted'] for x in results),
        valid_initial_fixtures=sum(x['fixture_valid'] for x in results),
        robot_task_attempts=0, robot_success_rate=None, reference_solution_coverage=None,
        formal_skill_promotions=0, memory_updates=0, diversity=diversity, results=results,
        limitations=['all development samples; no unseen test split',
                     'fixture checks exclude G1 reachability, visibility and swept-path validity',
                     'T05–T07 facilities are synthetic qualification fixtures, not connected HK rooms',
                     'native G1 scenes compiled only; existing tools need new-asset perception and contact qualification'])
    write_new(output/'results.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--seed-start', type=int, default=31000)
    parser.add_argument('--per-task', type=int, default=10)
    parser.add_argument('--tasks', nargs='+', choices=TASKS, default=list(TASKS))
    parser.add_argument('--variation', choices=['joint', 'position', 'asset'], default='joint')
    parser.add_argument('--no-native', action='store_true', help='Skip the four native G1 scene exemplars')
    args = parser.parse_args()
    if args.per_task < 1 or args.seed_start < 0 or len(args.tasks) != len(set(args.tasks)):
        parser.error('Positive sample count, nonnegative seeds and distinct tasks required')
    summary = initialize(args.output, range(args.seed_start, args.seed_start+args.per_task),
                         args.tasks, args.variation, not args.no_native)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('results', 'diversity')}, ensure_ascii=False))
