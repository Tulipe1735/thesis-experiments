"""Load the pinned SmolVLA checkpoint and run one inference on a saved T01 frame.

Runs in the separate `~/.venvs/g1-vla` interpreter (torch + lerobot 0.4.4); it does
not import MuJoCo. The point is to prove the runtime loads on this machine and that
the native postprocessor returns finite (1,50,28) absolute radians, not to execute a
robot. Robot execution is `t01_vla_policy.py`.

Weight staging comes from `grasp_optimization/smolvla_preview.py`; the checkpoint and
the SmolVLM2 processor live under `$G1_VLA_WORK` (default `~/vla-work`).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "grasp_optimization")]
os.environ.setdefault("G1_VLA_WORK", str(Path.home() / "vla-work"))
os.environ["MUJOCO_GL"] = "egl"

from experiments.t0_agent_v1.common import relative, write_new  # noqa: E402

INSTRUCTION = "Pick up the cup and place it on the tray."


def load_observation(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    joints = {name: row["q"] for name, row in raw["body_state"]["joints"].items()}
    return {"head_rgb_path": raw["head_rgb_path"], "joints_q_rad": joints,
            "observation_id": raw["observation_id"], "simulation_seconds": raw["simulation_seconds"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--predictions", type=int, default=2)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    observation = load_observation(args.observation.resolve())
    write_new(output / "registration.json", {
        "date": "2026-11-05", "boundary": "simulation", "kind": "vla_smoke",
        "interpreter": sys.executable,
        "checkpoint": "kiteml/G1-ego-test-smolvla",
        "revision": "cf2f88ba6d5db3f3647b453438a0a1904e07919f",
        "initial_state": None,
        "source_observation": relative(args.observation),
        "device": args.device, "predictions": args.predictions,
        "instruction": INSTRUCTION,
        "prediction": ("loads under 8 GB and returns finite (1,50,28) absolute radians; "
                       "falsified by OOM, import error, or range violations above the radian bounds"),
        "motor_execution": False,
    })
    report = {"status": "NOT_STARTED", "inference_calls": 0, "motor_execution": False}
    started = time.monotonic()
    try:
        from smolvla_preview import LocalSmolVLA
        policy = LocalSmolVLA(args.device)
        report["load_seconds"] = round(time.monotonic() - started, 2)
        report["checkpoint_path"] = str(policy.checkpoint_path)
        calls = []
        for index in range(args.predictions):
            result, actions = policy.predict(observation, INSTRUCTION)
            path = output / f"actions_{index + 1:02}.npy"
            import numpy as np
            np.save(path, actions)
            calls.append({"index": index + 1, "action_file": relative(path), **result})
        report.update(status="REAL_INFERENCE_OK_MOTOR_EXECUTION_DISABLED",
                      inference_calls=policy.calls, calls=calls, memory=policy.memory())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        report.update(status="LOCAL_INFERENCE_ERROR", error_type=type(exc).__name__,
                      error=str(exc)[:3000],
                      memory=None)
    report["wall_seconds"] = round(time.monotonic() - started, 1)
    write_new(output / "result.json", report)
    print(json.dumps({key: report[key] for key in ("status", "inference_calls", "wall_seconds")},
                     ensure_ascii=False))
    return 0 if report["status"] == "REAL_INFERENCE_OK_MOTOR_EXECUTION_DISABLED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
