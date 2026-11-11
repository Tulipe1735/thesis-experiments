"""Small op table for the TP01 chain.

open_hand and check run in the parent process. The other five are Worker
implementations. Whether a candidate may run is a router/IR decision.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import ContractError, Op, Predicate, Scope, Status, Step


def _preds(*names: str) -> tuple[Predicate, ...]:
    return tuple(Predicate(name) for name in names)


@dataclass(frozen=True)
class OpSpec:
    op_id: str
    pre: tuple[Predicate, ...]
    post: tuple[Predicate, ...]
    budget_s: float
    failure_codes: tuple[str, ...]
    arg_keys: tuple[str, ...] = ()
    required_arg_keys: tuple[str, ...] = ()
    builtin: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.op_id, str) or not self.op_id:
            raise ContractError("op spec needs an op_id")
        if isinstance(self.budget_s, bool) or not isinstance(self.budget_s, (int, float)):
            raise ContractError("budget_s must be a positive finite number")
        if not math.isfinite(self.budget_s) or self.budget_s <= 0:
            raise ContractError("budget_s must be a positive finite number")
        object.__setattr__(self, "budget_s", float(self.budget_s))
        if not isinstance(self.builtin, bool):
            raise ContractError("builtin must be bool")
        if not self.post:
            raise ContractError("op spec needs a postcondition")
        for item in (*self.pre, *self.post):
            if not isinstance(item, Predicate):
                raise ContractError("op spec predicates must be Predicate")
        pre_keys = [item.key() for item in self.pre]
        post_keys = [item.key() for item in self.post]
        if len(pre_keys) != len(set(pre_keys)) or len(post_keys) != len(set(post_keys)):
            raise ContractError("duplicate predicate in op spec")
        if not self.failure_codes or len(set(self.failure_codes)) != len(self.failure_codes):
            raise ContractError("failure_codes must be non-empty and unique")
        if any(not isinstance(code, str) or not code for code in self.failure_codes):
            raise ContractError("failure code must be a non-empty string")
        if len(set(self.arg_keys)) != len(self.arg_keys) or any(not isinstance(key, str) or not key for key in self.arg_keys):
            raise ContractError("arg_keys must be unique non-empty strings")
        if len(set(self.required_arg_keys)) != len(self.required_arg_keys):
            raise ContractError("duplicate required arg key")
        if not set(self.required_arg_keys) <= set(self.arg_keys):
            raise ContractError("required_arg_keys must be a subset of arg_keys")


LOCATE_TARGET = OpSpec(
    op_id="locate_target",
    pre=_preds("target_visible", "hand_empty", "guard_clear"),
    post=_preds("target_localized"),
    budget_s=1.0,
    failure_codes=("TARGET_NOT_FOUND", "LOW_CONFIDENCE"),
)
REACH_TARGET = OpSpec(
    op_id="reach_target",
    pre=_preds("target_localized", "hand_empty", "guard_clear"),
    post=_preds("palm_near_target"),
    budget_s=12.0,
    failure_codes=("REACH_UNREACHABLE", "JOINT_LIMIT", "TRACKING_ERROR", "COLLISION"),
    arg_keys=("offset_x", "offset_y", "offset_z"),
)
OPEN_HAND = OpSpec(
    op_id="open_hand",
    pre=_preds("guard_clear"),
    post=_preds("hand_open"),
    budget_s=2.0,
    failure_codes=("HAND_NOT_OPEN",),
    builtin=True,
)
CLOSE_HAND = OpSpec(
    op_id="close_hand",
    pre=_preds("palm_near_target", "hand_open", "guard_clear"),
    post=_preds("grasp_contact"),
    budget_s=4.0,
    failure_codes=("GRASP_MISS", "CONTACT_TOO_WEAK", "CONTACT_LOST"),
)
LIFT_TARGET = OpSpec(
    op_id="lift_target",
    pre=_preds("grasp_contact", "guard_clear"),
    post=_preds("target_lifted"),
    budget_s=10.0,
    failure_codes=("TARGET_NOT_LIFTED", "OBJECT_SLIP", "GUARD_TRIGGERED"),
)
HOLD_STABLE = OpSpec(
    op_id="hold_stable",
    pre=_preds("target_lifted", "guard_clear"),
    post=_preds("target_stable"),
    budget_s=2.0,
    failure_codes=("NOT_STABLE", "OBJECT_SLIP", "GUARD_TRIGGERED"),
)
CHECK = OpSpec(
    op_id="check",
    pre=(),
    post=_preds("target_stable"),
    budget_s=0.1,
    failure_codes=("CHECK_FAILED",),
    arg_keys=("predicate",),
    required_arg_keys=("predicate",),
    builtin=True,
)

_TABLE = (
    LOCATE_TARGET,
    REACH_TARGET,
    OPEN_HAND,
    CLOSE_HAND,
    LIFT_TARGET,
    HOLD_STABLE,
    CHECK,
)

SMALL_OPS = tuple(item for item in _TABLE if not item.builtin)
BUILTIN_OPS = tuple(item for item in _TABLE if item.builtin)
ALL_SPECS = {item.op_id: item for item in _TABLE}

# The first chain, fixed once. open_hand is inside the chain: close_hand
# requires hand_open, and nothing else produces it. check carries the
# predicate it asserts, because the builtin op has a required argument.
TP01_CHAIN = (
    Step("locate_target"),
    Step("open_hand"),
    Step("reach_target"),
    Step("close_hand"),
    Step("lift_target"),
    Step("hold_stable"),
    Step("check", (("predicate", "target_stable"),), "assert_goal"),
)

# Predicates that must already hold at the episode's first step. If the saved
# initial state cannot satisfy these, the program is not admissible and the
# runtime must REFUSE rather than execute a chain with a false precondition.
TP01_INITIAL = _preds("target_visible", "hand_empty", "guard_clear")

TP01_CHAIN_BUDGET_S = sum(ALL_SPECS[step.op_id].budget_s for step in TP01_CHAIN)


def spec(op_id: str) -> OpSpec:
    return ALL_SPECS[op_id]


def make_op(
    spec: OpSpec,
    scope: Scope,
    status: Status,
    implementation: str | None = None,
    implementation_sha256: str | None = None,
    evidence: tuple[str, ...] = (),
    version: int = 1,
) -> Op:
    """Build an Op from a spec. Callers cannot override the spec's contract."""
    if not isinstance(spec, OpSpec):
        raise ContractError("make_op expects an OpSpec")
    if spec.builtin:
        if implementation is not None or implementation_sha256 is not None:
            raise ContractError(f"builtin op {spec.op_id} cannot have an implementation")
    elif implementation is None or implementation_sha256 is None:
        raise ContractError(f"{spec.op_id} needs an implementation and implementation_sha256")
    return Op(
        op_id=spec.op_id,
        version=version,
        scope=scope,
        status=status,
        pre=spec.pre,
        post=spec.post,
        budget_s=spec.budget_s,
        failure_codes=spec.failure_codes,
        implementation=implementation,
        implementation_sha256=implementation_sha256,
        builtin=spec.builtin,
        arg_keys=spec.arg_keys,
        required_arg_keys=spec.required_arg_keys,
        evidence=evidence,
    )


