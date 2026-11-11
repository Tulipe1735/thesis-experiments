"""Live code policy on a generated T01 case.

The agent writes Python in a persistent namespace; `robot` is bound to the live
plant. Physics advances while the model thinks, so every observation can be
stale when the code starts. This is the advisor's interface, with one recorded
difference: the plant is stepped after the model call returns, by the measured
latency, instead of on a background thread. For this interface the next
observation is equally stale either way.

Budget: 10 model calls, 600 s simulation, 120 s hard compute cap per program.
"""

import argparse
import contextlib
import io
import json
import math
import signal
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PACKAGE = ROOT / "experiments/grow_up_harness_v2"
if str(PACKAGE / "calibration") not in sys.path:
    sys.path.insert(0, str(PACKAGE / "calibration"))

import t01_agent_pilot as pilot  # noqa: E402
from harness import artifact as artifact_mod, codex_decision  # noqa: E402
from experiments.cordis_t01.worker import SavedInitialRobot  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot  # noqa: E402
from experiments.t0_agent_v1.tray_verify import verify  # noqa: E402

SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_repl3_20261105_001"
CALL_CAP = 10
SIM_BUDGET_S = 600.0
COMPUTE_CAP_S = 120.0
# Interface guards, enforced here rather than requested in the prompt.
MAX_MOVE_M = 0.03
MIN_MOVE_S = 2.0
ARTIFACT = PACKAGE / "artifacts/t01_cup_to_tray.yaml"
CARD_TEXT = None

SCHEMA = {
    "type": "object",
    "properties": {"note": {"type": "string"}, "code": {"type": "string"}},
    "required": ["note", "code"],
    "additionalProperties": False,
}


class MoveRejected(RuntimeError):
    """Stop policy code at a refused target and expose the command diagnostics."""

    def __init__(self, details):
        self.details = dict(details)
        super().__init__(json.dumps(self.details, allow_nan=False))


class RobotSession:
    """The advisor's `robot` object, bound to the live plant."""

    def __init__(self, robot, port):
        self._robot, self._port = robot, port
        self.finished = False
        self.log = []

    def observe(self):
        return self._port.observe()

    def state(self):
        return self._port.state()

    def fk(self, links=None, joints=None):
        return self._robot.fk("left")

    def set_joints(self, targets, duration=1.0):
        return self._port.invoke("set_joints", {"targets": targets, "duration": float(duration)})

    def move_ee(self, side, position, quaternion_xyzw=None, duration=2.0):
        state = self._port.state()
        palm = state["palms"].get(side)
        target = [float(value) for value in position]
        if palm is None:
            entry = {"side": side, "requested_position_m": target,
                     "status": "UNKNOWN_SIDE", "executed": False}
            self.log.append(entry)
            return dict(entry, sides=sorted(state["palms"]))
        distance = math.dist(palm["position_m"], target)
        requested = float(duration)
        entry = {"side": side, "current_position_m": list(palm["position_m"]),
                 "requested_position_m": target, "distance_m": round(distance, 5),
                 "duration_requested_s": requested}
        if distance > MAX_MOVE_M + 1e-9:
            entry.update(status="MOVE_TOO_LONG", executed=False,
                         max_move_m=MAX_MOVE_M,
                         hint=f"split into steps of at most {MAX_MOVE_M:.2f} m")
            self.log.append(entry)
            raise MoveRejected(entry)
        applied = max(MIN_MOVE_S, requested)
        result = self._port.invoke("move_ee", {
            "side": side, "position": target, "quaternion_xyzw": quaternion_xyzw,
            "duration": applied,
        })
        entry.update(status=result.get("status"), executed=result.get("executed", True),
                     duration_applied_s=applied)
        if result["status"] == "POSE_IK_REJECTED":
            entry.update(position_error_m=result["position_error_m"],
                         orientation_error_rad=result["orientation_error_rad"])
        self.log.append(entry)
        if result["status"] == "POSE_IK_REJECTED":
            raise MoveRejected(entry)
        return dict(result, duration_requested_s=requested, duration_applied_s=applied)

    def wait(self, seconds):
        return self._port.invoke("wait", {"seconds": float(seconds)})

    def done(self):
        self.finished = True
        return {"status": "DONE"}


def observation_summary(observation, robot, port):
    state = port.state()
    palms = state.get("palms", {})
    joints = state.get("joints", {})
    return {
        "simulation_seconds": observation.get("simulation_seconds"),
        "head_rgb_path": observation.get("head_rgb_path"),
        "depth_path": observation.get("depth_path"),
        "resolution_wh": observation.get("resolution_wh"),
        "K": observation.get("K"),
        "T_optical_to_pelvis": observation.get("T_optical_to_pelvis"),
        "left_palm": palms.get("left"),
        "waist_pitch_rad": joints.get("waist_pitch_joint", {}).get("q"),
        "guard": getattr(robot, "guard", None),
    }


