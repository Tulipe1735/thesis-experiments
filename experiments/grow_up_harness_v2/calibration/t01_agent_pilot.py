"""Run one paired, bounded T01 development block, with S0C0 first."""

import argparse
from collections import Counter
import math
from pathlib import Path
import sys
import time

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
sys.path[:0] = [str(PACKAGE), str(ROOT)]

from harness import codex_decision, evidence
from t01_controls import CASE_ID, SUITE
import t01_motion
from experiments.cordis_t01.worker import SavedInitialRobot
from experiments.t0_agent_v1.common import append_event, read, relative, sha, write_new
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot
from experiments.t0_agent_v1.tray_tools import locate_tray, visible_cups
from experiments.t0_agent_v1.tray_verify import verify
from rgbd_cup import PerceptionError


ARMS = ("S0C0", "S1C0", "S0C1", "S1C1")
MODEL = "gpt-5.6-sol"
CALL_CAP = 10
TOKEN_CAP = 300_000
WALL_CAP = 600
DECISION_TIMEOUT_S = 120.0
ACTIONS_PER_TURN = 8
# Registered engineering grasp geometry (runs/t01_controls_20261104_001). The
# palm site sits this far from the cup's grasp point, before rotation.
CUP_IN_PALM_M = (0.045, -0.055, -0.052)
# One plain move may not exceed this palm travel; longer motions must be split
# or use move_linear. A 30 cm single move drifts the floating base past 0.12 m.
MAX_MOVE_M = 0.05
# Opening the hand with the palm above this height over the tray is refused; the
# cup would drop and topple (runs/t01_agent_pilot_20261104_006/S1C1).
RELEASE_MAX_PALM_ABOVE_TRAY_M = 0.12
SKILL_CARD = (
    "Reach the cup in five phases, a few short commands each. "
    "1) Clear: lift the palm to about (-0.07, 0.34, 0.09) keeping the current wrist orientation, then raise it "
    "to (-0.04, 0.34, 0.30) with a level palm. Each leg is several moves of at most 5 cm; one long move drifts the base. "
    "2) Lean: set waist_pitch_joint to about -0.10 rad, wait 1 s, and move back to the clear pose; "
    "without this lean the approach stops about 20 cm short. "
    "3) Approach: the grasp pose is cup_bottoms_m minus the rotated cup_in_palm_m from grasp_probe; "
    "start from approach_start_xyz_m and walk to grasp_xyz_m in steps of 2-3 cm, keeping the palm yaw. "
    "4) Close: set the thumb to 0.0/0.65/0.65 rad and index and middle to -0.8/-0.6 rad, wait, "
    "then lift in 3-5 cm steps to 12 cm and check that the cup stayed with the hand. "
    "5) Place: use place_probe, not the tray centre. Move the palm to place_probe.above_xyz_m with "
    "the same palm yaw, then lower to place_probe.lower_xyz_m; that puts the cup bottom at "
    "place_probe.cup_bottom_at_lower_m over the tray centre. Aiming the palm at the tray centre "
    "leaves the cup one cup_in_palm away and it lands beside the tray. "
    "Do not open the hand before the palm is at or below place_probe.release_palm_below_z_m; "
    "releasing higher is refused as RELEASE_TOO_HIGH and the cup topples. "
    "Open the hand fully, wait 0.5 s without moving, then retreat upward in 5 cm steps and call finish. "
    "The episode ends at release: touching or re-grasping the cup afterwards is refused as "
    "REAPPROACH_AFTER_RELEASE. Let the scene settle for at least 1 s before finishing. "
    "No single move may exceed 5 cm of palm travel; longer moves are rejected, so split them. "
    "Use 2 s or more per move; a large jump in one command trips tracking protection. "
    "If grasp_xyz_m is rejected, change waist_pitch_joint by 0.05 rad, wait, and read grasp_probe again. "
    "If a probe reports POSE_IK_REJECTED, move nearer before retrying. "
    "Never infer successful placement from a completed motion."
)


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


