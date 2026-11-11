"""Registered local accumulation pilot; each phase refuses stale inputs/outputs.

Run controls first, then candidates, then paired validation. All simulation
uses the common bounded joint adapter; candidate code runs in the existing
seccomp Worker. This pilot is one known initial, not a method comparison.
"""

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

import mujoco
import numpy as np

from harness import artifact, codex_decision, local_reach, tp01
from harness.agent import check_source
from harness.contracts import CodeModule, Op, Predicate, Scope, Skill, Status, Step, Validation, ValidationReport
from harness.registry import Registry
from experiments.cordis_t01.worker import SavedInitialRobot
from experiments.grow_up_v2.isolation.worker import Worker
from experiments.t0_agent_v1.common import REFERENCE, read, relative, sha, write_new
from experiments.t0_agent_v1.tray_verify import verify

SOURCE = ROOT / "experiments/t0_agent_v1/tray_astra_20261025_002/episodes/2500_T01_astra"
ENGINEERING = ROOT / "experiments/grow_up_harness_v2/runs/t01_program_check_20261105_017/episode"
PARENT = ROOT / "experiments/grow_up_harness_v2/runs/local_artifact_cycle_20261106_002"
CONTROL_PARENT = ROOT / "experiments/grow_up_harness_v2/runs/local_artifact_cycle_20261106_003"
MODEL = "gpt-6.1-terra"
SCHEMA = {"type": "object", "properties": {"note": {"type": "string"},
          "source": {"type": "string"}, "mode": {"type": "string", "enum": ["code", "skill"]}},
          "required": ["note", "source", "mode"], "additionalProperties": False}


def local_action(result):
    """Enforce the documented wire format; never translate a malformed reply."""
    if not isinstance(result, dict) or not isinstance(result.get("action"), dict):
        raise ValueError("ACTION_SCHEMA: result.action must be an object")
    action = result["action"]
    if "op" not in action:
        raise ValueError("ACTION_SCHEMA: expected action.op; received keys " + repr(sorted(action)))
    op = action["op"]
    expected = {"set_joints": {"op", "targets", "duration"}, "wait": {"op", "duration"},
                "done": {"op"}, "fail": {"op", "reason"}}
    if op not in expected or set(action) != expected[op]:
        raise ValueError("ACTION_SCHEMA: unsupported operation or fields")
    return action


def geometry(robot):
    """Known robot-only geometry, never object or scene truth."""
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


def integration_hash(robot):
    state = np.empty(mujoco.mj_stateSize(robot.model, mujoco.mjtState.mjSTATE_INTEGRATION))
    mujoco.mj_getState(robot.model, robot.data, state, mujoco.mjtState.mjSTATE_INTEGRATION)
    return hashlib.sha256(state.tobytes() + robot.targets.tobytes()).hexdigest()


def new_robot(output, registration):
    output.mkdir(parents=True, exist_ok=False)
    episode = output / "episode"
    episode.mkdir()
    write_new(episode / "instance.json", registration["instance"])
    robot = SavedInitialRobot(episode, registration["instance"], budget=30.,
                              scene_path=ROOT / registration["plant"]["path"],
                              initial_state=ROOT / registration["initial_state"]["path"])
    with np.load(SOURCE / "initial_state.npz", allow_pickle=False) as old, \
         np.load(episode / "initial_state.npz", allow_pickle=False) as new:
        exact = set(old.files) == set(new.files) and all(np.array_equal(old[k], new[k]) for k in old.files)
    write_new(output / "initial_state_audit.json", {"all_arrays_exactly_equal": exact,
              "integration_and_targets_sha256": integration_hash(robot)})
    if not exact:
        raise ValueError("actual initial differs from registered saved state")
    return robot


def engineering_actions(robot, records):
    for record in records:
        desired = record["joints"]
        start = {name: float(robot.targets[robot.ai[name]]) for name in desired}
        count = max(1, math.ceil(max(abs(desired[n] - start[n]) for n in desired) / .025))
        for i in range(1, count + 1):
            yield {"op": "set_joints", "targets": {n: start[n] + (desired[n] - start[n]) * i / count
                    for n in desired}, "duration": .2}
    for _ in range(7):
        yield {"op": "wait", "duration": .2}


