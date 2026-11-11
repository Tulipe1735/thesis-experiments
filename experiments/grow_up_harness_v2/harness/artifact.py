"""The artifact: one YAML file, a strict schema, an IR, and two generators.

The YAML carries semantics and parameters, never execution logic. It is
validated into the models below, compiled to an IR, and from that IR two
projections are generated: a Python program and a Markdown skill card. Neither
generated file is a source of truth; editing either one is overwritten on the
next compile, and the manifest records what was produced from which artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "artifact.v1"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- point and scalar references -------------------------------------------------

class LiteralPoint(Strict):
    literal: tuple[float, float, float]


class ObservedPoint(Strict):
    observed: Literal["grasp.xyz", "grasp.approach_start", "palm"]


class PlacePoint(Strict):
    place: Literal["above", "lower"]
    slot: str | None = None


PointRef = Annotated[Union[LiteralPoint, ObservedPoint, PlacePoint], Field(union_mode="left_to_right")]


class ParamRef(Strict):
    param: str


class GraspWaistRef(Strict):
    grasp_waist: Literal[True]


Scalar = Union[float, ParamRef, GraspWaistRef]


class YawLiteral(Strict):
    literal: float


class YawGrasp(Strict):
    grasp: Literal[True]


YawRef = Annotated[Union[YawGrasp, YawLiteral], Field(union_mode="left_to_right")]


# --- IR steps --------------------------------------------------------------------

class _Step(Strict):
    op: str


class WalkTo(_Step):
    op: Literal["walk_to"]
    to: PointRef
    yaw: YawRef
    orientation: Literal["yaw", "keep"] = "yaw"
    step_m: Scalar | None = None
    execution: Literal["walk", "linear"] = "walk"
    seconds: Scalar | None = None


class MoveTo(_Step):
    op: Literal["move_to"]
    to: PointRef
    yaw: YawRef
    orientation: Literal["yaw", "keep"] = "yaw"


class LineTo(_Step):
    op: Literal["line_to"]
    to: PointRef
    yaw: YawRef
    orientation: Literal["yaw", "keep"] = "keep"
    seconds: Scalar


class Joints(_Step):
    op: Literal["joints"]
    targets: dict[str, Scalar]
    seconds: Scalar


class Wait(_Step):
    op: Literal["wait"]
    seconds: Scalar


class CloseHand(_Step):
    op: Literal["close_hand"]
    seconds: Scalar


class OpenHand(_Step):
    op: Literal["open_hand"]
    seconds: Scalar


class RaiseClear(_Step):
    op: Literal["raise_clear"]
    clearance_m: Scalar
    yaw: YawRef
    execution: Literal["walk", "linear"] = "walk"
    seconds: Scalar | None = None


class DescendToLower(_Step):
    op: Literal["descend_to_lower"]
    height_m: Scalar
    yaw: YawRef
    execution: Literal["walk", "linear"] = "walk"
    seconds: Scalar | None = None


class RetreatUp(_Step):
    op: Literal["retreat_up"]
    distance_m: Scalar
    steps: int = Field(ge=1, le=4)
    yaw: YawRef


class RecenterCup(_Step):
    op: Literal["recenter_cup"]
    tolerance_m: Scalar
    step_m: Scalar


class Finish(_Step):
    op: Literal["finish"]


Step = Annotated[
    Union[WalkTo, MoveTo, LineTo, Joints, Wait, CloseHand, OpenHand, RaiseClear,
          DescendToLower, RetreatUp, RecenterCup, Finish],
    Field(discriminator="op"),
]


class IR(Strict):
    budget_s: float = Field(gt=0)
    parameters: dict[str, float]
    slots: dict[str, tuple[float, float]] = {}
    close_angles: dict[str, float]
    phases: dict[Literal["plan", "lift", "correct", "release"], tuple[Step, ...]]

    @model_validator(mode="after")
    def _phases_present(self):
        required = {"plan", "lift", "correct", "release"}
        missing = required - set(self.phases)
        if missing:
            raise ValueError(f"missing phases: {sorted(missing)}")
        missing_params = {"step_m", "place_above_m", "place_lower_m"} - set(self.parameters)
        if missing_params:
            raise ValueError(f"missing generator parameters: {sorted(missing_params)}")
        if self.parameters["step_m"] <= 0:
            raise ValueError("step_m must be positive")
        return self


# --- artifact sections -----------------------------------------------------------

class Provenance(Strict):
    form: Literal["engineering_composition", "generated_program", "learned_policy"]
    author: str
    first_run: str
    note: str | None = None


class InitialState(Strict):
    path: str
    sha256: str = Field(pattern="^[0-9a-f]{64}$")


class Scope(Strict):
    task: str
    assets: tuple[str, ...] = Field(min_length=1)
    stage: str | None = None
    initial_states: tuple[InitialState, ...] = Field(min_length=1)


class FailureExit(Strict):
    code: str
    condition: str
    recovery: str | None = None


class Contract(Strict):
    preconditions: tuple[str, ...] = Field(min_length=1)
    postconditions: tuple[str, ...] = Field(min_length=1)
    failure_exits: tuple[FailureExit, ...] = Field(min_length=1)


class Assumptions(Strict):
    max_single_move_m: float = Field(gt=0)
    release_height_m: float = Field(gt=0)
    placement_tolerance_m: float | None = None
    contact_load_max_N: float | None = None
    notes: tuple[str, ...] = ()


class Binding(Strict):
    plant_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    evaluator_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    simulation_budget_s: float = Field(gt=0)


class Interfaces(Strict):
    observations: tuple[str, ...]
    commands: tuple[str, ...]
    guards: tuple[str, ...]


class Arm(Strict):
    arm: str
    episodes: int = Field(ge=1)
    successes: int = Field(ge=0)


class Run(Strict):
    path: str
    arm: str
    verified_success: bool
    stable_s: float | None = None
    margin_m: float | None = None
    commands: int | None = None
    simulation_s: float | None = None
    outcome: str | None = None


class Transfer(Strict):
    episodes: int = Field(ge=1)
    successes: int = Field(ge=0)
    run: str
    by_group: dict[str, str]


class Acceptance(Strict):
    run: str
    note: str | None = None


class Evidence(Strict):
    paired: dict[Literal["without", "with"], Arm] | None = None
    runs: tuple[Run, ...] = ()
    transfer: Transfer | None = None
    acceptance: Acceptance | None = None


class Projection(Strict):
    path: str
    entry: str | None = None


class Projections(Strict):
    code: Projection
    skill: Projection


class Artifact(Strict):
    schema_version: Literal["artifact.v1"]
    id: str = Field(pattern="^[a-z][a-z0-9_]{2,63}$")
    version: int = Field(ge=1)
    kind: Literal["skill", "procedure"]
    status: Literal["draft", "candidate", "validated"] = "draft"
    provenance: Provenance
    scope: Scope
    contract: Contract
    assumptions: Assumptions
    binding: Binding
    interfaces: Interfaces
    ir: IR
    evidence: Evidence
    limits: tuple[str, ...] = Field(min_length=1)
    projections: Projections

    @model_validator(mode="after")
    def _slots_are_known(self):
        for phase, steps in self.ir.phases.items():
            for step in steps:
                for name in ("to",):
                    ref = getattr(step, name, None)
                    if isinstance(ref, PlacePoint) and ref.slot and ref.slot not in self.ir.slots:
                        raise ValueError(f"{phase}: unknown slot {ref.slot}")
        return self

    @model_validator(mode="after")
    def _params_are_referenced(self):
        known = set(self.ir.parameters)
        for phase, steps in self.ir.phases.items():
            for step in steps:
                for value in _scalars(step):
                    if isinstance(value, ParamRef) and value.param not in known:
                        raise ValueError(f"{phase}: unknown parameter {value.param}")
        return self


def _scalars(step: BaseModel):
    for name, value in step:
        if isinstance(value, dict):
            yield from value.values()
        elif isinstance(value, list):
            yield from value
        else:
            yield value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(artifact: Artifact) -> str:
    return hashlib.sha256(_canonical(artifact.model_dump(mode="json")).encode()).hexdigest()


def load(path: Path | str) -> Artifact:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    artifact = Artifact.model_validate(data)
    for state in artifact.scope.initial_states:
        saved = ROOT / state.path
        if not saved.is_file():
            raise FileNotFoundError(f"initial state not found: {state.path}")
        actual = _sha(saved)
        if actual != state.sha256:
            raise ValueError(f"initial state hash mismatch for {state.path}: {actual}")
    return artifact


# --- generators ------------------------------------------------------------------

def _scalar(value: Scalar) -> str:
    if isinstance(value, ParamRef):
        return f"P[{value.param!r}]"
    if isinstance(value, GraspWaistRef):
        return "params['waist_pitch_rad']"
    return repr(float(value))


def _point(value: PointRef) -> str:
    if isinstance(value, LiteralPoint):
        return f"[{value.literal[0]}, {value.literal[1]}, {value.literal[2]}]"
    if isinstance(value, ObservedPoint):
        return {
            "grasp.xyz": "grasp['grasp_xyz_m']",
            "grasp.approach_start": "grasp['approach_start_xyz_m']",
            "palm": "list(observation['left_palm']['position_m'])",
        }[value.observed]
    slot = f", {value.slot!r}" if value.slot else ""
    return f"_place(params, PLACE_{value.place.upper()}_M{slot})"


def _yaw(value: YawRef) -> str:
    return "params['palm_yaw_rad']" if isinstance(value, YawGrasp) else repr(float(value.literal))


def _emit(step: Step, indent: str) -> list[str]:
    """Render one IR step as Python over the `commands` list and a `palm` cursor."""
    if isinstance(step, (WalkTo, MoveTo)):
        if isinstance(step, WalkTo) and step.execution == "linear":
            secs = _scalar(step.seconds) if step.seconds is not None else "APPROACH_S"
            return [f"{indent}target = {_point(step.to)}",
                    f"{indent}commands.append({{'op': 'move_linear', 'x': target[0], 'y': target[1],",
                    f"{indent}                 'z': target[2], 'yaw': {_yaw(step.yaw)},",
                    f"{indent}                 'orientation': {step.orientation!r},",
                    f"{indent}                 'seconds': {secs}}})",
                    f"{indent}palm = list(target)"]
        verb = "_walk" if isinstance(step, WalkTo) else None
        limit = ""
        if isinstance(step, WalkTo) and step.step_m is not None:
            limit = f", {_scalar(step.step_m)}"
        head = [
            f"{indent}target = {_point(step.to)}",
            f"{indent}for point in _walk(palm, target{limit}):"
            if isinstance(step, WalkTo) else None,
            f"{indent}    commands.append(_move(point, {_yaw(step.yaw)}, "
            f"{step.orientation!r}))" if isinstance(step, WalkTo) else None,
            None if isinstance(step, WalkTo) else
            f"{indent}commands.append(_move(target, {_yaw(step.yaw)}, {step.orientation!r}))",
            f"{indent}palm = list(target)",
        ]
        return [line for line in head if line is not None]
    if isinstance(step, LineTo):
        return [f"{indent}target = {_point(step.to)}",
                f"{indent}commands.append({{'op': 'move_linear', 'x': target[0], 'y': target[1],",
                f"{indent}                 'z': target[2], 'yaw': {_yaw(step.yaw)},",
                f"{indent}                 'orientation': {step.orientation!r},",
                f"{indent}                 'seconds': {_scalar(step.seconds)}}})",
                f"{indent}palm = list(target)"]
    if isinstance(step, Joints):
        pairs = ", ".join(f"{name!r}: {_scalar(value)}" for name, value in step.targets.items())
        return [f"{indent}commands.append({{'op': 'joints', 'seconds': {_scalar(step.seconds)},",
                f"{indent}                 'targets': [{{'joint': k, 'radians': v}} "
                f"for k, v in {{{pairs}}}.items()]}})"]
    if isinstance(step, Wait):
        return [f"{indent}commands.append({{'op': 'wait', 'seconds': {_scalar(step.seconds)}}})"]
    if isinstance(step, CloseHand):
        return [f"{indent}commands.append(_hand(CLOSE, {_scalar(step.seconds)}))"]
    if isinstance(step, OpenHand):
        return [f"{indent}commands.append(_hand(OPEN, {_scalar(step.seconds)}))"]
    if isinstance(step, RaiseClear):
        if step.execution == "linear":
            secs = _scalar(step.seconds) if step.seconds is not None else "APPROACH_S"
            return [f"{indent}target = [palm[0], palm[1], max(palm[2] + {_scalar(step.clearance_m)},",
                    f"{indent}                        _place(params, PLACE_ABOVE_M)[2])]",
                    f"{indent}commands.append({{'op': 'move_linear', 'x': target[0], 'y': target[1],",
                    f"{indent}                 'z': target[2], 'yaw': {_yaw(step.yaw)},",
                    f"{indent}                 'orientation': 'keep',",
                    f"{indent}                 'seconds': {secs}}})",
                    f"{indent}palm = list(target)"]
        return [f"{indent}target = [palm[0], palm[1], max(palm[2] + {_scalar(step.clearance_m)},",
                f"{indent}                        _place(params, PLACE_ABOVE_M)[2])]",
                f"{indent}for point in _walk(palm, target):",
                f"{indent}    commands.append(_move(point, {_yaw(step.yaw)}, 'keep'))",
                f"{indent}palm = list(target)"]
    if isinstance(step, DescendToLower):
        if step.execution == "linear":
            secs = _scalar(step.seconds) if step.seconds is not None else "APPROACH_S"
            return [f"{indent}target = [palm[0], palm[1], _place(params, {_scalar(step.height_m)})[2]]",
                    f"{indent}commands.append({{'op': 'move_linear', 'x': target[0], 'y': target[1],",
                    f"{indent}                 'z': target[2], 'yaw': {_yaw(step.yaw)},",
                    f"{indent}                 'orientation': 'keep',",
                    f"{indent}                 'seconds': {secs}}})",
                    f"{indent}palm = list(target)"]
        return [f"{indent}target = [palm[0], palm[1], _place(params, {_scalar(step.height_m)})[2]]",
                f"{indent}for point in _walk(palm, target):",
                f"{indent}    commands.append(_move(point, {_yaw(step.yaw)}, 'keep'))",
                f"{indent}palm = list(target)"]
    if isinstance(step, RetreatUp):
        return [f"{indent}for _index in range({step.steps}):",
                f"{indent}    palm = [palm[0], palm[1], palm[2] + {_scalar(step.distance_m)}]",
                f"{indent}    commands.append(_move(palm, {_yaw(step.yaw)}, 'keep'))"]
    if isinstance(step, RecenterCup):
        return [f"{indent}commands.extend(_recenter(observation, params, "
                f"{_scalar(step.tolerance_m)}, {_scalar(step.step_m)}))"]
    if isinstance(step, Finish):
        return [f"{indent}commands.append({{'op': 'finish'}})"]
    raise TypeError(f"unhandled step: {type(step).__name__}")


def generate_code(artifact: Artifact) -> str:
    params = {key: float(value) for key, value in artifact.ir.parameters.items()}
    params.setdefault("waist_pitch_rad", -0.10)
    close = {key: float(value) for key, value in artifact.ir.close_angles.items()}
    header = [
        '"""Generated by harness.artifact from the YAML artifact. Do not edit.',
        "",
        f"artifact: {artifact.id} v{artifact.version}",
        f"digest: {digest(artifact)}",
        '"""',
        "",
        "import math",
        "",
        f"P = {params!r}",
        f"CLOSE = {close!r}",
        "OPEN = {name: 0.0 for name in CLOSE}",
        f"PLACE_ABOVE_M = {artifact.ir.parameters['place_above_m']!r}",
        f"PLACE_LOWER_M = {artifact.ir.parameters['place_lower_m']!r}",
        f"WAIST_PITCH = {params['waist_pitch_rad']!r}",
        f"APPROACH_S = {artifact.ir.parameters.get('approach_seconds', 2.0)!r}",
        "",
        "",
        "def _walk(start, end, limit=None):",
        "    limit = P['step_m'] if limit is None else limit",
        "    gap = math.dist(start, end)",
        "    count = max(1, math.ceil(gap / limit))",
        "    return [[start[i] + (end[i] - start[i]) * step / count for i in range(3)]",
        "            for step in range(1, count + 1)]",
        "",
        "",
        "def _move(point, yaw, orientation='yaw', seconds=None):",
        "    return {'op': 'move', 'x': point[0], 'y': point[1], 'z': point[2],",
        "            'yaw': yaw, 'orientation': orientation,",
        "            'seconds': APPROACH_S if seconds is None else seconds}",
        "",
        "",
        "def _hand(angles, seconds):",
        "    return {'op': 'joints', 'seconds': seconds,",
        "            'targets': [{'joint': name, 'radians': value} for name, value in angles.items()]}",
        "",
        "",
        f"SLOTS = { {k: list(v) for k, v in artifact.ir.slots.items()} !r}",
        "",
        "",
        "def _place(params, height, slot=None):",
        "    dx, dy = SLOTS[slot] if slot else (0.0, 0.0)",
        "    yaw = params['palm_yaw_rad']",
        "    ox, oy, oz = params['cup_in_palm_m']",
        "    rx = math.cos(yaw) * ox - math.sin(yaw) * oy",
        "    ry = math.sin(yaw) * ox + math.cos(yaw) * oy",
        "    tray = params['tray_floor_m']",
        "    return [tray[0] + dx - rx, tray[1] + dy - ry, tray[2] + height - oz]",
        "",
        "",
        "def _chosen(observation):",
        "    probe = observation.get('grasp_probe')",
        "    if not probe or not probe.get('yaws'):",
        "        raise ValueError('GRASP_UNREACHABLE: no candidate yaw passes the IK check')",
        "    return probe['yaws'][0]",
        "",
        "",
        "def grasp_parameters(observation):",
        "    probe = observation.get('grasp_probe')",
        "    tray = observation.get('tray_floor_center_m')",
        "    if not probe or tray is None:",
        "        raise ValueError('grasp_parameters needs grasp_probe and tray_floor_center_m')",
        "    chosen = _chosen(observation)",
        "    return {'palm_yaw_rad': chosen['palm_yaw_rad'],",
        "            'waist_pitch_rad': chosen.get('waist_pitch_rad', WAIST_PITCH),",
        "            'cup_in_palm_m': list(probe['cup_in_palm_m']),",
        "            'tray_floor_m': list(tray)}",
        "",
        "",
        "def _recenter(observation, params, tolerance, step):",
        "    cups = observation.get('cup_bottoms_m') or []",
        "    if len(cups) != 1:",
        "        return []",
        "    tray = params['tray_floor_m']",
        "    dx, dy = tray[0] - cups[0][0], tray[1] - cups[0][1]",
        "    gap = math.hypot(dx, dy)",
        "    if gap <= tolerance:",
        "        return []",
        "    palm = list(observation['left_palm']['position_m'])",
        "    scale = min(1.0, step / gap)",
        "    point = [palm[0] + dx * scale, palm[1] + dy * scale, palm[2]]",
        "    return [_move(point, params['palm_yaw_rad'], 'keep', 1.5)]",
        "",
    ]
    body = []
    for phase in ("plan", "lift", "correct", "release"):
        signature = "observation" if phase == "plan" else "observation, params"
        body += ["", f"def {phase}({signature}):", "    commands = []"]
        if phase == "plan":
            body.append("    grasp = _chosen(observation)")
            body.append("    params = {'palm_yaw_rad': grasp['palm_yaw_rad'],")
            body.append("              'waist_pitch_rad': grasp.get('waist_pitch_rad', WAIST_PITCH)}")
        body.append("    palm = list(observation['left_palm']['position_m'])")
        for step in artifact.ir.phases[phase]:
            body += _emit(step, "    ")
        body.append("    return commands")
    return "\n".join(header + body) + "\n"