def prompt_for(observation, robot, port, history, remaining):
    return {
        "skill_card": CARD_TEXT,
        "task": "Place the single upright cup on the tray floor, release it and let it settle.",
        "robot": (
            "You control a simulated G1 with two Dex3-1 hands. Write Python in a persistent "
            "namespace; `robot` is bound to the live plant. Physics advances while you think. "
            "Available: robot.observe(), robot.state(), robot.fk(), "
            "robot.set_joints(targets, duration), robot.move_ee(side, position, quaternion_xyzw=None, duration=2), "
            "robot.wait(seconds), robot.done(). Use numpy, math, json, cv2, PIL."
        ),
        "images": ("head_rgb_path and depth_path are filesystem paths, not arrays: read RGB with "
                   "cv2.imread(path) and depth with np.load(path). Use the string exactly as returned; "
                   "never rebuild it. Depth is optical z in metres with NaN where invalid. "
                   "K is 3x3 intrinsics; T_optical_to_pelvis maps optical camera coordinates "
                   "(x right, y down, z forward) to the current pelvis frame."),
        "observation": observation_summary(observation, robot, port),
        "previous": history[-3:],
        "remaining_calls": remaining,
        "simulation_budget_s": SIM_BUDGET_S,
        "rules": ('Return only {"note": str, "code": str}. The code runs once, then control returns. '
                  'Physics keeps advancing for the measured model latency before your code starts. '
                  'A move is refused without motion when its target is more than 0.03 m from the '
                  'current palm; split longer travel into steps. Every move runs for at least 2 s; '
                  'shorter durations are raised to 2 s. Opening the hand above tray floor + 0.12 m '
                  'or touching the cup after release is refused. Call robot.done() when you believe '
                  'the cup is released and settled.'),
    }


class ComputeLimitReached(BaseException):
    """Hard stop for one policy program. BaseException so `except Exception` cannot swallow it."""


def run_code(code, namespace):
    stream = io.StringIO()
    started = time.monotonic()
    error = None

    def stop(signum, frame):
        raise ComputeLimitReached(f"policy exceeded {COMPUTE_CAP_S:g} s of compute")

    previous = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, COMPUTE_CAP_S, 1.0)
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            exec(compile(code, "<policy>", "exec"), namespace)
    except ComputeLimitReached:
        error = traceback.format_exc(limit=3)[-1200:]
    except Exception:
        error = traceback.format_exc(limit=3)[-1200:]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    return {"stdout": stream.getvalue()[-2000:], "error": error,
            "compute_s": round(time.monotonic() - started, 2)}


