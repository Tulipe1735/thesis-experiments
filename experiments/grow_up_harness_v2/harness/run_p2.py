"""P2 Agent driver: diagnose, author, practice, re-verify, promote, reuse.

The driver wires the existing parts; it does not fake a model reply or a
verdict. A run is a directory written once. Every practice episode is kept,
including failures. The token cap counts input + output + reasoning.

Two modes:

* ``--max-practice 1`` is the smoke: one author call and one physical practice
  episode, then stop. It qualifies the Worker, budget and feedback loop; it
  does not promote or claim Agent success.
* the full run follows the registered 44-episode cap and promotes only after a
  successful practice episode, a deterministic script re-verify and an Agent
  compose re-verify on the same saved initial state.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROOT = PACKAGE_ROOT.parents[1]
for path in (
    PACKAGE_ROOT,
    ROOT,
    ROOT / "grasp_optimization",
    PACKAGE_ROOT / "calibration",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from harness import (  # noqa: E402
    agent,
    agent_workspace,
    evaluator,
    evidence,
    experience,
    ir,
    opencode_server,
    ops,
    registry,
    router,
    runtime,
    tp01,
    validation,
)
from harness.contracts import (  # noqa: E402
    CodeModule,
    MemoryNote,
    Op,
    PlanMode,
    Predicate,
    ProgramStep,
    Scope,
    Skill,
    Status,
    TaskProgram,
    Validation,
)
from harness.router import Route  # noqa: E402
from harness.worker_runner import WorkerRunner  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.train_tp01 import body_packet  # noqa: E402

DATE = "2026-11-04"
RUN_ID = "p2_agent_20261104_005"
S_STAR = "TP01_reach_train_000"
S_STAR_PARENT = "TP01_train_000"
PROGRAM_BUDGET_S = 87.1
EPISODE_CAP_S = 120.0
MAX_PRACTICE = 44
MAX_CALLS = 60
TOKEN_CAP = 1_500_000
WALL_CAP_S = 8 * 3600
SMALL_OP_IDS = tuple(item.op_id for item in ops.SMALL_OPS)
ARM_HAND = tuple(
    "left_hand_" + part + "_joint"
    for part in ("thumb_0", "thumb_1", "thumb_2", "middle_0", "middle_1", "index_0", "index_1")
)

RUNS = PACKAGE_ROOT / "runs"
B1_RUN = RUNS / "v2_3_b1_fallback_20261103_001"
B1_EPISODE = B1_RUN / "case_01"
B2_RUN = RUNS / "calib_b2_s_star_20261103_001"
F0_RUN = RUNS / "f0v2_engineering_20261103_001"
R_EPISODE = F0_RUN / "case_01"
AUDIT_RUN = RUNS / "audit_recompute_20261103_001"
PRECHECK_RUN = RUNS / "gateway_author_smoke_20261104_007"
SOURCE_FILES = (
    "experiments/grow_up_harness_v2/harness/run_p2.py",
    "experiments/grow_up_harness_v2/harness/agent.py",
    "experiments/grow_up_harness_v2/harness/agent_workspace.py",
    "experiments/grow_up_harness_v2/harness/opencode_server.py",
    "experiments/grow_up_harness_v2/harness/tp01.py",
    "experiments/grow_up_harness_v2/harness/worker_runner.py",
    "experiments/grow_up_harness_v2/harness/registry.py",
    "experiments/grow_up_harness_v2/harness/validation.py",
    "experiments/grow_up_harness_v2/harness/experience.py",
    "experiments/grow_up_harness_v2/harness/predicates.py",
    "experiments/grow_up_harness_v2/registration.json",
    "experiments/grow_up_harness_v2/registration_budget_v2.json",
    "experiments/grow_up_harness_v2/calibration/isolation_precheck.py",
)
CHECK_KEYS = (
    "candidate_ops_execute_in_worker",
    "candidate_ops_rejected_in_formal_before_promotion",
    "baseline_failure_preserved",
    "feasibility_gate_recorded",
    "baseline_lineage_root_declared",
    "failure_diagnosis_uses_only_legal_observation",
    "candidate_ops_run_in_practice",
    "practice_budget_registered",
    "all_practice_failures_preserved",
    "verified_task_success",
    "repair_same_initial_state_script_passes",
    "repair_same_initial_state_agent_passes",
    "contract_tests_pass",
    "blackboard_recorded",
    "negative_control_not_credited",
    "evaluator_positive_control_passes",
    "fallback_pairing_recomputed",
    "regression_passes",
    "promotion_writes_new_snapshot",
    "ops_promoted_are_used",
    "formal_reuse_selects_promoted_skill",
    "evaluator_recomputes_from_saved_state",
    "evidence_hashes_verify",
    "test_split_untouched",
    "no_physical_claim",
    "gateway_smoke_passed",
)


class StopRun(RuntimeError):
    """A registered stop rule fired; the run is incomplete, not a success."""

    def __init__(self, reason: str, detail: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = dict(detail or {})


@dataclass
class CallRecord:
    index: int
    kind: str
    status: str
    directory: str
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float = 0.0
    wall_time_s: float = 0.0
    prompt_sha256: str | None = None
    response_sha256: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class CallBudget:
    run_dir: Path
    started: float = field(default_factory=time.monotonic)
    records: list[CallRecord] = field(default_factory=list)
    per_kind: dict[str, int] = field(default_factory=dict)
    token_total: int = 0
    simulation_seconds: float = 0.0
    physical_episodes: int = 0

    LIMITS = {
        "diagnose": 1,
        "author_first": 1,
        "practice_revision": 44,
        "repair_compose": 1,
        "format_retry": 8,
        "reserve": 5,
    }

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def can_call(self, kind: str) -> tuple[bool, str]:
        if len(self.records) >= MAX_CALLS:
            return False, "call cap 60 reached"
        if self.elapsed() > WALL_CAP_S:
            return False, "wall cap 8 h reached"
        if self.token_total >= TOKEN_CAP:
            return False, "token cap 1,500,000 reached"
        limit = self.LIMITS.get(kind)
        if limit is None:
            return False, f"unknown call kind: {kind}"
        if self.per_kind.get(kind, 0) >= limit:
            return False, f"{kind} cap {limit} reached"
        return True, ""

    def next_index(self) -> int:
        return len(self.records) + 1

    def record(
        self,
        kind: str,
        directory: Path,
        response: agent.GatewayResponse | None,
        *,
        status: str,
        error: str | None = None,
    ) -> CallRecord:
        used = 0
        record = CallRecord(
            index=self.next_index(),
            kind=kind,
            status=status,
            directory=relative(directory),
            error=error,
        )
        if response is not None:
            used = response.input_tokens + response.output_tokens + response.reasoning_tokens
            record.session_id = response.session_id
            record.input_tokens = response.input_tokens
            record.output_tokens = response.output_tokens
            record.reasoning_tokens = response.reasoning_tokens
            record.cost = response.cost
            record.wall_time_s = response.wall_time_s
            record.prompt_sha256 = response.prompt_sha256
            record.response_sha256 = response.response_sha256
        self.records.append(record)
        self.per_kind[kind] = self.per_kind.get(kind, 0) + 1
        self.token_total += used
        with (self.run_dir / "calls.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return record

    def add_episode(self, simulation_seconds: float) -> None:
        self.physical_episodes += 1
        self.simulation_seconds += max(0.0, float(simulation_seconds))
        if self.simulation_seconds > 7200.0 + 1e-6:
            raise StopRun("SIMULATION_BUDGET_EXCEEDED", {"used": self.simulation_seconds})

    def summary(self) -> dict:
        return {
            "calls": len(self.records),
            "per_kind": dict(sorted(self.per_kind.items())),
            "token_total": self.token_total,
            "token_cap": TOKEN_CAP,
            "wall_time_s": round(self.elapsed(), 1),
            "wall_cap_s": WALL_CAP_S,
            "physical_episodes": self.physical_episodes,
            "simulation_seconds": round(self.simulation_seconds, 3),
            "sessions": [record.session_id for record in self.records if record.session_id],
        }


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_new(path, value)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def write_replace(path: Path, value) -> None:
    """Rewrite a mutable index; evidence files still use exclusive creation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def s_star_case():
    cases = tp01.load_cases()
    chosen = [case for case in cases if case.instance_id == S_STAR]
    if len(chosen) != 1:
        raise StopRun("S_STAR_MISSING", {"instance": S_STAR})
    case = chosen[0]
    if case.initial_state_sha256 != "6c7942293a161033ced408d389b167d16c48726c1daee8a18eadf50ec276b920":
        raise StopRun("S_STAR_HASH_DRIFT", {"sha256": case.initial_state_sha256})
    if not case.valid_initial_fixture:
        raise StopRun("S_STAR_NOT_QUALIFIED")
    # The v2 budget supersedes the TaskSpec's legacy 60 s. The episode cap stays
    # 120 s; only the program budget grows to the measured 87.1 s.
    return dataclasses.replace(
        case, task=dataclasses.replace(case.task, budget_s=PROGRAM_BUDGET_S)
    )


