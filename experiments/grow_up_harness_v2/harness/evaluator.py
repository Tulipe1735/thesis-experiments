"""Independent replay of one TP01 episode and the split feedback record.

Replay reads only saved evidence and the frozen instance. It rebuilds the scene,
reapplies the recorded hand impedance and recomputes the tabletop verdict. It
never reads the agent's done flag, the live plant or evaluator-only fields from
saved feedback.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np

from . import tp01
from .contracts import Feedback

# tp01 puts the repository root on sys.path and loads the verified plant.
from experiments.t0_agent_v1.diversity_predicates import snapshot  # noqa: E402
from experiments.t0_agent_v1.tabletop_predicates import evaluate_trace  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import (  # noqa: E402
    configure_robot,
    set_left_hand_impedance,
)


@dataclass(frozen=True)
class Verdict:
    verified_task_success: bool
    goal_satisfied: bool
    terminal_stable_s: float
    robot_evidence_valid: bool
    initial_valid: bool
    evaluator_version: str
    trajectory_sha256: str
    execution_error: dict | None
    protection: str | None


def _read(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def replay(
    case: tp01.TP01Case, episode_dir: Path, scene_path: Path | None = None
) -> Verdict:
    """Recompute the task verdict from one episode's saved evidence."""
    episode_dir = Path(episode_dir)
    if scene_path is not None:
        return _replay(case, episode_dir, Path(scene_path))
    with tempfile.TemporaryDirectory(prefix="tp01-replay-") as folder:
        return _replay(case, episode_dir, Path(folder) / "scene.xml")


def _replay(case: tp01.TP01Case, episode_dir: Path, scene_path: Path) -> Verdict:
    runtime = _read(episode_dir / "execution.json")
    initial = _read(episode_dir / "initial_pose.json")
    model = tp01.build_scene(case, scene_path)
    configure_robot(model)
    config_path = episode_dir / "left_hand_impedance.json"
    if config_path.exists():
        config = _read(config_path)
        applied = set_left_hand_impedance(model, config["kp"], config["kd"])
        if applied != config:
            raise ValueError("Recorded motor configuration differs")
    data = mujoco.MjData(model)
    rows = []
    with np.load(episode_dir / "integration_states.npz", allow_pickle=False) as trace:
        for state in trace["integration_state"]:
            mujoco.mj_setState(model, data, state, mujoco.mjtState.mjSTATE_INTEGRATION)
            mujoco.mj_forward(model, data)
            rows.append(snapshot(model, data, case.instance, base=initial["base_reference"]))
    result = evaluate_trace(
        case.instance,
        rows,
        initial_valid=case.valid_initial_fixture,
        execution_error=runtime["execution_error"],
        protection=runtime["guard"],
    )
    return Verdict(
        verified_task_success=bool(result["verified_task_success"]),
        goal_satisfied=bool(result["goal_satisfied"]),
        terminal_stable_s=float(result["terminal_simultaneous_stable_s"]),
        robot_evidence_valid=bool(result["robot_evidence_valid"]),
        initial_valid=bool(result["initial_valid"]),
        evaluator_version=result["evaluator_version"],
        trajectory_sha256=_sha256_file(episode_dir / "integration_states.npz"),
        execution_error=result["execution_error"],
        protection=result["protection"],
    )


def feedback(
    episode_id: str,
    task_id: str,
    verdict: Verdict,
    *,
    stage: str | None = None,
    failure_code: str | None = None,
    failed_op: str | None = None,
    failed_step: int | None = None,
    sim_time: float = 0.0,
) -> Feedback:
    """Split one verdict into agent-visible and evaluator-only feedback."""
    value = "success" if verdict.verified_task_success else "failure"
    agent_visible = {
        "verdict": value,
        "stage": stage,
        "failure_code": failure_code,
        "task_id": task_id,
        "sim_time": float(sim_time),
        "stable_s": round(verdict.terminal_stable_s, 1),
    }
    evaluator_only = {
        "goal_satisfied": verdict.goal_satisfied,
        "verified_task_success": verdict.verified_task_success,
        "terminal_stable_s": verdict.terminal_stable_s,
        "evaluator_version": verdict.evaluator_version,
        "trajectory_sha256": verdict.trajectory_sha256,
    }
    return Feedback(
        episode_id=episode_id,
        verdict=value,
        stage=stage,
        failure_code=failure_code,
        failed_op=failed_op,
        failed_step=failed_step,
        agent_visible=agent_visible,
        evaluator_only=evaluator_only,
    )
