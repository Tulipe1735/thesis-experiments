"""Failure diagnosis and candidate extraction.

Experience building can only write candidates. It reads a finished episode's
agent-visible feedback and blackboard, never the evaluator-only fields, and it
cannot promote anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .agent import check_source
from .contracts import (
    ALLOWED_IMPORTS,
    CodeModule,
    MemoryNote,
    Op,
    Predicate,
    Scope,
    Skill,
    Status,
    TaskSpec,
)
from .ops import SMALL_OPS, TP01_CHAIN, TP01_INITIAL, make_candidate_ops, spec


@dataclass(frozen=True)
class FailureDiagnosis:
    episode: str
    task_id: str
    failed_op: str | None
    failed_step: int | None
    failure_code: str | None
    agent_visible: dict
    blackboard: dict
    mechanism: str
    repair_boundary: str
    legal_only: bool

    def to_dict(self) -> dict:
        return {
            "episode": self.episode,
            "task_id": self.task_id,
            "failed_op": self.failed_op,
            "failed_step": self.failed_step,
            "failure_code": self.failure_code,
            "agent_visible": dict(self.agent_visible),
            "blackboard": dict(self.blackboard),
            "mechanism": self.mechanism,
            "repair_boundary": self.repair_boundary,
            "legal_only": self.legal_only,
        }


def _read(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _last_jsonl(path: Path) -> dict:
    if not path.is_file():
        return {}
    rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(rows[-1]) if rows else {}


def diagnose(
    episode_dir: Path,
    task: TaskSpec,
    *,
    mechanism: str = "not_diagnosed",
    repair_boundary: str = "not_bounded",
) -> FailureDiagnosis:
    """Read only agent-visible feedback and the blackboard."""
    episode_dir = Path(episode_dir)
    feedback = _read(episode_dir / "feedback.json") if (episode_dir / "feedback.json").is_file() else {}
    agent_visible = dict(feedback.get("agent_visible", {}))
    attempts = _read(episode_dir / "attempts.json") if (episode_dir / "attempts.json").is_file() else []
    failed = next(
        (item for item in reversed(attempts) if item.get("status") == "failed"),
        {},
    )
    blackboard = _last_jsonl(episode_dir / "blackboard.jsonl")
    return FailureDiagnosis(
        episode=str(episode_dir),
        task_id=task.id,
        failed_op=failed.get("op_id") or feedback.get("failed_op"),
        failed_step=failed.get("index", feedback.get("failed_step")),
        failure_code=failed.get("failure_code") or feedback.get("failure_code"),
        agent_visible=agent_visible,
        blackboard=dict(blackboard.get("blackboard", blackboard)),
        mechanism=mechanism,
        repair_boundary=repair_boundary,
        legal_only=not any(key in agent_visible for key in ("target_pose", "object_pose", "thresholds", "raw_frames")),
    )


def candidate_memory(diagnosis: FailureDiagnosis, scope: Scope) -> MemoryNote:
    text = (
        f"Failure {diagnosis.failure_code} at {diagnosis.failed_op} step {diagnosis.failed_step}. "
        f"Mechanism: {diagnosis.mechanism}. Repair boundary: {diagnosis.repair_boundary}."
    )
    return MemoryNote(
        id=f"mem_{diagnosis.task_id}_candidate",
        text=text,
        scope=scope,
        status=Status.CANDIDATE,
        evidence=(diagnosis.episode,),
    )


def candidate_code(payload: dict, scope: Scope, *, version: int = 1) -> tuple[CodeModule, ...]:
    """Turn validated author_ops sources into candidate CodeModules."""
    modules = []
    for op_id in (item.op_id for item in SMALL_OPS):
        source = payload["ops"][op_id]
        check_source(source)
        modules.append(
            CodeModule(
                id=f"code_{op_id}_v{version}",
                version=version,
                scope=scope,
                status=Status.CANDIDATE,
                source=source,
                allowed_imports=tuple(sorted(ALLOWED_IMPORTS)),
                tests=(),
                dependencies=("python:3.12", "numpy:2.5.4", "worker:seccomp-v1"),
                evidence=(),
            )
        )
    return tuple(modules)


def candidate_ops(modules: tuple[CodeModule, ...], scope: Scope, *sources, version: int = 1) -> tuple[Op, ...]:
    by_id = {module.id.removeprefix("code_").rsplit("_v", 1)[0]: module for module in modules}
    implementations = {
        op_id: (module.id, module.source_sha256)
        for op_id, module in by_id.items()
    }
    evidence = tuple(str(item) for item in sources)
    return make_candidate_ops(
        [spec(item.op_id) for item in SMALL_OPS],
        scope,
        implementations,
        evidence=evidence,
        version=version,
    )


def candidate_skill(
    scope: Scope,
    task: TaskSpec,
    evidence: tuple[str, ...] = (),
    *,
    version: int = 1,
) -> Skill:
    return Skill(
        id=f"skill_tp01_chain_candidate_v{version}",
        version=version,
        scope=scope,
        status=Status.CANDIDATE,
        validation=None,
        steps=TP01_CHAIN,
        pre=TP01_INITIAL,
        post=(Predicate("target_stable"),),
        evidence=evidence,
        dependencies=("python:3.12", "numpy:2.5.4", "worker:seccomp-v1", "evaluator:tabletop-predicates-v1"),
    )
