"""Five calibration runners built from R's recorded stage actions.

These are not Agent-authored ops. They replay the exact low-level requests R
issued during each engineering stage, so the seven-step chain can run end to
end through ``Runtime.run`` and expose predicate or budget mismatches. The
runtime still owns the budgets and the verdict; the runners only provide the
candidate-op equivalents.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from harness import tp01
from harness.contracts import (
    ContractError,
    PlanMode,
    ProgramStep,
    Scope,
    Snapshot,
    SnapshotView,
    Status,
    TaskProgram,
)
from harness.ops import TP01_CHAIN, make_op, spec
from harness.runtime import StepOutcome
from experiments.t0_agent_v1.reuse_grasp import locate_target

BUDGETS = {
    "locate_target": 2.0,
    "open_hand": 2.0,
    "reach_target": 48.0,
    "close_hand": 13.0,
    "lift_target": 13.0,
    "hold_stable": 9.0,
    "check": 0.1,
}

STAGE_GROUPS = {
    "raise_front": "reach_target",
    "raise_clear": "reach_target",
    "translate_clear": "reach_target",
    "free_space_finger_preshape": "reach_target",
    "orient_clear": "reach_target",
    "above_target": "reach_target",
    "approach_open": "reach_target",
    "finger_preclose_before_thumb": "close_hand",
    "adaptive_close": "close_hand",
    "firm_grip_after_opposing_touch": "close_hand",
    "grip_settle": "close_hand",
    "test_lift_2cm": "lift_target",
    "pressure_during_test_lift_2cm": "lift_target",
    "test_lift_hold": "lift_target",
    "main_lift": "lift_target",
    "pressure_during_main_lift": "lift_target",
    "pressure_during_hold": "hold_stable",
    "hold": "hold_stable",
}

REJECTION = {
    "locate_target": "TARGET_NOT_FOUND",
    "reach_target": "TRACKING_ERROR",
    "close_hand": "CONTACT_LOST",
    "lift_target": "TARGET_NOT_LIFTED",
    "hold_stable": "NOT_STABLE",
}


def _prefix(stage: str) -> str:
    parts = stage.split("_")
    while parts:
        try:
            float(parts[-1])
        except ValueError:
            break
        parts.pop()
    return "_".join(parts)


def _time(record: dict) -> float | None:
    observation = record.get("result", {}).get("observation") if isinstance(record.get("result"), dict) else None
    if observation is None:
        return None
    return float(observation["simulation_seconds"])


def stage_slices(source: Path) -> dict[str, list[dict]]:
    """Split the low-level requests by R's high-level stage end times."""
    source = Path(source)
    high = json.loads((source / "tools/actions.json").read_text(encoding="utf-8"))
    low = json.loads((source / "actions.json").read_text(encoding="utf-8"))
    with_time = [(record, _time(record)) for record in low]
    if any(time is None for _record, time in with_time):
        raise ValueError("low-level action without an observation time")
    initial = [record for record, time in with_time if time <= 0.6 + 1e-9]
    slices: dict[str, list[dict]] = {
        "locate_target": initial,
        "open_hand": [],
        "reach_target": [],
        "close_hand": [],
        "lift_target": [],
        "hold_stable": [],
        "check": [],
    }
    previous = max(time for _record, time in with_time if time <= 0.6 + 1e-9)
    for row in high:
        end = _time(row)
        stage = row.get("stage")
        if end is None or stage is None:
            continue
        group = STAGE_GROUPS.get(_prefix(stage))
        if group is None:
            raise KeyError(f"unmapped high-level stage: {stage}")
        slices[group].extend(record for record, time in with_time if previous < time <= end + 1e-9)
        previous = end
    return slices


def _estimate(plant, case: tp01.TP01Case) -> dict:
    target = next(item for item in case.instance["objects"] if item["is_target"])
    task = dict(target_category=case.target_category, nominal_rgba=target["asset"]["rgba"])
    result = locate_target(plant.rgbd(), task)
    return dict(
        target_estimate_in_palm=result["cup_bottom_position_m"],
        confidence=1.0,
        target_points=100,
        radius_estimate_m=result["radius_estimate_m"],
    )


def _replay(step: ProgramStep, plant, budget, records: list[dict]) -> StepOutcome:
    executed = 0
    for record in records:
        response = budget.dispatch(plant, record["request"])
        if response.get("status") != "EXECUTED":
            return StepOutcome(
                step.op_id,
                "failed",
                failure_code="GUARD_TRIGGERED" if plant.guard else REJECTION.get(step.op_id, "TRACKING_ERROR"),
                actions=executed,
                sim_time=float(plant.data.time),
                detail={"response": response.get("status"), "reason": response.get("reason")},
            )
        executed += 1
    return StepOutcome(
        step.op_id,
        "executed",
        actions=executed,
        sim_time=float(plant.data.time),
        detail={"requests": len(records)},
    )


def reference_runner(case: tp01.TP01Case, slices: dict[str, list[dict]]):
    """Return a StepRunner that replays each stage's recorded requests."""

    def run(step: ProgramStep, *, plant, blackboard: dict, budget) -> StepOutcome:
        if step.op_id not in slices:
            raise ContractError(f"no reference runner for {step.op_id}")
        outcome = _replay(step, plant, budget, slices[step.op_id])
        if step.op_id == "locate_target" and outcome.status == "executed":
            outcome = replace(outcome, blackboard=_estimate(plant, case))
        return outcome

    return run


def v2_ops(case: tp01.TP01Case, implementation_sha256: str):
    scope = Scope("TP01", case.task.assets)
    artifacts = []
    for step in TP01_CHAIN:
        base = replace(spec(step.op_id), budget_s=BUDGETS[step.op_id])
        if base.builtin:
            artifacts.append(make_op(base, scope, Status.VALIDATED, version=2))
        else:
            artifacts.append(
                make_op(
                    base,
                    scope,
                    Status.VALIDATED,
                    implementation="calibration/reference_runners.py",
                    implementation_sha256=implementation_sha256,
                    version=2,
                    evidence=(
                        "experiments/grow_up_harness_v2/runs/f0v2_engineering_20261103_001/case_01",
                    ),
                )
            )
    return tuple(artifacts)


def chain(case: tp01.TP01Case, implementation_sha256: str):
    artifacts = v2_ops(case, implementation_sha256)
    refs = tuple((artifact.op_id, artifact.digest()) for artifact in artifacts)
    snapshot = Snapshot(
        id="snap_reference_chain_v2",
        refs=refs,
        parent=None,
        label="reference chain on R stage actions",
        frozen=False,
    )
    view = SnapshotView(snapshot, {ref: artifact for (ref, _digest), artifact in zip(refs, artifacts)})
    program = TaskProgram(
        id="prog_reference_chain_v2",
        task_id=case.task.id,
        snapshot_id=snapshot.id,
        mode=PlanMode.REUSE,
        steps=tuple(
            ProgramStep(
                index=index,
                op_id=step.op_id,
                op_version=2,
                args=step.args,
                label=step.label,
            )
            for index, step in enumerate(TP01_CHAIN)
        ),
        artifact_ids=(),
        budget_s=round(sum(BUDGETS.values()), 1),
    )
    return program, view, artifacts