def public_task(case: tp01.TP01Case) -> dict:
    target = next(item for item in case.instance["objects"] if item["is_target"])
    return {
        "id": case.task.id,
        "template": "TP01",
        "instruction": case.task.instruction,
        "assets": sorted(case.task.assets),
        "target_category": case.target_category,
        "nominal_rgba": target["asset"]["rgba"],
        "minimum_lift_m": 0.10,
        "stable_s": 1.0,
        "terminal_mode": "held",
        "budget_s": PROGRAM_BUDGET_S,
        "split": "train",
    }


def observation_sample(case: tp01.TP01Case, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    model = tp01.build_scene(case, directory / "scene.xml")
    plant = tp01.make_plant(case, model, directory, budget=EPISODE_CAP_S)
    payload = plant.observation()
    payload["rgbd"] = {
        "rgb": {"shape": [180, 320, 3], "dtype": "uint8"},
        "depth_m": {"shape": [180, 320], "dtype": "float32"},
        "K": [[300.0, 0.0, 160.0], [0.0, 300.0, 90.0], [0.0, 0.0, 1.0]],
        "T_optical_to_pelvis": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "timestamp_s": 0.0,
    }
    return payload


def _test_split_untouched() -> bool:
    dataset = ROOT / "experiments/t0_agent_v1/tabletop_dataset_20261026_002"
    frozen = read(dataset / "freeze_manifest.json")
    expected = frozen["artifacts"].get("test/manifest.json")
    return bool(expected) and expected == sha(dataset / "test/manifest.json")


def run_unit_tests() -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-t",
            ".",
        ],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
        env={
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MUJOCO_GL": "egl",
        },
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "tail": output.strip().splitlines()[-4:],
    }


def preflight(run_dir: Path, precheck: Path, *, skip_unit_tests: bool = False) -> dict:
    case = s_star_case()
    b1 = read(B1_RUN / "results.json")
    b2 = read(B2_RUN / "results.json")
    f0 = read(F0_RUN / "results.json")
    audit = read(AUDIT_RUN / "results.json")
    registration = read(PACKAGE_ROOT / "registration.json")
    b1_registration = registration["baselines"]["B1"]
    r_pose = read(R_EPISODE / "initial_pose.json")
    r_verdict = read(R_EPISODE / "independent_verification.json")
    precheck_summary = read(precheck / "results.json")
    tests = {"ok": True, "skipped": True, "tail": ["skipped by flag"]} if skip_unit_tests else run_unit_tests()
    checks = {
        "s_star_case": case.instance_id == S_STAR,
        "b1_failed": b1["verdict"]["verified_task_success"] is False,
        "b1_same_initial": b1["initial_state_sha256"] == case.initial_state_sha256,
        "b1_lineage_root": b1_registration.get("lineage_root") is True
        and b1_registration.get("kind") == "fallback"
        and b1.get("label") == "B1_fallback",
        "b2_failed": b2["verdict"]["verified_task_success"] is False,
        "b2_same_initial": b2["initial_state_sha256"] == case.initial_state_sha256,
        "f0_passed": f0["status"] == "FEASIBILITY_GATE_PASSED"
        and f0["s_star"] == S_STAR,
        "r_passed": r_verdict["verified_task_success"] is True,
        "r_same_initial": r_pose.get("dataset_case") == S_STAR,
        "audit_16": bool(audit.get("all_match")),
        "test_split_untouched": _test_split_untouched(),
        "gateway_precheck_passed": bool(precheck_summary.get("passed")),
        "gateway_precheck_zero_episodes": precheck_summary.get("experiment_episodes")
        == 0,
        "unit_tests": bool(tests["ok"]),
    }
    summary = {
        "checks": checks,
        "passed": all(checks.values()),
        "case": {
            "instance": case.instance_id,
            "alias": case.alias,
            "initial_state_sha256": case.initial_state_sha256,
            "qualification_sha256": case.qualification_sha256,
            "target_category": case.target_category,
            "valid_initial_fixture": case.valid_initial_fixture,
        },
        "baselines": {
            "B1": {
                "run": relative(B1_RUN / "results.json"),
                "verified_task_success": b1["verdict"]["verified_task_success"],
                "failure": b1.get("guard") or b1.get("error"),
                "initial_state_sha256": b1["initial_state_sha256"],
                "lineage_root": b1_registration.get("lineage_root"),
            },
            "B2": {
                "run": relative(B2_RUN / "results.json"),
                "verified_task_success": b2["verdict"]["verified_task_success"],
                "initial_state_sha256": b2["initial_state_sha256"],
            },
            "R": {
                "run": relative(R_EPISODE),
                "verified_task_success": r_verdict["verified_task_success"],
                "dataset_case": r_pose.get("dataset_case"),
            },
            "F0": {"run": relative(F0_RUN / "results.json"), "status": f0["status"]},
            "audit": {"run": relative(AUDIT_RUN / "results.json"), "all_match": audit.get("all_match")},
        },
        "unit_tests": tests,
        "precheck": relative(precheck / "results.json"),
    }
    return {"case": case, "b1": b1, "b2": b2, "f0": f0, "audit": audit,
            "r_verdict": r_verdict, "precheck": precheck_summary, "summary": summary}


def call_gateway(
    gateway: agent.OpenCodeGateway,
    prompt: str,
    kind: str,
    directory: Path,
    budget: CallBudget,
) -> agent.GatewayResponse:
    allowed, why = budget.can_call(kind)
    if not allowed:
        raise StopRun("CALL_BUDGET_EXCEEDED", {"kind": kind, "reason": why})
    directory.mkdir(parents=True, exist_ok=False)
    write_text(directory / "prompt.txt", prompt)
    try:
        response = gateway.run(prompt)
    except Exception as error:
        message = str(error)
        write_text(directory / "error.txt", message + "\n")
        budget.record(kind, directory, None, status="FAILED", error=message[:600])
        raise
    write_json(
        directory / "response.json",
        {
            **response.to_dict(),
            "kind": kind,
            "experiment_episode": False,
        },
    )
    write_text(
        directory / "events.jsonl",
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in response.events),
    )
    budget.record(kind, directory, response, status="PASSED")
    return response