def execute(root, name, registration, *, source=None, engineering=None, wait=False,
            reuse=None, continuation=False):
    output = root / name
    robot = new_robot(output, registration)
    wall = time.monotonic()
    commands = calls = 0
    error = None
    worker = None
    security = None
    handoff = None
    records = read(ENGINEERING / "physics_events.json")
    actions = [r for r in records if r["category"] == "action"]
    start_hash = integration_hash(robot)
    robot.advance(.75, "initial_settling")
    write_new(output / "public_initial.json", tp01.t01_joint_observation(robot))
    log = (output / "actions.jsonl").open("x", encoding="utf-8")
    observations = (output / "observations.jsonl").open("x", encoding="utf-8")
    replies = (output / "worker_replies.jsonl").open("x", encoding="utf-8")

    def dispatch(action):
        nonlocal commands
        if time.monotonic() - wall > 120:
            raise ValueError("LOCAL_WALL_CAP")
        if commands >= 200:
            raise ValueError("LOCAL_COMMAND_CAP")
        before = tp01.t01_joint_observation(robot)
        observations.write(json.dumps(before) + "\n")
        observations.flush()
        response = tp01.t01_joint_dispatch(robot, action, deadline=30.)
        commands += 1
        log.write(json.dumps({"request": action, "response": response}) + "\n")
        log.flush()
        if response["status"] != "EXECUTED" or robot.guard:
            raise ValueError(response["status"])

    try:
        if wait:
            for _ in range(140):
                dispatch({"op": "wait", "duration": .2})
        elif engineering is not None:
            for action in engineering_actions(robot, actions[:6]):
                dispatch(action)
        else:
            check_source(source)
            worker = Worker(source, registration["body_geometry"], cpu_seconds=30, wall_timeout=2.)
            security = worker.security
            while True:
                if time.monotonic() - wall > 120:
                    raise ValueError("LOCAL_WALL_CAP")
                observation = tp01.t01_joint_observation(robot)
                observations.write(json.dumps(observation) + "\n")
                observations.flush()
                calls += 1
                replies.write(json.dumps({"attempt": calls, "event": "call_started"}) + "\n")
                replies.flush()
                result = worker.act(observation, registration["local_contract"])
                replies.write(json.dumps({"attempt": calls, "event": "returned", "result": result}) + "\n")
                replies.flush()
                action = local_action(result)
                if action["op"] == "done":
                    break
                if action["op"] == "fail":
                    raise ValueError(action["reason"])
                dispatch(action)
            worker.close()
            worker = None
        if continuation:
            before = integration_hash(robot)
            handoff = {"A_end_s": float(robot.data.time), "A_final_hash": before,
                       "B_initial_hash": integration_hash(robot), "reset_calls": 0,
                       "A_public_terminal": tp01.t01_joint_observation(robot),
                       "B_public_initial": tp01.t01_joint_observation(robot),
                       "B_provenance": "given engineering base; recorded second clear leg",
                       "object_binding": registration["object_binding"]}
            for action in engineering_actions(robot, actions[6:13]):
                dispatch(action)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if worker is not None:
            worker.close()
        log.close()
        observations.close()
        replies.close()
    terminal_hash = integration_hash(robot)
    environment = robot.finish()
    local = local_reach.evaluate(output / "episode", registration["local_contract"],
                                end_s=handoff["A_end_s"] if handoff else None,
                                execution_error=error if not handoff else None)
    write_new(output / "local_verdict.json", local)
    official = verify(output / "episode", execution_error=error)
    if handoff:
        next_contract = dict(registration["local_contract"], position_m=[-.04, .34, .30],
                             quaternion_xyzw=[0., 0., 0., 1.])
        next_verdict = local_reach.evaluate(output / "episode", next_contract,
                                          start_s=handoff["A_end_s"], execution_error=error)
        handoff["B_local_success"] = next_verdict["verified_local_success"]
        handoff["connection_passed"] = bool(local["verified_local_success"]
                                            and next_verdict["verified_local_success"]
                                            and handoff["A_final_hash"] == handoff["B_initial_hash"])
        write_new(output / "continuation_verdict.json", next_verdict)
        write_new(output / "handoff.json", handoff)
    result = {"name": name, "local_success": local["verified_local_success"],
              "full_task_success": official["verified_success"], "error": error,
              "commands": commands, "worker_calls": calls, "worker_security": security,
              "simulation_seconds": environment["simulation_seconds"],
              "wall_seconds": time.monotonic() - wall, "initial_hash": start_hash,
              "final_hash": terminal_hash, "first_stable_s": local["first_stable_s"],
              "final_position_error_m": local["final_position_error_m"],
              "reuse": reuse, "handoff": handoff, "episode": relative(output / "episode")}
    write_new(output / "result.json", result)
    print(json.dumps({k: result[k] for k in ("name", "local_success", "commands", "simulation_seconds", "error")}), flush=True)
    return result


