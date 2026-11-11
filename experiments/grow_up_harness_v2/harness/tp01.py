"""TP01 training cases, scenes, plants and the runtime-only predicate state.

The four reach cases and the eight tabletop cases are frozen training states.
This module only wires them to the existing plant and evaluator; it copies
neither. ``step_state`` is evaluator-side runtime state and must not reach the
agent.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.t0_agent_v1.training_runtime import ensure_runtime

# Load the hash-verified plant before any module imports a direct copy.
ensure_runtime()

from experiments.t0_agent_v1 import reach_training_initials, train_tp01  # noqa: E402
from experiments.t0_agent_v1.diversity_predicates import snapshot  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import (  # noqa: E402
    TabletopPlant,
    build_training_scene,
)

from . import predicates  # noqa: E402
from .contracts import Observation, Predicate, TaskSpec  # noqa: E402

REACH_DATASET = ROOT / "experiments/t0_agent_v1/tp01_reach_dataset_20261026_001"
TABLETOP_DATASET = ROOT / "experiments/t0_agent_v1/tabletop_dataset_20261026_003"

# The plant's left-hand joint order, frozen with the closed pose recorded in
# grasp_optimization/episodes/final_reference_1000/run_config.json.
HAND_JOINTS = tuple(
    f"left_hand_{part}_joint"
    for part in ("thumb_0", "thumb_1", "thumb_2", "middle_0", "middle_1", "index_0", "index_1")
)

# Reference closed pose from that run config.
CLOSED_ANGLES = (0.0, 0.65, 0.65, -0.8, -0.6, -0.8, -0.6)

# Open anchor per joint: the plant's standing hand target (q=0), which is the
# pose every engineering recipe starts from. The documented mechanical ranges
# in grasp_optimization/assets/robot_profile.json extend past it for three
# joints (thumb_1 to -0.611, thumb_0 to -1.047, middle_0 to -1.571 side), so
# travel beyond the anchor is clamped to fully open rather than counted as
# closing.
OPEN_ANGLES = (0.0,) * 7

TEMPLATE_LABEL = "pick up the target and hold it stable for 1 s"


@dataclass(frozen=True)
class TP01Case:
    alias: str
    instance_id: str
    instance: dict
    case_path: Path
    task: TaskSpec
    target: str
    target_category: str
    initial_bottom_z_m: float
    initial_state_sha256: str
    qualification_sha256: str
    valid_initial_fixture: bool


def _read(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _instruction(case_path: Path, instance: dict) -> str:
    task_path = Path(case_path) / "task.json"
    if task_path.exists():
        instruction = _read(task_path).get("instruction")
        if instruction:
            return instruction
    label = instance.get("label")
    return label if label else TEMPLATE_LABEL


def _target(instance: dict) -> dict:
    return next(item for item in instance["objects"] if item["is_target"])


def _goal(instance: dict, target: str) -> dict:
    return next(
        goal
        for goal in instance["goals"]
        if goal["predicate"] == "HeldLifted" and goal["object"] == target
    )


def _bottom(goal: dict, case_path: Path, target: str) -> float:
    # The evaluator fixes the lift datum from the first replayed frame, which is
    # the settled state. Read that same value here so runtime and evaluator
    # cannot disagree at the 10 cm boundary.
    initial = _read(Path(case_path) / "initial_state.json")
    settled = (
        initial.get("settled_snapshot", {})
        .get("objects", {})
        .get(target, {})
        .get("position_m")
    )
    if isinstance(settled, list) and len(settled) == 3:
        return float(settled[2])
    if "initial_bottom_z_m" in goal:
        return float(goal["initial_bottom_z_m"])
    raise ValueError(f"no settled or declared initial bottom for {target}")


def _case(entry: dict) -> TP01Case:
    instance = entry["instance"]
    record = entry["record"]
    case_path = Path(entry["case_path"])
    target = _target(instance)
    goal = _goal(instance, target["name"])
    qualification = record.get("qualification_xml_sha256")
    if qualification is None:
        qualification = _sha256_file(case_path / "qualification.xml")
    task = TaskSpec(
        id=instance["id"],
        template="TP01",
        instruction=_instruction(case_path, instance),
        # The category is the scope level: a Skill validated on one cup must be
        # admissible for another cup (a different asset id) and refused for an
        # orange or a bottle. The exact asset id stays in the set as evidence.
        assets=frozenset({target["asset"]["kind"], target["asset"]["id"]}),
        goal=Predicate(
            "HeldLifted",
            (
                ("object", target["name"]),
                ("minimum_lift_m", 0.10),
                ("stable_s", 1.0),
            ),
        ),
        budget_s=60.0,
        split="train",
    )
    return TP01Case(
        alias=entry["alias"],
        instance_id=instance["id"],
        instance=instance,
        case_path=case_path,
        task=task,
        target=target["name"],
        target_category=entry["task"]["target_category"],
        initial_bottom_z_m=_bottom(goal, case_path, target["name"]),
        initial_state_sha256=record["initial_state_sha256"],
        qualification_sha256=qualification,
        valid_initial_fixture=bool(record["valid_initial_fixture"]),
    )


def load_cases(dataset: Path = REACH_DATASET) -> tuple[TP01Case, ...]:
    """Load one of the two frozen TP01 training datasets as typed cases."""
    dataset = Path(dataset).resolve()
    if dataset == REACH_DATASET:
        source = reach_training_initials.load_cases(dataset)
    elif dataset == TABLETOP_DATASET:
        source = train_tp01.training_cases(dataset)
    else:
        raise ValueError(f"unsupported TP01 dataset: {dataset}")
    return tuple(_case(entry) for entry in source)


def build_scene(case: TP01Case, path: Path) -> "mujoco.MjModel":
    """Build the case scene through the frozen tabletop scene compiler."""
    if not Path(case.case_path).exists():
        raise FileNotFoundError(case.case_path)
    return build_training_scene(case.instance, Path(path))


def make_plant(
    case: TP01Case, model, output: Path, budget: float = 60.0
) -> TabletopPlant:
    """Bind a typed case to the frozen training plant."""
    return TabletopPlant(case.instance, case.case_path, model, output, budget=budget)


def observation(plant, rgbd: bool = True) -> Observation:
    """Project the plant's public sensors into the typed observation."""
    payload = plant.observation()
    if rgbd:
        payload["rgbd"] = plant.rgbd()
    return Observation(time=payload["simulation_seconds"], payload=payload)


