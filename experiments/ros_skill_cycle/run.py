"""Bounded Revision selects from real ROS episodes, then freezes new evaluation requests."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time
import shutil
from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new, append_event
from .runtime_env import bootstrap, configured
from .prepare import bundle, prepare_test, VARIATION, PREVIOUS_FROZEN


def launch(job_folder, context, recipe):
    job_folder.mkdir(parents=True, exist_ok=False)
    write_new(job_folder / 'context.json', context)
    execution = job_folder / 'execution'
    with (job_folder / 'server.log').open('x') as server_log, (job_folder / 'client.log').open('x') as client_log:
        server = subprocess.Popen([sys.executable, '-B', '-m', 'experiments.ros_skill_cycle.server',
            '--bundle', relative(recipe), '--context', relative(job_folder / 'context.json'),
            '--output', relative(execution)], cwd=ROOT, env=configured(), stdout=server_log, stderr=server_log)
        client = subprocess.Popen([sys.executable, '-B', '-m', 'experiments.ros_skill_cycle.client',
            '--bundle', relative(recipe), '--request-id', context['request_id'],
            '--output', relative(job_folder / 'client_result.json')], cwd=ROOT, env=configured(),
            stdout=client_log, stderr=client_log)
        try:
            deadline = time.monotonic() + 45.
            while not (execution / 'ready.json').exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Server startup failed; inspect ' + relative(job_folder / 'server.log'))
                time.sleep(.1)
            client.wait(timeout=480)
            if client.returncode:
                raise RuntimeError('Action client failed; inspect '+relative(job_folder/'client.log'))
            server.wait(timeout=20.)
            if server.returncode:
                raise RuntimeError('Server shutdown failed')
        finally:
            if client.poll() is None:
                client.terminate()
                client.wait(timeout=10.)
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=8.)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    if context.get('non_physical_probe'):
        return read(job_folder / 'client_result.json')
    return read(execution / 'result.json')


def select(rows):
    by = {}
    for row in rows:
        by.setdefault(row['arm'], {})[row['case_id']] = row
    baseline = by['nominal']
    candidates = []
    for arm, outcomes in by.items():
        if arm == 'nominal':
            continue
        repaired = sum(r['independent_success'] and not baseline[c]['independent_success'] for c,r in outcomes.items())
        regressed = sum(not r['independent_success'] and baseline[c]['independent_success'] for c,r in outcomes.items())
        candidates.append(dict(arm=arm, repaired=repaired, regressed=regressed,
            successes=sum(r['independent_success'] for r in outcomes.values()),
            low_level_commands=sum(r['low_level_command_calls'] for r in outcomes.values()),
            gain=next(iter(outcomes.values()))['policy']['gain'], accepted=repaired>=1 and regressed==0))
    accepted = [r for r in candidates if r['accepted']]
    accepted.sort(key=lambda r:(-r['successes'],r['low_level_commands'],r['gain']))
    return dict(candidates=candidates, selected=accepted[0] if accepted else None,
                criterion='successes descending, low-level command cost ascending, gain ascending; repair/no-regression gate')


def jobs(output, suite, recipes, memory):
    registration = read(suite / 'registration.json')
    for path, digest in {**registration['input_sha256'], **registration['source_sha256']}.items():
        if sha(ROOT / path) != digest:
            raise ValueError('Frozen input/source changed: ' + path)
    rows = []
    for index, job in enumerate(registration['schedule']):
        case = next(c for c in registration['cases'] if c['id'] == job['case_id'])
        folder = suite / 'jobs' / (case['id'] + '__' + job['arm'])
        result_path = folder / 'execution/result.json'
        if result_path.exists():
            row = read(result_path)
        else:
            if folder.exists():
                raise RuntimeError('Incomplete attempt retained; automatic retries forbidden: ' + relative(folder))
            request_id = sha(suite / 'registration.json')[:12] + f'-{index:02d}'
            context = dict(case=case, model=registration['models'][case['model_key']],
                           request_id=request_id, fault=job.get('fault'))
            print(json.dumps(dict(event='started', phase=registration['phase'], **job)), flush=True)
            row = launch(folder, context, recipes[job['arm']])
        row = dict(row, arm=job['arm'], job=relative(folder), phase=registration['phase'])
        rows.append(row)
        memory(dict(event='trial_completed', case_id=case['id'], arm=job['arm'],
                    phase=registration['phase'], runtime_check=row['runtime_result']['runtime_check']))
        print(json.dumps(dict(event='completed', case_id=case['id'], arm=job['arm'],
            phase=registration['phase'], independent_success=row['independent_success'],
            runtime_check=row['runtime_result']['runtime_check'], seconds=row['simulation_seconds'])), flush=True)
    return rows


def boundary(output, policy):
    target = output / 'boundary'
    target.mkdir(exist_ok=False)
    dev = read(output / 'registration.json')
    control = next(c for c in dev['cases'] if c['id']=='control_2500')
    old = read(VARIATION / 'registration.json')
    previous = read(PREVIOUS_FROZEN / 'registration.json')
    weak = deepcopy(next(c for c in previous['cases'] if c['id']=='orientation_710201'))
    joint = deepcopy(next(c for c in old['cases'] if c['id']=='joint_280400'))
    joint['initial_source'] = relative(VARIATION / 'cases/joint_280400/episode/initial_state.npz')
    cases, schedule = [], []
    for index, (source, fault) in enumerate([(control,'missing_red_marker'),(control,'invalid_depth'),
            (weak,None),(joint,None),(control,'post_force_left'),(control,'post_force_right')]):
        c=deepcopy(source)
        c['id']=f'boundary_{index+1:02d}'
        c['evaluation_role']='predeclared_consumed_failure_or_fault_challenge'
        cases.append(c)
        schedule.append(dict(case_id=c['id'],arm='selected',fault=fault))
    inputs={c['initial_source']:sha(ROOT/c['initial_source']) for c in cases}
    inputs.update({r['path']:r['sha256'] for r in dev['models'].values()})
    write_new(target/'registration.json',dict(cases=cases,models=dev['models'],input_sha256=inputs,
        source_sha256=dev['source_sha256'],schedule=schedule,phase='boundary',maximum_physical_episodes=6,
        post_forces_N=[5.,-5.],force_duration_s=.1,disturbance_trigger='placement_motion_completed',
        selected_policy=policy,new_generalization_cases=0))
    from experiments.cordis_t01.qualify_guard_initials import qualify
    qualified=qualify(target)
    write_new(target/'initial_qualification.json',qualified)
    if not qualified['all_valid']:
        raise ValueError('Boundary initial invalid; retained without replacement')
    return target


def main(output, probe=False, probe_id=None):
    bootstrap('experiments.ros_skill_cycle.run')
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    registration = read(output / 'registration.json')
    if probe:
        folder=output/('transport_probe_'+probe_id if probe_id else 'transport_probe')
        print(json.dumps(launch(folder,dict(non_physical_probe=True,request_id='transport-'+output.name+'-'+str(probe_id)),
                                      output/'recipes/nominal')),flush=True)
        return
    binding_path=output/'driver_binding.json'
    drivers={relative(Path(__file__).with_name(name)):sha(Path(__file__).with_name(name))
             for name in ['run.py','prepare.py','build_interfaces.py','test_contract.py']}
    if binding_path.exists():
        if read(binding_path)['sources']!=drivers:
            raise ValueError('Registered experiment driver changed; no implicit continuation')
    else:
        snapshots=output/'driver_snapshots'
        snapshots.mkdir(exist_ok=False)
        for name in ['run.py','prepare.py','build_interfaces.py','test_contract.py']:
            shutil.copyfile(Path(__file__).with_name(name),snapshots/name)
        write_new(binding_path,dict(sources=drivers,registered_before_physical_jobs=True))
    rclpy.init()
    node=Node('revision',namespace='/thesis_skill')
    publisher=node.create_publisher(String,'revision_events',100)
    def memory(event):
        append_event(output/'revision_memory.jsonl',event)
        publisher.publish(String(data=json.dumps(event)))
        rclpy.spin_once(node,timeout_sec=0.)
    try:
        recipes={arm:output/'recipes'/arm for arm in registration['policies']}
        development=jobs(output,output,recipes,memory)
        if not (output/'development_results.json').exists():
            write_new(output/'development_results.json',dict(rows=development))
        selection=select(development)
        if not (output/'selection.json').exists():
            write_new(output/'selection.json',selection)
        if not selection['selected']:
            write_new(output/'no_promotion.json',dict(reason='No candidate passed preregistered repair/regression gate'))
            return
        selected=registration['policies'][selection['selected']['arm']]
        memory(dict(event='candidate_accepted',**selection['selected']))
        frozen=output/'selected_skill'
        if not frozen.exists():
            bundle(frozen,selected,'1.0.0',registration['source_sha256'])
            write_new(frozen/'selection_binding.json',dict(selection_sha256=sha(output/'selection.json'),
                       development_results_sha256=sha(output/'development_results.json')))
        target=output/'frozen_test'
        if not target.exists():
            target=prepare_test(output,selected)
        test=jobs(output,target,dict(nominal=recipes['nominal'],selected=frozen),memory)
        if not (target/'results.json').exists():
            write_new(target/'results.json',dict(rows=test))
        target=output/'boundary'
        if not target.exists():
            target=boundary(output,selected)
        challenges=jobs(output,target,dict(selected=frozen),memory)
        if not (target/'results.json').exists():
            write_new(target/'results.json',dict(rows=challenges))
        total=sum(r['physical_episodes'] for r in development+test+challenges)
        if total>46:
            raise AssertionError('Core physical budget exceeded')
        write_new(output/'completion.json',dict(status='execution_completed_pending_independent_audit',
            physical_episodes=total,development_requests=len(development),frozen_requests=len(test),
            boundary_requests=len(challenges),model_requests=0,weight_updates=0,selected_policy=selected))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--probe',action='store_true')
    parser.add_argument('--probe-id')
    args=parser.parse_args()
    main(args.output.resolve(),args.probe,args.probe_id)