NUMBER = {"type": "number"}
STRING = {"type": "string"}
JOINTS = {"type": "array", "items": obj(joint=STRING, radians=NUMBER)}


def command(op, **parameters):
    return obj(op={"type": "string", "enum": [op]}, **parameters)


def action_schema(code):
    moves = {k: NUMBER for k in ("x", "y", "z", "yaw", "seconds")}
    moves["orientation"] = {"type": "string", "enum": ["keep", "yaw"]}
    variants = [command("move", **moves), command("check_pose", **moves),
                command("joints", targets=JOINTS, seconds=NUMBER),
                command("wait", seconds=NUMBER), command("finish")]
    if code:
        variants.append(command("move_linear", **moves))
    return obj(actions={"type": "array", "items": {"anyOf": variants}}, reason=STRING)


def observe(port, robot):
    raw = port.observe()
    body = raw["body_state"]
    try:
        cups = visible_cups(raw, expected_count=1)
    except PerceptionError:
        cups = []
    try:
        tray = locate_tray(raw)["center_floor_pelvis_m"]
    except PerceptionError:
        tray = None
    return {
        "frame": "current_pelvis", "simulation_seconds": body["simulation_seconds"],
        "cup_bottoms_m": [cup["cup_bottom_position_m"] for cup in cups],
        "cup_radius_prior_m": 0.041,
        "tray_floor_center_m": tray,
        "left_palm": body["palms"]["left"],
        "grasp_probe": (
            t01_motion.grasp_probe(robot, cups[0]["cup_bottom_position_m"], CUP_IN_PALM_M)
            if cups else None
        ),
        "place_probe": (
            t01_motion.place_probe(tray, CUP_IN_PALM_M) if tray is not None else None
        ),
        "left_contact_load_N": body["approximate_contact_load_N"]["left"],
        "joints": {
            name: {"q": row["q"], "target": row["target"], **t01_motion.joint_bounds(robot, name)}
            for name, row in body["joints"].items() if controllable(name)
        },
    }


def controllable(name):
    return name.startswith("waist_") or (
        name.startswith("left_") and any(
            token in name for token in ("shoulder", "elbow", "wrist", "_hand_")
        )
    )


def number(value, lo, hi):
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError("Numeric parameter is outside the command bounds")
    return float(value)


def parse_commands(answer, schema, joints):
    if not isinstance(answer, dict) or set(answer) != {"actions", "reason"} or not isinstance(answer["reason"], str):
        raise ValueError("Unexpected decision fields")
    actions = answer["actions"]
    if type(actions) is not list or not 1 <= len(actions) <= ACTIONS_PER_TURN:
        raise ValueError(f"Return one to {ACTIONS_PER_TURN} commands")
    shapes = {
        v["properties"]["op"]["enum"][0]: set(v["required"])
        for v in schema["properties"]["actions"]["items"]["anyOf"]
    }
    for i, action in enumerate(actions):
        if not isinstance(action, dict) or not isinstance(action.get("op"), str):
            raise ValueError("Action is missing its operation")
        op = action["op"]
        if op not in shapes or set(action) != shapes[op]:
            raise ValueError("Unexpected action or action fields")
        if op == "finish":
            if i != len(actions) - 1:
                raise ValueError("finish must be the last action")
            continue
        number(action["seconds"], .02, 15.)
        if op in ("move", "move_linear", "check_pose"):
            for axis in "xyz":
                number(action[axis], -1., 1.)
            number(action["yaw"], -math.pi, math.pi)
            if action["orientation"] not in ("keep", "yaw"):
                raise ValueError("Orientation must be keep or yaw")
        elif op == "joints":
            seen = set()
            if type(action["targets"]) is not list or not 1 <= len(action["targets"]) <= len(joints):
                raise ValueError("Expected nonempty joint target list")
            for target in action["targets"]:
                if not isinstance(target, dict) or set(target) != {"joint", "radians"}:
                    raise ValueError("Invalid joint target fields")
                name = target["joint"]
                if not isinstance(name, str) or name not in joints or name in seen:
                    raise ValueError("Unknown or duplicate joint")
                seen.add(name)
                number(target["radians"], *joints[name]["range_rad"])
    return actions


