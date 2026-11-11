#!/usr/bin/env python3
"""Verify the T02 artifact.v2 Phase 1 store and write machine-readable evidence.

Checks content-addressed refs, task-tree membership, both projections, code
compilation, and a synthetic dispatch of the composite through the same action
gate used before physics. The synthetic dispatch is not an episode.

    cd experiments/grow_up_harness_v2
    PYTHONDONTWRITEBYTECODE=1 "$G1_PYTHON" -B \
      calibration/t02_v2_verify.py --run runs/t02_v2_migration_<date>_<n>
"""
import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
ROOT = HARNESS.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HARNESS))

from harness import artifact_v2 as A, grow_loop  # noqa: E402

TREE = HARNESS / "artifacts_v2/task_tree_v3.json"
HAND = ["left_hand_thumb_0_joint", "left_hand_thumb_1_joint", "left_hand_thumb_2_joint",
        "left_hand_middle_0_joint", "left_hand_middle_1_joint",
        "left_hand_index_0_joint", "left_hand_index_1_joint"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dispatch_trace(code: str) -> dict:
    namespace = {}
    exec(compile(code, "<composite>", "exec"), namespace)
    cup_position = [0.0, 0.32, 0.82]
    cup_quaternion = [0.0, 0.0, 0.0, 1.0]
    contract = {"cup_position_m": cup_position, "cup_quaternion_xyzw": cup_quaternion}
    observation = {
        "simulation_seconds": 0.0,
        "joints": {name: {"q": 0.0, "target": 0.0} for name in HAND},
        "left_palm": {"position_m": cup_position, "quaternion_xyzw": cup_quaternion},
    }
    state = namespace["init"]({})
    ops = []
    for _ in range(3000):
        result = namespace["act"](observation, contract, state)
        state = result["state"]
        action = result["action"]
        grow_loop.check_action(action, observation)
        ops.append(action["op"])
        if action["op"] == "done":
            break
        if action["op"] == "set_joints":
            for name, value in action["targets"].items():
                observation["joints"][name]["target"] = value
        observation["simulation_seconds"] += action["duration"]
    return {"terminated": bool(ops and ops[-1] == "done"), "calls": len(ops),
            "ops": dict(Counter(ops)), "simulated_seconds": observation["simulation_seconds"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True, help="Harness-relative run directory")
    args = parser.parse_args()
    run = (HARNESS / args.run).resolve()
    store_path = run / "store"
    metadata = json.loads((run / "migration.json").read_text())
    tree = json.loads(TREE.read_text())
    store = A.Store(store_path, tree)

    refs = store.refs()
    ref_checks = {ref: A.ref(store.load(ref)) == ref for ref in refs}
    projections = store.verify()
    composite_ref = metadata["composite_ref"]
    code = store.code(composite_ref)
    compile(code, f"<{composite_ref}>", "exec")
    trace = dispatch_trace(code)
    skill = store.skill(composite_ref)

    checks = {
        "all_refs_recompute": all(ref_checks.values()),
        "all_projections_recompute": all(projections.values()),
        "composite_code_compiles": True,
        "composite_task_node_in_tree": store.load(composite_ref).task_node in
                                       {node["id"] for node in tree["nodes"]},
        "composite_steps": len(store.load(composite_ref).ir),
        "synthetic_dispatch": trace,
        "skill_has_contract_table": "| 参数 | 类型 | 说明 |" in skill,
    }
    failed = (not checks["all_refs_recompute"] or not checks["all_projections_recompute"]
              or not checks["composite_task_node_in_tree"] or not trace["terminated"]
              or trace["calls"] >= 3000)
    result = {
        "run": str(run.relative_to(HARNESS)),
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "boundary": "compile and dispatch only; no physics episode, no T02 capability claim",
        "migration_json_sha256": sha(run / "migration.json"),
        "task_tree": {"path": str(TREE.relative_to(ROOT)), "sha256": sha(TREE)},
        "refs": refs,
        "ref_checks": ref_checks,
        "projections": projections,
        "checks": checks,
        "passed": not failed,
    }
    (run / "verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": checks}, indent=2, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
