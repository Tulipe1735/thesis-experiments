"""Can a T02 Worker fit its caps? Exact joint schedule plus measured wall costs.

    MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 "$G1_PYTHON" -B \
      experiments/grow_up_harness_v2/calibration/t02_worker_budget.py \
      --initial experiments/grow_up_harness_v2/runs/t02_qualify_20261107_002/sampled_initials/t02_92901_000.npz \
      --instance-from experiments/grow_up_harness_v2/runs/t02_qualify_20261107_002/t02_92901_000/positive_visual/episode/instance.json \
      --output experiments/grow_up_harness_v2/runs/t02_worker_budget_<date>_<n>

The schedule replays the qualified recorded targets under the Worker outlet rules
(0.03 rad arm and 0.05 rad hand per command at d = 0.15 s, the fastest legal rate).
No policy, model or success claim: timing only.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2/calibration"))

import grow  # noqa: E402,F401
from harness import grow_loop as L, t02_episode as E, t02_generator as G, tp01  # noqa: E402
from experiments.t0_agent_v1.runtime import CountedPort  # noqa: E402

D = .15
CAPS = {"simulation_s": 180., "commands": 1200, "wall_s": 1200.}
PREDICTION = ("Simulated time and commands sit within about 5% of their caps either side. Physics near 6 wall s per "
              "simulated s plus one render per command should exceed the 1200 s wall cap.")
FALSIFIED_BY = "Projected Worker wall time under 1200 s at the full schedule."


def schedule(start_targets: dict) -> dict:
    events = json.loads((G.SOURCE / "physics_events.json").read_text())[1:]
    actions = [a for p in sorted(G.SOURCE.glob("cup_attempt_*/actions.json")) for a in json.loads(p.read_text())
               if "result" in a and "simulation_seconds" in a["result"]]
    current = dict(start_targets)
    motion = waits = oversize = 0
    motion_s = wait_s = 0.
    for action, event in zip(actions, events, strict=True):
        if event["category"] != "action":
            wait_s += action["arguments"]["seconds"]
            waits += math.ceil(action["arguments"]["seconds"] / .2 - 1e-9)
            continue
        steps = 1
        for name, value in event["joints"].items():
            limit = .05 if "_hand_" in name else .03
            steps = max(steps, math.ceil(abs(value - current[name]) / limit - 1e-9))
            current[name] = value
        moved = len(event["joints"])
        oversize += moved > 14
        motion += steps
        motion_s += steps * D
    return {"motion_commands": motion, "motion_s": motion_s, "wait_commands": waits, "wait_s": wait_s,
            "commands_listing_over_14_joints": oversize, "commands": motion + waits, "simulation_s": motion_s + wait_s}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial", type=Path, required=True)
    parser.add_argument("--instance-from", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    L.write_new(output / "registration.json", {"date": time.strftime("%Y-%m-%d"), "model_calls": 0, "caps": CAPS,
                "step_s": D, "prediction": PREDICTION, "falsification": FALSIFIED_BY})
    episode = output / "episode"
    episode.mkdir()
    instance = json.loads(args.instance_from.read_text())
    L.write_new(episode / "instance.json", instance)
    model_path = ROOT / json.loads((G.SOURCE / "model_reference.json").read_text())["path"]
    robot = tp01.TickRecordedRobot(episode, instance, budget=L.SETTLE_S + 30., scene_path=model_path,
                                   initial_state=args.initial.resolve())
    port = CountedPort(robot)
    robot.advance(L.SETTLE_S, "initial_settling")
    joints = robot.state()["joints"]
    plan = schedule({name: value["target"] for name, value in joints.items()})

    observe_s = []
    for _ in range(5):
        started = time.monotonic()
        observation = E.observe(robot, port)
        observe_s.append(time.monotonic() - started)
    advance_s = []
    for _ in range(25):
        started = time.monotonic()
        robot.advance(.2, "budget_probe")
        advance_s.append(time.monotonic() - started)
    robot.finish()

    per_observe = sum(observe_s) / len(observe_s)
    per_sim_s = sum(advance_s) / (25 * .2)
    projected = plan["simulation_s"] * per_sim_s + plan["commands"] * per_observe
    L.write_new(output / "results.json", {
        "schedule_full_recorded_targets": plan, "caps": CAPS,
        "observe_wall_s": observe_s, "advance_wall_s_per_simulated_s": per_sim_s,
        "projected_worker_wall_s": projected,
        "fits": {"simulation_s": plan["simulation_s"] <= CAPS["simulation_s"],
                 "commands": plan["commands"] <= CAPS["commands"], "wall_s": projected <= CAPS["wall_s"]},
        "cups_visible_in_observation": len(observation["cup_bottoms_m"]),
        "tray_visible_in_observation": observation["tray"] is not None,
        "observation_keys": sorted(observation), "observation_joint_count": len(observation["joints"])})
    print((output / "results.json").read_text())


if __name__ == "__main__":
    main()