def opens_hand(action, robot):
    """True when a joint command on three or more hand joints lowers their mean angle."""
    hand = [(target["joint"], target["radians"]) for target in action["targets"]
            if target["joint"].startswith("left_hand_")]
    if len(hand) < 3:
        return False
    before = sum(abs(robot.targets[robot.ai[name]]) for name, _ in hand) / len(hand)
    after = sum(abs(value) for _, value in hand) / len(hand)
    return after < before - .05


def closes_hand(action, robot):
    """True when a joint command on three or more hand joints raises their mean angle."""
    hand = [(target["joint"], target["radians"]) for target in action["targets"]
            if target["joint"].startswith("left_hand_")]
    if len(hand) < 3:
        return False
    before = sum(abs(robot.targets[robot.ai[name]]) for name, _ in hand) / len(hand)
    after = sum(abs(value) for _, value in hand) / len(hand)
    return after > before + .05


def execute(port, action, robot, tray_floor_m=None, session=None):
    op = action["op"]
    seconds = action["seconds"]
    if op == "joints":
        palm_z = port.state()["palms"]["left"]["position_m"][2]
        if tray_floor_m is not None and opens_hand(action, robot):
            ceiling = tray_floor_m[2] + RELEASE_MAX_PALM_ABOVE_TRAY_M
            if palm_z > ceiling + 1e-9:
                raise ValueError(
                    f"RELEASE_TOO_HIGH: palm z {palm_z:.3f} is above {ceiling:.3f}; "
                    "lower the palm before opening the hand"
                )
            if session is not None:
                session["released"] = True
        if session is not None and session.get("released") and closes_hand(action, robot):
            raise ValueError(
                "REAPPROACH_AFTER_RELEASE: the cup is already released; retreat and finish"
            )
        return [port.invoke("set_joints", {
            "targets": {item["joint"]: item["radians"] for item in action["targets"]},
            "duration": seconds,
        })]
    if op == "wait":
        return [port.invoke("wait", {"seconds": seconds})]
    end = [action[key] for key in "xyz"]
    quaternion = t01_motion.quaternion_for(action)
    if op == "check_pose":
        return [t01_motion.check_pose(robot, end, quaternion, seconds)]
    if session is not None and session.get("released") and tray_floor_m is not None:
        if end[2] < tray_floor_m[2] + .10:
            raise ValueError(
                "REAPPROACH_AFTER_RELEASE: the cup is already released; retreat and finish"
            )
    if op == "move":
        current = port.state()["palms"]["left"]["position_m"]
        if math.dist(current, end) > MAX_MOVE_M + 1e-9:
            raise ValueError(
                f"move exceeds the {MAX_MOVE_M:.2f} m single-command limit; split it or use move_linear"
            )
    count, start = 1, end
    if op == "move_linear":
        palm = port.state()["palms"]["left"]
        start = palm["position_m"]
        if quaternion is None:
            quaternion = palm["quaternion_xyzw"]
        count = max(1, math.ceil(math.dist(start, end) / .02))
        if seconds / count < .02:
            raise ValueError("Duration too short for linear interpolation")
    replies = []
    for step in range(1, count + 1):
        position = [a + (b - a) * step / count for a, b in zip(start, end)]
        result = port.invoke("move_ee", {
            "side": "left", "position": position, "quaternion_xyzw": quaternion,
            "duration": seconds / count,
        })
        replies.append(result)
        if result["status"] != "EXECUTED":
            break
    return replies


