"""FAST and REFUSE routing over the registry projection.

The router never guesses from task-id substrings. A task is covered when an
admissible artifact's scope covers it and the program validates. The skill graph
is derived from postconditions and preconditions, not from names.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from . import ops, predicates
from .contracts import (
    ContractError,
    PlanMode,
    Predicate,
    ProgramArtifact,
    ProgramStep,
    Skill,
    SnapshotView,
    Status,
    TaskProgram,
    TaskSpec,
    scope_covers,
)
from .ir import (
    compile_cached_program,
    compile_skill,
    op_index,
    validate_program,
    validate_sequence,
)

FORMAL = "formal"
PRACTICE = "practice"
ADMISSIONS = (FORMAL, PRACTICE)


class Route(str, Enum):
    FAST = "fast"
    SLOW = "slow"
    REFUSE = "refuse"


@dataclass(frozen=True)
class Decision:
    route: Route
    reason: str
    program: TaskProgram | None = None
    mode: PlanMode | None = None
    artifact_id: str | None = None
    authoring_request: str | None = None


def _admissible(status: Status, admission: str) -> bool:
    if admission not in ADMISSIONS:
        raise ContractError(f"unknown admission: {admission}")
    if status is Status.VALIDATED:
        return True
    return admission == PRACTICE and status is Status.CANDIDATE


def _allowed(artifact, admission: str) -> bool:
    return _admissible(artifact.status, admission)


def skill_graph(view: SnapshotView, admission: str = FORMAL) -> dict[str, tuple[str, ...]]:
    """Edges ``a -> b`` when ``a.post`` establishes every ``b.pre`` predicate."""
    skills = [
        artifact
        for artifact in view.artifacts.values()
        if isinstance(artifact, Skill) and _allowed(artifact, admission)
    ]
    graph: dict[str, list[str]] = {skill.id: [] for skill in skills}
    for first in skills:
        posted = {item.key() for item in first.post}
        for second in skills:
            if first.id == second.id:
                continue
            if all(item.key() in posted for item in second.pre):
                graph[first.id].append(second.id)
    return {key: tuple(sorted(value)) for key, value in graph.items()}


def _initial_ok(initial: tuple[Predicate, ...], state) -> tuple[bool, tuple[str, ...]]:
    if state is None:
        return False, ("predicate_state_required",)
    _ok, _results, missing = predicates.check_all([item.name for item in initial], state)
    failed = tuple(
        item.name for item in initial if item.name not in missing and not predicates.evaluate(item.name, state)
    )
    return not missing and not failed, tuple(sorted(set(missing) | set(failed)))


def _chain_program(task: TaskSpec, view: SnapshotView, admission: str) -> TaskProgram:
    """Build the registered TP01 op chain as a TaskProgram."""
    index = op_index(view, admission)
    steps = tuple(
        ProgramStep(
            index=position,
            op_id=step.op_id,
            op_version=index[step.op_id].version,
            args=step.args,
            label=step.label,
        )
        for position, step in enumerate(ops.TP01_CHAIN)
    )
    program = TaskProgram(
        id=f"prog_tp01_chain_{task.id}",
        task_id=task.id,
        snapshot_id=view.snapshot.id,
        mode=PlanMode.REUSE,
        steps=steps,
        artifact_ids=(),
        budget_s=ops.TP01_CHAIN_BUDGET_S,
    )
    validate_program(program, view, admission, task)
    validate_sequence(program, view, admission, task, ops.TP01_INITIAL)
    return program


def _artifact_candidates(task: TaskSpec, view: SnapshotView, admission: str):
    for artifact in view.artifacts.values():
        if not isinstance(artifact, (ProgramArtifact, Skill)):
            continue
        if isinstance(artifact, ProgramArtifact) and artifact.task_id != task.id:
            continue
        if not _allowed(artifact, admission) or not scope_covers(artifact.scope, task):
            continue
        yield artifact


def decide(
    task: TaskSpec,
    view: SnapshotView,
    *,
    admission: str = FORMAL,
    predicate_state: dict | None = None,
    initial: tuple[Predicate, ...] = ops.TP01_INITIAL,
) -> Decision:
    """Return FAST with an executable program, SLOW in practice, or REFUSE."""
    if task.template != "TP01":
        return Decision(Route.REFUSE, f"unknown task template: {task.template}", mode=PlanMode.REFUSE)
    ok, names = _initial_ok(initial, predicate_state)
    if not ok:
        return Decision(
            Route.REFUSE,
            "initial predicates not established: " + ",".join(names),
            mode=PlanMode.REFUSE,
        )

    for artifact in _artifact_candidates(task, view, admission):
        try:
            if isinstance(artifact, ProgramArtifact):
                program = compile_cached_program(artifact, task, view, admission)
            else:
                program = compile_skill(artifact, task, view, PlanMode.REUSE, admission=admission)
                validate_sequence(program, view, admission, task, initial)
        except ContractError:
            continue
        return Decision(
            Route.FAST,
            f"{artifact.kind} {artifact.id} covers {task.id}",
            program=program,
            mode=PlanMode.REUSE,
            artifact_id=artifact.id,
        )

    try:
        program = _chain_program(task, view, admission)
    except (ContractError, KeyError) as error:
        if admission == PRACTICE:
            return Decision(
                Route.SLOW,
                f"no executable chain in practice: {error}",
                mode=PlanMode.SYNTHESIZE,
                authoring_request=f"author:{task.id}",
            )
        return Decision(Route.REFUSE, f"no validated program covers {task.id}: {error}", mode=PlanMode.REFUSE)
    return Decision(
        Route.FAST,
        f"registered TP01 op chain covers {task.id}",
        program=program,
        mode=PlanMode.REUSE,
        artifact_id="TP01_CHAIN",
    )
