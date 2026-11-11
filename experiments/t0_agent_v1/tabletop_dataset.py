"""Frozen training and evaluation tasks for one tabletop pick/place skill family."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import random
import sys

import mujoco
import numpy as np

from .common import ROOT, REFERENCE, read, relative, sha, write_new
from .diversity import SOURCE, build_scene, object_row, pack, quaternion, radius
from .diversity_assets import catalog
from .diversity_predicates import LIMITS, relation, rotation, snapshot
from .tabletop_predicates import VERSION as EVALUATOR_VERSION, evaluate_trace, frame_predicates

VERSION = 'tabletop-dataset-v2'
RANDOM_NAMESPACE = 'tabletop-dataset-v1'
FAMILY = 'tabletop_pick_place'
TEMPLATES = {
    'TP01': dict(label='指定物抓起并稳持', mode='hold', target_kinds=['cup', 'fruit', 'bottle'],
                 initial='一个指定物由桌面承托，另有非目标罐', goal='离开桌面至少10cm，由手承托并稳定1s'),
    'TP02': dict(label='指定物桌面移位', mode='relocate', target_kinds=['cup', 'fruit', 'bottle'],
                 initial='指定物在源位置，目标桌面区未满足', goal='指定物进入目标区，已释放、承托且稳定'),
    'TP03': dict(label='指定杯放入托盘', mode='cup_to_tray', target_kinds=['cup'],
                 initial='一个杯在桌上，托盘为空', goal='杯底完整入盘并实际承托、释放和稳定', maps_to='T01'),
    'TP04': dict(label='指定水果放入果盘', mode='fruit_to_platter', target_kinds=['fruit'],
                 initial='一个刚体水果在桌上，果盘为空', goal='水果完整入盘并实际承托、释放和稳定', maps_to='T03'),
    'TP05': dict(label='同类多物归集', mode='collect', target_kinds=['cup', 'fruit'],
                 initial='三个同类目标物在桌上，目标容器为空', goal='三物全部入同一容器，共同释放稳定', maps_to='T02的桌面扩展'),
    'TP06': dict(label='杯子水果分类收纳', mode='sort', target_kinds=['cup', 'fruit'],
                 initial='2–3杯、1–2水果和一个非目标罐混合摆放', goal='杯入托盘、水果入果盘，全部释放稳定', maps_to='T04'),
    'TP07': dict(label='桌面按位分发', mode='distribute', target_kinds=['cup'],
                 initial='两只空杯均在桌上，两个目标区未满足', goal='两杯分别进入两个不同目标区，允许交换杯的分配'),
    'TP08': dict(label='两个容器之间转移', mode='transfer', target_kinds=['cup', 'fruit'],
                 initial='一个目标物由源容器承托，另一容器为空', goal='目标物由目标容器承托，已释放且稳定'),
}
SPLITS = {
    'train': dict(split='train', asset_partition='train', position_partition='train', default_count=32),
    'test_position': dict(split='test', asset_partition='train', position_partition='test', default_count=8),
    'test_asset': dict(split='test', asset_partition='test', position_partition='train', default_count=4),
    'test_joint': dict(split='test', asset_partition='test', position_partition='test', default_count=4),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def rng(*parts):
    return random.Random(':'.join(map(str, (RANDOM_NAMESPACE, *parts))))


def asset_library():
    """Reserved specimens differ in geometry/mass; their prototype families overlap."""
    rows = {}
    for prototype in catalog().values():
        if prototype['kind'] in ('shelf', 'cabinet'):
            continue
        container = prototype['kind'] in ('tray', 'platter')
        scales = dict(train=[1.04, 1.06, 1.08] if container else [.98, 1., 1.02],
                      test=[1.02, 1.10] if container else [.95, 1.05])
        for partition, factors in scales.items():
            for index, factor in enumerate(factors):
                a = deepcopy(prototype)
                a['prototype_id'] = prototype['id']
                a['id'] = f'{prototype["id"]}__{partition}_{index}'
                a['asset_partition'] = partition
                a['specimen_scale'] = factor
                a['mesh_scale_factor'] = factor if prototype['id'] == 'robosuite_bottle' else None
                for key in ('radius_m', 'height_m', 'footprint_radius_m', 'floor_m', 'rim_m'):
                    if key in a:
                        a[key] *= factor
                for key in ('radii_m', 'half_xy_m'):
                    if key in a:
                        a[key] = [v*factor for v in a[key]]
                if a.get('handle'):
                    a['footprint_radius_m'] = max(a['footprint_radius_m'], a['radius_m']+.031)
                a['mass_kg'] *= factor**3
                a['rgba'] = [min(1., c*(.92+.04*index)) for c in a['rgba'][:3]]+[1.]
                rows[a['id']] = a
    return rows


def position_cells():
    cells = []
    for row, y in enumerate((-.30, -.145, .010)):
        for column, x in enumerate((-.425, -.255, -.085, .085, .255, .425)):
            cells.append(dict(id=f'table_{row}_{column}', frame='table', center_xy_m=[x, y],
                jitter_xy_m=.012, partition='test' if (row+column)%3 == 0 else 'train'))
    for column, x in enumerate((-.080, -.048, -.016, .016, .048, .080)):
        cells.append(dict(id=f'container_{column}', frame='source_container', center_xy_m=[x, 0.],
            jitter_xy_m=.004, partition='test' if column in (0, 3) else 'train'))
    return cells


def schedule(counts=None):
    counts = counts or {key: s['default_count'] for key,s in SPLITS.items()}
    if set(counts) != set(SPLITS) or any(type(n) is not int or n < 1 for n in counts.values()):
        raise ValueError('Positive integer counts required for all four strata')
    rows, train_seed, test_seed = [], 50000, 60000
    for template in TEMPLATES:
        for stratum, config in SPLITS.items():
            for index in range(counts[stratum]):
                seed = train_seed if stratum == 'train' else test_seed
                if stratum == 'train':
                    train_seed += 1
                else:
                    test_seed += 1
                rows.append(dict(id=f'{template}_{stratum}_{index:03}', template=template, stratum=stratum,
                                 index=index, seed=seed, **{k:v for k,v in config.items() if k != 'default_count'}))
    return rows


def overlaps(item, other):
    if item['initial_support'] != other['initial_support']:
        return False
    ac, bc = 'half_xy_m' in item['asset'], 'half_xy_m' in other['asset']
    if ac or bc:
        box, circle = (item, other) if ac else (other, item)
        if ac and bc:
            # A conservative circumscribed circle suffices for the two fixed lanes.
            return math.dist(item['position_m'][:2], other['position_m'][:2]) < radius(item)+radius(other)+.004
        local = rotation(box['quaternion_wxyz']).T @ (np.asarray(circle['position_m'])-box['position_m'])
        distance = np.linalg.norm(np.maximum(np.abs(local[:2])-np.asarray(box['asset']['half_xy_m']), 0.))
        return distance < radius(circle)+.006
    return math.dist(item['position_m'][:2], other['position_m'][:2]) < radius(item)+radius(other)+.006


def make_instance(slot, assets=None):
    assets = assets or asset_library()
    template = TEMPLATES[slot['template']]
    prng = rng(slot['seed'], 'poses')
    z = read(REFERENCE/'runtime_context.json')['table_height_m']
    instance = dict(id=slot['id'], task=slot['template'], template_id=slot['template'],
        seed=slot['seed'], split=slot['split'], stratum=slot['stratum'],
        asset_partition=slot['asset_partition'], position_partition=slot['position_partition'],
        skill_family=FAMILY, label=template['label'], boundary='simulation', scene_id='pantry_tabletop',
        generator_version=VERSION, evaluator_version=EVALUATOR_VERSION,
        objects=[], facilities=[], regions=[], goals=[], process_constraints=[],
        sampling=dict(namespace=VERSION, attempts=[], outcome_filter=False, replacements=0,
                      pose_budget_per_object=96, held_out=slot['split']=='test'),
        readiness=dict(native_G1_scene=True, robot_task_executed=False, reachability='not_checked',
                       perception_and_swept_paths='not_checked', robot_tools_qualified=False),
        robot=dict(stance=read(ROOT/'grasp_optimization/scenes/pantry/p01_zones_v01/candidates/P01_native_v01_practice_1000.json')['robot_stance'],
                   joint_offsets_rad={}, source='grasp_optimization/episodes/final_reference_1000'))

    draws = Counter()

    def choose(kind):
        pool = sorted((a for a in assets.values() if a['kind'] == kind
                       and a['asset_partition'] == slot['asset_partition']), key=lambda a:a['id'])
        rng('asset_order',slot['template'],kind,slot['asset_partition']).shuffle(pool)
        target_cycle = slot['index']//len(template['target_kinds'])
        offset = target_cycle if kind in template['target_kinds'] else slot['index']
        selected = pool[(offset+draws[kind]) % len(pool)]
        draws[kind] += 1
        return deepcopy(selected)

    def container(name, kind, x=0.):
        item = object_row(name, choose(kind), [x+prng.uniform(-.004, .004), .290+prng.uniform(-.004, .004), z+.0005],
                          prng.uniform(-.025, .025), target=False)
        instance['objects'].append(item)
        return item

    def region(name, x):
        instance['regions'].append(dict(name=name, position_m=[x+prng.uniform(-.015, .015),
            .290+prng.uniform(-.010, .010), z], half_xy_m=[.12, .10],
            quaternion_wxyz=quaternion(0), support_body='worktable'))

    mode = template['mode']
    kind = template['target_kinds'][slot['index'] % len(template['target_kinds'])]
    if mode in ('cup_to_tray', 'collect') and kind == 'cup':
        container('tray', 'tray')
    elif mode in ('fruit_to_platter', 'collect'):
        container('platter', 'platter')
    elif mode == 'sort':
        container('tray', 'tray', -.34)
        container('platter', 'platter', .34)
    elif mode == 'transfer':
        support_kind = 'tray' if kind == 'cup' else 'platter'
        container('source_container', support_kind, -.33)
        container('target_container', support_kind, .33)
    elif mode == 'relocate':
        region('delivery', 0.)
    elif mode == 'distribute':
        region('seat_left', -.23)
        region('seat_right', .23)

    kinds = [kind]*(3 if mode == 'collect' else 2 if mode == 'distribute' else 1)
    if mode == 'sort':
        kinds = ['cup']*(2+slot['index']%2)+['fruit']*(1+(slot['index']//2)%2)
    kinds += ['distractor']
    used_cells = set()
    for index, item_kind in enumerate(kinds):
        name = f'{item_kind}_{index+1}'
        a = choose(item_kind)
        support = 'source_container' if mode == 'transfer' and item_kind != 'distractor' else 'worktable'
        frame = 'source_container' if support == 'source_container' else 'table'
        pool = [c for c in position_cells() if c['partition'] == slot['position_partition'] and c['frame'] == frame]
        placed = None
        for attempt in range(96):
            available = [c for c in pool if c['id'] not in used_cells]
            if not available:
                break
            cell = prng.choice(available)
            xy = [c+prng.uniform(-cell['jitter_xy_m'], cell['jitter_xy_m']) for c in cell['center_xy_m']]
            yaw = prng.uniform(-math.pi, math.pi)
            if support == 'source_container':
                parent = next(x for x in instance['objects'] if x['name'] == support)
                xyz = np.asarray(parent['position_m'])+rotation(parent['quaternion_wxyz']) @ [*xy, parent['asset']['floor_m']+.0005]
            else:
                xyz = [*xy, z+.0005]
            item = object_row(name, a, xyz, yaw, support, item_kind != 'distractor')
            accepted = all(not overlaps(item, other) for other in instance['objects'])
            instance['sampling']['attempts'].append(dict(object=name, cell=cell['id'], attempt=attempt,
                position_m=list(xyz), quaternion_wxyz=item['quaternion_wxyz'], accepted=accepted,
                rejection=None if accepted else 'conservative_footprint_overlap'))
            if accepted:
                item.update(position_cell=cell['id'], local_source_xy_m=xy)
                instance['objects'].append(item)
                used_cells.add(cell['id'])
                placed = item
                break
        if placed is None:
            instance['sampling']['generation_rejection'] = 'pose_budget_exhausted:'+name
            return instance

    targets = [x for x in instance['objects'] if x['is_target']]
    for item in targets:
        name, k = item['name'], item['asset']['kind']
        if mode == 'hold':
            instance['goals'].append(dict(predicate='HeldLifted', object=name,
                initial_bottom_z_m=item['position_m'][2], minimum_lift_m=.10))
        elif mode == 'relocate':
            instance['goals'].append(dict(predicate='OnRegion', object=name, target='delivery'))
        elif mode == 'distribute':
            pass
        else:
            dest = 'target_container' if mode == 'transfer' else 'tray' if k == 'cup' else 'platter'
            instance['goals'].append(dict(predicate='SupportedIn', object=name, target=dest))
    if mode == 'distribute':
        instance['goals'] = [dict(predicate='DistinctSeats', objects=[x['name'] for x in targets],
                                 targets=['seat_left', 'seat_right'])]
    witnesses = []
    try:
        for item in instance['objects']:
            if item['asset']['kind'] in ('tray', 'platter'):
                related = [x for x in targets if any(g.get('object') == x['name'] and g.get('target') == item['name'] for g in instance['goals'])
                           or x['initial_support'] == item['name']]
                witnesses.extend(pack(item, related))
    except ValueError as error:
        instance['sampling']['generation_rejection'] = str(error)
    # Targets and small objects must remain within the table's complete support.
    for item in instance['objects']:
        if item['initial_support'] != 'worktable':
            continue
        a = item['asset']
        extent = (np.abs(rotation(item['quaternion_wxyz'])[:2,:2]) @ a['half_xy_m']
                  if 'half_xy_m' in a else np.array([radius(item)]*2))
        if np.any(np.abs(item['position_m'][:2])+extent+.002 > [.66, .46]):
            instance['sampling']['generation_rejection'] = 'outside_table:'+item['name']
    instance['static_capacity_witness'] = dict(placements=witnesses, robot_solution=False)
    instance['counts'] = dict(Counter(x['asset']['kind'] for x in instance['objects']))
    # Group identity ignores continuous jitter. Whole groups must stay in one split.
    instance['group_id'] = digest(dict(template=slot['template'],
        objects=sorted((x['name'], x['asset']['id'], x.get('position_cell')) for x in instance['objects'])))
    instance['physical_fingerprint'] = digest(dict(objects=instance['objects'], regions=instance['regions'], goals=instance['goals']))
    instance['initial_predicates'] = ['OnDeclaredSupport', 'NoInitialInterpenetration',
                                    'StableFor1s', 'GoalNotAlreadySatisfied']
    instance['skill_contract'] = dict(family=FAMILY, candidate_generated=False,
        arguments=['object_role', 'source_support', 'target_role_or_region', 'terminal_mode'],
        terminal_mode='held' if mode == 'hold' else 'released',
        multi_object_semantics='repeat a shared skill by role; no per-template executable program provided')
    return instance


def adapt_vendor_meshes(path, instance):
    """Apply specimen scaling in a local generated XML, never in upstream files."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(path)
    root = tree.getroot()
    changed = False
    for item in instance['objects']:
        a = item['asset']
        if a.get('prototype_id') != 'robosuite_bottle':
            continue
        # diversity.build_scene recognises the exact upstream ID.
        # Specimen IDs were temporarily mapped during scene generation below.
        prefix = item['name']+'_vendor_'
        for mesh in root.findall('./asset/mesh'):
            if mesh.get('name', '').startswith(prefix):
                mesh.set('scale', ' '.join([str(a['specimen_scale'])]*3))
        body = root.find(f"./worldbody/body[@name='{item['name']}']")
        for node in body.findall('geom'):
            if node.get('name', '').startswith(prefix):
                pos = [float(v)*a['specimen_scale'] for v in node.get('pos', '0 0 0').split()]
                node.set('pos', ' '.join(map(str, pos)))
                node.set('rgba',' '.join(map(str,a['rgba'])))
        changed = True
    if changed:
        # Only a newly created, not-yet-qualified build file is amended here.
        tree.write(path, encoding='utf-8', xml_declaration=True)
    return mujoco.MjModel.from_xml_path(str(path))


