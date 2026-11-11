"""Near-side generated T03 curriculum and shared, bounded adaptive recipe outlet.

Uses the original frozen sampler code with an explicit position-cell parameter
adapter. No coordinates are selected by observed policy success.
"""
import copy
import math
import signal
import time
import types
from pathlib import Path
import mujoco
import numpy as np
from . import tp01
from .t03_runtime import BudgetPlant, platter_from_camera
from .agent import check_source
from experiments.t0_agent_v1 import tabletop_dataset as D
from experiments.t0_agent_v1.common import write_new,relative,sha
from experiments.t0_agent_v1.adaptive_reuse_grasp import (AdaptiveGrasp,AdaptivePort,DEFAULTS,
    validate_adaptive_recipe,parameters_for,PROGRAM)
from experiments.t0_agent_v1.tabletop_training_plant import independent_verify,set_left_hand_impedance
from experiments.t0_agent_v1.train_tp01 import body_packet
from experiments.grow_up_v2.isolation.worker import Worker

BASE_SOURCE='''def act(observation, task, state):
    return {"action":{"op":"done"},"state":{"parameters":{}}}
'''


def cells(config):
    return [{'id':f'near_{i}_{j}','frame':'table','center_xy_m':[x,y],
        'jitter_xy_m':config['jitter_m'],'partition':'test' if (i+j)%3==0 else 'train'}
        for i,y in enumerate(config['y_centers_m']) for j,x in enumerate(config['x_centers_m'])]


def generate(slot,grid):
    namespace=dict(D.make_instance.__globals__)
    namespace['position_cells']=lambda:copy.deepcopy(grid)
    sampler=types.FunctionType(D.make_instance.__code__,namespace,D.make_instance.__name__,D.make_instance.__defaults__)
    return sampler(slot)


def recipe_reply(reply):
    if type(reply) is not dict or set(reply)!={'action','state'} or reply['action']!={'op':'done'}:
        raise ValueError('recipe output requires exactly action={op:done} and state')
    if type(reply['state']) is not dict or set(reply['state'])!={'parameters'}:
        raise ValueError('state requires exactly parameters')
    recipe=validate_adaptive_recipe({'program':PROGRAM,'parameters':reply['state']['parameters'],'by_category':{}})
    return parameters_for(recipe,'fruit')


def execute(case,out,source,open_source,caps):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);check_source(source)
    plant=BudgetPlant(case['instance'],case['folder'],mujoco.MjModel.from_xml_path(str(case['folder']/'pantry_G1.xml')),out,caps['simulation_s'])
    plant.command_count=0;plant.caps=caps;plant.started=time.monotonic()
    error=None;feedback=[];stage='configure';controller=None;calls=0;security={};port=None
    previous=signal.getsignal(signal.SIGALRM)
    def timeout(signum,frame):raise TimeoutError('EPISODE_WALL_BUDGET_EXCEEDED')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,caps['wall_s'])
    try:
        plant.head_image(out/'initial_head.jpg')
        with Worker(source,body_packet(),wall_timeout=5.,cpu_seconds=120) as worker:
            security['recipe']=worker.security
            reply=worker.act(plant.observation(),{'phase':'configure','target_category':'fruit'});calls+=1
            params=recipe_reply(reply);write_new(out/'recipe_binding.json',{'reply':reply,'parameters':params})
        impedance=set_left_hand_impedance(plant.model,params['hand_kp'],params['hand_kd'])
        for name in impedance['joints']:
            i=plant.ai[name];plant.kp[i]=params['hand_kp'];plant.kd[i]=params['hand_kd']
        write_new(out/'left_hand_impedance.json',impedance)
        port=AdaptivePort(plant,params);folder=out/'tools';folder.mkdir()
        controller=AdaptiveGrasp(port,folder,case['public'],params)
        stage='reuse_hand_open'
        with Worker(open_source,body_packet(),wall_timeout=5.,cpu_seconds=120) as worker:
            security['hand_open']=worker.security
            for _ in range(60):
                reply=worker.act(plant.observation(),{});calls+=1
                if reply['action']['op']=='done':break
                response=plant.dispatch(reply['action'])
                if response['status']!='EXECUTED':raise RuntimeError('HAND_OPEN_REJECTED')
            else:raise RuntimeError('HAND_OPEN_BUDGET')
        port.invoke('wait',{'seconds':.6})
        for stage in ['locate','preflight','prepare','preflight','approach','close_and_test','lift_and_hold','transfer','lower','release_and_retreat']:
            if stage=='transfer':
                goal=next(x for x in case['instance']['objects'] if x['asset']['kind']=='platter')
                controller.target=platter_from_camera(plant,goal['asset']);controller.tray={'source':'head_RGBD_visible_platter'}
                write_new(out/'placement_target.json',{'target_pelvis_m':controller.target.tolist(),'truth':False})
            if stage=='release_and_retreat':
                port.hold_targets=None
            result=getattr(controller,stage)()
            feedback.append({'stage':stage,'result':result,'phase':controller.phase})
            if stage=='preflight' and not result['reachable']:raise RuntimeError('ADAPTIVE_APPROACH_PREFLIGHT_REJECTED')
            if plant.guard:raise RuntimeError('ROBOT_GUARD:'+plant.guard)
    except Exception as exc:
        error={'type':type(exc).__name__,'message':str(exc)[:700],'stage':stage}
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        if controller:controller.save()
        runtime=plant.save(error,{'stage':stage,'phase':controller.phase if controller else None},security,calls)
    verdict=independent_verify(out,case['instance'],plant.model,initial_valid=case['ready'])
    write_new(out/'verdict.json',verdict);write_new(out/'tool_feedback.json',feedback)
    result={'task_id':case['instance']['id'],'success':verdict['verified_task_success'],'error':error,
        'commands':plant.command_count,'worker_calls':calls,'simulation_s':runtime['simulation_seconds'],
        'wall_s':time.monotonic()-plant.started,'source_sha256':__import__('hashlib').sha256(source.encode()).hexdigest(),
        'initial_hash':plant.initial_hash,'runtime':runtime,'verdict':relative(out/'verdict.json')}
    write_new(out/'result.json',result);return result
