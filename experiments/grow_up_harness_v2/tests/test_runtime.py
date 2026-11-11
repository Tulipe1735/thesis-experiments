"""Program execution skeleton: budgets, failure codes, posts and one replan."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from harness import tp01
from harness.contracts import (
    PlanMode,
    Predicate,
    ProgramStep,
    Scope,
    Skill,
    Snapshot,
    SnapshotView,
    Status,
    Step,
    TaskProgram,
    TaskSpec,
)
from harness.ops import TP01_INITIAL, make_op, spec
from harness.runtime import Budget, Runtime, StepOutcome, builtin_runner

SHA = "cd" * 32


def task() -> TaskSpec:
    return TaskSpec(
        id="TP01_reach_train_000",
        template="TP01",
        instruction="lift the cup",
        assets=frozenset({"cup"}),
        goal=Predicate("HeldLifted", (("object", "cup"), ("minimum_lift_m", 0.10), ("stable_s", 1.0))),
        budget_s=60.0,
    )


def view(with_repair: bool = False) -> SnapshotView:
    scope = Scope("TP01", frozenset({"cup"}))
    artifacts = [
        make_op(spec("open_hand"), scope, Status.VALIDATED),
        make_op(spec("locate_target"), scope, Status.VALIDATED, "code_locate", SHA),
    ]
    if with_repair:
        artifacts.append(
            Skill(
                id="regrasp",
                version=1,
                scope=scope,
                status=Status.CANDIDATE,
                validation=None,
                steps=(Step("open_hand"),),
                pre=(Predicate("guard_clear"),),
                post=(Predicate("hand_open"),),
            )
        )
    refs = tuple(
        (getattr(artifact, "op_id", getattr(artifact, "id", "")), artifact.digest())
        for artifact in artifacts
    )
    snapshot = Snapshot(id="snap_runtime", refs=refs, parent=None, label="test", frozen=False)
    return SnapshotView(snapshot, {ref: artifact for (ref, _digest), artifact in zip(refs, artifacts)})


def program(*op_ids: str, on_failure=(), view_id: str = "snap_runtime") -> TaskProgram:
    return TaskProgram(
        id="prog_runtime",
        task_id="TP01_reach_train_000",
        snapshot_id=view_id,
        mode=PlanMode.REUSE,
        steps=tuple(
            ProgramStep(index=index, op_id=op_id, op_version=1)
            for index, op_id in enumerate(op_ids)
        ),
        artifact_ids=(),
        on_failure=on_failure,
        budget_s=60.0,
    )


class FakePlant:
    def __init__(self, output: Path, time: float = 0.0, budget: float = 60.0):
        self.output = Path(output)
        self.data = SimpleNamespace(time=time)
        self.budget = budget
        self.guard = None
        self.initial_hash = "ab" * 32
        self.full_states = [(0.0, np.zeros(8))]
        self.dispatched = []
        self.saved = None

    def state_array(self) -> np.ndarray:
        state = np.zeros(8)
        state[0] = self.data.time
        state[1] = 1.0
        return state

    def state_bytes(self) -> bytes:
        return np.ascontiguousarray(self.state_array()).tobytes()

    def dispatch(self, request: dict) -> dict:
        self.dispatched.append(request)
        self.data.time += float(request.get("duration", 0.0))
        self.full_states.append((self.data.time, self.state_array()))
        return {"status": "EXECUTED"}

    def save(self, error, policy_state, worker_security, policy_calls):
        (self.output / "execution.json").write_text(
            json.dumps({"simulation_seconds": self.data.time, "guard": self.guard})
        )
        (self.output / "actions.json").write_text("[]")
        np.savez_compressed(
            self.output / "integration_states.npz",
            time=np.array([self.data.time]),
            integration_state=np.array([self.state_array()]),
        )
        self.saved = dict(error=error, policy_calls=policy_calls)
        return {"simulation_seconds": self.data.time, "guard": self.guard}


class OpenHandPlant:
    def __init__(self):
        self.data = SimpleNamespace(time=0.0)
        self.targets = np.zeros(len(tp01.HAND_JOINTS))
        self.ai = {name: index for index, name in enumerate(tp01.HAND_JOINTS)}
        self.budget = 60.0
        self.guard = None
        self.requests = []

    def observation(self) -> dict:
        return {"joints": {name: {"q": 0.0} for name in tp01.HAND_JOINTS}}

    def dispatch(self, request):
        self.requests.append(request)
        self.data.time += request["duration"]
        return {"status": "EXECUTED"}


def ok_state(plant, case, perception=None):
    return {
        "hand": {"open_fraction": 1.0},
        "perception": {"target_estimate": [0.4, 0.3, 0.96], "confidence": 0.9},
    }


def closed_state(plant, case, perception=None):
    return {"hand": {"open_fraction": 0.1}}


def ok_runner(step, *, plant, blackboard, budget):
    plant.data.time += 0.1
    plant.full_states.append((plant.data.time, np.zeros(8)))
    return StepOutcome(step.op_id, "executed", actions=1, sim_time=plant.data.time)


def failing_runner(step, *, plant, blackboard, budget):
    return StepOutcome(step.op_id, "failed", failure_code="TARGET_NOT_FOUND")


def unknown_runner(step, *, plant, blackboard, budget):
    return StepOutcome(step.op_id, "failed", failure_code="BOGUS")


def slow_runner(step, *, plant, blackboard, budget):
    plant.data.time += 2.0
    plant.full_states.append((plant.data.time, np.zeros(8)))
    return StepOutcome(step.op_id, "executed", actions=1, sim_time=plant.data.time)


def fail_once(step, *, plant, blackboard, budget):
    if step.op_id == "locate_target" and not getattr(plant, "failed_once", False):
        plant.failed_once = True
        return StepOutcome(step.op_id, "failed", failure_code="TARGET_NOT_FOUND")
    return ok_runner(step, plant=plant, blackboard=blackboard, budget=budget)


def bad_key_runner(step, *, plant, blackboard, budget):
    return StepOutcome(step.op_id, "executed", blackboard={"Bad-Key": 1})


def too_many_runner(step, *, plant, blackboard, budget):
    return StepOutcome(step.op_id, "executed", blackboard={f"k{index}": 1 for index in range(33)})


def dispatch_runner(step, *, plant, blackboard, budget):
    budget.dispatch(plant, {"op": "wait", "duration": 2.0})
    return StepOutcome(step.op_id, "executed")


def locate_runner(step, *, plant, blackboard, budget):
    return StepOutcome(
        "locate_target",
        "executed",
        blackboard={
            "target_estimate_in_palm": [0.4, 0.3, 0.96],
            "confidence": 0.9,
        },
    )


def perception_state(plant, case, perception=None):
    state = {"hand": {"open_fraction": 1.0}}
    if perception is not None:
        state["perception"] = perception
    return state


class BuiltinRunnerTests(unittest.TestCase):
    def test_open_hand_is_a_noop_when_already_open(self) -> None:
        plant = OpenHandPlant()
        outcome = builtin_runner(SimpleNamespace(task=task()))(
            ProgramStep(index=0, op_id="open_hand", op_version=1),
            plant=plant,
            blackboard={},
            budget=Budget(60.0, 2.0, 0.0),
        )
        self.assertEqual(outcome.status, "executed")
        self.assertEqual(outcome.actions, 0)
        self.assertEqual(plant.requests, [])


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="runtime-")
        self.output = Path(self.temp.name) / "episode"
        self.output.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_case(self, program, runner, *, state_fn=ok_state, **kwargs):
        plant = FakePlant(self.output)
        return Runtime(plant, SimpleNamespace(task=task()), self.output, state_fn=state_fn).run(
            program, runner, verify=False, **kwargs
        )

    def test_success_writes_evidence_and_hashes(self) -> None:
        result = self.run_case(program("open_hand"), ok_runner)
        self.assertEqual(result.outcome.value, "succeeded")
        self.assertEqual(len(result.steps), 1)
        for name in ("program.json", "task.json", "events.jsonl", "blackboard.jsonl", "attempts.json", "manifest.json", "hashes.json"):
            self.assertTrue((self.output / name).is_file(), name)
        hashes = json.loads((self.output / "hashes.json").read_text())
        self.assertIn("program.json", hashes)
        self.assertNotIn("hashes.json", hashes)

    def test_final_state_hash_matches_saved_last_frame(self) -> None:
        result = self.run_case(program("open_hand"), ok_runner)
        with np.load(self.output / "integration_states.npz") as trace:
            last = trace["integration_state"][-1]
        expected = hashlib.sha256(np.ascontiguousarray(last).tobytes()).hexdigest()
        self.assertEqual(result.final_state_sha256, expected)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["final_state_sha256"], expected)

    def test_declared_failure_code_stops_the_program(self) -> None:
        result = self.run_case(program("locate_target", "open_hand"), failing_runner)
        self.assertEqual(result.outcome.value, "failed")
        self.assertEqual(result.failure_code, "TARGET_NOT_FOUND")
        self.assertEqual(result.failed_op, "locate_target")
        self.assertEqual(len(result.steps), 1)

    def test_unknown_failure_code_is_normalised(self) -> None:
        result = self.run_case(program("locate_target"), unknown_runner)
        self.assertEqual(result.failure_code, "UNKNOWN_FAILURE_CODE")

    def test_step_budget_is_enforced(self) -> None:
        result = self.run_case(program("locate_target"), slow_runner)
        self.assertEqual(result.failure_code, "STEP_BUDGET_EXCEEDED")

    def test_total_budget_is_enforced(self) -> None:
        plant = FakePlant(self.output, time=61.0)
        result = Runtime(plant, SimpleNamespace(task=task()), self.output, state_fn=ok_state).run(
            program("open_hand"), ok_runner, verify=False
        )
        self.assertEqual(result.failure_code, "BUDGET_EXCEEDED")

    def test_budget_is_checked_before_dispatch(self) -> None:
        plant = FakePlant(self.output)
        result = Runtime(plant, SimpleNamespace(task=task()), self.output, state_fn=ok_state).run(
            program("locate_target"), dispatch_runner, verify=False
        )
        self.assertEqual(result.failure_code, "STEP_BUDGET_EXCEEDED")
        self.assertEqual(plant.dispatched, [])

    def test_postcondition_is_checked_not_trusted(self) -> None:
        result = self.run_case(program("open_hand"), ok_runner, state_fn=closed_state)
        self.assertEqual(result.failure_code, "POSTCONDITION_NOT_MET")
        self.assertEqual(result.events[-1]["predicate"], "hand_open")

    def test_post_sees_the_step_blackboard(self) -> None:
        result = self.run_case(
            program("locate_target"),
            locate_runner,
            view=view(),
            task=task(),
            initial=TP01_INITIAL,
            state_fn=perception_state,
        )
        self.assertIsNone(result.failure_code)
        self.assertTrue(result.steps[0].detail["post_ok"])
        self.assertEqual(result.post_failures, [])

    def test_non_strict_posts_are_recorded_and_execution_continues(self) -> None:
        result = self.run_case(
            program("open_hand"), ok_runner, state_fn=closed_state, strict_posts=False
        )
        self.assertIsNone(result.failure_code)
        self.assertFalse(result.steps[0].detail["post_ok"])
        self.assertEqual(result.post_failures[0]["predicate"], "hand_open")

    def test_illegal_blackboard_key_fails(self) -> None:
        result = self.run_case(program("open_hand"), bad_key_runner)
        self.assertEqual(result.failure_code, "INVALID_BLACKBOARD")

    def test_blackboard_entry_limit_fails(self) -> None:
        result = self.run_case(program("open_hand"), too_many_runner)
        self.assertEqual(result.failure_code, "INVALID_BLACKBOARD")

    def test_one_repair_replan_replaces_the_tail(self) -> None:
        snapshot = view(with_repair=True)
        result = self.run_case(
            program("locate_target", "open_hand", on_failure=(("TARGET_NOT_FOUND", "regrasp"),), view_id=snapshot.snapshot.id),
            fail_once,
            view=snapshot,
            task=task(),
            initial=TP01_INITIAL,
            admission="practice",
        )
        self.assertEqual(result.replans, 1)
        self.assertIsNone(result.failure_code)
        self.assertEqual(result.steps[0].failure_code, "TARGET_NOT_FOUND")
        self.assertEqual(result.steps[1].op_id, "open_hand")
        self.assertIn("replan", [event["event"] for event in result.events])


if __name__ == "__main__":
    unittest.main()