def make_builtin_ops(scope: Scope) -> tuple[Op, ...]:
    # Builtins are parent-process ops, not candidates waiting on a code module.
    return tuple(make_op(item, scope, Status.VALIDATED) for item in BUILTIN_OPS)


def make_candidate_ops(
    specs,
    scope: Scope,
    implementations: dict[str, tuple[str, str]],
    evidence: tuple[str, ...] = (),
    version: int = 1,
) -> tuple[Op, ...]:
    """Bind each non-builtin spec to a CodeModule id and its source hash."""
    ops: list[Op] = []
    for item in specs:
        if not isinstance(item, OpSpec):
            raise ContractError("make_candidate_ops expects OpSpec values")
        if item.builtin:
            raise ContractError(f"builtin op cannot be a candidate: {item.op_id}")
        try:
            module_id, source_sha256 = implementations[item.op_id]
        except KeyError:
            raise ContractError(f"missing implementation for {item.op_id}") from None
        except (TypeError, ValueError):
            raise ContractError(
                f"implementation for {item.op_id} must be (code_module_id, source_sha256)"
            ) from None
        ops.append(
            make_op(
                item,
                scope,
                Status.CANDIDATE,
                implementation=module_id,
                implementation_sha256=source_sha256,
                evidence=evidence,
                version=version,
            )
        )
    return tuple(ops)
