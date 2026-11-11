"""Register the existing SmolVLA cup checkpoint as one candidate PolicyArtifact."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import policy_artifact
from harness.contracts import PolicyArtifact, Predicate, Scope, Status
from harness.registry import Registry
from experiments.t0_agent_v1.common import read, relative, sha, write_new

CKPT = ROOT / "grasp_optimization/training/cup_fourview_sft_v1/best/model.safetensors"
DATASET = ROOT / "grasp_optimization/datasets/cup_fourview_v1"
TRAIN_RESULT = ROOT / "grasp_optimization/training/cup_fourview_sft_v1/result.json"
PHYSICAL = ROOT / "grasp_optimization/reports/cup_finetune_results.json"


def dataset_identity() -> str:
    info = hashlib.sha256((DATASET / "meta/info.json").read_bytes()).hexdigest()
    stats = hashlib.sha256((DATASET / "meta/stats.json").read_bytes()).hexdigest()
    return hashlib.sha256((info + stats).encode()).hexdigest()


def main() -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    info = read(DATASET / "meta/info.json")
    result = read(TRAIN_RESULT)
    physical = read(PHYSICAL)
    names = tuple(info["features"]["action"]["names"])
    if len(names) != 28:
        raise ValueError("expected 28 action names")
    initial_paths = {
        1000: "grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/pregrasp_state.npz",
        1300: "grasp_optimization/episodes/cup_full_pregrasp_1300/pregrasp_state.npz",
        1301: "grasp_optimization/episodes/cup_full_pregrasp_1301/pregrasp_state.npz",
        1302: "grasp_optimization/episodes/cup_full_pregrasp_1302/pregrasp_state.npz",
        1303: "grasp_optimization/episodes/cup_full_pregrasp_1303/pregrasp_state.npz",
    }
    initial_states = tuple(initial_paths[seed] for seed in (1000, 1300, 1301, 1302, 1303))
    for path in initial_states:
        if not (ROOT / path).is_file():
            raise FileNotFoundError(path)
    write_new(output / "registration.json", {
        "date": "2026-11-06", "kind": "policy_artifact_registration", "status": "registered_before_projection",
        "boundary": "saved checkpoint and evidence only; no physics, no model requests",
        "checkpoint": {"path": relative(CKPT), "sha256": sha(CKPT)},
        "dataset": {"path": relative(DATASET), "identity": dataset_identity()},
        "training_result": {"path": relative(TRAIN_RESULT), "sha256": sha(TRAIN_RESULT)},
        "physical_result": {"path": relative(PHYSICAL), "sha256": sha(PHYSICAL)},
        "prediction": "one candidate PolicyArtifact compiles to code and skill from the same digest; physical 0/4 remains and no validation is claimed",
        "falsification": "checkpoint/dataset hash mismatch, any validated status, or a projection whose content disagrees with the record",
        "no_new_training": True, "no_new_physics": True,
    })
    policy = PolicyArtifact(
        id="policy_cup_fourview_sft", version=1,
        scope=Scope("P01", frozenset({"DH_2F_mug_06"}), "pregrasp_to_grasp"),
        status=Status.CANDIDATE, validation=None,
        checkpoint={"path": relative(CKPT), "sha256": sha(CKPT)},
        policy_type="smolvla_flow_matching",
        observation_keys=("observation.state", "task",
                          "observation.images.cam_left_high", "observation.images.cam_right_high",
                          "observation.images.cam_left_wrist", "observation.images.cam_right_wrist"),
        action={"joint_names": names, "units": "absolute_joint_radians", "horizon": 50, "fps": 30.0},
        training={"dataset_path": relative(DATASET), "dataset_sha256": dataset_identity(),
                  "train_episodes": (0, 1, 2, 3), "validation_episodes": (4, 5),
                  "objective": "flow_matching_il", "optimizer_steps": result["optimizer_steps"],
                  "selected_step": result["selected_step"], "seed": 20261024},
        evaluation={"official_evaluator": "grasp_optimization/verify_grasp.py",
                    "dense_evaluator": "not_available_for_p01",
                    "initial_states": initial_states,
                    "metrics": ("HeldLifted", "opposed_grip", "max_lift_m", "terminal_hold_s")},
        pre=(Predicate("target_visible"), Predicate("hand_empty"), Predicate("guard_clear")),
        post=(Predicate("HeldLifted"),),
        failure_codes=("LEFT_PALM_DEPARTURE_CLOSING", "GRIP_LOST", "RIGHT_PALM_DEPARTURE",
                       "RIGHT_CONTACT_LOAD", "LEFT_CONTACT_LOAD", "TRACKING_PROTECTION"),
        evidence=(relative(TRAIN_RESULT), relative(PHYSICAL)),
        limits=("candidate; physical 0/4 on new positions and 0/1 on the training anchor",
                "4 training demonstrations, 2 offline-validation demonstrations",
                "four cameras are an engineering approximate rig; original extrinsics unknown",
                "arm drift during finger closing triggered protection in 14/15 runs",
                "offline action MSE is not task success; no new-position validation",
                "P01 has no dense evaluator yet; official HeldLifted is the only physical gate"),
    )
    registry = Registry(output / "registry")
    snapshot = registry.commit([(policy.id, registry.put(policy))], label="policy_cup_fourview_sft")
    frozen = registry.freeze(snapshot.id)
    projection = output / "projection"
    manifest = policy_artifact.compile_policy(policy, projection)
    view = registry.load(frozen.id)
    loaded = view.artifacts[policy.id]
    if loaded.digest() != policy.digest():
        raise ValueError("registry digest changed")
    checks = {
        "artifact_digest": policy.digest(),
        "checkpoint_sha256": policy.checkpoint["sha256"],
        "dataset_identity": policy.training["dataset_sha256"],
        "status": policy.status.value,
        "validation": policy.validation,
        "physical_successes": {
            str(row["seed"]): row["successes"] for row in physical["physical"]["pairs"]
        },
        "projection_manifest": relative(projection / "manifest.json"),
        "projection_hashes": manifest["generated"],
        "registry_integrity": registry.verify(frozen.id),
        "formal_op_count": len(registry.op_table(frozen.id, "formal")),
        "skill_graph": registry.skill_graph(frozen.id),
    }
    write_new(output / "artifact.json", policy.to_dict())
    write_new(output / "results.json", checks)
    print(json.dumps(checks, indent=2))
    return checks


if __name__ == "__main__":
    main()
