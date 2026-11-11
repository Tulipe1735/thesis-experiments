"""RGB-D can avoidance leaf: route selection around unchanged grasp endpoint.

Robot-only kinematics and observed obstacle geometry never read scene body poses.
"""
import math
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np
from scipy import ndimage
from scipy.optimize import least_squares

from . import t03_locate_branch as L, t03_locate_temporal as T
from . import t03_curriculum as C
from experiments.grow_up_v2.isolation.worker import Worker
from experiments.t0_agent_v1.adaptive_reuse_grasp import (
    ArmPlanner, checked_route, grasp_rotation, route_goals)
from experiments.t0_agent_v1.common import write_new
from experiments.t0_agent_v1.reuse_grasp import ActionFailure, point_cloud
from experiments.t0_agent_v1.train_tp01 import body_packet

VERSION = 't03-rgbd-can-approach-v1'
LOW_CONFIDENCE = T.LOW_CONFIDENCE
MIN_CLEARANCE = .006
MIN_TABLE_CLEARANCE = .001
INTERFACE = ('act(observation,task,state) returns exactly {"action":{"op":"done"},'
             '"state":{"route_id":string_or_null}}. observation.routes is a bounded list of '
             'precomputed {route_id,reachable,obstacle_clearance_m,table_clearance_m}. '
             'Return default if reachable, obstacle clearance>=0.006 and table clearance>=0.001; otherwise choose '
             'the first such alternate. Null if no safe candidate. Host owns all motion. '
             'Do not change parameters, geometry, permissions or success judgement.')


def cylinders_from_rgbd(sensor, estimate):
    rgb = np.asarray(sensor['rgb'],float)/255.
    cloud = point_cloud(sensor['depth_m'],sensor['K'],sensor['T_optical_to_pelvis'])
    plane = np.asarray(estimate['table_plane'])
    height = cloud[...,2]-(cloud[...,:2]@plane[:2]+plane[2])
    mask = (np.isfinite(cloud).all(axis=-1) & (cloud[...,0]>.1) & (cloud[...,0]<.8)
            & (cloud[...,1]>.1) & (cloud[...,1]<.7) & (height>.012) & (height<.20)
            & (np.ptp(rgb,axis=-1)<.12) & (rgb.mean(axis=-1)>.18))
    labels,count = ndimage.label(mask)
    obstacles = []
    for i in range(1,count+1):
        points = cloud[labels==i]
        if len(points)<30:
            continue
        lo,hi = np.percentile(points,[3,97],axis=0)
        if max(hi[:2]-lo[:2])>.14 or hi[2]-lo[2]<.025:
            continue
        wall = points[(points[:,2]>np.percentile(points[:,2],10))
                      & (points[:,2]<np.percentile(points[:,2],75))]
        fits = []
        for delta in (0.,.02,.04):
            start = np.r_[np.median(wall[:,:2],axis=0)+[delta,0.],.025]
            fit = least_squares(lambda v:np.linalg.norm(wall[:,:2]-v[:2],axis=1)-v[2],
                start,bounds=(np.r_[lo[:2]-.08,.015],np.r_[hi[:2]+.08,.065]),
                loss='soft_l1',f_scale=.001)
            fits.append(fit)
        fit = min(fits,key=lambda f:float(np.mean(f.fun**2)))
        rms = float(np.sqrt(np.mean(fit.fun**2)))
        if rms>.004 or not fit.success or fit.x[2]>.060:
            raise ActionFailure('VISIBLE_CAN_FIT_REJECTED')
        center = fit.x[:2]
        floor = float(plane@np.r_[center,1.])
        obstacles.append({'center_xy_m':center.tolist(),'radius_m':float(fit.x[2]+.004),
                          'bottom_m':floor,'top_m':float(np.max(points[:,2])+.004),
                          'fit_rms_m':rms,'pixels':len(points),'source':'current_head_RGBD_gray_component'})
    return obstacles


def cylinder_distance(points, obstacle):
    radial = np.linalg.norm(points[:,:2]-obstacle['center_xy_m'],axis=1)-obstacle['radius_m']
    mid=(obstacle['top_m']+obstacle['bottom_m'])/2
    vertical=abs(points[:,2]-mid)-(obstacle['top_m']-obstacle['bottom_m'])/2
    pair=np.c_[radial,vertical]
    return np.linalg.norm(np.maximum(pair,0),axis=1)+np.minimum(np.max(pair,axis=1),0)


def collision_points(model):
    shapes=[]
    for g in range(model.ngeom):
        name=model.body(int(model.geom_bodyid[g])).name or ''
        if not name.startswith(('left_hand_','left_wrist_')) or not model.geom_contype[g]:
            continue
        kind=model.geom_type[g]
        if kind==mujoco.mjtGeom.mjGEOM_MESH:
            mesh=model.geom_dataid[g]
            v=model.mesh_vert[model.mesh_vertadr[mesh]:model.mesh_vertadr[mesh]+model.mesh_vertnum[mesh]].copy()
            f=model.mesh_face[model.mesh_faceadr[mesh]:model.mesh_faceadr[mesh]+model.mesh_facenum[mesh]]
            triangles=v[f]
            points=np.vstack([v,triangles.mean(axis=1),(triangles[:,0]+triangles[:,1])/2,
                              (triangles[:,1]+triangles[:,2])/2,(triangles[:,2]+triangles[:,0])/2])
        elif kind==mujoco.mjtGeom.mjGEOM_BOX:
            size=model.geom_size[g]
            axes=[np.linspace(-x,x,max(2,math.ceil(2*x/.004)+1)) for x in size]
            points=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1).reshape(-1,3)
        else:
            raise ValueError('Unsupported hand collision primitive:'+str(kind))
        shapes.append((g,points))
    return shapes


