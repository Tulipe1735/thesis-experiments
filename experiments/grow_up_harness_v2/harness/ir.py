"""Compile and validate a TaskProgram against one snapshot.

The op table is the snapshot's Op artifacts. Admission is not PlanMode:
formal sees validated ops only, practice also sees candidates. Scope checks
go through scope_covers, not task-id prefixes.
"""

from __future__ import annotations

from dataclasses import replace

from .contracts import (
    ContractError,
    Op,
    PlanMode,
    Predicate,
    Procedure,
    ProgramArtifact,
    ProgramStep,
    Skill,
    SnapshotView,
    Status,
    TaskProgram,
    TaskSpec,
    scope_covers,
)


def _admission(mode: str) -> str:
    if mode not in ("formal", "practice"):
        raise ContractError(f"unknown admission mode: {mode!r}")
    return mode


def _plan_mode(mode: PlanMode) -> PlanMode:
    if not isinstance(mode, PlanMode):
        try:
            mode = PlanMode(mode)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"invalid plan mode: {mode!r}") from exc
    if mode is not PlanMode.REUSE and mode is not PlanMode.COMPOSE:
        raise ContractError(f"compile mode must be reuse or compose, not {mode.value}")
    return mode


def _view(view: SnapshotView) -> SnapshotView:
    if not isinstance(view, SnapshotView):
        raise ContractError("view must be a SnapshotView")
    return view


def _task(task: TaskSpec) -> TaskSpec:
    if not isinstance(task, TaskSpec):
        raise ContractError("task must be a TaskSpec")
    return task


def _optional_task(task: TaskSpec | None) -> TaskSpec | None:
    if task is None:
        return None
    return _task(task)


def _allowed(status: Status, mode: str) -> bool:
    if status is Status.VALIDATED:
        return True
    return mode == "practice" and status is Status.CANDIDATE


def op_index(view: SnapshotView, mode: str) -> dict[str, Op]:
    """Latest allowed op for each op_id.

    A same-version digest clash is checked only among ops this mode can see.
    A candidate must not make the formal index unreadable; practice still
    rejects that ambiguous pair. Rejected and retired ops are invisible.
    """
    admission = _admission(mode)
    _view(view)
    chosen: dict[str, Op] = {}
    digests: dict[tuple[str, int], str] = {}
    for artifact in view.artifacts.values():
        if not isinstance(artifact, Op) or not _allowed(artifact.status, admission):
            continue
        identity = (artifact.op_id, artifact.version)
        digest = artifact.digest()
        previous = digests.get(identity)
        if previous is not None and previous != digest:
            raise ContractError(
                f"conflicting digests for {artifact.op_id} version {artifact.version}"
            )
        digests[identity] = digest
        current = chosen.get(artifact.op_id)
        if current is None or artifact.version > current.version:
            chosen[artifact.op_id] = artifact
    return chosen


def validate_step(
    step: ProgramStep,
    view: SnapshotView,
    mode: str,
    task: TaskSpec | None = None,
) -> Op:
    if not isinstance(step, ProgramStep):
        raise ContractError("step must be a ProgramStep")
    task = _optional_task(task)
    index = op_index(view, mode)
    op = index.get(step.op_id)
    if op is None:
        raise ContractError(f"op not available in {mode}: {step.op_id}")
    if step.op_version != op.version:
        raise ContractError(
            f"op version mismatch for {step.op_id}: program has {step.op_version}, index has {op.version}"
        )
    if task is not None and not scope_covers(op.scope, task):
        raise ContractError(f"op out of scope: {step.op_id}")
    arg_names = {key for key, _ in step.args}
    unknown = sorted(arg_names - set(op.arg_keys))
    if unknown:
        raise ContractError(f"unknown arg keys for {step.op_id}: {unknown}")
    missing = sorted(set(op.required_arg_keys) - arg_names)
    if missing:
        raise ContractError(f"missing required arg keys for {step.op_id}: {missing}")
    return op


def validate_sequence(
    program: TaskProgram,
    view: SnapshotView,
    mode: str = "formal",
    task: TaskSpec | None = None,
    initial: tuple[Predicate, ...] = (),
) -> dict[str, set[str]]:
    """Check the step-to-step precondition chain.

    ``validate_program`` only checks that each referenced op exists, is in
    scope and has its arguments. It does not notice a chain that jumps from
    ``locate_target`` straight to ``close_hand``. This function does: every
    precondition must be true at the start (``initial``) or be posted by a
    step that runs earlier.

    Returns, per step index, the predicates established before that step.
    """
    if not isinstance(program, TaskProgram):
        raise ContractError("program must be a TaskProgram")
    available = {item.key() for item in initial}
    established: dict[str, set[str]] = {}
    for index, step in enumerate(program.steps):
        op = validate_step(step, view, mode, task)
        missing = [item.name for item in op.pre if item.key() not in available]
        if missing:
            raise ContractError(
                f"step {index} ({step.op_id}) preconditions not established: {sorted(missing)}"
            )
        established[str(index)] = {item.name for item in op.pre if item.key() in available}
        available.update(item.key() for item in op.post)
    return established


