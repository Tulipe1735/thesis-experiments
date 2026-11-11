"""Run one candidate op step inside the isolated Worker.

V2.3 wiring. A step's candidate source runs in the frozen 2026-10-26 seccomp
Worker: one Worker per step, started before the first ``act`` call and closed
in a ``finally`` block. ``worker.security`` is copied into
``StepOutcome.detail["worker_security"]`` so the episode evidence shows which
sandbox the candidate actually ran in.

The Worker receives only ``tp01.observation(plant).agent_view()`` and the
public task dict. The plant, model, evaluator, file system, blackboard and
object truth stay in the parent; ``blackboard`` is accepted for the
:class:`harness.runtime.StepRunner` seam and is never forwarded. Every action
is authorised by ``Budget.dispatch`` before it reaches the plant, so a
candidate cannot spend more simulation time than the step or program budget
allows.

``StepOutcome.blackboard`` is the Worker's optional ``blackboard`` delta, not
a verdict: ``Runtime`` merges it through
:class:`harness.blackboard.Blackboard`, and an illegal delta fails the step
with ``INVALID_BLACKBOARD`` there.
"""

from __future__ import annotations

import json
import math
from typing import Any

from . import tp01
from .contracts import ContractError, ProgramStep
from .ops import OpSpec, spec as op_spec
from .runtime import Budget, BudgetError, StepOutcome

# ``harness.tp01`` puts the repository root on ``sys.path`` and loads the
# hash-verified runtime, so this import resolves to the registered Worker and
# its verified ``_entry.py`` rather than a second copy.
from experiments.grow_up_v2.isolation.worker import Worker, WorkerError  # noqa: E402

UNKNOWN_FAILURE_CODE = "UNKNOWN_FAILURE_CODE"
PREFERRED_WORKER_CODE = "TRACKING_ERROR"
ALLOWED_ACTIONS = ("wait", "set_joints")


