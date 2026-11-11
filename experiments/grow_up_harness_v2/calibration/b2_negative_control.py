"""B2 negative control: a wait-only program must never be credited.

Runs one TP01 initial state with the frozen plant and evaluator, executing
only ``wait`` actions for the frozen program budget. The episode is a real
physics episode with real integration states; the only thing missing is the
task work. If the evaluator reports ``verified_task_success`` here, the
whole acceptance path is broken and P2 must stop before practice.

This is a calibration unit, not an agent episode: it never calls a model and
never counts toward P2 success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.grow_up_harness_v2.harness.ops import TP01_CHAIN_BUDGET_S  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, write_new  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import (  # noqa: E402
    TabletopPlant,
    build_training_scene,
    independent_verify,
)

DATASET = ROOT / "experiments/t0_agent_v1/tabletop_dataset_20261026_003"
CASES = ROOT / "experiments/t0_agent_v1/tabletop_dataset_20261026_002"
REACH = ROOT / "experiments/t0_agent_v1/tp01_reach_dataset_20261026_001"
WAIT_S = 0.2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def case_entry(split: str, instance_id: str, dataset: str) -> tuple[dict, Path]:
    if dataset == "reach":
        for entry in read(REACH / "training_manifest.json")["instances"]:
            if entry["id"] == instance_id:
                return entry, REACH / "train" / instance_id
        raise KeyError(f"{instance_id} not in reach manifest")
    manifest = read(DATASET / split / "manifest.json")
    for entry in manifest["instances"]:
        if entry["id"] == instance_id:
            return entry, CASES / split / "instances" / instance_id
    raise KeyError(f"{instance_id} not in {split} manifest")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", default="TP01_train_000")
    parser.add_argument("--split", default="train")
    parser.add_argument("--dataset", default="tabletop", choices=("tabletop", "reach"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--budget", type=float, default=TP01_CHAIN_BUDGET_S)
    args = parser.parse_args(argv)

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)

    entry, case_dir = case_entry(args.split, args.instance, args.dataset)
    instance = read(case_dir / "instance.json")
    scene = output / "scene.xml"
    model = build_training_scene(instance, scene)

    plant = TabletopPlant(instance, case_dir, model, output, budget=args.budget)
    error = None
    actions = 0
    while not plant.guard and plant.data.time < args.budget - 1e-8:
        response = plant.dispatch({"op": "wait", "duration": WAIT_S})
        if response.get("status") != "EXECUTED":
            error = dict(type="ActionRejected", message=str(response.get("reason") or response.get("status")))
            break
        actions += 1
    if error is None and not plant.guard and plant.data.time < args.budget - 1e-8:
        error = dict(type="CalibrationBudgetExceeded", message="wait loop stopped before the budget")
    runtime = plant.save(error, None, None, actions)
    verdict = independent_verify(output, instance, model, initial_valid=bool(entry["valid_initial_fixture"]))

    checks = {
        "episode_is_physical": runtime["simulation_seconds"] > 0.0,
        "no_joint_commands": all(event["request"].get("op") == "wait" for event in plant.events),
        "negative_control_not_credited": verdict["verified_task_success"] is False,
        "goal_not_satisfied": verdict["goal_satisfied"] is False,
        "initial_state_matches_manifest": sha256_file(case_dir / "initial_state.json") == entry["initial_state_sha256"],
        "evaluator_version": verdict["evaluator_version"],
    }
    summary = {
        "date": "2026-11-03",
        "boundary": "simulation",
        "kind": "calibration_negative_control",
        "instance": args.instance,
        "split": args.split,
        "dataset": args.dataset,
        "budget_s": args.budget,
        "wait_step_s": WAIT_S,
        "actions": actions,
        "simulation_seconds": runtime["simulation_seconds"],
        "initial_state_sha256": entry["initial_state_sha256"],
        "verdict": verdict,
        "checks": checks,
        "passed": all(value is True for key, value in checks.items() if isinstance(value, bool)),
        "episode": relative(output),
    }
    write_new(output / "results.json", summary)
    print(json.dumps({"passed": summary["passed"], "checks": checks}, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
