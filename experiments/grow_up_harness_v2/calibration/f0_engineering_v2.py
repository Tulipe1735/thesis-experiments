"""F0 v2: the frozen adaptive engineering reference over the four reach states.

F0 v1 (``f0_engineering.py``) ran the base ``reuse_grasp`` recipe over the eight
``tabletop_dataset_20261026_003`` train states. All eight sit 0.65-0.96 m in
front of the pelvis, while the left arm tops out near 0.50 m at counter height,
and the base recipe's route fails even on reachable targets. F0 v2 keeps the
gate's meaning and changes the two things v1 got wrong:

* the states are the four frozen, human-authorized ``tp01_reach_dataset_20261026_001``
  cases, whose targets sit in the prior-success box fixed before any outcome;
* the reference is the exact 2026-10-26 adaptive module that produced the three
  registered successes, with its registered recipe, at the 120 s calibration cap
  that module was registered under.

Successes here are calibration, not agent achievements. Failures are preserved.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "grasp_optimization") not in sys.path:
    sys.path.insert(0, str(ROOT / "grasp_optimization"))

from experiments.t0_agent_v1.training_runtime import ensure_runtime  # noqa: E402
ensure_runtime()
from experiments.t0_agent_v1.common import relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.reach_training_initials import load_cases  # noqa: E402

DATASET = ROOT / "experiments/t0_agent_v1/tp01_reach_dataset_20261026_001"
REFERENCE = ROOT / (
    "experiments/t0_agent_v1/tp01_adaptive_dev_20261026_015/"
    "frozen_sources/experiments/t0_agent_v1/adaptive_reuse_grasp.py"
)
RECIPE_SOURCE = ROOT / "experiments/t0_agent_v1/tp01_adaptive_dev_20261026_015/registration.json"
BUDGET_S = 120.0
EVALUATOR_VERSION = "tabletop-predicates-v1"


def load_reference():
    """Load the frozen adaptive module into the real package so relatives resolve."""
    spec = importlib.util.spec_from_file_location(
        "experiments.t0_agent_v1.adaptive_reuse_grasp_015", REFERENCE
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--budget", type=float, default=BUDGET_S)
    parser.add_argument("--case", action="append", default=None)
    args = parser.parse_args(argv)

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    reference = load_reference()
    recipe = json.loads(RECIPE_SOURCE.read_text(encoding="utf-8"))["recipe"]
    cases = [case for case in load_cases(DATASET) if not args.case or case["alias"] in args.case]
    if not cases:
        raise SystemExit("no matching reach cases")

    episodes = []
    for case in cases:
        alias = case["alias"]
        folder = output / alias
        scene = DATASET / "scenes" / (alias + ".xml")
        print("F0V2_START", alias, case["instance"]["id"], flush=True)
        try:
            verdict = reference.execute_adaptive(scene, case, folder, recipe, budget=args.budget)
            row = dict(
                alias=alias,
                id=case["instance"]["id"],
                parent_instance=case["instance"].get("parent_instance"),
                target_category=case["task"]["target_category"],
                success=bool(verdict.get("verified_task_success")),
                error=verdict.get("error"),
                simulation_seconds=verdict.get("simulation_seconds"),
                low_level_commands=verdict.get("low_level_commands"),
                folder=relative(folder),
                scene_sha256=sha(scene),
                initial_state_sha256=case["record"]["initial_state_sha256"],
            )
        except Exception as exc:  # keep the failure; never retry silently
            row = dict(
                alias=alias,
                id=case["instance"]["id"],
                parent_instance=case["instance"].get("parent_instance"),
                target_category=case["task"]["target_category"],
                success=False,
                error={"type": type(exc).__name__, "message": str(exc)[:600]},
                folder=relative(folder),
                scene_sha256=sha(scene),
                initial_state_sha256=case["record"]["initial_state_sha256"],
            )
            print("F0V2_ERROR", alias, type(exc).__name__, str(exc)[:200], flush=True)
        verification = folder / "independent_verification.json"
        if verification.exists():
            saved = json.loads(verification.read_text(encoding="utf-8"))
            row.update(
                goal_satisfied=saved.get("goal_satisfied"),
                terminal_stable_s=saved.get("terminal_simultaneous_stable_s"),
                evaluator_version=saved.get("evaluator_version"),
            )
        episodes.append(row)
        write_new(output / f"{alias}.json", row)
        print("F0V2_RESULT", alias, row["success"], row.get("error"), flush=True)

    winners = [row for row in episodes if row["success"]]
    summary = {
        "date": "2026-11-03",
        "boundary": "simulation",
        "kind": "F0_engineering_reference_gate_v2",
        "dataset": relative(DATASET),
        "dataset_freeze_sha256": sha(DATASET / "freeze_manifest.json"),
        "reference_module": relative(REFERENCE),
        "reference_sha256": sha(REFERENCE),
        "recipe_source": relative(RECIPE_SOURCE),
        "recipe_sha256": sha(RECIPE_SOURCE),
        "recipe": recipe,
        "budget_s": args.budget,
        "evaluator_version": EVALUATOR_VERSION,
        "episodes": episodes,
        "successes": len(winners),
        "s_star": winners[0]["id"] if winners else None,
        "status": "FEASIBILITY_GATE_PASSED" if winners else "FEASIBILITY_GATE_FAILED",
        "counted_as_agent_success": False,
    }
    write_new(output / "results.json", summary)
    print("F0V2_SUMMARY", json.dumps({k: summary[k] for k in ("successes", "s_star", "status")}), flush=True)
    return 0 if winners else 1


if __name__ == "__main__":
    raise SystemExit(main())
