"""T03 fruit support geometry v2, user-authorized 2026-11-11.

Frozen source is not edited. Only fruit->platter/tray support height uses actual
ellipsoid lowest point. All force, margin, release, stability, error and guard
conditions are the original predicates. Other task relations delegate unchanged.
"""
import types
from .t03_fruit_height_audit import proposed_relation
from experiments.t0_agent_v1 import diversity_predicates as D

VERSION='t03-fruit-bottom-v2-20261111'


def evaluate_trace(instance,frames,*,initial_valid=False,execution_error=None,protection=None):
    scope=dict(D.frame_predicates.__globals__);scope['relation']=proposed_relation
    frame=types.FunctionType(D.frame_predicates.__code__,scope,D.frame_predicates.__name__,D.frame_predicates.__defaults__)
    namespace=dict(D.evaluate_trace.__globals__);namespace.update(relation=proposed_relation,frame_predicates=frame)
    evaluate=types.FunctionType(D.evaluate_trace.__code__,namespace,D.evaluate_trace.__name__,D.evaluate_trace.__defaults__)
    evaluate.__kwdefaults__=D.evaluate_trace.__kwdefaults__
    result=evaluate(instance,frames,initial_valid=initial_valid,execution_error=execution_error,protection=protection)
    result.update(evaluator_version=VERSION,scope='T03 fruit to platter/tray geometric bottom; unchanged physical and robot gates',
        authorization='user explicitly approved evaluator correction 2026-11-11',formal_skill_promotion=False)
    return result


def verify(folder,instance,model,initial_valid=True):
    from experiments.t0_agent_v1.tabletop_training_plant import independent_verify
    namespace=dict(independent_verify.__globals__);namespace['evaluate_trace']=evaluate_trace
    replay=types.FunctionType(independent_verify.__code__,namespace,independent_verify.__name__,independent_verify.__defaults__)
    return replay(folder,instance,model,initial_valid=initial_valid)
