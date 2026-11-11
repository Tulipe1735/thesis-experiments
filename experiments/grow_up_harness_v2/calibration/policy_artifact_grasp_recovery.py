"""Register the v2 + path + selector/recovery grasp policy as a PolicyArtifact."""

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
PATH_RUN = RUNS / "grasp_policy_path_20261106_001"
CLOSURE_RUN = RUNS / "grasp_policy_validation_20261106_001"
REC1 = RUNS / "grasp_policy_recovery_20261106_001"
REC2 = RUNS / "grasp_policy_recovery_20261106_002"
V2 = ROOT / "grasp_optimization/reports/v2_progress.json"


def _rows(run: Path) -> list[dict]:
    return read(run / "results.json")["rows"]


def _per_seed(rows: list[dict], key: str = "independent_success") -> dict:
    return {int(row["seed"]): bool(row.get(key)) for row in rows}


def main() -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    params = {"step_m": .015, "behind_m": .13, "high_z": .30,
              "policy": "v6", "selector_index_N": 4.0}
    param_path = output / "policy_parameters.json"
    param_path.write_text(json.dumps(params, indent=2) + "\n", encoding="utf-8")
    param_sha = sha(param_path)
    path_rows = _rows(PATH_RUN)
    rec_rows = _rows(REC1) + _rows(REC2)
    c3 = {int(row["seed"]): bool(row["independent_success"]) for row in rec_rows}
    c1 = _per_seed(path_rows)
    v2 = read(V2)["paired_summary"]["comparisons"]
    c0 = {int(row["seed"]): bool(row["v2_success"]) for row in v2}
    c2 = {int(row["seed"]): bool(row["independent_success"])
          for row in read(CLOSURE_RUN / "results.json")["rows"] if row["closure"] == "thumb_lead"}
    curve = [
        {"stage": "C0", "name": "v2_adaptive", "successes": sum(c0.values()), "n": 8,
         "per_seed": c0, "status": "baseline"},
        {"stage": "C1", "name": "path_step_0.015", "successes": sum(c1.values()), "n": 8,
         "per_seed": c1, "status": "no_net_gain"},
        {"stage": "C2", "name": "full_close_thumb_lead", "successes": sum(c2.values()), "n": 8,
         "per_seed": c2, "status": "rejected_regression"},
        {"stage": "C3", "name": "selector_recovery", "successes": sum(c3.values()), "n": 8,
         "per_seed": c3, "status": "candidate"},
    ]
    composite = hashlib.sha256("".join(
        sha(p) for p in (PATH_RUN / "results.json", CLOSURE_RUN / "results.json",
                         REC1 / "results.json", REC2 / "results.json")
    ).encode()).hexdigest()
    initial_states = []
    for seed in range(1200, 1208):
        for run in (REC1, REC2):
            trial = run / f"trial_{seed}"
            if (trial / "initial_state.npz").is_file():
                initial_states.append(relative(trial / "initial_state.npz"))
                break
    if len(initial_states) != 8:
        raise ValueError(f"expected 8 initial states, got {len(initial_states)}")
    policy = PolicyArtifact(
        id="policy_grasp_v2_recovery", version=1,
        scope=Scope("P01", frozenset({"DH_2F_mug_06"}), "pregrasp_to_grasp"),
        status=Status.CANDIDATE, validation=None,
        checkpoint={"path": relative(param_path), "sha256": param_sha, "parameters": params},
        policy_type="parameterized_visual_tactile_controller",
        observation_keys=("head_rgb_path", "depth_path", "resolution_wh", "K",
                          "T_optical_to_pelvis", "head_camera", "body_state"),
        action={"joint_names": ("left_shoulder_pitch_joint", "left_shoulder_roll_joint",
                               "left_shoulder_yaw_joint", "left_elbow_joint",
                               "left_wrist_roll_joint", "left_wrist_pitch_joint",
                               "left_wrist_yaw_joint", "left_hand_thumb_0_joint",
                               "left_hand_thumb_1_joint", "left_hand_thumb_2_joint",
                               "left_hand_middle_0_joint", "left_hand_middle_1_joint",
                               "left_hand_index_0_joint", "left_hand_index_1_joint",
                               "waist_pitch_joint"),
                "units": "mixed_cartesian_waypoints_and_absolute_joint_radians",
                "horizon": 1, "fps": 500.0},
        training={"dataset_path": relative(REC1), "dataset_sha256": composite,
                  "train_episodes": (1206,), "validation_episodes": tuple(range(1200, 1208)),
                  "objective": "black_box_policy_search_with_recovery_skill",
                  "optimizer_steps": 27, "selected_step": 1, "seed": 1206},
        evaluation={"official_evaluator": "grasp_optimization/verify_grasp.py",
                    "dense_evaluator": "not_available_for_p01",
                    "initial_states": tuple(initial_states),
                    "metrics": ("HeldLifted", "max_lift_m", "terminal_hold_s",
                                "selector_triggered", "recovery_used")},
        pre=(Predicate("target_visible"), Predicate("hand_empty"), Predicate("guard_clear")),
        post=(Predicate("HeldLifted"),),
        failure_codes=("NO_REACHABLE_VISUAL_TARGET_PATH_V3", "INSUFFICIENT_THUMB_AND_FINGER_LOAD",
                       "RETENTION_LOST", "TRACKING_PROTECTION", "LEFT_PALM_DEPARTURE_CLOSING",
                       "RIGHT_PALM_DEPARTURE"),
        evidence=(relative(PATH_RUN / "results.json"), relative(CLOSURE_RUN / "results.json"),
                  relative(REC1 / "results.json"), relative(REC2 / "results.json")),
        limits=("development seeds 1200-1207 were already consumed by frozen v2; 8/8 is not unseen-position evidence",
                "C2 full closure regressed to 6/8 and was rejected; only C3 selector+recovery is retained",
                "selector threshold index<4.0 N was fitted on these 8 seeds and needs new-position validation",
                "one upright white cup, one tray-free grasp task, fixed lighting and simulated tactile only",
                "no formal validation level; candidate until a new frozen transfer batch passes"),
    )
    registry = Registry(output / "registry")
    snapshot = registry.commit([(policy.id, registry.put(policy))], label="policy_grasp_v2_recovery")
    frozen = registry.freeze(snapshot.id)
    projection = output / "projection"
    manifest = policy_artifact.compile_policy(policy, projection)
    write_new(output / "curve.json", {"benchmark": "seeds 1200-1207, development, consumed",
                                      "points": curve})
    # Small dependency-free SVG curve.
    w, h, left, bottom = 640, 360, 70, 50
    points = []
    for i, row in enumerate(curve):
        x = left + i * (w - left - 40) / (len(curve) - 1)
        y = bottom + (1 - row["successes"] / 8) * (h - bottom - 40)
        points.append((x, y, row))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<line x1="{left}" y1="{bottom}" x2="{left}" y2="{h-40}" stroke="#777"/>',
           f'<line x1="{left}" y1="{h-40}" x2="{w-40}" y2="{h-40}" stroke="#777"/>']
    for value in (0, 4, 8):
        y = bottom + (1 - value / 8) * (h - bottom - 40)
        svg.append(f'<text x="45" y="{y+4}" font-size="12" fill="#555">{value}/8</text>')
    svg.append(f'<polyline fill="none" stroke="#0b6b5b" stroke-width="3" points="' +
               " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points) + '"/>')
    for x, y, row in points:
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#0b6b5b"/>')
        svg.append(f'<text x="{x:.1f}" y="{y-12:.1f}" font-size="13" text-anchor="middle" fill="#111">'
                   f'{row["stage"]} {row["successes"]}/8</text>')
        svg.append(f'<text x="{x:.1f}" y="{h-22}" font-size="10" text-anchor="middle" fill="#555">'
                   f'{row["name"]}</text>')
    svg.append('</svg>')
    (output / "curve.svg").write_text("\n".join(svg) + "\n", encoding="utf-8")
    checks = {"artifact_digest": policy.digest(), "checkpoint_sha256": param_sha,
              "status": policy.status.value, "validation": policy.validation,
              "curve": curve, "projection_manifest": relative(projection / "manifest.json"),
              "projection_hashes": manifest["generated"],
              "registry_integrity": registry.verify(frozen.id),
              "formal_op_count": len(registry.op_table(frozen.id, "formal")),
              "skill_graph": registry.skill_graph(frozen.id)}
    write_new(output / "results.json", checks)
    print(json.dumps({key: value for key, value in checks.items() if key != "curve"}, indent=2))
    print(json.dumps(curve, indent=2))
    return checks


if __name__ == "__main__":
    main()