def prompt_for(arm, state, feedback, remaining):
    prompt = {
        "task": "Place the single upright cup on the tray floor, release it and let it settle.",
        "observation": state, "previous_commands": feedback, "remaining_turns": remaining,
        "commands": {
            "move": {"example": {"op": "move", "x": 0., "y": .33, "z": .1, "orientation": "keep",
                                 "yaw": 0., "seconds": 3.},
                     "meaning": "Target x,y,z in current pelvis metres (x forward, y left, z up). "
                                "Keep preserves the whole current wrist orientation; yaw uses level palm rotation about +Z."},
            "check_pose": "Same fields as move, with op check_pose. Dry-run IK and joint speed only; "
                          "no movement or collision/tracking guarantee. A failed probe stops the batch.",
            "joints": "Absolute joint targets in radians, e.g. {\"op\":\"joints\",\"targets\":[{\"joint\":"
                      "\"left_elbow_joint\",\"radians\":0.5}],\"seconds\":2}. Use reported joint range and velocity limits.",
            "wait": "Advance seconds without changing joint targets.",
            "finish": "End episode; saved physics will be scored independently.",
        },
        "rules": (
            f'Return only {{"actions":[...],"reason":"..."}}. Use 1 to {ACTIONS_PER_TURN} commands, '
            "each timed command .02 to 15 s. "
            "A rejected command interrupts the batch and returns a new observation. "
            "Use small increments from the current palm. grasp_probe is a dry-run IK report: "
            "grasp_xyz_m and approach_start_xyz_m are palm targets computed from the observed cup. "
            "place_probe gives the palm targets that put the cup over the tray centre. "
            "A single move may not exceed 5 cm of palm travel; it is rejected above that, so split it. "
            "Do not open the hand above the tray unless the palm is at or below "
            "place_probe.release_palm_below_z_m; that is refused as RELEASE_TOO_HIGH. "
            "It does not guarantee collision-free or trackable motion. "
            "If IK passes but tracking fails, shorten the motion. "
            "Unknown cup or tray position is null or an empty list. "
            "Model outputs are interpreted as commands only; you cannot access files or tools."
        ),
    }
    if arm[1] == "1":
        prompt["skill_card"] = SKILL_CARD
    if arm[3] == "1":
        prompt["commands"]["move_linear"] = (
            "Same absolute target and duration as move; reusable straight-line palm interpolation "
            "from the current pose. Stops at the first failed guarded IK waypoint."
        )
    return prompt


