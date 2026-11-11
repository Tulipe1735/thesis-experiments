"""Generated-task accumulation loop: route, propose, gate, execute, judge, diagnose, store.

Success is decided only by ``local_reach.evaluate`` replaying the saved
trajectory. Models propose code (proposer) and explain failures (critic); a
critic label is compared with the evaluator-derived label, never used as a
verdict. Library entries stay ``candidate``; this loop does not promote.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from . import local_reach, local_reach_v3, tp01
from .agent import AgentSchemaError, check_source
from .llm import Client, LLMError
from .task_generator import ARM_JOINTS, SOURCE
from experiments.cordis_t01.worker import SavedInitialRobot
from experiments.grow_up_v2.isolation.worker import Worker, WorkerError

ROOT = tp01.ROOT
SETTLE_S = .75
FAILURE_CLASSES = ("INTERFACE", "WORKER_ERROR", "BUDGET", "UNSAFE", "NOT_REACHED",
                   "ORIENTATION", "NOT_HELD")


def write_new(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=1, allow_nan=False)
        handle.write("\n")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def body_geometry(robot) -> dict:
    """Robot-only kinematic chain, pelvis to left palm; no object or scene truth."""
    model = robot.model
    body = int(model.site_bodyid[model.site("left_palm").id])
    chain = []
    public = robot.state()["joints"]
    while body != robot.pelvis_id:
        joints = []
        for j in range(model.body_jntadr[body], model.body_jntadr[body] + model.body_jntnum[body]):
            name = model.joint(j).name
            joints.append({"name": name, "axis": model.jnt_axis[j].tolist(),
                           "pos": model.jnt_pos[j].tolist(), "range": model.jnt_range[j].tolist(),
                           "type": int(model.jnt_type[j]), "initial_q": public[name]["q"]})
        chain.append({"name": model.body(body).name, "pos": model.body_pos[body].tolist(),
                      "quaternion_wxyz": model.body_quat[body].tolist(), "joints": joints})
        body = int(model.body_parentid[body])
    site = model.site("left_palm").id
    return {"chain_from_pelvis": list(reversed(chain)),
            "palm_site": {"pos": model.site_pos[site].tolist(),
                          "quaternion_wxyz": model.site_quat[site].tolist()}}


def check_action(action, observation: dict) -> dict:
    """The action rules of ``tp01.t01_joint_dispatch`` without a robot; raises ValueError."""
    if not isinstance(action, dict) or "op" not in action:
        raise ValueError("ACTION_SCHEMA: action must be an object with key op")
    expected = {"set_joints": {"op", "targets", "duration"}, "wait": {"op", "duration"},
                "done": {"op"}, "fail": {"op", "reason"}}
    op = action["op"]
    if op not in expected or set(action) != expected[op]:
        raise ValueError(f"ACTION_SCHEMA: op {op!r} with keys {sorted(action)}; "
                         f"allowed {{op: keys}} = { {k: sorted(v) for k, v in expected.items()} }")
    if op in ("done", "fail"):
        return action
    duration = action["duration"]
    if (type(duration) not in (int, float) or not math.isfinite(duration)
            or not .02 <= duration <= .2 or abs(duration / .002 - round(duration / .002)) > 1e-6):
        raise ValueError(f"duration {duration!r} must be 0.02-0.20 s on the 0.002 s grid")
    if op == "wait":
        return action
    targets = action["targets"]
    if not isinstance(targets, dict) or not 1 <= len(targets) <= 14:
        raise ValueError("targets must map 1-14 left arm/hand joint names to numbers")
    joints = observation["joints"]
    for name, value in targets.items():
        if name not in joints or type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"invalid left joint target {name!r}={value!r}")
        hand = "_hand_" in name
        delta = abs(value - joints[name]["target"])
        if delta > (.05 if hand else .03) + 1e-8:
            raise ValueError(f"LOCAL_JOINT_DELTA: {name} moves {delta:.4f} rad from its current target")
        if 1.5 * delta / duration > (.5 if hand else .3) + 1e-8:
            raise ValueError(f"LOCAL_JOINT_SPEED: {name} 1.5*{delta:.4f}/{duration} exceeds limit")
    return action


def dry_run(source: str, geometry: dict, contract: dict, observation: dict, steps: int) -> dict:
    """Interface gate before physics: AST whitelist, Worker start, ``steps`` act calls."""
    calls, security = 0, {}
    try:
        check_source(source)
        with Worker(source, geometry, cpu_seconds=30, wall_timeout=2.) as worker:
            security = worker.security
            for _ in range(steps):
                calls += 1
                action = check_action(worker.act(observation, contract)["action"], observation)
                if action["op"] in ("done", "fail"):
                    break
    except (AgentSchemaError, WorkerError, ValueError, KeyError, TypeError) as error:
        return {"passed": False, "error": f"{type(error).__name__}: {error}", 'worker_calls': calls, 'security': security}
    return {"passed": True, 'worker_calls': calls, 'security': security}


class Episode:
    """One physical episode on the saved initial; caps are per episode."""

    def __init__(self, output: Path, plan: dict, caps: dict):
        self.output, self.plan, self.caps = output, plan, caps

    def run(self, contract: dict, *, mode: str, source: str | None = None,
            sampled_q: dict | None = None, task_input: dict | None = None) -> dict:
        """``contract`` is judged by the evaluator; the policy's act sees only ``task_input``."""
        output = self.output
        output.mkdir(parents=True, exist_ok=False)
        episode = output / "episode"
        episode.mkdir()
        write_new(episode / "instance.json", self.plan["instance"])
        version = self.plan.get("evaluator_version", "explicit-pose-replay-v2")
        if version not in ("explicit-pose-replay-v2", local_reach_v3.VERSION):
            raise ValueError(f"unknown evaluator {version}")
        robot_type = tp01.TickRecordedRobot if version == local_reach_v3.VERSION else SavedInitialRobot
        robot = robot_type(episode, self.plan["instance"], budget=SETTLE_S + self.caps["simulation_s"],
                                  scene_path=ROOT / self.plan["plant"]["path"],
                                  initial_state=SOURCE / "initial_state.npz")
        wall = time.monotonic()
        counts = {"commands": 0, "worker_calls": 0}
        error = None
        actions = (output / "actions.jsonl").open("x", encoding="utf-8")
        deadline = SETTLE_S + self.caps["simulation_s"]

        def dispatch(action):
            if time.monotonic() - wall > self.caps["wall_s"]:
                raise ValueError("LOCAL_WALL_CAP")
            if counts["commands"] >= self.caps["commands"]:
                raise ValueError("LOCAL_COMMAND_CAP")
            response = tp01.t01_joint_dispatch(robot, action, deadline=deadline)
            counts["commands"] += 1
            actions.write(json.dumps({"request": action, "status": response["status"]}) + "\n")
            if response["status"] != "EXECUTED" or robot.guard:
                raise ValueError(f"GUARD: {response['status']}")

        worker = None
        try:
            robot.advance(SETTLE_S, "initial_settling")
            write_new(output / "public_initial.json", tp01.t01_joint_observation(robot))
            if mode == "wait":
                for _ in range(int(self.caps["simulation_s"] / .2) - 1):
                    dispatch({"op": "wait", "duration": .2})
            elif mode == "engineering":
                start = {n: float(robot.targets[robot.ai[n]]) for n in ARM_JOINTS}
                steps = max(1, math.ceil(max(abs(sampled_q[n] - start[n]) for n in ARM_JOINTS) / .025))
                for i in range(1, steps + 1):
                    dispatch({"op": "set_joints", "duration": .2, "targets": {
                        n: start[n] + (sampled_q[n] - start[n]) * i / steps for n in ARM_JOINTS}})
                for _ in range(10):
                    dispatch({"op": "wait", "duration": .2})
            elif mode == "worker":
                check_source(source)
                worker = Worker(source, self.plan["body_geometry"], cpu_seconds=30, wall_timeout=2.)
                while True:
                    observation = tp01.t01_joint_observation(robot)
                    counts["worker_calls"] += 1
                    action = check_action(worker.act(observation, task_input)["action"], observation)
                    if action["op"] == "done":
                        break
                    if action["op"] == "fail":
                        raise ValueError("POLICY_FAIL: " + str(action["reason"]))
                    dispatch(action)
            else:
                raise ValueError(mode)
        except (ValueError, KeyError, TypeError, WorkerError, AgentSchemaError) as exc:
            error = {"type": type(exc).__name__, "message": str(exc)[:500]}
        finally:
            if worker is not None:
                worker.close()
            actions.close()
        environment = robot.finish()
        evaluator = local_reach_v3 if version == local_reach_v3.VERSION else local_reach
        verdict = evaluator.evaluate(episode, contract, start_s=SETTLE_S, execution_error=error)
        rows = verdict.pop("rows")
        np.savez_compressed(output / "verdict_rows.npz",
                            time=[r["time"] for r in rows],
                            position_error_m=[r["position_error_m"] for r in rows],
                            orientation_error_rad=[r["orientation_error_rad"] for r in rows],
                            safe=[r["safe"] for r in rows])
        facts = failure_facts(verdict, rows, error, counts, environment)
        write_new(output / "verdict.json", verdict)
        result = {"mode": mode, "success": verdict["verified_local_success"], "error": error,
                  **counts, "simulation_seconds": environment["simulation_seconds"],
                  "wall_seconds": time.monotonic() - wall, "facts": facts,
                  "source_sha256": sha_text(source) if source else None,
                  "evaluator_version": version, "recording_version": getattr(robot, "recording_version", "float-accumulation-v1")}
        write_new(output / "result.json", result)
        return result