def hand_open_fraction(plant) -> float:
    """Closure relative to the reference closed pose, anchored at the rest pose.

    ``1.0`` at the open anchor (q=0, the plant's standing hand target), ``0.0``
    at the reference closed angle, linear in between. Closure is clamped to
    ``[0, 1]``, so a joint driven further open than the anchor (thumb_1 can
    travel to -0.611) stays at fully open instead of reading as closing.
    ``thumb_0`` has no reference closure and is skipped. This is a
    convention normalised by the documented ranges, not a finger width.
    """
    joints = plant.observation()["joints"]
    fractions = []
    for name, opened, closed in zip(HAND_JOINTS, OPEN_ANGLES, CLOSED_ANGLES):
        if closed == opened:
            continue
        q = float(joints[name]["q"])
        closure = (q - opened) / (closed - opened)
        fractions.append(1.0 - min(1.0, max(0.0, closure)))
    return min(fractions)


def visibility_perception(plant, case: TP01Case) -> dict:
    """Runtime-side visibility of the target in the head camera.

    The router's initial gate needs ``target_visible`` before any Agent code
    runs. The saved state has no blackboard yet, so read the camera and project
    the target's plant position into it. This is a runtime check, not an Agent
    input: the Agent never sees the target position.
    """
    rgbd = plant.rgbd()
    depth = rgbd.get("depth_m")
    if depth is None:
        return {"target_depth_valid": False, "target_points": 0, "target_estimate": None, "confidence": 0.0}
    depth = np.asarray(depth, dtype=float)
    K = np.asarray(rgbd["K"], dtype=float)
    T = np.asarray(rgbd["T_optical_to_pelvis"], dtype=float)
    pelvis = plant.data.xpos[plant.pelvis_id]
    rotation = plant.data.xmat[plant.pelvis_id].reshape(3, 3)
    # The body origin sits near the cup base; the centre of mass is a better
    # projection target for a depth-window visibility count.
    target_world = plant.data.xipos[plant.model.body(case.target).id]
    target_pelvis = rotation.T @ (target_world - pelvis)
    target_optical = T[:3, :3].T @ (target_pelvis - T[:3, 3])
    z = float(target_optical[2])
    if not np.isfinite(z) or z <= 0.05:
        return {"target_depth_valid": False, "target_points": 0, "target_estimate": None, "confidence": 0.0}
    u = K[0, 0] * target_optical[0] / z + K[0, 2]
    v = K[1, 1] * target_optical[1] / z + K[1, 2]
    if not (0 <= u < depth.shape[1] and 0 <= v < depth.shape[0]):
        return {"target_depth_valid": False, "target_points": 0, "target_estimate": None, "confidence": 0.0}
    x, y = int(round(u)), int(round(v))
    window = depth[max(0, y - 5) : y + 6, max(0, x - 5) : x + 6]
    valid = np.isfinite(window) & (window > 0.05) & (np.abs(window - z) < 0.05)
    points = int(valid.sum())
    return {
        "target_depth_valid": bool(points >= 25),
        "target_points": points,
        "target_estimate": None,
        "confidence": 0.0,
    }