def controls(root):
    root.mkdir(parents=True, exist_ok=False)
    plant = read(SOURCE / "model_reference.json")
    instance = read(SOURCE / "instance.json")
    # Read saved state and geometry without a physical step, before registration.
    model = mujoco.MjModel.from_binary_path(str(ROOT / plant["path"]))
    data = mujoco.MjData(model)
    with np.load(SOURCE / "initial_state.npz", allow_pickle=False) as saved:
        mujoco.mj_setState(model, data, saved["mujoco_integration_state"], mujoco.mjtState.mjSTATE_INTEGRATION)
        mujoco.mj_forward(model, data)
    pelvis = model.body("pelvis").id
    site = model.site("left_palm").id
    quat = np.empty(4)
    mujoco.mju_mat2Quat(quat, (data.xmat[pelvis].reshape(3, 3).T @ data.site_xmat[site].reshape(3, 3)).ravel())
    class StaticBody:
        def state(self):
            return {"joints": {model.joint(j).name: {"q": float(data.qpos[model.jnt_qposadr[j]])}
                               for j in range(model.njnt) if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE}}
    body = StaticBody()
    body.model, body.pelvis_id = model, pelvis
    paths = [Path(__file__), Path(tp01.__file__), Path(local_reach.__file__),
             Path(artifact.__file__), ROOT / "grasp_optimization/pantry_robot.py",
             ROOT / "experiments/grow_up_harness_v2/harness/contracts.py",
             ROOT / "experiments/grow_up_harness_v2/harness/registry.py",
             Path(codex_decision.__file__), ROOT / "experiments/t0_agent_v1/common.py",
             ROOT / "experiments/cordis_t01/worker.py",
             ROOT / "grasp_optimization/assets/robot_profile.json",
             ROOT / "grasp_optimization/reports/dependencies.json",
             REFERENCE / "runtime_context.json", REFERENCE / "initial_state.npz", REFERENCE / "model.mjb",
             ROOT / "experiments/t0_agent_v1/runtime.py", ROOT / "experiments/t0_agent_v1/tray_verify.py",
             ROOT / "experiments/grow_up_v2/isolation/worker.py",
             ROOT / "experiments/grow_up_v2/isolation/_entry.py",
             ENGINEERING / "physics_events.json", ROOT / plant["path"], SOURCE / "initial_state.npz",
             PARENT / "author_v1/answer.json", PARENT / "author_v1/metadata.json"]
    contract = {"effect": "empty_hand_clearance_reach_hold", "frame": "current_pelvis",
                "position_m": [-.07, .34, .09], "quaternion_xyzw": quat[[1, 2, 3, 0]].tolist(),
                "position_tolerance_m": .008, "orientation_tolerance_rad": .15, "hold_s": 1.,
                "contact_max_N": .1, "hand_open_min": .95, "object_displacement_max_m": .005,
                "preconditions": ["known_saved_initial", "hand_empty", "hand_open", "guard_clear"],
                "failure_exits": ["POSE_NOT_REACHED", "CONTACT_OR_DISPLACEMENT", "GUARD_TRIGGERED",
                                  "LOCAL_BUDGET_EXCEEDED", "LOCAL_JOINT_DELTA", "LOCAL_JOINT_SPEED",
                                  "LOCAL_COMMAND_CAP", "LOCAL_WALL_CAP", "POLICY_OR_WORKER_ERROR"]}
    registration = {
        "date": "2026-11-06", "status": "registered_before_physics", "boundary": "simulation",
        "model": MODEL, "instance": instance, "plant": {"path": plant["path"], "sha256": sha(ROOT / plant["path"])},
        "environment": {"python": sys.version, "numpy": np.__version__, "mujoco": mujoco.__version__},
        "control_evidence_root": relative(root),
        "parent_lineage": {"run": relative(PARENT), "reason": "schema wiring repair before candidate execution",
                           "inherited_candidate": relative(PARENT / "author_v1/answer.json"),
                           "prior_model_requests": 1, "prior_physical_episodes": 2,
                           "all_lineage_model_requests_max": 4, "all_lineage_physical_episodes_max": 9,
                           "no_candidate_source_change": True, "local_thresholds_unchanged": True},
        "initial_state": {"path": relative(SOURCE / "initial_state.npz"), "sha256": sha(SOURCE / "initial_state.npz")},
        "sample_units": {"independent_initials": 1, "known_consumed_seed": instance["seed"],
                         "purpose": "mechanism pilot on known engineering initial; no success-rate inference",
                         "resampling": False, "random_object_sampling": False},
        "local_contract": contract, "body_geometry": geometry(body),
        "object_binding": {"hand": "left_palm", "target_pose": "clearance_pose_A",
                           "protected_object": "task_cup", "asset": "DH_2F_mug_06"},
        "budget": {"simulation_s_per_episode": 30., "commands_per_episode": 200,
                   "worker_calls_per_episode": 201, "worker_cpu_s": 30, "worker_act_wall_s": 2.,
                   "episode_wall_s": 120., "author_timeout_s": 120., "model_requests_max": 3,
                   "candidate_versions_max": 2, "revisions_max": 1, "locked_submissions_max": 1,
                   "physical_episodes_max": 7, "reuse_calls_max": 1},
        "design_reason": {"n": "minimum single-initial paired mechanism evidence; no population claim",
                          "position": "8 mm is a local pose tolerance, distinct from unchanged official 1 mm tray margin",
                          "orientation": "0.15 rad bounds orientation drift while preserving start orientation",
                          "hold": "1 s matches existing local reach/hold protocol",
                          "budget": "30 s covers the observed 12 s engineering clearance plus bounded hold and corrections; not old 600 s",
                          "revision": "one feedback-driven repair, no seed replacement"},
        "order": ["negative_wait", "positive_engineering", "candidate_v1", "candidate_v2_if_v1_fails",
                  "paired_without", "paired_with", "reuse_then_engineering_continuation_if_admitted"],
        "order_reason": "fixed diagnostic gate, then paired baseline first to avoid candidate exposure; no randomized method claim",
        "baselines": {"original_failure": "_006 whole-task 0/3 context only; not a local clean baseline",
                      "fallback": "none; failures stop without alternate controller",
                      "negative": "wait using same bounded action outlet",
                      "positive": "first six recorded engineering joint moves, resplit through same bounded outlet",
                      "treatment": "terra-authored local code; engineering source inaccessible"},
        "formal_path": "paired; real no-skill agent retains atoms, same model/request/action budgets; two original-speed videos required",
        "selection": "v1 unless failed, then exactly one repair; lock final version before paired runs; no replacement after paired",
        "clock": "decision-capability clock: physics paused during LLM/Worker compute; all decision wall time charged separately",
        "permissions": "LLM receives only supplied JSON in isolated no-tool Codex; Worker seccomp denies filesystem/network; joint output only",
        "prediction": "wait fails and engineering passes; a local candidate may pass; if admitted, exact-version reuse reaches A and engineering B without reset",
        "falsification": "wait passes invalidates batch; engineering fails stops authoring; candidate/pair/connection failure refutes that step",
        "continuation_contract": {"position_m": [-.04, .34, .30], "quaternion_xyzw": [0, 0, 0, 1],
                                  "other_thresholds": "same as local_contract", "source_action_indices": [6, 13],
                                  "provenance": "given engineering B; no autonomous B claim"},
        "coverage_and_comparison": "not_tested; three-flow and method baselines deferred until first loop",
        "dependencies": {relative(p): sha(p) for p in paths},
    }
    write_new(root / "registration.json", registration)
    negative = execute(root, "negative_wait", registration, wait=True)
    positive = execute(root, "positive_engineering", registration, engineering=True)
    write_new(root / "controls.json", {"negative": negative, "positive": positive,
              "passed": not negative["local_success"] and positive["local_success"]})


