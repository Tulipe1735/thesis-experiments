"""Acceptance check for the v2 palm_near_target predicate.

Uses the reference-chain measurement and the registered constants. The positive
case must pass, both one-axis negatives must fail, and a mixed frame must raise
PredicateUnavailable rather than returning False.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "experiments/grow_up_harness_v2") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import predicates  # noqa: E402
from experiments.t0_agent_v1.common import write_new  # noqa: E402

PALM = [0.3223204661074674, 0.2620271455689017, 0.2232517649669975]
TARGET = [0.413142016468474, 0.2891856973504275, 0.1683119465831284]


def state(palm, target, palm_frame="current_pelvis", target_frame="current_pelvis") -> dict:
    return {
        "target": "cup",
        "objects": {
            "cup": {
                "position_m": [0.0, 0.0, 0.0],
                "pelvis_position_m": list(target),
                "frame": target_frame,
                "initial_bottom_z_m": 0.0,
                "mass_kg": 0.2,
                "hand_contact_N": 1.0,
                "upward_support_N": {"left_hand": 2.0},
                "linear_speed_m_s": 0.0,
                "angular_speed_rad_s": 0.0,
            }
        },
        "palm": {"position_m": list(palm), "frame": palm_frame},
        "robot": {"tilt_deg": 0.0, "drift_m": 0.0},
        "protection": None,
        "external_forces": False,
        "equality_constraints": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)

    cases = []
    positive = state(PALM, TARGET)
    cases.append(dict(name="reference_positive", expected=True, value=predicates.evaluate("palm_near_target", positive)))
    horizontal = state([TARGET[0] + 0.2, TARGET[1], TARGET[2]], TARGET)
    cases.append(dict(name="horizontal_negative", expected=False, value=predicates.evaluate("palm_near_target", horizontal)))
    vertical = state([TARGET[0], TARGET[1], TARGET[2] + 0.12], TARGET)
    cases.append(dict(name="vertical_negative", expected=False, value=predicates.evaluate("palm_near_target", vertical)))
    mixed = state(PALM, TARGET, palm_frame="current_pelvis", target_frame="world")
    try:
        predicates.evaluate("palm_near_target", mixed)
        mixed_result = "did_not_raise"
    except predicates.PredicateUnavailable:
        mixed_result = "PredicateUnavailable"
    cases.append(dict(name="mixed_frame", expected="PredicateUnavailable", value=mixed_result))

    summary = {
        "date": "2026-11-04",
        "boundary": "simulation",
        "kind": "tp01_palm_near_target_v2_check",
        "predicate_version": predicates.VERSION,
        "constants": {
            "horizontal_m": predicates.THRESHOLDS["palm_horizontal_m"],
            "vertical_m": predicates.THRESHOLDS["palm_vertical_m"],
        },
        "reference": {
            "palm_pelvis_m": PALM,
            "target_pelvis_m": TARGET,
            "horizontal_m": 0.09479525802932694,
            "vertical_m": 0.054939818383869105,
        },
        "cases": cases,
        "passed": all(item["value"] == item["expected"] for item in cases),
    }
    write_new(output / "results.json", summary)
    print(json.dumps(summary, indent=1)[-1200:])
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
