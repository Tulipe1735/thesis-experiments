"""Recompute historical T02 local slot outcomes without changing any run."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'experiments/grow_up_harness_v2'))
sys.path.insert(0,str(Path(__file__).parent))
from t02_execution import stable_slot
from experiments.t0_agent_v1.common import read,relative,sha,write_new


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    runs=ROOT/'experiments/grow_up_harness_v2/runs'
    paths=sorted(runs.glob('t02_gen_*/result.json'))+sorted(runs.glob('t02_slot_check_20261105_*/result.json'))
    inputs={relative(p):sha(p) for result in paths for p in
            (result,result.parent/'episode/verified_samples.json',result.parent/'episode/independent_verification.json')}
    write_new(out/'registration.json',{'date':'2026-11-07','boundary':'simulation offline saved-frame replay',
       'prediction':'tray-only successes do not imply designated slot success; no historical files change',
       'falsification':'a historical tray success already satisfies the registered slot hold, or inputs change',
       'slot_xy_m':[-.09,0.],'slot_tolerance_m':.015,'terminal_hold_s':1.,'max_gap_s':.051,'inputs':inputs,
       'source_sha256':{relative(p):sha(p) for p in (Path(__file__),Path(__file__).with_name('t02_execution.py'))}})
    rows=[]
    for path in paths:
        old=read(path);verdict=read(path.parent/'episode/independent_verification.json')
        metrics=stable_slot(read(path.parent/'episode/verified_samples.json'),'task_cup',[-.09,0.])
        valid=verdict['initial_valid'] and verdict['no_external_forces'] and verdict['equality_constraints']==0 and not verdict['execution_error'] and not verdict['protection']
        rows.append({'original':relative(path),'old_single_cup_success':old['single_cup_success'],
           'old_slot_success':old.get('slot_success'),'new_slot_success':bool(valid and metrics['stable_slot_success']),
           **metrics,'whole_task_success':verdict['verified_success']})
    result={'rows':rows,'count':len(rows),'new_slot_successes':sum(r['new_slot_success'] for r in rows),
            'historical_inputs_unchanged':all(sha(ROOT/p)==h for p,h in inputs.items())}
    write_new(out/'results.json',result);print(result,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
