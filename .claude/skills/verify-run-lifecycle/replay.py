"""Replay RunLifecycle paths on the real tabletop.kernel/negative/start_physical/report.

Only MuJoCo, the plant and the physics of one episode are stand-ins; kernel.execute keeps
its first line, out.mkdir(parents=True, exist_ok=False). Run from experiments/grow_up_harness_v2.
"""
import contextlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

sys.path.insert(0, '.')
fake_mujoco = types.ModuleType('mujoco')
fake_mujoco.MjModel = types.SimpleNamespace(from_xml_path=lambda path: None)
sys.modules['mujoco'] = fake_mujoco
plant_mod = types.ModuleType('experiments.t0_agent_v1.tabletop_training_plant')


class Plant:
    def __init__(self, *args, **kwargs):
        self.guard, self.initial_hash = None, 'h'

    def dispatch(self, action):
        return {'status': 'EXECUTED'}

    def save(self, *args):
        return {}


plant_mod.TabletopPlant = Plant
sys.modules['experiments.t0_agent_v1.tabletop_training_plant'] = plant_mod
interrupt = set()


def execute(case, out, spec, caps, brain=None):
    out.mkdir(parents=True, exist_ok=False)
    if (case['folder'].name, out.name) in interrupt:
        interrupt.discard((case['folder'].name, out.name))
        raise KeyboardInterrupt('operator stops the process mid-episode')
    (out / 'result.json').write_text(json.dumps({'success': True, 'error': None}))
    (out / 'tools.json').write_text('[]')
    if brain is not None:
        (out / 'decisions.json').write_text('[]')
        (out / 'result.json').write_text(json.dumps({'success': True, 'error': None, 'agent': {
            'nodes': ['locate'], 'stop': 'done', 'brain_calls': 1}}))
    return {'initial_hash': 'h', 'success': True, 'error': None}


fake_kernel = types.ModuleType('harness.kernel')
fake_kernel.execute = execute
# The real agent_episode starts with the same execute call; its retry branches stay inside one episode.
fake_kernel.agent_episode = lambda case, out, spec, caps, brain: execute(case, out, spec, caps, brain=brain)
fake_kernel.verifier = lambda template, hand_rule=None: lambda *a, **k: {
    'verified_task_success': False, 'goal_satisfied': False, 'robot_evidence_valid': True}
sys.modules['harness.kernel'] = fake_kernel
import harness
harness.kernel = fake_kernel
from calibration import tabletop as T


def new_run(folder, rows, arms=None):
    run = Path(folder)
    tasks = [{'id': i, 'template': t, 'ready': True, 'source': 'x', 'robot_initial_hash': 'h', 'bucket': 'near'}
             for i, t in rows]
    (run / 'tasks.json').write_text(json.dumps(tasks))
    for i, _ in rows:
        (run / 'tasks' / i).mkdir(parents=True)
        (run / 'tasks' / i / 'instance.json').write_text(json.dumps({'objects': [{'is_target': True, 'position_m': [.34, .32, 0]}]}))
        (run / 'tasks' / i / 'task.json').write_text('{}')
    (run / 'config.json').write_text(json.dumps({'caps': {'wall_s': 1e9, 'physical_episodes': 6},
                                                 'episode_caps': {'simulation_s': 1},
                                                 **({'arms': arms, 'brain': {}} if arms else {})}))
    (run / 'kernel.json').write_text(json.dumps({'version': 'K_v1'}))
    (run / 'registration.json').write_text(json.dumps({'start_epoch': __import__('time').time()}))
    (run / 'events.jsonl').write_text('')
    return run


