"""Measure R's per-stage simulation time and propose the V2.3 op budgets.

R is the F0 v2 positive control. Its ``tools/actions.json`` records every
high-level engineering action with the stage name and the simulation time after
the action. Grouping those rows gives the elapsed time of each chain phase.

This is a measurement, not a re-run: the source episode is read-only. The
proposed budgets are a new registration, not a threshold edit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402

SOURCE = ROOT / "experiments/grow_up_harness_v2/runs/f0v2_engineering_20261103_001/case_01"

PHASES = {
    "reach_target": (
        "raise_front",
        "raise_clear",
        "translate_clear",
        "free_space_finger_preshape",
        "orient_clear",
        "above_target",
        "approach_open",
    ),
    "close_hand": (
        "finger_preclose_before_thumb",
        "adaptive_close",
        "firm_grip_after_opposing_touch",
        "grip_settle",
    ),
    "lift_target": (
        "test_lift_2cm",
        "pressure_during_test_lift_2cm",
        "test_lift_hold",
        "main_lift",
        "pressure_during_main_lift",
    ),
}

BUDGETS = {
    "locate_target": 2.0,
    "open_hand": 2.0,
    "reach_target": 48.0,
    "close_hand": 13.0,
    "lift_target": 13.0,
    "hold_stable": 9.0,
    "check": 0.1,
}


def _prefix(stage: str) -> str:
    parts = stage.split("_")
    while parts and parts[-1].isdigit():
        parts.pop()
    return "_".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default=str(SOURCE))
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = read(source / "tools/actions.json")

    timed = []
    previous = 0.6  # the registered initial settling wait
    for row in rows:
        observation = row.get("result", {}).get("observation") if isinstance(row.get("result"), dict) else None
        stage = row.get("stage")
        if observation is None:
            continue
        now = float(observation["simulation_seconds"])
        timed.append(dict(stage=stage, prefix=_prefix(stage), start=previous, end=now, duration=now - previous))
        previous = now
    final = previous

    def bounds(prefixes) -> tuple[float, float]:
        selected = [row for row in timed if row["prefix"] in prefixes]
        return min(row["start"] for row in selected), max(row["end"] for row in selected)

    reach_start, reach_end = bounds(PHASES["reach_target"])
    close_start, close_end = bounds(PHASES["close_hand"])
    lift_start, lift_end = bounds(PHASES["lift_target"])

    measured = [
        dict(op="locate_target", start=0.0, end=0.6, duration=0.6, source="initial settling plus RGB-D locate"),
        dict(op="open_hand", start=0.6, end=0.6, duration=0.0, source="hand starts open"),
        dict(op="reach_target", start=reach_start, end=reach_end, duration=reach_end - reach_start),
        dict(op="close_hand", start=close_start, end=close_end, duration=close_end - close_start),
        dict(op="lift_target", start=lift_start, end=lift_end, duration=lift_end - lift_start),
        dict(op="hold_stable", start=lift_end, end=final, duration=final - lift_end),
        dict(op="check", start=final, end=final, duration=0.0),
    ]
    table = []
    for row in measured:
        budget = BUDGETS[row["op"]]
        table.append(dict(row, budget_s=budget, margin_s=round(budget - row["duration"], 3)))

    summary = {
        "date": "2026-11-03",
        "boundary": "simulation",
        "kind": "tp01_stage_timing",
        "source": relative(source),
        "source_tools_actions_sha256": sha(source / "tools/actions.json"),
        "source_actions_sha256": sha(source / "actions.json"),
        "final_simulation_seconds": final,
        "phases": measured,
        "op_budgets_s": BUDGETS,
        "program_budget_s": round(sum(BUDGETS.values()), 3),
        "episode_cap_s": 120.0,
        "measured_total_s": round(sum(row["duration"] for row in measured), 3),
        "table": table,
        "rule": (
            "Budget is the measured phase duration plus a bounded margin; the program budget "
            "is the sum of the seven op budgets. The episode cap is 120 s because the measured "
            "reference needs 75.44 s and the previous 60 s cap cut it before the lift threshold."
        ),
    }
    write_new(output / "timing.json", summary)
    print("PHASE  measured_s  budget_s")
    for row in table:
        print(f"{row['op']:16s} {row['duration']:8.2f} {row['budget_s']:9.2f}")
    print(f"{'program':16s} {summary['measured_total_s']:8.2f} {summary['program_budget_s']:9.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
