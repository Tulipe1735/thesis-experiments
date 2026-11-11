"""Freeze six new within-family initials after development acceptance, before execution."""
import argparse
from copy import deepcopy
import math
from pathlib import Path
import random

from experiments.cordis_t01.prepare_variation import case, quaternion, CUPS, TRAYS
from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new
from experiments.t0_agent_v1.runtime import PilotRobot
from .pipeline import VARIATION, PROGRAM


def prepare(output, development):
    dev_audit = read(development / 'audit.json')
    if dev_audit['status'] != 'passed' or dev_audit['groups']['repaired'] < 1 or dev_audit['groups']['regressed']:
        raise ValueError('Development repair and no-regression acceptance required')
    dev = read(development / 'registration.json')
    output.mkdir(parents=True, exist_ok=False)
    # Ranges and the roster are fixed before creating or qualifying physical initials.
    definitions = [('position', 710100), ('position', 710101),
                   ('orientation', 710200), ('orientation', 710201),
                   ('joint', 710300), ('joint', 710301)]
    cases = []
    for index, (group, seed) in enumerate(definitions):
        c = case(group, seed, CUPS[0], TRAYS[index % 2])
        rng = random.Random(f't01-frozen-20261029:{group}:{seed}')
        item, tray = c['instance']['cups'][0], c['instance']['tray']
        if group in ['position', 'joint']:
            item['cup_table_xy_m'] = [.3031511632603484 + rng.uniform(-.005, .005),
                                      .24447098780563076 + rng.uniform(-.005, .005)]
        tray['xy_m'] = [.22378 + rng.uniform(-.002, .002), .385 + rng.uniform(-.002, .002)]
        tray['yaw_rad'] = rng.uniform(-.03, .03) if group != 'position' else 0.
        tray['quaternion_wxyz'] = quaternion(tray['yaw_rad'])
        c['instance']['cup_table_xy_m'] = item['cup_table_xy_m']
        c['instance']['sampling'].update(namespace=f't01-frozen-20261029:{seed}',
            position_range_m=.005, tray_position_range_m=.002, tray_yaw_limit_rad=.03,
            held_out=True, no_outcome_resampling=True)
        c['evaluation_role'] = 'new_frozen_within_family_instance'
        cases.append(c)
    policies = deepcopy(dev['policies'])
    schedule = []
    rng = random.Random('t01-frozen-paired-run-order-20261029')
    rng.shuffle(cases)
    for c in cases:
        order = list(policies)
        rng.shuffle(order)
        schedule.extend(dict(case_id=c['id'], condition=arm) for arm in order)
    design = dict(date='2026-10-29', boundary='simulation', phase='frozen_within_family_test',
        status='registered_before_initial_qualification_and_policy_execution', cases=cases,
        definitions=definitions, policies=policies, schedule=schedule, replaced_cases=0,
        experimental_unit='actual initial state; two reset executions form one paired unit',
        policy_frozen_from=relative(development / 'registration.json'),
        policy_source_sha256={relative(ROOT / 'experiments/t01_revision/candidate.py'):
                              sha(ROOT / 'experiments/t01_revision/candidate.py')},
        common_budget_sim_s=180., attempts_per_case_per_condition=1,
        claim='small descriptive within-family frozen comparison; no new asset-family or population claim',
        test_outcomes_never_tune_this_version=True, invalid_initials_abort_batch_without_replacement=True,
        runtime='Python/MuJoCo; ROS 2 not claimed', model_requests=0)
    write_new(output / 'design.json', design)
    original = read(VARIATION / 'registration.json')
    inputs = {relative(development / 'registration.json'): sha(development / 'registration.json'),
              relative(development / 'audit.json'): sha(development / 'audit.json')}
    for c in cases:
        folder = output / 'initial_states' / c['id']
        folder.mkdir(parents=True, exist_ok=False)
        robot = PilotRobot(folder, c['instance'], scene_path=ROOT / original['models'][c['model_key']]['path'])
        robot.renderer.close()
        write_new(folder / 'snapshot_kind.json', dict(physics_steps=0, private_initialization_only=True))
        c['initial_source'] = relative(folder / 'initial_state.npz')
        inputs[c['initial_source']] = sha(ROOT / c['initial_source'])
    inputs.update({r['path']: r['sha256'] for r in original['models'].values()})
    sources = dict(dev['source_sha256'])
    sources.update({relative(p): sha(p) for p in Path(__file__).parent.glob('*.py')})
    write_new(output / 'registration.json', dict(**design, models=original['models'],
              input_sha256=inputs, source_sha256=sources, expected_program=PROGRAM,
              simulation_budget_s=180., max_physical_episodes=len(schedule)))
    print(dict(prepared=relative(output), cases=len(cases), physical_episodes=len(schedule)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--development', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output.resolve(), args.development.resolve())