def _positive(name: str, value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return float(value)


def _worker_code(codes: tuple[str, ...]) -> str:
    """Map a Worker crash to the op's declared closed set.

    ``TRACKING_ERROR`` is the honest code when the op declares it: the worker
    died while the plant was still being driven. Otherwise the runtime
    normalises the code to ``UNKNOWN_FAILURE_CODE``.
    """
    return PREFERRED_WORKER_CODE if PREFERRED_WORKER_CODE in codes else UNKNOWN_FAILURE_CODE


def _op_rule(step: ProgramStep) -> OpSpec:
    try:
        return op_spec(step.op_id)
    except KeyError:
        raise ContractError(f"no candidate op spec for {step.op_id}") from None


def _delta(result: dict) -> dict:
    """The Worker's optional blackboard delta; the runtime validates it."""
    value = result.get("blackboard", {})
    if value is None:
        return {}
    return value


class WorkerRunner:
    """StepRunner for one candidate op; one isolated Worker per call.

    ``profile`` is the frozen body packet the Worker hands to ``init``;
    ``task`` is the public task dict (category, thresholds, terminal mode),
    never evaluator truth. ``wall_timeout`` bounds one ``act`` call and
    ``cpu_seconds`` the whole process, matching the 2026-10-26 runs.
    """

    def __init__(
        self,
        source: str,
        profile: dict,
        task: dict,
        *,
        wall_timeout: float = 5.0,
        cpu_seconds: float = 120.0,
    ):
        if not isinstance(source, str) or not source:
            raise ValueError("source must be non-empty text")
        if not isinstance(profile, dict):
            raise TypeError("profile must be a dictionary")
        if not isinstance(task, dict):
            raise TypeError("task must be a dictionary")
        for name, value in (("profile", profile), ("task", task)):
            try:
                json.dumps(value, allow_nan=False)
            except (TypeError, ValueError) as error:
                raise ValueError(f"{name} must be JSON-serialisable: {error}") from None
        self.source = source
        self.profile = profile
        self.task = dict(task)
        self.wall_timeout = _positive("wall_timeout", wall_timeout)
        self.cpu_seconds = int(_positive("cpu_seconds", cpu_seconds, minimum=1))

    def __call__(
        self, step: ProgramStep, *, plant, blackboard: dict, budget: Budget
    ) -> StepOutcome:
        """Drive one Worker until done, fail, guard, or budget error.

        The step ends on the candidate's ``done`` (executed), its ``fail``
        (failed with the reason), a tripped plant guard (``GUARD_TRIGGERED``),
        a spent step or program budget (``STEP_BUDGET_EXCEEDED``), or a Worker
        error or timeout (``TRACKING_ERROR`` when the op declares it, else
        ``UNKNOWN_FAILURE_CODE``). The runtime owns the closed-set mapping for
        the returned code.
        """
        rule = _op_rule(step)
        counts: dict[str, int] = {}
        calls = 0
        security: dict[str, Any] = {}
        worker = None
        try:
            worker = Worker(
                self.source,
                self.profile,
                wall_timeout=self.wall_timeout,
                cpu_seconds=self.cpu_seconds,
            )
            security = dict(worker.security)
            while True:
                if plant.guard:
                    return self._failed(
                        step,
                        "GUARD_TRIGGERED",
                        plant,
                        counts,
                        security,
                        calls,
                        guard=plant.guard,
                    )
                observation = tp01.observation(plant).agent_view()
                observation["blackboard"] = blackboard
                result = worker.act(observation, self.task)
                calls += 1
                action = result["action"]
                operation = action.get("op")
                if operation == "done":
                    return self._executed(step, plant, counts, security, calls, result)
                if operation == "fail":
                    reason = str(action.get("reason") or "unspecified")[:400]
                    return self._failed(
                        step,
                        reason if reason in rule.failure_codes else UNKNOWN_FAILURE_CODE,
                        plant,
                        counts,
                        security,
                        calls,
                        reason=reason,
                    )
                if operation not in ALLOWED_ACTIONS:
                    return self._failed(
                        step,
                        UNKNOWN_FAILURE_CODE,
                        plant,
                        counts,
                        security,
                        calls,
                        error=f"unsupported action: {operation!r}",
                    )
                try:
                    response = budget.dispatch(plant, action)
                except (TypeError, ValueError) as error:
                    # A malformed duration fails the step, not the harness.
                    return self._failed(
                        step,
                        UNKNOWN_FAILURE_CODE,
                        plant,
                        counts,
                        security,
                        calls,
                        error=type(error).__name__,
                        message=str(error)[:400],
                    )
                counts[operation] = counts.get(operation, 0) + 1
                status = response.get("status")
                if status == "STOPPED" or plant.guard:
                    return self._failed(
                        step,
                        "GUARD_TRIGGERED",
                        plant,
                        counts,
                        security,
                        calls,
                        guard=plant.guard or response.get("reason"),
                    )
                if status == "BUDGET_EXHAUSTED":
                    return self._failed(
                        step,
                        "BUDGET_EXCEEDED",
                        plant,
                        counts,
                        security,
                        calls,
                        reason=response.get("reason"),
                    )
                if status != "EXECUTED":
                    return self._failed(
                        step,
                        UNKNOWN_FAILURE_CODE,
                        plant,
                        counts,
                        security,
                        calls,
                        response=status,
                        reason=response.get("reason"),
                    )
        except BudgetError as error:
            return self._failed(
                step,
                "STEP_BUDGET_EXCEEDED",
                plant,
                counts,
                security,
                calls,
                budget=str(error),
            )
        except WorkerError as error:
            return self._failed(
                step,
                _worker_code(rule.failure_codes),
                plant,
                counts,
                security,
                calls,
                error=type(error).__name__,
                message=str(error)[:400],
            )
        finally:
            if worker is not None:
                worker.close()

    @staticmethod
    def _detail(security: dict, calls: int, counts: dict, **extra: Any) -> dict:
        detail = {
            "worker_security": security,
            "worker_calls": calls,
            "dispatches": dict(counts),
        }
        detail.update(extra)
        return detail

    def _executed(
        self, step: ProgramStep, plant, counts: dict, security: dict, calls: int, result: dict
    ) -> StepOutcome:
        return StepOutcome(
            step.op_id,
            "executed",
            actions=sum(counts.values()),
            sim_time=float(plant.data.time),
            blackboard=_delta(result),
            detail=self._detail(security, calls, counts),
        )

    def _failed(
        self,
        step: ProgramStep,
        code: str,
        plant,
        counts: dict,
        security: dict,
        calls: int,
        **extra: Any,
    ) -> StepOutcome:
        return StepOutcome(
            step.op_id,
            "failed",
            failure_code=code,
            actions=sum(counts.values()),
            sim_time=float(plant.data.time),
            detail=self._detail(security, calls, counts, **extra),
        )