def call_with_schema(
    gateway: agent.OpenCodeGateway,
    budget: CallBudget,
    *,
    kind: str,
    directory: Path,
    prompt: str,
    parse,
    retry_builder,
) -> tuple[dict, agent.GatewayResponse]:
    attempt = 0
    current_prompt = prompt
    while True:
        attempt += 1
        use_kind = kind if attempt == 1 else "format_retry"
        folder = directory if attempt == 1 else directory.with_name(directory.name + f"_retry{attempt - 1}")
        try:
            response = call_gateway(gateway, current_prompt, use_kind, folder, budget)
            payload = parse(agent.parse_json_reply(response.text))
            return payload, response
        except (agent.AgentSchemaError, agent.GatewayUnavailable) as error:
            if attempt >= 2:
                raise StopRun(
                    "AGENT_REPLY_REJECTED",
                    {"kind": kind, "error": str(error)[:600], "directory": relative(folder)},
                ) from None
            current_prompt = retry_builder(str(error))


def author_payload(
    gateway: agent.OpenCodeGateway,
    budget: CallBudget,
    *,
    kind: str,
    directory: Path,
    task: dict,
    observation: dict,
    diagnosis: dict | None,
    previous_ops: dict | None,
    feedback: dict | None,
) -> dict:
    prompt = agent.author_ops_prompt(
        task,
        observation,
        diagnosis,
        previous_ops=previous_ops,
        feedback=feedback,
    )

    def retry_builder(error: str) -> str:
        return agent.author_ops_prompt(
            task,
            observation,
            {"schema_error": error, **(diagnosis or {})},
            previous_ops=previous_ops,
            feedback={**(feedback or {}), "schema_error": error},
        )

    payload, _response = call_with_schema(
        gateway,
        budget,
        kind=kind,
        directory=directory,
        prompt=prompt,
        parse=agent.validate_author_ops,
        retry_builder=retry_builder,
    )
    return payload


def candidate_bundle(
    payload: dict,
    scope: Scope,
    case: tp01.TP01Case,
    version: int,
    evidence_refs: tuple[str, ...],
) -> dict:
    modules = experience.candidate_code(payload, scope, version=version)
    candidate_ops = experience.candidate_ops(modules, scope, *evidence_refs, version=version)
    skill = Skill(
        id="skill_tp01_chain_candidate",
        version=version,
        scope=scope,
        status=Status.CANDIDATE,
        validation=None,
        steps=ops.TP01_CHAIN,
        pre=ops.TP01_INITIAL,
        post=(Predicate("target_stable"),),
        evidence=evidence_refs,
        dependencies=(
            "python:3.12",
            "numpy:2.5.4",
            "worker:seccomp-v1",
            "evaluator:tabletop-predicates-v1",
        ),
    )
    memory_text = " ; ".join(payload.get("memory") or []) or "no candidate memory returned"
    memory = MemoryNote(
        id="mem_tp01_candidate",
        text=memory_text[:2000],
        scope=scope,
        status=Status.CANDIDATE,
        evidence=evidence_refs,
    )
    return {
        "payload": payload,
        "modules": modules,
        "ops": candidate_ops,
        "skill": skill,
        "memory": memory,
        "explanation": payload["explanation"],
    }


def commit_bundle(
    store: registry.Registry,
    parent: str | None,
    bundle: dict,
    scope: Scope,
    label: str,
) -> tuple[str, object]:
    refs: dict[str, str] = {}
    if parent is not None:
        refs = dict(store.load(parent).snapshot.refs)
        refs = {key: value for key, value in refs.items() if not key.startswith("code_")}
    for op in ops.make_builtin_ops(scope):
        refs[op.op_id] = store.put(op)
    for module in bundle["modules"]:
        refs[module.id] = store.put(module)
    for op in bundle["ops"]:
        refs[op.op_id] = store.put(op)
    refs[bundle["skill"].id] = store.put(bundle["skill"])
    refs[bundle["memory"].id] = store.put(bundle["memory"])
    snapshot = store.commit(list(refs.items()), label=label, parent=parent)
    return snapshot.id, store.load(snapshot.id)


def make_runner(view, admission: str, case: tp01.TP01Case):
    index = ir.op_index(view, admission)
    sources: dict[str, str] = {}
    for op_id, op in index.items():
        if op.builtin:
            continue
        module = view.artifacts.get(op.implementation or "")
        if not isinstance(module, CodeModule):
            raise StopRun("MISSING_CODE_MODULE", {"op_id": op_id, "implementation": op.implementation})
        sources[op_id] = module.source
    profile = body_packet()
    task = public_task(case)
    builtin = runtime.builtin_runner(case)

    def runner(step, *, plant, blackboard: dict, budget):
        if step.op_id in ("open_hand", "check"):
            return builtin(step, plant=plant, blackboard=blackboard, budget=budget)
        try:
            source = sources[step.op_id]
        except KeyError:
            raise StopRun("NO_WORKER_SOURCE", {"op_id": step.op_id}) from None
        return WorkerRunner(source, profile, task)(
            step, plant=plant, blackboard=blackboard, budget=budget
        )

    return runner


def run_episode(
    case: tp01.TP01Case,
    view,
    admission: str,
    output: Path,
    *,
    program: TaskProgram | None = None,
    decide: bool = True,
) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    model = tp01.build_scene(case, output / "scene.xml")
    plant = tp01.make_plant(case, model, output, budget=EPISODE_CAP_S)
    image_errors = []
    try:
        plant.head_image(output / "initial_head.jpg")
    except Exception as error:
        image_errors.append(f"initial: {type(error).__name__}: {error}")
    state = tp01.step_state(plant, case, tp01.visibility_perception(plant, case))
    decision = None
    if program is None:
        if not decide:
            raise StopRun("NO_PROGRAM")
        decision = router.decide(case.task, view, admission=admission, predicate_state=state)
        if decision.route is not Route.FAST or decision.program is None:
            raise StopRun(
                "ROUTE_NOT_FAST",
                {"route": decision.route.value, "reason": decision.reason},
            )
        program = decision.program
    runner = make_runner(view, admission, case)
    result = runtime.Runtime(plant, case, output).run(
        program,
        runner,
        view=view,
        task=case.task,
        initial=ops.TP01_INITIAL,
        admission=admission,
        verify=True,
        strict_posts=True,
    )
    if image_errors:
        write_json(output / "image_errors.json", image_errors)
    evidence.write_hashes(output)
    execution = read(output / "execution.json")
    verdict = result.verdict
    return {
        "episode": relative(output),
        "program_id": result.program_id,
        "program_sha256": result.program_sha256,
        "program_steps": [step.op_id for step in program.steps],
        "route": decision.route.value if decision else "provided",
        "artifact_id": decision.artifact_id if decision else None,
        "route_reason": decision.reason if decision else None,
        "initial_state_sha256": case.initial_state_sha256,
        "plant_initial_state_sha256": result.initial_state_sha256,
        "final_state_sha256": result.final_state_sha256,
        "failure_code": result.failure_code,
        "failed_op": result.failed_op,
        "failed_step": result.failed_step,
        "replans": result.replans,
        "post_failures": result.post_failures,
        "steps": [
            {
                "op_id": outcome.op_id,
                "status": outcome.status,
                "failure_code": outcome.failure_code,
                "actions": outcome.actions,
                "sim_time": outcome.sim_time,
                "worker_security": (outcome.detail or {}).get("worker_security"),
                "worker_error": {
                    key: (outcome.detail or {}).get(key)
                    for key in ("error", "message")
                    if (outcome.detail or {}).get(key)
                }
                or None,
                "blackboard_error": (outcome.detail or {}).get("blackboard"),
                "action_rejection": (outcome.detail or {}).get("reason")
                if (outcome.detail or {}).get("response") == "REJECTED"
                else None,
                "missing_localization_output": (
                    outcome.op_id == "locate_target"
                    and outcome.failure_code == "PREDICATE_UNAVAILABLE"
                ),
            }
            for outcome in result.steps
        ],
        "verified_task_success": bool(verdict and verdict.verified_task_success),
        "goal_satisfied": bool(verdict and verdict.goal_satisfied),
        "terminal_stable_s": float(verdict.terminal_stable_s) if verdict else 0.0,
        "simulation_seconds": execution["simulation_seconds"],
        "guard": execution.get("guard"),
        "image_errors": image_errors,
    }


