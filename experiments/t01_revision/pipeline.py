"""Register and execute paired T01 revisions; never overwrite an earlier suite."""
import argparse
from copy import deepcopy
import json
import random
from pathlib import Path
import time
import traceback

from experiments.cordis_t01.guard_worker import Session as BaseSession
from experiments.cordis_t01.qualify_guard_initials import qualify
from experiments.t0_agent_v1.common import ROOT, REFERENCE, read, relative, sha, write_new, append_event
from .candidate import RevisionSkills

VARIATION = ROOT / 'experiments/cordis_t01/runs/t01_variation_20261028_001'
COMPARISON = ROOT / 'experiments/cordis_t01/runs/handoff_guard_comparison_20261028_001'
PROGRAM = ['inspect_scene', 'grasp_cup', 'transfer_to_tray', 'inspect_alignment',
           'correct_alignment', 'release_in_tray', 'verify_task']


class Session(BaseSession):
    def __init__(self, output, suite, case_id, *, condition):
        self.condition = condition
        self.output, self.folder = output, output / 'episode'
        self.folder.mkdir(exist_ok=False)
        self.registration = read(suite / 'registration.json')
        self.case = next(c for c in self.registration['cases'] if c['id'] == case_id)
        self.instance = self.case['instance']
        self.model = self.registration['models'][self.case['model_key']]
        self.bindings = {**self.registration['source_sha256'], **self.registration['input_sha256']}
        self.bindings.update({relative(p): sha(p) for p in [suite / 'registration.json', suite / 'design.json',
            REFERENCE / 'initial_state.npz', REFERENCE / 'runtime_context.json', REFERENCE / 'episode_memory.json',
            ROOT / 'grasp_optimization/assets/robot_profile.json']})
        if not self.unchanged():
            raise ValueError('Registered source or input changed')
        self.robot = self.port = self.skills = None
        self.error = self.result = self.failed_tool = None
        self.closed, self.calls, self.started = False, 0, time.monotonic()
        write_new(output / 'registration.json', dict(case=self.case, suite=relative(suite),
                  model=self.model, bindings=self.bindings, boundary='simulation', max_episodes=1,
                  runtime='Python/MuJoCo', ros2_execution=False))
        write_new(self.folder / 'instance.json', self.instance)
        write_new(self.folder / 'run_config.json', dict(date='2026-10-29', task='T01', mode='scripted',
                  driver='t01_revision.pipeline', seed=self.instance['seed'], target_count=1,
                  split=self.case['evaluation_role'], group=self.case['group'], case_id=case_id,
                  boundary='simulation', policy_reads_object_truth=False, spectator_used_by_policy=False,
                  model_requests=0, ros2_execution=False))

    def initialize(self):
        super().initialize()
        gain = self.registration['policies'][self.condition].get('gain', 1.)
        self.skills = RevisionSkills(self.port, self.folder, gain=gain)

def prepare(output, gain):
    output.mkdir(parents=True, exist_ok=False)
    original = read(VARIATION / 'registration.json')
    variation = {c['id']: c for c in original['cases']}
    comparison = {c['id']: c for c in read(COMPARISON / 'registration.json')['cases']}
    cases = []
    for name in ['orientation_280201', 'control_2500']:
        c = deepcopy(variation[name])
        c['initial_source'] = relative(VARIATION / 'cases' / name / 'episode/initial_state.npz')
        cases.append(c)
    cases.append(deepcopy(comparison['fresh_480100']))
    for c in cases:
        c['evaluation_role'] = 'consumed_development_case'
    policies = dict(nominal=dict(guard=False), candidate=dict(guard=True, gain=gain))
    schedule = []
    rng = random.Random('t01-revision-development-20261029')
    for c in cases:
        arms = list(policies)
        rng.shuffle(arms)
        schedule.extend(dict(case_id=c['id'], condition=arm) for arm in arms)
    sources = dict(original['source_sha256'])
    for directory in ['experiments/cordis_t01', 'experiments/t01_revision']:
        sources.update({relative(p): sha(p) for p in (ROOT / directory).glob('*.py')})
    inputs = {c['initial_source']: sha(ROOT / c['initial_source']) for c in cases}
    inputs.update({r['path']: r['sha256'] for r in original['models'].values()})
    design = dict(date='2026-10-29', boundary='simulation', phase='development',
                  status='registered_before_execution', cases=cases, policies=policies, schedule=schedule,
                  experimental_unit='saved actual initial state paired across policies',
                  question='does damped visual centering repair the known placement failure without the known regression?',
                  changed_factor='centering correction gain only; original controller/evaluator unchanged',
                  old_cases_never_called_unseen=True, replaced_cases=0, attempts_per_condition=1,
                  claim='descriptive paired engineering validation; no population inference',
                  runtime='Python/MuJoCo; ROS 2 and ros2_control not installed or claimed',
                  model_requests=0, skill_promotion='only after paired success, regression and immutable audit')
    write_new(output / 'design.json', design)
    write_new(output / 'registration.json', dict(**design, models=original['models'],
              input_sha256=inputs, source_sha256=sources, expected_program=PROGRAM,
              simulation_budget_s=180., max_physical_episodes=len(schedule)))
    print(json.dumps(dict(prepared=relative(output), episodes=len(schedule))), flush=True)


def run(output, only=None):
    registration = read(output / 'registration.json')
    if not all(sha(ROOT / p) == h for p, h in
               {**registration['source_sha256'], **registration['input_sha256']}.items()):
        raise ValueError('Frozen source or input changed')
    qualification = qualify(output)
    if not (output / 'initial_qualification.json').exists():
        write_new(output / 'initial_qualification.json', qualification)
    if not qualification['all_valid']:
        raise ValueError('Invalid initial state; retained without replacement')
    results = []
    for job in registration['schedule']:
        if only and job['case_id'] not in only:
            continue
        folder = output / 'episodes' / (job['case_id'] + '__' + job['condition'])
        # Re-entering the runner reads a completed job but never re-executes it.
        if folder.exists():
            if not (folder / 'result.json').exists():
                raise ValueError('Incomplete job retained; use a separately registered new attempt')
            result = read(folder / 'result.json')
            results.append(result)
            continue
        folder.mkdir(parents=True, exist_ok=False)
        append_event(output / 'execution.jsonl', dict(event='started', **job))
        print(json.dumps(dict(event='started', **job)), flush=True)
        session = Session(folder, output, job['case_id'], condition=job['condition'])
        try:
            for tool in ['inspect_scene', 'grasp_cup', 'transfer_to_tray']:
                session.call(tool, {})
            if registration['policies'][job['condition']]['guard']:
                decision = session.call('inspect_alignment', {})
                if decision['status'] == 'CORRECT':
                    session.call('correct_alignment', {})
            session.call('release_in_tray', {})
        except Exception:
            traceback.print_exc()
        finally:
            if session.robot is not None:
                result = session.call('verify_task', {})
            else:
                result = dict(**job, verified_success=False, infrastructure_failure=True)
                write_new(folder / 'result.json', result)
        results.append(result)
        append_event(output / 'execution.jsonl', dict(event='completed', **result))
        print(json.dumps(dict(event='completed', **result)), flush=True)
    complete = len(results) == len(registration['schedule'])
    if complete:
        write_new(output / 'results.json', dict(date='2026-10-29', boundary='simulation',
                  status='completed', results=results, model_requests=0, ros2_execution=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'run'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gain', type=float, default=.5)
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare(args.output.resolve(), args.gain)
    else:
        run(args.output.resolve(), args.only)
