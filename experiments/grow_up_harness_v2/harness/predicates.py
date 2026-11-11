"""Frozen definitions for the ten step-boundary predicates.

Every predicate used by an ``Op`` has exactly one definition here: a data
source, a formula and a frozen threshold. Two adapters build the same
``state`` mapping: ``from_trace_frame`` for saved integration state and
``from_live`` for the running plant. Nothing in this module is agent
visible; the agent only learns the verdict through feedback.

Thresholds mirror the frozen TP01 evaluator where the two overlap
(``experiments/t0_agent_v1/diversity_predicates.py``: ``hand_force_N=0.1``,
``linear_speed_m_s=0.02``, ``angular_speed_rad_s=0.2``, ``stable_s=1.0``,
``max_sample_gap_s=0.051``). A different value here would let the runtime
and the evaluator disagree, so they are not tunable per op.

``HeldLifted`` is the task goal, not a step predicate; it is evaluated only
by ``tabletop_predicates.evaluate_trace``.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

VERSION = "tp01-step-predicates-v2"

THRESHOLDS: dict[str, float] = {
    # guard
    "max_tilt_deg": 5.0,
    "max_drift_m": 0.03,
    # target_visible
    "min_visible_points": 25.0,
    # hand
    "min_open_fraction": 0.6,
    "hand_force_N": 0.1,
    # target_localized
    "min_confidence": 0.5,
    # palm_near_target v2: two axes in the pelvis frame
    "palm_horizontal_m": 0.12,
    "palm_vertical_m": 0.08,
    # grasp_contact / holding_target
    "min_hand_contact_N": 0.1,
    "hand_support_fraction": 0.25,
    "max_nonhand_support_N": 0.1,
    # target_lifted / target_stable
    "minimum_lift_m": 0.10,
    "linear_speed_m_s": 0.02,
    "angular_speed_rad_s": 0.2,
    # window width that turns target_stable into the task's 1 s hold
    "stable_s": 1.0,
}

GRAVITY = 9.81

# Predicates a step contract may declare. HeldLifted is excluded: it is the
# task goal and belongs to the evaluator.
STEP_PREDICATES = (
    "target_visible",
    "hand_empty",
    "hand_open",
    "target_localized",
    "palm_near_target",
    "grasp_contact",
    "holding_target",
    "target_lifted",
    "target_stable",
    "guard_clear",
)


class PredicateUnavailable(RuntimeError):
    """The state does not carry the data a predicate needs.

    This is not ``False``. A guard that cannot be read must stop the step,
    not be treated as a violated postcondition.
    """


@dataclass(frozen=True)
class PredicateSpec:
    name: str
    source: str
    definition: str
    needs: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source,
            "definition": self.definition,
            "needs": list(self.needs),
        }


SPECS: dict[str, PredicateSpec] = {
    "guard_clear": PredicateSpec(
        name="guard_clear",
        source="plant",
        definition=(
            "no protection trigger, |tilt| <= 5 deg, |drift| <= 0.03 m, "
            "no external forces, no active equality constraint"
        ),
        needs=("protection", "robot.tilt_deg", "robot.drift_m", "external_forces", "equality_constraints"),
    ),
    "target_visible": PredicateSpec(
        name="target_visible",
        source="observation",
        definition=(
            "the current RGB-D frame has finite target depth and at least 25 "
            "points selected by the target mask"
        ),
        needs=("perception",),
    ),
    "hand_empty": PredicateSpec(
        name="hand_empty",
        source="plant",
        definition="no object reports hand contact >= 0.1 N",
        needs=("objects",),
    ),
    "hand_open": PredicateSpec(
        name="hand_open",
        source="plant",
        definition="left hand aperture >= 0.6 of its documented open range",
        needs=("hand.open_fraction",),
    ),
    "target_localized": PredicateSpec(
        name="target_localized",
        source="blackboard-shape",
        definition=(
            "blackboard carries a finite target estimate in the pelvis frame "
            "and confidence >= 0.5; correctness is not checked here"
        ),
        needs=("perception.target_estimate", "perception.confidence"),
    ),
    "palm_near_target": PredicateSpec(
        name="palm_near_target",
        source="plant",
        definition=(
            "palm and target share the pelvis frame; horizontal distance <= 0.12 m "
            "and vertical distance <= 0.08 m"
        ),
        needs=(
            "palm.position_m",
            "palm.frame",
            "objects[].pelvis_position_m",
            "objects[].frame",
        ),
    ),
    "grasp_contact": PredicateSpec(
        name="grasp_contact",
        source="plant",
        definition="target hand contact >= 0.1 N",
        needs=("objects",),
    ),
    "holding_target": PredicateSpec(
        name="holding_target",
        source="plant",
        definition=(
            "hand support >= 0.25*m*g, non-hand support < 0.1 N, "
            "hand contact >= 0.1 N"
        ),
        needs=("objects",),
    ),
    "target_lifted": PredicateSpec(
        name="target_lifted",
        source="plant",
        definition=(
            "holding_target and target bottom at least 0.10 m above the "
            "episode initial bottom"
        ),
        needs=("objects",),
    ),
    "target_stable": PredicateSpec(
        name="target_stable",
        source="plant",
        definition=(
            "target_lifted and linear speed <= 0.02 m/s and angular speed "
            "<= 0.2 rad/s; the 1 s window is accumulated by the runtime"
        ),
        needs=("objects",),
    ),
}


def digest() -> str:
    payload = {
        "version": VERSION,
        "thresholds": THRESHOLDS,
        "specs": {name: SPECS[name].to_dict() for name in STEP_PREDICATES},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get(state: Mapping[str, Any], path: str) -> Any:
    node: Any = state
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            raise PredicateUnavailable(f"missing {path}")
        node = node[part]
    return node


def _number(state: Mapping[str, Any], path: str) -> float:
    value = _get(state, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PredicateUnavailable(f"{path} is not a number")
    if not math.isfinite(value):
        raise PredicateUnavailable(f"{path} is not finite")
    return float(value)


def _target(state: Mapping[str, Any]) -> Mapping[str, Any]:
    name = _get(state, "target")
    objects = _get(state, "objects")
    if name not in objects:
        raise PredicateUnavailable(f"target {name!r} is not in objects")
    return objects[name]


def _supports(item: Mapping[str, Any]) -> tuple[float, float]:
    supports = item.get("upward_support_N")
    if not isinstance(supports, Mapping):
        raise PredicateUnavailable("upward_support_N")
    hand = 0.0
    nonhand = 0.0
    for key, value in supports.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PredicateUnavailable(f"support {key!r} is not a number")
        if "_hand_" in key:
            hand += float(value)
        else:
            nonhand += float(value)
    return hand, nonhand


def _hand_contact(item: Mapping[str, Any]) -> float:
    value = item.get("hand_contact_N")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PredicateUnavailable("hand_contact_N")
    return float(value)


def _holds(state: Mapping[str, Any]) -> bool:
    item = _target(state)
    hand, nonhand = _supports(item)
    mass = _number(item, "mass_kg")
    return (
        hand >= THRESHOLDS["hand_support_fraction"] * mass * GRAVITY
        and nonhand < THRESHOLDS["max_nonhand_support_N"]
        and _hand_contact(item) >= THRESHOLDS["min_hand_contact_N"]
    )


def _lifted(state: Mapping[str, Any]) -> bool:
    item = _target(state)
    position = item.get("position_m")
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        raise PredicateUnavailable("target position_m")
    initial = item.get("initial_bottom_z_m")
    if initial is None:
        raise PredicateUnavailable("initial_bottom_z_m")
    if isinstance(initial, bool) or not isinstance(initial, (int, float)) or not math.isfinite(initial):
        raise PredicateUnavailable("initial_bottom_z_m is not finite")
    if not _holds(state):
        return False
    return float(position[2]) - float(initial) >= THRESHOLDS["minimum_lift_m"]


def evaluate(name: str, state: Mapping[str, Any]) -> bool:
    """Evaluate one step predicate on a prepared state mapping."""
    if name not in SPECS:
        raise PredicateUnavailable(f"unknown predicate: {name}")
    if name == "guard_clear":
        forces = state.get("external_forces")
        constraints = state.get("equality_constraints")
        if not isinstance(forces, bool):
            raise PredicateUnavailable("external_forces")
        if isinstance(constraints, bool) or not isinstance(constraints, (int, float)):
            raise PredicateUnavailable("equality_constraints")
        return (
            state.get("protection") is None
            and abs(_number(state, "robot.tilt_deg")) <= THRESHOLDS["max_tilt_deg"]
            and abs(_number(state, "robot.drift_m")) <= THRESHOLDS["max_drift_m"]
            and not forces
            and float(constraints) == 0
        )
    if name == "target_visible":
        perception = _get(state, "perception")
        return bool(
            perception.get("target_depth_valid")
            and _number(state, "perception.target_points") >= THRESHOLDS["min_visible_points"]
        )
    if name == "hand_empty":
        objects = _get(state, "objects")
        if not objects:
            raise PredicateUnavailable("objects is empty")
        return all(_hand_contact(item) < THRESHOLDS["hand_force_N"] for item in objects.values())
    if name == "hand_open":
        return _number(state, "hand.open_fraction") >= THRESHOLDS["min_open_fraction"]
    if name == "target_localized":
        estimate = _get(state, "perception.target_estimate")
        if not isinstance(estimate, (list, tuple)) or len(estimate) != 3:
            raise PredicateUnavailable("target_estimate is not a 3-vector")
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in estimate):
            raise PredicateUnavailable("target_estimate is not finite")
        return _number(state, "perception.confidence") >= THRESHOLDS["min_confidence"]
    if name == "palm_near_target":
        palm = _get(state, "palm.position_m")
        if not isinstance(palm, (list, tuple)) or len(palm) != 3:
            raise PredicateUnavailable("palm.position_m")
        palm_frame = _get(state, "palm.frame")
        target = _target(state)
        target_frame = target.get("frame")
        if not isinstance(palm_frame, str) or not isinstance(target_frame, str):
            raise PredicateUnavailable("palm or target frame missing")
        if palm_frame != target_frame:
            raise PredicateUnavailable(
                f"mixed frames: palm={palm_frame}, target={target_frame}"
            )
        if palm_frame != "current_pelvis":
            raise PredicateUnavailable(
                f"palm_near_target needs the pelvis frame, got {palm_frame}"
            )
        position = target.get("pelvis_position_m")
        if not isinstance(position, (list, tuple)) or len(position) != 3:
            raise PredicateUnavailable("objects[].pelvis_position_m")
        horizontal = math.hypot(
            float(palm[0]) - float(position[0]), float(palm[1]) - float(position[1])
        )
        vertical = abs(float(palm[2]) - float(position[2]))
        return (
            horizontal <= THRESHOLDS["palm_horizontal_m"]
            and vertical <= THRESHOLDS["palm_vertical_m"]
        )
    if name == "grasp_contact":
        return _hand_contact(_target(state)) >= THRESHOLDS["min_hand_contact_N"]
    if name == "holding_target":
        return _holds(state)
    if name == "target_lifted":
        return _lifted(state)
    if name == "target_stable":
        item = _target(state)
        return (
            _lifted(state)
            and _number(item, "linear_speed_m_s") <= THRESHOLDS["linear_speed_m_s"]
            and _number(item, "angular_speed_rad_s") <= THRESHOLDS["angular_speed_rad_s"]
        )
    raise PredicateUnavailable(f"unhandled predicate: {name}")


def check_all(names, state: Mapping[str, Any]) -> tuple[bool, dict[str, bool], tuple[str, ...]]:
    """Evaluate ``names``; report unavailable predicates separately."""
    results: dict[str, bool] = {}
    missing: list[str] = []
    for name in names:
        try:
            results[name] = evaluate(name, state)
        except PredicateUnavailable:
            missing.append(name)
    ok = not missing and all(results.values())
    return ok, results, tuple(missing)


def from_trace_frame(
    frame: Mapping[str, Any],
    instance: Mapping[str, Any],
    target: str,
    initial_bottom_z: Mapping[str, float] | None = None,
) -> dict:
    """Build a predicate state from one saved evaluator frame.

    ``initial_bottom_z`` must be the episode's accepted initial bottom height
    per object (``evaluate_trace`` fixes it from ``frames[0]``). Without it,
    ``target_lifted`` and ``target_stable`` stay unavailable rather than
    silently measuring from the current frame.

    Palm, hand aperture and perception are not part of the integration-state
    trace, so predicates that need them stay unavailable here. That is the
    intended asymmetry: the trace adapter can only verify plant facts.
    """
    objects = {}
    for item in instance["objects"]:
        state = frame["objects"][item["name"]]
        bottom = None
        if initial_bottom_z is not None and item["name"] in initial_bottom_z:
            bottom = float(initial_bottom_z[item["name"]])
        elif "initial_bottom_z_m" in state:
            bottom = float(state["initial_bottom_z_m"])
        objects[item["name"]] = {
            "position_m": list(state["position_m"]),
            "frame": "world",
            "initial_bottom_z_m": bottom,
            "mass_kg": float(item["asset"]["mass_kg"]),
            "hand_contact_N": float(state["hand_contact_N"]),
            "upward_support_N": dict(state["upward_support_N"]),
            "linear_speed_m_s": float(state["linear_speed_m_s"]),
            "angular_speed_rad_s": float(state["angular_speed_rad_s"]),
        }
    return {
        "time": float(frame["time"]),
        "target": target,
        "objects": objects,
        "robot": dict(frame["robot"]),
        "protection": frame.get("protection"),
        "external_forces": bool(frame.get("external_forces", False)),
        "equality_constraints": int(frame.get("equality_constraints", 0)),
    }


def from_live(
    *,
    time: float,
    target: str,
    objects: Mapping[str, Mapping[str, Any]],
    palm: Mapping[str, Any] | None,
    hand: Mapping[str, Any] | None,
    robot: Mapping[str, Any],
    perception: Mapping[str, Any] | None = None,
    protection: Any = None,
    external_forces: bool = False,
    equality_constraints: int = 0,
) -> dict:
    """Build a predicate state from the running plant."""
    state: dict[str, Any] = {
        "time": float(time),
        "target": target,
        "objects": {name: dict(item) for name, item in objects.items()},
        "robot": dict(robot),
        "protection": protection,
        "external_forces": bool(external_forces),
        "equality_constraints": int(equality_constraints),
    }
    if palm is not None:
        state["palm"] = dict(palm)
    if hand is not None:
        state["hand"] = dict(hand)
    if perception is not None:
        state["perception"] = dict(perception)
    return state


def held_lifted_names() -> tuple[str, ...]:
    """Predicates the runtime may use at a step boundary."""
    return STEP_PREDICATES
