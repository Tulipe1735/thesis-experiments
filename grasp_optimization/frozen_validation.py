"""Pre-register untouched practice placements and evaluate without online tuning."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SUITE = ROOT/'validation/frozen_v1'
SEEDS = [1003, 1004, 1100, 1101, 1102, 1103, 1104, 1105]
SOURCES = ['vision_grasp.py', 'rgbd_cup.py', 'arm_planner.py', 'pantry_robot.py', 'pantry_scene.py',
           'diagnose_grasp.py', 'verify_grasp.py', 'audit_visual_evidence.py', 'run_direct_grasp.py',
           'assets/robot_profile.json', 'assets/g1/upstream_model.xml',
           'episodes/final_reference_1000/episode_memory.json']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def freeze():
    SUITE.mkdir(parents=True, exist_ok=False)
    folder = ROOT/'scenes/pantry/p01_zones_v01/candidates'
    config = json.loads((folder.parent/'zone_config.json').read_text())
    manifest = dict(created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                    seeds=SEEDS, repeats=2, changed_conditions=['cup table XY and cup yaw'],
                    policy_updates_allowed=False, memory_updates_used=False, model_requests=0,
                    evaluation_scope='previously untuned practice placements; not formal held-out benchmark',
                    placement_sampling='six uniform proposals within approved center rectangle; no IK/outcome rejection',
                    acceptance='unchanged independent 10cm opposing-grip 1s verifier',
                    sources={name:digest(ROOT/name) for name in SOURCES}, candidates={})
    for seed in SEEDS:
        path = folder/f'P01_native_v01_practice_{seed}.json'
        if seed >= 1100:
            if path.exists():
                raise FileExistsError(path)
            rng = random.Random(f'frozen-visual-eval-v1:{config["config_sha256"]}:{seed}')
            x0, x1, y0, y1 = config['sampling_center_rectangle_xy_m']
            xy = [rng.uniform(x0, x1), rng.uniform(y0, y1)]
            candidate = dict(instance_id=f'P01_native_v01_practice_{seed}', seed=seed, split='practice',
                             version='frozen-visual-eval-v1', status='UNSCREENED_UNIFORM_APPROVED_ZONE',
                             config_sha256=config['config_sha256'], cup_root_name=config['cup_root_name'],
                             cup_table_xy_m=xy, yaw_in_table_rad=rng.uniform(-math.pi, math.pi),
                             robot_stance=config['stance'], goal=config['goal'], initial_snapshot=None,
                             position_checks=[], rejected_proposals=0, physical_task_trials=0,
                             validation=dict(conservative_footprint=True, position_ik=None,
                                             standing=None, hand_orientation=None, grasp_proven=False))
            candidate['candidate_sha256'] = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode()).hexdigest()
            with path.open('x') as stream:
                json.dump(candidate, stream, indent=2); stream.write('\n')
        manifest['candidates'][str(seed)] = dict(path=str(path.relative_to(ROOT)), sha256=digest(path))
    for name in SOURCES:
        destination = SUITE/'sources'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, destination)
    write(SUITE/'manifest.json', manifest)
    print('FROZEN_BEFORE_RUNS', SUITE, SEEDS, flush=True)


def check_frozen():
    manifest = json.loads((SUITE/'manifest.json').read_text())
    for name, sha in manifest['sources'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Frozen source changed: '+name)
    for item in manifest['candidates'].values():
        if digest(ROOT/item['path']) != item['sha256']:
            raise ValueError('Frozen candidate changed')
    return manifest


def evaluate():
    manifest = check_frozen()
    rows = []
    for seed in manifest['seeds']:
        for repeat in range(1, manifest['repeats']+1):
            check_frozen()
            folder = ROOT/'episodes'/f'frozen_v1_{seed}_repeat_{repeat}'
            result_path = folder/'frozen_trial.json'
            if result_path.exists():
                rows.append(json.loads(result_path.read_text()))
                continue
            if folder.exists():
                raise RuntimeError('Partial trial requires inspection, not overwrite: '+str(folder))
            print('FROZEN_TRIAL_START', seed, repeat, flush=True)
            log = SUITE/f'{seed}_repeat_{repeat}.log'
            with log.open('w') as stream:
                process = subprocess.run([sys.executable, str(ROOT/'vision_grasp.py'), '--seed', str(seed),
                                          '--output', str(folder)], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
                if (folder/'environment_result.json').exists():
                    subprocess.run([sys.executable, str(ROOT/'verify_grasp.py'), str(folder)], cwd=ROOT,
                                   stdout=stream, stderr=subprocess.STDOUT)
                    subprocess.run([sys.executable, str(ROOT/'audit_visual_evidence.py'), str(folder)], cwd=ROOT,
                                   stdout=stream, stderr=subprocess.STDOUT)
            environment = json.loads((folder/'environment_result.json').read_text()) if (folder/'environment_result.json').exists() else None
            verification = json.loads((folder/'independent_verification.json').read_text()) if (folder/'independent_verification.json').exists() else None
            row = dict(seed=seed, repeat=repeat, episode_id=folder.name, exit_code=process.returncode,
                       verified_success=bool(verification and verification['verified_success']),
                       environment=environment, verification=verification,
                       source_freeze_sha256=digest(SUITE/'manifest.json'))
            write(result_path, row)
            rows.append(row)
            write(SUITE/'results.json', rows)
            print('FROZEN_TRIAL_RESULT', seed, repeat, row['verified_success'],
                  environment.get('agent_stop_reason') if environment else 'SETUP_ERROR', flush=True)
    import numpy as np
    pairs = []
    for seed in manifest['seeds']:
        folders = [ROOT/'episodes'/f'frozen_v1_{seed}_repeat_{i}' for i in (1, 2)]
        with np.load(folders[0]/'trajectory.npz') as a, np.load(folders[1]/'trajectory.npz') as b:
            same = {key: bool(np.array_equal(a[key], b[key])) for key in a.files}
        pairs.append(dict(seed=seed, exact_repeat_arrays=same,
                          successes=sum(r['verified_success'] for r in rows if r['seed']==seed)))
    summary = dict(placements=len(manifest['seeds']), repetitions=len(rows),
                   successful_placements=sum(p['successes']==2 for p in pairs),
                   successful_runs=sum(r['verified_success'] for r in rows),
                   duplicate_resets_are_not_independent_trials=True,
                   frozen_sources_unchanged=bool(check_frozen()), pairs=pairs,
                   formal_success_rate_claim=False)
    write(SUITE/'summary.json', summary)
    print('FROZEN_SUITE_DONE', json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['freeze', 'run', 'check'])
    args = parser.parse_args()
    if args.mode == 'freeze': freeze()
    elif args.mode == 'run': evaluate()
    else: print(json.dumps(check_frozen(), indent=2))
