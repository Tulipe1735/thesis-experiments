"""B1 fallback: preserve the frozen training candidate's failure on S*.

S* is ``TP01_reach_train_000`` (``case_01`` of the frozen reach dataset). The
policy is the frozen 2026-10-26 training candidate ``candidate_v2.py``, executed
through the public ``execute_case`` path with its public task dict and the
registered 120 s / 400-call budget. Nothing here is retried or repaired: the
episode is the fallback baseline of the baseline family, and its failure is the
result.

Pairing is deliberately out of scope. A candidate can only be paired against a
positive reference once the strict seven-step reference chain is itself a
positive example; until then this episode only preserves what the fallback does.

An unexpected ``verified_task_success`` is not a win: it means the fallback
baseline is misclassified, so the script records it as
``B1_UNEXPECTED_SUCCESS`` and exits 123 for the operator to investigate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "grasp_optimization") not in sys.path:
    sys.path.insert(0, str(ROOT / "grasp_optimization"))

from experiments.grow_up_harness_v2.harness import tp01  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.tabletop_training_plant import execute_case  # noqa: E402
from experiments.t0_agent_v1.train_tp01 import body_packet  # noqa: E402

DATE = "2026-11-03"
DATASET = ROOT / "experiments/t0_agent_v1/tp01_reach_dataset_20261026_001"
INSTANCE = "TP01_reach_train_000"
ALIAS = "case_01"
SOURCE = ROOT / "experiments/t0_agent_v1/tp01_training_20261026_003/candidate_v2.py"
BUDGET_S = 120.0
MAX_CALLS = 400
PAIRING_NOTE = (
    "Pairing waits until the strict seven-step reference chain is a positive "
    "example. This episode only preserves the fallback failure."
)


def s_star() -> tuple[tp01.TP01Case, Path]:
    """Load the frozen S* case and refuse a scene or fixture that has drifted."""
    cases = tp01.load_cases(DATASET)
    chosen = [case for case in cases if case.instance_id == INSTANCE]
    if len(chosen) != 1 or chosen[0].alias != ALIAS:
        raise SystemExit(f"{INSTANCE} is not the single {ALIAS} of the reach dataset")
    case = chosen[0]
    scene = DATASET / "scenes" / (ALIAS + ".xml")
    registry = read(DATASET / "scenes" / (ALIAS + ".json"))
    if sha(scene) != registry["sha256"]:
        raise SystemExit("frozen reach scene changed")
    if sha(case.case_path / "instance.json") != registry["instance_sha256"]:
        raise SystemExit("frozen reach instance changed")
    if sha(case.case_path / "initial_state.json") != case.initial_state_sha256:
        raise SystemExit("frozen reach initial state changed")
    return case, scene


def public_task(case: tp01.TP01Case) -> dict:
    """The task dict the frozen training candidate was executed with."""
    target = next(item for item in case.instance["objects"] if item["is_target"])
    return dict(
        target_category=case.target_category,
        nominal_rgba=target["asset"]["rgba"],
        minimum_lift_m=0.10,
        stable_s=1.0,
        terminal_mode="held",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--budget", type=float, default=BUDGET_S)
    parser.add_argument("--max-calls", type=int, default=MAX_CALLS)
    args = parser.parse_args(argv)

    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    output = output_root / ALIAS

    case, scene = s_star()
    scene_sha256 = sha(scene)
    task = public_task(case)
    source_text = SOURCE.read_text(encoding="utf-8")
    profile = body_packet()

    print("B1_START", INSTANCE, relative(scene), task["target_category"], flush=True)
    status = "B1_FALLBACK_FAILURE_PRESERVED"
    try:
        episode = execute_case(
            scene,
            case.instance,
            case.case_path,
            output,
            source_text,
            profile,
            task,
            budget=args.budget,
            max_calls=args.max_calls,
        )
    except Exception as exc:  # keep the failure; never retry silently
        episode = dict(
            verified_task_success=False,
            terminal_stable_s=0.0,
            simulation_seconds=None,
            policy_calls=0,
            low_level_commands=0,
            error={"type": type(exc).__name__, "message": str(exc)[:600]},
            guard=None,
        )
        status = "B1_EPISODE_ERROR"

    verdict = dict(
        verified_task_success=bool(episode["verified_task_success"]),
        terminal_stable_s=episode.get("terminal_stable_s"),
    )
    if verdict["verified_task_success"]:
        status = "B1_UNEXPECTED_SUCCESS"

    summary = {
        "date": DATE,
        "boundary": "simulation",
        "label": "B1_fallback",
        "instance": INSTANCE,
        "alias": ALIAS,
        "dataset": relative(DATASET),
        "scene": relative(scene),
        "scene_sha256": scene_sha256,
        "source": relative(SOURCE),
        "source_sha256": sha(SOURCE),
        "initial_state_sha256": case.initial_state_sha256,
        "budget_s": args.budget,
        "max_calls": args.max_calls,
        "task": task,
        "verdict": verdict,
        "simulation_seconds": episode.get("simulation_seconds"),
        "policy_calls": episode.get("policy_calls"),
        "low_level_commands": episode.get("low_level_commands"),
        "error": episode.get("error"),
        "guard": episode.get("guard"),
        "folder": relative(output),
        "paired": False,
        "pairing_note": PAIRING_NOTE,
        "status": status,
        "counted_as_agent_success": False,
        "formal_skill_promotion": False,
    }
    write_new(output_root / "results.json", summary)
    print(
        "B1_SUMMARY",
        json.dumps(
            {
                "status": status,
                "verified_task_success": verdict["verified_task_success"],
                "terminal_stable_s": verdict["terminal_stable_s"],
                "simulation_seconds": summary["simulation_seconds"],
                "error": summary["error"],
                "guard": summary["guard"],
                "folder": summary["folder"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if status == "B1_UNEXPECTED_SUCCESS":
        return 123
    return 0 if status == "B1_FALLBACK_FAILURE_PRESERVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