def inherit_controls(root):
    """Path-only driver repair: reuse exact control evidence, do not rerun it."""
    root.mkdir(parents=True, exist_ok=False)
    registration = read(CONTROL_PARENT / "registration.json")
    previous = read(CONTROL_PARENT / "controls.json")
    allowed_changes = {relative(Path(__file__)), relative(Path(artifact.__file__))}
    unchanged = {path: sha(ROOT / path) == digest for path, digest in registration["dependencies"].items()
                 if path not in allowed_changes}
    if not all(unchanged.values()) or not previous["passed"]:
        raise ValueError("control inheritance requires unchanged physical/evaluation dependencies and passed controls")
    registration["control_evidence_root"] = relative(CONTROL_PARENT)
    registration["parent_lineage"]["additional_controls_run"] = relative(CONTROL_PARENT)
    registration["parent_lineage"]["prior_physical_episodes"] = 4
    registration["parent_lineage"]["all_lineage_physical_episodes_max"] = 9
    registration["parent_lineage"]["path_only_repair"] = {
        "reason": "resolve registry path before relative manifest reference; same candidate source and physical contract",
        "parent_registration_sha256": sha(CONTROL_PARENT / "registration.json"),
        "controls_sha256": sha(CONTROL_PARENT / "controls.json"),
        "unchanged_physical_dependencies": unchanged,
        "changed_nonphysical_files": sorted(allowed_changes)}
    registration["dependencies"] = {path: sha(ROOT / path) for path in registration["dependencies"]}
    registration["dependencies"][relative(CONTROL_PARENT / "controls.json")] = sha(CONTROL_PARENT / "controls.json")
    registration["budget"]["physical_episodes_max"] = 5
    registration["status"] = "registered_before_candidate_execution_with_inherited_controls"
    write_new(root / "registration.json", registration)
    write_new(root / "controls.json", {"negative": previous["negative"], "positive": previous["positive"],
              "passed": True, "source": relative(CONTROL_PARENT / "controls.json"),
              "source_sha256": sha(CONTROL_PARENT / "controls.json"), "new_control_episodes": 0})