def route_clearance(state, goals, yaw, parameters, obstacles, plane):
    planner=ArmPlanner()
    # Retain the original full preflight, including lift reachability and robot self collision.
    plan=checked_route(planner,state,goals,yaw,parameters)
    if not plan['reachable']:
        return plan, None, None
    data=planner.start(state)
    shapes=collision_points(planner.model)
    obstacle_margin=1.
    table_margin=1.
    clearance_rows=[]
    for stage,goal,*_ in goals:
        if stage in ('test_lift','main_lift'):
            break
        start=data.site_xpos[planner.site].copy()
        count=1 if stage=='orient_clear' else max(1,math.ceil(np.linalg.norm(np.asarray(goal)-start)/.01))
        for k in range(1,count+1):
            planner.solve(data,start+(np.asarray(goal)-start)*k/count,yaw)
            mujoco.mj_kinematics(planner.model,data)
            points=np.vstack([local@data.geom_xmat[g].reshape(3,3).T+data.geom_xpos[g] for g,local in shapes])
            table_margin=min(table_margin,float(np.min(points[:,2]-(points[:,:2]@plane[:2]+plane[2]))))
            for obstacle in obstacles:
                margin=float(np.min(cylinder_distance(points,obstacle)))
                if margin<obstacle_margin:
                    clearance_rows.append({'stage':stage,'step':k,'minimum_obstacle_m':margin})
                    obstacle_margin=margin
    plan['observed_clearance_minima']=clearance_rows
    return plan,obstacle_margin,table_margin


def validate_reply(reply, candidates):
    if (type(reply) is not dict or set(reply)!={'action','state'} or reply['action']!={'op':'done'}
            or type(reply['state']) is not dict or set(reply['state'])!={'route_id'}):
        raise ValueError('approach leaf requires exact done and state.route_id')
    chosen=reply['state']['route_id']
    if chosen is None:
        raise ActionFailure('NO_OBSERVED_CLEAR_APPROACH')
    if type(chosen) is not str or chosen not in candidates:
        raise ValueError('unknown route_id')
    row=candidates[chosen]['public']
    if (not row['reachable'] or row['obstacle_clearance_m']<MIN_CLEARANCE
            or row['table_clearance_m']<MIN_TABLE_CLEARANCE):
        raise ValueError('selected route fails immutable clearance/reachability gate')
    return chosen


def bind(fn,**overrides):
    fn2=L.rebound(fn,**overrides)
    fn2.__kwdefaults__=fn.__kwdefaults__
    return fn2


def execute(case,out,grasp_source,open_source,placement_source,finish_source,caps,locate_source,approach_source):
    out=Path(out)
    calls=[]

    class ObstacleGrasp(C.AdaptiveGrasp):
        def preflight(self):
            result=super().preflight()
            # The original pre-prepare check stays unchanged. Only the ready
            # phase has actual preshaped joint state for environment checks.
            if self.phase!='ready' or not result['reachable']:
                return result
            obstacles=cylinders_from_rgbd(self.port.plant.rgbd(),self.estimate)
            if not obstacles:
                calls.append({'time_s':self.port.state()['simulation_seconds'],'branch':'no_visible_can','worker_calls':0})
                return result
            yaw=self.plan['selected_yaw_rad']
            plane=np.asarray(self.estimate['table_plane'])
            candidates={}
            for route_id,mode in [('default',self.adaptive['approach_mode']),('top_down','top_down')]:
                params={**self.adaptive,'approach_mode':mode}
                goals=route_goals(self.grasp_anchor,self.offset,yaw,params)
                path,obstacle_margin,table_margin=route_clearance(self.port.state(),goals,yaw,params,obstacles,plane)
                public={'route_id':route_id,'reachable':path['reachable'],
                        'obstacle_clearance_m':obstacle_margin if obstacle_margin is not None else -1.,
                        'table_clearance_m':table_margin if table_margin is not None else -1.}
                candidates[route_id]={'public':public,'path':path}
            obs={'routes':[row['public'] for row in candidates.values()]}
            with Worker(approach_source,body_packet(),wall_timeout=5.,cpu_seconds=120) as worker:
                reply=worker.act(obs,{'phase':'obstacle_approach_selection'})
                row={'time_s':self.port.state()['simulation_seconds'],'obstacles':obstacles,'observation':obs,
                     'reply':reply,'worker_security':worker.security,'worker_calls':1}
                calls.append(row)
            chosen=validate_reply(reply,candidates)
            row['selected']=chosen
            self.plan={**self.plan,'path':candidates[chosen]['path']}
            return {**result,'approach_leaf_route':chosen,'environment_collision_checked':'observed_can_and_table_only'}

    # Inject the approach subclass into the existing temporal/locate pipeline;
    # their MRO preserves the original locator, offsets, lift, place and finish.
    curriculum=SimpleNamespace(**vars(C))
    curriculum.AdaptiveGrasp=ObstacleGrasp
    locate=SimpleNamespace(**vars(L))
    locate.C=curriculum
    locate.execute=bind(L.execute,C=curriculum)
    run=bind(T.execute,L=locate)
    result=run(case,out,grasp_source,open_source,placement_source,finish_source,caps,locate_source)
    write_new(out/'obstacle_approach.json',{'runtime_version':VERSION,'calls':calls,'ground_truth_used':False,
              'allowed_effect':'select original or top_down approach, same endpoint/yaw','hidden_resets':0})
    return result
