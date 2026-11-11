"""Freeze recipes and actual initial states before ROS skill-cycle execution."""
import argparse
from copy import deepcopy
from pathlib import Path
import random
import shutil
from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new
from experiments.t0_agent_v1.runtime import PilotRobot
from experiments.cordis_t01.prepare_variation import case, quaternion, CUPS, TRAYS
from experiments.cordis_t01.qualify_guard_initials import qualify
from .runtime_env import NATIVE, INTERFACES

HERE = Path(__file__).parent
VARIATION = ROOT / 'experiments/cordis_t01/runs/t01_variation_20261028_001'
COMPARISON = ROOT / 'experiments/cordis_t01/runs/handoff_guard_comparison_20261028_001'
PREVIOUS_FROZEN = ROOT / 'experiments/t01_revision/runs/frozen_gain050_20261029_001'
GAINS = (.25, .5, .75)


def generated(group, seed, tray):
    item = case(group, seed, CUPS[0], tray)
    rng = random.Random(f'ros-skill-cycle-20261029:{group}:{seed}')
    cup, container = item['instance']['cups'][0], item['instance']['tray']
    cup['cup_table_xy_m'] = [.3031511632603484 + (rng.uniform(-.005, .005) if group != 'orientation' else 0.),
                             .24447098780563076 + (rng.uniform(-.005, .005) if group != 'orientation' else 0.)]
    container['xy_m'] = [.22378 + rng.uniform(-.002, .002), .385 + rng.uniform(-.002, .002)]
    container['yaw_rad'] = rng.uniform(-.03, .03) if group != 'position' else 0.
    container['quaternion_wxyz'] = quaternion(container['yaw_rad'])
    item['instance']['cup_table_xy_m'] = cup['cup_table_xy_m']
    item['instance']['sampling'].update(namespace=f'ros-skill-cycle:{seed}', held_out=True,
        position_range_m=.005, tray_position_range_m=.002, tray_yaw_limit_rad=.03,
        no_outcome_resampling=True, actual_pose_saved=True)
    return item


def sources():
    paths = ['execution.py', 'public_check.py', 'server.py', 'client.py', 'runtime_env.py', 'ExecuteSkill.action']
    bindings = {relative(HERE / p): sha(HERE / p) for p in paths}
    previous = read(VARIATION / 'registration.json')
    bindings.update(previous['source_sha256'])
    bindings.update({relative(p):sha(p) for p in (ROOT / 'experiments/cordis_t01').glob('*.py')})
    bindings.update({relative(p):sha(p) for p in (ROOT / 'experiments/t01_revision').glob('*.py')})
    for path in [NATIVE / 'lib/libthesis_kernel.so', INTERFACES / 'build.json']:
        bindings[relative(path)] = sha(path)
    for path in list((INTERFACES / 'lib').glob('*.so')) + list((INTERFACES / 'python').rglob('*.so')):
        bindings[relative(path)] = sha(path)
    return bindings


def bundle(output, policy, version, bindings):
    output.mkdir(parents=True, exist_ok=False)
    implementation = output / 'implementation'
    implementation.mkdir()
    frozen = dict(bindings)
    for name in ['execution.py', 'public_check.py']:
        shutil.copyfile(HERE / name, implementation / name)
        frozen[relative(implementation / name)] = sha(implementation / name)
    write_new(output / 'policy.json', policy)
    frozen[relative(output / 'policy.json')] = sha(output / 'policy.json')
    manifest = dict(skill_id='T01_ros_cup_to_tray', skill_version=version, status='frozen_executable_recipe',
        policy=policy, bindings=frozen, boundary='simulation',
        contract=dict(target='one visible compatible white cup to calibrated marked tray',
            cup_radius_prior_m=.041, compatible_trays=TRAYS, entry_visible_markers=4,
            holding='original anonymous thumb and other finger load gates',
            postcondition='public visual proxy; independent private physics verdict recorded separately',
            failure='abort, reject or unverified; never automatically retry',
            model_requests=0, weight_updates=0))
    write_new(output / 'manifest.json', manifest)
    return manifest


