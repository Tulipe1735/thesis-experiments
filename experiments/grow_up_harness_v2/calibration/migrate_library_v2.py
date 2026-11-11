"""Migrate the grow_reach_20261106_001 library entry into an artifact.v2 leaf.

Reads the registered run read-only. Writes a new store under --output
(exclusive), imports every independent verdict that executed the entry, checks
that the leaf's code projection is byte-identical to the executed source, and
exports the task tree.

    "$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/migrate_library_v2.py \
      --output experiments/grow_up_harness_v2/runs/artifact_v2_migration_<date>_<n>
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import artifact_v2 as A  # noqa: E402

HARNESS = ROOT / "experiments/grow_up_harness_v2"
RUN = HARNESS / "runs/grow_reach_20261106_001"
ENTRY = "code_f7e83f8334a4"
TREE = HARNESS / "artifacts_v2/task_tree_v1.json"

REACH_CONTRACT = {
    "pre": ["hand_empty", "hand_open", "guard_clear"],
    "post": ["palm_at_pose"],
    "params": {
        "position_m": {"type": "vec3", "description": "目标掌位，当前骨盆系，米"},
        "quaternion_xyzw": {"type": "quat_xyzw", "description": "目标掌姿，当前骨盆系"},
        "hold_s": {"type": "float", "description": "到位后需保持的秒数"},
    },
    "failure_codes": ["NOT_REACHED", "ORIENTATION", "NOT_HELD", "BUDGET", "UNSAFE"],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    entry = json.loads((RUN / "library" / f"{ENTRY}.json").read_text())
    registration = json.loads((RUN / "registration.json").read_text())
    store = A.Store(args.output / "store", json.loads(TREE.read_text()))
    digest = store.put_source(entry["source"])
    if digest != entry["source_sha256"]:
        raise ValueError("library source hash mismatch")
    leaf = store.add({
        "schema": A.SCHEMA, "kind": "leaf", "name": "reach_pose_hold", "task_node": "B2.1",
        "summary": entry["card"]["summary"],
        "contract": REACH_CONTRACT,
        "scope": {"task_family": registration["train_tasks"]["generator"],
                  "initial_sha256": [registration["train_tasks"]["source_initial"]["sha256"]],
                  "plant_sha256": registration["train_tasks"]["plant"]["sha256"]},
        "provenance": {"author": registration["proposer"]["model"], "parents": [],
                       "created_on": entry["created_on"],
                       "note": f"migrated from {RUN.relative_to(ROOT)}/library/{ENTRY}.json"},
        "implementation": {"language": "python", "source_sha256": digest},
    })
    episodes = [e["episode"] for e in entry["evidence"]]
    rows = [json.loads(line) for line in (RUN / "tasks.jsonl").read_text().splitlines()]
    episodes += [f"{RUN.relative_to(ROOT)}/heldout_library/{r['task_id']}/fast_{ENTRY}"
                 for r in rows if r["phase"] == "heldout_library"]
    imported = []
    for episode in episodes:
        result = json.loads((ROOT / episode / "result.json").read_text())
        verdict = ROOT / episode / "verdict.json"
        if result["source_sha256"] != digest:
            raise ValueError(f"{episode} executed different source")
        task = episode.split("/")[-2] if "/fast_" in episode else episode.split("/")[-3]
        success = json.loads(verdict.read_text())["verified_local_success"]
        store.record(leaf, task, success, episode, sha(verdict))
        imported.append({"episode": episode, "task": task, "success": success})
    code = store.code(leaf)
    snapshot = store.snapshot("after_migration")
    checks = {"code_projection_equals_executed_source": A.sha_text(code) == entry["source_sha256"],
              "projections_recompute": store.verify(),
              "evidence_imported": len(imported),
              "evidence_success": sum(r["success"] for r in imported)}
    result = {"leaf": leaf, "checks": checks, "imported": imported, "snapshot": snapshot,
              "inputs": {str((RUN / "library" / f"{ENTRY}.json").relative_to(ROOT)):
                         sha(RUN / "library" / f"{ENTRY}.json"),
                         str(TREE.relative_to(ROOT)): sha(TREE),
                         str(Path(A.__file__).relative_to(ROOT)): sha(Path(A.__file__))}}
    (args.output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"leaf": leaf, "checks": checks}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
