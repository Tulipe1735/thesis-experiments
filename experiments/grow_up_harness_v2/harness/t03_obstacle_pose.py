"""User-authorized local grasp-offset selection under unchanged safety limits."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from . import t03_obstacle_approach as O, t03_locate_branch as L, t03_locate_temporal as T, t03_curriculum as C
from experiments.grow_up_v2.isolation.worker import Worker
from experiments.t0_agent_v1.adaptive_reuse_grasp import grasp_rotation, route_goals, validate_adaptive_recipe, PROGRAM
from experiments.t0_agent_v1.common import write_new
from experiments.t0_agent_v1.reuse_grasp import ActionFailure
from experiments.t0_agent_v1.train_tp01 import body_packet

VERSION='t03-rgbd-can-local-offset-v2'


def offset_candidates(controller, obstacles):
    """Finite observation-relative pose family; no task ID, seed or scene truth."""
    yaw=controller.plan['selected_yaw_rad']
    base_offset=controller.offset.copy()
    palm=controller.grasp_anchor-grasp_rotation(yaw,controller.adaptive)@base_offset
    nearest=min(obstacles,key=lambda o:np.linalg.norm(palm[:2]-o['center_xy_m']))
    outward=palm[:2]-nearest['center_xy_m']
    length=np.linalg.norm(outward)
    if length<.01:
        raise ActionFailure('PALM_INSIDE_OBSTACLE_PLAN_UNCERTAIN')
    outward=outward/length
    side=np.array([-outward[1],outward[0]])
    yield 'default',controller.adaptive,base_offset,controller.plan['path']['goals']
    yield 'top_down',dict(controller.adaptive,approach_mode='top_down'),base_offset,route_goals(
        controller.grasp_anchor,base_offset,yaw,dict(controller.adaptive,approach_mode='top_down'))
    for distance in (.02,.04,.06):
        for lateral in (0.,.03,-.03):
            shift=distance*outward+lateral*side
            delta=-(grasp_rotation(yaw,controller.adaptive)[:2,:2].T@shift)
            offset=base_offset.copy();offset[:2]+=delta
            changes=np.array(controller.adaptive['offset_delta_m']).copy();changes[:2]+=delta
            if not (-.05<=changes[0]<=.05 and -.09<=changes[1]<=.05):
                continue
            parameters={**controller.adaptive,'approach_mode':'top_down','offset_delta_m':changes.tolist()}
            # Validate through the actual existing native recipe bounds.
            validate_adaptive_recipe({'program':PROGRAM,'parameters':parameters,'by_category':{}})
            yield f'away_{distance:.2f}_side_{lateral:.2f}',parameters,offset,route_goals(
                controller.grasp_anchor,offset,yaw,parameters)


def execute(case,out,grasp_source,open_source,placement_source,finish_source,caps,locate_source,approach_source):
    out=Path(out);calls=[]
    class PoseGrasp(C.AdaptiveGrasp):
        def preflight(self):
            result=super().preflight()
            if self.phase!='ready' or not result['reachable']:
                return result
            obstacles=O.cylinders_from_rgbd(self.port.plant.rgbd(),self.estimate)
            if not obstacles:
                calls.append({'time_s':self.port.state()['simulation_seconds'],'branch':'no_visible_can','worker_calls':0})
                return result
            yaw=self.plan['selected_yaw_rad'];candidates={}
            for route_id,parameters,offset,goals in offset_candidates(self,obstacles):
                plan,margin,table=O.route_clearance(self.port.state(),goals,yaw,parameters,
                                                   obstacles,np.asarray(self.estimate['table_plane']))
                public={'route_id':route_id,'reachable':plan['reachable'],
                  'obstacle_clearance_m':margin if margin is not None else -1.,
                  'table_clearance_m':table if table is not None else -1.}
                candidates[route_id]={'public':public,'path':plan,'parameters':parameters,'offset':offset}
                if (route_id=='default' and public['reachable'] and margin>=O.MIN_CLEARANCE
                        and table>=O.MIN_TABLE_CLEARANCE):
                    break
            observation={'routes':[v['public'] for v in candidates.values()]}
            with Worker(approach_source,body_packet(),wall_timeout=5.,cpu_seconds=120) as w:
                reply=w.act(observation,{'phase':'obstacle_approach_selection'})
                row={'time_s':self.port.state()['simulation_seconds'],'obstacles':obstacles,
                     'observation':observation,'reply':reply,'worker_security':w.security,'worker_calls':1}
                calls.append(row)
            selected=O.validate_reply(reply,candidates)
            choice=candidates[selected]
            row.update(selected=selected,selected_offset_m=choice['offset'].tolist(),
                       original_offset_m=self.offset.tolist(),
                       parameter_changes={'offset_delta_m':choice['parameters']['offset_delta_m'],
                                          'approach_mode':choice['parameters']['approach_mode']})
            self.adaptive=choice['parameters']
            self.port.parameters=self.adaptive
            self.offset=choice['offset']
            self.plan={**self.plan,'selected_offset_m':self.offset.tolist(),'path':choice['path']}
            return {**result,'approach_leaf_route':selected,'user_authorized_local_pose':True}

    curriculum=SimpleNamespace(**vars(C));curriculum.AdaptiveGrasp=PoseGrasp
    locate=SimpleNamespace(**vars(L));locate.C=curriculum;locate.execute=O.bind(L.execute,C=curriculum)
    run=O.bind(T.execute,L=locate)
    result=run(case,out,grasp_source,open_source,placement_source,finish_source,caps,locate_source)
    write_new(out/'obstacle_approach.json',{'runtime_version':VERSION,'calls':calls,
        'ground_truth_used':False,'hidden_resets':0,'user_authorization':'local pose/preshape allowed 2026-11-11',
        'actual_extension':'bounded native XY grasp offset only; original yaw, preshape, pressure, lift, place and finish reused'})
    return result
