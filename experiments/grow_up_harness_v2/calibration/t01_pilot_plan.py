"""Freeze the four-arm T01 development pilot layout without running its arms."""

import argparse
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from experiments.t0_agent_v1.common import read, relative, sha, write_new
from t01_controls import SUITE


ARMS = {
    "S0C0": {"skill_cards": False, "reusable_code": False},
    "S1C0": {"skill_cards": True, "reusable_code": False},
    "S0C1": {"skill_cards": False, "reusable_code": True},
    "S1C1": {"skill_cards": True, "reusable_code": True},
}
CASE_IDS = ("position_280100", "orientation_280200", "asset_280300", "joint_280400")
SEED = 20261104


def make_plan(controls_path: Path) -> dict:
    controls = read(controls_path)
    if not controls["passed"] or [
        (row["arm"], row["verified_success"]) for row in controls["controls"]
    ] != [("B2_wait", False), ("R_engineering", True)]:
        raise ValueError("T01 evaluator controls must pass before designing the pilot")
    if len({row["actual_initial_state_sha256"] for row in controls["controls"]}) != 1:
        raise ValueError("Evaluator controls did not use the same initial state")
    registration_path = SUITE / "registration.json"
    registration = read(registration_path)
    rng = random.Random(SEED)
    cases = [next(row for row in registration["cases"] if row["id"] == case) for case in CASE_IDS]
    rng.shuffle(cases)
    arm_order = list(ARMS)
    rng.shuffle(arm_order)
    slots = []
    for block, case in enumerate(cases):
        saved = SUITE / "cases" / case["id"] / "episode" / "initial_state.npz"
        model = registration["models"][case["model_key"]]
        if sha(ROOT / model["path"]) != model["sha256"]:
            raise ValueError(f"Model changed for {case['id']}")
        initial = {"path": relative(saved), "sha256": sha(saved)}
        for position, arm in enumerate(arm_order[block:] + arm_order[:block]):
            slots.append({
                "slot": len(slots) + 1, "case_id": case["id"], "block": block + 1,
                "position_within_block": position + 1, "arm": arm,
                "initial_state": initial, "model": model, "instance": case["instance"],
            })
    return {
        "task": "T01", "boundary": "simulation", "split": "consumed_development",
        "status": "layout_frozen_not_authorized_for_execution",
        "purpose": "integration pilot only; no transfer or hypothesis test",
        "order_seed": SEED, "arms": ARMS, "slots": slots,
        "source_registration_sha256": sha(registration_path),
        "simulation_budget_s": registration["simulation_budget_s"],
        "evaluator_sha256": sha(ROOT / "experiments/t0_agent_v1/tray_verify.py"),
        "controls": {"path": relative(controls_path), "sha256": sha(controls_path)},
        "before_execution": [
            "qualify one isolated backend for every arm",
            "freeze exact model, common action/observation contracts, card and code artifacts",
            "set equal call/token/wall budgets and record a complete new execution registration",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = make_plan(args.controls.resolve())
    args.output.mkdir(parents=True, exist_ok=False)
    write_new(args.output / "plan.json", plan)