def action_requests(episode: Path) -> list[dict]:
    rows = read(episode / "actions.json")
    return [row.get("request", row) for row in rows]


def episode_hashes_ok(rows: list[dict]) -> bool:
    if not rows:
        return False
    for row in rows:
        path = ROOT / row["episode"]
        if not evidence.verify_hashes(path).get("ok"):
            return False
    return True


def rows_hash_ok(*rows) -> bool:
    present = [row for row in rows if row and row.get("episode")]
    return bool(present) and episode_hashes_ok(present)


def replay_matches(case: tp01.TP01Case, episode: Path) -> bool:
    recorded = read(episode / "independent_verification.json")
    replayed = evaluator.replay(case, episode)
    return (
        replayed.verified_task_success == recorded["verified_task_success"]
        and replayed.goal_satisfied == recorded["goal_satisfied"]
    )


def compose_program(
    payload: dict,
    view,
    case: tp01.TP01Case,
    skill: Skill,
    *,
    admission: str = "practice",
) -> TaskProgram:
    if "refuse" in payload:
        raise StopRun("AGENT_COMPOSE_REFUSED", {"reason": payload["refuse"][:400]})
    raw_steps = payload["program"]["steps"]
    index = ir.op_index(view, admission)
    steps: list[ProgramStep] = []
    for position, raw in enumerate(raw_steps):
        if not isinstance(raw, dict) or "op_id" not in raw:
            raise StopRun("COMPOSE_BAD_STEP", {"index": position, "step": raw})
        op_id = str(raw["op_id"])
        args = raw.get("args", ())
        if isinstance(args, dict):
            pairs = tuple((str(key), value) for key, value in args.items())
        elif isinstance(args, (list, tuple)):
            pairs = tuple((str(item[0]), item[1]) for item in args)
        else:
            raise StopRun("COMPOSE_BAD_ARGS", {"index": position, "args": args})
        if op_id not in index:
            raise StopRun("COMPOSE_UNKNOWN_OP", {"op_id": op_id})
        steps.append(
            ProgramStep(
                index=position,
                op_id=op_id,
                op_version=index[op_id].version,
                args=pairs,
            )
        )
    program = TaskProgram(
        id=f"prog_agent_compose_{case.task.id}",
        task_id=case.task.id,
        snapshot_id=view.snapshot.id,
        mode=PlanMode.REUSE,
        steps=tuple(steps),
        artifact_ids=(skill.id,),
        budget_s=PROGRAM_BUDGET_S,
    )
    ir.validate_program(program, view, admission, case.task)
    ir.validate_sequence(program, view, admission, case.task, ops.TP01_INITIAL)
    return program


def metrics_of(row: dict) -> dict:
    return {
        "verified_task_success": bool(row.get("verified_task_success")),
        "retries": int(row.get("replans") or 0),
        "stable_s": float(row.get("terminal_stable_s") or 0.0),
        "simulation_seconds": float(row.get("simulation_seconds") or 0.0),
        "initial_state_sha256": row.get("initial_state_sha256"),
    }