def validate_program(
    program: TaskProgram,
    view: SnapshotView,
    mode: str = "formal",
    task: TaskSpec | None = None,
) -> None:
    admission = _admission(mode)
    if not isinstance(program, TaskProgram):
        raise ContractError("program must be a TaskProgram")
    _view(view)
    task = _optional_task(task)
    if program.snapshot_id != view.snapshot.id:
        raise ContractError("program snapshot does not match view")
    if program.budget_s <= 0:
        raise ContractError("program budget must be positive")
    if not program.steps:
        raise ContractError("program needs at least one step")
    if task is not None and program.task_id != task.id:
        raise ContractError("program task does not match task")
    ops = [validate_step(step, view, admission, task) for step in program.steps]
    for artifact_id in program.artifact_ids:
        artifact = view.artifacts.get(artifact_id)
        if not isinstance(artifact, (Skill, Procedure)):
            raise ContractError(f"program artifact must be a skill or procedure: {artifact_id}")
        if not _allowed(artifact.status, admission):
            raise ContractError(f"artifact not allowed in {admission}: {artifact_id}")
        if task is not None and not scope_covers(artifact.scope, task):
            raise ContractError(f"artifact out of scope: {artifact_id}")
    # Codes come from the program's step ops, not from other ops in the snapshot.
    declared = {code for op in ops for code in op.failure_codes}
    for code, target_id in program.on_failure:
        if code not in declared:
            raise ContractError(f"repair code not declared by step ops: {code}")
        target = view.artifacts.get(target_id)
        # One replan replaces the tail with a single skill, not another composition.
        if not isinstance(target, Skill):
            raise ContractError(f"repair target must be a skill: {target_id}")
        if not _allowed(target.status, admission):
            raise ContractError(f"repair target not allowed in {admission}: {target_id}")
        if task is not None and not scope_covers(target.scope, task):
            raise ContractError(f"repair target out of scope: {target_id}")


def _bind_steps(
    skill: Skill,
    index: dict[str, Op],
    start: int,
    admission: str,
) -> list[ProgramStep]:
    bound: list[ProgramStep] = []
    for offset, step in enumerate(skill.steps):
        op = index.get(step.op_id)
        if op is None:
            raise ContractError(f"op not available in {admission}: {step.op_id}")
        bound.append(
            ProgramStep(
                index=start + offset,
                op_id=step.op_id,
                op_version=op.version,
                args=step.args,
                label=step.label,
                source_skill=skill.id,
            )
        )
    return bound


def _skills(skills: list[Skill] | tuple[Skill, ...]) -> tuple[Skill, ...]:
    if isinstance(skills, (str, bytes)) or not isinstance(skills, (list, tuple)):
        raise ContractError("skills must be a list or tuple")
    if not skills:
        raise ContractError("compile_chain needs at least one skill")
    for skill in skills:
        if not isinstance(skill, Skill):
            raise ContractError("compile_chain expects Skill values")
    return tuple(skills)


def compile_skill(
    skill: Skill,
    task: TaskSpec,
    view: SnapshotView,
    mode: PlanMode,
    admission: str = "formal",
    program_id: str | None = None,
    initial: tuple[Predicate, ...] | None = None,
) -> TaskProgram:
    if not isinstance(skill, Skill):
        raise ContractError("compile_skill expects a Skill")
    task = _task(task)
    view = _view(view)
    plan_mode = _plan_mode(mode)
    index = op_index(view, admission)
    program = TaskProgram(
        id=program_id or f"prog_{skill.id}_{task.id}",
        task_id=task.id,
        snapshot_id=view.snapshot.id,
        mode=plan_mode,
        steps=tuple(_bind_steps(skill, index, 0, admission)),
        artifact_ids=(skill.id,),
        on_failure=skill.on_failure,
        budget_s=task.budget_s,
    )
    validate_program(program, view, admission, task)
    if initial is not None:
        validate_sequence(program, view, admission, task, initial)
    return program


def compile_chain(
    skills: list[Skill] | tuple[Skill, ...],
    task: TaskSpec,
    view: SnapshotView,
    mode: PlanMode = PlanMode.COMPOSE,
    admission: str = "formal",
    program_id: str | None = None,
    initial: tuple[Predicate, ...] | None = None,
) -> TaskProgram:
    task = _task(task)
    view = _view(view)
    if not isinstance(mode, PlanMode):
        try:
            mode = PlanMode(mode)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"invalid plan mode: {mode!r}") from exc
    chain = _skills(skills)
    index = op_index(view, admission)
    bound: list[ProgramStep] = []
    for skill in chain:
        bound.extend(_bind_steps(skill, index, len(bound), admission))
    program = TaskProgram(
        id=program_id or "prog_" + "__".join(skill.id for skill in chain) + f"_{task.id}",
        task_id=task.id,
        snapshot_id=view.snapshot.id,
        mode=mode,
        steps=tuple(bound),
        artifact_ids=tuple(skill.id for skill in chain),
        on_failure=(),
        budget_s=task.budget_s,
    )
    validate_program(program, view, admission, task)
    if initial is not None:
        validate_sequence(program, view, admission, task, initial)
    return program


def compile_cached_program(
    artifact: ProgramArtifact,
    task: TaskSpec,
    view: SnapshotView,
    admission: str = "formal",
) -> TaskProgram:
    if not isinstance(artifact, ProgramArtifact):
        raise ContractError("compile_cached_program expects a ProgramArtifact")
    task = _task(task)
    view = _view(view)
    program = replace(
        artifact.program,
        id=f"prog_{artifact.id}_{task.id}",
        task_id=task.id,
        snapshot_id=view.snapshot.id,
    )
    validate_program(program, view, admission, task)
    return program


def compile_repair(
    skill: Skill,
    task: TaskSpec,
    view: SnapshotView,
    admission: str = "formal",
) -> TaskProgram:
    return compile_skill(skill, task, view, PlanMode.REUSE, admission=admission)
