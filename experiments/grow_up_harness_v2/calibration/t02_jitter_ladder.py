"""One rung of the T02 jitter ladder: frozen replay artifact on freshly sampled initials.

    MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 "$G1_PYTHON" -B \
      experiments/grow_up_harness_v2/calibration/t02_jitter_ladder.py \
      --seed 92201 --count 3 --radius-m 0.005 --prediction "..." --falsification "..." \
      --output experiments/grow_up_harness_v2/runs/t02_ladder_5mm_<date>_<n>

No model calls and no store writes. Wait runs on the first task only; a wait success
voids the rung. The visual positive and the replay both run on every task: a failed
positive is reported beside the replay rather than skipping it, because this measures
where the replay fails, not agent practice. A replay failure on a task whose positive
also failed cannot be attributed to the replay.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2/calibration"))

import grow  # noqa: E402,F401
from harness import artifact_v2 as A, grow_loop as L, t02_episode as E, t02_generator as G  # noqa: E402

CAPS = {"simulation_s": 240., "commands": 1650, "wall_s": 1800.}
TREE = ROOT / "experiments/grow_up_harness_v2/artifacts_v2/task_tree_v2.json"
STORE = ROOT / "experiments/grow_up_harness_v2/runs/t02_replay_store_20261107_001/store"
ARTIFACT = "t02_three_cup_replay@8398f5db4447"


def row(task, arm, folder, result):
    verdict = json.loads((folder / "verdict.json").read_text())
    cups = {name: {key: cup[key] for key in ("footprint_margin_m", "tray_floor_support_N", "hand_contact_N",
                                             "cup_tilt_deg", "cup_position_tray_m")}
            for name, cup in verdict["final"]["cups"].items()}
    return {"task": task["task_id"], "arm": arm, "success": result["success"], "error": result["error"],
            "label": result["facts"]["rule_label"], "guard": result["facts"]["guard"],
            "supported_cups": result["facts"]["supported_cup_count"],
            "terminal_hold_s": result["facts"]["terminal_hold_s"], "initial_valid": verdict["initial_valid"],
            "commands": result["commands"], "simulation_s": result["simulation_seconds"],
            "wall_s": result["wall_seconds"], "final_cups": cups}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--radius-m", type=float, required=True)
    parser.add_argument("--prediction", required=True)
    parser.add_argument("--falsification", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)

    store = A.Store(STORE, json.loads(TREE.read_text()))
    if not store.verify()[ARTIFACT]:
        raise RuntimeError("stored projection does not recompute")
    code = store.code(ARTIFACT)
    generated = G.generate(args.seed, args.count, args.radius_m, output=output)
    L.write_new(output / "registration.json", {
        "date": time.strftime("%Y-%m-%d"), "status": "registered_before_physics", "boundary": "MuJoCo simulation",
        "column": "engineering", "model_calls": 0, "store_writes": 0, "caps": CAPS,
        "artifact": ARTIFACT, "code_sha256": A.sha_text(code), "generated": generated,
        "baselines": {"negative": "wait on the first task; success voids the rung", "positive": "visual engineering on every task",
                      "fallback": "none", "original_failure": "none at this radius",
                      "treatment": "frozen replay artifact through the Worker, no retry"},
        "prediction": args.prediction, "falsification": args.falsification})

    probe = output / "geometry_probe"
    probe.mkdir()
    instance = json.loads((G.SOURCE / "instance.json").read_text())
    L.write_new(probe / "instance.json", instance)
    robot = L.SavedInitialRobot(probe, instance, budget=1., scene_path=ROOT / generated["plant"]["path"],
                                initial_state=G.SOURCE / "initial_state.npz")
    geometry = L.body_geometry(robot)
    robot.finish()

    rows = []
    void = False
    with (output / "rows.jsonl").open("x", encoding="utf-8") as log:
        def run(task, arm, reference, **kwargs):
            folder = output / task["task_id"] / arm
            plan = {"plant": generated["plant"], "body_geometry": geometry, "positive_reference": reference}
            result = E.Episode(folder, plan, CAPS, task).run(task["public"], **kwargs)
            entry = row(task, arm, folder, result)
            rows.append(entry)
            log.write(json.dumps(entry) + "\n")
            log.flush()
            return entry

        for index, task in enumerate(generated["tasks"]):
            if index == 0 and run(task, "negative_wait", None, mode="wait")["success"]:
                void = True
                break
            run(task, "positive_visual", "visual_engineering", mode="engineering")
            params = {key: task["public"][key] for key in G.FAMILY["contract"]["params"]}
            run(task, "replay_worker", None, mode="worker", source=code, task_input=params)
    replay = [r for r in rows if r["arm"] == "replay_worker"]
    positive = [r for r in rows if r["arm"] == "positive_visual"]
    L.write_new(output / "results.json", {
        "status": "void" if void else "complete", "radius_m": args.radius_m,
        "replay_success": sum(r["success"] for r in replay), "replay_tasks": len(replay),
        "positive_success": sum(r["success"] for r in positive), "positive_tasks": len(positive),
        "invalid_initials": sum(not r["initial_valid"] for r in replay), "rows": rows})


if __name__ == "__main__":
    main()