def run_arm(output, arm, case, model_ref, saved, budget, decide, *, model=MODEL,
            call_cap=CALL_CAP, wall_cap=WALL_CAP, decision_timeout_s=DECISION_TIMEOUT_S):
    started = time.monotonic()
    output.mkdir()
    episode = output / "episode"
    episode.mkdir()
    write_new(episode / "instance.json", case["instance"])
    kwargs = dict(budget=budget, scene_path=ROOT / model_ref["path"])
    if saved is None:
        # Generated case: the sampler built the instance, so the plant starts there.
        robot = PilotRobot(episode, case["instance"], **kwargs)
        initial_sha = sha(episode / "initial_state.npz")
    else:
        robot = SavedInitialRobot(episode, case["instance"], initial_state=saved, **kwargs)
        initial_sha = sha(episode / "initial_state.npz")
        if initial_sha != sha(saved):
            robot.renderer.close()
            raise ValueError("Restored state differs from registered bytes")
    port = CountedPort(robot)
    usage = Counter()
    calls = 0
    pose_checks = 0
    cost = 0.0
    outcome = "CALL_CAP"
    error = None
    feedback = []
    session = {}
    schema = action_schema(arm[3] == "1")
    try:
        robot.advance(.75, "initial_settling")
        for turn in range(call_cap):
            if robot.guard:
                outcome = robot.guard
                break
            if time.monotonic() - started >= wall_cap:
                outcome = "WALL_CAP"
                break
            state = observe(port, robot)
            deadline = wall_cap - (time.monotonic() - started)
            if deadline <= 0:
                outcome = "WALL_CAP"
                break
            calls += 1
            answer, used = decide(prompt_for(arm, state, feedback, call_cap-turn), schema,
                                  output / f"call_{calls:02}", model=model,
                                  timeout=min(decision_timeout_s, deadline))
            for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
                usage[key] += used[key]
            cost += used.get("cost", 0.0)
            if (usage["input_tokens"] + usage["output_tokens"]
                    + (usage["reasoning_output_tokens"] if used.get("reasoning_excluded_from_output") else 0)
                    >= TOKEN_CAP):
                outcome = "TOKEN_CAP"
                break
            try:
                actions = parse_commands(answer, schema, state["joints"])
            except ValueError as exc:
                feedback = [{"status": "INVALID_DECISION", "reason": str(exc)}]
                append_event(output / "actions.jsonl", {"turn": calls, "feedback": feedback})
                continue
            feedback = []
            for action in actions:
                if robot.guard:
                    outcome = robot.guard
                    break
                if time.monotonic() - started >= wall_cap:
                    outcome = "WALL_CAP"
                    break
                op = action["op"]
                if op == "finish":
                    outcome = "AGENT_FINISH"
                    append_event(output / "actions.jsonl", {"turn": calls, "action": action,
                                                            "status": "REQUESTED_VERIFICATION"})
                    break
                try:
                    if op == "check_pose":
                        pose_checks += 1
                    replies = execute(port, action, robot, state.get("tray_floor_center_m"), session)
                    last = replies[-1]
                    status = last.get("status") or last.get("guard") or "EXECUTED"
                    summary = {k: last[k] for k in ("ik_position_error_m", "position_error_m",
                               "ik_orientation_error_rad", "orientation_error_rad",
                               "actual_position_error_m", "minimum_seconds") if k in last}
                except ValueError as exc:
                    status, summary = "REJECTED", {"reason": str(exc)}
                row = {"action": action, "status": status, **summary}
                feedback.append(row)
                append_event(output / "actions.jsonl", {"turn": calls, **row})
                if status not in ("EXECUTED", "POSE_FEASIBLE"):
                    break
            if outcome != "CALL_CAP":
                break
        if robot.guard:
            outcome = robot.guard
    except Exception as exc:
        outcome = "HARNESS_OR_GATEWAY_ERROR"
        error = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    control_wall = time.monotonic() - started
    environment = robot.finish()
    verdict = verify(episode, execution_error=error)
    result = {
        "arm": arm, "outcome": outcome, "error": error, "episode": relative(episode),
        "verified_success": verdict["verified_success"], "valid_initial": verdict["initial_valid"],
        "initial_sha256": initial_sha, "terminal_stable_s": verdict["terminal_simultaneous_stable_s"],
        "simulation_seconds": environment["simulation_seconds"],
        "wall_seconds": control_wall, "model_requests": calls, "tokens": dict(usage),
        "reported_model_cost": cost, "read_only_pose_checks": pose_checks,
        "low_level_command_calls": port.command_calls, "protection": verdict["protection"],
        "trajectory_sha256": sha(episode / "trajectory.npz"),
        "verdict_sha256": sha(episode / "independent_verification.json"),
    }
    write_new(output / "result.json", result)
    evidence.write_hashes(output)
    return result


