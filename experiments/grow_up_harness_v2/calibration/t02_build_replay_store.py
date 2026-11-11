"""Build the artifact.v2 store for T02: three per-cup leaves and one composite.

    "$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/t02_build_replay_store.py \
      --output experiments/grow_up_harness_v2/runs/t02_replay_store_<date>_<n>

No physics and no model. The composite's code projection is walked to completion
against a target-tracking stub, every action through the same rule check the
episode uses. That proves the interface and the budget arithmetic, not the task.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import artifact_v2 as A, grow_loop as L, t02_generator as G, t02_replay as R  # noqa: E402
from harness.agent import check_source  # noqa: E402
from harness.task_generator import _sha  # noqa: E402

TREE = ROOT / "experiments/grow_up_harness_v2/artifacts_v2/task_tree_v2.json"
AUTHOR = "engineering:recorded_motor_targets_2401"


def walk(code: str, start: dict) -> dict:
    """Run act to done; targets follow commands exactly. Counts commands and simulated time."""
    namespace = {}
    exec(compile(code, "<projection>", "exec"), namespace)
    state = namespace["init"]({})
    joints = {name: {"q": value, "dq": 0., "target": value} for name, value in start.items()}
    commands, simulated, final = 0, 0., None
    while True:
        result = namespace["act"]({"joints": joints}, {"object_count": 3., "hold_s": 1.}, state)
        state = json.loads(json.dumps(result["state"]))
        action = L.check_action(result["action"], {"joints": joints})
        if action["op"] == "done":
            return {"commands": commands, "simulation_s": simulated,
                    "final_targets": {name: value["target"] for name, value in joints.items()}}
        if action["op"] == "fail":
            raise ValueError(action["reason"])
        if action["op"] == "set_joints":
            for name, value in action["targets"].items():
                joints[name]["target"] = value
        commands += 1
        simulated += action["duration"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    store = A.Store(output / "store", json.loads(TREE.read_text()))
    plant = json.loads((G.SOURCE / "model_reference.json").read_text())["path"]
    scope = {"initial_sha256": [_sha(G.SOURCE / "initial_state.npz")], "plant_sha256": _sha(ROOT / plant)}
    leaves = []
    for number, plan in enumerate(R.segments(G.SOURCE), 1):
        source = R.leaf_source(plan)
        digest = store.put_source(source)
        post = f"cup_{number}_in_tray"
        leaves.append(store.add({
            "schema": A.SCHEMA, "kind": "leaf", "name": f"t02_cup{number}_replay", "task_node": "T02",
            "summary": f"Open-loop replay of recorded engineering targets for cup {number}, retimed to the Worker "
                       "joint limits; reads no cup or tray estimate.",
            "contract": {"pre": ["hand_empty", "guard_clear"] + ([f"cup_{number - 1}_in_tray"] if number > 1 else []),
                         "post": [post], "params": {}, "failure_codes": ["UNSAFE", "BUDGET", "NOT_HELD"]},
            # A distinct family keeps one-cup leaves out of whole-task FAST candidates.
            "scope": {"task_family": "t02_cup_replay_v1", **scope},
            "provenance": {"author": AUTHOR, "parents": [], "created_on": "t02_replay_store",
                           "note": "engineering column; open loop; source episode 2401 of tray_20261025_repair_003"},
            "implementation": {"language": "python", "source_sha256": digest}}))
    composite = store.add({
        "schema": A.SCHEMA, "kind": "composite", "name": "t02_three_cup_replay", "task_node": "T02",
        "summary": "Collect three cups by running the three per-cup replay leaves in order. Open loop; "
                   "validated only as far as its ledger shows.",
        "contract": G.FAMILY["contract"],
        "scope": {"task_family": G.FAMILY["task_family"], **scope},
        "provenance": {"author": AUTHOR, "parents": [], "created_on": "t02_replay_store",
                       "note": "engineering column; composite of per-cup replay leaves"},
        "ir": [{"use": leaf, "params": {}} for leaf in leaves]})
    code = store.code(composite)
    check_source(code)
    with (G.SOURCE / "physics_events.json").open() as handle:
        recorded = {}
        for event in json.load(handle):
            recorded.update(event.get("joints", {}))
    start = {name: 0. for name in recorded}
    walked = walk(code, start)
    errors = {name: abs(walked["final_targets"][name] - recorded[name]) for name in recorded}
    report = {
        "date": time.strftime("%Y-%m-%d"), "boundary": "no physics; interface and arithmetic only",
        "column": "engineering", "leaves": leaves, "composite": composite,
        "code_bytes": len(code.encode()), "projections_recompute": store.verify(),
        "walk_from_zero_targets": {k: walked[k] for k in ("commands", "simulation_s")},
        "max_final_target_error_rad": max(errors.values()),
    }
    if not all(report["projections_recompute"].values()) or report["max_final_target_error_rad"] > 1e-4:
        raise RuntimeError(f"store failed its own check: {report}")
    store.snapshot("built")
    L.write_new(output / "build.json", report)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
