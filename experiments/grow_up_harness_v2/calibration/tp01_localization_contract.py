"""Replay the archived localization bug and check the corrected Worker handoff."""

import argparse
import hashlib
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from harness import agent, evidence, registry, run_p2
from harness.contracts import Scope


ARCHIVE = run_p2.RUNS / "p2_agent_20261104_005/agent/author_001/payload.json"
HANDOFF_WITNESS = """
def act(observation, task, state):
    estimate = observation["blackboard"].get("target_estimate_in_palm")
    if not isinstance(estimate, list) or len(estimate) != 3:
        return {"action": {"op": "fail", "reason": "REACH_UNREACHABLE"}}
    return {"action": {"op": "fail", "reason": "JOINT_LIMIT"}}
"""


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    case = run_p2.s_star_case()
    archived = run_p2.read(ARCHIVE)
    source = archived["locate_target"]
    marker = "        bb['localized']=1\n"
    if source.count(marker) != 1:
        raise ValueError("Archived localization source changed")
    adjusted = source.replace(
        marker, marker
        + "        bb['target_estimate_in_palm']=det['target_xyz']\n"
        + "        bb['confidence']=1.0\n",
    )
    run_p2.write_json(output / "registration.json", {
        "purpose": "interface regression only; the reach witness never moves the arm",
        "confidence": "binary acceptance of the archived detector; not a calibrated probability",
        "archive": run_p2.relative(ARCHIVE), "archive_sha256": run_p2.sha(ARCHIVE),
        "initial_state_sha256": case.initial_state_sha256, "max_episodes": 2,
        "model_requests": 0,
        "driver_sha256": run_p2.sha(Path(__file__)),
        "source_sha256": [hashlib.sha256(item.encode()).hexdigest() for item in (source, adjusted)],
    })
    scope = Scope(task="TP01", assets=frozenset({case.target_category}), stage=case.task.id)
    rows = {}
    for arm, locate in (("archived", source), ("aligned", adjusted)):
        payload = agent.validate_author_ops({
            "ops": {**archived, "locate_target": locate, "reach_target": HANDOFF_WITNESS},
            "explanation": "Localization contract probe", "memory": [],
        })
        bundle = run_p2.candidate_bundle(payload, scope, case, 1, (run_p2.relative(ARCHIVE),))
        store = registry.Registry(output / arm / "registry")
        _, view = run_p2.commit_bundle(store, None, bundle, scope, arm)
        episode = output / arm / "episode"
        rows[arm] = run_p2.run_episode(case, view, "practice", episode)
        rows[arm]["final_frame_saved"] = (episode / "final_head.jpg").is_file()
        rows[arm]["episode_hashes_ok"] = evidence.verify_hashes(episode)["ok"]
    original, fixed = rows["archived"], rows["aligned"]
    passed = (
        (original["failed_op"], original["failure_code"]) == ("locate_target", "PREDICATE_UNAVAILABLE")
        and (fixed["failed_op"], fixed["failure_code"]) == ("reach_target", "JOINT_LIMIT")
        and original["plant_initial_state_sha256"] == fixed["plant_initial_state_sha256"]
        and all(not row["verified_task_success"] and not row["image_errors"]
                and row["final_frame_saved"] and row["episode_hashes_ok"] for row in rows.values())
    )
    run_p2.write_json(output / "results.json", {"passed": passed, "arms": rows})
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(0 if run(parser.parse_args().output.resolve()) else 1)
