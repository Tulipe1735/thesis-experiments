"""F0: the engineering reference over the eight TP01 training states.

This is the feasibility gate. It runs the registered engineering recipe
(``reuse_grasp.BASELINE``) once per training state, at 60 s per episode, with
the frozen plant and evaluator. It never calls a model, and its successes are
calibration, not agent achievements.

Output: one episode folder per state, plus ``results.json`` with the verdict
per state and the resulting S* (lowest-id success) or ``FEASIBILITY_GATE_FAILED``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "grasp_optimization") not in sys.path:
    sys.path.insert(0, str(ROOT / "grasp_optimization"))

from experiments.t0_agent_v1.common import relative, write_new  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import build_training_scene  # noqa: E402
from experiments.t0_agent_v1.train_tp01 import training_cases  # noqa: E402
from experiments.t0_agent_v1 import reuse_grasp  # noqa: E402


def selected(only: list[str] | None) -> list[dict]:
    rows = []
    for index, case in enumerate(training_cases()):
        instance_id = case["instance"]["id"]
        if only and instance_id not in only:
            continue
        rows.append(
            {
                "alias": f"R{index:02d}",
                "id": instance_id,
                "instance": case["instance"],
                "task": case["task"],
                "case_path": case["case_path"],
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--budget", type=float, default=60.0)
    parser.add_argument("--instance", action="append", default=None)
    args = parser.parse_args(argv)

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = selected(args.instance)
    if not rows:
        raise SystemExit("no matching TP01 instances")

    episodes = []
    scenes = output / "scenes"
    scenes.mkdir(parents=True, exist_ok=True)
    for row in rows:
        # reuse_grasp.execute creates the episode folder itself (exist_ok=False),
        # so the scene has to live outside it.
        folder = output / row["id"]
        scene = scenes / f"{row['id']}.xml"
        build_training_scene(row["instance"], scene)
        case = {
            "alias": row["alias"],
            "instance": row["instance"],
            "case_path": row["case_path"],
            "task": row["task"],
        }
        print("F0_START", row["id"], flush=True)
        try:
            verdict = reuse_grasp.execute(scene, case, folder, reuse_grasp.BASELINE, budget=args.budget)
            row_out = dict(
                id=row["id"],
                alias=row["alias"],
                success=bool(verdict.get("verified_task_success")),
                error=verdict.get("error"),
                simulation_seconds=verdict.get("simulation_seconds"),
                folder=relative(folder),
            )
        except Exception as exc:  # keep the failure; never retry silently
            row_out = dict(
                id=row["id"],
                alias=row["alias"],
                success=False,
                error={"type": type(exc).__name__, "message": str(exc)[:600]},
                folder=relative(folder),
            )
            print("F0_ERROR", row["id"], type(exc).__name__, str(exc)[:200], flush=True)
        episodes.append(row_out)
        write_new(output / f"{row['id']}.json", row_out)
        print("F0_RESULT", row["id"], row_out["success"], row_out["error"], flush=True)

    winners = [row["id"] for row in episodes if row["success"]]
    summary = {
        "date": "2026-11-03",
        "boundary": "simulation",
        "kind": "F0_engineering_reference_gate",
        "budget_s": args.budget,
        "episodes": episodes,
        "successes": len(winners),
        "s_star": winners[0] if winners else None,
        "status": "FEASIBILITY_GATE_PASSED" if winners else "FEASIBILITY_GATE_FAILED",
        "counted_as_agent_success": False,
        "recipe": reuse_grasp.BASELINE,
    }
    write_new(output / "results.json", summary)
    print("F0_SUMMARY", json.dumps({k: summary[k] for k in ("successes", "s_star", "status")}), flush=True)
    return 0 if winners else 1


if __name__ == "__main__":
    raise SystemExit(main())
