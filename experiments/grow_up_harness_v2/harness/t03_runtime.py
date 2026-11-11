"""T03 adapters: numeric route proposals, original body limits, independent replay.

The artifact's native init/act computes route proposals only. The trusted adapter
checks IK and dispatches the existing grasp/place stages. No scene truth goes to
candidate code. Engineering references explicitly use truth for the platter pose.
"""
import copy
import math
import signal
import time
from pathlib import Path
import numpy as np
import mujoco
from . import tp01
from .agent import check_source
from experiments.t0_agent_v1.common import read, write_new, relative
from experiments.t0_agent_v1.tabletop_training_plant import TabletopPlant, independent_verify
from experiments.t0_agent_v1.reuse_grasp import (ReuseGrasp, ReusePort, BASELINE,
    prepared_state, point_cloud, ActionFailure)
from experiments.t0_agent_v1.train_tp01 import body_packet
from experiments.grow_up_v2.isolation.worker import Worker
from arm_planner import ArmPlanner, yaw_rotation

BASE_SOURCE = '''def init(profile):
    return None

def act(observation, task, state):
    return {"action": {"op": "done"}, "state": {"legacy": True}}
'''
ROUTE_INTERFACE = '''Native numeric Worker: init(profile) optional; act(observation, task, state).
Return exactly {"action":{"op":"done"},"state":{"routes":[...]}}.
Each route has exactly {"yaw_rad":float,"offset_m":[x,y,z],"waypoints":[[x,y,z],...]}.
1..8 routes; yaw -pi..pi; offset x=-0.06,y=0,z in [-0.08,0.03].
1..8 finite pelvis-frame waypoints, coordinate absolute bounds <=1.5m.
Last waypoint MUST equal fruit_bottom - Rz(yaw)*offset within 1e-8m.
Observation is {robot: proprioception, fruit: RGB-D fit incl cup_bottom_position_m,
radius_estimate_m, table_plane, fit_rms_m}. No coordinates from dataset or model truth.
Task is {object_count:1,hold_s:1.0}. Profile is existing public robot body packet.
Code may import math, numpy, numpy.linalg; no file/network/process or MuJoCo access.
No set_joints output here: this leaf computes approach waypoints. Trusted adapter
uses existing robot-only IK to validate all waypoints and the following 2cm/12.5cm
lift, then executes bounded existing ReusePort actions. Existing grasp, hold,
transport, lower and release remain unchanged. Do not rewrite them or claim success.
Yaw and sphere-height offset may change only in the supplied bounds; no waist/legs.
'''


def validate_reply(reply, fruit, allow_legacy=False):
    if type(reply) is not dict or set(reply) != {'action','state'} or reply['action'] != {'op':'done'}:
        raise ValueError('route output requires exactly action={op:done} and state')
    state=reply['state']
    if allow_legacy and state == {'legacy':True}: return state
    if type(state) is not dict or set(state) != {'routes'}:
        raise ValueError('state requires exactly routes')
    routes=state['routes']
    if type(routes) is not list or not 1<=len(routes)<=8:
        raise ValueError('state.routes requires 1..8 routes')
    for i,r in enumerate(routes):
        if type(r) is not dict or set(r) != {'yaw_rad','offset_m','waypoints'}:
            raise ValueError(f'routes[{i}] requires yaw_rad,offset_m,waypoints')
        yaw=r['yaw_rad']
        if type(yaw) not in (int,float) or not math.isfinite(yaw) or not -math.pi<=yaw<=math.pi:
            raise ValueError(f'routes[{i}].yaw_rad outside [-pi,pi]')
        off=r['offset_m']; points=r['waypoints']
        if type(off) is not list or len(off)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in off):
            raise ValueError(f'routes[{i}].offset_m requires finite vec3')
        if off[:2]!=[-.06,0.] or not -.08<=off[2]<=.03:
            raise ValueError(f'routes[{i}].offset_m violates retained palm geometry')
        if type(points) is not list or not 1<=len(points)<=8:
            raise ValueError(f'routes[{i}].waypoints requires 1..8 points')
        for point in points:
            if type(point) is not list or len(point)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1.5 for v in point):
                raise ValueError(f'routes[{i}].waypoints requires bounded finite vec3')
        palm=np.asarray(fruit['cup_bottom_position_m'])-yaw_rotation(yaw)@off
        if np.max(np.abs(palm-np.asarray(points[-1])))>1e-8:
            raise ValueError(f'routes[{i}] final waypoint must match observed fruit and offset')
    return state


