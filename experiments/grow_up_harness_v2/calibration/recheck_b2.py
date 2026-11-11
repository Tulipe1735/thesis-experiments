"""Recompute a B2 episode's checks without touching the episode.

The first B2 run wrote ``results.json`` with a wrong check key: it looked for
``event["op"]`` while the plant records ``event["request"]["op"]``. The
physics, the actions and the verdict are unchanged; only the derived label
was wrong. This writes ``results_recheck.json`` next to the episode so the
registered record carries a correct, reproducible summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.t0_agent_v1.common import write_new  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode")
    args = parser.parse_args(argv)

    folder = Path(args.episode).resolve()
    actions = json.loads((folder / "actions.json").read_text(encoding="utf-8"))
    execution = json.loads((folder / "execution.json").read_text(encoding="utf-8"))
    verdict = json.loads((folder / "independent_verification.json").read_text(encoding="utf-8"))

    checks = {
        "episode_is_physical": execution["simulation_seconds"] > 0.0,
        "no_joint_commands": all(item["request"].get("op") == "wait" for item in actions),
        "actions_are_wait_only": len(actions) > 0,
        "negative_control_not_credited": verdict["verified_task_success"] is False,
        "goal_not_satisfied": verdict["goal_satisfied"] is False,
    }
    payload = {
        "date": "2026-11-03",
        "kind": "b2_negative_control_recheck",
        "episode": str(folder.relative_to(ROOT)),
        "note": "derived checks only; actions.json, execution.json and integration_states.npz are unchanged",
        "actions": len(actions),
        "simulation_seconds": execution["simulation_seconds"],
        "checks": checks,
        "passed": all(value is True for value in checks.values()),
        "verdict": verdict,
    }
    write_new(folder / "results_recheck.json", payload)
    print(json.dumps({"passed": payload["passed"], "checks": checks}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
