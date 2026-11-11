"""Candidate-op Worker wiring and the formal-admission gate.

The runner tests use a fake plant and the real isolated Worker (except the
lifecycle test, which patches the Worker to observe the ``finally`` close).
No MuJoCo model is built here.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from harness import tp01, worker_runner
from harness.contracts import (
    ContractError,
    PlanMode,
    Predicate,
    ProgramStep,
    Scope,
    Snapshot,
    SnapshotView,
    Status,
    TaskProgram,
    TaskSpec,
)
from harness.ir import validate_program
from harness.ops import make_op, spec
from harness.runtime import Budget, StepOutcome
from harness.worker_runner import WorkerRunner

SHA = "cd" * 32
ARM_JOINT = "left_elbow_joint"
PROFILE = {"body_profile": {"robot": "g1"}}
PUBLIC_TASK = {
    "target_category": "cup",
    "nominal_rgba": [0.8, 0.8, 0.8, 1.0],
    "minimum_lift_m": 0.10,
    "stable_s": 1.0,
    "terminal_mode": "held",
}

NOOP_SOURCE = '''
def act(observation, task, state):
    name = "left_hand_index_0_joint"
    if observation["simulation_seconds"] > 0:
        return {"action": {"op": "done"}, "state": state, "blackboard": {}}
    return {
        "action": {
            "op": "set_joints",
            "targets": {name: observation["joints"][name]["q"]},
            "duration": 0.2,
        },
        "state": state,
        "blackboard": {},
    }
'''

DONE_SOURCE = '''
def act(observation, task, state):
    return {"action": {"op": "done"}, "state": state}
'''

DECLARED_FAIL_SOURCE = '''
def act(observation, task, state):
    return {"action": {"op": "fail", "reason": "TARGET_NOT_FOUND"}, "state": state}
'''

FREE_TEXT_FAIL_SOURCE = '''
def act(observation, task, state):
    return {"action": {"op": "fail", "reason": "the cup is out of reach"}, "state": state}
'''

UNSUPPORTED_SOURCE = '''
def act(observation, task, state):
    return {"action": {"op": "teleport"}, "state": state}
'''

CRASH_SOURCE = '''
def act(observation, task, state):
    raise RuntimeError("boom")
'''

VIEW_SOURCE = '''
def act(observation, task, state):
    keys = ",".join(sorted(observation))
    return {"action": {"op": "fail", "reason": keys + "|" + task["target_category"]},
            "state": state}
'''

DELTA_SOURCE = '''
def act(observation, task, state):
    return {"action": {"op": "done"}, "state": state,
            "blackboard": {"target_points": 12, "confidence": 0.5}}
'''


class FakePlant:
    """Observation payload, guard and time only; no MuJoCo."""

    def __init__(self, *, time: float = 0.0, guard: str | None = None, responses=()):
        self.data = SimpleNamespace(time=time)
        self.budget = 60.0
        self.guard = guard
        self.responses = list(responses)
        self.dispatched: list[dict] = []

    def observation(self) -> dict:
        joints = {
            name: {"q": 0.05, "dq": 0.0, "target": 0.05, "torque_Nm": 0.0}
            for name in tp01.HAND_JOINTS
        }
        joints[ARM_JOINT] = {"q": 0.0, "dq": 0.0, "target": 0.0, "torque_Nm": 0.0}
        return {
            "simulation_seconds": float(self.data.time),
            "joints": joints,
            "left_palm": {
                "frame": "current_pelvis",
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
            "tactile_joint_load_N": {name: 0.0 for name in tp01.HAND_JOINTS},
            "guard": self.guard,
        }

    def rgbd(self) -> dict:
        return {
            "rgb": [[[0, 0, 0]]],
            "depth_m": [[0.5]],
            "K": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "T_optical_to_pelvis": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            "timestamp_s": float(self.data.time),
        }

    def dispatch(self, request: dict) -> dict:
        self.dispatched.append(request)
        self.data.time += float(request.get("duration", 0.0))
        response = self.responses.pop(0) if self.responses else {"status": "EXECUTED"}
        if response.get("status") == "STOPPED" and self.guard is None:
            self.guard = response.get("reason") or "GUARD"
        return response


def step(op_id: str = "reach_target", index: int = 0) -> ProgramStep:
    return ProgramStep(index=index, op_id=op_id, op_version=1)


def budget(op_id: str = "reach_target", *, wall: float | None = None) -> Budget:
    return Budget(60.0, spec(op_id).budget_s if wall is None else wall, 0.0)


def run(
    source: str,
    plant: FakePlant | None = None,
    *,
    op_id: str = "reach_target",
    wall: float | None = None,
    blackboard: dict | None = None,
) -> tuple[StepOutcome, FakePlant]:
    plant = FakePlant() if plant is None else plant
    runner = WorkerRunner(source, PROFILE, PUBLIC_TASK)
    outcome = runner(step(op_id), plant=plant, blackboard=blackboard or {}, budget=budget(op_id, wall=wall))
    return outcome, plant


class WorkerExecutionTests(unittest.TestCase):
    def test_noop_candidate_runs_inside_the_worker(self) -> None:
        outcome, plant = run(NOOP_SOURCE)
        self.assertEqual(outcome.status, "executed")
        self.assertIsNone(outcome.failure_code)
        self.assertEqual(len(plant.dispatched), 1)
        self.assertEqual(plant.dispatched[0]["op"], "set_joints")
        self.assertIn("worker_security", outcome.detail)
        self.assertIs(outcome.detail["worker_security"].get("seccomp"), True)
        self.assertAlmostEqual(outcome.sim_time, 0.2)

    def test_done_stops_without_dispatch(self) -> None:
        outcome, plant = run(DONE_SOURCE)
        self.assertEqual(outcome.status, "executed")
        self.assertEqual(outcome.actions, 0)
        self.assertEqual(plant.dispatched, [])

    def test_declared_fail_code_is_preserved(self) -> None:
        outcome, plant = run(DECLARED_FAIL_SOURCE, op_id="locate_target")
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.failure_code, "TARGET_NOT_FOUND")
        self.assertEqual(outcome.detail["reason"], "TARGET_NOT_FOUND")
        self.assertEqual(plant.dispatched, [])

    def test_free_text_fail_reason_is_kept_but_code_is_closed_set(self) -> None:
        outcome, _plant = run(FREE_TEXT_FAIL_SOURCE, op_id="locate_target")
        self.assertEqual(outcome.failure_code, "UNKNOWN_FAILURE_CODE")
        self.assertEqual(outcome.detail["reason"], "the cup is out of reach")

    def test_unsupported_action_fails_the_step(self) -> None:
        outcome, plant = run(UNSUPPORTED_SOURCE)
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.failure_code, "UNKNOWN_FAILURE_CODE")
        self.assertIn("unsupported action", outcome.detail["error"])
        self.assertEqual(plant.dispatched, [])

    def test_guard_before_the_first_act_fails_the_step(self) -> None:
        plant = FakePlant(guard="BASE_DRIFT")
        outcome, plant = run(NOOP_SOURCE, plant)
        self.assertEqual(outcome.failure_code, "GUARD_TRIGGERED")
        self.assertEqual(outcome.detail["worker_calls"], 0)
        self.assertEqual(plant.dispatched, [])
        self.assertIn("worker_security", outcome.detail)

    def test_guard_tripped_by_a_dispatch_fails_the_step(self) -> None:
        plant = FakePlant(responses=[{"status": "STOPPED", "reason": "BASE_DRIFT"}])
        outcome, plant = run(NOOP_SOURCE, plant)
        self.assertEqual(outcome.failure_code, "GUARD_TRIGGERED")
        self.assertEqual(outcome.detail["guard"], "BASE_DRIFT")
        self.assertEqual(len(plant.dispatched), 1)

    def test_step_budget_is_checked_before_dispatch(self) -> None:
        outcome, plant = run(NOOP_SOURCE, wall=0.1)
        self.assertEqual(outcome.failure_code, "STEP_BUDGET_EXCEEDED")
        self.assertEqual(plant.dispatched, [])
        self.assertIn("budget", outcome.detail)

    def test_plant_budget_response_maps_to_budget_exceeded(self) -> None:
        plant = FakePlant(
            responses=[{"status": "BUDGET_EXHAUSTED", "reason": "SIMULATION_TIME_BUDGET"}]
        )
        outcome, _plant = run(NOOP_SOURCE, plant)
        self.assertEqual(outcome.failure_code, "BUDGET_EXCEEDED")

    def test_rejected_action_fails_the_step(self) -> None:
        plant = FakePlant(responses=[{"status": "REJECTED", "reason": "UNEXPECTED_FIELDS"}])
        outcome, _plant = run(NOOP_SOURCE, plant)
        self.assertEqual(outcome.failure_code, "UNKNOWN_FAILURE_CODE")
        self.assertEqual(outcome.detail["response"], "REJECTED")
        self.assertEqual(outcome.detail["reason"], "UNEXPECTED_FIELDS")

    def test_worker_crash_uses_a_declared_code(self) -> None:
        outcome, plant = run(CRASH_SOURCE, op_id="reach_target")
        self.assertEqual(outcome.failure_code, "TRACKING_ERROR")
        self.assertEqual(outcome.detail["error"], "WorkerError")
        self.assertEqual(plant.dispatched, [])
        self.assertIs(outcome.detail["worker_security"].get("seccomp"), True)

    def test_worker_crash_without_tracking_error_is_unknown(self) -> None:
        outcome, _plant = run(CRASH_SOURCE, op_id="locate_target")
        self.assertEqual(outcome.failure_code, "UNKNOWN_FAILURE_CODE")

    def test_worker_gets_only_the_legal_view_and_public_task(self) -> None:
        outcome, _plant = run(VIEW_SOURCE)
        self.assertEqual(
            outcome.detail["reason"],
            "blackboard,guard,joints,left_palm,rgbd,simulation_seconds,tactile_joint_load_N|cup",
        )

    def test_reach_reads_the_preceding_ops_localization(self) -> None:
        source = '''
def act(observation, task, state):
    if observation["blackboard"]["target_estimate_in_palm"] == [0.42, 0.12, 0.24]:
        return {"action": {"op": "done"}}
    return {"action": {"op": "fail", "reason": "REACH_UNREACHABLE"}}
'''
        outcome, _ = run(source, blackboard={"target_estimate_in_palm": [0.42, 0.12, 0.24]})
        self.assertEqual(outcome.status, "executed")

    def test_blackboard_delta_is_returned_not_merged(self) -> None:
        outcome, _plant = run(DELTA_SOURCE)
        self.assertEqual(outcome.status, "executed")
        self.assertEqual(outcome.blackboard, {"target_points": 12, "confidence": 0.5})


class RecordingWorker:
    """Worker double: records construction and close, always crashes."""

    instances: list["RecordingWorker"] = []

    def __init__(self, source, profile, *, wall_timeout=5.0, cpu_seconds=120):
        self.source = source
        self.profile = profile
        self.wall_timeout = wall_timeout
        self.cpu_seconds = cpu_seconds
        self.security = {"seccomp": True, "default_action": "EPERM", "imports": ["math"]}
        self.closed = False
        self.calls = 0
        RecordingWorker.instances.append(self)

    def act(self, observation, task):
        self.calls += 1
        raise worker_runner.WorkerError("boom")

    def close(self) -> None:
        self.closed = True


class WorkerLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        RecordingWorker.instances = []
        patcher = mock.patch.object(worker_runner, "Worker", RecordingWorker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_worker_per_step_is_closed_even_after_a_crash(self) -> None:
        plant = FakePlant()
        runner = WorkerRunner(CRASH_SOURCE, PROFILE, PUBLIC_TASK)
        first = runner(step(), plant=plant, blackboard={}, budget=budget())
        second = runner(step(index=1), plant=plant, blackboard={}, budget=budget())
        self.assertEqual(first.failure_code, "TRACKING_ERROR")
        self.assertEqual(second.failure_code, "TRACKING_ERROR")
        self.assertEqual(len(RecordingWorker.instances), 2)
        self.assertTrue(all(item.closed for item in RecordingWorker.instances))
        self.assertEqual(first.detail["worker_security"]["default_action"], "EPERM")


def task() -> TaskSpec:
    return TaskSpec(
        id="TP01_reach_train_000",
        template="TP01",
        instruction="lift the cup",
        assets=frozenset({"cup"}),
        goal=Predicate(
            "HeldLifted",
            (("object", "cup"), ("minimum_lift_m", 0.10), ("stable_s", 1.0)),
        ),
        budget_s=60.0,
    )


def view(status: Status) -> SnapshotView:
    scope = Scope("TP01", frozenset({"cup"}))
    artifact = make_op(spec("locate_target"), scope, status, "code", SHA)
    refs = (("locate_target", artifact.digest()),)
    snapshot = Snapshot(id="snap_worker", refs=refs, parent=None, label="test", frozen=False)
    return SnapshotView(snapshot, {"locate_target": artifact})


def program() -> TaskProgram:
    return TaskProgram(
        id="prog_worker",
        task_id="TP01_reach_train_000",
        snapshot_id="snap_worker",
        mode=PlanMode.REUSE,
        steps=(ProgramStep(index=0, op_id="locate_target", op_version=1),),
        artifact_ids=(),
        budget_s=60.0,
    )


class FormalAdmissionTests(unittest.TestCase):
    def test_candidate_ops_rejected_in_formal_before_promotion(self) -> None:
        """candidate_ops_rejected_in_formal_before_promotion."""
        with self.assertRaises(ContractError) as caught:
            validate_program(program(), view(Status.CANDIDATE), "formal", task())
        self.assertIn("op not available in formal: locate_target", str(caught.exception))
        # Practice may see the candidate; formal may not.
        validate_program(program(), view(Status.CANDIDATE), "practice", task())

    def test_validated_ops_pass_formal_admission(self) -> None:
        validate_program(program(), view(Status.VALIDATED), "formal", task())


if __name__ == "__main__":
    unittest.main()
