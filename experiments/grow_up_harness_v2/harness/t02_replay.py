"""Artifact.v2 leaves that replay qualified T02 motor targets through the Worker outlet.

Engineering column: a person chose this recipe and the targets come from recorded
engineering episode 2401. Open loop: it reads no cup or tray estimate, so success
says nothing about visual adaptation beyond what the sampled jitter tolerates.
"""
import json
from pathlib import Path

SOURCE_TEMPLATE = '''import math

JOINTS = %(joints)s
PLAN = %(plan)s
STEP_S = 0.15
WAIT_S = 0.2


def init(profile):
    return {"i": 0, "w": 0}


def act(observation, task, state):
    joints = observation["joints"]
    while state["i"] < len(PLAN):
        kind, value = PLAN[state["i"]]
        if kind == "w":
            if state["w"] < value:
                state["w"] += 1
                return {"action": {"op": "wait", "duration": WAIT_S}, "state": state}
            state["i"] += 1
            state["w"] = 0
            continue
        steps = 0
        for index, goal in value:
            name = JOINTS[index]
            limit = 0.05 if "_hand_" in name else 0.03
            steps = max(steps, math.ceil(abs(goal - joints[name]["target"]) / limit - 1e-9))
        if steps == 0:
            state["i"] += 1
            continue
        targets = {}
        for index, goal in value:
            name = JOINTS[index]
            current = joints[name]["target"]
            if abs(goal - current) > 1e-12:
                targets[name] = current + (goal - current) / steps
        return {"action": {"op": "set_joints", "targets": targets, "duration": STEP_S}, "state": state}
    return {"action": {"op": "done"}, "state": state}
'''


RETREAT_BOUNDARY = "pelvis_backward_tray_retreat_01"


def segments(source: Path) -> list[list[list]]:
    """One plan per cup attempt, aligned with physics events; raises on misalignment."""
    return [[[kind, value] for _, kind, value in plan] for plan in _plans(source)]


def segments_split(source: Path) -> list[tuple[list, list]]:
    """Per cup: (grasp, carry, lower and release) and (retreat, raise, settle), split at the recorded retreat."""
    split = []
    for plan in _plans(source):
        stages = [stage for stage, _, _ in plan]
        if stages.count(RETREAT_BOUNDARY) != 1:
            raise ValueError(f"expected one {RETREAT_BOUNDARY} per cup attempt")
        i = stages.index(RETREAT_BOUNDARY)
        split.append(([[k, v] for _, k, v in plan[:i]], [[k, v] for _, k, v in plan[i:]]))
    return split


def _plans(source: Path) -> list[list[tuple]]:
    events = json.loads((source / "physics_events.json").read_text())[1:]
    plans, offset = [], 0
    for path in sorted(source.glob("cup_attempt_*/actions.json")):
        actions = [a for a in json.loads(path.read_text()) if "result" in a and "simulation_seconds" in a["result"]]
        plan = []
        for action, event in zip(actions, events[offset:offset + len(actions)], strict=True):
            if abs(action["result"]["simulation_seconds"] - event["simulation_seconds"]) > 1e-8:
                raise ValueError("recorded action and physics event are misaligned")
            if event["category"] == "action":
                plan.append((action["stage"], "m", dict(event["joints"])))
            else:
                plan.append((action["stage"], "w", action["arguments"]["seconds"]))
        plans.append(plan)
        offset += len(actions)
    if offset != len(events):
        raise ValueError(f"{len(events) - offset} physics events belong to no cup attempt")
    return plans


def leaf_source(plan: list[list]) -> str:
    joints = sorted({name for kind, value in plan if kind == "m" for name in value})
    encoded = []
    for kind, value in plan:
        if kind == "w":
            chunks = int(value / .2)
            encoded.append(["w", chunks + (chunks * .2 < value - 1e-9)])
        else:
            encoded.append(["m", [[joints.index(n), round(v, 5)] for n, v in sorted(value.items())]])
    return SOURCE_TEMPLATE % {"joints": json.dumps(joints), "plan": json.dumps(encoded, separators=(",", ":"))}
