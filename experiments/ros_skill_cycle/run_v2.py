"""Separate preregistered active-observation supplement; never alter cycle-v1 evidence."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
from experiments.t0_agent_v1.common import ROOT,read,relative,sha,write_new,append_event
from experiments.cordis_t01.qualify_guard_initials import qualify
from .prepare import generated,snapshots,TRAYS
from .run import jobs
from .runtime_env import bootstrap

HERE=Path(__file__).parent


def make_bundle(output,parent):
    output.mkdir(parents=True,exist_ok=False)
    (output/'implementation').mkdir()
    original=read(parent/'selected_skill/manifest.json')
    for source,name in [(HERE/'execution_v2.py','execution.py'),(HERE/'public_check.py','public_check.py')]:
        shutil.copyfile(source,output/'implementation'/name)
    manifest=deepcopy(original)
    manifest.update(skill_version='1.1.0',status='frozen_active_observation_candidate')
    manifest['policy']=dict(original['policy'],active_verification=True)
    write_new(output/'policy.json',manifest['policy'])
    for path in [HERE/'execution_v2.py',HERE/'execution.py',HERE/'run_v2.py',
                 output/'implementation/execution.py',output/'implementation/public_check.py',output/'policy.json']:
        manifest['bindings'][relative(path)]=sha(path)
    manifest['contract']['active_observation']=dict(delta_m=[0.,.04,.04],duration_s=2.,maximum_attempts=1,
        trigger='public instantaneous postcondition insufficient',preflight='original continuous IK and self-collision')
    write_new(output/'manifest.json',manifest)
    return manifest


def freeze_phase(target,parent,cases,schedule,phase,bindings):
    target.mkdir(parents=True,exist_ok=False)
    original=read(parent/'registration.json')
    write_new(target/'planned_cases.json',cases)
    inputs=snapshots(target,cases,original['models'])
    write_new(target/'registration.json',dict(cases=cases,models=original['models'],schedule=schedule,
        input_sha256=inputs,source_sha256=bindings,phase=phase,maximum_physical_episodes=len(schedule)))
    qualification=qualify(target)
    write_new(target/'initial_qualification.json',qualification)
    if not qualification['all_valid']:
        raise ValueError('Supplement invalid initial retained without replacement')


def prepare(output,parent):
    output.mkdir(parents=True,exist_ok=False)
    completion=read(parent/'completion.json')
    if completion['selected_policy']!=dict(guard=True,gain=.5):
        raise ValueError('Supplement preregistered only for the selected gain=.5 parent')
    manifest=make_bundle(output/'recipe',parent)
    bindings=dict(manifest['bindings'])
    bindings[relative(output/'recipe/manifest.json')]=sha(output/'recipe/manifest.json')
    write_new(output/'protocol.json',dict(date='2026-10-29',status='registered_before_supplement_execution',
        boundary='simulation',parent=relative(parent),parent_results_preserved=True,
        maximum_physical_episodes=12,development=2,frozen_new_initials=8,external_disturbance_challenges=2,
        changed_factor='one bounded publicly triggered arm retreat for observability only',
        original_task_and_verifiers_unchanged=True,model_requests=0,weight_updates=0,
        gate='both consumed development initials independent success and >=1 public PASS',
        no_causal_comparison_between_parent12_and_new8=True,
        parent_frozen_initials_are_consumed_for_this_version=True,
        definitions=[('position',840100+i,TRAYS[i%2]) for i in range(4)]+
                    [('joint',840300+i,TRAYS[i%2]) for i in range(4)]))
    previous=read(parent/'registration.json')
    cases=[deepcopy(next(c for c in previous['cases'] if c['id']==name)) for name in ['control_2500','fresh_480100']]
    for c in cases:c['evaluation_role']='consumed_active_observation_development'
    schedule=[dict(case_id=c['id'],arm='active_view') for c in cases]
    freeze_phase(output/'development',parent,cases,schedule,'active_view_development',bindings)
    write_new(output/'source_binding.json',dict(bindings=bindings,physics_started=False))
    print(dict(prepared=relative(output),development=2,remaining_limit=10),flush=True)


def main(output,parent):
    bootstrap('experiments.ros_skill_cycle.run_v2')
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    if not output.exists():prepare(output,parent)
    rclpy.init()
    node=Node('revision_v11',namespace='/thesis_skill')
    publisher=node.create_publisher(String,'revision_events',100)
    def memory(event):
        append_event(output/'memory.jsonl',event)
        publisher.publish(String(data=json.dumps(event)))
        rclpy.spin_once(node,timeout_sec=0.)
    try:
        recipe=dict(active_view=output/'recipe')
        development=jobs(output,output/'development',recipe,memory)
        if not (output/'development/results.json').exists():
            write_new(output/'development/results.json',dict(rows=development))
        passed=all(r['independent_success'] for r in development) and any(r['runtime_result']['runtime_check']=='PASS' for r in development)
        if not (output/'development_gate.json').exists():
            write_new(output/'development_gate.json',dict(passed=passed,independent_successes=sum(r['independent_success'] for r in development),
                public_passes=sum(r['runtime_result']['runtime_check']=='PASS' for r in development)))
        if not passed:
            write_new(output/'no_promotion.json',dict(reason='Active observation development gate failed; no frozen test launched'))
            return
        binding=read(output/'source_binding.json')['bindings']
        target=output/'frozen_test'
        if not target.exists():
            cases=[generated(group,seed+i,TRAYS[i%2]) for group,seed in [('position',840100),('joint',840300)] for i in range(4)]
            for c in cases:c['evaluation_role']='new_frozen_active_observation_instance'
            schedule=[dict(case_id=c['id'],arm='active_view') for c in cases]
            freeze_phase(target,parent,cases,schedule,'active_view_frozen_test',binding)
            consumed=read(parent/'frozen_test/registration.json')['cases']+read(parent/'registration.json')['cases']
            used={sha(ROOT/c['initial_source']) for c in consumed}
            current=[sha(ROOT/c['initial_source']) for c in read(target/'registration.json')['cases']]
            if len(set(current))!=8 or used.intersection(current):
                raise ValueError('Active-observation new initials overlap consumed evidence')
        tests=jobs(output,target,recipe,memory)
        if not (target/'results.json').exists():write_new(target/'results.json',dict(rows=tests))
        target=output/'boundary'
        if not target.exists():
            base=next(c for c in read(parent/'registration.json')['cases'] if c['id']=='control_2500')
            cases=[];schedule=[]
            for i,fault in enumerate(['post_force_left','post_force_right']):
                c=deepcopy(base);c['id']=f'active_boundary_{i+1:02d}'
                c['evaluation_role']='declared_active_observation_external_disturbance'
                cases.append(c);schedule.append(dict(case_id=c['id'],arm='active_view',fault=fault))
            freeze_phase(target,parent,cases,schedule,'active_view_boundary',binding)
        challenges=jobs(output,target,recipe,memory)
        if not (target/'results.json').exists():write_new(target/'results.json',dict(rows=challenges))
        write_new(output/'completion.json',dict(status='completed_pending_independent_audit',requests=12,
            physical_episodes=sum(r['physical_episodes'] for r in development+tests+challenges),
            model_requests=0,weight_updates=0,skill_version='1.1.0'))
    finally:
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--parent',type=Path,required=True);a=p.parse_args();main(a.output.resolve(),a.parent.resolve())
