"""T02-only same-initial controls: replay recorded engineering motor commands.

Privileged recorded motor targets are confined to the positive reference.
No model calls, no policy training, no T01 execution or optimization.
"""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'experiments/grow_up_harness_v2'))
from harness.tp01 import TickRecordedRobot
from harness.local_reach_v3 import timing_quality
from experiments.t0_agent_v1.common import read,relative,sha,write_new
from experiments.t0_agent_v1.tray_verify import verify
import numpy as np
SOURCE=ROOT/'experiments/t0_agent_v1/tray_20261025_repair_003/episodes/2401_T02_scripted'


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    ref=read(SOURCE/'model_reference.json');events=read(SOURCE/'physics_events.json')
    action_paths=sorted(SOURCE.glob('cup_attempt_*/actions.json'))
    actions=[a for p in action_paths for a in read(p) if 'result' in a and 'simulation_seconds' in a['result']]
    if len(actions)!=len(events)-1 or any(abs(a['result']['simulation_seconds']-e['simulation_seconds'])>1e-8 for a,e in zip(actions,events[1:])):
        raise ValueError('recorded requests do not align with motor events')
    write_new(out/'registration.json',{'date':'2026-11-07','task':'T02','boundary':'simulation',
        'status':'registered_before_physics','initial':relative(SOURCE/'initial_state.npz'),
        'inputs':{relative(p):sha(p) for p in [SOURCE/'initial_state.npz',SOURCE/'instance.json',SOURCE/'physics_events.json',ROOT/ref['path'],Path(__file__),Path(verify.__code__.co_filename)]+action_paths},
        'prediction':'wait fails; engineering motor replay reproduces three-cup success on seed 2401 with no sample gaps >0.051 s',
        'falsification':'negative succeeds, positive fails, or physical final state differs from recorded reference',
        'baselines':{'original_failure':'2400: perception after two cups; 2402: approach tracking',
            'fallback':'none','negative':'wait on same initial','positive':'recorded motor target replay','treatment':'none; qualification before practice'},
        'budget':{'episodes':2,'simulation_s':180,'model_calls':0,'retries':0},
        'classification':'engineering reference, not Agent authorship or generalization',
        'actual_instance':read(SOURCE/'instance.json'),'recording':'integer-ticks-v1'})
    rows=[]
    for arm in ('negative_wait','positive_motor_replay'):
        folder=out/arm;folder.mkdir();episode=folder/'episode';episode.mkdir()
        write_new(episode/'instance.json',read(SOURCE/'instance.json'))
        robot=TickRecordedRobot(episode,read(SOURCE/'instance.json'),budget=180,
                                scene_path=ROOT/ref['path'],initial_state=SOURCE/'initial_state.npz')
        calls=0
        error=None
        try:
            if arm=='negative_wait':robot.advance(2.,'negative_wait')
            else:
                robot.advance(events[0]['requested_seconds'],events[0]['category'])
                for action,event in zip(actions,events[1:]):
                    if event['category']=='action':
                        response=robot.set_joints(event['joints'],duration=action['arguments']['duration']);calls+=1
                        if response['status']!='EXECUTED':
                            raise ValueError(f"positive motor command failed: {response['status']}")
                    else:robot.advance(action['arguments']['seconds'],event['category'])
                    if robot.guard:break
        except ValueError as exc:
            error={"type":type(exc).__name__,"message":str(exc)}
        finally:robot.finish()
        verdict=verify(episode,execution_error=error)
        with np.load(episode/'trajectory.npz',allow_pickle=False) as trace:quality=timing_quality(trace['time'])
        same=True
        with np.load(SOURCE/'initial_state.npz',allow_pickle=False) as a,np.load(episode/'initial_state.npz',allow_pickle=False) as b:
            same=set(a.files)==set(b.files) and all(np.array_equal(a[k],b[k]) for k in a.files)
        with np.load(SOURCE/'final_state.npz',allow_pickle=False) as a,np.load(episode/'final_state.npz',allow_pickle=False) as b:
            final_same=set(a.files)==set(b.files) and all(np.array_equal(a[k],b[k]) for k in a.files)
        row={'arm':arm,'success':verdict['verified_success'],'initial_equal':same,'final_equal_to_reference':final_same,
             'valid_initial':verdict['initial_valid'],'protection':verdict['protection'],'execution_error':error,
             'simulation_s':robot.data.time,'motor_commands':calls,'model_calls':0,'timing_quality':quality,
             'verdict':relative(episode/'independent_verification.json')}
        row['qualified']=not error and same and verdict['initial_valid'] and not verdict['protection'] and not quality['gaps'] and verdict['verified_success']==(arm=='positive_motor_replay')
        if arm=='positive_motor_replay':row['qualified'] &= final_same
        write_new(folder/'result.json',row);rows.append(row);print(row,flush=True)
        if not row['qualified']:break
    result={'controls':rows,'qualified':len(rows)==2 and all(r['qualified'] for r in rows),'agent_practice_started':False}
    write_new(out/'results.json',result)
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