def compile_scene(instance, path, native=False):
    adapted = deepcopy(instance)
    vendor = False
    for item in adapted['objects']:
        if item['asset'].get('prototype_id') == 'robosuite_bottle':
            if sha(ROOT/item['asset']['source']) != item['asset']['source_sha256']:
                raise ValueError('External asset manifest changed')
            catalog()  # Validate all original upstream files against the manifest.
            item['asset']['id'] = 'robosuite_bottle'
            vendor = True
    model = build_scene(adapted, path, native=native)
    if vendor:
        del model
        model = adapt_vendor_meshes(path, instance)
    return model


def qualify(instance, model):
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    initial_qpos, initial_qvel = data.qpos.tolist(), data.qvel.tolist()
    first = snapshot(model, data, instance)
    frames = []
    for step in range(1000):
        mujoco.mj_step(model, data)
        if (step+1)%25 == 0:
            frames.append(snapshot(model, data, instance))
    reasons = ['initial_penetration'] if first['penetrations'] else []
    by_name = {x['name']:x for x in instance['objects']}
    for item in instance['objects']:
        name, support = item['name'], item['initial_support']
        for frame in frames[-21:]:
            state = frame['objects'][name]
            if support in by_name:
                supported = relation(instance, frame, name, support, True)
            else:
                supported = state['upward_support_N'].get(support, 0.) >= .25*item['asset']['mass_kg']*9.81
            if not supported:
                reasons.append('unsupported:'+name)
                break
            if state['linear_speed_m_s'] > .02 or state['angular_speed_rad_s'] > .2:
                reasons.append('unstable:'+name)
                break
    if frames[-1]['penetrations']:
        reasons.append('settled_penetration')
    if frame_predicates(instance, frames[-1]):
        reasons.append('goal_already_satisfied')
    result = evaluate_trace(instance, frames)
    return dict(valid_initial_fixture=not reasons, rejection_reasons=reasons,
        sampled_qpos=initial_qpos, sampled_qvel=initial_qvel, settled_qpos=data.qpos.tolist(),
        settled_qvel=data.qvel.tolist(), initial_snapshot=first, settled_snapshot=frames[-1],
        settle_s=float(data.time), goal_check=result, robot_task_attempts=0,
        policy_observations=0, gateway_requests=0, expert_demonstrations=0)