def checked_routes(state,fruit,proposal,*,phase):
    planner=ArmPlanner(); initial=state
    if phase=='initial':
        initial,prep=prepared_state(planner,state)
        if initial is None:return {'reachable':False,'reason':'preparation_preview_failed','preparation':prep}
    trials=[]
    for r in proposal['routes']:
        data=planner.start(initial);yaw=r['yaw_rad']; goals=r['waypoints']
        palm=np.asarray(goals[-1]); points=goals+[(palm+[0,0,.02]).tolist(),(palm+[0,0,.125]).tolist()]
        rows=[];ok=True
        for index,goal in enumerate(points):
            first=data.site_xpos[planner.site].copy()
            steps=max(1,math.ceil(np.linalg.norm(np.asarray(goal)-first)/.025))
            for step in range(1,steps+1):
                previous=data.qpos[planner.qids].copy()
                result=planner.solve(data,first+(np.asarray(goal)-first)*step/steps,yaw)
                jump=float(np.max(np.abs(data.qpos[planner.qids]-previous)))
                rows.append({'waypoint':index,'step':step,'jump_rad':jump,**result})
                if not result['reachable'] or (index!=0 and jump>.5):ok=False;break
            if not ok:break
        trials.append({'route':r,'reachable':ok,'checked_points':len(rows),'terminal_check':rows[-1]})
        if ok:return {'reachable':True,'selected':r,'trials':trials,'collision_checked':False}
    return {'reachable':False,'trials':trials,'collision_checked':False}


class BudgetPlant(TabletopPlant):
    def dispatch(self,action):
        if self.command_count>=self.caps['commands']:
            raise RuntimeError('COMMAND_BUDGET_EXCEEDED')
        if time.monotonic()-self.started>=self.caps['wall_s']:
            raise TimeoutError('EPISODE_WALL_BUDGET_EXCEEDED')
        self.command_count+=1
        return super().dispatch(action)


class RouteGrasp(ReuseGrasp):
    def __init__(self,port,folder,task,worker,legacy):
        super().__init__(port,folder,task,copy.deepcopy(BASELINE['parameters']))
        self.worker,self.legacy=worker,legacy
        self.route_calls=0; self.route_plan=None; self.last_input=None

    def preflight(self):
        self.last_input={'robot':self.port.state(),'fruit':self.estimate}
        reply=self.worker.act(self.last_input,{'object_count':1,'hold_s':1.})
        proposal=validate_reply(reply,self.estimate,self.legacy);self.route_calls+=1
        write_new(self.folder/f'route_call_{self.route_calls}.json',{'input':self.last_input,'reply':reply})
        if proposal.get('legacy'):
            return super().preflight()
        self.route_plan=checked_routes(self.port.state(),self.estimate,proposal,phase=self.phase)
        write_new(self.folder/f'route_check_{self.route_calls}.json',self.route_plan)
        return self.route_plan

    def approach(self):
        if self.legacy:return super().approach()
        if self.phase!='ready' or not self.route_plan or not self.route_plan['reachable']:
            raise ActionFailure('NO_CHECKED_APPROACH_ROUTE')
        r=self.route_plan['selected'];self.yaw=r['yaw_rad'];self.offset=np.asarray(r['offset_m']);self.palm=np.asarray(r['waypoints'][-1])
        for i,goal in enumerate(r['waypoints']):
            if i==0:
                self.action('candidate_orient','move_ee',side='left',position=goal,
                    quaternion_xyzw=[0.,0.,math.sin(self.yaw/2),math.cos(self.yaw/2)],duration=1.5)
            else:self.linear(f'candidate_waypoint_{i}',goal,2.)
        self.phase='approached'
        return {'status':'APPROACHED','artifact_route':True}


def platter_from_camera(plant,goal_asset):
    """Visible colored procedural platter; no scene body lookup."""
    sensor=plant.rgbd(); rgb=np.asarray(sensor['rgb'],float)/255
    cloud=point_cloud(sensor['depth_m'],sensor['K'],sensor['T_optical_to_pelvis'])
    nominal=np.asarray(goal_asset['rgba'][:3]);nominal/=np.linalg.norm(nominal)
    length=np.linalg.norm(rgb,axis=-1);cos=(rgb@nominal)/np.maximum(length,1e-9)
    valid=np.isfinite(cloud).all(axis=-1)&(cloud[...,0]>.1)&(cloud[...,0]<.7)&(abs(cloud[...,1])<.5)&(cloud[...,2]>.14)&(cloud[...,2]<.21)&(cos>.985)&(length>.1)
    points=cloud[valid]
    if len(points)<100:raise ActionFailure('PLATTER_RGBD_INSUFFICIENT_POINTS')
    lo,hi=np.percentile(points,[2,98],axis=0)
    return np.r_[(lo[:2]+hi[:2])/2, np.percentile(points[:,2],35)]


