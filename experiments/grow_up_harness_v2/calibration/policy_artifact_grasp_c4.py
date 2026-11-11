"""Register the C4 offset/yaw grasp skill and its conditional reset portfolio."""

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

RUNS = ROOT / "experiments/grow_up_harness_v2/runs"
C4_SCAN = RUNS / "grasp_policy_c4_20261106_002"
PORTFOLIO = RUNS / "grasp_policy_c4_20261106_007"
C5 = RUNS / "grasp_policy_c5_20261106_001"


def main() -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    params = {"policy": "v3", "step_m": .015, "behind_m": .13, "high_z": .30,
              "closure": "thumb_lead", "preferred_yaw": .2,
              "offset": [.03, -.07, -.052]}
    param_path = output / "policy_parameters.json"
    param_path.write_text(json.dumps(params, indent=2) + "\n", encoding="utf-8")
    portfolio = read(PORTFOLIO / "results.json")
    scan = read(C4_SCAN / "results.json")
    c5 = read(C5 / "scan.json")
    composite = hashlib.sha256("".join(
        sha(p) for p in (C4_SCAN / "results.json", PORTFOLIO / "results.json", C5 / "scan.json")
    ).encode()).hexdigest()
    initial_states = []
    for seed in (1400, 1401, 1402, 1403):
        trial = PORTFOLIO / str(seed) / "attempt1"
        initial_states.append(relative(trial / "initial_state.npz"))
    policy = PolicyArtifact(
        id="policy_grasp_c4_offset_yaw", version=1,
        scope=Scope("P01", frozenset({"DH_2F_mug_06"}), "pregrasp_to_grasp"),
        status=Status.CANDIDATE, validation=None,
        checkpoint={"path": relative(param_path), "sha256": sha(param_path), "parameters": params},
        policy_type="parameterized_visual_tactile_controller",
        observation_keys=("head_rgb_path", "depth_path", "resolution_wh", "K",
                          "T_optical_to_pelvis", "head_camera", "body_state"),
        action={"joint_names": ("left_shoulder_pitch_joint", "left_shoulder_roll_joint",
                               "left_shoulder_yaw_joint", "left_elbow_joint",
                               "left_wrist_roll_joint", "left_wrist_pitch_joint",
                               "left_wrist_yaw_joint", "left_hand_thumb_0_joint",
                               "left_hand_thumb_1_joint", "left_hand_thumb_2_joint",
                               "left_hand_middle_0_joint", "left_hand_middle_1_joint",
                               "left_hand_index_0_joint", "left_hand_index_1_joint"),
                "units": "mixed_cartesian_waypoints_and_absolute_joint_radians",
                "horizon": 1, "fps": 500.0},
        training={"dataset_path": relative(PORTFOLIO), "dataset_sha256": composite,
                  "train_episodes": (1400,), "validation_episodes": (1400, 1401, 1402, 1403),
                  "objective": "black_box_policy_search_with_reset_fallback",
                  "optimizer_steps": 9, "selected_step": 1, "seed": 1400},
        evaluation={"official_evaluator": "grasp_optimization/verify_grasp.py",
                    "dense_evaluator": "not_available_for_p01",
                    "initial_states": tuple(initial_states),
                    "metrics": ("HeldLifted", "max_lift_m", "terminal_hold_s",
                                "reset_required", "same_initial_state")},
        pre=(Predicate("target_visible"), Predicate("hand_empty"), Predicate("guard_clear")),
        post=(Predicate("HeldLifted"),),
        failure_codes=("NO_REACHABLE_VISUAL_TARGET_PATH_V3", "INSUFFICIENT_THUMB_AND_FINGER_LOAD",
                       "C4_REGRASP_UNREACHABLE", "RETENTION_LOST", "TRACKING_PROTECTION"),
        evidence=(relative(C4_SCAN / "results.json"), relative(PORTFOLIO / "results.json"),
                  relative(C5 / "scan.json")),
        limits=("C4 worked on seed 1400 only; 1401/1402 were solved by the baseline attempt",
                "the 1400 success used an explicit reset to the same saved initial state; this is conditional, not continuous recovery",
                "1403 has 0/160 reachable yaw/offset paths in the offline kinematic scan; classify as out of current envelope, not a learned-skill failure",
                "one upright white cup, fixed lighting, simulated tactile; no formal validation"),
    )
    registry = Registry(output / "registry")
    snapshot = registry.commit([(policy.id, registry.put(policy))], label="policy_grasp_c4_offset_yaw")
    frozen = registry.freeze(snapshot.id)
    projection = output / "projection"
    manifest = policy_artifact.compile_policy(policy, projection)
    portfolio_summary = {
        "attempt1": "VisionGraspV10 baseline (adaptive + C3 recovery)",
        "attempt2_if_failed": "C4 offset/yaw full-close from the same saved initial state",
        "seeds": portfolio["rows"], "successes": portfolio["successes"],
        "conditional_reset_successes": portfolio["conditional_reset_successes"],
        "c5_1403": {"reachable_paths": c5["reachable_count"], "trials": c5["trials"],
                    "classification": "OUT_OF_CURRENT_KINEMATIC_ENVELOPE"},
        "promotion": False,
    }
    write_new(output / "portfolio.json", portfolio_summary)
    checks = {"artifact_digest": policy.digest(), "checkpoint_sha256": sha(param_path),
              "status": policy.status.value, "validation": policy.validation,
              "portfolio": portfolio_summary,
              "projection_manifest": relative(projection / "manifest.json"),
              "projection_hashes": manifest["generated"],
              "registry_integrity": registry.verify(frozen.id),
              "formal_op_count": len(registry.op_table(frozen.id, "formal"))}
    write_new(output / "results.json", checks)
    print(json.dumps({k: v for k, v in checks.items() if k != "portfolio"}, indent=2))
    print(json.dumps(portfolio_summary, indent=2))
    return checks


if __name__ == "__main__":
    main()