def public_task(instance):
    """No initial xyz, asset dimensions, qpos, contacts, witnesses or test keys."""
    roles = [dict(role=x['name'], category=x['asset']['kind'], appearance_rgba=x['asset']['rgba'],
                  target=x['is_target']) for x in instance['objects']]
    goals = [{k:v for k,v in g.items() if k != 'initial_bottom_z_m'} for g in instance['goals']]
    return dict(id=instance['id'], family=FAMILY, template_id=instance['template_id'],
        instruction=TEMPLATES[instance['template_id']]['goal'], roles=roles,
        initial_semantics=TEMPLATES[instance['template_id']]['initial'], goals=goals,
        target_region_names=[r['name'] for r in instance['regions']],
        observation_interface='head RGB-D and proprioception through approved runtime',
        current_status='task_and_initial_state_prepared; no robot attempt or skill generated')


def audit(instances, assets):
    train = [x for x in instances if x['split'] == 'train']
    test = [x for x in instances if x['split'] == 'test']
    cells = {c['id']:c for c in position_cells()}
    asset_ids = lambda rows: {o['asset']['id'] for x in rows for o in x['objects']}
    group_ids = lambda rows: {x['group_id'] for x in rows}
    checks = dict(no_seed_overlap=not ({x['seed'] for x in train}&{x['seed'] for x in test}),
        no_group_overlap=not (group_ids(train)&group_ids(test)),
        no_exact_physical_duplicates=not ({x['physical_fingerprint'] for x in train}&{x['physical_fingerprint'] for x in test}),
        unique_instance_ids=len({x['id'] for x in instances})==len(instances),
        every_template_in_both_splits=all(any(x['template_id']==t for x in train) and any(x['template_id']==t for x in test) for t in TEMPLATES))
    for x in instances:
        if x['sampling'].get('generation_rejection'):
            checks['all_scheduled_instances_generated'] = False
            continue
        for obj in x['objects']:
            if obj['asset'] != assets.get(obj['asset']['id']):
                checks['actual_asset_parameters_match_registry'] = False
            if obj['asset']['asset_partition'] != x['asset_partition']:
                checks['asset_partition_enforced'] = False
            if obj.get('position_cell') and cells[obj['position_cell']]['partition'] != x['position_partition']:
                checks['position_partition_enforced'] = False
    checks.setdefault('all_scheduled_instances_generated', True)
    checks.setdefault('asset_partition_enforced', True)
    checks.setdefault('position_partition_enforced', True)
    checks.setdefault('actual_asset_parameters_match_registry', True)
    checks['heldout_specimens_absent_from_training'] = not (asset_ids(train)&asset_ids([x for x in test if x['asset_partition']=='test']))
    checks['position_tests_use_only_training_asset_ids'] = asset_ids([x for x in test if x['stratum']=='test_position']) <= asset_ids(train)
    # Geometry and mass, not just labels/colours, differ for every held-out specimen.
    train_shapes = {digest({k:v for k,v in a.items() if k in ('kind','radius_m','height_m','half_xy_m','radii_m','mass_kg','floor_m','rim_m')})
                    for a in assets.values() if a['asset_partition']=='train'}
    test_shapes = {digest({k:v for k,v in a.items() if k in ('kind','radius_m','height_m','half_xy_m','radii_m','mass_kg','floor_m','rim_m')})
                   for a in assets.values() if a['asset_partition']=='test'}
    checks['heldout_assets_have_new_physical_parameters'] = not bool(train_shapes&test_shapes)
    return dict(passed=all(checks.values()), checks=checks,
                train_groups=len(group_ids(train)), test_groups=len(group_ids(test)),
                train_asset_ids=sorted(asset_ids(train)), heldout_asset_ids=sorted(asset_ids([x for x in test if x['asset_partition']=='test'])))


