"""One development Worker episode of a stored artifact's code projection on a consumed T02 initial.

    MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 "$G1_PYTHON" -B \
      experiments/grow_up_harness_v2/calibration/t02_worker_dev.py \
      --store experiments/grow_up_harness_v2/runs/t02_replay_store_20261107_001/store \
      --artifact t02_three_cup_replay@8398f5db4447 \
      --qualify experiments/grow_up_harness_v2/runs/t02_qualify_20261107_002 --task-index 0 \
      --prediction "..." --falsification "..." \
      --output experiments/grow_up_harness_v2/runs/t02_worker_dev_<date>_<n>

Development evidence only: the store is read, never written, and the initial is
already consumed. Not a train, held-out or generalization result.
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


def main():
    parser = argparse.ArgumentParser()
    for name in ("--artifact", "--prediction", "--falsification"):
        parser.add_argument(name, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--qualify", type=Path, required=True)
    parser.add_argument("--task-index", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    store = A.Store(args.store.resolve(), json.loads(TREE.read_text()))
    if not store.verify()[args.artifact]:
        raise RuntimeError("stored projection does not recompute")
    code = store.code(args.artifact)
    generated = json.loads((args.qualify / "registration.json").read_text())["generated"]
    task = generated["tasks"][args.task_index]
    L.write_new(output / "registration.json", {
        "date": time.strftime("%Y-%m-%d"), "status": "registered_before_physics", "boundary": "MuJoCo simulation",
        "column": "engineering", "role": "development; consumed initial", "model_calls": 0, "caps": CAPS,
        "caps_note": "post-change caps; registered v1 was 180 s / 1200 commands / 1200 s wall. Wall raised after t02_worker_dev_20261107_001 hit LOCAL_WALL_CAP at 184 simulated s",
        "artifact": args.artifact, "code_sha256": A.sha_text(code), "task": task["task_id"],
        "prediction": args.prediction, "falsification": args.falsification})
    folder = output / "geometry_probe"
    folder.mkdir()
    instance = json.loads((G.SOURCE / "instance.json").read_text())
    L.write_new(folder / "instance.json", instance)
    robot = L.SavedInitialRobot(folder, instance, budget=1., scene_path=ROOT / generated["plant"]["path"],
                                initial_state=G.SOURCE / "initial_state.npz")
    geometry = L.body_geometry(robot)
    robot.finish()
    plan = {"plant": generated["plant"], "body_geometry": geometry}
    params = {k: task["public"][k] for k in G.FAMILY["contract"]["params"]}
    result = E.Episode(output / "episode", plan, CAPS, task).run(task["public"], mode="worker", source=code, task_input=params)
    print(json.dumps({k: result[k] for k in ("success", "error", "commands", "worker_calls", "simulation_seconds", "wall_seconds", "facts")}, indent=1))


if __name__ == "__main__":
    main()
