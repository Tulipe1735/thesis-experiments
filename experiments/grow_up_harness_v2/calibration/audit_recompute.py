"""Recompute the 16 audited TP01 training verdicts with the frozen wrapper.

The audited episodes predate the v2 harness. This script reads them without
writing: it rebuilds each scene from the frozen instance, replays the saved
integration states through the same snapshot and predicate code the evaluator
uses, and compares the verdict with the one already on disk.

A mismatch means the v2 evaluator wiring changed behaviour; stop and fix the
wrapper before touching the runtime.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "grasp_optimization") not in sys.path:
    sys.path.insert(0, str(ROOT / "grasp_optimization"))

from experiments.t0_agent_v1.common import read, relative, write_new  # noqa: E402
from experiments.t0_agent_v1.training_runtime import ensure_runtime  # noqa: E402
ensure_runtime()
import mujoco  # noqa: E402
from experiments.t0_agent_v1.diversity_predicates import snapshot  # noqa: E402
from experiments.t0_agent_v1.tabletop_predicates import evaluate_trace  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import (  # noqa: E402
    build_training_scene,
    configure_robot,
    set_left_hand_impedance,
)
from experiments.t0_agent_v1.train_tp01 import training_cases  # noqa: E402

TRAINING = ROOT / "experiments/t0_agent_v1/tp01_training_20261026_003"
AUDIT = TRAINING / "audit_20261026_001/verification.json"


def recompute(folder: Path, case: dict, scene: Path) -> dict:
    build_training_scene(case["instance"], scene)
    model = mujoco.MjModel.from_xml_path(str(scene))
    configure_robot(model)
    config_path = folder / "left_hand_impedance.json"
    if config_path.exists():
        config = read(config_path)
        applied = set_left_hand_impedance(model, config["kp"], config["kd"])
        if applied != config:
            raise ValueError("Recorded motor configuration differs")
    runtime = read(folder / "execution.json")
    initial = read(folder / "initial_pose.json")
    data = mujoco.MjData(model)
    rows = []
    with np.load(folder / "integration_states.npz", allow_pickle=False) as trace:
        for state in trace["integration_state"]:
            mujoco.mj_setState(model, data, state, mujoco.mjtState.mjSTATE_INTEGRATION)
            mujoco.mj_forward(model, data)
            rows.append(snapshot(model, data, case["instance"], base=initial["base_reference"]))
    return evaluate_trace(
        case["instance"],
        rows,
        initial_valid=True,
        execution_error=runtime["execution_error"],
        protection=runtime["guard"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    scenes = output / "scenes"
    scenes.mkdir()

    audit = read(AUDIT)
    rows, mismatches = [], []
    for split in ("practice_v1", "practice_v2"):
        for case in training_cases():
            alias = case["alias"]
            folder = TRAINING / split / alias
            saved = read(folder / "independent_verification.json")
            scene = scenes / f"{split}_{alias}.xml"
            result = recompute(folder, case, scene)
            match = (
                bool(result["verified_task_success"]) is bool(saved["verified_task_success"])
                and bool(result["goal_satisfied"]) is bool(saved["goal_satisfied"])
            )
            row = dict(
                split=split,
                alias=alias,
                instance=case["instance"]["id"],
                saved_success=bool(saved["verified_task_success"]),
                replay_success=bool(result["verified_task_success"]),
                saved_goal=bool(saved["goal_satisfied"]),
                replay_goal=bool(result["goal_satisfied"]),
                match=match,
                folder=relative(folder),
            )
            rows.append(row)
            if not match:
                mismatches.append(row)
            print("AUDIT", split, alias, "match" if match else "MISMATCH", flush=True)

    summary = {
        "date": "2026-11-03",
        "boundary": "simulation",
        "kind": "audited_episode_recompute",
        "audit": relative(AUDIT),
        "audit_claims_reproduced": audit["checks"]["all_16_verdicts_independently_reproduced"],
        "rows": rows,
        "total": len(rows),
        "matches": sum(1 for row in rows if row["match"]),
        "mismatches": mismatches,
        "all_match": not mismatches,
        "read_only": True,
    }
    write_new(output / "results.json", summary)
    print(f"AUDIT_SUMMARY {summary['matches']}/{summary['total']} match", flush=True)
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