def check_registration(root):
    registration = read(root / "registration.json")
    for path, digest in registration["dependencies"].items():
        if sha(ROOT / path) != digest:
            raise ValueError("registered dependency changed: " + path)
    if not read(root / "controls.json")["passed"]:
        raise ValueError("controls failed; authoring forbidden")
    return registration


def prompt(registration, observation, feedback=None, available=None, memories=None):
    packet = {"task": "Reach and hold the public explicit clearance pose with empty open left hand.",
            "contract": registration["local_contract"], "body_geometry": registration["body_geometry"],
            "observation": observation, "feedback": feedback, "available_skill": available,
            "runtime_bindings": {
                "profile_argument_to_init": "body_geometry value itself: chain_from_pelvis and palm_site at top level",
                "task_argument_to_act": "contract value itself: position_m, quaternion_xyzw, tolerances etc at top level; no task.contract or task.body_geometry wrapper",
                "observation_argument_to_act": "observation shown here, updated after every action",
                "state_argument_to_act": "value returned by init(profile), or None if no init; then previous result.state",
                "exact_action_examples": [{"action": {"op": "set_joints", "targets": {"left_elbow_joint": .2}, "duration": .2}, "state": {}},
                                          {"action": {"op": "wait", "duration": .2}, "state": {}},
                                          {"action": {"op": "done"}, "state": {}},
                                          {"action": {"op": "fail", "reason": "POSE_NOT_REACHED"}, "state": {}}]},
            "budget": registration["budget"],
            "rules": ["Return note, source, mode. Write source with act(observation, task, state), optional init(profile).",
                      "Return {action: {...}, state: JSON}. State persists between act calls. init returns initial state.",
                      "Actions are EXACT JSON dictionaries in runtime_bindings.exact_action_examples. The operation key is op, never type; no field aliases are accepted.",
                      "Only 14 left arm/hand joints. No waist, move_ee, IK helper, filesystem, network or evaluator access.",
                      "Every duration 0.02–0.20 s on .002 grid; max target delta .03 arm/.05 hand; smooth velocity 1.5*delta/duration <= .30 arm/.50 hand rad/s. Observe q vs target separately.",
                      "Only imports math/numpy. You may synthesize numerical kinematics from the given robot-only geometry; no existing solver is provided.",
                      "Geometry: each body applies fixed pos/quaternion_wxyz, then hinge rotation about joint.pos/axis in its local frame; palm site transform at end. Joint type 3 is hinge. Non-commanded joints stay at observed initial_q.",
                      "Proprioception is public, no object target is used. Preserve task.quaternion_xyzw, keep hand open, explicitly wait for stable hold before done.",
                      "Keep a small staged state machine in state. After each motion, verify actual motion from the next observation before a dependent action; never infer motion from the command being accepted.",
                      "Bind derived values to observation.simulation_seconds and discard stale derived state after motion; re-observe before using a pose or contact estimate again.",
                      "mode=code executes your exact source. mode=skill calls available_skill's frozen source; use only when an available_skill is supplied. Never regenerate equivalent code as reuse."]}
    if memories:
        packet["external_skill_memory"] = [
            {"id": note.id, "status": note.status.value, "text": note.text,
             "evidence": list(note.evidence)} for note in memories
        ]
        packet["rules"].append(
            "external_skill_memory is attributed, unvalidated prior text. Use it only as guidance; "
            "do not copy its code templates, cite it as a local success, or treat it as a callable skill."
        )
    return packet


