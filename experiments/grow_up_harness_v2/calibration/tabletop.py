"""One entry point for the T01-T04 flow (docs/research/GROW_UP_ROOT_DOWN_REVISE_20261113.md).

Stage 0 commands: prepare (register a run and either materialize listed frozen
dataset instances or generate near-bucket training instances), kernel (negative
controls plus the fixed engineering tool chain of kernel K_v1 per instance),
report (tool reliability table per template and reach bucket), contacts
(read-only replay of robot contacts at stops and object supports at boundaries) and
checkpoints (a source episode per listed task resumed from each of its checkpoints)
trials (rerun reproduction plus a reach trial from every checkpoint of a run) and vlm
(offline K3 feasibility on the frames locate saw).
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'experiments/grow_up_harness_v2')]

from experiments.t0_agent_v1.common import read, write_new, append_event

TEMPLATES = ('TP01', 'TP03', 'TP04')
OBJECT_RECIPE = 'experiments/t0_agent_v1/tp01_adaptive_dev_20261026_015/registration.json'
# T03 near-side grid: the only table region where the fixed stance has preflight evidence
# (48/54 T03 preflights passed there; 0/15 passed at the stage-0 _002 positions outside it).
NEAR_GRID = {'x_centers_m': [0.28, 0.34, 0.4], 'y_centers_m': [0.25, 0.32, 0.39], 'jitter_m': 0.008}
CONFIGS = ROOT / 'experiments/grow_up_harness_v2/configs'
# Frozen library and datasets that runs read in place and must never write.
FROZEN = (ROOT / 'experiments/t0_agent_v1',)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log(run, event, **data):
    append_event(run / 'events.jsonl', {'event': event, 'epoch': time.time(), **data})


def events(run):
    return [json.loads(line) for line in (run / 'events.jsonl').read_text().splitlines()]


def written_since(roots, epoch):
    """Files under roots modified after epoch: `find ROOT -newer registration.json` as a check."""
    return sorted(str(p) for root in roots for p in Path(root).rglob('*') if p.is_file() and p.stat().st_mtime > epoch)


def generated_seeds(spec):
    return {s + i for s in spec['seed_start'].values() for i in range(spec['count'])}


def seed_reuse(config, configs=CONFIGS):
    """Registered configs whose generate seeds this config shares without naming them in `replicates`.

    A replication lists the reproduced run's output in `replicates` and keeps its generate spec.
    """
    spec, replicates = config['generate'], config.get('replicates', [])
    clashes = {}
    for path in sorted(Path(configs).glob('*.json')):
        other = read(path)
        if not isinstance(other, dict) or other.get('output') == config['output'] or 'seed_start' not in (other.get('generate') or {}):
            continue
        shared = generated_seeds(spec) & generated_seeds(other['generate'])
        if not shared:
            continue
        if other['output'] in replicates and other['generate'] == spec:
            continue
        clashes[other['output']] = sorted(shared)
    return clashes


def kernel_spec(bundle_path):
    from harness import kernel as K
    from harness.library import read_bundle
    bundle = read_bundle(ROOT / bundle_path)
    refs = bundle['components']
    leaves = {name: bundle['artifacts'][refs[key]]['implementation']['source_sha256'] for name, key in K.LEAVES.items()}
    registration = read(ROOT / OBJECT_RECIPE)
    return {'version': K.VERSION, 'tools': K.TOOLS, 'chains': K.CHAINS, 'checks': K.CHECKS,
            'bundle': {'path': bundle_path, 'bundle_id': bundle['bundle_id'], 'components': refs},
            'leaves': leaves, 'sources': {h: bundle['sources'][h] for h in leaves.values()},
            'object_recipe': registration['recipe'],
            'object_recipe_source': {'path': OBJECT_RECIPE, 'sha256': sha(ROOT / OBJECT_RECIPE)},
            'fruit_recipe': 'defaults + frozen t03_adaptive_recipe leaf reply (T03 parent binding)',
            'evaluators': {'TP01': 'tabletop-predicates-v1', 'TP03': 'fruit-bottom v2 (cup relation unchanged)',
                           'TP04': 'fruit-bottom v2'}}


def reach_bucket(instance):
    """Report dimension from the sampled target cell: 'near' lies in NEAR_GRID, 'far' needs a move tool.

    It groups measurements only; it is not a runtime routing condition.
    """
    x, y = next(o for o in instance['objects'] if o['is_target'])['position_m'][:2]
    pad = NEAR_GRID['jitter_m'] + 1e-9
    inside = all(min(c) - pad <= v <= max(c) + pad
                 for v, c in ((x, NEAR_GRID['x_centers_m']), (y, NEAR_GRID['y_centers_m'])))
    return 'near' if inside else 'far'


def generate(run, template, index, seed, spec):
    """Sample one near-bucket training instance with the frozen sampler, as the T03 line does.

    Every rejection is kept as a not-ready row; nothing is resampled.
    """
    from harness import t03_curriculum as C
    from experiments.t0_agent_v1 import tabletop_dataset as D
    from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant, build_training_scene
    task_id = f'{template}_near_{seed}'
    folder = run / 'tasks' / task_id
    folder.mkdir(parents=True, exist_ok=False)
    slot = {'id': task_id, 'template': template, 'stratum': 'train', 'seed': seed, 'index': index,
            'split': 'train', 'asset_partition': spec['asset_partition'],
            'position_partition': spec['position_partition']}
    instance = C.generate(slot, C.cells(spec['grid']))
    write_new(folder / 'instance.json', instance)
    placed = any(o['is_target'] for o in instance['objects'])
    # A rejection before the target is placed still belongs to the bucket it was sampled for.
    row = {'id': task_id, 'template': template, 'seed': seed, 'index': index, 'ready': False,
           'reason': instance['sampling'].get('generation_rejection'), 'source': str(folder.relative_to(ROOT)),
           'bucket': reach_bucket(instance) if placed else 'near'}
    if not row['reason']:
        write_new(folder / 'task.json', D.public_task(instance))
        qualified = D.qualify(instance, D.compile_scene(instance, folder / 'qualification.xml'))
        write_new(folder / 'initial_state.json', qualified)
        row.update(ready=qualified['valid_initial_fixture'], reason=qualified['rejection_reasons'])
        model = build_training_scene(instance, folder / 'pantry_G1.xml')
        initial = folder / 'robot_initial'
        initial.mkdir()
        plant = TabletopPlant(instance, folder, model, initial, budget=1.)
        plant.save(None, None, None, 0)
        row['robot_initial_hash'] = plant.initial_hash
    write_new(folder / 'materialized.json', row)
    log(run, 'task_generated', **row)
    return row


def materialize(run, dataset, instance_id):
    """Hash-check one frozen instance and build its robot scene inside the run.

    qualification.xml and initial_state.json are read in place: their asset paths
    are relative to the dataset folder, so a copy elsewhere would not load.
    """
    from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant, build_training_scene
    manifest = read(dataset / 'train/manifest.json')
    entry = next(e for e in manifest['instances'] if e['id'] == instance_id)
    for key, digest in (('evaluator_instance', 'evaluator_sha256'), ('initial_state', 'initial_state_sha256'),
                        ('qualification_xml', 'qualification_xml_sha256'), ('public_task', 'public_sha256')):
        if sha(dataset / entry[key]) != entry[digest]:
            raise ValueError(f'{instance_id}: {key} hash mismatch')
    source = (dataset / entry['qualification_xml']).resolve().parent
    if (dataset / entry['initial_state']).resolve().parent != source:
        raise ValueError(f'{instance_id}: qualification and initial state are in different folders')
    folder = run / 'tasks' / instance_id
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'instance.json').write_bytes((dataset / entry['evaluator_instance']).read_bytes())
    (folder / 'task.json').write_bytes((dataset / entry['public_task']).read_bytes())
    instance = read(folder / 'instance.json')
    model = build_training_scene(instance, folder / 'pantry_G1.xml')
    initial = folder / 'robot_initial'
    initial.mkdir()
    plant = TabletopPlant(instance, source, model, initial, budget=1.)
    plant.save(None, None, None, 0)
    row = {'id': instance_id, 'template': entry['template_id'], 'ready': bool(entry['valid_initial_fixture']),
           'source': str(source.relative_to(ROOT)), 'robot_initial_hash': plant.initial_hash,
           'bucket': reach_bucket(instance)}
    write_new(folder / 'materialized.json', row)
    return row


def prepare(path):
    c = read(path)
    for key in ('prediction', 'falsification', 'baselines', 'caps', 'episode_caps', 'kernel_bundle'):
        if not c.get(key):
            raise ValueError('missing preregistration: ' + key)
    if bool(c.get('instances')) == bool(c.get('generate')):
        raise ValueError('register exactly one of instances or generate')
    spec = c.get('generate')
    if set(c.get('instances') or spec['seed_start']) - set(TEMPLATES):
        raise ValueError('stage 0 measures only ' + ', '.join(TEMPLATES))
    if spec:
        if spec['grid'] != NEAR_GRID:
            raise ValueError('generate.grid must equal the near bucket grid')
        seeds = [s + i for s in spec['seed_start'].values() for i in range(spec['count'])]
        if len(set(seeds)) != len(seeds):
            raise ValueError('generate seeds overlap between templates')
        clashes = seed_reuse(c)
        if clashes:
            raise ValueError(f'seeds already registered by {sorted(clashes)}: move seed_start to an unused range, or for '
                             'a deliberate replication list that output in replicates and keep its generate spec')
    else:
        dataset = ROOT / c['dataset']
        listed = {e['id']: e['template_id'] for e in read(dataset / 'train/manifest.json')['instances']}
        for template, ids in c['instances'].items():
            if any(listed.get(i) != template for i in ids):
                raise ValueError(f'{template}: instance not in the frozen training manifest')
    run = ROOT / c['output']
    run.mkdir(parents=True, exist_ok=False)
    write_new(run / 'config.json', c)
    write_new(run / 'kernel.json', kernel_spec(c['kernel_bundle']))
    write_new(run / 'registration.json', {'start_epoch': time.time(), 'kernel': read(run / 'kernel.json')['version'],
        'column': 'engineering (fixed tool chain, no agent)', 'test_split_used': False,
        'python': sys.version, 'runtime_record': 'declared interface versions; source-tree bytes are not frozen'})
    log(run, 'prepared')
    if spec:
        rows = [generate(run, template, i, start + i, spec)
                for template, start in spec['seed_start'].items() for i in range(spec['count'])]
    else:
        rows = [materialize(run, dataset, i) for ids in c['instances'].values() for i in ids]
    write_new(run / 'tasks.json', rows)
    log(run, 'materialized', count=len(rows))
    return run


def start_physical(run, task, arm):
    c, reg = read(run / 'config.json'), read(run / 'registration.json')
    if time.time() - reg['start_epoch'] >= c['caps']['wall_s']:
        raise RuntimeError('RUN_WALL_BUDGET')
    if sum(e['event'] == 'physical_started' for e in events(run)) >= c['caps']['physical_episodes']:
        raise RuntimeError('PHYSICAL_BUDGET')
    log(run, 'physical_started', task=task, arm=arm)


def negative(run, row):
    """Same wait control as the T03 line: 2 s of wait must never satisfy the goal."""
    import mujoco
    from harness import kernel as K
    from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant
    folder = run / 'tasks' / row['id']
    out = run / 'episodes' / row['id'] / 'negative'
    start_physical(run, row['id'], 'negative')
    out.mkdir(parents=True, exist_ok=False)
    instance = read(folder / 'instance.json')
    model = mujoco.MjModel.from_xml_path(str(folder / 'pantry_G1.xml'))
    plant = TabletopPlant(instance, ROOT / row['source'], model, out,
                          budget=read(run / 'config.json')['episode_caps']['simulation_s'])
    for _ in range(10):
        if plant.dispatch({'op': 'wait', 'duration': .2})['status'] != 'EXECUTED':
            log(run, 'batch_invalid', reason='NEGATIVE_WAIT_REJECTED', task=row['id'])
            raise RuntimeError('NEGATIVE_WAIT_REJECTED')
    write_new(out / 'result.json', plant.save(None, {'stage': 'negative_wait'}, None, 0))
    verdict = K.verifier(row['template'])(out, instance, model, initial_valid=row['ready'])
    write_new(out / 'verdict.json', verdict)
    if (verdict['verified_task_success'] or verdict['goal_satisfied'] or not verdict['robot_evidence_valid']
            or plant.guard or plant.initial_hash != row['robot_initial_hash']):
        log(run, 'batch_invalid', reason='NEGATIVE_CONTROL_FAILED', task=row['id'])
        raise RuntimeError('NEGATIVE_CONTROL_FAILED')
    log(run, 'physical_completed', task=row['id'], arm='negative', success=False)


def kernel(run):
    """Negative control per template, then the engineering chain on every listed instance.

    A rerun continues after the last completed episode. An episode that started and never
    completed was interrupted; it is never rerun, and the whole batch is void.
    """
    from harness import kernel as K
    rows, spec, c = read(run / 'tasks.json'), read(run / 'kernel.json'), read(run / 'config.json')
    check_kernel_unchanged(spec)
    past = events(run)
    if any(e['event'] == 'batch_invalid' for e in past):
        raise RuntimeError('BATCH_INVALID')
    done = {(e['task'], e['arm']) for e in past if e['event'] == 'physical_completed'}
    interrupted = sorted({(e['task'], e['arm']) for e in past if e['event'] == 'physical_started'} - done)
    if interrupted:
        log(run, 'batch_invalid', reason='INTERRUPTED', episodes=interrupted)
        raise RuntimeError(f'INTERRUPTED: {interrupted} started and never completed, so the batch is void')
    for template in dict.fromkeys(r['template'] for r in rows):
        first = next((r for r in rows if r['template'] == template and r['ready']), None)
        if first and (first['id'], 'negative') not in done:
            negative(run, first)
    for row in rows:
        if (row['id'], 'engineering') in done:
            continue
        if not row['ready']:
            log(run, 'skipped', task=row['id'], reason='initial fixture rejected')
            continue
        folder = run / 'tasks' / row['id']
        case = {'folder': folder, 'source': ROOT / row['source'], 'instance': read(folder / 'instance.json'),
                'ready': row['ready'], 'template': row['template']}
        start_physical(run, row['id'], 'engineering')
        result = K.execute(case, run / 'episodes' / row['id'] / 'engineering', spec, c['episode_caps'])
        if result['initial_hash'] != row['robot_initial_hash']:
            log(run, 'batch_invalid', reason='INITIAL_STATE_MISMATCH', task=row['id'])
            raise RuntimeError('INITIAL_STATE_MISMATCH')
        log(run, 'physical_completed', task=row['id'], arm='engineering', success=result['success'])
        if result['error'] and result['error']['type'] in (
                'WorkerError', 'WorkerStartupError', 'WorkerProtocolError', 'WorkerCrashed', 'ValueError', 'PermissionError',
                'TypeError', 'PicklingError'):
            log(run, 'batch_invalid', reason='SYSTEM_EXECUTION_FAILURE', task=row['id'])
            raise RuntimeError('SYSTEM_EXECUTION_FAILURE:' + str(result['error']))
    written = written_since(FROZEN, read(run / 'registration.json')['start_epoch'])
    if written:
        log(run, 'batch_invalid', reason='FROZEN_SOURCE_WRITTEN', files=written[:20])
        raise RuntimeError('FROZEN_SOURCE_WRITTEN: ' + ', '.join(written[:5]))


def check_kernel_unchanged(spec):
    """The kernel interface recorded at prepare must still be the one that runs."""
    now = json.loads(json.dumps(kernel_spec(spec['bundle']['path'])))
    changed = sorted(k for k in now.keys() | spec.keys() if now.get(k) != spec.get(k))
    if changed:
        raise RuntimeError(f'KERNEL_CHANGED_AFTER_PREPARE: {changed} differ from kernel.json; '
                           'prepare a new run with a new output instead of resuming this one')


def tally(episodes):
    """Per-tool reliability from tools.json rows; pure so it is testable without MuJoCo."""
    table = {}
    for group, tools in episodes:
        for row in tools:
            t = table.setdefault((group, row['tool']), dict(reached=0, ok=0, failed=0, detected=0,
                                                            undetected=0, recoverable=0))
            t['reached'] += 1
            if row['truth_ok']:
                t['ok'] += 1
                continue
            t['failed'] += 1
            t['detected' if not row['visible_ok'] else 'undetected'] += 1
            t['recoverable'] += bool(row.get('recoverable'))
    return table


def report(run):
    rows = read(run / 'tasks.json')
    episodes, summary = [], {}
    for row in rows:
        # Runs prepared before buckets existed get theirs from the saved instance.
        row.setdefault('bucket', reach_bucket(read(run / 'tasks' / row['id'] / 'instance.json')))
        group = f"{row['template']}/{row['bucket']}"
        s = summary.setdefault(group, dict(attempted=0, success=0, listed=0))
        s['listed'] += 1
        folder = run / 'episodes' / row['id'] / 'engineering'
        if not (folder / 'result.json').exists():
            continue
        episodes.append((group, read(folder / 'tools.json')))
        s['attempted'] += 1
        s['success'] += bool(read(folder / 'result.json')['success'])
    table = tally(episodes)
    log_ = events(run)
    invalid = [e['reason'] for e in log_ if e['event'] == 'batch_invalid']
    finished = {e['task'] for e in log_ if e['event'] == 'physical_completed' and e['arm'] == 'engineering'}
    out = {'kernel': read(run / 'kernel.json')['version'], 'column': 'engineering', 'batch_invalid': invalid,
           'tasks': summary,
           'tools': [{'group': k[0], 'tool': k[1], **v} for k, v in sorted(table.items())],
           'definitions': {'group': 'template/reach bucket; near = target sampled inside NEAR_GRID, far = outside',
                           'ok': 'evaluator-side boundary check of kernel.json checks',
                           'detected': 'the tool raised or reported failure itself',
                           'undetected': 'the tool reported success but the boundary check failed',
                           'recoverable': 'final failure left the target at rest, upright and released, no guard'}}
    path = run / 'report.json'
    if not invalid and any(r['ready'] and r['id'] not in finished for r in rows):
        print('PARTIAL: the batch has not ended, so report.json is not written yet')
    elif not path.exists():
        write_new(path, out)
    elif read(path) != json.loads(json.dumps(out)):
        raise FileExistsError(f'{path} holds a different report; finished runs are read-only, so read it '
                              'or measure again in a new run instead of rewriting it')
    if invalid:
        print('BATCH_INVALID ' + ', '.join(invalid) + ': the whole batch is void, no success rates')
        return out
    for group, s in sorted(summary.items()):
        print(f"{group}: {s['success']}/{s['attempted']} full success (listed {s['listed']})")
    print('group     tool     reached ok failed detected undetected recoverable')
    for r in out['tools']:
        print(f"{r['group']:9} {r['tool']:8} {r['reached']:7} {r['ok']:2} {r['failed']:6} "
              f"{r['detected']:8} {r['undetected']:10} {r['recoverable']:11}")
    return out


ROBOT_PARTS = (('left_hand_', 'left_hand'), ('left_wrist', 'left_wrist'), ('left_elbow', 'left_arm'),
               ('left_shoulder', 'left_arm'))


def contact_category(bodies, robot, target, objects):
    """Name a robot contact as '<robot part>-><other side>' from body names; pure for testing."""
    def part(name):
        return next((label for prefix, label in ROBOT_PARTS if name.startswith(prefix)), 'robot_other')

    def other(name):
        if name in robot:
            return 'self'
        if name.startswith(target):
            return 'target'
        return next((kind for prefix, kind in objects.items() if name.startswith(prefix)), 'scene:' + name)
    a, b = bodies
    if a in robot and b in robot:
        return f'{part(a)}->self:{part(b)}'
    mine, theirs = (a, b) if a in robot else (b, a)
    return f'{part(mine)}->{other(theirs)}'


def contacts(run, out):
    """Read-only replay of robot contacts at the end of each grasp-reaching episode.

    Saved integration states are restored into a fresh plant of the same scene and
    checked with the plant's own monitor rule; no action is dispatched and no
    physical budget is used. Contacts are re-solved from the saved post-step state,
    so they can differ from the live monitor by one physics step.
    """
    import mujoco
    import numpy as np
    from experiments.t0_agent_v1.diversity_predicates import snapshot
    from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant, set_left_hand_impedance
    out.mkdir(parents=True, exist_ok=False)
    write_new(out / 'registration.json', {'run': str(run), 'start_epoch': time.time(), 'physical_episodes': 0,
        'method': 'mj_setState + mj_forward + plant.monitor on saved integration and boundary states'})
    spec = mujoco.mjtState.mjSTATE_INTEGRATION
    episodes = []
    for row in read(run / 'tasks.json'):
        folder = run / 'episodes' / row['id'] / 'engineering'
        if not (folder / 'tools.json').exists():
            continue
        tools = read(folder / 'tools.json')
        if not any(t['tool'] in ('grasp', 'place') for t in tools):
            continue
        instance = read(run / 'tasks' / row['id'] / 'instance.json')
        target = next(o for o in instance['objects'] if o['is_target'])
        objects = {o['name']: o['asset']['kind'] for o in instance['objects'] if not o['is_target']}
        model = mujoco.MjModel.from_xml_path(str(run / 'tasks' / row['id'] / 'pantry_G1.xml'))
        scratch = out / 'plants' / row['id']
        scratch.mkdir(parents=True)
        plant = TabletopPlant(instance, ROOT / row['source'], model, scratch, budget=1e9)
        params = read(folder / 'recipe_binding.json')['parameters']
        set_left_hand_impedance(plant.model, params['hand_kp'], params['hand_kd'])
        robot = {model.body(b).name for b in plant.robot_bodies}

        def inspect(state):
            mujoco.mj_setState(model, plant.data, state, spec)
            mujoco.mj_forward(model, plant.data)
            plant.guard = None
            plant.monitor(advance_tracking=False)
            d = plant.diagnostics
            found = [dict(c, category=contact_category(c['bodies'], robot, target['name'], objects))
                     for c in d['forbidden_contacts']]
            return {'time_s': float(plant.data.time), 'faults': d['faults'], 'forbidden_contacts': found,
                    'speed_faults': d['speed_faults']}

        trace = np.load(folder / 'integration_states.npz')
        samples = [inspect(state) for state in trace['integration_state']]
        first = next((s for s in samples if s['faults']), None)
        boundaries = []
        states = np.load(folder / 'boundary_states.npz')['state']
        for tool in tools:
            if tool['tool'] not in ('grasp', 'place'):
                continue
            mujoco.mj_setState(model, plant.data, states[tool['state_index']], spec)
            mujoco.mj_forward(model, plant.data)
            frame = snapshot(model, plant.data, instance, base=plant.base_reference)['objects'][target['name']]
            boundaries.append({'tool': tool['tool'], 'truth_ok': tool['truth_ok'],
                               'upward_support_N': frame['upward_support_N'],
                               'hand_contact_N': frame['hand_contact_N']})
        episodes.append({'id': row['id'], 'template': row['template'], 'target': target['asset'].get('prototype_id'),
                         'error': read(folder / 'result.json')['error'], 'first_fault': first,
                         'terminal': samples[-1], 'boundaries': boundaries,
                         'fault_samples': sum(bool(s['faults']) for s in samples), 'samples': len(samples)})
    written = written_since([run, *FROZEN], read(out / 'registration.json')['start_epoch'])
    if written:
        raise RuntimeError('SOURCE_WRITTEN: the replay wrote into the run it reads: ' + ', '.join(written[:5]))
    write_new(out / 'contacts.json', episodes)
    def line(label, sample):
        found = sample['forbidden_contacts']
        cats = sorted({c['category'] for c in found})
        load = max((c['normal_load_N'] for c in found), default=0.)
        return f"    {label} t={sample['time_s']:.2f}s {sample['faults']} {cats} max {load:.2f} N"
    for e in episodes:
        error = e['error'] and f"{e['error']['stage']}:{e['error']['message'][:40]}"
        print(f"{e['id']:18} {e['target'] or '':22} {error or 'no error'} "
              f"({e['fault_samples']}/{e['samples']} samples with faults)")
        print(line('first fault', e['first_fault']) if e['first_fault'] else '    no fault in saved samples')
        print(line('terminal   ', e['terminal']))
        for b in e['boundaries']:
            support = {k: round(v, 3) for k, v in b['upward_support_N'].items()}
            print(f"    {b['tool']} boundary ok={b['truth_ok']} support={support} hand_contact={b['hand_contact_N']:.2f} N")
    return episodes


def same_episode(a, b):
    """Which records of episode folder b equal those of a; pure file reads.

    Arrays compare dtype, shape and bytes. The verdict's trajectory_sha256 is left out:
    savez zip entries carry write timestamps, so equal arrays give different file bytes.
    """
    import numpy as np
    out = {}
    for name in ('integration_states.npz', 'boundary_states.npz'):
        with np.load(a / name) as x, np.load(b / name) as y:
            out[name] = sorted(x.files) == sorted(y.files) and all(
                (x[k].dtype, x[k].shape) == (y[k].dtype, y[k].shape) and x[k].tobytes() == y[k].tobytes()
                for k in x.files)
    for name in ('actions.json', 'execution.json', 'tools.json'):
        out[name] = read(a / name) == read(b / name)
    va, vb = (read(f / 'verdict.json') for f in (a, b))
    va.pop('trajectory_sha256')
    vb.pop('trajectory_sha256')
    out['verdict.json'] = va == vb
    ra, rb = read(a / 'result.json'), read(b / 'result.json')
    out['result'] = all(ra[k] == rb[k] for k in ('success', 'error', 'commands', 'worker_calls', 'simulation_s'))
    return out


def checkpoints(path):
    """E1 check: a fresh source episode per listed task, then one resume from each of its checkpoints.

    Tasks come from an already prepared run and use its kernel.json. A harness check, not a
    task measurement: nothing here enters a reliability table.
    """
    from harness import kernel as K
    c = read(path)
    for key in ('prediction', 'falsification', 'episode_caps', 'tasks', 'tasks_from'):
        if not c.get(key):
            raise ValueError('missing preregistration: ' + key)
    source = ROOT / c['tasks_from']
    rows = {r['id']: r for r in read(source / 'tasks.json')}
    if any(not rows[t]['ready'] for t in c['tasks']):
        raise ValueError('listed task has a rejected initial fixture')
    run = ROOT / c['output']
    run.mkdir(parents=True, exist_ok=False)
    write_new(run / 'config.json', c)
    spec = read(source / 'kernel.json')
    checked = []
    for task in c['tasks']:
        folder = source / 'tasks' / task
        case = {'folder': folder, 'source': ROOT / rows[task]['source'], 'instance': read(folder / 'instance.json'),
                'ready': True, 'template': rows[task]['template']}
        first = run / task / 'source'
        result = K.execute(case, first, spec, c['episode_caps'])
        print(f"{task} source: success={result['success']} error={result['error'] and result['error']['stage']}")
        for entry in read(first / 'checkpoints.json'):
            name = Path(entry['path']).name.removesuffix('.pkl.gz')
            resumed = K.execute(case, run / task / ('resume_' + name), spec, c['episode_caps'], resume=ROOT / entry['path'])
            same = same_episode(first, run / task / ('resume_' + name))
            checked.append({'task': task, 'checkpoint': entry['path'], 'done': entry['done'], 'next': entry['next'],
                            'source_error': result['error'], 'resumed_error': resumed['error'],
                            'equal': same, 'all_equal': all(same.values())})
            print(f"  {name:34} {'equal' if all(same.values()) else 'DIFFERS ' + str([k for k, v in same.items() if not v])}")
    write_new(run / 'checkpoint_check.json', checked)
    print(f"{sum(r['all_equal'] for r in checked)}/{len(checked)} resumes equal their source episode")
    return checked


def node_rows(template, checkpoints, error, trials):
    """Nodes one episode reached, from its checkpoint list; pure for testing.

    Checkpoint k means nodes 0..k-1 passed. A failed episode failed at the node after its
    last checkpoint; a failure before the first checkpoint (configuration) reaches no node.
    """
    from harness import kernel as K
    if not checkpoints:
        return []
    done = max(c['done'] for c in checkpoints)
    rows = [{'node': k, 'passed': True, 'attribution': None} for k in range(done)]
    if error and done < len(K.stages(template)):
        rows.append({'node': done, 'passed': False, 'attribution': trials.get(done, {}).get('attribution')})
    return rows


def trials(path):
    """E2 check on a checkpointed rerun of a stage-0 run.

    1. Each rerun episode must equal its stage-0 episode (same_episode). 2. A reach trial
    runs from every checkpoint that has a next node; with the K_v1 reference on K_v1
    episodes it must reproduce the source tool boundary (recoverable excluded: it is only
    set on an episode's final row). Every attribution is untestable by construction.
    """
    from harness import kernel as K
    from harness import reach_trial as R
    c = read(path)
    for key in ('prediction', 'falsification', 'episode_caps', 'caps', 'run', 'compare_with'):
        if not c.get(key):
            raise ValueError('missing preregistration: ' + key)
    run, old = ROOT / c['run'], ROOT / c['compare_with']
    out = ROOT / c['output']
    out.mkdir(parents=True, exist_ok=False)
    write_new(out / 'config.json', c)
    spec, rows = read(run / 'kernel.json'), read(run / 'tasks.json')
    previous = {r['id']: r for r in read(old / 'tasks.json')}
    reproduced, records, stages, used = [], [], [], 0
    for row in rows:
        before = previous[row['id']]
        same_task = (read(run / 'tasks' / row['id'] / 'instance.json') == read(old / 'tasks' / row['id'] / 'instance.json')
                     and row.get('robot_initial_hash') == before.get('robot_initial_hash') and row['ready'] == before['ready'])
        folder = run / 'episodes' / row['id'] / 'engineering'
        if not (folder / 'result.json').exists():
            reproduced.append({'task': row['id'], 'same_task': same_task, 'episode': None})
            continue
        same = same_episode(old / 'episodes' / row['id'] / 'engineering', folder)
        reproduced.append({'task': row['id'], 'same_task': same_task, 'episode': same, 'all_equal': all(same.values())})
        case = {'folder': run / 'tasks' / row['id'], 'source': ROOT / row['source'], 'ready': row['ready'],
                'instance': read(run / 'tasks' / row['id'] / 'instance.json'), 'template': row['template']}
        source_tools, by_node = read(folder / 'tools.json'), {}
        for entry in read(folder / 'checkpoints.json'):
            if entry['next'] is None:
                continue
            if used >= c['caps']['trials']:
                raise RuntimeError('TRIAL_BUDGET')
            used += 1
            name = Path(entry['path']).name.removesuffix('.pkl.gz')
            trial = R.reach_trial(case, ROOT / entry['path'], out / 'trials' / row['id'] / name, spec, c['episode_caps'])
            source = next(t for t in source_tools if t['tool'] == trial['tool'])
            trial['equals_source'] = ({k: v for k, v in trial['boundary'].items() if k != 'recoverable'}
                                      == {k: v for k, v in source.items() if k != 'recoverable'})
            trial['attribution'] = R.attribute(trial, executor_is_reference=True, calibration={})
            trial['task'], trial['template'] = row['id'], row['template']
            by_node[trial['node']] = trial
            records.append(trial)
            print(f"{row['id']:18} {trial['label']:28} reachable={trial['reachable']!s:5} "
                  f"{'= source' if trial['equals_source'] else 'DIFFERS from source'}")
        result = read(folder / 'result.json')
        stages += [dict(r, template=row['template']) for r in
                   node_rows(row['template'], read(folder / 'checkpoints.json'), result['error'], by_node)]
    nodes = [{'template': t, 'label': R.node_label(t, k), **v}
             for t in dict.fromkeys(r['template'] for r in rows)
             for k, v in sorted(R.attributed_rates([r for r in stages if r['template'] == t]).items())]
    summary = {'reproduced': reproduced, 'trials': len(records),
               'trials_equal_source': sum(r['equals_source'] for r in records), 'nodes': nodes,
               'definitions': {'raw_p': 'stage completed without raising, engineering column',
                               'attributed_p': 'equal to raw_p here: every K_v1 trial on K_v1 episodes is untestable'}}
    write_new(out / 'reach_trials.json', records)
    write_new(out / 'summary.json', summary)
    done = [r for r in reproduced if r['episode'] is not None]
    print(f"rerun equals stage 0: {sum(r['all_equal'] and r['same_task'] for r in done)}/{len(done)} episodes; "
          f"tasks identical {sum(r['same_task'] for r in reproduced)}/{len(reproduced)}")
    print(f"trials equal their source boundary: {summary['trials_equal_source']}/{len(records)}")
    print('template node                          reached raw_p attributed_p')
    for n in summary['nodes']:
        print(f"{n['template']:8} {n['label']:29} {n['reached']:7} {n['raw_p']:.2f}  {n['attributed_p']:.2f}")
    return summary


def colour_baseline(rgb, rgba, min_pixels=20):
    """nominal_rgba colour variant: centre of the largest component passing the platter rule's colour test.

    Same test as t03_runtime.platter_from_camera (cos > .985 to the nominal colour, brightness > .1),
    image-only. None when no component reaches min_pixels.
    """
    import numpy as np
    from scipy import ndimage
    x = np.asarray(rgb, float) / 255
    nominal = np.asarray(rgba[:3], float) / np.linalg.norm(rgba[:3])
    length = np.linalg.norm(x, axis=-1)
    labels, count = ndimage.label(((x @ nominal) / np.maximum(length, 1e-9) > .985) & (length > .1))
    if not count:
        return None
    sizes = np.bincount(labels.ravel())[1:]
    if sizes.max() < min_pixels:
        return None
    ys, xs = np.nonzero(labels == np.argmax(sizes) + 1)
    return [float(xs.mean()), float(ys.mean())]


def score(answer, mask, high):
    """2D hit: the answered point lies on a target pixel. A wrong answer at confidence >= high is a high-confidence error."""
    if answer['outcome'] != 'answer':
        return {'outcome': answer['outcome'], 'hit': False, 'high_confidence_error': False}
    x, y = answer['point_px']
    i, j = int(y), int(x)
    hit = bool(0 <= i < len(mask) and 0 <= j < len(mask[0]) and mask[i][j])
    return {'outcome': 'answer', 'hit': hit, 'high_confidence_error': not hit and answer['confidence'] >= high}


def locate_frames(run, row, sizes, scratch):
    """The RGB locate read at the run's 00_configured checkpoint, fresh renders at other sizes, target masks.

    The kernel camera is 320x180; that frame follows TabletopPlant.rgbd (the cached frame while it is
    younger than 0.4 s). Masks come from MuJoCo segmentation of the target body's subtree.
    """
    import io
    import mujoco
    import numpy as np
    from harness import kernel as K
    from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant
    folder = run / 'episodes' / row['id'] / 'engineering'
    entry = next(e for e in read(folder / 'checkpoints.json') if e['done'] == 0)
    snap = K.read_checkpoint(ROOT / entry['path'])
    links = dict.fromkeys(('instance', 'plant', 'port', 'controller', 'model', 'data', 'renderer', 'kinematics'))
    saved = K._Thawer(io.BytesIO(snap['objects']), links, scratch).load()['plant']
    instance = read(run / 'tasks' / row['id'] / 'instance.json')
    model = mujoco.MjModel.from_xml_path(str(run / 'tasks' / row['id'] / 'pantry_G1.xml'))
    plant = TabletopPlant(instance, ROOT / row['source'], model, scratch, budget=1.)
    mujoco.mj_setState(model, plant.data, snap['mujoco_state'], K.INTEGRATION)
    mujoco.mj_forward(model, plant.data)
    plant.rgbd_cache = saved['rgbd_cache']
    sensor = plant.rgbd()
    target = model.body(next(o for o in instance['objects'] if o['is_target'])['name']).id

    def inside(body):
        while body and body != target:
            body = int(model.body_parentid[body])
        return body == target
    geoms = [g for g in range(model.ngeom) if inside(int(model.geom_bodyid[g]))]
    options = mujoco.MjvOption()
    options.geomgroup[:] = [0, 1, 1, 0, 0, 0]
    frames = {}
    for width, height in sizes:
        renderer = mujoco.Renderer(model, height=height, width=width, max_geom=4000)
        renderer.update_scene(plant.data, camera='g1_head', scene_option=options)
        rgb = np.asarray(sensor['rgb'], np.uint8) if (width, height) == (320, 180) else renderer.render().copy()
        renderer.enable_segmentation_rendering()
        renderer.update_scene(plant.data, camera='g1_head', scene_option=options)
        segment = renderer.render().copy()
        renderer.close()
        mask = (segment[..., 1] == mujoco.mjtObj.mjOBJ_GEOM) & np.isin(segment[..., 0], geoms)
        frames[(width, height)] = (rgb, mask)
    if plant.renderer:
        plant.renderer.close()
    return frames, {'checkpoint': entry['path'], 'state_time_s': snap['simulation_s'],
                    'frame_time_s': sensor['timestamp_s']}


def vlm_renders(c, run, out):
    """E3 frames, target masks and their provenance under out. vlm runs this in a child process so the
    MuJoCo scenes are freed before the model loads: with both resident, WSL OOM-killed llama-server (_002)."""
    import numpy as np
    from PIL import Image
    from harness import vlm_locate as V
    sizes = [tuple(s) for s in c['sizes']]
    renders = []
    (out / 'frames').mkdir()
    for task in read(run / 'tasks.json'):
        folder = run / 'episodes' / task['id'] / 'engineering'
        if not (folder / 'checkpoints.json').exists() or not read(folder / 'checkpoints.json'):
            continue
        public = read(run / 'tasks' / task['id'] / 'task.json')
        role = next(r for r in public['roles'] if r['target'])
        instance = read(run / 'tasks' / task['id'] / 'instance.json')
        prototype = next(o for o in instance['objects'] if o['is_target'])['asset'].get('prototype_id')
        located = next(t for t in read(folder / 'tools.json') if t['tool'] == 'locate')
        group = ('rule_ok' if located['truth_ok'] else 'hard' if prototype in c['hard_prototypes'] else 'rule_failed_other')
        scratch = out / 'scratch' / task['id']
        scratch.mkdir(parents=True)
        frames, origin = locate_frames(run, task, sizes, scratch)
        for (width, height), (rgb, mask) in frames.items():
            size = f'{width}x{height}'
            with (out / 'frames' / f"{task['id']}_{size}.png").open('xb') as f:
                Image.fromarray(rgb).save(f, format='PNG')
            with (out / 'frames' / f"{task['id']}_{size}_mask.png").open('xb') as f:
                Image.fromarray(mask.astype(np.uint8) * 255).save(f, format='PNG')
            renders.append({'task': task['id'], 'template': task['template'], 'prototype': prototype, 'group': group,
                            'size': size, 'mask_pixels': int(mask.sum()), 'query': V.query_text(role),
                            'appearance_rgba': role['appearance_rgba'], **origin})
    write_new(out / 'renders.json', renders)


def vlm(path):
    """E3 offline feasibility of the K3 VLM locate primitive (design doc §5.4 K3).

    Frames: the 320x180 frame locate read in every ready episode of a checkpointed run, plus
    registered larger renders of the same camera (a sensor change, reported only). Groups by
    the run's own locate outcome. Arms: the VLM and the nominal_rgba colour baseline.
    """
    import io
    import multiprocessing
    import statistics
    import numpy as np
    from PIL import Image
    from harness import vlm_locate as V
    c = read(path)
    for key in ('prediction', 'falsification', 'run', 'ollama', 'sizes', 'high_confidence', 'repeats', 'hard_prototypes',
                'caps'):
        if c.get(key) in (None, '', [], {}):
            raise ValueError('missing preregistration: ' + key)
    run, out = ROOT / c['run'], ROOT / c['output']
    out.mkdir(parents=True, exist_ok=False)
    write_new(out / 'config.json', c)
    setup = dict(c['ollama'])
    model = V.identity(setup['endpoint'], setup['model'])
    setup['digest'] = model['digest']
    write_new(out / 'model.json', model)
    sizes = [tuple(s) for s in c['sizes']]
    child = multiprocessing.get_context('spawn').Process(target=vlm_renders, args=(c, run, out))
    child.start()
    child.join()
    if child.exitcode:
        raise RuntimeError(f'frame rendering exited with code {child.exitcode}')
    rows, calls = [], 0
    for render in read(out / 'renders.json'):
        name = f"{render['task']}_{render['size']}"
        png = (out / 'frames' / f'{name}.png').read_bytes()
        rgb = np.asarray(Image.open(io.BytesIO(png)))
        mask = np.asarray(Image.open(out / 'frames' / f'{name}_mask.png')) > 0
        height, width = mask.shape
        base = colour_baseline(rgb, render['appearance_rgba'])
        answer = {'outcome': 'abstain'} if base is None else {'outcome': 'answer', 'point_px': base, 'confidence': 1.}
        common = {k: v for k, v in render.items() if k != 'appearance_rgba'}
        rows.append({**common, 'arm': 'colour', 'answer': answer, **score(answer, mask, c['high_confidence'])})
        replies = []
        for repeat in range(c['repeats']):
            if calls >= c['caps']['calls']:
                raise RuntimeError('VLM_CALL_BUDGET')
            calls += 1
            replies.append(V.ask(png, render['query'], setup, cache=out / 'cache' if repeat == 0 else None))
        answer = V.parse(replies[0]['text'], width, height)
        rows.append({**common, 'arm': 'vlm', 'answer': answer, 'replies': replies,
                     'repeats_agree': len({r['text'] for r in replies}) == 1,
                     **score(answer, mask, c['high_confidence'])})
        print(f"{render['task']:18} {render['group']:17} {render['size']:8} colour hit={rows[-2]['hit']!s:5} "
              f"vlm {answer['outcome']:7} hit={rows[-1]['hit']!s:5} {replies[0]['latency_s']:.1f}s")
    write_new(out / 'frames.json', rows)
    table = []
    for key in sorted({(r['arm'], r['size'], r['group']) for r in rows}):
        part = [r for r in rows if (r['arm'], r['size'], r['group']) == key]
        entry = {'arm': key[0], 'size': key[1], 'group': key[2], 'n': len(part), 'hit': sum(r['hit'] for r in part),
                 'abstain': sum(r['outcome'] == 'abstain' for r in part),
                 'invalid': sum(r['outcome'] == 'invalid' for r in part),
                 'high_confidence_error': sum(r['high_confidence_error'] for r in part)}
        if key[0] == 'vlm':
            entry['median_latency_s'] = statistics.median(r['replies'][0]['latency_s'] for r in part)
            entry['repeats_agree'] = sum(r['repeats_agree'] for r in part)
        table.append(entry)
    cell = {(t['arm'], t['size'], t['group']): t for t in table}
    primary = f'{sizes[0][0]}x{sizes[0][1]}'
    vlm_hard, colour_hard = cell.get(('vlm', primary, 'hard')), cell.get(('colour', primary, 'hard'))
    errors = cell.get(('vlm', primary, 'rule_ok'), {}).get('high_confidence_error', 0)
    falsified = [reason for reason, hit in (
        (f'hard-frame hits {vlm_hard and vlm_hard["hit"]} not above colour baseline {colour_hard and colour_hard["hit"]}',
         not vlm_hard or vlm_hard['hit'] <= (colour_hard['hit'] if colour_hard else 0)),
        (f'{errors} high-confidence errors on rule-success frames', errors > 0)) if hit]
    summary = {'model': model, 'primary_size': primary, 'calls': calls, 'table': table,
               'falsified': falsified, 'k3_enters_k2': not falsified,
               'scope': 'decision uses the primary (kernel camera) size only; other sizes need a sensor decision'}
    write_new(out / 'summary.json', summary)
    print('arm    size     group             n hit abstain invalid hc_err latency agree')
    for t in table:
        print(f"{t['arm']:6} {t['size']:8} {t['group']:17} {t['n']:2} {t['hit']:3} {t['abstain']:7} {t['invalid']:7} "
              f"{t['high_confidence_error']:6} {t.get('median_latency_s', 0):7.1f} {t.get('repeats_agree', '')}")
    print('K3 falsified: ' + '; '.join(falsified) if falsified else 'K3 not falsified on the primary size')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'kernel', 'report'):
        sub.add_parser(name).add_argument('path', type=Path)
    sub.add_parser('checkpoints').add_argument('path', type=Path)
    sub.add_parser('trials').add_argument('path', type=Path)
    sub.add_parser('vlm').add_argument('path', type=Path)
    replay = sub.add_parser('contacts')
    replay.add_argument('path', type=Path)
    replay.add_argument('out', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        print(prepare(args.path))
    elif args.command == 'kernel':
        kernel(args.path)
        report(args.path)
    elif args.command == 'checkpoints':
        checkpoints(args.path)
    elif args.command == 'trials':
        trials(args.path)
    elif args.command == 'vlm':
        vlm(args.path)
    elif args.command == 'contacts':
        contacts(args.path, args.out)
    else:
        report(args.path)


if __name__ == '__main__':
    main()