def failure_facts(verdict: dict, rows: list, error, counts: dict, environment: dict) -> dict:
    """Evaluator-derived numbers the agent may see after an episode, plus a rule label."""
    errors = [r["position_error_m"] for r in rows]
    angles = [r["orientation_error_rad"] for r in rows]
    unsafe = [r for r in rows if not r["safe"]]
    facts = {
        "execution_error": error, "guard": environment["protection"],
        "commands": counts["commands"], "worker_calls": counts["worker_calls"],
        "final_position_error_m": verdict["final_position_error_m"],
        "min_position_error_m": min(errors) if errors else None,
        "final_orientation_error_rad": verdict["final_orientation_error_rad"],
        "min_orientation_error_rad": min(angles) if angles else None,
        "terminal_hold_s": verdict["terminal_hold_s"], "unsafe_frames": len(unsafe),
        "max_contact_N": max((r["contact_N"] for r in rows), default=None),
        "min_hand_open_fraction": min((r["hand_open_fraction"] for r in rows), default=None),
    }
    facts["rule_label"] = rule_label(verdict, facts)
    return facts


def rule_label(verdict: dict, facts: dict) -> str | None:
    if verdict["verified_local_success"]:
        return None
    message = (facts["execution_error"] or {}).get("message", "")
    if message.startswith(("ACTION_SCHEMA", "LOCAL_JOINT", "duration", "targets", "invalid left")):
        return "INTERFACE"
    if facts["execution_error"] and facts["execution_error"]["type"] in ("WorkerTimeout", "WorkerCrashed",
                                                                         "WorkerProtocolError", "AgentSchemaError", "WorkerError",
                                                                         "WorkerOutputLimit", "WorkerInputLimit", "IsolationError"):
        return "WORKER_ERROR"
    if message.startswith(("LOCAL_BUDGET", "LOCAL_COMMAND", "LOCAL_WALL")) or "BUDGET" in str(facts["guard"]):
        return "BUDGET"
    if facts["unsafe_frames"] or facts["guard"]:
        return "UNSAFE"
    contract_pos = .008
    if facts["final_position_error_m"] is None or facts["final_position_error_m"] > contract_pos:
        return "NOT_REACHED"
    if facts["final_orientation_error_rad"] > .15:
        return "ORIENTATION"
    return "NOT_HELD"