def execute(case,out,source,open_source,caps,*,reference=False,negative=False,legacy=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    check_source(source)
    plant=BudgetPlant(case['instance'],case['folder'],mujoco.MjModel.from_xml_path(str(case['folder']/'pantry_G1.xml')),out,caps['simulation_s'])
    plant.command_count=0;plant.caps=caps;plant.started=time.monotonic()
    port=ReusePort(plant);folder=out/'tools';folder.mkdir();error=None;stage='initial';feedback=[];security={};calls=0
    previous=signal.getsignal(signal.SIGALRM)
    def timeout(signum,frame):raise TimeoutError('EPISODE_WALL_BUDGET_EXCEEDED')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,caps['wall_s'])
    controller=None
    try:
        plant.head_image(out/'initial_head.jpg')
        if negative:
            stage='negative_wait';port.invoke('wait',{'seconds':.6})
        else:
            stage='reuse_hand_open'
            with Worker(open_source,body_packet(),wall_timeout=5.,cpu_seconds=120) as opener:
                security['hand_open']=opener.security
                for _ in range(60):
                    reply=opener.act(plant.observation(),{}) ;calls+=1
                    if reply['action']['op']=='done':break
                    response=plant.dispatch(reply['action'])
                    if response['status']!='EXECUTED':raise ActionFailure('HAND_OPEN_REJECTED')
                else:raise RuntimeError('HAND_OPEN_CALL_BUDGET')
            port.invoke('wait',{'seconds':.6})
            with Worker(source,body_packet(),wall_timeout=5.,cpu_seconds=120) as worker:
                security['route']=worker.security
                controller=RouteGrasp(port,folder,case['public'],worker,legacy)
                for stage in ['locate','preflight','prepare','preflight','approach','close_and_test','lift_and_hold','transfer','lower','release_and_retreat']:
                    if stage=='transfer':
                        goal=next(x for x in case['instance']['objects'] if x['asset']['kind']=='platter')
                        if reference:
                            b=plant.model.body(goal['name']).id;p=plant.model.body('pelvis').id
                            center=plant.data.xpos[b]+plant.data.xmat[b].reshape(3,3)@[0,0,goal['asset']['floor_m']]
                            target=plant.data.xmat[p].reshape(3,3).T@(center-plant.data.xpos[p])
                        else:target=platter_from_camera(plant,goal['asset'])
                        controller.target=np.asarray(target);controller.tray={'source':'truth_engineering_reference' if reference else 'visible_platter_RGBD'}
                        write_new(out/'placement_target.json',{'target':controller.target.tolist(),'truth_assistance':reference})
                    result=getattr(controller,stage)()
                    feedback.append({'stage':stage,'result':result,'phase':controller.phase})
                    if stage=='preflight' and not result['reachable']:raise ActionFailure('APPROACH_PREFLIGHT_REJECTED')
                    if plant.guard:raise ActionFailure('ROBOT_GUARD:'+plant.guard)
    except Exception as exc:
        error={'type':type(exc).__name__,'message':str(exc)[:700],'stage':stage}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        if controller: calls+=controller.route_calls
        if controller and controller.last_input is not None:
            write_new(out/'route_public_input.json',controller.last_input)
        runtime=plant.save(error,{'stage':stage,'phase':controller.phase if controller else None},security,calls)
    verdict=independent_verify(out,case['instance'],plant.model,initial_valid=case['ready'])
    write_new(out/'tool_feedback.json',feedback)
    write_new(out/'verdict.json',verdict)
    result={'task_id':case['instance']['id'],'success':verdict['verified_task_success'],'error':error,
        'runtime':runtime,'commands':plant.command_count,'worker_calls':calls,
        'simulation_s':runtime['simulation_seconds'],'wall_s':time.monotonic()-plant.started,
        'source_sha256':__import__('hashlib').sha256(source.encode()).hexdigest(),
        'initial_hash':plant.initial_hash,'reference':reference,'negative':negative,
        'verdict':relative(out/'verdict.json')}
    write_new(out/'result.json',result)
    return result