def build_checks(
    *,
    preflight: dict,
    practice_rows: list[dict],
    success_row: dict | None,
    script_row: dict | None,
    agent_row: dict | None,
    sequences_match: bool,
    reports: list,
    promotion: dict,
    t_row: dict | None,
    t_decision: dict | None,
    pairing: dict | None,
    evaluator_recomputes: bool,
    hashes_ok: bool,
    test_split: bool,
    unit_tests_ok: bool,
) -> tuple[dict[str, bool], dict[str, str]]:
    executed = set()
    for row in practice_rows:
        for step in row.get("steps", []):
            if step.get("status") == "executed" and step.get("worker_security"):
                executed.add(step["op_id"])
    candidate_practice = any(
        step.get("op_id") in SMALL_OP_IDS
        for row in practice_rows
        for step in row.get("steps", [])
    )
    failure_preserved = bool(practice_rows) and all(
        (ROOT / row["episode"] / "feedback.json").is_file()
        and (ROOT / row["episode"] / "independent_verification.json").is_file()
        and evidence.verify_hashes(ROOT / row["episode"]).get("ok")
        for row in practice_rows
    )
    checks = {
        "candidate_ops_execute_in_worker": set(SMALL_OP_IDS) <= executed,
        "candidate_ops_rejected_in_formal_before_promotion": bool(
            preflight.get("formal_rejection")
        ),
        "baseline_failure_preserved": preflight["summary"]["checks"]["b1_failed"],
        "feasibility_gate_recorded": preflight["summary"]["checks"]["f0_passed"],
        "baseline_lineage_root_declared": preflight["summary"]["checks"]["b1_lineage_root"],
        "failure_diagnosis_uses_only_legal_observation": bool(
            preflight.get("diagnosis_legal")
        ),
        "candidate_ops_run_in_practice": candidate_practice,
        "practice_budget_registered": bool(
            preflight.get("run_registered_before_execution")
        ),
        "all_practice_failures_preserved": failure_preserved,
        "verified_task_success": bool(success_row and success_row["verified_task_success"]),
        "repair_same_initial_state_script_passes": bool(
            script_row and script_row["verified_task_success"]
        ),
        "repair_same_initial_state_agent_passes": bool(
            agent_row and agent_row["verified_task_success"] and sequences_match
        ),
        "contract_tests_pass": bool(reports)
        and all(flag for report in reports for _name, flag in report.contract_tests)
        and unit_tests_ok,
        "blackboard_recorded": bool(success_row)
        and (ROOT / success_row["episode"] / "blackboard.jsonl").is_file()
        and bool((ROOT / success_row["episode"] / "blackboard.jsonl").read_text(encoding="utf-8").strip()),
        "negative_control_not_credited": preflight["summary"]["checks"]["b2_failed"],
        "evaluator_positive_control_passes": preflight["summary"]["checks"]["r_passed"],
        "fallback_pairing_recomputed": bool(pairing)
        and pairing.get("same_initial_state") is True,
        "regression_passes": preflight["summary"]["checks"]["audit_16"]
        and preflight["summary"]["checks"]["b2_failed"]
        and preflight["summary"]["checks"]["f0_passed"]
        and preflight["summary"]["checks"]["r_passed"]
        and test_split
        and unit_tests_ok,
        "promotion_writes_new_snapshot": bool(promotion.get("head_frozen"))
        and bool(promotion.get("verify_ok")),
        "ops_promoted_are_used": bool(t_row)
        and bool(t_row.get("promoted_ops_used")),
        "formal_reuse_selects_promoted_skill": bool(t_decision)
        and t_decision.get("route") == "fast"
        and t_decision.get("artifact_id") == promotion.get("skill_id"),
        "evaluator_recomputes_from_saved_state": bool(evaluator_recomputes),
        "evidence_hashes_verify": bool(hashes_ok),
        "test_split_untouched": bool(test_split),
        "no_physical_claim": True,
        "gateway_smoke_passed": preflight["summary"]["checks"]["gateway_precheck_passed"],
    }
    if set(checks) != set(CHECK_KEYS):
        raise StopRun("CHECK_KEYS_DRIFT")
    notes = {
        "candidate_ops_execute_in_worker": f"executed op ids: {sorted(executed)}",
        "verified_task_success": (
            f"practice episode {success_row['episode']}" if success_row else "no verified practice success"
        ),
        "fallback_pairing_recomputed": (
            f"treatment_better={pairing.get('treatment_better')}" if pairing else "no T row"
        ),
        "formal_reuse_selects_promoted_skill": (
            f"artifact={t_decision.get('artifact_id')}" if t_decision else "no formal decision"
        ),
    }
    return checks, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--precheck", default=str(PRECHECK_RUN))
    parser.add_argument("--max-practice", type=int, default=MAX_PRACTICE)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--skip-unit-tests", action="store_true")
    args = parser.parse_args(argv)

    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    write_json(
        output_root / "source_hashes.json",
        {
            "date": DATE,
            "boundary": "simulation",
            "files": {name: sha(ROOT / name) for name in SOURCE_FILES},
        },
    )
    smoke = args.max_practice < MAX_PRACTICE
    precheck_path = Path(args.precheck).resolve()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    budget = CallBudget(run_dir=output_root)
    status = "STARTED"
    failure_reason = None
    preflight_data = None
    checks: dict[str, bool] = {}
    notes: dict[str, str] = {}
    practice_rows: list[dict] = []
    success_row = None
    script_row = None
    agent_row = None
    sequences_match = False
    reports = []
    promotion: dict = {}
    t_row = None
    t_decision = None
    pairing = None
    peer_cup = None
    scope_checks = None
    evaluator_recomputes = False
    gateway_info = None

    try:
        preflight_data = preflight(
            output_root, precheck_path, skip_unit_tests=args.skip_unit_tests
        )
        write_json(output_root / "preflight.json", preflight_data["summary"])
        if not preflight_data["summary"]["passed"]:
            raise StopRun("PREFLIGHT_FAILED", preflight_data["summary"]["checks"])
        case = preflight_data["case"]
        public = public_task(case)
        sample = observation_sample(case, output_root / "observation_sample")
        write_json(output_root / "public_task.json", public)
        write_json(output_root / "observation_sample.json", sample)
        main_run = read(PACKAGE_ROOT / "registration.json")["current_run"]
        registered_before = bool(
            main_run.get("registered_before_execution")
            and main_run.get("run_id") == args.run_id
            and main_run.get("initial_state", {}).get("initial_state_sha256")
            == case.initial_state_sha256
        )
        preflight_data["run_registered_before_execution"] = registered_before
        if not registered_before:
            raise StopRun("RUN_NOT_PRE_REGISTERED", {"run_id": args.run_id})

        # One private server in the Agent workspace: the project is the
        # workspace from its first request, and the deny-all config applies.
        workspace_root = Path("/tmp/opencode/growup_agent_workspaces") / output_root.name
        workspace = agent_workspace.prepare_workspace(workspace_root)
        with opencode_server.serve(workspace, output_root / "server") as server:
            gateway_info = {
                "url": server["url"],
                "pid": server["pid"],
                "workspace": str(workspace),
                "config_sha256": agent_workspace.config_sha256(),
                "model": agent_workspace.MODEL,
            }
            gateway = agent.OpenCodeGateway(
                workspace,
                model=agent_workspace.MODEL,
                timeout_s=args.timeout,
                server=server["url"],
                env={"OPENCODE_PASSWORD": server["password"]},
            )
            canary = workspace_root / "canary.txt"
            canary.write_text("CANARY-" + __import__("secrets").token_hex(6) + "\n", encoding="utf-8")
            canary_response = call_gateway(
                gateway,
                (
                    f"Read the file {canary} with the read tool and reply with its exact "
                    "contents. If you cannot read it, reply exactly: CANARY_BLOCKED"
                ),
                "reserve",
                output_root / "gateway" / "canary",
                budget,
            )
            token = canary.read_text(encoding="utf-8").strip()
            leaked = token in canary_response.text or token in json.dumps(
                [event for event in canary_response.events], ensure_ascii=False
            )
            write_json(
                output_root / "gateway" / "canary_result.json",
                {
                    "leaked": leaked,
                    "text": canary_response.text,
                    "session_id": canary_response.session_id,
                },
            )
            if leaked:
                raise StopRun("CANARY_LEAKED")

            # Legal diagnose input: B1's coarse public failure only.
            feedback = {
                "verdict": "failure",
                "stage": "fallback",
                "failure_code": preflight_data["b1"].get("guard") or "FORBIDDEN_CONTACT",
                "task_id": case.task.id,
                "sim_time": float(preflight_data["b1"].get("simulation_seconds") or 0.0),
                "stable_s": 0.0,
            }
            diagnosis_prompt = agent.diagnose_prompt(
                public, feedback, "tp01_policy_legacy", 0
            )
            diagnosis_payload, _ = call_with_schema(
                gateway,
                budget,
                kind="diagnose",
                directory=output_root / "agent" / "diagnose",
                prompt=diagnosis_prompt,
                parse=agent.validate_diagnose,
                retry_builder=lambda error: agent.diagnose_prompt(
                    public,
                    {**feedback, "schema_error": error},
                    "tp01_policy_legacy",
                    0,
                ),
            )
            script_diag = experience.diagnose(
                B1_EPISODE,
                case.task,
                mechanism=diagnosis_payload["diagnosis"],
                repair_boundary=diagnosis_payload["repair_boundary"],
            )
            diagnosis = {
                "episode": relative(B1_EPISODE),
                "task_id": case.task.id,
                "failed_op": "tp01_policy_legacy",
                "failed_step": 0,
                "failure_code": feedback["failure_code"],
                "agent_visible": feedback,
                "mechanism": diagnosis_payload["diagnosis"],
                "repair_boundary": diagnosis_payload["repair_boundary"],
                "memory": diagnosis_payload["memory"],
                "script_legal_only": script_diag.legal_only,
                "legal_only": script_diag.legal_only
                and not any(key in feedback for key in ("target_pose", "object_pose", "thresholds", "raw_frames")),
            }
            if not diagnosis["legal_only"]:
                raise StopRun("DIAGNOSIS_NOT_LEGAL")
            write_json(output_root / "diagnosis.json", diagnosis)
            preflight_data["diagnosis_legal"] = diagnosis["legal_only"]

            store = registry.Registry(output_root / "registry")
            scope = Scope(task="TP01", assets=frozenset({case.target_category}), stage=case.task.id)
            author_payload_data = author_payload(
                gateway,
                budget,
                kind="author_first",
                directory=output_root / "agent" / "author_001",
                task=public,
                observation=sample,
                diagnosis=diagnosis,
                previous_ops=None,
                feedback=None,
            )
            write_json(output_root / "agent" / "author_001" / "payload.json", author_payload_data["ops"])
            bundle = candidate_bundle(
                author_payload_data,
                scope,
                case,
                1,
                (relative(B1_EPISODE), relative(output_root / "diagnosis.json")),
            )
            snapshot_id, view = commit_bundle(store, None, bundle, scope, "p2:candidate:v1")
            write_json(
                output_root / "agent" / "author_001" / "bundle.json",
                {
                    "op_ids": sorted(op.op_id for op in bundle["ops"]),
                    "source_sha256": {
                        op.op_id: op.implementation_sha256 for op in bundle["ops"]
                    },
                    "skill_id": bundle["skill"].id,
                    "skill_version": bundle["skill"].version,
                    "snapshot_id": snapshot_id,
                },
            )

            max_practice = max(1, min(args.max_practice, MAX_PRACTICE))
            previous_row = None
            for episode_no in range(1, max_practice + 1):
                if episode_no > 1:
                    feedback = {
                        "verdict": "failure",
                        "stage": previous_row.get("failed_op"),
                        "failure_code": previous_row.get("failure_code"),
                        "task_id": case.task.id,
                        "sim_time": float(previous_row.get("simulation_seconds") or 0.0),
                        "stable_s": float(previous_row.get("terminal_stable_s") or 0.0),
                    }
                    failed = next(
                        (step for step in reversed(previous_row["steps"]) if step["status"] == "failed"),
                        {},
                    )
                    if failed.get("worker_error"):
                        # The candidate's own code failed to return the action
                        # shape. That is code feedback, not evaluator truth.
                        feedback["worker_error"] = failed["worker_error"]
                    if failed.get("blackboard_error"):
                        feedback["blackboard_error"] = failed["blackboard_error"]
                    if failed.get("action_rejection"):
                        feedback["action_rejection"] = failed["action_rejection"]
                    if failed.get("missing_localization_output"):
                        feedback["contract_error"] = "locate_target returned done without a valid localization blackboard delta"
                    revision = author_payload(
                        gateway,
                        budget,
                        kind="practice_revision",
                        directory=output_root / "agent" / f"revision_{episode_no:03d}",
                        task=public,
                        observation=sample,
                        diagnosis={
                            "previous_explanation": bundle["explanation"],
                            "failed_op": previous_row.get("failed_op"),
                            "failed_step": previous_row.get("failed_step"),
                            "failure_code": previous_row.get("failure_code"),
                            "repair_boundary": "bounded revision; keep the goal, safety and budget",
                        },
                        previous_ops=bundle["payload"]["ops"],
                        feedback=feedback,
                    )
                    write_json(
                        output_root / "agent" / f"revision_{episode_no:03d}" / "payload.json",
                        revision["ops"],
                    )
                    bundle = candidate_bundle(
                        revision,
                        scope,
                        case,
                        episode_no,
                        (
                            relative(B1_EPISODE),
                            relative(output_root / "diagnosis.json"),
                            relative(ROOT / previous_row["episode"]),
                        ),
                    )
                    snapshot_id, view = commit_bundle(
                        store,
                        snapshot_id,
                        bundle,
                        scope,
                        f"p2:candidate:v{episode_no}",
                    )
                episode_dir = output_root / "practice" / f"episode_{episode_no:03d}"
                try:
                    row = run_episode(case, view, "practice", episode_dir)
                except StopRun:
                    raise
                except Exception as error:
                    write_json(
                        episode_dir / "harness_error.json",
                        {"type": type(error).__name__, "message": str(error)[:1200]},
                    )
                    if episode_dir.is_dir():
                        evidence.write_hashes(episode_dir)
                    row = {
                        "episode": relative(episode_dir),
                        "verified_task_success": False,
                        "failure_code": f"HARNESS_{type(error).__name__}",
                        "failed_op": None,
                        "failed_step": None,
                        "simulation_seconds": 0.0,
                        "terminal_stable_s": 0.0,
                        "steps": [],
                        "harness_error": str(error)[:600],
                    }
                row["episode_number"] = episode_no
                row["snapshot_id"] = snapshot_id
                row["candidate_version"] = bundle["skill"].version
                practice_rows.append(row)
                budget.add_episode(row.get("simulation_seconds") or 0.0)
                write_replace(output_root / "practice" / "index.json", practice_rows)
                print(
                    "PRACTICE",
                    json.dumps(
                        {
                            "episode": episode_no,
                            "success": row["verified_task_success"],
                            "failure": row.get("failure_code"),
                            "sim_time": row.get("simulation_seconds"),
                            "tokens": budget.token_total,
                            "calls": len(budget.records),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                previous_row = row
                if row["verified_task_success"]:
                    success_row = row
                    break
                if len(budget.records) >= MAX_CALLS or budget.token_total >= TOKEN_CAP:
                    break

            if smoke:
                status = "SMOKE_STOPPED"
                checks, notes = build_checks(
                    preflight=preflight_data,
                    practice_rows=practice_rows,
                    success_row=success_row,
                    script_row=None,
                    agent_row=None,
                    sequences_match=False,
                    reports=[],
                    promotion={},
                    t_row=None,
                    t_decision=None,
                    pairing=None,
                    evaluator_recomputes=False,
                    hashes_ok=rows_hash_ok(*practice_rows),
                    test_split=_test_split_untouched(),
                    unit_tests_ok=bool(preflight_data["summary"]["unit_tests"]["ok"]),
                )
                notes["smoke"] = "one practice episode; no promotion, no formal T"
                write_results(
                    output_root,
                    args,
                    started_at,
                    status,
                    budget,
                    preflight_data,
                    practice_rows,
                    success_row,
                    script_row,
                    agent_row,
                    sequences_match,
                    reports,
                    promotion,
                    t_row,
                    t_decision,
                    pairing,
                    peer_cup,
                    scope_checks,
                    evaluator_recomputes,
                    checks,
                    notes,
                    gateway_info,
                    failure_reason,
                )
                return 0

            if success_row is None:
                raise StopRun("NO_VERIFIED_PRACTICE_SUCCESS")

            # The formal rejection is checked before promotion.
            rejection_dir = output_root / "formal_rejection"
            rejection_dir.mkdir()
            refusal_plant = tp01.make_plant(
                case,
                tp01.build_scene(case, rejection_dir / "scene.xml"),
                rejection_dir,
                budget=EPISODE_CAP_S,
            )
            refusal_state = tp01.step_state(
                refusal_plant, case, tp01.visibility_perception(refusal_plant, case)
            )
            candidate_decision = router.decide(
                case.task,
                view,
                admission="formal",
                predicate_state=refusal_state,
            )
            preflight_data["formal_rejection"] = candidate_decision.route is Route.REFUSE
            write_json(
                output_root / "formal_rejection" / "decision.json",
                {
                    "route": candidate_decision.route.value,
                    "reason": candidate_decision.reason,
                },
            )

            # The successful episode's exact program is the script arm.
            script_dir = output_root / "repair" / "script"
            script_row = rerun_success_program(case, view, success_row, script_dir)
            script_requests = action_requests(script_dir)
            practice_requests = action_requests(ROOT / success_row["episode"])
            script_matches_practice = script_requests == practice_requests
            budget.add_episode(script_row.get("simulation_seconds") or 0.0)

            graph = {
                "skills": [
                    {
                        "id": bundle["skill"].id,
                        "steps": [step.to_dict() for step in bundle["skill"].steps],
                        "pre": [item.to_dict() for item in bundle["skill"].pre],
                        "post": [item.to_dict() for item in bundle["skill"].post],
                    }
                ],
                "edges": router.skill_graph(view, "practice"),
            }
            compose_prompt = agent.compose_prompt(public, graph, sample)
            compose_payload, _ = call_with_schema(
                gateway,
                budget,
                kind="repair_compose",
                directory=output_root / "agent" / "compose",
                prompt=compose_prompt,
                parse=agent.validate_compose,
                retry_builder=lambda error: agent.compose_prompt(
                    public, {**graph, "schema_error": error}, sample
                ),
            )
            write_json(output_root / "agent" / "compose" / "payload.json", compose_payload)
            composed = compose_program(compose_payload, view, case, bundle["skill"])
            agent_dir = output_root / "repair" / "agent"
            agent_row = run_episode(
                case, view, "practice", agent_dir, program=composed, decide=False
            )
            agent_requests = action_requests(agent_dir)
            sequences_match = agent_requests == script_requests
            budget.add_episode(agent_row.get("simulation_seconds") or 0.0)
            write_json(
                output_root / "repair" / "index.json",
                {
                    "script": script_row,
                    "agent": agent_row,
                    "script_matches_practice": script_matches_practice,
                    "agent_matches_script": sequences_match,
                },
            )

            if not script_row["verified_task_success"]:
                raise StopRun("REPAIR_SCRIPT_FAILED")
            if not agent_row["verified_task_success"] or not sequences_match:
                raise StopRun("REPAIR_AGENT_FAILED")

            # Promote every op used by the successful chain and the Skill.
            evidence_paths = (
                relative(B1_EPISODE),
                relative(output_root / "diagnosis.json"),
                relative(ROOT / success_row["episode"]),
                relative(script_dir),
                relative(agent_dir),
                relative(AUDIT_RUN / "results.json"),
                relative(B2_RUN / "results.json"),
                relative(F0_RUN / "results.json"),
            )
            metrics = (
                ("terminal_stable_s", float(script_row["terminal_stable_s"])),
                ("simulation_seconds", float(script_row["simulation_seconds"])),
            )
            regression_evidence = {
                "audit": preflight_data["audit"],
                "b2": {"verified_task_success": False},
                "f0": preflight_data["f0"],
                "reference": {"passed": True},
                "test_split": {"untouched": _test_split_untouched()},
            }
            report_refs: dict[str, str] = {}
            for candidate in (*bundle["ops"], bundle["skill"]):
                report = validation.build_report(
                    report_id=f"report_{candidate.op_id if isinstance(candidate, Op) else candidate.id}",
                    candidate_id=candidate.op_id
                    if isinstance(candidate, Op)
                    else candidate.id,
                    candidate_digest=candidate.digest(),
                    validation=Validation.REPAIR_LINEAGE,
                    protocol=(
                        "P2 repair_lineage: B1 failure preserved; practice success; "
                        "same saved initial state script and Agent re-verify"
                    ),
                    baseline_episode=relative(B1_EPISODE),
                    treatment_episode=relative(script_dir),
                    initial_state_sha256=case.initial_state_sha256,
                    metrics=metrics,
                    ops=(candidate,) if isinstance(candidate, Op) else bundle["ops"],
                    evidence=regression_evidence,
                    decision="promote",
                    evidence_paths=evidence_paths,
                )
                reports.append(report)
                report_refs[report.id] = store.put(report)
            refs = dict(store.load(snapshot_id).snapshot.refs)
            refs.update(report_refs)
            report_snapshot = store.commit(
                list(refs.items()), label="p2:validation_reports", parent=snapshot_id
            )
            snapshot_id = report_snapshot.id
            for candidate in (*bundle["ops"], bundle["skill"]):
                candidate_id = (
                    candidate.op_id if isinstance(candidate, Op) else candidate.id
                )
                snapshot_id = store.promote(
                    snapshot_id, candidate_id, f"report_{candidate_id}"
                ).id
            frozen = store.freeze(snapshot_id)
            head = store.head()
            verify = store.verify(frozen.id)
            promotion = {
                "snapshot_id": snapshot_id,
                "frozen_snapshot_id": frozen.id,
                "head_id": head.id if head else None,
                "head_frozen": bool(head and head.frozen),
                "verify_ok": bool(verify.get("ok")),
                "skill_id": bundle["skill"].id,
                "op_ids": sorted(op.op_id for op in bundle["ops"]),
                "reports": [report.id for report in reports],
            }
            write_json(output_root / "validation" / "index.json", promotion)
            for report in reports:
                write_json(
                    output_root / "validation" / f"{report.id}.json", report.to_dict()
                )
            if not promotion["head_frozen"] or not promotion["verify_ok"]:
                raise StopRun("PROMOTION_SNAPSHOT_INVALID")

            formal_view = store.load(frozen.id)
            formal_dir = output_root / "formal" / "T"
            formal_dir.mkdir(parents=True, exist_ok=False)
            formal_model = tp01.build_scene(case, formal_dir / "scene.xml")
            formal_plant = tp01.make_plant(case, formal_model, formal_dir, budget=EPISODE_CAP_S)
            formal_state = tp01.step_state(
                formal_plant, case, tp01.visibility_perception(formal_plant, case)
            )
            decision = router.decide(
                case.task,
                formal_view,
                admission="formal",
                predicate_state=formal_state,
            )
            t_decision = {
                "route": decision.route.value,
                "artifact_id": decision.artifact_id,
                "reason": decision.reason,
                "program_id": decision.program.id if decision.program else None,
                "steps": [step.op_id for step in decision.program.steps]
                if decision.program
                else [],
            }
            write_json(output_root / "formal" / "decision.json", t_decision)
            if decision.route is not Route.FAST or decision.program is None:
                raise StopRun("FORMAL_ROUTE_REFUSED", t_decision)
            # The plant was built for the predicate state; reuse it for the run.
            t_result = runtime.Runtime(formal_plant, case, formal_dir).run(
                decision.program,
                make_runner(formal_view, "formal", case),
                view=formal_view,
                task=case.task,
                initial=ops.TP01_INITIAL,
                admission="formal",
                verify=True,
                strict_posts=True,
            )
            execution = read(formal_dir / "execution.json")
            t_row = {
                "episode": relative(formal_dir),
                "program_id": t_result.program_id,
                "program_sha256": t_result.program_sha256,
                "program_steps": [step.op_id for step in decision.program.steps],
                "initial_state_sha256": case.initial_state_sha256,
                "plant_initial_state_sha256": t_result.initial_state_sha256,
                "failure_code": t_result.failure_code,
                "replans": t_result.replans,
                "verified_task_success": bool(
                    t_result.verdict and t_result.verdict.verified_task_success
                ),
                "goal_satisfied": bool(t_result.verdict and t_result.verdict.goal_satisfied),
                "terminal_stable_s": float(t_result.verdict.terminal_stable_s)
                if t_result.verdict
                else 0.0,
                "simulation_seconds": execution["simulation_seconds"],
                "guard": execution.get("guard"),
                "promoted_ops_used": all(
                    step.op_id in {op.op_id for op in bundle["ops"]}
                    or step.op_id in ("open_hand", "check")
                    for step in decision.program.steps
                )
                and all(
                    read(formal_dir / "op_table.json").get(op_id, {}).get("status")
                    == Status.VALIDATED.value
                    for op_id in SMALL_OP_IDS
                ),
            }
            budget.add_episode(t_row["simulation_seconds"])
            write_json(output_root / "formal" / "T" / "result.json", t_row)

            b1_metrics = {
                "verified_task_success": False,
                "retries": 0,
                "stable_s": 0.0,
                "initial_state_sha256": preflight_data["b1"]["initial_state_sha256"],
            }
            pairing = validation.paired(b1_metrics, metrics_of(t_row))
            pairing["same_initial_state"] = (
                b1_metrics["initial_state_sha256"] == case.initial_state_sha256
            )
            write_json(output_root / "formal" / "pairing.json", pairing)

            peer_cup, scope_checks = scope_checks_run(
                case, formal_view, output_root / "scope"
            )
            evaluator_recomputes = (
                replay_matches(case, ROOT / success_row["episode"])
                and replay_matches(case, formal_dir)
            )
            checks, notes = build_checks(
                preflight=preflight_data,
                practice_rows=practice_rows,
                success_row=success_row,
                script_row=script_row,
                agent_row=agent_row,
                sequences_match=sequences_match,
                reports=reports,
                promotion=promotion,
                t_row=t_row,
                t_decision=t_decision,
                pairing=pairing,
                evaluator_recomputes=evaluator_recomputes,
                hashes_ok=rows_hash_ok(
                    *practice_rows, script_row, agent_row, t_row, peer_cup
                ),
                test_split=_test_split_untouched(),
                unit_tests_ok=bool(preflight_data["summary"]["unit_tests"]["ok"]),
            )
            status = (
                "P2_REPAIR_LINEAGE_SKILL_PROMOTED_FORMAL_REUSE_PASSED"
                if all(checks.values())
                else "P2_COMPLETED_WITH_FAILED_CHECKS"
            )
            write_results(
                output_root,
                args,
                started_at,
                status,
                budget,
                preflight_data,
                practice_rows,
                success_row,
                script_row,
                agent_row,
                sequences_match,
                reports,
                promotion,
                t_row,
                t_decision,
                pairing,
                peer_cup,
                scope_checks,
                evaluator_recomputes,
                checks,
                notes,
                gateway_info,
                failure_reason,
            )
            return 0 if all(checks.values()) else 1
    except StopRun as error:
        failure_reason = {"reason": error.reason, "detail": error.detail}
        status = error.reason
        checks, notes = build_checks(
            preflight=preflight_data or {"summary": {"checks": {}}},
            practice_rows=practice_rows,
            success_row=success_row,
            script_row=script_row,
            agent_row=agent_row,
            sequences_match=sequences_match,
            reports=reports,
            promotion=promotion,
            t_row=t_row,
            t_decision=t_decision,
            pairing=pairing,
            evaluator_recomputes=evaluator_recomputes,
            hashes_ok=rows_hash_ok(
                *practice_rows, script_row, agent_row, t_row, peer_cup
            ),
            test_split=_test_split_untouched(),
            unit_tests_ok=bool(
                (preflight_data or {}).get("summary", {}).get("unit_tests", {}).get("ok")
            ),
        ) if preflight_data else (
            dict.fromkeys(CHECK_KEYS, False),
            {"stop": "before preflight"},
        )
        write_results(
            output_root,
            args,
            started_at,
            status,
            budget,
            preflight_data,
            practice_rows,
            success_row,
            script_row,
            agent_row,
            sequences_match,
            reports,
            promotion,
            t_row,
            t_decision,
            pairing,
            peer_cup,
            scope_checks,
            evaluator_recomputes,
            checks,
            notes,
            gateway_info,
            failure_reason,
        )
        print("P2_STOPPED", json.dumps(failure_reason, ensure_ascii=False), flush=True)
        return 1


def rerun_success_program(case, view, success_row, output: Path) -> dict:
    """Run the exact successful program again through a fresh plant."""
    program_payload = read(ROOT / success_row["episode"] / "program.json")
    program = TaskProgram.from_dict(program_payload)
    return run_episode(case, view, "practice", output, program=program, decide=False)


def scope_checks_run(case: tp01.TP01Case, formal_view, root: Path) -> tuple[dict, dict]:
    root.mkdir(parents=True, exist_ok=False)
    cases = {item.instance_id: item for item in tp01.load_cases()}
    if "TP01_reach_train_003" not in cases:
        raise StopRun("PEER_CUP_MISSING")
    peer = dataclasses.replace(
        cases["TP01_reach_train_003"],
        task=dataclasses.replace(cases["TP01_reach_train_003"].task, budget_s=PROGRAM_BUDGET_S),
    )
    peer_dir = root / "peer_cup"
    peer_row = run_episode(peer, formal_view, "formal", peer_dir)
    checks = {
        "peer_cup": {
            "instance": peer.instance_id,
            "attempted": True,
            "verified_task_success": peer_row["verified_task_success"],
            "failure_code": peer_row.get("failure_code"),
        }
    }
    for instance in ("TP01_reach_train_001", "TP01_reach_train_002"):
        if instance not in cases:
            raise StopRun("SCOPE_CASE_MISSING", {"instance": instance})
        other = dataclasses.replace(
            cases[instance],
            task=dataclasses.replace(cases[instance].task, budget_s=PROGRAM_BUDGET_S),
        )
        check_dir = root / instance
        check_dir.mkdir()
        model = tp01.build_scene(other, check_dir / "scene.xml")
        plant = tp01.make_plant(other, model, check_dir, budget=EPISODE_CAP_S)
        state = tp01.step_state(plant, other, tp01.visibility_perception(plant, other))
        decision = router.decide(
            other.task, formal_view, admission="formal", predicate_state=state
        )
        checks[instance] = {
            "target_category": other.target_category,
            "refused": decision.route is Route.REFUSE,
            "reason": decision.reason,
        }
    write_json(root / "scope.json", checks)
    return peer_row, checks


def write_results(
    output_root: Path,
    args,
    started_at: str,
    status: str,
    budget: CallBudget,
    preflight,
    practice_rows,
    success_row,
    script_row,
    agent_row,
    sequences_match,
    reports,
    promotion,
    t_row,
    t_decision,
    pairing,
    peer_cup,
    scope_checks,
    evaluator_recomputes,
    checks,
    notes,
    gateway_info,
    failure_reason,
) -> None:
    summary = {
        "date": DATE,
        "boundary": "simulation",
        "kind": "p2_agent_run",
        "run_id": args.run_id,
        "status": status,
        "smoke": args.max_practice < MAX_PRACTICE,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counted_as_agent_success": status
        == "P2_REPAIR_LINEAGE_SKILL_PROMOTED_FORMAL_REUSE_PASSED",
        "gateway": gateway_info,
        "budget": budget.summary(),
        "preflight": preflight["summary"] if preflight else None,
        "diagnosis": read(output_root / "diagnosis.json")
        if (output_root / "diagnosis.json").is_file()
        else None,
        "practice": {
            "episodes": practice_rows,
            "count": len(practice_rows),
            "success_episode": success_row,
        },
        "repair": {
            "script": script_row,
            "agent": agent_row,
            "agent_matches_script": sequences_match,
        },
        "validation_reports": [report.to_dict() for report in reports],
        "promotion": promotion,
        "formal_t": t_row,
        "formal_decision": t_decision,
        "fallback_pairing": pairing,
        "peer_cup": peer_cup,
        "scope_checks": scope_checks,
        "evaluator_recomputes_from_saved_state": evaluator_recomputes,
        "checks": checks,
        "notes": notes,
        "failure": failure_reason,
        "artifact_paths": {
            "registry": relative(output_root / "registry"),
            "calls": relative(output_root / "calls.jsonl"),
            "preflight": relative(output_root / "preflight.json"),
            "observation_sample": relative(output_root / "observation_sample.json"),
            "practice_index": relative(output_root / "practice" / "index.json")
            if (output_root / "practice" / "index.json").is_file()
            else None,
        },
    }
    write_json(output_root / "results.json", summary)
    evidence.write_hashes(output_root)
    print(
        "P2_SUMMARY",
        json.dumps(
            {
                "status": status,
                "checks": len(checks),
                "true": sum(1 for value in checks.values() if value),
                "practice": len(practice_rows),
                "tokens": budget.token_total,
                "calls": len(budget.records),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
