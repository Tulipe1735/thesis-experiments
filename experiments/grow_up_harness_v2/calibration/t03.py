"""One T03 entry point: prepare, train, evaluate, execute, card, report.

Programs are frozen explicitly with artifacts.py. A run holds only its selected
bundles, generated initial states and execution evidence, never another store.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'experiments/grow_up_harness_v2')]

from harness import artifact_mapping as M, t03_handoff as H, t03_evaluator as E
from harness.library import read_bundle
from calibration import t03_focus
from experiments.t0_agent_v1.common import read, write_new, append_event

PARAMS = {'object_count': 1, 'hold_s': 1.0}
ROLE_STAGE = {'open_ref': 'prepare', 'grasp_ref': 'close_and_test',
    'placement_ref': 'transfer', 'finish_ref': 'release_and_retreat',
    'locate_ref': 'locate', 'locate_runtime': 'locate',
    'approach_ref': 'preflight', 'approach_runtime': 'preflight'}


def view(bundle):
    return M.Views(bundle['family'], bundle['ref'], **bundle['views'])


def validate_bundles(config, bundles):
    from harness import t03_locate_temporal as T, t03_obstacle_approach as O, t03_obstacle_pose as P
    for bundle in bundles.values():
        if bundle['family'] != 'T03' or bundle['evaluator'] != E.VERSION:
            raise ValueError('T03 bundle must name the current authorized evaluator')
        refs = bundle['components']
        if not {'open_ref', 'grasp_ref', 'placement_ref', 'finish_ref'} <= refs.keys():
            raise ValueError('T03 requires open, grasp, placement and finish components')
        if refs.keys() - ROLE_STAGE.keys():
            raise ValueError('unknown T03 component or runtime interface')
        if refs.get('locate_runtime') not in (None, T.VERSION):
            raise ValueError('unsupported locate runtime version')
        if refs.get('approach_runtime') not in (None, O.VERSION, P.VERSION):
            raise ValueError('unsupported approach runtime version')
        if 'approach_ref' in refs and ('locate_ref' not in refs or refs.get('locate_runtime') != T.VERSION
                                      or 'approach_runtime' not in refs):
            raise ValueError('approach leaf requires temporal locate and an explicit approach runtime')
        if ('approach_runtime' in refs and 'approach_ref' not in refs
                or 'locate_runtime' in refs and 'locate_ref' not in refs):
            raise ValueError('runtime interface has no corresponding leaf')
        for key, ref in refs.items():
            if key.endswith('_ref'):
                data = bundle['artifacts'][ref]
                bundle['sources'][data['implementation']['source_sha256']]
    if 'parent' in bundles:
        before, after = bundles['parent']['components'], bundles['candidate']['components']
        changed = {ROLE_STAGE[k] for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
        declared = {f['stage'] for f in config['focuses']}
        if changed - declared:
            raise ValueError('changed stages outside focuses: ' + ', '.join(sorted(changed - declared)))


def log(run, event, **data):
    append_event(run / 'events.jsonl', {'event': event, 'epoch': time.time(), **data})


def events(run):
    return [json.loads(line) for line in (run / 'events.jsonl').read_text().splitlines()]


def start_physical(run, task, arm):
    c, reg = read(run / 'config.json'), read(run / 'registration.json')
    if time.time() - reg['start_epoch'] >= c['caps']['wall_s']:
        raise RuntimeError('ROUND_WALL_BUDGET')
    if sum(e['event'] == 'physical_started' for e in events(run)) >= c['caps']['physical_episodes']:
        raise RuntimeError('PHYSICAL_BUDGET')
    log(run, 'physical_started', task=task, arm=arm)


def prepare(path):
    c = read(path)
    # The existing focus gate remains the only precheck.
    t03_focus.precheck(path, ROOT / c['previous'] if c.get('previous') else None)
    bundles = {key: read_bundle(ROOT / value) for key, value in c['bundles'].items()}
    if 'candidate' not in bundles or bundles.keys() - {'candidate', 'parent'}:
        raise ValueError('bundles requires candidate and optional parent')
    validate_bundles(c, bundles)
    for key in ('negative', 'engineering_positive', 'original_failure', 'treatment'):
        if not c['baselines'].get(key):
            raise ValueError('missing baseline declaration: ' + key)
    for key in ('prediction', 'falsification'):
        if not c.get(key):
            raise ValueError('missing preregistration: ' + key)
    schedules = [set(range(c[f'{split}_seed_start'], c[f'{split}_seed_start'] + c[f'{split}_count']))
                 for split in ('train', 'holdout')]
    if schedules[0] & schedules[1] or set(c['consumed_dev_seeds']) & set.union(*schedules):
        raise ValueError('planned seeds overlap consumed seeds or another split')
    run = ROOT / c['output']
    run.mkdir(parents=True, exist_ok=False)
    write_new(run / 'config.json', c)
    write_new(run / 'artifacts.json', bundles)
    write_new(run / 'registration.json', {'start_epoch': time.time(),
        'bundle_ids': {k: b['bundle_id'] for k, b in bundles.items()}, 'evaluator': E.VERSION,
        'runtime_record': 'declared interface versions; source-tree bytes are not frozen',
        'holdout_gate': 'full training success of this exact candidate before generating holdout'})
    log(run, 'prepared')
    generate(run, 'train')
    return run


def generate(run, split):
    from harness import t03_curriculum as C
    from experiments.t0_agent_v1 import tabletop_dataset as D
    from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant, build_training_scene
    c = read(run / 'config.json')
    # Sampling never filters by a policy outcome. Every rejection is saved.
    consumed = c['consumed_dev_seeds']
    for i in range(c[f'{split}_count']):
        if time.time() - read(run / 'registration.json')['start_epoch'] >= c['caps']['wall_s']:
            raise RuntimeError('ROUND_WALL_BUDGET')
        seed = c[f'{split}_seed_start'] + i
        tid = f'T03_{split}_{seed}'
        folder = run / 'tasks' / split / tid
        folder.mkdir(parents=True, exist_ok=False)
        consumed.append(seed)
        # The run's own config records consumed seeds; the input config stays intact.
        (run / 'config.json').write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n')
        slot = {'id': tid, 'template': 'TP04', 'stratum': split, 'seed': seed,
            'index': c['asset_index_cycle'][i % len(c['asset_index_cycle'])],
            'split': 'train' if split == 'train' else 'test', 'asset_partition': 'train',
            'position_partition': c[f'{split}_position_partition']}
        instance = C.generate(slot, C.cells(c['grid']))
        write_new(folder / 'instance.json', instance)
        row = {'id': tid, 'split': split, 'ready': False,
               'reason': instance['sampling'].get('generation_rejection')}
        if not row['reason']:
            write_new(folder / 'task.json', D.public_task(instance))
            qualified = D.qualify(instance, D.compile_scene(instance, folder / 'qualification.xml'))
            write_new(folder / 'initial_state.json', qualified)
            row.update(ready=qualified['valid_initial_fixture'], reason=qualified['rejection_reasons'])
            model = build_training_scene(instance, folder / 'pantry_G1.xml')
            initial = folder / 'robot_initial'
            initial.mkdir()
            plant = TabletopPlant(instance, folder, model, initial, budget=c['episode_caps']['simulation_s'])
            plant.save(None, None, None, 0)
            row['robot_initial_hash'] = plant.initial_hash
        write_new(folder / 'generation_result.json', row)
        log(run, 'task_generated', **row)


def task_rows(run, split):
    return [read(p) for p in sorted((run / 'tasks' / split).glob('*/generation_result.json'))]


def negative(run, row):
    import mujoco
    from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant
    folder = run / 'tasks' / row['split'] / row['id']
    out = run / row['split'] / row['id'] / 'negative'
    out.mkdir(parents=True, exist_ok=False)
    start_physical(run, row['id'], 'negative')
    instance = read(folder / 'instance.json')
    model = mujoco.MjModel.from_xml_path(str(folder / 'pantry_G1.xml'))
    plant = TabletopPlant(instance, folder, model, out, budget=read(run / 'config.json')['episode_caps']['simulation_s'])
    for _ in range(10):
        if plant.dispatch({'op': 'wait', 'duration': .2})['status'] != 'EXECUTED':
            raise RuntimeError('NEGATIVE_WAIT_REJECTED')
    write_new(out / 'result.json', plant.save(None, {'stage': 'negative_wait'}, None, 0))
    verdict = E.verify(out, instance, model, initial_valid=row['ready'])
    write_new(out / 'verdict.json', verdict)
    if (verdict['verified_task_success'] or verdict['goal_satisfied'] or not verdict['robot_evidence_valid']
            or plant.guard or plant.initial_hash != row['robot_initial_hash']):
        log(run, 'batch_invalid', reason='NEGATIVE_CONTROL_FAILED')
        raise RuntimeError('NEGATIVE_CONTROL_FAILED')
    log(run, 'physical_completed', task=row['id'], arm='negative', success=False)


def physical(run, row, arm, call=None):
    from harness import t03_finish as F, t03_locate_branch as L, t03_locate_temporal as T
    from harness import t03_obstacle_approach as O, t03_obstacle_pose as P
    from experiments.grow_up_v2.isolation.worker import Worker
    from experiments.t0_agent_v1.train_tp01 import body_packet
    if any(e['event'] == 'batch_invalid' for e in events(run)):
        raise RuntimeError('BATCH_INVALID')
    control = run / row['split'] / row['id'] / 'negative/verdict.json'
    if not control.exists() or read(control)['verified_task_success']:
        raise RuntimeError('NEGATIVE_CONTROL_REQUIRED')
    c, bundles = read(run / 'config.json'), read(run / 'artifacts.json')
    validate_bundles(c, bundles)
    bundle = bundles['parent' if arm == 'parent' else 'candidate']
    mapped, refs = view(bundle), bundle['components']
    invocation = call or {'artifact_ref': mapped.ref, 'params': PARAMS}
    # A skill selects this exact implementation; it never regenerates a controller.
    source = mapped.resolve(invocation, PARAMS)
    with Worker(source, body_packet(), wall_timeout=5., cpu_seconds=120) as worker:
        if worker.act({}, PARAMS) != {'action': {'op': 'done'}, 'state': refs}:
            raise ValueError('ROOT_COMPONENT_BINDING_MISMATCH')
        security = worker.security
    log(run, 'root_resolved', task=row['id'], arm=arm, bundle_id=bundle['bundle_id'])
    folder = run / 'tasks' / row['split'] / row['id']
    instance = read(folder / 'instance.json')
    fruit = next(o for o in instance['objects'] if o['is_target'])
    case = {'folder': folder, 'instance': instance, 'ready': row['ready'],
        'public': {'target_category': 'fruit', 'nominal_rgba': fruit['asset']['rgba'],
                   'minimum_lift_m': .1, 'stable_s': 1., 'terminal_mode': 'released'}}
    out = run / row['split'] / row['id'] / arm
    if out.exists():
        raise FileExistsError(out)
    def leaf(key):
        artifact = bundle['artifacts'][refs[key]]
        return bundle['sources'][artifact['implementation']['source_sha256']]
    args = [case, out, *(leaf(k) for k in ('grasp_ref', 'open_ref', 'placement_ref', 'finish_ref')), c['episode_caps']]
    execute = F.execute
    if 'locate_ref' in refs:
        execute = T.execute if refs.get('locate_runtime') == T.VERSION else L.execute
        args.append(leaf('locate_ref'))
    if 'approach_ref' in refs:
        execute = {O.VERSION: O.execute, P.VERSION: P.execute}[refs['approach_runtime']]
        args.append(leaf('approach_ref'))
    start_physical(run, row['id'], arm)
    result = execute(*args)
    write_new(out / 'root_binding.json', {'bundle_id': bundle['bundle_id'], 'artifact_ref': mapped.ref,
        'components': refs, 'invocation': invocation, 'worker_security': security,
        'decision_stages': {'approach': 'preflight'},
        'caller': 'local explicit skill call' if arm == 'skill' else 'direct code'})
    if result['initial_hash'] != row['robot_initial_hash']:
        log(run, 'batch_invalid', reason='INITIAL_STATE_MISMATCH')
        raise RuntimeError('INITIAL_STATE_MISMATCH')
    log(run, 'physical_completed', task=row['id'], arm=arm, success=result['success'])
    if result['error'] and result['error']['type'] in (
            'WorkerError', 'WorkerStartupError', 'WorkerProtocolError', 'WorkerCrashed', 'ValueError', 'PermissionError'):
        log(run, 'batch_invalid', reason='SYSTEM_EXECUTION_FAILURE')
        raise RuntimeError('SYSTEM_EXECUTION_FAILURE:' + str(result['error']))
    return result


def training_success(run):
    """Full independent success, never a numeric gate or primitive success."""
    candidate_id = read(run / 'artifacts.json')['candidate']['bundle_id']
    for path in (run / 'train').glob('*/code/verdict.json'):
        verdict = read(path)
        binding = read(path.parent / 'root_binding.json')
        if (verdict['verified_task_success'] and verdict['evaluator_version'] == E.VERSION
                and binding['bundle_id'] == candidate_id):
            return True
    return False


def batch(run, split):
    if any(e['event'] == 'batch_invalid' for e in events(run)):
        raise RuntimeError('BATCH_INVALID')
    if split == 'holdout':
        if not training_success(run):
            raise RuntimeError('NO_FULL_TRAINING_SUCCESS_HOLDOUT_LOCKED')
        generate(run, 'holdout')
    results = []
    rng = random.Random(read(run / 'config.json')['pair_order_seed'])
    bundles = read(run / 'artifacts.json')
    for row in task_rows(run, split):
        if not row['ready']:
            results.append({'task': row['id'], 'skipped': row['reason']})
            continue
        negative(run, row)
        arms = ['code', 'skill'] + (['parent'] if 'parent' in bundles else [])
        rng.shuffle(arms)
        pair = {'task': row['id'], 'order': arms}
        for arm in arms:
            pair[arm] = physical(run, row, arm)
        base = run / split / row['id']
        # Compare bytes directly. A trajectory comparison needs no hash registry.
        same = ((base / 'code/integration_states.npz').read_bytes()
                == (base / 'skill/integration_states.npz').read_bytes())
        pair['same_trajectory'] = same
        write_new(base / 'pair_audit.json', {'same_trajectory': same})
        if not same:
            log(run, 'batch_invalid', reason='CODE_SKILL_TRAJECTORY_MISMATCH')
            raise RuntimeError('CODE_SKILL_TRAJECTORY_MISMATCH')
        results.append(pair)
        # Checkpoint after each task, including failures, without replacing evidence.
        log(run, 'task_completed', split=split, task=row['id'], result=pair)
    write_new(run / f'{split}_results.json', results)
    return results


def report(run):
    records = events(run)
    counts = {'generated_tasks': sum(e['event'] == 'task_generated' for e in records),
        'physical_episodes_started': sum(e['event'] == 'physical_started' for e in records),
        'physical_episodes_completed': sum(e['event'] == 'physical_completed' for e in records),
        'root_worker_calls': sum(e['event'] == 'root_resolved' for e in records),
        'model_calls': sum(e['event'] == 'model_started' for e in records)}
    print(json.dumps(counts, ensure_ascii=False))
    print(t03_focus.focus_card(run)[1])


def propose(run, role, diagnosis):
    """One bounded model call; retain raw replies and rejected candidates."""
    from harness.agent import check_source
    from harness.llm import Client, LLMReplyError
    from calibration.mapping_holdout import load_key
    c = read(run / 'config.json')
    key = role + '_ref'
    if ROLE_STAGE[key] not in {f['stage'] for f in c['focuses']}:
        raise ValueError('proposal role is outside the registered focuses')
    calls = sum(e['event'] == 'model_started' for e in events(run))
    if calls >= c['caps']['model_calls']:
        raise RuntimeError('MODEL_CALL_BUDGET')
    if time.time() - read(run / 'registration.json')['start_epoch'] >= c['caps']['wall_s']:
        raise RuntimeError('ROUND_WALL_BUDGET')
    bundle = read(run / 'artifacts.json')['candidate']
    artifact = bundle['artifacts'][bundle['components'][key]]
    folder = run / 'proposals' / f'{calls + 1:03}'
    folder.mkdir(parents=True, exist_ok=False)
    packet = {'role': role, 'artifact': artifact, 'diagnosis': read(diagnosis),
              'source': bundle['sources'][artifact['implementation']['source_sha256']]}
    write_new(folder / 'packet.json', packet)
    load_key()
    log(run, 'model_started', role=role)
    try:
        reply, _meta = Client(**c['model']).chat(
            'Repair only this numeric leaf. Preserve its exact I/O interface and native bounds. '
            'Do not rewrite the controller, evaluator or guards. Return exactly source and explanation JSON.',
            json.dumps(packet, ensure_ascii=False), folder / 'model')
        if (type(reply) is not dict or set(reply) != {'source', 'explanation'}
                or not isinstance(reply['source'], str) or not isinstance(reply['explanation'], str)):
            raise ValueError('exact source and explanation required')
        check_source(reply['source'])
    except (ValueError, LLMReplyError) as exc:
        write_new(folder / 'rejection.json', {'error': str(exc), 'physical_episodes': 0})
        raise
    (folder / 'source.py').write_text(reply['source'], encoding='utf-8')
    write_new(folder / 'candidate.json', {'role': role, 'parent': bundle['components'][key],
        'explanation': reply['explanation'], 'status': 'candidate',
        'gate': 'static source check only; no Worker or physical validation'})
    print(folder / 'source.py')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'train', 'evaluate', 'card', 'report'):
        sub.add_parser(name).add_argument('path', type=Path)
    execute = sub.add_parser('execute')
    execute.add_argument('path', type=Path)
    execute.add_argument('--task', required=True)
    execute.add_argument('--split', choices=['train', 'holdout'], required=True)
    execute.add_argument('--arm', choices=['parent', 'code', 'skill'], required=True)
    execute.add_argument('--call', type=Path)
    proposal = sub.add_parser('propose')
    proposal.add_argument('path', type=Path)
    proposal.add_argument('--role', choices=['grasp', 'locate', 'approach', 'placement', 'finish'], required=True)
    proposal.add_argument('--diagnosis', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        print(prepare(args.path))
    elif args.command in ('train', 'evaluate'):
        batch(args.path, 'train' if args.command == 'train' else 'holdout')
        report(args.path)
    elif args.command == 'card':
        print(view(read(args.path / 'artifacts.json')['candidate']).card)
    elif args.command == 'report':
        report(args.path)
    elif args.command == 'propose':
        propose(args.path, args.role, args.diagnosis)
    else:
        if args.split == 'holdout' and not training_success(args.path):
            raise RuntimeError('NO_FULL_TRAINING_SUCCESS_HOLDOUT_LOCKED')
        row = next(r for r in task_rows(args.path, args.split) if r['id'] == args.task)
        if not row['ready']:
            raise ValueError('initial fixture rejected: ' + str(row['reason']))
        control = args.path / args.split / args.task / 'negative/verdict.json'
        if not control.exists():
            negative(args.path, row)
        print(json.dumps(physical(args.path, row, args.arm, read(args.call) if args.call else None), ensure_ascii=False))


if __name__ == '__main__':
    main()
