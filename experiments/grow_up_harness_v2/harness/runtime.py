"""Program execution skeleton and the recorded-program replay.

Two entry points share one evidence format:

* ``Runtime.run`` executes a ``TaskProgram`` step by step through a caller
  supplied runner, enforcing total and per-step budgets, the closed failure-code
  set, one repair replan and the postcondition check.
* ``replay_recorded`` re-executes a recorded request list through a fresh plant,
  applies the recorded hand impedance after plant construction, and recomputes
  the verdict with the independent evaluator.

Candidate op execution in the isolated Worker arrives in V2.3. The runner
interface is the seam it will plug into.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Protocol, Sequence

from . import evaluator, predicates, tp01
from .blackboard import Blackboard, BlackboardError
from .contracts import (
    ContractError,
    Outcome,
    PlanMode,
    ProgramStep,
    Skill,
    SnapshotView,
    TaskProgram,
    TaskSpec,
)
from .ir import compile_skill, op_index, validate_program, validate_sequence
from .ops import spec as op_spec
from .router import skill_graph


@dataclass(frozen=True)
class StepOutcome:
    op_id: str
    status: str
    failure_code: str | None = None
    actions: int = 0
    sim_time: float = 0.0
    blackboard: dict = field(default_factory=dict)
    detail: dict = field(default_factory=dict)


class BudgetError(RuntimeError):
    """A request would exceed the step or program simulation budget."""


@dataclass(frozen=True)
class Budget:
    """Remaining simulation time for one step and the whole program."""

    program_s: float
    step_s: float
    step_started: float

    def step_remaining(self, now: float) -> float:
        return self.step_s - (now - self.step_started)

    def program_remaining(self, now: float) -> float:
        return self.program_s - now

    def check(self, now: float, duration: float) -> None:
        step = self.step_remaining(now)
        program = self.program_remaining(now)
        if duration > step + 1e-9:
            raise BudgetError(f"step budget needs {duration:.3f}s, has {step:.3f}s")
        if duration > program + 1e-9:
            raise BudgetError(f"program budget needs {duration:.3f}s, has {program:.3f}s")

    def dispatch(self, plant, request: dict) -> dict:
        self.check(float(plant.data.time), float(request.get("duration", 0.0)))
        return plant.dispatch(request)


class StepRunner(Protocol):
    def __call__(
        self, step: ProgramStep, *, plant, blackboard: dict, budget: Budget
    ) -> StepOutcome: ...


# Runtime-owned failure codes are not op failure codes, so the closed-set
# normalisation must leave them alone.
RUNTIME_CODES = frozenset(
    {
        "BUDGET_EXCEEDED",
        "STEP_BUDGET_EXCEEDED",
        "POSTCONDITION_NOT_MET",
        "PREDICATE_UNAVAILABLE",
        "INVALID_BLACKBOARD",
        "UNKNOWN_FAILURE_CODE",
        "INVALID_REPAIR_TARGET",
    }
)


@dataclass
class RunResult:
    episode_id: str
    outcome: Outcome
    program_id: str
    program_sha256: str
    initial_state_sha256: str
    final_state_sha256: str
    failure_code: str | None
    failed_op: str | None
    failed_step: int | None
    replans: int
    steps: list[StepOutcome]
    events: list[dict]
    evidence: Path
    verdict: evaluator.Verdict | None = None
    post_failures: list[dict] = field(default_factory=list)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def state_hash(plant) -> str:
    """Hash the exact integration state ``plant.save`` writes for the last frame."""
    if hasattr(plant, "state_bytes"):
        raw = plant.state_bytes()
    else:
        import mujoco
        import numpy as np

        state = np.empty(
            mujoco.mj_stateSize(plant.model, mujoco.mjtState.mjSTATE_INTEGRATION)
        )
        mujoco.mj_getState(
            plant.model, plant.data, state, mujoco.mjtState.mjSTATE_INTEGRATION
        )
        raw = np.ascontiguousarray(state).tobytes()
    return hashlib.sha256(raw).hexdigest()


def _perception(blackboard: Blackboard | dict) -> dict | None:
    estimate = blackboard.get("target_estimate_in_palm")
    if estimate is None:
        return None
    return {
        "target_depth_valid": True,
        "target_points": int(blackboard.get("target_points", 0)),
        "target_estimate": estimate,
        "confidence": float(blackboard.get("confidence", 0.0)),
    }


def _post_failed(step: ProgramStep, state: dict, rule) -> tuple[str | None, str | None]:
    for predicate in rule.post:
        try:
            if not predicates.evaluate(predicate.name, state):
                return "POSTCONDITION_NOT_MET", predicate.name
        except predicates.PredicateUnavailable as error:
            return "PREDICATE_UNAVAILABLE", f"{predicate.name}: {error}"
    return None, None


def builtin_runner(case: tp01.TP01Case) -> StepRunner:
    """Parent-process runner for ``open_hand`` and ``check``."""

    def run(
        step: ProgramStep, *, plant, blackboard: dict, budget: Budget
    ) -> StepOutcome:
        if step.op_id == "open_hand":
            actions = 0
            while tp01.hand_open_fraction(plant) < 0.99:
                targets = {}
                for name in tp01.HAND_JOINTS:
                    current = float(plant.targets[plant.ai[name]])
                    targets[name] = current + max(-0.05, min(0.05, -current))
                response = budget.dispatch(
                    plant, {"op": "set_joints", "targets": targets, "duration": 0.2}
                )
                actions += 1
                status = response.get("status")
                if status != "EXECUTED":
                    return StepOutcome(
                        "open_hand",
                        "failed",
                        failure_code="HAND_NOT_OPEN",
                        actions=actions,
                        sim_time=float(plant.data.time),
                        blackboard=dict(blackboard),
                        detail={"response": status, "reason": response.get("reason")},
                    )
            return StepOutcome(
                "open_hand",
                "executed",
                actions=actions,
                sim_time=float(plant.data.time),
                blackboard=dict(blackboard),
            )
        if step.op_id == "check":
            name = step.arg("predicate")
            if not isinstance(name, str):
                return StepOutcome(
                    "check", "failed", failure_code="CHECK_FAILED", blackboard=dict(blackboard)
                )
            state = tp01.step_state(plant, case, _perception(blackboard))
            ok = predicates.evaluate(name, state)
            return StepOutcome(
                "check",
                "executed" if ok else "failed",
                failure_code=None if ok else "CHECK_FAILED",
                sim_time=float(plant.data.time),
                blackboard=dict(blackboard),
                detail={"predicate": name, "result": ok},
            )
        raise ContractError(f"no builtin runner for {step.op_id}")

    return run


class Runtime:
    """Execute a validated program against one plant and write one episode."""

    def __init__(self, plant, case: tp01.TP01Case, output: Path, *, state_fn: Callable | None = None):
        self.plant = plant
        self.case = case
        self.output = Path(output)
        self.state_fn = state_fn or (lambda p, c, perception=None: tp01.step_state(p, c, perception))

    def _validate(self, program, view, task, initial, admission) -> None:
        if view is None or task is None:
            return
        validate_program(program, view, admission, task)
        validate_sequence(program, view, admission, task, initial)

    def _repair(self, program, step, code, view, task, admission) -> tuple[TaskProgram, Skill] | None:
        target_id = dict(program.on_failure).get(code)
        if target_id is None or view is None or task is None:
            return None
        skill = view.artifacts.get(target_id)
        if not isinstance(skill, Skill):
            return None
        compiled = compile_skill(skill, task, view, PlanMode.REUSE, admission=admission)
        tail = tuple(
            replace(item, index=step.index + 1 + offset)
            for offset, item in enumerate(compiled.steps)
        )
        return replace(program, steps=program.steps[: step.index + 1] + tail), skill

    def run(
        self,
        program: TaskProgram,
        runner: StepRunner,
        *,
        view: SnapshotView | None = None,
        task: TaskSpec | None = None,
        initial: tuple = (),
        verify: bool = True,
        admission: str = "formal",
        strict_posts: bool = True,
    ) -> RunResult:
        self._validate(program, view, task, initial, admission)
        self.plant.budget = min(float(self.plant.budget), float(program.budget_s))
        index = op_index(view, admission) if view is not None else {}
        steps = list(program.steps)
        outcomes: list[StepOutcome] = []
        events: list[dict] = []
        blackboard = Blackboard()
        bb_records: list[str] = []
        post_failures: list[dict] = []
        failure_code = failed_op = failed_step = None
        replans = 0
        cursor = 0
        while cursor < len(steps):
            step = steps[cursor]
            step_rule = index.get(step.op_id) or op_spec(step.op_id)
            if self.plant.data.time > program.budget_s:
                failure_code, failed_op, failed_step = "BUDGET_EXCEEDED", step.op_id, step.index
                events.append({"event": "budget_exceeded", "sim_time": self.plant.data.time})
                break
            started = float(self.plant.data.time)
            budget = Budget(float(program.budget_s), step_rule.budget_s, started)
            extra: dict = {}
            try:
                outcome = runner(
                    step, plant=self.plant, blackboard=blackboard.to_dict(), budget=budget
                )
            except BudgetError as error:
                outcome = StepOutcome(
                    step.op_id,
                    "failed",
                    failure_code="STEP_BUDGET_EXCEEDED",
                    sim_time=float(self.plant.data.time),
                    detail={"budget": str(error)},
                )
                extra["budget"] = str(error)
            elapsed = float(self.plant.data.time) - started
            code = outcome.failure_code
            predicate_name = None
            post_ok = None
            candidate = blackboard
            if outcome.status == "executed":
                if elapsed > step_rule.budget_s + 1e-6:
                    code = "STEP_BUDGET_EXCEEDED"
                else:
                    try:
                        candidate = blackboard.merge(outcome.blackboard)
                    except BlackboardError as error:
                        code = "INVALID_BLACKBOARD"
                        extra["blackboard"] = str(error)
                    else:
                        post_code, predicate_name = _post_failed(
                            step,
                            self.state_fn(self.plant, self.case, _perception(candidate)),
                            step_rule,
                        )
                        if post_code is None:
                            post_ok = True
                        else:
                            post_ok = False
                            if strict_posts:
                                code = post_code
                            else:
                                extra["post_code"] = post_code
                                extra["predicate"] = predicate_name
                                post_failures.append(
                                    {
                                        "index": step.index,
                                        "op_id": step.op_id,
                                        "code": post_code,
                                        "predicate": predicate_name,
                                    }
                                )
            elif code is not None and code not in step_rule.failure_codes and code not in RUNTIME_CODES:
                code = "UNKNOWN_FAILURE_CODE"
            if code is None:
                blackboard = candidate
                detail = dict(outcome.detail)
                detail["post_ok"] = post_ok
                detail.update(extra)
                recorded = replace(outcome, detail=detail)
                outcomes.append(recorded)
                bb_records.append(
                    blackboard.jsonl_record(step=step.index, op_id=step.op_id)
                )
                events.append(
                    {
                        "event": "step",
                        "index": step.index,
                        "op_id": step.op_id,
                        "status": "executed",
                        "failure_code": None,
                        "post_ok": post_ok,
                        "post_code": extra.get("post_code"),
                        "elapsed_s": elapsed,
                        "sim_time": float(self.plant.data.time),
                    }
                )
                cursor += 1
                continue
            if self.plant.guard and code in ("GUARD_TRIGGERED", "HAND_NOT_OPEN"):
                code = "GUARD_TRIGGERED"
            failed = StepOutcome(
                outcome.op_id,
                "failed",
                failure_code=code,
                actions=outcome.actions,
                sim_time=outcome.sim_time,
                blackboard=blackboard.to_dict(),
                detail=dict(
                    outcome.detail, guard=self.plant.guard, predicate=predicate_name, **extra
                ),
            )
            outcomes.append(failed)
            bb_records.append(blackboard.jsonl_record(step=step.index, op_id=step.op_id))
            events.append(
                {
                    "event": "step",
                    "index": step.index,
                    "op_id": step.op_id,
                    "status": "failed",
                    "failure_code": code,
                    "elapsed_s": elapsed,
                    "sim_time": float(self.plant.data.time),
                }
            )
            repair = self._repair(program, step, code, view, task, admission) if replans == 0 else None
            if repair is None:
                failure_code, failed_op, failed_step = code, step.op_id, step.index
                events.append(
                    {
                        "event": "failed",
                        "code": code,
                        "op_id": step.op_id,
                        "index": step.index,
                        "predicate": predicate_name,
                    }
                )
                break
            program, skill = repair
            steps = list(program.steps)
            replans = 1
            events.append(
                {
                    "event": "replan",
                    "failure_code": code,
                    "from_program": program.id,
                    "to_skill": skill.id,
                    "at_step": step.index,
                }
            )
            cursor = step.index + 1

        policy_calls = len(outcomes)
        runtime = self.plant.save(
            {"type": "RuntimeFailure", "message": failure_code} if failure_code else None,
            {"completed": failure_code is None},
            {"execution": "TaskProgram steps"},
            policy_calls,
        )
        verdict = evaluator.replay(self.case, self.output) if verify else None
        initial_sha = getattr(self.plant, "initial_hash", None) or _sha256_file(
            self.output / "initial_pose.json"
        )
        final_sha = state_hash(self.plant)
        succeeded = failure_code is None and (
            verdict.verified_task_success if verdict is not None else True
        )
        result = RunResult(
            episode_id=self.output.name,
            outcome=Outcome.SUCCEEDED if succeeded else Outcome.FAILED,
            program_id=program.id,
            program_sha256=program.digest(),
            initial_state_sha256=initial_sha,
            final_state_sha256=final_sha,
            failure_code=failure_code,
            failed_op=failed_op,
            failed_step=failed_step,
            replans=replans,
            steps=outcomes,
            events=events,
            evidence=self.output,
            verdict=verdict,
            post_failures=post_failures,
        )
        _write_json(self.output / "program.json", program.to_dict())
        _write_json(self.output / "task.json", self.case.task.to_dict())
        if view is not None:
            index = op_index(view, admission)
            _write_json(
                self.output / "op_table.json",
                {
                    step.op_id: index[step.op_id].to_dict()
                    for step in program.steps
                    if step.op_id in index
                },
            )
            _write_json(self.output / "snapshot.json", view.snapshot.to_dict())
            _write_json(self.output / "skill_graph.json", skill_graph(view, admission))
        _write_jsonl(self.output / "events.jsonl", events)
        (self.output / "blackboard.jsonl").write_text(
            "".join(bb_records), encoding="utf-8"
        )
        _write_json(self.output / "attempts.json", [outcome.__dict__ for outcome in outcomes])
        if verdict is not None:
            _write_verdict(self.output, verdict)
            fb = evaluator.feedback(
                self.output.name,
                self.case.task.id,
                verdict,
                stage=failed_op,
                failure_code=failure_code,
                failed_op=failed_op,
                failed_step=failed_step,
                sim_time=float(runtime["simulation_seconds"]),
            )
            _write_json(self.output / "feedback.json", fb.to_dict())
        _write_manifest(
            self.output,
            dict(
                episode_id=result.episode_id,
                task_id=self.case.task.id,
                split=self.case.task.split,
                program_id=result.program_id,
                program_sha256=result.program_sha256,
                snapshot_id=program.snapshot_id,
                initial_state_sha256=result.initial_state_sha256,
                final_state_sha256=result.final_state_sha256,
                failure_code=result.failure_code,
                replans=result.replans,
                simulation_seconds=runtime["simulation_seconds"],
                evaluator_version=(verdict.evaluator_version if verdict else None),
                counted_as_agent_success=False,
            ),
        )
        _write_hashes(self.output)
        return result


def replay_recorded(
    case: tp01.TP01Case,
    actions: Sequence[dict],
    output: Path,
    *,
    impedance: dict | None = None,
    budget_s: float = 120.0,
    source: str | None = None,
) -> RunResult:
    """Re-execute a recorded request list and verify it with the evaluator."""
    from experiments.t0_agent_v1.tabletop_training_plant import set_left_hand_impedance

    output = Path(output)
    model = tp01.build_scene(case, output / "scene.xml")
    plant = tp01.make_plant(case, model, output, budget=budget_s)
    # The plant's configure_robot() rewrites actuator gains, so impedance must be
    # applied after construction; applying it before silently changes the result.
    if impedance is not None:
        applied = set_left_hand_impedance(model, impedance["kp"], impedance["kd"])
        if applied != impedance:
            raise ValueError("recorded hand impedance differs")
        for name in applied["joints"]:
            index = plant.ai[name]
            plant.kp[index] = impedance["kp"]
            plant.kd[index] = impedance["kd"]
        _write_json(output / "left_hand_impedance.json", applied)
    error = None
    executed = 0
    for record in actions:
        request = record.get("request", record)
        response = plant.dispatch(request)
        if response.get("status") != "EXECUTED":
            error = {
                "type": "ActionRejected",
                "message": str(response.get("reason") or response.get("status")),
            }
            break
        executed += 1
    runtime = plant.save(error, {"completed": error is None}, {"execution": "recorded replay"}, executed)
    verdict = evaluator.replay(case, output)
    result = RunResult(
        episode_id=output.name,
        outcome=Outcome.SUCCEEDED if verdict.verified_task_success else Outcome.FAILED,
        program_id="replay:" + (source or "recorded"),
        program_sha256=hashlib.sha256(
            json.dumps(actions, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        initial_state_sha256=getattr(plant, "initial_hash", "") or _sha256_file(output / "initial_pose.json"),
        final_state_sha256=state_hash(plant),
        failure_code=None if error is None else error["message"],
        failed_op=None,
        failed_step=None,
        replans=0,
        steps=[],
        events=[{"event": "replay", "executed": executed, "of": len(actions)}],
        evidence=output,
        verdict=verdict,
    )
    _write_json(
        output / "replay.json",
        {
            "source": source,
            "requests": len(actions),
            "executed": executed,
            "budget_s": budget_s,
            "impedance_applied_after_plant": impedance is not None,
        },
    )
    _write_verdict(output, verdict)
    _write_jsonl(output / "events.jsonl", result.events)
    _write_manifest(
        output,
        dict(
            episode_id=result.episode_id,
            task_id=case.task.id,
            split=case.task.split,
            program_id=result.program_id,
            program_sha256=result.program_sha256,
            snapshot_id=None,
            initial_state_sha256=result.initial_state_sha256,
            final_state_sha256=result.final_state_sha256,
            failure_code=result.failure_code,
            replans=0,
            simulation_seconds=runtime["simulation_seconds"],
            evaluator_version=verdict.evaluator_version,
            counted_as_agent_success=False,
        ),
    )
    _write_hashes(output)
    return result


def _write_verdict(output: Path, verdict: evaluator.Verdict) -> None:
    _write_json(
        output / "independent_verification.json",
        {
            "goal_satisfied": verdict.goal_satisfied,
            "terminal_simultaneous_stable_s": verdict.terminal_stable_s,
            "robot_evidence_valid": verdict.robot_evidence_valid,
            "initial_valid": verdict.initial_valid,
            "verified_task_success": verdict.verified_task_success,
            "execution_error": verdict.execution_error,
            "protection": verdict.protection,
            "evaluator_version": verdict.evaluator_version,
            "trajectory_sha256": verdict.trajectory_sha256,
            "boundary": "simulation",
            "independent_replay": True,
            "formal_skill_promotion": False,
        },
    )


def _write_manifest(output: Path, fields: dict) -> None:
    _write_json(output / "manifest.json", dict(fields, boundary="simulation"))


def _write_hashes(output: Path) -> None:
    hashes = {
        path.relative_to(output).as_posix(): _sha256_file(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "hashes.json"
    }
    _write_json(output / "hashes.json", hashes)