def candidates(root):
    registration = check_registration(root)
    registry = Registry(root / "registry")
    initial = registry.commit([], label="local_cycle_before")
    scope = Scope("T01_LOCAL_CLEARANCE", frozenset({"DH_2F_mug_06"}),
                  stage="initial_sha256:" + registration["initial_state"]["sha256"])
    observation = read(ROOT / registration["control_evidence_root"] / "positive_engineering/public_initial.json")
    feedback = None
    locked = None
    for version in (1, 2):
        if version == 1:
            answer, usage = read(PARENT / "author_v1/answer.json"), read(PARENT / "author_v1/metadata.json")
            write_new(root / "inherited_submission.json", {"answer": relative(PARENT / "author_v1/answer.json"),
                      "sha256": sha(PARENT / "author_v1/answer.json"), "metadata": usage,
                      "source_sha256": hashlib.sha256(answer["source"].encode()).hexdigest()})
            source_path = PARENT / "author_v1"
        else:
            answer, usage = codex_decision.decide(prompt(registration, observation, feedback), SCHEMA,
                                                 root / f"author_v{version}", model=MODEL, timeout=120.)
            write_new(root / f"author_v{version}/answer.json", answer)
            source_path = root / f"author_v{version}"
        if answer["mode"] != "code":
            raise ValueError("no skill available during authoring")
        check_source(answer["source"])
        code = CodeModule(id="code_local_clearance", version=version, scope=scope, status=Status.CANDIDATE,
                          source=answer["source"], allowed_imports=("math", "numpy"),
                          dependencies=tuple(registration["dependencies"].values()),
                          evidence=(relative(source_path),))
        op = Op(op_id="local_clearance", version=version, scope=scope, status=Status.CANDIDATE,
                pre=tuple(Predicate(n) for n in registration["local_contract"]["preconditions"]
                          if n != "known_saved_initial"),
                post=(Predicate("ExplicitPoseHeld"),), budget_s=30.,
                failure_codes=tuple(registration["local_contract"]["failure_exits"]),
                implementation=code.id, implementation_sha256=code.source_sha256,
                dependencies=("registration:" + sha(root / "registration.json"),))
        skill = Skill(id="skill_local_clearance", version=version, scope=scope, status=Status.CANDIDATE,
                      validation=None, steps=(Step(op.op_id),), pre=op.pre, post=op.post,
                      dependencies=op.dependencies, evidence=code.evidence)
        snap = registry.commit([(code.id, registry.put(code)), (op.op_id, registry.put(op)),
                                (skill.id, registry.put(skill))], label=f"candidate_v{version}", parent=initial.id)
        manifest = artifact.compile_local_skill(registry, snap.id, skill.id, root / f"projection_v{version}",
                                                root / "registration.json")
        result = execute(root, f"candidate_v{version}", registration, source=code.source)
        write_new(root / f"candidate_v{version}/model_usage.json", usage)
        locked = {"snapshot_id": snap.id, "skill_digest": skill.digest(), "op_digest": op.digest(),
                  "code_digest": code.digest(), "source_sha256": code.source_sha256,
                  "artifact": manifest["artifact"], "practice_result": relative(root / f"candidate_v{version}/result.json"),
                  "candidate_status": "candidate", "formal_admissions": 0}
        if result["local_success"]:
            break
        # Only legal proprioception/action feedback goes back; no private verdict rows.
        observations = [json.loads(line) for line in (root / f"candidate_v{version}/observations.jsonl").read_text().splitlines()]
        feedback = {"previous_source": code.source, "error": result["error"],
                    "local_success": result["local_success"], "terminal_proprioception": observations[-1],
                    "actions": [json.loads(line) for line in (root / f"candidate_v{version}/actions.jsonl").read_text().splitlines()]}
    write_new(root / "locked_candidate.json", locked)


def render_pair_video(output):
    """Uniform 20 fps replay, no policy input or additional physics steps."""
    import cv2

    episode = output / "episode"
    ref = read(episode / "model_reference.json")
    model = mujoco.MjModel.from_binary_path(str(ROOT / ref["path"]))
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, width=640, height=360, max_geom=4000)
    video = output / "original_speed.mp4"
    if video.exists():
        raise FileExistsError(video)
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 20., (1280, 360))
    if not writer.isOpened():
        raise RuntimeError("video writer unavailable")
    try:
        with np.load(episode / "trajectory.npz", allow_pickle=False) as trace:
            for t in np.arange(0., trace["time"][-1] + .025, .05):
                i = int(np.argmin(abs(trace["time"] - t)))
                data.qpos[:] = trace["qpos"][i]
                mujoco.mj_forward(model, data)
                views = []
                for camera in ("task_observer", "g1_head"):
                    renderer.update_scene(data, camera=camera)
                    views.append(renderer.render().copy())
                frame = np.concatenate(views, axis=1)
                cv2.putText(frame, f"{output.name}  {t:.2f}s  1x", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 1)
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()
        renderer.close()
    return relative(video)


