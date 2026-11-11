"""Close the failed local pilot using only saved evidence; no robot or model calls."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import local_reach
from harness.registry import Registry
from experiments.t0_agent_v1.common import read, relative, sha, write_new

BASE = ROOT / "experiments/grow_up_harness_v2/runs"
RUN = BASE / "local_artifact_cycle_20261106_004"
GEOMETRY_AUDIT = BASE / "local_artifact_cycle_audit_20261106_001"


def audit(output):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    raw = read(RUN / "results.json")
    cases = read(GEOMETRY_AUDIT / "registration.json")["evaluated_episodes"]
    write_new(output / "registration.json", {
        "date": "2026-11-06", "boundary": "saved simulation evidence only", "physics_steps": 0,
        "model_requests": 0, "episodes": cases,
        "evaluator_sha256": sha(Path(local_reach.__file__)), "audit_source_sha256": sha(Path(__file__)),
        "prediction": "correct hand geometry and verified affine servo inversion preserve negative fail / positive pass; both candidates remain interface failures",
        "falsification": "any changed control verdict prevents using prior calibration as qualification",
        "sample_convention": "sample gaps >0.051 s break only the claimed hold; all saved frames must be safe",
        "original_records": "read only; new verdicts are post-repair offline results",
    })
    rows = []
    for name in cases:
        case = BASE / name
        registration = read(case.parent / "registration.json")
        previous = read(case / "result.json")
        verdict = local_reach.evaluate(case / "episode", registration["local_contract"],
                                       execution_error=previous["error"])
        folder = output / name.replace("/", "__")
        folder.mkdir()
        write_new(folder / "verdict.json", verdict)
        rows.append({"episode": relative(case / "episode"), "verdict": relative(folder / "verdict.json"),
                     "original_local_success": previous["local_success"],
                     "local_success": verdict["verified_local_success"],
                     "terminal_hold_s": verdict["terminal_hold_s"],
                     "final_position_error_m": verdict["final_position_error_m"],
                     "final_orientation_error_rad": verdict["final_orientation_error_rad"],
                     "error": previous["error"], "commands": previous["commands"]})
    registry = Registry(RUN / "registry")
    locked = read(RUN / "locked_candidate.json")
    # Finalize this session's new registry without changing any artifact status.
    frozen = registry.freeze(locked["snapshot_id"])
    view = registry.load(frozen.id)
    skill = registry.get_by_digest(locked["skill_digest"])
    op = registry.get_by_digest(locked["op_digest"])
    code = registry.get_by_digest(locked["code_digest"])
    before = next(read(p) for p in registry.snapshots_dir.glob("*.json") if read(p)["refs"] == [])
    library = {"before_snapshot": before["id"], "after_snapshot": frozen.to_dict(),
               "registry": relative(registry.root), "integrity": registry.verify(frozen.id),
               "formal_op_count": len(registry.op_table(frozen.id, "formal")),
               "formal_skill_admissions": 0, "locked_skill_status": skill.status.value,
               "locked_artifact": locked["artifact"], "source_sha256": code.source_sha256,
               "registration_bound_by_op": "registration:" + sha(RUN / "registration.json") in op.dependencies}
    write_new(output / "library_snapshot.json", library)
    graph = {"fact_source_snapshot": frozen.id,
             "nodes": [{"id": skill.id, "version": skill.version, "digest": skill.digest(), "status": skill.status.value},
                       {"id": op.op_id, "version": op.version, "digest": op.digest(), "status": op.status.value},
                       {"id": code.id, "version": code.version, "digest": code.digest(), "source_sha256": code.source_sha256}],
             "dependency_edges": [{"from": skill.id, "to": op.op_id, "kind": "declared_step_dependency"},
                                  {"from": op.op_id, "to": code.id, "kind": "pinned_source_dependency", "source_sha256": code.source_sha256}],
             "continuation_edges": [], "executed_later_reuse_calls": [],
             "reason": "both candidate versions failed before actuation; no formal admission, A-to-B continuation not run"}
    write_new(output / "skill_graph.json", graph)
    cost = dict(raw["cost"], worker_act_attempts=2, worker_successful_returns=1,
                raw_worker_calls_counter_underreported_by=1)
    result = {"prediction_comparison": {"controls_match": all(r["original_local_success"] == r["local_success"] for r in rows),
                                       "candidate_success_observed": False,
                                       "continuation_prediction": "not_tested; admission gate not reached"},
              "engineering_control_local_passes": sum(r["local_success"] for r in rows if "positive_engineering" in r["episode"]),
              "engineering_control_replays": 2, "independent_initials": 1,
              "candidate_versions": 2, "distinct_candidate_effects": 1,
              "candidate_local_passes": 0, "formal_admissions": 0, "new_autonomous_validated_effects": 0,
              "later_reuse_calls": 0, "continuation_attempts": 0, "continuation_passes": 0,
              "full_task_successes": 0, "full_task_judgments": 6,
              "new_task_coverage": "not_tested", "cost_benefit": "not_tested", "cost": cost,
              "rows": rows, "library": library, "offline_audit_wall_s": time.monotonic() - started,
              "qualification_limits": ["saved-frame evidence, not every physics timestep",
                                       "previous runtime inputs omitted from registration cannot be retroactively frozen",
                                       "neither candidate executed a joint command; physical controller performance untested"],
              "next_implementation_status": "runtime argument/action schemas, call-attempt logging, contract binding and evaluator repaired; no new candidate requests or physical runs after repairs",
              "original_results": relative(RUN / "results.json"),
              "counterexample_geometry_audit": relative(GEOMETRY_AUDIT / "contact_geometry.json"),
              "historical_source_capture": relative(GEOMETRY_AUDIT / "source_capture.json")}
    write_new(output / "results.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "library")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    audit(parser.parse_args().output.resolve())
