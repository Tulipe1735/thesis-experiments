"""Physical smoke test of an artifact.v2 composite code projection.

Copies the migrated store (read-only parent), adds one composite on task node
DEV.waypoints: reach_pose_hold to a literal waypoint (hold 0.3 s), then
reach_pose_hold to the task target. On two freshly generated tasks it runs the
leaf alone and the composite, each judged by local_reach on the task target.
This checks compilation and execution, not a capability claim.

    MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 "$G1_PYTHON" -B \
      experiments/grow_up_harness_v2/calibration/artifact_v2_composite_smoke.py \
      --output experiments/grow_up_harness_v2/runs/artifact_v2_composite_smoke_<date>_<n>
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import artifact_v2 as A, grow_loop as L, task_generator  # noqa: E402

HARNESS = ROOT / "experiments/grow_up_harness_v2"
PARENT = HARNESS / "runs/artifact_v2_migration_20261107_001/store"
TREE = HARNESS / "artifacts_v2/task_tree_v1.json"
LEAF = "reach_pose_hold@12ddba99e5ca"
SEED = 84001
PREDICTION = ("leaf alone and composite both succeed on both tasks; the composite uses more simulated time "
              "because it first holds at the waypoint")
FALSIFICATION = ("composite gate/interface error, composite fails to reach or hold the final target, or any "
                 "unsafe frame on the waypoint leg; a leaf-alone failure means the task, not the compiler, is suspect")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copytree(PARENT, out / "store", ignore=shutil.ignore_patterns("snapshots", "task_tree.*"))
    store = A.Store(out / "store", json.loads(TREE.read_text()))
    generated = task_generator.generate(SEED, 3, .3)
    waypoint, tasks = generated["tasks"][0]["public"], generated["tasks"][1:]
    params = generated["family"]["contract"]["params"]
    composite = {
        "schema": A.SCHEMA, "kind": "composite", "name": "reach_via_waypoint", "task_node": "DEV.waypoints",
        "summary": "reach_pose_hold to a fixed waypoint (hold 0.3 s), then to the task target",
        "contract": {**generated["family"]["contract"], "pre": ["hand_empty", "hand_open", "guard_clear"]},
        "scope": {"task_family": generated["generator"], "initial_sha256": [generated["source_initial"]["sha256"]],
                  "plant_sha256": generated["plant"]["sha256"]},
        "provenance": {"author": "human:composite_smoke", "parents": [LEAF], "created_on": "smoke",
                       "note": "hand-written IR to exercise the compiler; not an agent artifact"},
        "ir": [{"use": LEAF, "params": {"position_m": {"literal": waypoint["position_m"]},
                                        "quaternion_xyzw": {"literal": waypoint["quaternion_xyzw"]},
                                        "hold_s": {"literal": .3}}},
               {"use": LEAF, "params": {p: {"task": p} for p in params}}],
    }
    registration = {"date": "2026-11-07", "status": "registered_before_physics", "boundary": "MuJoCo simulation",
                    "parent_store": {"path": str(PARENT.relative_to(ROOT)), "ledger_sha256": sha(PARENT / "ledger.jsonl")},
                    "generated": generated, "waypoint_task": generated["tasks"][0]["task_id"],
                    "composite": composite, "prediction": PREDICTION, "falsification": FALSIFICATION,
                    "baselines": {"negative": "wait first task", "positive": "sampled joint target per task", "original_failure": "none", "fallback": "none", "treatment": "leaf versus hand-written composite"},
                    "author_note": "the composite IR is written by hand; this run counts as engineering, not Agent success",
                    "dependencies": {str(p.relative_to(ROOT)): sha(p) for p in
                                     (Path(A.__file__), Path(L.__file__), Path(task_generator.__file__), TREE,
                                      Path(L.local_reach.__file__), Path(__file__))}}
    L.write_new(out / "registration.json", registration)
    composite_ref = store.add(composite)
    instance = json.loads((task_generator.SOURCE / "instance.json").read_text())
    caps = {"simulation_s": 30., "commands": 200, "wall_s": 300.}
    plan = {"instance": instance, "plant": generated["plant"], "caps": caps,
            "body_geometry": json.loads((HARNESS / "runs/grow_reach_20261106_001/body_geometry.json").read_text())}
    observation = json.loads((HARNESS / "runs/grow_reach_20261106_001/control_negative/public_initial.json").read_text())
    negative = L.Episode(out / "control_negative", plan, caps).run(tasks[0]["public"], mode="wait")
    if negative["success"]:
        L.write_new(out / "results.json", {"status": "void", "reason": "negative control succeeded"})
        return
    rows = []
    for task in tasks:
        positive = L.Episode(out / task["task_id"] / "control_positive", plan, caps).run(
            task["public"], mode="engineering", sampled_q=task["private"]["sampled_arm_q"])
        if not positive["success"]:
            rows.append({"task": task["task_id"], "skipped": "positive control failed"})
            continue
        task_input = {k: task["public"][k] for k in params}
        for artifact_ref in (LEAF, composite_ref):
            code = store.code(artifact_ref)
            gate = L.dry_run(code, plan["body_geometry"], task_input, observation, 8)
            folder = out / task["task_id"] / artifact_ref.replace("@", "_")
            row = {"task": task["task_id"], "artifact": artifact_ref, "gate": gate}
            if gate["passed"]:
                result = L.Episode(folder, plan, caps).run(task["public"], mode="worker", source=code,
                                                           task_input=task_input)
                store.record(artifact_ref, task["task_id"], result["success"],
                             str(folder.relative_to(ROOT)), sha(folder / "verdict.json"))
                row.update(success=result["success"], label=result["facts"]["rule_label"],
                           simulation_s=result["simulation_seconds"], commands=result["commands"],
                           final_position_error_m=result["facts"]["final_position_error_m"],
                           unsafe_frames=result["facts"]["unsafe_frames"])
            rows.append(row)
            print(json.dumps(row), flush=True)
    snapshot = store.snapshot("after_smoke")
    summary = {"rows": rows, "composite": composite_ref, "snapshot": snapshot,
               "projections_recompute": store.verify(), "task_tree": store.task_tree()}
    L.write_new(out / "results.json", summary)


if __name__ == "__main__":
    main()
