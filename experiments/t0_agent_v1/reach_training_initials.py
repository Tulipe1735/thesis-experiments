"""Four approved training-only initial states in a prior-success workspace."""
import argparse
from copy import deepcopy
from pathlib import Path

from .training_runtime import ensure_runtime
ensure_runtime()
from .common import ROOT, read, relative, sha, write_new
from .train_tp01 import training_cases
from .tabletop_dataset import compile_scene, qualify, public_task
from .tabletop_training_plant import build_training_scene


def create(output, proposal):
    output, proposal = ROOT/output, ROOT/proposal
    design = read(proposal)
    original = {c['instance']['id']: c for c in training_cases()[:4]}
    output.mkdir(parents=True, exist_ok=False)
    scenes = output/'scenes'
    scenes.mkdir()
    write_new(output/'registration.json', dict(date='2026-10-26', boundary='simulation',
        version='prior-success-workspace-training-four-v1', train_cases=4, test_cases=0,
        proposal=relative(proposal), proposal_sha256=sha(proposal),
        human_authorization='另建 4 个初态继续训练（推荐）',
        original_data_modified=False, outcome_resampling=False, seeds=[73000,73001,73002,73003],
        source=relative(Path(__file__)), source_sha256=sha(Path(__file__))))
    rows = []
    for i, proposed in enumerate(design['instances']):
        parent = original[proposed['parent']]
        instance = deepcopy(parent['instance'])
        instance.update(id=proposed['id'], seed=proposed['seed'], split='train', stratum='train',
            generator_version='prior-success-workspace-training-four-v1',
            parent_instance=parent['instance']['id'], parent_instance_sha256=parent['record']['evaluator_sha256'])
        for item in instance['objects']:
            item['position_m'][:2] = proposed['target_xy_m'] if item['is_target'] else proposed['distractor_xy_m']
            item['position_cell'] = 'prior_success_workspace' if item['is_target'] else 'fixed_distractor_area'
            item['local_source_xy_m'] = item['position_m'][:2]
        instance['sampling'] = dict(namespace='prior-success-workspace-training-four-v1',
            actual_sample=proposed, outcome_filter=False, replacements=0,
            held_out=False, rule=design['rule'])
        instance['readiness'].update(reachability='requires_native_sensor_and_path_check',
                                     robot_task_executed=False)
        folder = output/'train'/instance['id']
        folder.mkdir(parents=True, exist_ok=False)
        write_new(folder/'instance.json', instance)
        write_new(folder/'task.json', public_task(instance))
        fixture = compile_scene(instance, folder/'qualification.xml')
        initial = qualify(instance, fixture)
        write_new(folder/'initial_state.json', initial)
        del fixture
        alias = f'case_{i+1:02}'
        scene = scenes/(alias+'.xml')
        model = build_training_scene(instance, scene)
        del model
        write_new(scenes/(alias+'.json'), dict(xml=relative(scene), sha256=sha(scene),
            instance=relative(folder/'instance.json'), instance_sha256=sha(folder/'instance.json')))
        rows.append(dict(alias=alias, id=instance['id'], instance=relative(folder/'instance.json'),
            case_path=relative(folder), instance_sha256=sha(folder/'instance.json'),
            initial_state_sha256=sha(folder/'initial_state.json'),
            valid_initial_fixture=initial['valid_initial_fixture'], rejection_reasons=initial['rejection_reasons']))
        print('FIXTURE', alias, initial['valid_initial_fixture'], initial['rejection_reasons'], flush=True)
    write_new(output/'training_manifest.json', dict(split='train', instances=rows, original_test_data_used=False))
    artifacts = {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    write_new(output/'freeze_manifest.json', dict(date='2026-10-26', artifacts=artifacts,
        rule='No post-outcome sampling or replacement. Qualification failure stays in the manifest.'))
    return output


def load_cases(dataset):
    dataset = Path(dataset)
    frozen = read(dataset/'freeze_manifest.json')
    for p, digest in frozen['artifacts'].items():
        if sha(dataset/p) != digest:
            raise ValueError('Frozen four-case dataset changed: '+p)
    rows = read(dataset/'training_manifest.json')['instances']
    cases = []
    for row in rows:
        instance = read(ROOT/row['instance'])
        if instance['split'] != 'train' or instance['template_id'] != 'TP01':
            raise ValueError('Only TP01 training cases allowed')
        if not row['valid_initial_fixture']:
            raise ValueError('Fixture qualification failed; cannot silently replace the case')
        target = next(o for o in instance['objects'] if o['is_target'])
        cases.append(dict(alias=row['alias'], instance=instance, case_path=ROOT/row['case_path'],
            record=row, task=dict(target_category=target['asset']['kind'], nominal_rgba=target['asset']['rgba'],
                minimum_lift_m=.1, stable_s=1., terminal_mode='held')))
    if len(cases) != 4:
        raise ValueError('Exactly four fixed training cases required')
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--proposal', required=True, type=Path)
    args = parser.parse_args()
    create(args.output, args.proposal)
