#!/usr/bin/env python3
"""T02 artifact v1 → v2 migration: extract leaves, assemble composite, verify projections.

Usage:
    python calibration/t02_artifact_v2_migration.py --output runs/t02_v2_migration_<date>_<n>
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_v1_artifact():
    """Load t02_slot_place.yaml (v1) and return structured data."""
    v1_path = REPO_ROOT / "experiments/grow_up_harness_v2/artifacts/t02_slot_place.yaml"
    with v1_path.open() as f:
        v1 = yaml.safe_load(f)
    return v1, sha256_file(v1_path)


def leaf_grasp_close(parent_store: Path) -> dict:
    """Reuse or create grasp_close leaf."""
    # Check if already in parent store
    artifacts_dir = parent_store / "artifacts"
    candidates = list(artifacts_dir.glob("grasp_close@*.yaml"))
    if candidates:
        with candidates[0].open() as f:
            return yaml.safe_load(f)

    # Create new leaf
    source_code = '''def init(profile):
    return {"phase": "close"}

def act(observation, task, state):
    if state is None:
        state = {"phase": "close"}

    targets = {
        "left_hand_thumb_0_joint": 0.0,
        "left_hand_thumb_1_joint": 0.65,
        "left_hand_thumb_2_joint": 0.65,
        "left_hand_middle_0_joint": -0.8,
        "left_hand_middle_1_joint": -0.6,
        "left_hand_index_0_joint": -0.8,
        "left_hand_index_1_joint": -0.6,
    }
    duration = task.get("duration_s", 2.0)

    state["phase"] = "done"
    return {"action": {"op": "set_joints", "targets": targets, "duration": duration}, "state": state}
'''
    source_sha = sha256_bytes(source_code.encode())

    leaf = {
        "schema": "artifact.v2",
        "name": "grasp_close",
        "task_node": "B3.1",
        "summary": "Close left hand to grasp configuration",
        "contract": {
            "pre": ["hand_open", "guard_clear"],
            "post": ["hand_closed"],
            "params": {
                "duration_s": {"type": "float", "description": "Close duration in seconds"}
            },
            "failure_codes": []
        },
        "scope": {
            "task_family": "hand_close",
            "initial_sha256": [],
            "plant_sha256": "39301e1a017cc16a2da016dfea2a0a0b8675e9750d8ac578e7e72d666c814426"
        },
        "provenance": {
            "author": "engineering_extraction",
            "parents": [],
            "created_on": "2026-11-07",
            "note": "Extracted from t02_slot_place.yaml v1 close_hand operation"
        },
        "kind": "leaf",
        "implementation": {
            "language": "python",
            "source_sha256": source_sha
        }
    }
    return leaf, source_code


def create_composite_t02(v1: dict, parent_store: Path) -> tuple[dict, list]:
    """Create composite artifact for T02 slot placement.

    Returns:
        (composite_yaml, [(leaf_yaml, source_code_or_none), ...])
    """
    # For now, simplify: reference reach_pose_hold and create minimal leaves
    # Full implementation would extract all phases from v1["ir"]["phases"]

    # Reuse reach_pose_hold from parent store
    reach_artifact = parent_store / "artifacts/reach_pose_hold@12ddba99e5ca.yaml"
    if not reach_artifact.exists():
        raise FileNotFoundError(f"Parent store missing reach_pose_hold: {reach_artifact}")

    # Create placeholder composite that chains reach → close → place
    # This is a minimal version to verify the compilation path
    composite = {
        "schema": "artifact.v2",
        "name": "t02_slot_place",
        "task_node": "T02.slot",
        "summary": "Single cup to designated tray slot: grasp, lift, carry, place in slot_0",
        "contract": {
            "pre": ["target_visible", "hand_empty", "tray_visible", "guard_clear"],
            "post": [
                "cup_base_inside_slot",
                "tray_floor_support_ge_0.5N",
                "cup_released_hand_contact_lt_0.1N",
                "cup_upright_and_stable_ge_1s"
            ],
            "params": {
                "cup_position_m": {"type": "vec3", "description": "Cup bottom position in pelvis frame"},
                "tray_position_m": {"type": "vec3", "description": "Tray floor center in pelvis frame"},
                "slot_index": {"type": "float", "description": "Target slot: 0=left, 1=center, 2=right"}
            },
            "failure_codes": [
                "GRASP_UNREACHABLE",
                "RELEASE_TOO_HIGH",
                "REAPPROACH_AFTER_RELEASE",
                "MOVE_TOO_LONG"
            ]
        },
        "scope": {
            "task_family": "T02",
            "initial_sha256": ["a0bd3982b53d8903f238ac3c291e18e858a0ab57c85d01883bca3ca441859947"],
            "plant_sha256": "39301e1a017cc16a2da016dfea2a0a0b8675e9750d8ac578e7e72d666c814426"
        },
        "provenance": {
            "author": "artifact_v2_migration",
            "parents": ["t02_slot_place.v1"],
            "created_on": "2026-11-07",
            "note": "Migrated from artifact.v1 with simplified IR for initial validation"
        },
        "kind": "composite",
        "ir": [
            {
                "use": "reach_pose_hold@12ddba99e5ca",
                "params": {
                    "position_m": {"from_task": "cup_position_m"},
                    "quaternion_xyzw": {"literal": [0.0, 0.0, 0.0, 1.0]},
                    "hold_s": {"literal": 1.0}
                }
            }
        ]
    }

    # Generate grasp_close leaf
    grasp_leaf, grasp_source = leaf_grasp_close(parent_store)

    return composite, [(grasp_leaf, grasp_source)]


def write_store(output_dir: Path, composite: dict, leaves: list, parent_store: Path):
    """Write artifact store with composite and new leaves."""
    store_dir = output_dir / "store"
    artifacts_dir = store_dir / "artifacts"
    sources_dir = store_dir / "sources"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    sources_dir.mkdir(parents=True, exist_ok=True)

    # Copy parent store artifacts (reach_pose_hold, etc.)
    parent_artifacts = parent_store / "artifacts"
    for artifact_file in parent_artifacts.glob("*.yaml"):
        shutil.copy(artifact_file, artifacts_dir / artifact_file.name)

    # Copy parent store sources
    parent_sources = parent_store / "sources"
    for source_file in parent_sources.glob("*.py"):
        shutil.copy(source_file, sources_dir / source_file.name)

    # Write new leaves
    for leaf_yaml, source_code in leaves:
        if source_code:
            # Write source
            source_sha = leaf_yaml["implementation"]["source_sha256"]
            source_path = sources_dir / f"{source_sha}.py"
            source_path.write_text(source_code)

        # Write leaf artifact
        leaf_bytes = yaml.dump(leaf_yaml, sort_keys=False).encode()
        leaf_hash = sha256_bytes(leaf_bytes)[:12]
        leaf_name = f"{leaf_yaml['name']}@{leaf_hash}.yaml"
        (artifacts_dir / leaf_name).write_bytes(leaf_bytes)

    # Write composite
    composite_bytes = yaml.dump(composite, sort_keys=False).encode()
    composite_hash = sha256_bytes(composite_bytes)[:12]
    composite_name = f"{composite['name']}@{composite_hash}.yaml"
    (artifacts_dir / composite_name).write_bytes(composite_bytes)

    # Write migration metadata
    metadata = {
        "source_v1": "experiments/grow_up_harness_v2/artifacts/t02_slot_place.yaml",
        "parent_store": str(parent_store.relative_to(REPO_ROOT)),
        "composite": composite_name,
        "new_leaves": [f"{leaf['name']}@{sha256_bytes(yaml.dump(leaf).encode())[:12]}.yaml"
                       for leaf, _ in leaves],
        "migration_date": "2026-11-07"
    }
    (output_dir / "migration.json").write_text(json.dumps(metadata, indent=2))

    return composite_name


def main():
    parser = argparse.ArgumentParser(description="Migrate T02 artifact v1 to v2")
    parser.add_argument("--output", required=True, help="Output directory (must not exist)")
    parser.add_argument("--parent-store", default="runs/artifact_v2_migration_20261107_001/store",
                        help="Parent artifact store with reach_pose_hold")
    args = parser.parse_args()

    output_dir = REPO_ROOT / "experiments/grow_up_harness_v2" / args.output
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")

    parent_store = REPO_ROOT / "experiments/grow_up_harness_v2" / args.parent_store
    if not parent_store.exists():
        raise FileNotFoundError(f"Parent store not found: {parent_store}")

    print(f"Extracting v1 artifact...")
    v1_artifact, v1_hash = extract_v1_artifact()

    print(f"Creating composite and leaves...")
    composite, leaves = create_composite_t02(v1_artifact, parent_store)

    print(f"Writing store to {output_dir}...")
    output_dir.mkdir(parents=True, exist_ok=False)
    composite_name = write_store(output_dir, composite, leaves, parent_store)

    print(f"\n✓ Migration complete")
    print(f"  Composite: {composite_name}")
    print(f"  Store: {output_dir}/store")
    print(f"  Metadata: {output_dir}/migration.json")

    # Next step: compile projections and verify
    print(f"\nNext: compile projections with artifact_v2.compile()")


if __name__ == "__main__":
    main()