def generate_skill(artifact: Artifact) -> str:
    scope = artifact.scope
    contract = artifact.contract
    lines = [
        f"# {artifact.id} v{artifact.version}",
        "",
        f"Generated from `artifacts/{artifact.id}.yaml` (digest `{digest(artifact)}`). "
        "Do not edit this file; change the YAML and recompile.",
        "",
        f"Status: `{artifact.status}`; provenance: `{artifact.provenance.form}`.",
        artifact.provenance.note or "",
        "Evidence below retains its original program/version scope; projection generation adds no physical qualification.",
        "",
        "## Scope",
        "",
        f"- task: `{scope.task}`",
        f"- assets: {', '.join(f'`{a}`' for a in scope.assets)}",
        f"- initial states: {len(scope.initial_states)} saved state(s), hash-bound",
        "",
        "## Contract",
        "",
        "Preconditions: " + ", ".join(f"`{p}`" for p in contract.preconditions),
        "",
        "Postconditions: " + ", ".join(f"`{p}`" for p in contract.postconditions),
        "",
        "| exit | condition | recovery |",
        "|---|---|---|",
    ]
    for exit_row in contract.failure_exits:
        lines.append(f"| `{exit_row.code}` | {exit_row.condition} | {exit_row.recovery or ''} |")
    lines += ["", "## Body assumptions", ""]
    lines.append(f"- one plain move at most {artifact.assumptions.max_single_move_m:.2f} m")
    lines.append(f"- release cup bottom at {artifact.assumptions.release_height_m:.2f} m above the tray floor")
    if artifact.assumptions.placement_tolerance_m:
        lines.append(f"- placement tolerance {artifact.assumptions.placement_tolerance_m:.3f} m")
    for note in artifact.assumptions.notes:
        lines.append(f"- {note}")
    lines += ["", "## Hand closure", "",
              "Set these joint angles to grip the cup:", ""]
    for name, value in artifact.ir.close_angles.items():
        lines.append(f"- `{name}` = {value}")
    params = {key: float(value) for key, value in artifact.ir.parameters.items()}
    params.setdefault("waist_pitch_rad", -0.10)
    lines += ["", "## Runtime bindings", "",
              "All points are metres in the current pelvis frame; joint/yaw angles are radians.",
              "The caller supplies `observation` with `left_palm.position_m`, `grasp_probe` "
              "and `tray_floor_center_m`. `grasp_probe.yaws` must be nonempty; otherwise exit "
              "`GRASP_UNREACHABLE`. Its first entry supplies `palm_yaw_rad`, "
              "`grasp_xyz_m`, `approach_start_xyz_m` and optional `waist_pitch_rad`.",
              "", "```python", f"P = {params!r}",
              f"CLOSE = {dict(artifact.ir.close_angles)!r}",
              "OPEN = {name: 0.0 for name in CLOSE}",
              f"SLOTS = { {k: list(v) for k, v in artifact.ir.slots.items()} !r}",
              "PLACE_ABOVE_M = P['place_above_m']", "PLACE_LOWER_M = P['place_lower_m']",
              f"APPROACH_S = {artifact.ir.parameters.get('approach_seconds', 2.0)!r}",
              "grasp = observation['grasp_probe']['yaws'][0]",
              "params = {'palm_yaw_rad': grasp['palm_yaw_rad'],",
              "          'waist_pitch_rad': grasp.get('waist_pitch_rad', P['waist_pitch_rad']),",
              "          'cup_in_palm_m': list(observation['grasp_probe']['cup_in_palm_m']),",
              "          'tray_floor_m': list(observation['tray_floor_center_m'])}",
              "```", "",
              "`plan(observation)` selects `grasp` and derives yaw/waist locally. "
              "Before subsequent phases the caller calls `grasp_parameters(observation)` "
              "once and retains that `params` binding. Each phase refreshes the palm cursor "
              "from `observation.left_palm.position_m`; commands run in the listed order.",
              "`_place(params, height, slot=None)` rotates `cup_in_palm_m` by palm yaw, "
              "then subtracts that offset from tray floor + slot xy + height. "
              "A missing slot means [0, 0]. `_walk` splits travel into equally spaced "
              "points no farther than its step limit. A plain move lasts `APPROACH_S`.",
              "`orientation=keep` preserves the current palm quaternion; its yaw argument "
              "is ignored. `orientation=yaw` applies the specified yaw quaternion.",
              "`correct` uses `observation.cup_bottoms_m`; unless exactly one cup is seen "
              "it emits no correction. Otherwise it makes at most one xy correction toward "
              "the tray, capped by its step size, at constant height/orientation for 1.5 s.",
              "", "## Program", ""]
    for phase in ("plan", "lift", "correct", "release"):
        lines.append(f"### {phase}")
        lines.append("")
        for step in artifact.ir.phases[phase]:
            lines.append("- " + _describe(step))
        lines.append("")
    lines += ["## Evidence", ""]
    paired = artifact.evidence.paired
    if paired is None:
        lines.append("- paired: not measured yet")
    else:
        lines.append(f"- paired: `{paired['without'].arm}` {paired['without'].successes}/"
                     f"{paired['without'].episodes} vs `{paired['with'].arm}` "
                     f"{paired['with'].successes}/{paired['with'].episodes}")
    if artifact.evidence.transfer:
        transfer = artifact.evidence.transfer
        groups = ", ".join(f"{k} {v}" for k, v in transfer.by_group.items())
        lines.append(f"- transfer: {transfer.successes}/{transfer.episodes} ({groups})")
    if artifact.evidence.acceptance:
        lines.append(f"- acceptance: `{artifact.evidence.acceptance.run}`")
    lines += ["", "## Limits", ""]
    for limit in artifact.limits:
        lines.append(f"- {limit}")
    return "\n".join(lines) + "\n"