def step_state(plant, case: TP01Case, perception: dict | None = None) -> dict:
    """Build one live predicate state. Runtime only; never agent visible."""
    frame = snapshot(
        plant.model, plant.data, case.instance, base=plant.base_reference
    )
    state = predicates.from_trace_frame(
        frame,
        case.instance,
        case.target,
        {case.target: case.initial_bottom_z_m},
    )
    # palm_near_target v2 needs the target and the palm in one frame. The palm
    # is already in the pelvis frame, so add the target's pelvis position and
    # override the adapter's world frame marker for that object only.
    import numpy as np

    pelvis = plant.data.xpos[plant.pelvis_id]
    rotation = plant.data.xmat[plant.pelvis_id].reshape(3, 3)
    target_world = plant.data.xpos[plant.model.body(case.target).id]
    local = rotation.T @ (target_world - pelvis)
    state["objects"][case.target]["pelvis_position_m"] = [float(v) for v in local]
    state["objects"][case.target]["frame"] = "current_pelvis"
    state["palm"] = plant.observation()["left_palm"]
    state["hand"] = {"open_fraction": hand_open_fraction(plant)}
    if perception is not None:
        state["perception"] = dict(perception)
    state["protection"] = plant.guard
    return state


def t01_joint_observation(robot) -> dict:
    """Public proprioception only, for an explicit-pose local T01 contract."""
    state = robot.state()
    names = {name for name in state["joints"]
             if name.startswith("left_") and any(part in name for part in
                 ("shoulder", "elbow", "wrist", "hand"))}
    return {
        "simulation_seconds": state["simulation_seconds"],
        "joints": {name: state["joints"][name] for name in sorted(names)},
        "left_palm": state["palms"]["left"],
        "left_contact_load_N": state["approximate_contact_load_N"]["left"],
        "guard": state["controller"]["guard"],
    }


def t01_joint_dispatch(robot, action: dict, *, deadline: float) -> dict:
    """Same bounded joint outlet for local controls and candidates; no IK API."""
    import math

    op = action.get("op")
    if op not in ("wait", "set_joints"):
        raise ValueError(f"unsupported local action: {op}")
    duration = action["duration"]
    if (type(duration) not in (int, float) or not math.isfinite(duration)
            or not .02 <= duration <= .2
            or abs(duration / .002 - round(duration / .002)) > 1e-6):
        raise ValueError("duration must be 0.02–0.20 s on the 0.002 s grid")
    if robot.data.time + duration > deadline + 1e-8:
        raise ValueError("LOCAL_BUDGET_EXCEEDED")
    if op == "wait":
        result = robot.advance(duration, "local_wait")
        return dict(result, status=robot.guard or "EXECUTED")
    targets = action["targets"]
    if not isinstance(targets, dict) or not 1 <= len(targets) <= 14:
        raise ValueError("expected 1–14 left arm/hand targets")
    allowed = t01_joint_observation(robot)["joints"]
    for name, value in targets.items():
        if name not in allowed or type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("invalid left joint target")
        hand = "_hand_" in name
        delta = abs(value - allowed[name]["target"])
        if delta > (.05 if hand else .03) + 1e-8:
            raise ValueError("LOCAL_JOINT_DELTA")
        if 1.5 * delta / duration > (.5 if hand else .3) + 1e-8:
            raise ValueError("LOCAL_JOINT_SPEED")
    return robot.set_joints(targets, duration=duration)


# New runs opt in; frozen controllers keep their original recorder unchanged.
from experiments.cordis_t01.worker import SavedInitialRobot as _SavedInitialRobot


class TickRecordedRobot(_SavedInitialRobot):
    """50 ms samples on integer integration ticks, with the original physics."""
    recording_version = "integer-ticks-v1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._record_tick = 0
        self._record_stride = round(.05 / self.model.opt.timestep)
        if not np.isclose(self._record_stride * self.model.opt.timestep, .05, atol=1e-12, rtol=0):
            raise ValueError("50 ms recording requires an integral number of physics steps")

    def _step(self):
        import mujoco
        self._controller()
        mujoco.mj_step(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        self._goal()
        self._record_tick += 1
        if self._record_tick == 1 or self._record_tick % self._record_stride == 0:
            self.trace.append((float(self.data.time), self.data.qpos.copy(), self.data.qvel.copy(),
                               self.targets.copy(), self.data.actuator_force.copy()))
