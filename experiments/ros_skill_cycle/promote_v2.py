"""Publish an audited observation revision while preserving the validated parent."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
from experiments.t0_agent_v1.common import ROOT,read,relative,sha,write_new


def promote(cycle,audit,confirmation,output):
    report=read(audit/'audit.json')
    if report['status']!='passed' or not report['gate']['passed']:
        raise ValueError('Passed development gate and independent audit required')
    paired=read(confirmation/'audit.json')
    if paired['status']!='passed' or not paired['paired_repair'] or not all(paired['checks'].values()):
        raise ValueError('Own frozen-version paired confirmation required')
    source=cycle/'recipe';manifest=read(source/'manifest.json')
    for path,digest in manifest['bindings'].items():
        if sha(ROOT/path)!=digest:
            raise ValueError('Frozen source changed: '+path)
    if paired['candidate']['policy']!=manifest['policy']:
        raise ValueError('Confirmation policy differs from tested recipe')
    output.mkdir(parents=True,exist_ok=False);(output/'implementation').mkdir()
    copied={}
    for suffix in ['implementation/execution.py','implementation/public_check.py','policy.json']:
        target=output/suffix;shutil.copyfile(source/suffix,target)
        if sha(target)!=sha(source/suffix):raise AssertionError('Executable packaging changed bytes')
        copied[relative(target)]=sha(target)
    canonical=deepcopy(manifest);canonical['status']='validated_recipe';canonical['bindings'].update(copied)
    write_new(output/'manifest.json',canonical)
    parent=ROOT/'experiments/t0_agent_v1/skill_registry/T01_ros_cup_to_tray_v1.json'
    registry=deepcopy(read(parent))
    registry.update(skill_version='1.1.0',name='T01 ROS 技能：有界修订与一次主动观察核验',
        parent_registry=relative(parent),parent_registry_sha256=sha(parent),
        validation_level='expanded',
        authorship='Engineering-assisted observation mechanism; automatic acceptance gate; parent bounded candidate screening preserved',
        artifact=dict(kind='bounded_engineering_tool_composition_with_active_observation',bundle=relative(output),
            manifest=relative(output/'manifest.json'),manifest_sha256=sha(output/'manifest.json'),
            tested_recipe=relative(source),tested_manifest_sha256=sha(source/'manifest.json'),
            executable_bytes_identical_to_tested_recipe=True,policy=manifest['policy']),
        observation_validation=dict(audit=relative(audit/'audit.json'),audit_sha256=sha(audit/'audit.json'),
            groups=report['groups'],gate=report['gate'],
            independent_unit='actual initial state, 8 prospective new initials for v1.1',
            no_causal_comparison_with_parent_test=True))
    registry['runtime_contract']['goal']['skill_version']='1.1.0'
    registry['runtime_contract']['active_observation']=canonical['contract']['active_observation']
    registry['runtime_contract']['observed_selected_and_boundary_false_positive_success']=sum(
        report['groups'][phase]['false_positive_success'] for phase in ['frozen_test','boundary'])
    registry['parent_validation']=registry.pop('validation')
    registry['parent_candidate_selection']=registry.pop('selection')
    registry['validation']=dict(
        paired_confirmation=dict(audit=relative(confirmation/'audit.json'),
            audit_sha256=sha(confirmation/'audit.json'),baseline_job=paired['baseline_job'],
            candidate_job=paired['candidate_job'],actual_initial_sha256=paired['actual_initial_sha256'],
            baseline_success=False,candidate_success=True,new_physical_episodes=1,
            new_generalization_initials=0),
        development=report['groups']['development'],frozen_new_initials=report['groups']['frozen_test'],
        boundary=report['groups']['boundary'],audit=relative(audit/'audit.json'),
        audit_sha256=sha(audit/'audit.json'),full_task_denominator=8,
        full_task_independent_successes=5,full_task_public_passes=5,
        retained_failure_cases=['joint_840300','joint_840301','joint_840303'],
        retained_failure_stage='grasp_cup: INSUFFICIENT_THUMB_AND_FINGER_LOAD',
        same_version_paired_foundation=True)
    registry['scope']=dict(
        validation='bounded within-family simulation capability, not external accreditation',
        action='T01-specific prebound skill/version instance with a unique endpoint',
        automation='Scripted candidate screening and engineering-authored observation revision',
        freeze='Both new-initial tests and registration confirmation execute the same frozen v1.1 recipe')
    registry['limitations'].append('The parent12 and v1.1 new8 are distinct cohorts and different programs; report full-task failures and public-check coverage separately')
    registry['limitations'].append('v1.1 succeeds on 5/8 new initials; 3 grasp failures remain and must not be removed from the denominator')
    target=ROOT/'experiments/t0_agent_v1/skill_registry/T01_ros_cup_to_tray_v1_1.json'
    write_new(target,registry)
    write_new(output/'registration_receipt.json',dict(status='registered',registry=relative(target),
        registry_sha256=sha(target),manifest_sha256=sha(output/'manifest.json'),
        audit_sha256=sha(audit/'audit.json'),confirmation_audit_sha256=sha(confirmation/'audit.json'),
        source_copies_sha256=copied,new_physical_episodes=0))
    print(dict(registry=relative(target),version='1.1.0'),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cycle',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--confirmation',type=Path,required=True)
    a=p.parse_args();promote(a.cycle.resolve(),a.audit.resolve(),a.confirmation.resolve(),a.output.resolve())