def snapshots(output, cases, models):
    inputs = {}
    for c in cases:
        if c.get('initial_source'):
            inputs[c['initial_source']] = sha(ROOT / c['initial_source'])
            continue
        folder = output / 'initial_states' / c['id']
        folder.mkdir(parents=True, exist_ok=False)
        robot = PilotRobot(folder, c['instance'], scene_path=ROOT / models[c['model_key']]['path'])
        robot.renderer.close()
        c['initial_source'] = relative(folder / 'initial_state.npz')
        inputs[c['initial_source']] = sha(ROOT / c['initial_source'])
        write_new(folder / 'snapshot_kind.json', dict(physics_steps=0, private_initialization_only=True))
    inputs.update({r['path']: r['sha256'] for r in models.values()})
    return inputs


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'protocol.json', dict(date='2026-10-29', status='registered_before_execution',
        boundary='simulation', task='T01', candidate_gains=GAINS,
        maximum_core_physical_episodes=46, maximum_development_episodes=16, frozen_pairs=12,
        boundary_requests=6, model_requests=0, weight_updates=0,
        selection='repair >=1 and regressions=0; maximize successes, then minimize low-level commands, then gain',
        public_verifier_scope='conservative RGBD proxy; return UNVERIFIED on insufficient evidence',
        test_results_never_tune_this_version=True, old_sources_and_results_never_overwritten=True,
        authorship='predefined bounded parameter screening; historical gain=.5 already known',
        method_source='https://doi.org/10.48550/arXiv.2609.00065'))
    original = read(VARIATION / 'registration.json')
    known = {c['id']: c for c in original['cases']}
    comparison = {c['id']: c for c in read(COMPARISON / 'registration.json')['cases']}
    cases = []
    for name in ['orientation_280201', 'control_2500']:
        c = deepcopy(known[name])
        c['initial_source'] = relative(VARIATION / 'cases' / name / 'episode/initial_state.npz')
        cases.append(c)
    cases.append(deepcopy(comparison['fresh_480100']))
    cases.append(generated('position', 820000, TRAYS[0]))
    for c in cases:
        c['evaluation_role'] = 'consumed_or_declared_development'
    models = original['models']
    inputs = snapshots(output, cases, models)
    bindings = sources()
    policies = dict(nominal=dict(guard=False, gain=.5))
    policies.update({f'gain{int(gain*100):03d}':dict(guard=True, gain=gain) for gain in GAINS})
    for arm, policy in policies.items():
        bundle(output / 'recipes' / arm, policy, arm, bindings)
    schedule = []
    rng = random.Random('ros-skill-cycle-development-order-20261029')
    for c in cases:
        arms = list(policies)
        rng.shuffle(arms)
        schedule.extend(dict(case_id=c['id'], arm=arm) for arm in arms)
    registration = dict(cases=cases, models=models, input_sha256=inputs, source_sha256=bindings,
        policies=policies, schedule=schedule, phase='development', maximum_physical_episodes=16,
        expected_program=['inspect_scene','grasp_cup','transfer_to_tray','inspect_alignment',
                          'correct_alignment','release_in_tray'], simulation_budget_s=180.)
    write_new(output / 'registration.json', registration)
    qualification = qualify(output)
    write_new(output / 'initial_qualification.json', qualification)
    if not qualification['all_valid']:
        raise ValueError('Invalid initial state retained; no outcome-based replacement')
    write_new(output / 'formation_ready.json', dict(status='ready', cases=4, requested_physical_episodes=16))
    print(dict(prepared=relative(output), cases=4, episodes=16), flush=True)


def prepare_test(output, selected):
    target = output / 'frozen_test'
    target.mkdir(exist_ok=False)
    dev = read(output / 'registration.json')
    cases = [generated(group, seed+i, TRAYS[i % 2]) for group, seed in
             [('position', 830100), ('orientation', 830200), ('joint', 830300)] for i in range(4)]
    for c in cases:
        c['evaluation_role'] = 'new_frozen_within_family_instance'
    write_new(target / 'planned_cases.json', cases)
    inputs = snapshots(target, cases, dev['models'])
    old_initials = {sha(ROOT / c['initial_source']) for c in dev['cases']}
    prior = read(PREVIOUS_FROZEN / 'registration.json')
    old_initials.update(sha(ROOT / c['initial_source']) for c in prior['cases'])
    current = [sha(ROOT / c['initial_source']) for c in cases]
    if len(set(current)) != 12 or old_initials.intersection(current):
        raise ValueError('Frozen test overlaps consumed initials')
    schedule = []
    rng = random.Random('ros-skill-cycle-frozen-pair-order-20261029')
    rng.shuffle(cases)
    for c in cases:
        arms = ['nominal', 'selected']
        rng.shuffle(arms)
        schedule.extend(dict(case_id=c['id'], arm=arm) for arm in arms)
    write_new(target / 'registration.json', dict(cases=cases, models=dev['models'], input_sha256=inputs,
        source_sha256=dev['source_sha256'], schedule=schedule, phase='frozen_test', maximum_physical_episodes=24,
        selected_policy=selected, no_consumed_initial_overlap=True))
    qualified = qualify(target)
    write_new(target / 'initial_qualification.json', qualified)
    if not qualified['all_valid']:
        raise ValueError('Invalid frozen initial retained without replacement')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args().output.resolve())