def paired(root):
    registration = check_registration(root)
    locked = read(root / "locked_candidate.json")
    practice = read(ROOT / locked["practice_result"])
    if not practice["local_success"]:
        write_new(root / "admission.json", {"formal_admissions": 0, "reason": "locked candidate failed local practice",
                                          "reuse": "not_run", "locked": locked})
        return
    registry = Registry(root / "registry")
    view = registry.load(locked["snapshot_id"])
    skill = registry.get_by_digest(locked["skill_digest"])
    module = registry.get_by_digest(locked["code_digest"])
    observation = read(ROOT / registration["control_evidence_root"] / "positive_engineering/public_initial.json")
    rows = []
    for arm in ("without", "with"):
        available = None
        if arm == "with":
            available = {"artifact": locked["artifact"], "source": module.source,
                         "contract": registration["local_contract"], "entry": "act"}
        answer, usage = codex_decision.decide(prompt(registration, observation, available=available),
                                             SCHEMA, root / f"decision_{arm}", model=MODEL, timeout=120.)
        write_new(root / f"decision_{arm}/answer.json", answer)
        if arm == "without" and answer["mode"] != "code":
            raise ValueError("baseline cannot call absent skill")
        invoked = answer["mode"] == "skill" and arm == "with"
        source = module.source if invoked else answer["source"]
        row = execute(root, f"paired_{arm}", registration, source=source,
                      reuse=locked["artifact"] if invoked else None)
        row["video"] = render_pair_video(root / f"paired_{arm}")
        row["model_usage"] = usage
        row["skill_invoked"] = invoked
        rows.append(row)
    baseline, treatment = rows
    same_initial = baseline["initial_hash"] == treatment["initial_hash"]
    faster = (baseline["first_stable_s"] is not None and treatment["first_stable_s"] is not None
              and baseline["first_stable_s"] - treatment["first_stable_s"] >= .05 - 1e-8)
    improve = not baseline["local_success"] or faster
    passed = bool(treatment["local_success"] and treatment["skill_invoked"] and same_initial and improve)
    checks = (("same_actual_initial", same_initial), ("skill_called", treatment["skill_invoked"]),
              ("treatment_local_success", treatment["local_success"]),
              ("paired_improvement", improve), ("two_original_speed_videos", True),
              ("controls_passed", True), ("no_treatment_execution_error", treatment["error"] is None),
              ("source_unchanged", module.source_sha256 == locked["source_sha256"]))
    report = ValidationReport(
        id="validation_local_clearance_paired", candidate_id=skill.id, candidate_digest=skill.digest(),
        validation=Validation.PAIRED, protocol="local_explicit_pose_paired_v1",
        baseline_episode=baseline["episode"], treatment_episode=treatment["episode"],
        initial_state_sha256=registration["initial_state"]["sha256"],
        metrics=(("baseline_local_success", float(baseline["local_success"])),
                 ("treatment_local_success", float(treatment["local_success"]))),
        contract_tests=checks, regression=(("wait_failed", True), ("engineering_passed", True)),
        decision="promote" if passed else "reject",
        evidence=tuple(relative(root / name) for name in
                       ("registration.json", "paired_without/result.json", "paired_with/result.json",
                        "paired_without/local_verdict.json", "paired_with/local_verdict.json"))
                 + (baseline["video"], treatment["video"]),
        created_at=datetime.now(timezone.utc).isoformat())
    op = view.artifacts["local_clearance"]
    op_report = replace(report, id="validation_local_clearance_op_paired", candidate_id=op.op_id,
                        candidate_digest=op.digest())
    refs = list(view.snapshot.refs) + [(report.id, registry.put(report)), (op_report.id, registry.put(op_report))]
    reported = registry.commit(refs, label="local_paired_report", parent=view.snapshot.id)
    write_new(root / "paired_results.json", {"rows": rows, "checks": list(checks), "passed": passed})
    snapshot = reported
    if passed:
        snapshot = registry.promote(snapshot.id, op.op_id, op_report.id)
        snapshot = registry.promote(snapshot.id, skill.id, report.id)
    frozen = registry.freeze(snapshot.id)
    admission = {"formal_admissions": int(passed), "validation": "paired" if passed else None,
                 "snapshot_id": frozen.id, "report_digest": report.digest(),
                 "candidate_digest": skill.digest(), "scope": skill.scope.to_dict(),
                 "reason": "paired improvement" if passed else "paired criterion not met",
                 "reuse": "registered_next_phase" if passed else "not_run"}
    write_new(root / "admission.json", admission)