def load_training_tasks(dataset):
    dataset = Path(dataset)
    frozen = read(dataset/'freeze_manifest.json')
    if sha(dataset/'train/manifest.json') != frozen['artifacts']['train/manifest.json']:
        raise ValueError('Frozen training manifest changed')
    manifest = read(dataset/'train/manifest.json')
    tasks = []
    by_id = {row['id']:row for row in manifest['instances']}
    order = manifest.get('randomized_instance_order',list(by_id))
    if len(order) != len(by_id) or set(order) != set(by_id):
        raise ValueError('Invalid training schedule')
    for identifier in order:
        row = by_id[identifier]
        path = dataset/row['public_task']
        if not path.resolve().is_relative_to((dataset/'train').resolve()) or sha(path) != row['public_sha256']:
            raise ValueError('Training manifest points outside its split or changed')
        tasks.append(read(path))
    return tasks


def initialize(output, counts=None, native=True):
    output = Path(output)
    if not output.is_absolute():
        output = ROOT/output
    output.resolve().relative_to(ROOT)
    slots, assets = schedule(counts), asset_library()
    output.mkdir(parents=True, exist_ok=False)
    modules = ['tabletop_dataset.py', 'tabletop_predicates.py', 'diversity.py',
               'diversity_assets.py', 'diversity_predicates.py', 'common.py']
    sources = {f'experiments/t0_agent_v1/{name}':sha(Path(__file__).with_name(name)) for name in modules}
    sources.update({relative(SOURCE):sha(SOURCE),
                    relative(REFERENCE/'runtime_context.json'):sha(REFERENCE/'runtime_context.json'),
                    relative(REFERENCE/'initial_state.npz'):sha(REFERENCE/'initial_state.npz')})
    write_new(output/'registration.json', dict(date='2026-10-26', boundary='simulation', version=VERSION,
        status='registered_before_generation', family=FAMILY, random_namespace=RANDOM_NAMESPACE,
        scope='one table; rigid objects; no cupboards or walking',
        templates=TEMPLATES, slots=slots, assets=assets, position_cells=position_cells(),
        predicate_limits=LIMITS, sources=sources,
        runtime=dict(python=sys.version, mujoco=mujoco.__version__, numpy=np.__version__),
        policy_task_attempt_budget=0, frozen_test_policy_feedback_budget=0, replacement_seed_budget=0,
        evaluation_plan='after training freeze one shared Skill/Memory; report each test axis separately',
        sample_size='engineering pilot coverage; no power or population-reliability claim',
        robot_initial_state=dict(path=relative(REFERENCE/'initial_state.npz'),
            sha256=sha(REFERENCE/'initial_state.npz'), copied=False,
            transfer_rule='robot joints restored by name, excluding old task objects; each new object uses its own recorded state'),
        design_workflow_reference='https://doi.org/10.48550/arXiv.2609.00065',
        historical_data='previous 31000-31009 and earlier task runs remain development only'))
    frozen = output/'frozen_sources'
    frozen.mkdir(exist_ok=False)
    for name in modules:
        with (frozen/name).open('xb') as stream:
            stream.write(Path(__file__).with_name(name).read_bytes())
    write_new(output/'templates.json', TEMPLATES)
    write_new(output/'assets.json', assets)
    write_new(output/'position_cells.json', position_cells())
    instances, results = [], []
    manifests = {s:[] for s in ('train','test')}
    for split in manifests:
        (output/split/'instances').mkdir(parents=True, exist_ok=False)
    native_done = set()
    for slot in slots:
        instance = make_instance(slot, assets)
        instances.append(instance)
        folder = output/slot['split']/'instances'/slot['id']
        folder.mkdir(exist_ok=False)
        write_new(folder/'instance.json', instance)
        write_new(folder/'task.json', public_task(instance) if not instance['sampling'].get('generation_rejection') else
                  dict(id=instance['id'], unusable=True, reason=instance['sampling']['generation_rejection']))
        result = dict(id=slot['id'], template=slot['template'], split=slot['split'], stratum=slot['stratum'],
            seed=slot['seed'], group_id=instance.get('group_id'), valid_initial_fixture=False,
            native_G1_compiled=False, robot_task_executed=False)
        if instance['sampling'].get('generation_rejection'):
            result['rejection_reasons'] = [instance['sampling']['generation_rejection']]
        else:
            try:
                model = compile_scene(instance, folder/'qualification.xml')
                qualification = qualify(instance, model)
                write_new(folder/'initial_state.json', qualification)
                result.update(valid_initial_fixture=qualification['valid_initial_fixture'],
                              rejection_reasons=qualification['rejection_reasons'], fixture_xml_sha256=sha(folder/'qualification.xml'))
                del model
                if native and slot['split']=='train' and slot['template'] not in native_done:
                    model = compile_scene(instance, folder/'pantry_G1.xml', native=True)
                    result.update(native_G1_compiled=True, native_xml_sha256=sha(folder/'pantry_G1.xml'))
                    native_done.add(slot['template'])
                    del model
            except Exception as error:
                result['qualification_error'] = f'{type(error).__name__}: {error}'
        write_new(folder/'result.json', result)
        path = lambda p: str(p.relative_to(output))
        manifests[slot['split']].append(dict(id=slot['id'], template_id=slot['template'], stratum=slot['stratum'],
            seed=slot['seed'], group_id=instance.get('group_id'), valid_initial_fixture=result['valid_initial_fixture'],
            public_task=path(folder/'task.json'), public_sha256=sha(folder/'task.json'),
            evaluator_instance=path(folder/'instance.json'), evaluator_sha256=sha(folder/'instance.json'),
            result=path(folder/'result.json'), result_sha256=sha(folder/'result.json')))
        results.append(result)
        if not result['valid_initial_fixture']:
            print(json.dumps(result,ensure_ascii=False),flush=True)
    split_audit = audit(instances, assets)
    write_new(output/'split_audit.json', split_audit)
    for split, rows in manifests.items():
        order = list(range(len(rows)))
        rng('run_order',split).shuffle(order)
        write_new(output/split/'manifest.json', dict(split=split, family=FAMILY, frozen=True,
            permission='practice_and_update_skill_memory' if split=='train' else 'evaluation_after_freeze_only',
            instances=rows, randomized_instance_order=[rows[i]['id'] for i in order]))
    summary = dict(date='2026-10-26', boundary='simulation', version=VERSION,
        status='generated_and_frozen' if split_audit['passed'] and all(r['valid_initial_fixture'] for r in results) else 'contains_rejections',
        task_family=FAMILY, templates=len(TEMPLATES), scheduled=len(slots),
        counts=dict(Counter(s['stratum'] for s in slots)),
        valid_initial_fixtures=dict(Counter(r['stratum'] for r in results if r['valid_initial_fixture'])),
        counts_by_template={t:{s:sum(r['template']==t and r['stratum']==s for r in results)
                              for s in SPLITS} for t in TEMPLATES},
        native_G1_compiled=sum(r['native_G1_compiled'] for r in results), split_audit_passed=split_audit['passed'],
        training_executed=False, shared_skill_generated=False, robot_task_attempts=0,
        agent_test_feedback_requests=0, results=results,
        limitations=['qualification fixture checks; G1 reachability/perception/swept paths still unqualified',
                     'new numeric asset specimens, shared prototype families; no category-heldout claim',
                     'test freeze is a workflow boundary; no operating-system access controls',
                     'agent practice and skill synthesis are future steps; no demonstration trajectories'])
    write_new(output/'results.json', summary)
    write_new(output/'freeze_manifest.json', dict(date='2026-10-26', version=VERSION,
        artifacts={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()},
        policy='verify hashes before use; do not change split/thresholds or learn from test feedback'))
    print(json.dumps({k:v for k,v in summary.items() if k != 'results'},ensure_ascii=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--no-native',action='store_true')
    args = parser.parse_args()
    initialize(args.output,native=not args.no_native)
