"""Registered curriculum and evidence gates; never treat runtime faults as frontier."""
from copy import deepcopy
from . import task_generator

STAGES = (
    {"id": "tight_pose", "task_node": "B2.2", "predecessor": None,
     "status": "ready", "orientation_tolerance_rad": .01, "position_tolerance_m": .004},
    {"id": "obstacle", "task_node": "B2.3", "predecessor": "tight_pose",
     "status": "requires_registered_scene_and_positive", "reason": "must register real obstacle geometry and a collision-free positive path"},
    {"id": "pregrasp", "task_node": "B2.1", "predecessor": "obstacle",
     "status": "requires_registered_scene_and_positive", "reason": "must register object-relative pregrasp targets and reachable positives"},
    {"id": "lift", "task_node": "B3.4", "predecessor": "pregrasp",
     "status": "requires_registered_scene_and_positive", "reason": "must wire grasp evaluator; empty-hand reach safety forbids grasp contact"},
    {"id": "t02_slot_placement", "task_node": "T02.slot", "predecessor": None,
     "status": "requires_registered_scene_and_positive", "slot_tolerance_mm": 15, "tilt_tolerance_deg": 5, "hold_duration_s": 1.0,
     "reason": "no single-cup slot positive exists: 2401 qualifies the three-cup task only, and audited slot placement is 0/9"},
)
FAULTS = {"INTERFACE", "WORKER_ERROR", "EVIDENCE_GAP"}


def author_gate(positive, attempts, candidate_count, *, attempted_all):
    """Only a measured capability miss or an empty applicable library opens authorship."""
    if not positive:
        return {"open": False, "reason": "positive_control_failed"}
    if any(a.get("execution_error") or a.get("evidence_status") == "insufficient_sampling"
           or a.get("label") in FAULTS for a in attempts):
        return {"open": False, "reason": "execution_or_evidence_fault"}
    if any(a["success"] for a in attempts):
        return {"open": False, "reason": "library_solved"}
    if candidate_count == 0:
        return {"open": True, "reason": "library_coverage_empty"}
    if not attempted_all or len(attempts) != candidate_count:
        return {"open": False, "reason": "library_not_exhausted"}
    if any(a.get("label") == "UNSAFE" for a in attempts):
        return {"open": False, "reason": "unsafe_execution_requires_diagnosis"}
    if any(a.get("label") not in {"NOT_REACHED", "ORIENTATION", "NOT_HELD"} for a in attempts):
        return {"open": False, "reason": "not_a_measured_capability_failure"}
    return {"open": True, "reason": "library_capability_failure"}


def generate(stage, **kwargs):
    spec = next(s for s in STAGES if s["id"] == stage)
    if spec["status"] != "ready":
        raise ValueError(f"stage {stage} is closed: {spec['reason']}")
    generated = deepcopy(task_generator.generate(**kwargs))
    generated['frontier_stage'] = spec
    # Retain the underlying reach family so existing leaves are actually tried.
    generated['family']['task_node'] = spec['task_node']
    for task in generated['tasks']:
        task['task_id'] = stage + '_' + task['task_id']
        task['public'].update({k:spec[k] for k in ('orientation_tolerance_rad','position_tolerance_m')})
    return generated
