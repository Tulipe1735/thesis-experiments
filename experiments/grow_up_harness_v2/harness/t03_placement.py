"""Explicit real-state seam for a placement-target leaf after the frozen grasp.

The original curriculum execute function runs byte-identically in an isolated
globals namespace whose existing camera-target hook calls the numeric artifact.
No simulator state reset, no model truth, no change to the body or evaluator.
"""
import copy,types
from pathlib import Path
import numpy as np
from . import t03_curriculum as C
from .t03_runtime import platter_from_camera
from .agent import check_source
from experiments.t0_agent_v1.reuse_grasp import point_cloud
from experiments.t0_agent_v1.train_tp01 import body_packet
from experiments.t0_agent_v1.common import write_new
from experiments.grow_up_v2.isolation.worker import Worker


def validate(reply):
    if type(reply) is not dict or set(reply)!={'action','state'} or reply['action']!={'op':'done'}:
        raise ValueError('placement reply requires exactly action={op:done},state')
    if type(reply['state']) is not dict or set(reply['state'])!={'offset_m'}:
        raise ValueError('placement state requires exactly offset_m')
    v=reply['state']['offset_m']
    if type(v) is not list or len(v)!=3 or any(type(x) not in (int,float) or not np.isfinite(x) for x in v):
        raise ValueError('offset_m requires finite vec3')
    if abs(v[0])>.02000001 or abs(v[1])>.12000001 or not 0<=v[2]<=.03000001:
        raise ValueError('offset_m bounds: x +/-0.02m, y +/-0.12m, release clearance z=0..0.03m')
    return np.asarray(v,float)


def numeric_gate(source):
    """Check a proposed placement leaf through the real Worker interface."""
    from experiments.grow_up_v2.isolation.worker import WorkerError
    check_source(source)
    try:
        with Worker(source, body_packet(), wall_timeout=5., cpu_seconds=120) as worker:
            reply = worker.act({'platter_center_pelvis_m': [.37, 0, .18]}, {'phase': 'placement_target'})
    except WorkerError as exc:
        if 'act must return a dictionary containing an action object' not in str(exc):
            raise
        raise ValueError('act must return a dictionary with action and state, not a tuple/list') from None
    validate(reply)
    return reply


def execute(case,out,grasp_source,open_source,placement_source,caps):
    check_source(placement_source);out=Path(out)
    def camera_target(plant,goal):
        center=platter_from_camera(plant,goal)
        observation={'robot':plant.observation(),'platter_center_pelvis_m':center.tolist(),
            'prior':'marked procedural platter in near-side T03 curriculum; long direction approximately pelvis y; no simulator pose',
            'max_fruit_radius_m':.041}
        with Worker(placement_source,body_packet(),wall_timeout=5.,cpu_seconds=120) as worker:
            reply=worker.act(observation,{'phase':'placement_target','object_count':1,'hold_s':1.})
            offset=validate(reply)
            write_new(out/'placement_invocation.json',{'observation':observation,'reply':reply,'worker_security':worker.security,
                'source_sha256':__import__('hashlib').sha256(placement_source.encode()).hexdigest()})
        return center+offset
    namespace=dict(C.execute.__globals__);namespace['platter_from_camera']=camera_target
    run=types.FunctionType(C.execute.__code__,namespace,C.execute.__name__,C.execute.__defaults__)
    result=run(case,out,grasp_source,open_source,caps)
    write_new(out/'artifact_execution.json',{'grasp_source_sha256':result['source_sha256'],
        'placement_source_sha256':__import__('hashlib').sha256(placement_source.encode()).hexdigest(),
        'placement_called':(out/'placement_invocation.json').exists(),
        'runtime_adapter':'harness/t03_placement.py + unchanged t03_curriculum.execute body',
        'real_state_continuation':True,'hidden_resets':0})
    return result
