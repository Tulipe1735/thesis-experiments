"""Physical geometry fixtures + complete-trace rejection controls; NOT robot tasks."""
import copy,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'experiments/grow_up_harness_v2')]
from harness import tp01,t03_evaluator as E
from experiments.t0_agent_v1 import tabletop_dataset as D,diversity_predicates as V
from experiments.t0_agent_v1.common import read,write_new,sha,relative
import numpy as np,mujoco


def run(out):
 out.mkdir(parents=True,exist_ok=False)
 source=ROOT/'experiments/grow_up_harness_v2/runs/t03_train_until_20261110_001/tasks/train/T03_near_train_113005/instance.json'
 settings=[('sphere_upright','orange_68mm_proxy__train_1',0.),('sphere_side','orange_68mm_proxy__train_1',math.pi/2),
 ('sphere_inverted','orange_68mm_proxy__train_1',math.pi),('ellipsoid_inverted','apple_ellipsoid_proxy__train_1',math.pi)]
 write_new(out/'registration.json',{'date':'2026-11-11','authorization':'user explicit evaluator correction approval',
 'purpose':'evaluator calibration only; no G1 robot, no training task success, no holdout execution',
 'fixtures':settings,'physics_s_per_fixture':3.,'count':4,'policy_calls':0,'model_calls':0,
 'acceptance':'all four actual physically settled fixtures have true SupportedIn for final >=1 s; geometry matches direct MuJoCo collision-shape lowest point; full robot task success must remain false without robot evidence; all constructed full-trace negatives must fail',
 'sources':{relative(p):sha(p) for p in [source,Path(__file__),ROOT/'experiments/grow_up_harness_v2/harness/t03_evaluator.py',ROOT/'experiments/grow_up_harness_v2/harness/t03_fruit_height_audit.py',Path(V.__file__)]}})
 results=[];reference=None
 for name,asset,angle in settings:
  folder=out/name;folder.mkdir();x=copy.deepcopy(read(source));x['id']='evaluator_'+name
  fruit=next(o for o in x['objects'] if o['is_target']);plate=next(o for o in x['objects'] if o['asset']['kind']=='platter')
  fruit['asset']=D.asset_library()[asset];radii=np.array(fruit['asset']['radii_m']);q=[math.cos(angle/2),math.sin(angle/2),0.,0.];ro=V.rotation(q);rp=V.rotation(plate['quaternion_wxyz'])
  extent=float(np.linalg.norm((rp.T@ro)[2]*radii));center=np.asarray(plate['position_m'])+rp@[0,0,plate['asset']['floor_m']+extent+.0005]
  fruit['position_m']=(center-ro@[0,0,radii[2]]).tolist();fruit['quaternion_wxyz']=q;fruit['initial_support']='platter'
  write_new(folder/'fixture.json',x);model=D.compile_scene(x,folder/'fixture.xml');data=mujoco.MjData(model);frames=[];geometry=[]
  for i in range(1500):
   mujoco.mj_step(model,data)
   if (i+1)%25==0:
    f=V.snapshot(model,data,x);frames.append(f)
    gid=model.geom('fruit_1_fruit').id;pid=model.body('platter').id
    rot=data.xmat[pid].reshape(3,3);local=rot.T@(data.geom_xpos[gid]-data.xpos[pid]);rel=rot.T@data.geom_xmat[gid].reshape(3,3)
    lowest=float(local[2]-np.linalg.norm(rel[2]*radii)-plate['asset']['floor_m'])
    from harness.t03_fruit_height_audit import geometry as measured
    pred=measured(x,f,'fruit_1','platter')['geometric_bottom_height_error_m']
    geometry.append({'time':data.time,'mujoco_geom_lowest_error_m':lowest,'predicate_lowest_error_m':pred})
  outcome=E.evaluate_trace(x,frames,initial_valid=True)
  write_new(folder/'frames.json',frames);write_new(folder/'geometry.json',geometry);write_new(folder/'verdict.json',outcome)
  good=outcome['goal_satisfied'] and not outcome['verified_task_success'] and max(abs(g['mujoco_geom_lowest_error_m']-g['predicate_lowest_error_m']) for g in geometry)<1e-10
  results.append({'fixture':name,'pass':bool(good),'goal':outcome['goal_satisfied'],'stable_s':outcome['terminal_simultaneous_stable_s'],'robot_task_success':outcome['verified_task_success']})
  if reference is None:reference=(x,frames)
 # Reuse a real settled physical fixture, add explicit robot evidence only as a unit-level trace acceptance probe.
 # It is NOT a robot execution or a training success.
 x,frames=reference;valid=copy.deepcopy(frames[-25:])
 for f in valid:f['robot']={'tilt_deg':0.,'drift_m':0.}
 controls=[]
 def check(label,trace,expected,**kw):
  v=E.evaluate_trace(x,trace,initial_valid=kw.pop('initial_valid',True),**kw);ok=v['verified_task_success']==expected
  controls.append({'case':label,'pass':ok,'expected':expected,'result':v,'synthetic_robot_evidence_not_task_success':True})
 check('full_1s_positive_trace',valid,True)
 check('too_short',valid[:10],False)
 shifted=copy.deepcopy(valid)
 for i,f in enumerate(shifted):f['time']=i*.06
 check('sample_gap',shifted,False)
 check('invalid_initial',valid,False,initial_valid=False)
 invalid=copy.deepcopy(valid)
 for f in invalid:f['robot']['tilt_deg']=6.
 check('invalid_robot',invalid,False)
 check('execution_error',valid,False,execution_error={'type':'DeliberateTestError'})
 check('protection',valid,False,protection='DELIBERATE_TEST_PROTECTION')
 for label,edit in [('floating',lambda f:f['objects']['fruit_1']['upward_support_N'].clear()),
   ('sidewall_only',lambda f:f['objects']['fruit_1'].update(upward_support_N={'platter_rim':2.})),
   ('not_released',lambda f:f['objects']['fruit_1'].update(hand_contact_N=.2)),
   ('too_deep',lambda f:f['objects']['fruit_1']['position_m'].__setitem__(2,f['objects']['fruit_1']['position_m'][2]-.01))]:
  bad=copy.deepcopy(valid)
  for f in bad:edit(f)
  check(label,bad,False)
 write_new(out/'trace_boundary_controls.json',controls)
 write_new(out/'result.json',{'physical_fixtures':results,'trace_controls':len(controls),
 'all_pass':all(r['pass'] for r in results) and all(c['pass'] for c in controls),
 'training_successes':0,'holdout_episodes':0,'physical_fixture_seconds':12.,'synthetic_robot_trace_controls_are_not_robot_executions':True})
 print(results,'all controls',all(c['pass'] for c in controls),flush=True)

if __name__=='__main__':run(Path(sys.argv[1]))
