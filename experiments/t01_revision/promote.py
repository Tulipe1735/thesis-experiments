"""Register an evidence-bound formal Skill only after paired and frozen audits pass."""
import argparse
import json
from pathlib import Path
import shutil

from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new


def promote(development, frozen, skill_id):
    dev, test = [read(p / 'audit.json') for p in [development, frozen]]
    if dev['status'] != 'passed' or test['status'] != 'passed':
        raise ValueError('Independent audits required')
    if dev['groups']['repaired'] < 1 or dev['groups']['regressed'] or test['groups']['regressed']:
        raise ValueError('A repaired pair and no observed regression are required')
    manifests = [read(p / 'registration.json') for p in [development, frozen]]
    if manifests[0]['policies'] != manifests[1]['policies']:
        raise ValueError('Policy changed between development and frozen test')
    for manifest in manifests:
        if not all(sha(ROOT / p) == digest for p, digest in
                   {**manifest['source_sha256'], **manifest['input_sha256']}.items()):
            raise ValueError('Frozen dependency changed')
    artifact = ROOT / 'experiments/t01_revision/validated' / skill_id
    artifact.mkdir(parents=True, exist_ok=False)
    program = ['inspect_scene', 'grasp_cup', 'transfer_to_tray', 'inspect_alignment',
               {'if': 'alignment.status == CORRECT', 'tool': 'correct_alignment'},
               'release_in_tray', 'verify_task']
    policy = dict(skill_id=skill_id, program=program,
                  gain=manifests[0]['policies']['candidate']['gain'],
                  implementation='RevisionSkills', module='experiments.t01_revision.candidate',
                  observation_boundary='head RGB-D, public robot model/FK, anonymous tactile and controller feedback',
                  max_corrections=1, original_trigger_m=.008, original_max_correction_m=.04)
    write_new(artifact / 'policy.json', policy)
    for name in ['candidate.py', 'pipeline.py']:
        shutil.copyfile(Path(__file__).with_name(name), artifact / name)
    evidence = {relative(p / n): sha(p / n) for p in [development, frozen]
                for n in ['design.json', 'registration.json', 'results.json', 'initial_qualification.json',
                          'audit.json', 'paired_comparison.csv']}
    dependencies = dict(manifests[0]['source_sha256'])
    dependencies.update(manifests[1]['source_sha256'])
    snapshots = {relative(p): sha(p) for p in artifact.iterdir() if p.is_file()}
    cases = []
    for suite, manifest in zip([development, frozen], manifests):
        for case in manifest['cases']:
            for condition in manifest['policies']:
                result = read(suite / 'episodes' / (case['id'] + '__' + condition) / 'result.json')
                cases.append(dict(suite=relative(suite), case_id=case['id'], condition=condition,
                    actual_initial_sha256=result['initial_sha256'], verified_success=result['verified_success'],
                    execution_error=result['execution_error'],
                    episode=result['episode'], verdict_sha256=result['verdict_sha256'],
                    trajectory_sha256=result['trajectory_sha256']))
    record = dict(schema_version='skill_registry.v1', skill_id=skill_id,
        name='T01 有界视觉交接纠正：减半幅度修订', status='validated_skill',
        formal_promotion=True, promotion_date='2026-10-29', boundary='simulation',
        validation_level='expanded', foundation_validation_level='paired',
        task=dict(task_id='T01', robot='G1 + dual Dex3-1', target_count=1,
            cup='DH_2F_mug_06 upright white cup, known 41 mm radius class',
            trays=['rectangular_low_rim_v1', 'marked_long_tray_v1'],
            observations='visible calibrated tray markers and compatible head RGB-D cup fit'),
        applicability=dict(required_stage='above_tray after a successful bounded grasp/transfer',
            confidence_and_path_checks='original confidence, trigger, correction bound and IK checks retained',
            fallback='keep nominal placement if perception or candidate path is rejected',
            validation_scope='the nine registered actual initials, all failures retained; no universal success guarantee'),
        artifact=dict(kind='bounded_engineering_tool_composition', policy=relative(artifact / 'policy.json'),
            policy_sha256=sha(artifact / 'policy.json'), source_snapshots=snapshots,
            execution_binding='same source, gain and conditional program used in all candidate episodes',
            authorship='Codex engineering-assisted feedback revision; no external model request or weight update'),
        paired_development=dev['groups'], frozen_within_family_test=test['groups'],
        known_limitations=['Frozen test is 5/6 versus nominal 5/6, not an observed overall test success gain',
            'orientation_710201 fails before the checkpoint because thumb/finger holding load is insufficient',
            'Does not repair all grasp, transfer reachability or endpoint tracking failures',
            'No new asset-family, unmarked-tray, real-robot or long-horizon claim'],
        frozen_dependencies=dependencies, evidence_sha256=evidence, case_evidence=cases,
        runtime='Python/MuJoCo validation; ROS 2 migration is separate evidence',
        model_requests=0, model_weight_updates=0, auto_default_enabled=False,
        historical_record_policy='prior registry, failures, results and execution-time promotion flags remain unchanged')
    path = ROOT / 'experiments/t0_agent_v1/skill_registry' / (skill_id + '.json')
    write_new(path, record)
    write_new(artifact / 'registration_receipt.json', dict(registry=relative(path), registry_sha256=sha(path)))
    print(dict(promoted=relative(path), validation_level=record['validation_level'],
               development=dev['groups'], frozen=test['groups']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development', type=Path, required=True)
    parser.add_argument('--frozen', type=Path, required=True)
    parser.add_argument('--skill-id', default='T01_visual_handoff_damped_v1')
    args = parser.parse_args()
    promote(args.development.resolve(), args.frozen.resolve(), args.skill_id)