def run(output, decide, *, model=MODEL, call_cap=CALL_CAP, extra_sources=(), gateway_metadata=None,
        wall_cap=WALL_CAP, decision_timeout_s=DECISION_TIMEOUT_S, arms=ARMS,
        suite=SUITE, case_id=CASE_ID):
    source = read(suite / "registration.json")
    case = next(c for c in source["cases"] if c["id"] == case_id)
    saved = ROOT / case["initial_source"] if case.get("initial_source") else None
    model_ref = source["models"][case["model_key"]]
    budget = source["simulation_budget_s"]
    evaluator = ROOT / "experiments/t0_agent_v1/tray_verify.py"
    controls_file = PACKAGE / "runs/t01_controls_20261104_001/results.json"
    if saved is not None:
        # The control case keeps its full qualification chain; generated cases do not.
        controls = read(controls_file)
        prior_reg = read(controls_file.parent / "registration.json")
        if (not controls["passed"] or [x["verified_success"] for x in controls["controls"]] != [False, True]
                or not all(x["actual_initial_state_sha256"] == sha(saved) for x in controls["controls"])
                or prior_reg["evaluator_sha256"] != sha(evaluator)
                or prior_reg["simulation_budget_s"] != budget or prior_reg["model"] != model_ref
                or sha(ROOT / model_ref["path"]) != model_ref["sha256"]):
            raise ValueError("T01 controls no longer qualify the registered plant and initial state")
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "registration.json", {
        "task": "T01", "split": "generated" if saved is None else "consumed_development_control",
        "purpose": "wiring pilot", "suite": str(suite), "case_id": case_id,
        "case": case, "initial_state_sha256": sha(saved) if saved else None, "model": model_ref,
        "backend": model, "arms": list(arms), "simulation_budget_s": budget,
        "gateway": gateway_metadata,
        "calls_per_arm": call_cap, "max_model_requests": len(arms) * call_cap,
        "tokens_per_arm_stop_after_response": TOKEN_CAP,
        "wall_seconds_per_arm": wall_cap, "actions_per_turn": ACTIONS_PER_TURN,
        "decision_timeout_s": decision_timeout_s,
        "stop": "Stop at an infrastructure error, invalid initial state, or missing evidence. Task failure is a valid result.",
        "controls_sha256": sha(controls_file) if saved is not None else None,
        "evaluator_sha256": sha(evaluator),
        "source_hashes": {relative(p): sha(p) for p in (Path(__file__), Path(codex_decision.__file__),
                          Path(t01_motion.__file__), *extra_sources,
                          ROOT / "experiments/cordis_t01/worker.py",
                          ROOT / "experiments/t0_agent_v1/runtime.py",
                          ROOT / "grasp_optimization/pantry_robot.py",
                          ROOT / "grasp_optimization/vision_grasp.py",
                          ROOT / "grasp_optimization/rgbd_cup.py",
                          ROOT / "experiments/t0_agent_v1/tray_tools.py")},
        "skill_card": SKILL_CARD, "schemas": {arm: action_schema(arm[3] == "1") for arm in arms},
    })
    rows = []
    for arm in arms:
        row = run_arm(output / arm, arm, case, model_ref, saved, budget, decide,
                      model=model, call_cap=call_cap, wall_cap=wall_cap,
                      decision_timeout_s=decision_timeout_s)
        if not evidence.verify_hashes(output / arm)["ok"]:
            raise ValueError("Episode evidence hash check failed")
        rows.append(row)
        append_event(output / "arms.jsonl", row)
        if row["error"] or not row["valid_initial"]:
            break
    complete = len(rows) == len(arms) and all(row["error"] is None and row["valid_initial"] for row in rows)
    write_new(output / "results.json", {"complete": complete, "arms": rows, "scope": "one development initial"})
    return complete


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--calls-per-arm", type=int, choices=range(1, CALL_CAP + 1), default=CALL_CAP)
    parser.add_argument("--suite", type=Path, default=SUITE)
    parser.add_argument("--case", default=CASE_ID)
    parser.add_argument("--arms", default=",".join(ARMS))
    args = parser.parse_args()
    arms = tuple(a.strip() for a in args.arms.split(",") if a.strip())
    raise SystemExit(0 if run(args.output.resolve(), codex_decision.decide,
                              model=args.model, call_cap=args.calls_per_arm,
                              arms=arms, suite=args.suite.resolve(), case_id=args.case) else 1)
