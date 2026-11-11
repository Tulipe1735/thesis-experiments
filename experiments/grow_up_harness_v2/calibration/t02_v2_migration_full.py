#!/usr/bin/env python3
"""T02 artifact v1 → v2 migration, Phase 1 (compile-path validation only).

Extracts three leaves from the T02 slot-placement v1 recipe, assembles a minimal
composite (reach_pose_hold → grasp_close → timed_wait), and writes a new store
under --output. Every artifact is added through ``artifact_v2.Store.add`` so the
content-addressed ref, task-tree membership, references and both projections are
validated at write time.

This run proves the migration and projection path. It does not execute physics
and does not claim a T02 slot success.

    cd experiments/grow_up_harness_v2
    PYTHONDONTWRITEBYTECODE=1 "$G1_PYTHON" -B \
      calibration/t02_v2_migration_full.py --output runs/t02_v2_migration_<date>_<n>
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import yaml

HARNESS = Path(__file__).resolve().parents[1]
ROOT = HARNESS.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HARNESS))

from harness import artifact_v2 as A  # noqa: E402

V1 = HARNESS / "artifacts/t02_slot_place.yaml"
TREE = HARNESS / "artifacts_v2/task_tree_v3.json"
PARENT_STORE = HARNESS / "runs/artifact_v2_migration_20261107_001/store"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def load_v1() -> tuple[dict, str]:
    with V1.open() as handle:
        return yaml.safe_load(handle), sha256_file(V1)


def leaf_sources(v1: dict) -> tuple[str, str, str]:
    """Return (grasp_close, hand_open, timed_wait) source text."""
    close = repr(dict(v1["ir"]["close_angles"]))
    grasp_close = '''CLOSE = __CLOSE__


def init(profile):
    return {"phase": "close"}


def act(observation, task, state):
    if not isinstance(state, dict) or "phase" not in state:
        state = {"phase": "close"}
    if state["phase"] == "done":
        return {"action": {"op": "done"}, "state": state}
    joints = observation.get("joints") or {}
    targets = {}
    for name, goal in CLOSE.items():
        if name not in joints:
            continue
        joint = joints[name]
        current = float(joint.get("target", joint.get("q", goal)))
        delta = goal - current
        if abs(delta) <= 0.01:
            continue
        targets[name] = current + max(-0.04, min(0.04, delta))
    if not targets:
        state["phase"] = "done"
        return {"action": {"op": "done"}, "state": state}
    return {"action": {"op": "set_joints", "targets": targets, "duration": 0.2}, "state": state}
'''.replace("__CLOSE__", close)

    hand_open = '''OPEN_JOINTS = ["left_hand_thumb_0_joint", "left_hand_thumb_1_joint",
               "left_hand_thumb_2_joint", "left_hand_middle_0_joint",
               "left_hand_middle_1_joint", "left_hand_index_0_joint",
               "left_hand_index_1_joint"]


def init(profile):
    return {"phase": "open"}


def act(observation, task, state):
    if not isinstance(state, dict) or "phase" not in state:
        state = {"phase": "open"}
    if state["phase"] == "done":
        return {"action": {"op": "done"}, "state": state}
    joints = observation.get("joints") or {}
    targets = {}
    for name in OPEN_JOINTS:
        if name not in joints:
            continue
        joint = joints[name]
        current = float(joint.get("target", joint.get("q", 0.0)))
        if abs(current) <= 0.01:
            continue
        targets[name] = current + max(-0.04, min(0.04, -current))
    if not targets:
        state["phase"] = "done"
        return {"action": {"op": "done"}, "state": state}
    return {"action": {"op": "set_joints", "targets": targets, "duration": 0.2}, "state": state}
'''

    timed_wait = '''def init(profile):
    return {"t0": None}


def act(observation, task, state):
    now = float(observation.get("simulation_seconds", 0.0))
    if not isinstance(state, dict) or state.get("t0") is None:
        state = {"t0": now}
    duration_s = float(task.get("duration_s", 1.0))
    remaining = duration_s - (now - state["t0"])
    if remaining <= 1e-9:
        return {"action": {"op": "done"}, "state": state}
    step = round(min(0.2, max(0.02, remaining)) / 0.002) * 0.002
    return {"action": {"op": "wait", "duration": step}, "state": state}
'''
    return grasp_close, hand_open, timed_wait


def leaf_data(v1: dict, tree: dict) -> list[tuple[dict, str]]:
    plant = v1["binding"]["plant_sha256"]
    initial = [i["sha256"] for i in v1["scope"]["initial_states"]]
    grasp_close, hand_open, timed_wait = leaf_sources(v1)
    common = {"author": "engineering_extraction", "parents": [], "created_on": "2026-11-07"}
    leaves = [
        ({
            "schema": A.SCHEMA, "kind": "leaf", "name": "grasp_close", "task_node": "B3.2",
            "summary": "Close the left hand to the T02 grasp angles in bounded steps",
            "contract": {"pre": ["hand_open", "guard_clear"], "post": ["hand_closed"],
                         "params": {}, "failure_codes": []},
            "scope": {"task_family": "hand_close", "initial_sha256": [], "plant_sha256": plant},
            "provenance": {**common, "note": f"From {rel(V1)} ir.close_angles"},
        }, grasp_close),
        ({
            "schema": A.SCHEMA, "kind": "leaf", "name": "hand_open", "task_node": "B3.2",
            "summary": "Open the left hand to zero in bounded steps",
            "contract": {"pre": ["guard_clear"], "post": ["hand_open"],
                         "params": {}, "failure_codes": []},
            "scope": {"task_family": "hand_open", "initial_sha256": [], "plant_sha256": plant},
            "provenance": {**common, "note": f"From {rel(V1)} ir.phases.release open_hand"},
        }, hand_open),
        ({
            "schema": A.SCHEMA, "kind": "leaf", "name": "timed_wait", "task_node": "B1.1",
            "summary": "Wait for duration_s in <=0.2 s dispatch slices (timing primitive)",
            "contract": {"pre": ["guard_clear"], "post": [],
                         "params": {"duration_s": {"type": "float", "description": "Wait duration seconds"}},
                         "failure_codes": []},
            "scope": {"task_family": "timing_primitive", "initial_sha256": [], "plant_sha256": plant},
            "provenance": {**common, "note": f"From {rel(V1)} wait steps; primitive, not a capability"},
        }, timed_wait),
    ]
    # Fail at build time, not inside Store.add, if a node is missing.
    ids = {node["id"] for node in tree["nodes"]}
    for data, _ in leaves:
        if data["task_node"] not in ids:
            raise ValueError(f"task_node {data['task_node']} missing from {rel(TREE)}")
    return leaves


def composite_data(leaf_refs: dict, v1: dict) -> dict:
    return {
        "schema": A.SCHEMA, "kind": "composite", "name": "t02_grasp_stub",
        "task_node": "T02.slot",
        "summary": "T02 Phase 1 stub: reach the cup pose, close the hand, wait; no lift, carry or release",
        "contract": {
            "pre": ["target_visible", "hand_empty", "guard_clear"],
            "post": ["hand_closed_at_target"],
            "params": {
                "cup_position_m": {"type": "vec3", "description": "Cup bottom in pelvis frame, m"},
                "cup_quaternion_xyzw": {"type": "quat_xyzw", "description": "Cup orientation xyzw"},
            },
            "failure_codes": ["NOT_REACHED", "ORIENTATION", "NOT_HELD", "BUDGET"],
        },
        "scope": {"task_family": "T02_slot_local", "initial_sha256": [],
                  "plant_sha256": v1["binding"]["plant_sha256"]},
        "provenance": {"author": "artifact_v2_migration_phase1",
                       "parents": [leaf_refs["grasp_close"], leaf_refs["hand_open"],
                                   leaf_refs["timed_wait"]],
                       "created_on": "2026-11-07",
                       "note": f"Minimal compile-path composite extracted from {rel(V1)}; "
                               "lift/carry/place/release deferred to Phase 2"},
        "ir": [
            {"use": "reach_pose_hold@12ddba99e5ca",
             "params": {"position_m": {"task": "cup_position_m"},
                        "quaternion_xyzw": {"task": "cup_quaternion_xyzw"},
                        "hold_s": {"literal": 0.5}}},
            {"use": leaf_refs["grasp_close"], "params": {}},
            {"use": leaf_refs["timed_wait"], "params": {"duration_s": {"literal": 0.5}}},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="T02 v1→v2 migration, Phase 1 compile-path only")
    parser.add_argument("--output", required=True, help="Harness-relative output dir (must not exist)")
    parser.add_argument("--parent-store", default=str(PARENT_STORE.relative_to(HARNESS)),
                        help="Harness-relative parent store with reach_pose_hold")
    args = parser.parse_args()

    out = HARNESS / args.output
    if out.exists():
        raise FileExistsError(f"Output exists: {out}")
    parent = HARNESS / args.parent_store
    if not parent.exists():
        raise FileNotFoundError(f"Parent store missing: {parent}")

    tree = json.loads(TREE.read_text())
    v1, v1_sha = load_v1()

    out.mkdir(parents=True)
    # Copy artifacts, sources, ledger and projections; drop stale snapshots/tree exports.
    shutil.copytree(parent, out / "store",
                    ignore=shutil.ignore_patterns("snapshots", "task_tree.json", "task_tree.mmd"))
    store = A.Store(out / "store", tree)

    leaf_refs = {}
    for data, source in leaf_data(v1, tree):
        digest = store.put_source(source)
        data = {**data, "implementation": {"language": "python", "source_sha256": digest}}
        leaf_refs[data["name"]] = store.add(data)

    composite_ref = store.add(composite_data(leaf_refs, v1))
    snapshot = store.snapshot("after_t02_migration")

    code = store.code(composite_ref)
    compile(code, f"<{composite_ref}>", "exec")
    projections = store.verify()
    if not all(projections.values()):
        raise RuntimeError(f"projection mismatch: {projections}")

    metadata = {
        "phase": "1_minimal_stub",
        "boundary": "compile-path validation only; no physics, no T02 capability claim",
        "source_v1": {"path": rel(V1), "sha256": v1_sha},
        "parent_store": {"path": rel(parent), "ledger_sha256": sha256_file(parent / "ledger.jsonl")},
        "task_tree": {"path": rel(TREE), "sha256": sha256_file(TREE)},
        "composite_ref": composite_ref,
        "new_leaf_refs": list(leaf_refs.values()),
        "checks": {
            "projections_recompute": projections,
            "composite_code_compiles": True,
            "composite_steps": len(store.load(composite_ref).ir),
            "task_node": store.load(composite_ref).task_node,
        },
        "snapshot": snapshot,
        "migration_date": "2026-11-07",
        "note": "Minimal composite for artifact.v2 pathway validation; full T02 choreography is Phase 2",
    }
    (out / "migration.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    print(json.dumps({"composite_ref": composite_ref, "new_leaf_refs": leaf_refs,
                      "checks": metadata["checks"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
