"""Real-state post-release finish leaf with the authorized independent verifier.

Only the old optional raise_clear_of_tray segment is replaced. Opening, backward
retreat, original final settle, grasp and camera-relative placement stay intact.
"""
import types
from pathlib import Path
from . import t03_curriculum as C,t03_placement as P,t03_evaluator as E
from .agent import check_source
from experiments.t0_agent_v1.common import write_new
from experiments.t0_agent_v1.train_tp01 import body_packet
from experiments.grow_up_v2.isolation.worker import Worker


def execute(case,out,grasp_source,open_source,placement_source,finish_source,caps):
 out=Path(out);check_source(finish_source)
 def target(plant,goal):
  center=P.platter_from_camera(plant,goal)
  observation={'robot':plant.observation(),'platter_center_pelvis_m':center.tolist(),'max_fruit_radius_m':.041}
  with Worker(placement_source,body_packet(),wall_timeout=5.,cpu_seconds=120) as worker:
   reply=worker.act(observation,{'phase':'placement_target','object_count':1,'hold_s':1.});offset=P.validate(reply)
   write_new(out/'placement_invocation.json',{'observation':observation,'reply':reply,'worker_security':worker.security})
  return center+offset
 class FinishGrasp(C.AdaptiveGrasp):
  def linear(self,stage,position,duration):
   if stage!='raise_clear_of_tray':return super().linear(stage,position,duration)
   start=float(self.port.plant.data.time);calls=[]
   with Worker(finish_source,body_packet(),wall_timeout=5.,cpu_seconds=120) as worker:
    for _ in range(32):
     obs=self.port.plant.observation();reply=worker.act(obs,{'phase':'post_release_finish','hold_s':1.,'released_and_backward_retreat_executed':True})
     if type(reply) is not dict or set(reply)!={'action','state'}:raise ValueError('finish requires exactly action/state')
     action=reply['action'];calls.append({'time_s':obs['simulation_seconds'],'reply':reply})
     if action.get('op')=='done':
      if self.port.plant.data.time-start<1.-1e-8:raise ValueError('finish must physically dwell >=1s')
      write_new(out/'finish_invocation.json',{'calls':calls,'worker_security':worker.security,'dwell_s':self.port.plant.data.time-start,
       'replaced_segment':stage,'extra_arm_motion':False});return
     if action.get('op')=='fail':raise RuntimeError('FINISH_REJECTED:'+str(action.get('reason')))
     if set(action)!={'op','duration'} or action['op']!='wait':raise ValueError('finish leaf may only wait, done or fail; no joint/Cartesian actions')
     if self.port.plant.data.time-start+action['duration']>3.+1e-8:raise RuntimeError('FINISH_3S_BUDGET')
     response=self.port.plant.dispatch(action)
     if response['status']!='EXECUTED':raise RuntimeError('FINISH_WAIT:'+str(response))
   raise RuntimeError('FINISH_CALL_BUDGET')
 namespace=dict(C.execute.__globals__);namespace.update(AdaptiveGrasp=FinishGrasp,platter_from_camera=target,independent_verify=E.verify)
 run=types.FunctionType(C.execute.__code__,namespace,C.execute.__name__,C.execute.__defaults__)
 result=run(case,out,grasp_source,open_source,caps)
 digest=__import__('hashlib').sha256
 write_new(out/'artifact_execution.json',{'grasp_source_sha256':digest(grasp_source.encode()).hexdigest(),
  'placement_source_sha256':digest(placement_source.encode()).hexdigest(),'finish_source_sha256':digest(finish_source.encode()).hexdigest(),
  'placement_called':(out/'placement_invocation.json').exists(),'finish_called':(out/'finish_invocation.json').exists(),
  'evaluator_version':E.VERSION,'evaluator_authorization':'user approved 2026-11-11','real_state_continuation':True,'hidden_resets':0})
 return result