PROPOSER_SYSTEM = """You extend a library of robot skills for a simulated humanoid's LEFT arm.
Reply with ONE JSON object only, in one of two forms:
 new leaf:      {"kind": "leaf", "name": snake_case, "summary": str, "note": str, "parents": [library refs you adapted], "source": str}
 composition:   {"kind": "composite", "name": snake_case, "summary": str, "note": str, "parents": [],
                 "ir": [{"use": library ref, "params": {param: {"task": task_param} | {"literal": value}}}, ...]}
A composite runs the referenced library artifacts in order; each step must bind every parameter the
referenced artifact declares. Use it only when existing artifacts, chained, solve the task.
A leaf's source defines act(observation, task, state) and optionally init(profile). Only `import math` / `import numpy`.
act returns {"action": ACTION, "state": JSON-serializable}. ACTION is exactly one of:
 {"op": "set_joints", "targets": {joint_name: float}, "duration": d}
 {"op": "wait", "duration": d}
 {"op": "done"}
 {"op": "fail", "reason": str}
d in [0.02, 0.20] and a multiple of 0.002. For set_joints each target may differ from observation.joints[name]["target"] by at most 0.03 rad (arm) / 0.05 (hand), and 1.5*delta/d <= 0.30 (arm) / 0.50 (hand).
init(profile) receives the body geometry and returns the initial state (or define no init: state starts as None).
The task argument act receives contains exactly the declared contract params.
"""