def run(output: Path, case_id: str, *, model: str, calls: int = CALL_CAP,
        scripted: str | None = None, sim_budget: float = SIM_BUDGET_S,
        prediction: str | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    registration = read(SUITE / "registration.json")
    case = next(row for row in registration["cases"] if row["id"] == case_id)
    model_ref = registration["models"][case["model_key"]]
    episode = output / "episode"
    episode.mkdir()
    write_new(episode / "instance.json", case["instance"])
    global CARD_TEXT
    if CARD_TEXT is None:
        CARD_TEXT = artifact_mod.generate_skill(artifact_mod.load(ARTIFACT))
    robot = PilotRobot(episode, case["instance"], budget=sim_budget,
                       scene_path=ROOT / model_ref["path"])
    port = CountedPort(robot)
    session = RobotSession(robot, port)
    namespace = {"robot": session, "json": json}
    write_new(output / "registration.json", {
        "date": time.strftime("%Y-%m-%d"), "boundary": "simulation", "kind": "t01_code_policy",
        "suite": relative(SUITE), "case_id": case_id, "model": model,
        "calls_cap": calls, "simulation_budget_s": sim_budget,
        "compute_cap_s": COMPUTE_CAP_S, "plant_sha256": model_ref["sha256"],
        "interface_guards": {"max_moves_ee_m": MAX_MOVE_M, "min_move_duration_s": MIN_MOVE_S},
        "move_rejection": {"exception": "MoveRejected",
                           "statuses": ["MOVE_TOO_LONG", "POSE_IK_REJECTED"]},
        "prediction": prediction,
        "evaluator_sha256": sha(ROOT / "experiments/t0_agent_v1/tray_verify.py"),
        "physics_during_latency": "post-hoc advance by measured latency, capped at the remaining budget",
        "model_requests": 0 if scripted else calls,
    })
    history = []
    calls_used = 0
    wall = time.monotonic()
    error = None
    try:
        robot.advance(.75, "initial_settling")
        limit = 1 if scripted else calls
        while calls_used < limit:
            calls_used += 1
            call_dir = output / f"call_{calls_used:02}"
            observation = port.observe()
            started = time.monotonic()
            if scripted:
                call_dir.mkdir()
                answer = {"note": "scripted", "code": scripted}
                usage = {}
            else:
                answer, usage = codex_decision.decide(
                    prompt_for(observation, robot, port, history, calls - calls_used + 1),
                    SCHEMA, call_dir, model=model, timeout=120.0)
            write_new(call_dir / "answer.json", {"note": answer.get("note", ""),
                                                 "code": answer.get("code", "")})
            latency = time.monotonic() - started
            # Physics advances during the model latency, capped at what is left.
            remaining = sim_budget - robot.data.time
            if remaining > 1e-6:
                robot.advance(min(latency, remaining), "model_latency")
            result = run_code(answer.get("code", ""), namespace)
            history.append({"note": answer.get("note", ""), "latency_s": round(latency, 2),
                            "stdout": result["stdout"], "error": result["error"],
                            "compute_s": result["compute_s"], "usage": usage})
            if session.finished or robot.guard:
                break
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:600]}
    runtime = robot.finish()
    verdict = verify(episode, execution_error=error)
    result = {
        "case": case_id, "model": model,
        "verified_success": verdict["verified_success"],
        "terminal_stable_s": verdict["terminal_simultaneous_stable_s"],
        "simulation_seconds": runtime["simulation_seconds"],
        "low_level_commands": port.command_calls,
        "calls_used": calls_used, "guard": robot.guard,
        "wall_seconds": round(time.monotonic() - wall, 1),
        "history": history, "error": error,
        "interface_log": session.log,
        "episode": relative(episode),
    }
    write_new(output / "result.json", result)
    return result


SELF_CHECK = '''
state = robot.state()
palm = state["palms"]["left"]["position_m"]
print("palm", palm)
print("waist", state["joints"]["waist_pitch_joint"]["q"])
far = [palm[0] - 0.10, palm[1], palm[2]]
try:
    robot.move_ee("left", far, duration=3.0)
except RuntimeError as error:
    print("far", type(error).__name__, str(error))
print("after_far", robot.state()["palms"]["left"]["position_m"])
near = [palm[0], palm[1], palm[2] + 0.02]
print("near", robot.move_ee("left", near, duration=0.5))
print("after_near", robot.state()["palms"]["left"]["position_m"])
robot.wait(0.5)
print("after wait", robot.state()["simulation_seconds"])
'''


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", default="asset_310300")
    parser.add_argument("--model", default="gpt-6.1-terra")
    parser.add_argument("--calls", type=int, default=CALL_CAP)
    parser.add_argument("--sim-budget", type=float, default=SIM_BUDGET_S)
    parser.add_argument("--cases", default=None, help="comma separated case ids; writes a summary")
    parser.add_argument("--prediction", default=None, help="expected result, recorded before the run")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    if args.cases:
        ids = [item.strip() for item in args.cases.split(",") if item.strip()]
        root = args.output.resolve()
        root.mkdir(parents=True, exist_ok=False)
        rows = []
        for case_id in ids:
            row = run(root / case_id, case_id, model=args.model, calls=args.calls,
                  sim_budget=args.sim_budget, prediction=args.prediction)
            statuses = {}
            for entry in row["interface_log"]:
                statuses[entry["status"]] = statuses.get(entry["status"], 0) + 1
            rows.append({"case": case_id, "verified_success": row["verified_success"],
                         "calls_used": row["calls_used"],
                         "low_level_commands": row["low_level_commands"],
                         "simulation_seconds": row["simulation_seconds"],
                         "interface_status_counts": statuses,
                         "guard": row["guard"], "wall_seconds": row["wall_seconds"]})
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        write_new(root / "summary.json", {
            "artifact": "t01_cup_to_tray", "branch": "code_policy", "model": args.model,
            "cases": ids, "episodes": len(rows), "prediction": args.prediction,
            "successes": sum(1 for r in rows if r["verified_success"]), "rows": rows,
        })
        return 0
    result = run(args.output.resolve(), args.case, model=args.model, calls=args.calls,
                 scripted=SELF_CHECK if args.self_check else None,
                 sim_budget=args.sim_budget)
    print(json.dumps({k: result[k] for k in ("case", "verified_success", "calls_used",
                                             "simulation_seconds", "low_level_commands")},
                     ensure_ascii=False, indent=1))
    if args.self_check:
        print(json.dumps(result["history"][0]["stdout"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