def _describe(step: Step) -> str:
    if isinstance(step, WalkTo):
        limit = _scalar(step.step_m) if step.step_m is not None else "P['step_m']"
        if step.execution == "linear":
            duration = f" in {_scalar(step.seconds)} s" if step.seconds is not None else ""
            return (f"move linearly to {_point(step.to)} from the actual palm{duration}, "
                    f"orientation={step.orientation}, yaw={_yaw(step.yaw)}")
        return (f"walk to {_point(step.to)}, step <= {limit} m, "
                f"orientation={step.orientation}, yaw={_yaw(step.yaw)}")
    if isinstance(step, MoveTo):
        return f"move to {_point(step.to)}, orientation={step.orientation}, yaw={_yaw(step.yaw)}"
    if isinstance(step, LineTo):
        return (f"straight-line carry to {_point(step.to)} in {_scalar(step.seconds)} s, "
                f"orientation={step.orientation}, yaw={_yaw(step.yaw)}")
    if isinstance(step, Joints):
        targets = ", ".join(f"{key}: {_scalar(value)}" for key, value in step.targets.items())
        return f"joints {{{targets}}} for {_scalar(step.seconds)} s"
    if isinstance(step, Wait):
        return f"wait {_scalar(step.seconds)} s"
    if isinstance(step, CloseHand):
        return f"close the hand in {_scalar(step.seconds)} s"
    if isinstance(step, OpenHand):
        return f"open the hand in {_scalar(step.seconds)} s"
    if isinstance(step, RaiseClear):
        if step.execution == "linear":
            mode = "linearly from the actual palm" + (
                f" in {_scalar(step.seconds)} s" if step.seconds is not None else "")
        else:
            mode = "split by P['step_m']"
        return (f"raise to max(palm.z + {_scalar(step.clearance_m)}, "
                f"_place(params, PLACE_ABOVE_M).z), orientation=keep, {mode}")
    if isinstance(step, DescendToLower):
        if step.execution == "linear":
            mode = "linearly from the actual palm" + (
                f" in {_scalar(step.seconds)} s" if step.seconds is not None else "")
        else:
            mode = "split by P['step_m']"
        return (f"descend to _place(params, {_scalar(step.height_m)}).z, "
                f"orientation=keep, {mode}")
    if isinstance(step, RetreatUp):
        return f"retreat upward {step.steps} x {_scalar(step.distance_m)} m, orientation=keep"
    if isinstance(step, RecenterCup):
        return (f"recentre the cup over the tray when off by more than "
                f"{_scalar(step.tolerance_m)} m, in steps of {_scalar(step.step_m)} m")
    return "finish"


