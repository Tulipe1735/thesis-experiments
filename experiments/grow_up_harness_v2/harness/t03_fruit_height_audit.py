"""PROPOSED shadow-only fruit support geometry correction. Not an official evaluator.

The frozen diversity predicates remain untouched. This module supplies an audit
and a reviewable adapter; no experiment has used it for acceptance or promotion.
"""
import types
import numpy as np
from . import tp01
from experiments.t0_agent_v1 import diversity_predicates as D


def geometry(instance,frame,obj_name,target_name):
    items={x['name']:x for x in instance['objects']+instance['facilities']+instance['regions']}
    item,target=items[obj_name],items[target_name]
    state,dest=frame['objects'][obj_name],frame['objects'][target_name]
    r=D.rotation(dest['quaternion_wxyz'])
    local=r.T@(np.asarray(state['position_m'])-dest['position_m'])
    extent,offset=D.footprint(item,state,r)
    a=target.get('asset')
    inner=np.asarray(a['half_xy_m'])-a.get('rim_m',0.) if a else np.asarray(target['half_xy_m'])
    margin=float(np.min(inner-np.abs(local[:2]+offset[:2])-extent))
    relative=r.T@D.rotation(state['quaternion_wxyz'])
    vertical_radius=float(np.sqrt(np.sum((relative[2]*item['asset']['radii_m'])**2)))
    bottom=float(local[2]+offset[2]-vertical_radius)
    floor=a.get('floor_m',0.) if a else 0.
    return {'margin_m':margin,'body_origin_height_error_m':float(local[2]-floor),
        'geometric_bottom_height_error_m':bottom-floor,'vertical_extent_m':vertical_radius}


def proposed_relation(instance,frame,obj_name,target_name,inside):
    item=next(x for x in instance['objects'] if x['name']==obj_name)
    if item['asset']['kind']!='fruit' or not inside:
        return D.relation(instance,frame,obj_name,target_name,inside)
    targets=[x for x in instance['objects'] if x['name']==target_name]
    if not targets or targets[0]['asset']['kind'] not in ('platter','tray'):
        return D.relation(instance,frame,obj_name,target_name,inside)
    target=targets[0]
    g=geometry(instance,frame,obj_name,target_name)
    state=frame['objects'][obj_name]
    support_name=target_name+'_floor'
    return bool(g['margin_m']>=D.LIMITS['margin_m']
        and abs(g['geometric_bottom_height_error_m'])<=D.LIMITS['height_error_m']
        and state['upward_support_N'].get(support_name,0.)>=.25*item['asset']['mass_kg']*9.81
        and state['hand_contact_N']<D.LIMITS['hand_force_N'])


def shadow_evaluate(instance,frames,**kwargs):
    namespace=dict(D.frame_predicates.__globals__);namespace['relation']=proposed_relation
    frame=types.FunctionType(D.frame_predicates.__code__,namespace,D.frame_predicates.__name__,D.frame_predicates.__defaults__)
    scope=dict(D.evaluate_trace.__globals__);scope.update(relation=proposed_relation,frame_predicates=frame)
    evaluate=types.FunctionType(D.evaluate_trace.__code__,scope,D.evaluate_trace.__name__,D.evaluate_trace.__defaults__)
    evaluate.__kwdefaults__=D.evaluate_trace.__kwdefaults__
    result=evaluate(instance,frames,**kwargs)
    result.update(evaluator_version='PROPOSED-t03-fruit-geometric-bottom-v1',shadow_only=True,
        acceptance_authorized=False,formal_skill_promotion=False)
    return result
