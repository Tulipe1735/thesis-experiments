"""Build the T02 store v2: per cup a place leaf and a retreat leaf, and one composite of all six.

    "$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/t02_build_split_store.py \
      --output experiments/grow_up_harness_v2/runs/t02_split_store_<date>_<n>

Same recorded targets as runs/t02_replay_store_20261107_001, split at the recorded
pelvis_backward_tray_retreat_01 so a proposer can replace one cup's retreat while
reusing the rest. All seven artifacts share the whole-task family, so FAST tries the
composite and SLOW sees every leaf's code. No physics, no model.
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

from harness import artifact_v2 as A, grow_loop as L, t02_generator as G, t02_replay as R  # noqa: E402
from harness.agent import check_source  # noqa: E402
from harness.task_generator import _sha  # noqa: E402
from t02_build_replay_store import walk  # noqa: E402

TREE = ROOT / "experiments/grow_up_harness_v2/artifacts_v2/task_tree_v2.json"
AUTHOR = "engineering:recorded_motor_targets_2401"
NODES = {"place": "B4.3", "retreat": "B2.4"}
CONTRACT = {"params": G.FAMILY["contract"]["params"], "failure_codes": ["UNSAFE", "BUDGET", "NOT_HELD"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    store = A.Store(output / "store", json.loads(TREE.read_text()))
    plant = json.loads((G.SOURCE / "model_reference.json").read_text())["path"]
    scope = {"task_family": G.FAMILY["task_family"], "initial_sha256": [_sha(G.SOURCE / "initial_state.npz")],
             "plant_sha256": _sha(ROOT / plant)}
    provenance = {"author": AUTHOR, "parents": [], "created_on": "t02_split_store",
                  "note": "engineering column; open loop; source episode 2401 of tray_20261025_repair_003"}
    steps = []
    for number, (place, retreat) in enumerate(R.segments_split(G.SOURCE), 1):
        held, placed = f"cup_{number}_held_released", f"cup_{number}_in_tray"
        before = [f"cup_{number - 1}_in_tray"] if number > 1 else []
        for part, plan, pre, post, summary in (
                ("place", place, ["hand_empty", "guard_clear"] + before, [held],
                 f"Cup {number}: recorded grasp, lift, carry, lower into the tray and open the hand. "
                 "Reads no cup or tray estimate."),
                ("retreat", retreat, [held], [placed],
                 f"Cup {number}: recorded pelvis-backward retreat, then raise clear of the tray and settle. "
                 "The hand passes close to the cup it just released.")):
            digest = store.put_source(R.leaf_source(plan))
            steps.append(store.add({
                "schema": A.SCHEMA, "kind": "leaf", "name": f"t02_cup{number}_{part}", "task_node": NODES[part],
                "summary": summary, "contract": {"pre": pre, "post": post, **CONTRACT}, "scope": scope,
                "provenance": provenance, "implementation": {"language": "python", "source_sha256": digest}}))
    composite = store.add({
        "schema": A.SCHEMA, "kind": "composite", "name": "t02_three_cup_split", "task_node": "T02",
        "summary": "Collect three cups: per cup a place leaf then a retreat leaf. Open loop.",
        "contract": G.FAMILY["contract"], "scope": scope,
        "provenance": {**provenance, "note": provenance["note"] + "; split at the recorded retreat"},
        "ir": [{"use": ref, "params": {k: {"task": k} for k in G.FAMILY["contract"]["params"]}} for ref in steps]})
    code = store.code(composite)
    check_source(code)
    recorded = {}
    for event in json.loads((G.SOURCE / "physics_events.json").read_text()):
        recorded.update(event.get("joints", {}))
    walked = walk(code, {name: 0. for name in recorded})
    old = A.Store(ROOT / "experiments/grow_up_harness_v2/runs/t02_replay_store_20261107_001/store", json.loads(TREE.read_text()))
    reference = walk(old.code("t02_three_cup_replay@8398f5db4447"), {name: 0. for name in recorded})
    report = {"date": time.strftime("%Y-%m-%d"), "boundary": "no physics; interface and arithmetic only",
              "column": "engineering", "leaves": steps, "composite": composite, "code_bytes": len(code.encode()),
              "projections_recompute": store.verify(),
              "walk_from_zero_targets": {k: walked[k] for k in ("commands", "simulation_s")},
              "same_schedule_as_unsplit": walked["commands"] == reference["commands"]
              and abs(walked["simulation_s"] - reference["simulation_s"]) < 1e-9
              and walked["final_targets"] == reference["final_targets"]}
    if not all(report["projections_recompute"].values()) or not report["same_schedule_as_unsplit"]:
        raise RuntimeError(f"split store failed its own check: {report}")
    store.snapshot("built")
    L.write_new(output / "build.json", report)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