def kernel_command(run):
    """`tabletop.py kernel RUN`: kernel(run) then report(run)."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            T.kernel(run)
            T.report(run)
        return 'ok'
    except BaseException as exc:
        return f'{type(exc).__name__}: {str(exc)[:90]}'


def started(run):
    return [(e['task'], e['arm']) for e in T.events(run) if e['event'] == 'physical_started']


@contextlib.contextmanager
def brain_session(run, setup):
    """Stand-in for the private OpenCode server; the real one opens a fresh numbered folder per kernel command."""
    yield object()


with mock.patch.object(T, 'check_kernel_unchanged'), mock.patch.object(T, 'FROZEN', ()), \
        mock.patch.object(T, 'brain_session', brain_session):
    print('== NoEpisodeStartedTwice / RerunNeverStuck: interrupted mid-episode, then rerun (expect INTERRUPTED, then BATCH_INVALID)')
    with tempfile.TemporaryDirectory() as folder:
        run = new_run(folder, [('a', 'TP01')])
        interrupt.add(('a', 'engineering'))
        print(' 1 kernel  ->', kernel_command(run))
        print(' 2 kernel  ->', kernel_command(run))
        print(' 3 kernel  ->', kernel_command(run))
        print(' physical_started:', started(run))

    print('== RerunNeverStuck: negative wait rejected, then rerun (expect void, then BATCH_INVALID)')
    with tempfile.TemporaryDirectory() as folder:
        run = new_run(folder, [('a', 'TP01')])
        with mock.patch.object(Plant, 'dispatch', return_value={'status': 'REJECTED'}):
            print(' 1 kernel  ->', kernel_command(run))
        print(' 2 kernel  ->', kernel_command(run))

    print('== FinalReportAlwaysWritten: report run by hand mid-batch, then the batch finishes (expect ok)')
    with tempfile.TemporaryDirectory() as folder:
        run = new_run(folder, [('a', 'TP01'), ('b', 'TP01')])
        real_start = T.start_physical

        def stop_before_b(run_, task, arm):
            if task == 'b':
                raise KeyboardInterrupt('operator stops the process between rows')
            return real_start(run_, task, arm)
        with mock.patch.object(T, 'start_physical', stop_before_b):
            print(' 1 kernel  ->', kernel_command(run))
        with contextlib.redirect_stdout(io.StringIO()):
            T.report(run)
        print(' 2 report  -> report.json written:', (run / 'report.json').exists())
        print(' 3 kernel  ->', kernel_command(run))
        print(' final report.json', json.loads((run / 'report.json').read_text())['tasks'])

    print('== Two arms, NoEpisodeStartedTwice: agent episode of row a interrupted, then rerun (expect INTERRUPTED, then BATCH_INVALID)')
    with tempfile.TemporaryDirectory() as folder:
        run = new_run(folder, [('a', 'TP01'), ('b', 'TP01')], ['engineering', 'agent'])
        interrupt.add(('a', 'agent'))
        print(' 1 kernel  ->', kernel_command(run))
        print(' 2 kernel  ->', kernel_command(run))
        print(' 3 kernel  ->', kernel_command(run))
        print(' physical_started:', started(run))

    print('== Two arms, FinishedReportCoversAllRows: stop between the arms of row b, rerun (expect ok, both arms of both rows)')
    with tempfile.TemporaryDirectory() as folder:
        run = new_run(folder, [('a', 'TP01'), ('b', 'TP01')], ['engineering', 'agent'])
        real_start = T.start_physical

        def stop_before_b_agent(run_, task, arm):
            if (task, arm) == ('b', 'agent'):
                raise KeyboardInterrupt('operator stops the process between episodes')
            return real_start(run_, task, arm)
        with mock.patch.object(T, 'start_physical', stop_before_b_agent):
            print(' 1 kernel  ->', kernel_command(run))
        print(' 2 kernel  ->', kernel_command(run))
        print(' physical_started:', started(run))
        saved = json.loads((run / 'report.json').read_text())
        print(' final report.json', {arm: c['tasks'] for arm, c in saved['columns'].items()},
              [(p['task'], sorted(k for k in p if k not in ('task', 'group'))) for p in saved['pairs']])
