"""Register an evidence-bound skill under existing paired/expanded repository rules."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
from experiments.t0_agent_v1.common import ROOT,read,relative,sha,write_new


def promote(cycle,audit,output):
    report=read(audit/'audit.json')
    if report['status']!='passed' or not report['selection']['selected']:
        raise ValueError('Passed immutable audit and accepted development repair required')
    selected=report['selection']['selected']
    if selected['repaired']<1 or selected['regressed']:
        raise ValueError('Paired foundation failed')
    source=cycle/'selected_skill'
    manifest=read(source/'manifest.json')
    output.mkdir(parents=True,exist_ok=False)
    (output/'implementation').mkdir()
    copied={}
    for name in ['execution.py','public_check.py']:
        path=output/'implementation'/name
        shutil.copyfile(source/'implementation'/name,path)
        if sha(path)!=sha(source/'implementation'/name):raise AssertionError('Frozen code changed in packaging')
        copied[relative(path)]=sha(path)
    shutil.copyfile(source/'policy.json',output/'policy.json')
    copied[relative(output/'policy.json')]=sha(output/'policy.json')
    promoted=deepcopy(manifest)
    promoted['status']='validated_recipe'
    promoted['bindings'].update(copied)
    write_new(output/'manifest.json',promoted)
    groups=report['groups']
    selected_test=groups['frozen']['selected']
    all_false_positives=(selected_test['false_positive_success']+groups['boundary']['false_positive_success'])
    level='expanded' if groups['frozen_regressed']==0 else 'paired'
    registry=dict(schema_version='skill_registry.v1',skill_id=manifest['skill_id'],skill_version=manifest['skill_version'],
        name='T01 ROS 2 闭环形成、冷启动调用与独立验收技能',status='validated_skill',formal_promotion=True,
        promotion_date='2026-10-29',boundary='simulation',validation_level=level,foundation_validation_level='paired',
        task=dict(task_id='T01',robot='G1 + dual Dex3-1',target_count=1,cup='DH_2F_mug_06 known white 41mm radius class',
                  compatible_trays=['rectangular_low_rim_v1','marked_long_tray_v1']),
        authorship='Engineering-defined candidate family, automated development screening in ROS workflow; historical gain=.5 already known',
        selection=dict(**selected,rule=report['selection']['criterion']),
        artifact=dict(kind='bounded_engineering_tool_composition',bundle=relative(output),
            manifest=relative(output/'manifest.json'),manifest_sha256=sha(output/'manifest.json'),
            tested_recipe=relative(source),tested_manifest_sha256=sha(source/'manifest.json'),
            executable_bytes_identical_to_tested_recipe=True,policy=manifest['policy']),
        validation=dict(development=groups['development'],frozen_new_initials=groups['frozen'],
            frozen_repaired=groups['frozen_repaired'],frozen_regressed=groups['frozen_regressed'],
            boundary=groups['boundary'],audit=relative(audit/'audit.json'),audit_sha256=sha(audit/'audit.json')),
        runtime_contract=dict(goal=dict(skill_id=manifest['skill_id'],skill_version=manifest['skill_version'],
                parameters=dict(target='single_visible_cup_to_marked_tray')),
            transport='real thesis_skill_interfaces/action/ExecuteSkill; isolated endpoint per cold-start instance',
            public_success='Action SUCCEEDED only when frozen public visual proxy passes',
            uncertainty='Action ABORTED with runtime_check=UNVERIFIED; physical outcome remains independently evaluated',
            private_evaluation_never_returned_to_execution_client=True,
            observed_selected_and_boundary_false_positive_success=all_false_positives),
        limitations=['Simulation only; no physical robot, new shape-family or long-horizon claim',
            'Automated bounded parameter selection, not model weight training or discovery of low-level control',
            'Public runtime proxy is incomplete and can abstain on true physical successes; report coverage with success',
            'Expanded observations describe these registered within-family initials only; no population guarantee',
            'Generic mid-motion cancel/resume and complete G1 ROS robot description remain outside this run'],
        model_requests=0,weight_updates=0,source_evidence_preserved=True,
        parent_skill='T01_visual_handoff_damped_v1; reused engineering primitives and known candidate family')
    target=ROOT/'experiments/t0_agent_v1/skill_registry/T01_ros_cup_to_tray_v1.json'
    write_new(target,registry)
    write_new(output/'registration_receipt.json',dict(status='registered',registry=relative(target),
        registry_sha256=sha(target),audit_sha256=sha(audit/'audit.json'),manifest_sha256=sha(output/'manifest.json'),
        source_copies_sha256=copied,new_physical_episodes=0,model_requests=0))
    print(dict(registry=relative(target),level=level,selected_policy=manifest['policy']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cycle',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();promote(a.cycle.resolve(),a.audit.resolve(),a.output.resolve())
