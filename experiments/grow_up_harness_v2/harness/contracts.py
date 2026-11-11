"""Typed artifacts, programs, episodes and feedback.

Pure data and validation. No MuJoCo, no registry, no IO.
Scope cover is an exact task id or template plus an asset subset. Predicate
names are a closed set. Code hashes are computed from source text.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    REJECTED = "rejected"
    RETIRED = "retired"


class Validation(str, Enum):
    PAIRED = "paired"
    REPAIR_LINEAGE = "repair_lineage"
    EXPANDED = "expanded"


class PlanMode(str, Enum):
    REUSE = "reuse"
    COMPOSE = "compose"
    SYNTHESIZE = "synthesize"
    REFUSE = "refuse"


class Outcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    INVALID = "invalid"


ALLOWED_PREDICATES = frozenset(
    {
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
        "HeldLifted",
        # Explicit-pose local task goal, independently replayed by local_reach.
        # Like HeldLifted this is not one of the ten TP01 boundary predicates.
        "ExplicitPoseHeld",
    }
)

ALLOWED_IMPORTS = frozenset(
    {
        "math",
        "numpy",
        "numpy.linalg",
        "numpy.random",
        "numpy.fft",
    }
)

OBSERVATION_KEYS = frozenset(
    {
        "simulation_seconds",
        "joints",
        "left_palm",
        "tactile_joint_load_N",
        "guard",
        "rgbd",
    }
)

# These names are evaluator state. They are rejected even though a caller
# might treat them as just another measurement.
EVALUATOR_ONLY_KEYS = frozenset(
    {
        "target_pose",
        "object_pose",
        "object_position_m",
        "contact_load_N",
        "threshold",
        "thresholds",
        "raw_frames",
        "spectator_camera",
        "test_split",
        "goal_truth",
    }
)

DECISIONS = frozenset({"promote", "reject", "demote", "retire"})
VERDICTS = frozenset({"success", "failure"})

_SHA256 = re.compile(r"[0-9a-f]{64}")


class ContractError(ValueError):
    """An artifact, program or observation violates a typed contract."""


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _enum(cls: type[Enum], value: Any, name: str):
    if isinstance(value, cls):
        return value
    try:
        return cls(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"invalid {name}: {value!r}") from exc


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _version(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractError("version must be an int >= 1")
    return value


def _index(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError(f"{name} must be an int >= 0")
    return value


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ContractError(f"{name} must be a positive finite number")
    return float(value)


def _finite_time(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("time must be finite and >= 0")
    if not math.isfinite(value) or value < 0:
        raise ContractError("time must be finite and >= 0")
    return float(value)


def _scalar(value: Any) -> float | str:
    # Ints are stored as floats so 1 and 1.0 do not fork a content digest.
    if isinstance(value, str):
        if not value:
            raise ContractError("empty string")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ContractError("value must be a finite number or a non-empty string")
    return float(value)


def _as_tuple(value: Any, name: str) -> tuple:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ContractError(f"{name} must be a tuple")


def _pairs(value: Any, name: str) -> tuple[tuple[str, float | str], ...]:
    raw = _as_tuple(value, name)
    pairs: list[tuple[str, float | str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ContractError(f"{name} entries must be pairs")
        key, raw_value = item
        if not isinstance(key, str) or not key:
            raise ContractError(f"{name} key must be a non-empty string")
        if key in seen:
            raise ContractError(f"duplicate {name} key: {key}")
        seen.add(key)
        pairs.append((key, _scalar(raw_value)))
    return tuple(pairs)


def _strings(value: Any, name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    raw = _as_tuple(value, name)
    if not allow_empty and not raw:
        raise ContractError(f"{name} must be non-empty")
    items: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item:
            raise ContractError(f"{name} entries must be non-empty strings")
        items.append(item)
    return tuple(items)


def _assets(value: Any) -> frozenset[str]:
    if isinstance(value, str) or not isinstance(value, (set, frozenset, list, tuple)):
        raise ContractError("assets must be a set of names")
    assets = frozenset(value)
    if not assets or any(not isinstance(item, str) or not item for item in assets):
        raise ContractError("assets must be non-empty names")
    return assets


def _sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ContractError(f"{name} must be 64 lowercase hex characters")
    return value


def _predicates(value: Any, name: str, *, allow_empty: bool) -> tuple[Predicate, ...]:
    raw = _as_tuple(value, name)
    if not allow_empty and not raw:
        raise ContractError(f"{name} must be non-empty")
    items: list[Predicate] = []
    seen: set[tuple] = set()
    for item in raw:
        if not isinstance(item, Predicate):
            raise ContractError(f"{name} entries must be Predicate")
        identity = item.key()
        if identity in seen:
            raise ContractError(f"duplicate predicate in {name}")
        seen.add(identity)
        items.append(item)
    return tuple(items)


def _instances(value: Any, cls: type, name: str) -> tuple:
    raw = _as_tuple(value, name)
    for item in raw:
        if not isinstance(item, cls):
            raise ContractError(f"{name} entries must be {cls.__name__}")
    return tuple(raw)


def _repairs(value: Any) -> tuple[tuple[str, str], ...]:
    raw = _as_tuple(value, "on_failure")
    repairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ContractError("on_failure entries must be (code, target) pairs")
        code, target = item
        if not isinstance(code, str) or not code or not isinstance(target, str) or not target:
            raise ContractError("on_failure needs a non-empty code and target")
        if code in seen:
            raise ContractError(f"duplicate on_failure code: {code}")
        seen.add(code)
        repairs.append((code, target))
    return tuple(repairs)


def _failure_codes(value: Any) -> tuple[str, ...]:
    codes = _strings(value, "failure_codes", allow_empty=False)
    if len(codes) != len(set(codes)):
        raise ContractError("duplicate failure code")
    return codes


def _flag_pairs(value: Any, name: str) -> tuple[tuple[str, bool], ...]:
    raw = _as_tuple(value, name)
    flags: list[tuple[str, bool]] = []
    for item in raw:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ContractError(f"{name} entries must be pairs")
        key, flag = item
        if not isinstance(key, str) or not key:
            raise ContractError(f"{name} name must be a non-empty string")
        if not isinstance(flag, bool):
            raise ContractError(f"{name} value must be bool")
        flags.append((key, flag))
    return tuple(flags)


def _metric_pairs(value: Any) -> tuple[tuple[str, float], ...]:
    raw = _as_tuple(value, "metrics")
    metrics: list[tuple[str, float]] = []
    for item in raw:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ContractError("metrics entries must be pairs")
        key, number = item
        if not isinstance(key, str) or not key:
            raise ContractError("metric name must be a non-empty string")
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ContractError("metric value must be a finite number")
        metrics.append((key, float(number)))
    return tuple(metrics)


def _claim(status: Status, validation: Validation | None, kind: str) -> None:
    if status is Status.CANDIDATE and validation is not None:
        raise ContractError(f"candidate {kind} cannot claim a validation level")
    if status is Status.VALIDATED and validation is None:
        raise ContractError(f"validated {kind} needs a validation level")


def _scope(value: Any) -> Scope:
    if not isinstance(value, Scope):
        raise ContractError("scope must be a Scope")
    return value


def _string_keys(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be a dict")
    if any(not isinstance(key, str) or not key for key in value):
        raise ContractError(f"{name} keys must be non-empty strings")
    return dict(value)


def _failed_pair(failed_op: Any, failed_step: Any) -> tuple[str | None, int | None]:
    if failed_op is None:
        if failed_step is not None:
            raise ContractError("failed_step requires failed_op")
        return None, None
    op = _text(failed_op, "failed_op")
    if isinstance(failed_step, bool) or not isinstance(failed_step, int) or failed_step < 0:
        raise ContractError("failed_step must be an int >= 0 when failed_op is set")
    return op, failed_step


def _arg(args: tuple[tuple[str, float | str], ...], key: str, default: Any) -> Any:
    for name, value in args:
        if name == key:
            return value
    return default


@dataclass(frozen=True)
class Predicate:
    name: str
    params: tuple[tuple[str, float | str], ...] = ()

    def __post_init__(self) -> None:
        name = _text(self.name, "predicate name")
        if name not in ALLOWED_PREDICATES:
            raise ContractError(f"unknown predicate: {name}")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "params", _pairs(self.params, "params"))

    def key(self) -> tuple[str, tuple[tuple[str, float | str], ...]]:
        return (self.name, self.params)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "params": [[key, value] for key, value in self.params],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Predicate:
        return cls(name=data["name"], params=data.get("params", ()))


@dataclass(frozen=True)
class Scope:
    task: str
    assets: frozenset[str]
    stage: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "task", _text(self.task, "task"))
        object.__setattr__(self, "assets", _assets(self.assets))
        object.__setattr__(self, "stage", _optional_text(self.stage, "stage"))

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "assets": sorted(self.assets),
            "stage": self.stage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Scope:
        return cls(
            task=data["task"],
            assets=frozenset(data["assets"]),
            stage=data.get("stage"),
        )


@dataclass(frozen=True)
class TaskSpec:
    id: str
    template: str
    instruction: str
    assets: frozenset[str]
    goal: Predicate
    budget_s: float = 60.0
    split: str = "practice"

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "template", _text(self.template, "template"))
        object.__setattr__(self, "instruction", _text(self.instruction, "instruction"))
        object.__setattr__(self, "assets", _assets(self.assets))
        if not isinstance(self.goal, Predicate):
            raise ContractError("goal must be a Predicate")
        object.__setattr__(self, "budget_s", _positive(self.budget_s, "budget_s"))
        object.__setattr__(self, "split", _text(self.split, "split"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "template": self.template,
            "instruction": self.instruction,
            "assets": sorted(self.assets),
            "goal": self.goal.to_dict(),
            "budget_s": self.budget_s,
            "split": self.split,
        }


def scope_covers(scope: Scope, task: TaskSpec) -> bool:
    """Exact cover: scope assets are a subset, and task id or template matches.

    A shared underscore prefix is not cover. v1 treated that as a match.
    """
    if not isinstance(scope, Scope) or not isinstance(task, TaskSpec):
        raise ContractError("scope_covers expects a Scope and a TaskSpec")
    if not scope.assets <= task.assets:
        return False
    return scope.task == task.template or scope.task == task.id


@dataclass(frozen=True)
class Snapshot:
    id: str
    refs: tuple[tuple[str, str], ...]
    parent: str | None
    label: str
    frozen: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        refs = _as_tuple(self.refs, "refs")
        seen: set[str] = set()
        parsed: list[tuple[str, str]] = []
        for item in refs:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ContractError("snapshot refs must be (artifact_id, digest) pairs")
            artifact_id, digest = item
            artifact_id = _text(artifact_id, "artifact id")
            digest = _sha256(digest, "digest")
            if artifact_id in seen:
                raise ContractError(f"snapshot has duplicate artifact id: {artifact_id}")
            seen.add(artifact_id)
            parsed.append((artifact_id, digest))
        object.__setattr__(self, "refs", tuple(parsed))
        object.__setattr__(self, "parent", _optional_text(self.parent, "parent"))
        object.__setattr__(self, "label", _text(self.label, "label"))
        if not isinstance(self.frozen, bool):
            raise ContractError("frozen must be bool")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "refs": [[artifact_id, digest] for artifact_id, digest in self.refs],
            "parent": self.parent,
            "label": self.label,
            "frozen": self.frozen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Snapshot:
        return cls(
            id=data["id"],
            refs=tuple((artifact_id, digest) for artifact_id, digest in data["refs"]),
            parent=data.get("parent"),
            label=data["label"],
            frozen=data.get("frozen", False),
        )


@dataclass(frozen=True)
class Step:
    op_id: str
    args: tuple[tuple[str, float | str], ...] = ()
    label: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "op_id", _text(self.op_id, "op_id"))
        object.__setattr__(self, "args", _pairs(self.args, "args"))
        object.__setattr__(self, "label", _optional_text(self.label, "label"))

    def arg(self, key: str, default: Any = None) -> Any:
        return _arg(self.args, key, default)

    def to_dict(self) -> dict:
        return {
            "op_id": self.op_id,
            "args": [[key, value] for key, value in self.args],
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Step:
        return cls(
            op_id=data["op_id"],
            args=data.get("args", ()),
            label=data.get("label"),
        )


@dataclass(frozen=True)
class CodeModule:
    id: str
    version: int
    scope: Scope
    status: Status
    source: str
    allowed_imports: tuple[str, ...]
    tests: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    sandbox: str = "seccomp-v1"
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "version", _version(self.version))
        object.__setattr__(self, "scope", _scope(self.scope))
        object.__setattr__(self, "status", _enum(Status, self.status, "status"))
        object.__setattr__(self, "source", _text(self.source, "source"))
        imports = _strings(self.allowed_imports, "allowed_imports", allow_empty=False)
        unsafe = [name for name in imports if name not in ALLOWED_IMPORTS]
        if unsafe:
            raise ContractError(f"imports not allowed in the worker sandbox: {unsafe}")
        object.__setattr__(self, "allowed_imports", imports)
        object.__setattr__(self, "tests", _strings(self.tests, "tests"))
        object.__setattr__(self, "dependencies", _strings(self.dependencies, "dependencies"))
        object.__setattr__(self, "sandbox", _text(self.sandbox, "sandbox"))
        object.__setattr__(self, "evidence", _strings(self.evidence, "evidence"))

    @property
    def source_sha256(self) -> str:
        return hashlib.sha256(self.source.encode("utf-8")).hexdigest()

    @property
    def kind(self) -> str:
        return "code"

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "version": self.version,
            "scope": self.scope.to_dict(),
            "status": self.status.value,
            "source": self.source,
            "source_sha256": self.source_sha256,
            "allowed_imports": list(self.allowed_imports),
            "tests": list(self.tests),
            "dependencies": list(self.dependencies),
            "sandbox": self.sandbox,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class Op:
    op_id: str
    version: int
    scope: Scope
    status: Status
    pre: tuple[Predicate, ...]
    post: tuple[Predicate, ...]
    budget_s: float
    failure_codes: tuple[str, ...]
    implementation: str | None
    implementation_sha256: str | None
    builtin: bool = False
    arg_keys: tuple[str, ...] = ()
    required_arg_keys: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "op_id", _text(self.op_id, "op_id"))
        object.__setattr__(self, "version", _version(self.version))
        object.__setattr__(self, "scope", _scope(self.scope))
        object.__setattr__(self, "status", _enum(Status, self.status, "status"))
        object.__setattr__(self, "pre", _predicates(self.pre, "pre", allow_empty=True))
        object.__setattr__(self, "post", _predicates(self.post, "post", allow_empty=False))
        object.__setattr__(self, "budget_s", _positive(self.budget_s, "budget_s"))
        object.__setattr__(self, "failure_codes", _failure_codes(self.failure_codes))
        if not isinstance(self.builtin, bool):
            raise ContractError("builtin must be bool")
        arg_keys = _strings(self.arg_keys, "arg_keys")
        if len(arg_keys) != len(set(arg_keys)):
            raise ContractError("duplicate arg key")
        required = _strings(self.required_arg_keys, "required_arg_keys")
        if len(required) != len(set(required)):
            raise ContractError("duplicate required arg key")
        if not set(required) <= set(arg_keys):
            raise ContractError("required_arg_keys must be a subset of arg_keys")
        object.__setattr__(self, "arg_keys", arg_keys)
        object.__setattr__(self, "required_arg_keys", required)
        if self.builtin:
            if self.implementation is not None or self.implementation_sha256 is not None:
                raise ContractError("builtin op cannot carry an implementation")
            implementation = None
            implementation_sha256 = None
        else:
            # implementation is a CodeModule id. The sha256 is that module's source.
            implementation = _text(self.implementation, "implementation")
            implementation_sha256 = _sha256(self.implementation_sha256, "implementation_sha256")
        object.__setattr__(self, "implementation", implementation)
        object.__setattr__(self, "implementation_sha256", implementation_sha256)
        object.__setattr__(self, "dependencies", _strings(self.dependencies, "dependencies"))
        object.__setattr__(self, "evidence", _strings(self.evidence, "evidence"))

    @property
    def kind(self) -> str:
        return "op"

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "op_id": self.op_id,
            "version": self.version,
            "scope": self.scope.to_dict(),
            "status": self.status.value,
            "pre": [item.to_dict() for item in self.pre],
            "post": [item.to_dict() for item in self.post],
            "budget_s": self.budget_s,
            "failure_codes": list(self.failure_codes),
            "implementation": self.implementation,
            "implementation_sha256": self.implementation_sha256,
            "builtin": self.builtin,
            "arg_keys": list(self.arg_keys),
            "required_arg_keys": list(self.required_arg_keys),
            "dependencies": list(self.dependencies),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class Skill:
    id: str
    version: int
    scope: Scope
    status: Status
    validation: Validation | None
    steps: tuple[Step, ...]
    pre: tuple[Predicate, ...] = ()
    post: tuple[Predicate, ...] = ()
    on_failure: tuple[tuple[str, str], ...] = ()
    evidence: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "version", _version(self.version))
        object.__setattr__(self, "scope", _scope(self.scope))
        status = _enum(Status, self.status, "status")
        validation = None if self.validation is None else _enum(Validation, self.validation, "validation")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "validation", validation)
        _claim(status, validation, "skill")
        steps = _instances(self.steps, Step, "steps")
        if not steps:
            raise ContractError("skill needs at least one step")
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "pre", _predicates(self.pre, "pre", allow_empty=True))
        object.__setattr__(self, "post", _predicates(self.post, "post", allow_empty=False))
        object.__setattr__(self, "on_failure", _repairs(self.on_failure))
        object.__setattr__(self, "evidence", _strings(self.evidence, "evidence"))
        object.__setattr__(self, "dependencies", _strings(self.dependencies, "dependencies"))

    @property
    def kind(self) -> str:
        return "skill"

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "version": self.version,
            "scope": self.scope.to_dict(),
            "status": self.status.value,
            "validation": self.validation.value if self.validation else None,
            "steps": [step.to_dict() for step in self.steps],
            "pre": [item.to_dict() for item in self.pre],
            "post": [item.to_dict() for item in self.post],
            "on_failure": [[code, target] for code, target in self.on_failure],
            "evidence": list(self.evidence),
            "dependencies": list(self.dependencies),
        }


@dataclass(frozen=True)
class Procedure:
    """A composition of skills. This type stores the composition; it does not run it."""

    id: str
    version: int
    scope: Scope
    status: Status
    validation: Validation | None
    skill_ids: tuple[str, ...]
    steps: tuple[Step, ...]
    pre: tuple[Predicate, ...] = ()
    post: tuple[Predicate, ...] = ()
    on_failure: tuple[tuple[str, str], ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "version", _version(self.version))
        object.__setattr__(self, "scope", _scope(self.scope))
        status = _enum(Status, self.status, "status")
        validation = None if self.validation is None else _enum(Validation, self.validation, "validation")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "validation", validation)
        _claim(status, validation, "procedure")
        object.__setattr__(self, "skill_ids", _strings(self.skill_ids, "skill_ids", allow_empty=False))
        steps = _instances(self.steps, Step, "steps")
        if not steps:
            raise ContractError("procedure needs at least one step")
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "pre", _predicates(self.pre, "pre", allow_empty=True))
        object.__setattr__(self, "post", _predicates(self.post, "post", allow_empty=False))
        object.__setattr__(self, "on_failure", _repairs(self.on_failure))
        object.__setattr__(self, "evidence", _strings(self.evidence, "evidence"))

    @property
    def kind(self) -> str:
        return "procedure"

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "version": self.version,
            "scope": self.scope.to_dict(),
            "status": self.status.value,
            "validation": self.validation.value if self.validation else None,
            "skill_ids": list(self.skill_ids),
            "steps": [step.to_dict() for step in self.steps],
            "pre": [item.to_dict() for item in self.pre],
            "post": [item.to_dict() for item in self.post],
            "on_failure": [[code, target] for code, target in self.on_failure],
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class ProgramStep:
    index: int
    op_id: str
    op_version: int
    args: tuple[tuple[str, float | str], ...] = ()
    label: str | None = None
    source_skill: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", _index(self.index, "index"))
        object.__setattr__(self, "op_id", _text(self.op_id, "op_id"))
        object.__setattr__(self, "op_version", _version(self.op_version))
        object.__setattr__(self, "args", _pairs(self.args, "args"))
        object.__setattr__(self, "label", _optional_text(self.label, "label"))
        object.__setattr__(self, "source_skill", _optional_text(self.source_skill, "source_skill"))

    def arg(self, key: str, default: Any = None) -> Any:
        return _arg(self.args, key, default)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "op_id": self.op_id,
            "op_version": self.op_version,
            "args": [[key, value] for key, value in self.args],
            "label": self.label,
            "source_skill": self.source_skill,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProgramStep:
        return cls(
            index=data["index"],
            op_id=data["op_id"],
            op_version=data["op_version"],
            args=data.get("args", ()),
            label=data.get("label"),
            source_skill=data.get("source_skill"),
        )


@dataclass(frozen=True)
class TaskProgram:
    id: str
    task_id: str
    snapshot_id: str
    mode: PlanMode
    steps: tuple[ProgramStep, ...]
    artifact_ids: tuple[str, ...]
    on_failure: tuple[tuple[str, str], ...] = ()
    budget_s: float = 60.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "task_id", _text(self.task_id, "task_id"))
        object.__setattr__(self, "snapshot_id", _text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "mode", _enum(PlanMode, self.mode, "mode"))
        steps = _instances(self.steps, ProgramStep, "steps")
        if not steps:
            raise ContractError("program needs at least one step")
        indices = [step.index for step in steps]
        if indices != list(range(len(steps))):
            raise ContractError("program step indices must be contiguous from zero")
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "artifact_ids", _strings(self.artifact_ids, "artifact_ids"))
        object.__setattr__(self, "on_failure", _repairs(self.on_failure))
        object.__setattr__(self, "budget_s", _positive(self.budget_s, "budget_s"))

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "snapshot_id": self.snapshot_id,
            "mode": self.mode.value,
            "steps": [step.to_dict() for step in self.steps],
            "artifact_ids": list(self.artifact_ids),
            "on_failure": [[code, target] for code, target in self.on_failure],
            "budget_s": self.budget_s,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskProgram:
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            snapshot_id=data["snapshot_id"],
            mode=data["mode"],
            steps=tuple(ProgramStep.from_dict(item) for item in data["steps"]),
            artifact_ids=data["artifact_ids"],
            on_failure=data["on_failure"],
            budget_s=data["budget_s"],
        )


@dataclass(frozen=True)
class ProgramArtifact:
    id: str
    version: int
    task_id: str
    scope: Scope
    status: Status
    validation: Validation | None
    program: TaskProgram
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "version", _version(self.version))
        object.__setattr__(self, "task_id", _text(self.task_id, "task_id"))
        object.__setattr__(self, "scope", _scope(self.scope))
        status = _enum(Status, self.status, "status")
        validation = None if self.validation is None else _enum(Validation, self.validation, "validation")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "validation", validation)
        _claim(status, validation, "program")
        if not isinstance(self.program, TaskProgram):
            raise ContractError("program must be a TaskProgram")
        if self.program.task_id != self.task_id:
            raise ContractError("program artifact task_id does not match program")
        object.__setattr__(self, "evidence", _strings(self.evidence, "evidence"))

    @property
    def kind(self) -> str:
        return "program"

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "version": self.version,
            "task_id": self.task_id,
            "scope": self.scope.to_dict(),
            "status": self.status.value,
            "validation": self.validation.value if self.validation else None,
            "program": self.program.to_dict(),
            "evidence": list(self.evidence),
        }


def _nonnegative_ints(value: Any, name: str) -> tuple[int, ...]:
    raw = _as_tuple(value, name)
    if not raw or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in raw):
        raise ContractError(f"{name} must be a non-empty tuple of ints >= 0")
    return tuple(raw)


@dataclass(frozen=True)
class PolicyArtifact:
    """A learned policy checkpoint with its contract, training and evaluation spec.

    This is an artifact in the same registry as code/skill/procedure artifacts.
    The checkpoint is referenced by path and SHA; the artifact itself is small.
    ``code`` and ``skill`` projections are generated from this record, not
    maintained as separate sources. A candidate cannot claim a validation level.
    """

    id: str
    version: int
    scope: Scope
    status: Status
    validation: Validation | None
    checkpoint: dict
    policy_type: str
    observation_keys: tuple[str, ...]
    action: dict
    training: dict
    evaluation: dict
    pre: tuple[Predicate, ...]
    post: tuple[Predicate, ...]
    failure_codes: tuple[str, ...]
    evidence: tuple[str, ...] = ()
    limits: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "version", _version(self.version))
        object.__setattr__(self, "scope", _scope(self.scope))
        status = _enum(Status, self.status, "status")
        validation = None if self.validation is None else _enum(Validation, self.validation, "validation")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "validation", validation)
        _claim(status, validation, "policy")

        checkpoint = _string_keys(self.checkpoint, "checkpoint")
        _text(checkpoint.get("path"), "checkpoint.path")
        _sha256(checkpoint.get("sha256"), "checkpoint.sha256")
        object.__setattr__(self, "checkpoint", checkpoint)
        object.__setattr__(self, "policy_type", _text(self.policy_type, "policy_type"))
        object.__setattr__(self, "observation_keys",
                           _strings(self.observation_keys, "observation_keys", allow_empty=False))

        action = _string_keys(self.action, "action")
        object.__setattr__(self, "action", action)
        _strings(action.get("joint_names"), "action.joint_names", allow_empty=False)
        _text(action.get("units"), "action.units")
        _version(action.get("horizon"))
        _positive(action.get("fps"), "action.fps")

        training = _string_keys(self.training, "training")
        object.__setattr__(self, "training", training)
        _text(training.get("dataset_path"), "training.dataset_path")
        _sha256(training.get("dataset_sha256"), "training.dataset_sha256")
        _nonnegative_ints(training.get("train_episodes"), "training.train_episodes")
        _nonnegative_ints(training.get("validation_episodes"), "training.validation_episodes")
        _text(training.get("objective"), "training.objective")
        _index(training.get("optimizer_steps"), "training.optimizer_steps")
        _index(training.get("selected_step"), "training.selected_step")
        _index(training.get("seed"), "training.seed")

        evaluation = _string_keys(self.evaluation, "evaluation")
        object.__setattr__(self, "evaluation", evaluation)
        _text(evaluation.get("official_evaluator"), "evaluation.official_evaluator")
        _text(evaluation.get("dense_evaluator"), "evaluation.dense_evaluator")
        _strings(evaluation.get("initial_states"), "evaluation.initial_states", allow_empty=False)
        _strings(evaluation.get("metrics"), "evaluation.metrics", allow_empty=False)

        object.__setattr__(self, "pre", _predicates(self.pre, "pre", allow_empty=False))
        object.__setattr__(self, "post", _predicates(self.post, "post", allow_empty=False))
        object.__setattr__(self, "failure_codes", _failure_codes(self.failure_codes))
        object.__setattr__(self, "evidence", _strings(self.evidence, "evidence"))
        object.__setattr__(self, "limits", _strings(self.limits, "limits", allow_empty=False))

    @property
    def kind(self) -> str:
        return "policy"

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "version": self.version,
            "scope": self.scope.to_dict(),
            "status": self.status.value,
            "validation": self.validation.value if self.validation else None,
            "checkpoint": dict(self.checkpoint),
            "policy_type": self.policy_type,
            "observation_keys": list(self.observation_keys),
            "action": dict(self.action),
            "training": dict(self.training),
            "evaluation": dict(self.evaluation),
            "pre": [item.to_dict() for item in self.pre],
            "post": [item.to_dict() for item in self.post],
            "failure_codes": list(self.failure_codes),
            "evidence": list(self.evidence),
            "limits": list(self.limits),
        }


@dataclass(frozen=True)
class MemoryNote:
    id: str
    text: str
    scope: Scope
    status: Status
    evidence: tuple[str, ...] = ()
    supersedes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "text", _text(self.text, "text"))
        object.__setattr__(self, "scope", _scope(self.scope))
        object.__setattr__(self, "status", _enum(Status, self.status, "status"))
        object.__setattr__(self, "evidence", _strings(self.evidence, "evidence"))
        object.__setattr__(self, "supersedes", _optional_text(self.supersedes, "supersedes"))

    @property
    def kind(self) -> str:
        return "memory"

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "text": self.text,
            "scope": self.scope.to_dict(),
            "status": self.status.value,
            "evidence": list(self.evidence),
            "supersedes": self.supersedes,
        }


@dataclass(frozen=True)
class ValidationReport:
    id: str
    candidate_id: str
    candidate_digest: str
    validation: Validation
    protocol: str
    baseline_episode: str | None
    treatment_episode: str | None
    initial_state_sha256: str
    metrics: tuple[tuple[str, float], ...]
    contract_tests: tuple[tuple[str, bool], ...]
    regression: tuple[tuple[str, bool], ...]
    decision: str
    evidence: tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id"))
        object.__setattr__(self, "candidate_id", _text(self.candidate_id, "candidate_id"))
        object.__setattr__(
            self,
            "candidate_digest",
            _sha256(self.candidate_digest, "candidate_digest"),
        )
        validation = _enum(Validation, self.validation, "validation")
        object.__setattr__(self, "validation", validation)
        object.__setattr__(self, "protocol", _text(self.protocol, "protocol"))
        baseline = _optional_text(self.baseline_episode, "baseline_episode")
        treatment = _optional_text(self.treatment_episode, "treatment_episode")
        object.__setattr__(self, "baseline_episode", baseline)
        object.__setattr__(self, "treatment_episode", treatment)
        object.__setattr__(
            self,
            "initial_state_sha256",
            _sha256(self.initial_state_sha256, "initial_state_sha256"),
        )
        object.__setattr__(self, "metrics", _metric_pairs(self.metrics))
        contract_tests = _flag_pairs(self.contract_tests, "contract_tests")
        regression = _flag_pairs(self.regression, "regression")
        object.__setattr__(self, "contract_tests", contract_tests)
        object.__setattr__(self, "regression", regression)
        decision = _text(self.decision, "decision")
        if decision not in DECISIONS:
            raise ContractError(f"invalid decision: {decision}")
        if decision == "promote" and not all(flag for _, flag in contract_tests):
            raise ContractError("promote requires every contract test to pass")
        if decision == "promote" and not all(flag for _, flag in regression):
            raise ContractError("promote requires every regression check to pass")
        object.__setattr__(self, "decision", decision)
        if validation is Validation.PAIRED and baseline is None and treatment is None:
            raise ContractError("paired validation needs a baseline or treatment episode")
        if validation is Validation.REPAIR_LINEAGE and (baseline is None or treatment is None):
            raise ContractError("repair_lineage needs both baseline and treatment episodes")
        object.__setattr__(self, "evidence", _strings(self.evidence, "evidence"))
        object.__setattr__(self, "created_at", _text(self.created_at, "created_at"))

    @property
    def kind(self) -> str:
        return "validation"

    def digest(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "validation": self.validation.value,
            "protocol": self.protocol,
            "baseline_episode": self.baseline_episode,
            "treatment_episode": self.treatment_episode,
            "initial_state_sha256": self.initial_state_sha256,
            "metrics": [[key, value] for key, value in self.metrics],
            "contract_tests": [[key, value] for key, value in self.contract_tests],
            "regression": [[key, value] for key, value in self.regression],
            "decision": self.decision,
            "evidence": list(self.evidence),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Observation:
    time: float
    payload: dict

    def __post_init__(self) -> None:
        object.__setattr__(self, "time", _finite_time(self.time))
        payload = _string_keys(self.payload, "payload")
        unknown = set(payload) - OBSERVATION_KEYS
        leaked = unknown & EVALUATOR_ONLY_KEYS
        if leaked:
            raise ContractError(f"evaluator-only keys in observation: {sorted(leaked)}")
        if unknown:
            raise ContractError(f"unknown observation keys: {sorted(unknown)}")
        if "simulation_seconds" not in payload:
            raise ContractError("observation payload must include simulation_seconds")
        object.__setattr__(self, "payload", payload)

    def agent_view(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True)
class Feedback:
    episode_id: str
    verdict: str
    stage: str | None
    failure_code: str | None
    failed_op: str | None
    failed_step: int | None
    agent_visible: dict
    evaluator_only: dict

    def __post_init__(self) -> None:
        object.__setattr__(self, "episode_id", _text(self.episode_id, "episode_id"))
        verdict = _text(self.verdict, "verdict")
        if verdict not in VERDICTS:
            raise ContractError(f"invalid verdict: {verdict}")
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(self, "stage", _optional_text(self.stage, "stage"))
        object.__setattr__(self, "failure_code", _optional_text(self.failure_code, "failure_code"))
        failed_op, failed_step = _failed_pair(self.failed_op, self.failed_step)
        object.__setattr__(self, "failed_op", failed_op)
        object.__setattr__(self, "failed_step", failed_step)
        agent = _string_keys(self.agent_visible, "agent_visible")
        evaluator = _string_keys(self.evaluator_only, "evaluator_only")
        overlap = set(agent) & set(evaluator)
        if overlap:
            raise ContractError(f"feedback field leaked across boundary: {sorted(overlap)}")
        object.__setattr__(self, "agent_visible", agent)
        object.__setattr__(self, "evaluator_only", evaluator)

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "verdict": self.verdict,
            "stage": self.stage,
            "failure_code": self.failure_code,
            "failed_op": self.failed_op,
            "failed_step": self.failed_step,
            "agent_visible": dict(self.agent_visible),
            "evaluator_only": dict(self.evaluator_only),
        }


@dataclass
class EpisodeResult:
    episode_id: str
    outcome: Outcome
    program_id: str | None
    program_sha256: str | None
    snapshot_id: str | None
    initial_state_sha256: str
    final_state_sha256: str
    failure_code: str | None
    failed_op: str | None
    failed_step: int | None
    replans: int
    events: list[dict] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)
    degraded: bool = False
    agent_usage: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.episode_id = _text(self.episode_id, "episode_id")
        self.outcome = _enum(Outcome, self.outcome, "outcome")
        self.program_id = _optional_text(self.program_id, "program_id")
        self.program_sha256 = (
            None
            if self.program_sha256 is None
            else _sha256(self.program_sha256, "program_sha256")
        )
        self.snapshot_id = _optional_text(self.snapshot_id, "snapshot_id")
        self.initial_state_sha256 = _sha256(self.initial_state_sha256, "initial_state_sha256")
        self.final_state_sha256 = _sha256(self.final_state_sha256, "final_state_sha256")
        self.failure_code = _optional_text(self.failure_code, "failure_code")
        self.failed_op, self.failed_step = _failed_pair(self.failed_op, self.failed_step)
        self.replans = _index(self.replans, "replans")
        if not isinstance(self.events, list) or not isinstance(self.attempts, list):
            raise ContractError("events and attempts must be lists")
        if not isinstance(self.degraded, bool):
            raise ContractError("degraded must be bool")
        if not isinstance(self.agent_usage, dict):
            raise ContractError("agent_usage must be a dict")
        self.events = list(self.events)
        self.attempts = list(self.attempts)
        self.agent_usage = dict(self.agent_usage)

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "outcome": self.outcome.value,
            "program_id": self.program_id,
            "program_sha256": self.program_sha256,
            "snapshot_id": self.snapshot_id,
            "initial_state_sha256": self.initial_state_sha256,
            "final_state_sha256": self.final_state_sha256,
            "failure_code": self.failure_code,
            "failed_op": self.failed_op,
            "failed_step": self.failed_step,
            "replans": self.replans,
            "events": list(self.events),
            "attempts": list(self.attempts),
            "degraded": self.degraded,
            "agent_usage": dict(self.agent_usage),
        }


Artifact = Op | CodeModule | Skill | Procedure | ProgramArtifact | PolicyArtifact | MemoryNote | ValidationReport


@dataclass(frozen=True)
class SnapshotView:
    snapshot: Snapshot
    artifacts: dict[str, Artifact]

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, Snapshot):
            raise ContractError("snapshot view needs a Snapshot")
        if not isinstance(self.artifacts, dict):
            raise ContractError("snapshot view artifacts must be a dict")
        for artifact_id, artifact in self.artifacts.items():
            if not isinstance(artifact_id, str) or not artifact_id:
                raise ContractError("snapshot artifact id must be a non-empty string")
            if not isinstance(
                artifact,
                (Op, CodeModule, Skill, Procedure, ProgramArtifact, PolicyArtifact,
                 MemoryNote, ValidationReport),
            ):
                raise ContractError(f"unknown artifact type for {artifact_id}")
            if artifact_id not in dict(self.snapshot.refs):
                raise ContractError(f"artifact {artifact_id} is not referenced by the snapshot")
        object.__setattr__(self, "artifacts", dict(self.artifacts))


def artifact_from_dict(data: dict) -> Artifact:
    if not isinstance(data, dict):
        raise ContractError("artifact must be a dict")
    kind = data.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ContractError("artifact kind is required")
    if kind == "op":
        return Op(
            op_id=data["op_id"],
            version=data["version"],
            scope=Scope.from_dict(data["scope"]),
            status=data["status"],
            pre=tuple(Predicate.from_dict(item) for item in data["pre"]),
            post=tuple(Predicate.from_dict(item) for item in data["post"]),
            budget_s=data["budget_s"],
            failure_codes=data["failure_codes"],
            implementation=data["implementation"],
            implementation_sha256=data["implementation_sha256"],
            builtin=data["builtin"],
            arg_keys=data.get("arg_keys", ()),
            required_arg_keys=data.get("required_arg_keys", ()),
            dependencies=data.get("dependencies", ()),
            evidence=data.get("evidence", ()),
        )
    if kind == "code":
        module = CodeModule(
            id=data["id"],
            version=data["version"],
            scope=Scope.from_dict(data["scope"]),
            status=data["status"],
            source=data["source"],
            allowed_imports=data["allowed_imports"],
            tests=data.get("tests", ()),
            dependencies=data.get("dependencies", ()),
            sandbox=data.get("sandbox", "seccomp-v1"),
            evidence=data.get("evidence", ()),
        )
        recorded = data.get("source_sha256")
        if recorded is not None and recorded != module.source_sha256:
            raise ContractError("source_sha256 does not match source")
        return module
    if kind == "skill":
        return Skill(
            id=data["id"],
            version=data["version"],
            scope=Scope.from_dict(data["scope"]),
            status=data["status"],
            validation=data["validation"],
            steps=tuple(Step.from_dict(item) for item in data["steps"]),
            pre=tuple(Predicate.from_dict(item) for item in data["pre"]),
            post=tuple(Predicate.from_dict(item) for item in data["post"]),
            on_failure=data["on_failure"],
            evidence=data["evidence"],
            dependencies=data["dependencies"],
        )
    if kind == "procedure":
        return Procedure(
            id=data["id"],
            version=data["version"],
            scope=Scope.from_dict(data["scope"]),
            status=data["status"],
            validation=data["validation"],
            skill_ids=data["skill_ids"],
            steps=tuple(Step.from_dict(item) for item in data["steps"]),
            pre=tuple(Predicate.from_dict(item) for item in data["pre"]),
            post=tuple(Predicate.from_dict(item) for item in data["post"]),
            on_failure=data["on_failure"],
            evidence=data["evidence"],
        )
    if kind == "program":
        return ProgramArtifact(
            id=data["id"],
            version=data["version"],
            task_id=data["task_id"],
            scope=Scope.from_dict(data["scope"]),
            status=data["status"],
            validation=data["validation"],
            program=TaskProgram.from_dict(data["program"]),
            evidence=data["evidence"],
        )
    if kind == "policy":
        return PolicyArtifact(
            id=data["id"],
            version=data["version"],
            scope=Scope.from_dict(data["scope"]),
            status=data["status"],
            validation=data["validation"],
            checkpoint=data["checkpoint"],
            policy_type=data["policy_type"],
            observation_keys=tuple(data["observation_keys"]),
            action=data["action"],
            training=data["training"],
            evaluation=data["evaluation"],
            pre=tuple(Predicate.from_dict(item) for item in data["pre"]),
            post=tuple(Predicate.from_dict(item) for item in data["post"]),
            failure_codes=data["failure_codes"],
            evidence=data.get("evidence", ()),
            limits=data["limits"],
        )
    if kind == "memory":
        return MemoryNote(
            id=data["id"],
            text=data["text"],
            scope=Scope.from_dict(data["scope"]),
            status=data["status"],
            evidence=data["evidence"],
            supersedes=data.get("supersedes"),
        )
    if kind == "validation":
        return ValidationReport(
            id=data["id"],
            candidate_id=data["candidate_id"],
            candidate_digest=data["candidate_digest"],
            validation=data["validation"],
            protocol=data["protocol"],
            baseline_episode=data["baseline_episode"],
            treatment_episode=data["treatment_episode"],
            initial_state_sha256=data["initial_state_sha256"],
            metrics=data["metrics"],
            contract_tests=data["contract_tests"],
            regression=data["regression"],
            decision=data["decision"],
            evidence=data["evidence"],
            created_at=data["created_at"],
        )
    raise ContractError(f"unknown artifact kind: {kind}")
