"""T02 control qualification on sampled initials: no model calls, no agent code.

    MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 "$G1_PYTHON" -B \
      experiments/grow_up_harness_v2/calibration/t02_qualify.py \
      --seed 92901 --count 2 --radius-m 0.002 \
      --output experiments/grow_up_harness_v2/runs/t02_qualify_<date>_<n>

Arms per sampled initial, fixed order: wait, recorded motor targets, visual
engineering. The prediction is written before any physics. Seeds used here are
development seeds and must not be reused as train or held-out seeds.
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

import grow  # noqa: E402,F401  (same import order as grow_t02.py)
from harness import grow_loop as L, t02_episode as E, t02_generator as G  # noqa: E402

CAPS = {"simulation_s": 180., "commands": 1200, "wall_s": 1200.}
ARMS = (("negative_wait", "wait", None),
        ("positive_recorded_motor", "engineering", "recorded_motor_targets"),
        ("positive_visual", "engineering", "visual_engineering"))
PREDICTION = ("Wait fails on every initial. Recorded motor targets are open loop and visual engineering "
              "succeeded on 1 of 3 historical repair_003 initials, so at 2 mm jitter I expect at least one "
              "positive arm to pass on each initial, without assuming which.")
FALSIFIED_BY = "Any wait success voids the batch. An initial where both positive arms fail cannot enter practice."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--radius-m", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    generated = G.generate(args.seed, args.count, args.radius_m, output=args.output)
    L.write_new(args.output / "registration.json", {
        "date": time.strftime("%Y-%m-%d"), "status": "registered_before_physics", "boundary": "MuJoCo simulation",
        "model_calls": 0, "seed_role": "development; consumed by this run", "caps": CAPS, "arms": ARMS,
        "generated": generated, "prediction": PREDICTION, "falsification": FALSIFIED_BY})
    rows = []
    void = False
    for task in generated["tasks"]:
        for name, mode, reference in ARMS:
            plan = {"plant": generated["plant"], "positive_reference": reference}
            result = E.Episode(args.output / task["task_id"] / name, plan, CAPS, task).run(task["public"], mode=mode)
            verdict = json.loads((args.output / task["task_id"] / name / "verdict.json").read_text())
            row = {"task": task["task_id"], "arm": name, "success": result["success"], "error": result["error"],
                   "supported_cups": result["facts"]["supported_cup_count"],
                   "terminal_hold_s": result["facts"]["terminal_hold_s"], "guard": result["facts"]["guard"],
                   "initial_valid": verdict["initial_valid"], "commands": result["commands"],
                   "simulation_s": result["simulation_seconds"], "wall_s": result["wall_seconds"]}
            rows.append(row)
            print(json.dumps(row), flush=True)
            if name == "negative_wait" and result["success"]:
                void = True
                break
        if void:
            break
    L.write_new(args.output / "results.json", {"status": "void" if void else "complete", "rows": rows})


if __name__ == "__main__":
    main()