def proposer_prompt(task: dict, plan: dict, observation: dict, library: list, history: list,
                    family: dict, skill_graph: dict | None = None) -> str:
    packet = {
        "goal": family.get("goal", "Move the open left palm to task.position_m with orientation task.quaternion_xyzw "
                "(both in the current pelvis frame), hold it within tolerance for task.hold_s, then return done."),
        "task": task,
        "contract_of_new_artifact": family["contract"],
        "task_tree_node": family["task_node"],
        "skill_graph": skill_graph,
        "body_geometry": plan["body_geometry"],
        "geometry_convention": "each body: fixed pos then quaternion_wxyz relative to parent; a hinge joint rotates "
                               "about its axis through joint pos in the body frame; palm_site pose is in the last body. "
                               "Commanded joints track targets; joints you do not command keep their target.",
        "observation_example": observation,
        "observation_notes": family.get("observation_notes", "observation.left_palm gives the measured palm pose; joints[name] has q, dq, target. "
                             "Read actual q after each motion; the hand must stay open (do not command hand joints)."),
        "budget": {k: plan["caps"][k] for k in ("simulation_s", "commands")},
        "library": library,
        "library_note": "Each entry: ref, skill card (contract, task-tree node, independent evidence) and, for leaves, "
                        "the exact code. Adapt leaves (list them in parents) or compose them by ref.",
        "previous_attempts_on_this_task": history,
    }
    return json.dumps(packet, ensure_ascii=False)


CRITIC_SYSTEM = """You diagnose why a robot reach-and-hold attempt failed. Reply with ONE JSON object:
{"failure_class": one of %s, "explanation": str, "advice": str}.
Use only the facts given. advice is one or two concrete code changes for the next attempt.""" % list(FAILURE_CLASSES)


def critic_prompt(task: dict, facts: dict, last_actions: list, source: str) -> str:
    shown = {k: v for k, v in facts.items() if k != "rule_label"}
    return json.dumps({"task": task, "facts": shown, "last_actions": last_actions,
                       "source": source}, ensure_ascii=False)


def last_actions(output: Path, n: int = 6) -> list:
    path = output / "actions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()[-n:]]