def reuse(root):
    registration = check_registration(root)
    admission = read(root / "admission.json")
    if admission["formal_admissions"] != 1:
        raise ValueError("no admitted skill; no formal reuse")
    registry = Registry(root / "registry")
    view = registry.load(admission["snapshot_id"])
    skill = view.artifacts["skill_local_clearance"]
    module = registry.code_projection(view.snapshot.id)["local_clearance"]
    if "local_clearance" not in registry.op_table(view.snapshot.id, "formal"):
        raise ValueError("formal reuse requires a validated op")
    reference = {"id": skill.id, "version": skill.version, "digest": skill.digest(),
                 "source_sha256": module.source_sha256, "snapshot_id": view.snapshot.id}
    artifact.compile_local_skill(registry, view.snapshot.id, skill.id, root / "frozen_projection", root / "registration.json")
    write_new(root / "reuse_registration.json", {"artifact": reference,
              "object_binding": registration["object_binding"], "task": "A clearance then given engineering B raised clearance",
              "prediction": "A holds, B enters next pose directly; failure of either refutes successful connection",
              "reset_between_A_B": False, "model_requests": 0, "new_code_generation": False,
              "registration_parent_sha256": sha(root / "registration.json")})
    execute(root, "reuse_continuation", registration, source=module.source, reuse=reference, continuation=True)


def summarize(root):
    registration = read(root / "registration.json")
    rows = [read(path) for path in sorted(root.glob("*/result.json"))]
    metadata = [read(path) for path in sorted(root.glob("*/metadata.json"))]
    metadata += [read(PARENT / "author_v1/metadata.json")]
    parent_rows = [read(PARENT / name / "result.json") for name in ("negative_wait", "positive_engineering")]
    parent_rows += [read(CONTROL_PARENT / name / "result.json") for name in ("negative_wait", "positive_engineering")]
    admission = read(root / "admission.json") if (root / "admission.json").exists() else {"formal_admissions": 0, "reason": "not_reached"}
    candidates = [r for r in rows if r["name"].startswith("candidate_")]
    reused = [r for r in rows if r["name"] == "reuse_continuation"]
    summary = {"prediction": registration["prediction"], "controls": read(root / "controls.json"),
               "candidates_submitted": len(candidates), "candidate_local_passes": sum(r["local_success"] for r in candidates),
               "formal_admissions": admission["formal_admissions"], "admission": admission,
               "actual_later_reuse": len(reused),
               "connection_passes": sum(bool(r["handoff"] and r["handoff"]["connection_passed"]) for r in reused),
               "full_task_successes": sum(r["full_task_success"] for r in rows),
               "new_task_coverage": "not_tested", "cost_benefit_vs_no_reuse": "not_tested",
               "engineering_given_abilities": 1, "independent_initials": 1,
               "parent_episode_costs": parent_rows,
               "cost": {"episodes": len(rows) + len(parent_rows), "current_run_episodes": len(rows),
                        "model_requests": len(metadata),
                        "input_tokens": sum(m.get("input_tokens", 0) for m in metadata),
                        "output_tokens": sum(m.get("output_tokens", 0) for m in metadata),
                        "reasoning_tokens": sum(m.get("reasoning_output_tokens", 0) for m in metadata),
                        "missing_usage_requests": sum(m.get("status") != "ok" for m in metadata),
                        "currency_cost": "not_reported_by_transport",
                        "commands": sum(r["commands"] for r in rows + parent_rows),
                        "worker_calls": sum(r["worker_calls"] for r in rows),
                        "simulation_s": sum(r["simulation_seconds"] for r in rows + parent_rows),
                        "episode_wall_s": sum(r["wall_seconds"] for r in rows + parent_rows),
                        "model_wall_s": sum(m["wall_seconds"] for m in metadata),
                        "completed_phase_wall_s": sum(read(p)["wall_seconds"] for parent in (root, PARENT, CONTROL_PARENT)
                                                      for p in parent.glob("phase_*_timing.json"))},
               "rows": rows}
    write_new(root / "results.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "controls")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("controls", "inherit-controls", "candidates", "paired", "reuse", "summarize"), required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    started = time.monotonic()
    try:
        if args.phase == "controls":
            controls(args.output)
        elif args.phase == "inherit-controls":
            inherit_controls(args.output)
        elif args.phase == "candidates":
            candidates(args.output)
        elif args.phase == "paired":
            paired(args.output)
        elif args.phase == "reuse":
            reuse(args.output)
        else:
            summarize(args.output)
    except Exception as error:
        if args.output.is_dir():
            write_new(args.output / f"phase_{args.phase}_error.json", {
                "error": type(error).__name__, "message": str(error),
                "wall_seconds": time.monotonic() - started})
        raise
    finally:
        if args.output.is_dir():
            write_new(args.output / f"phase_{args.phase}_timing.json", {"wall_seconds": time.monotonic() - started})


if __name__ == "__main__":
    main()
