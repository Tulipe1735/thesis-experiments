"""Regenerate TP03 cases with the robot standing within arm reach.

The stock generator stands the robot 0.66 m from the table edge, so 0/18 table
cells fall inside the 0.45 m forward reach. This launcher declares two changes
before any run:

- stance moved to pelvis y = 0.41 m over the same table;
- target cells restricted to the four near-row cells that become reachable.

Nothing else is touched: same assets, same sampler, same evaluator.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import experiments.t0_agent_v1.tabletop_dataset as dataset  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402

STANCE_Y_M = 0.41
NEAR_CELLS = ("table_2_1", "table_2_2", "table_2_3", "table_2_4")
TEMPLATE = "TP03"
SEEDS = (70001, 70002, 70003, 70004)


def build_case(slot, output):
    instance = dataset.make_instance(slot)
    target = next(item for item in instance["objects"] if item["is_target"])
    if target["position_cell"] not in NEAR_CELLS:
        raise ValueError(f"target landed outside the declared cells: {target['position_cell']}")
    stance = instance["robot"]["stance"]
    stance["pelvis_table_xy_m"] = [0.0, STANCE_Y_M]
    stance["floor_marker_rectangle_xy_m"] = [-0.25, 0.25, STANCE_Y_M - 0.25, STANCE_Y_M + 0.25]
    stance["stance_adjusted_for"] = "left-arm forward reach 0.45 m"
    output.mkdir(parents=True, exist_ok=False)
    model = dataset.compile_scene(instance, output / "pantry_G1.xml", native=True)
    shutil.copyfile(output / "pantry_G1.xml", output / "qualification.xml")
    fixture = dataset.qualify(instance, model)
    write_new(output / "initial_state.json", fixture)
    write_new(output / "instance.json", instance)
    write_new(output / "task.json", dataset.public_task(instance))
    return {
        "id": instance["id"],
        "template_id": instance["template_id"],
        "seed": instance["seed"],
        "split": instance["split"],
        "valid_initial_fixture": fixture["valid_initial_fixture"],
        "rejection_reasons": fixture["rejection_reasons"],
        "cup_cell": target["position_cell"],
        "cup_position_m": target["position_m"],
        "evaluator_instance": str(Path(output.name) / "instance.json"),
    }


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    original_cells = dataset.position_cells
    near = [cell for cell in original_cells() if cell["id"] in NEAR_CELLS]
    dataset.position_cells = lambda: near
    rows = []
    try:
        for index, seed in enumerate(SEEDS):
            slot = dict(id=f"{TEMPLATE}_reach_{index:03}", template=TEMPLATE, stratum="train",
                        index=0, seed=seed, split="train", asset_partition="train",
                        position_partition="train")
            rows.append(build_case(slot, output / slot["id"]))
            status = "ok" if rows[-1]["valid_initial_fixture"] else rows[-1]["rejection_reasons"]
            print(f"{slot['id']} cell={rows[-1]['cup_cell']} {status}", flush=True)
    finally:
        dataset.position_cells = original_cells
    write_new(output / "manifest.json", {
        "split": "train", "frozen": True, "family": dataset.FAMILY,
        "template": TEMPLATE,
        "generator_version": dataset.VERSION,
        "changes_before_run": {
            "stance_pelvis_table_xy_m": [0.0, STANCE_Y_M],
            "target_cells": list(NEAR_CELLS),
            "reason": "stock stance puts 0/18 cells inside the 0.45 m forward reach; this stance reaches 4/18",
        },
        "instances": rows,
    })
    write_new(output / "registration.json", {
        "date": "2026-11-05", "boundary": "simulation", "kind": "generated_tp03_reachable_stance",
        "generator": relative(Path(dataset.__file__)),
        "generator_sha256": sha(Path(dataset.__file__)),
        "launcher": relative(Path(__file__)), "launcher_sha256": sha(Path(__file__)),
        "model_requests": 0,
    })
    return {"cases": len(rows), "valid": sum(1 for r in rows if r["valid_initial_fixture"])}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.output.resolve()), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
