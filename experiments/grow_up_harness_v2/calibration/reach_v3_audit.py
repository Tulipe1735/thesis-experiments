"""Read-only historical v2/v3 replay; no trajectory copies or repaired frames."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/grow_up_harness_v2'))
from harness import local_reach_v3 as V


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    source=args.source.resolve(); out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    reg=json.loads((source/'registration.json').read_text())
    tasks={t['task_id']:t['public'] for split in ('train_tasks','heldout_tasks') for t in reg[split]['tasks']}
    cases=sorted(source.rglob('verdict.json'))
    input_paths = {source/'registration.json'}
    for p in cases:
        input_paths.update((p,p.with_name('result.json')))
        episode=p.parent/'episode'
        input_paths.update(episode/name for name in ('trajectory.npz','initial_state.npz','model_reference.json','environment_result.json'))
        reference=json.loads((episode/'model_reference.json').read_text())
        input_paths.add(ROOT/reference['path'])
    inputs={str(p.relative_to(ROOT)):sha(p) for p in sorted(input_paths)}
    registration={'date':'2026-11-07','boundary':'simulation; offline replay only','inputs':inputs, 'cases':[str(p.relative_to(ROOT)) for p in cases],
        'prediction':'No v2 success changes: strict 0.051 gap rule remains. Historical gaps remain insufficient evidence, never filled.',
        'falsification':'Any success verdict changes or any historical file changes',
        'sources':{str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),Path(V.__file__),Path(V.local_reach.__file__))}}
    (out/'registration.json').write_text(json.dumps(registration,indent=1)+'\n')
    rows=[]
    for index,p in enumerate(cases):
        old=json.loads(p.read_text());result=json.loads(p.with_name('result.json').read_text())
        task_id=next((part for part in p.parts if part in tasks), None)
        if task_id is None:
            if p.parent.name != 'control_negative':
                raise ValueError(f'unknown task for {p}')
            task_id=reg['train_tasks']['tasks'][0]['task_id']
        verdict=V.evaluate(p.parent/'episode',tasks[task_id],start_s=old['start_s'],
                           end_s=old['end_s'],execution_error=result['error'])
        verdict.pop('rows')
        with (out/f'verdict_{index:03d}.json').open('x') as f: json.dump(verdict,f,indent=1)
        rows.append({'original':str(p.relative_to(ROOT)),'task':task_id,'v2':old['verified_local_success'],
            'v3':verdict['verified_local_success'],'evidence_status':verdict['evidence_status'],
            'gaps':len(verdict['timing_quality']['gaps']),'v3_verdict':f'verdict_{index:03d}.json'})
    summary={'rows':rows,'count':len(rows),'changed_verdicts':sum(r['v2']!=r['v3'] for r in rows),
        'historical_inputs_unchanged':all(sha(ROOT/p)==h for p,h in inputs.items())}
    (out/'results.json').write_text(json.dumps(summary,indent=1)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'}),flush=True)
if __name__=='__main__':main()