def compile_artifact(artifact: Artifact) -> dict:
    code_path = ROOT / artifact.projections.code.path
    skill_path = ROOT / artifact.projections.skill.path
    code_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text(generate_code(artifact), encoding="utf-8")
    skill_path.write_text(generate_skill(artifact), encoding="utf-8")
    ir_path = code_path.parent / "ir.json"
    ir_path.write_text(json.dumps(artifact.ir.model_dump(mode="json"), ensure_ascii=False,
                                  indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact": {"id": artifact.id, "version": artifact.version, "digest": digest(artifact)},
        "dependencies": {
            "generator": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": _sha(Path(__file__))},
            "binding": artifact.binding.model_dump(mode="json"),
        },
        "generated": {
            str(code_path.relative_to(ROOT)): _sha(code_path),
            str(skill_path.relative_to(ROOT)): _sha(skill_path),
            str(ir_path.relative_to(ROOT)): _sha(ir_path),
        },
    }
    manifest_path = code_path.parent / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    return manifest


def compile_local_skill(registry, snapshot_id: str, skill_id: str, output: Path,
                        registration_path: Path) -> dict:
    """Project a single-effect Skill using the existing content-addressed registry.

    The Skill's Op pins the exact CodeModule source; the immutable snapshot is
    the fact source. The registration supplies the hashed physical contract.
    This does not confer validation or change the snapshot.
    """
    from .contracts import Skill

    view = registry.load(snapshot_id)
    skill = view.artifacts[skill_id]
    if not isinstance(skill, Skill) or len(skill.steps) != 1:
        raise ValueError("local projection expects one Skill with one Op")
    step = skill.steps[0]
    op = view.artifacts[step.op_id]
    module = registry.code_projection(snapshot_id)[op.op_id]
    if "registration:" + _sha(registration_path) not in op.dependencies:
        raise ValueError("registration differs from the Op's bound physical contract")
    output.mkdir(parents=True, exist_ok=False)
    (output / "program.py").write_text(module.source, encoding="utf-8")
    ir = {"skill": skill.to_dict(), "op": op.to_dict(),
          "code_module_digest": module.digest(), "source_sha256": module.source_sha256}
    (output / "ir.json").write_text(json.dumps(ir, indent=2) + "\n", encoding="utf-8")
    registration = json.loads(registration_path.read_text())
    text = [f"# {skill.id} v{skill.version}", "",
            f"Generated from registry snapshot `{snapshot_id}`; digest `{skill.digest()}`.",
            f"Status: {skill.status.value}; validation: {skill.validation.value if skill.validation else 'none'}.",
            "", "Input: `act(observation, task, state)`. Public proprioception supplies "
            "joints (q, target), left_palm (current_pelvis, metres, quaternion_xyzw), "
            "contact loads and guard; task supplies the explicit pose contract. "
            "`init(profile)` optionally receives known robot geometry. State is local to a call.",
            "", "Preconditions: " + ", ".join(p.name for p in op.pre),
            "Postconditions: " + ", ".join(p.name for p in op.post),
            f"Failure exits: {', '.join(op.failure_codes)}; stop and report, no hidden recovery.",
            f"Budget: {op.budget_s} simulation seconds; joint commands and waits only.",
            "", "Physical contract (authoritative registration, hashed in manifest):", "```json",
            json.dumps(registration["local_contract"], indent=2), "```", "",
            "The code projection is the exact registered source, including action ordering, "
            "orientation handling and failure branches. The semantic card describes the "
            "declared contract; only the independent verdict establishes physical effects.",
            f"Source module: {module.id} v{module.version}, sha256 `{module.source_sha256}`.",
            "Scope: " + json.dumps(skill.scope.to_dict(), sort_keys=True), ""]
    (output / "SKILL.md").write_text("\n".join(text), encoding="utf-8")
    manifest = {"artifact": {"id": skill.id, "version": skill.version, "digest": skill.digest()},
                "snapshot_id": snapshot_id, "fact_source": str(registry.root.resolve().relative_to(ROOT)),
                "dependencies": {"registration": _sha(registration_path),
                                 "generator": _sha(Path(__file__)),
                                 "op": op.digest(), "code_module": module.digest(),
                                 "source": module.source_sha256,
                                 "bound_files": registration["dependencies"]},
                "generated": {name: _sha(output / name)
                              for name in ("program.py", "SKILL.md", "ir.json")}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
