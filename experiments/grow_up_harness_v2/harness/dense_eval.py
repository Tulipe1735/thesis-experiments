"""Dense, replay-only scores beside the unchanged official T01 verdict.

The official predicate remains ``experiments/t0_agent_v1/tray_verify.py``.
This module does not change it and never promotes an artifact. It turns saved
``verified_samples.json`` rows into a continuous score and a failure class so
IL/RL and data curation can use partial progress instead of a single 1 mm gate.

All values are recomputed from saved physical samples; no plant is stepped.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Same thresholds as the frozen official evaluator. Keep them here only for
# decomposition; the official verdict is still read from independent_verification.
T = {
    "margin_m": 0.001,
    "support_N": 0.5,
    "hand_N": 0.1,
    "other_N": 0.1,
    "height_m": 0.004,
    "tilt_deg": 10.0,
    "linear_m_s": 0.02,
    "angular_rad_s": 0.2,
    "pelvis_tilt_deg": 5.0,
    "pelvis_drift_m": 0.03,
    "stable_s": 1.0,
}


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _final_cup(verification: dict) -> dict:
    return verification["final"]["cups"]["task_cup"]


def _passes(item: dict, *, margin_floor: float) -> bool:
    return bool(
        item["footprint_margin_m"] >= margin_floor
        and item["tray_floor_support_N"] >= T["support_N"]
        and item["hand_contact_N"] < T["hand_N"]
        and item["other_object_contact_N"] < T["other_N"]
        and abs(item["support_height_error_m"]) <= T["height_m"]
        and item["cup_tilt_deg"] <= T["tilt_deg"]
        and item["linear_speed_m_s"] <= T["linear_m_s"]
        and item["angular_speed_rad_s"] <= T["angular_rad_s"]
        and item["pelvis_tilt_deg"] <= T["pelvis_tilt_deg"]
        and item["pelvis_drift_m"] <= T["pelvis_drift_m"]
    )


def _hold(rows: list[dict], *, margin_floor: float) -> tuple[float, float | None]:
    started = None
    longest = 0.0
    first = None
    for row in rows:
        if _passes(row["cups"]["task_cup"], margin_floor=margin_floor):
            if started is None:
                started = row["time"]
            longest = max(longest, row["time"] - started)
            if first is None and row["time"] - started >= T["stable_s"] - 1e-8:
                first = row["time"]
        else:
            started = None
    return longest, first


def score_case(verification_path: Path) -> dict:
    verification_path = Path(verification_path)
    episode = verification_path.parent
    verification = json.loads(verification_path.read_text())
    rows = json.loads((episode / "verified_samples.json").read_text())
    final = _final_cup(verification)
    relaxed_hold, relaxed_first = _hold(rows, margin_floor=0.0)
    official_hold = float(verification.get("terminal_simultaneous_stable_s", 0.0))
    official = bool(verification.get("verified_success"))

    margin = float(final["footprint_margin_m"])
    support = float(final["tray_floor_support_N"])
    hand = float(final["hand_contact_N"])
    other = float(final["other_object_contact_N"])
    height = abs(float(final["support_height_error_m"]))
    tilt = float(final["cup_tilt_deg"])
    linear = float(final["linear_speed_m_s"])
    angular = float(final["angular_speed_rad_s"])
    pelvis_tilt = float(final["pelvis_tilt_deg"])
    pelvis_drift = float(final["pelvis_drift_m"])

    # Normalised components: 1 is best. These are diagnostics, not the task gate.
    margin_score = _clip((margin + 0.02) / 0.026)
    support_score = _clip(support / 1.0)
    hand_score = 1.0 if hand < T["hand_N"] else 0.0
    other_score = 1.0 if other < T["other_N"] else 0.0
    height_score = _clip(1.0 - height / 0.02)
    tilt_score = _clip(1.0 - tilt / 20.0)
    speed_score = _clip(1.0 - max(linear / T["linear_m_s"], angular / T["angular_rad_s"]))
    pelvis_score = min(_clip(1.0 - pelvis_tilt / T["pelvis_tilt_deg"]),
                       _clip(1.0 - pelvis_drift / T["pelvis_drift_m"]))
    stable_score = _clip(relaxed_hold / T["stable_s"])

    critical = (
        support >= T["support_N"], hand < T["hand_N"], other < T["other_N"],
        height <= T["height_m"], tilt <= T["tilt_deg"], linear <= T["linear_m_s"],
        angular <= T["angular_rad_s"], pelvis_tilt <= T["pelvis_tilt_deg"],
        pelvis_drift <= T["pelvis_drift_m"],
    )
    dense = (0.30 * margin_score + 0.15 * support_score + 0.15 * stable_score
             + 0.10 * height_score + 0.10 * tilt_score + 0.10 * min(hand_score, other_score)
             + 0.10 * speed_score * pelvis_score)
    if not all(critical):
        dense = min(dense, 0.45)

    classes = []
    if verification.get("execution_error"):
        classes.append("execution_error")
    if verification.get("protection"):
        classes.append("protection")
    if not verification.get("initial_valid", True):
        classes.append("invalid_initial")
    if support < T["support_N"]:
        classes.append("no_tray_support")
    if hand >= T["hand_N"]:
        classes.append("hand_contact")
    if other >= T["other_N"]:
        classes.append("rim_or_other_contact")
    if height > T["height_m"]:
        classes.append("height_error")
    if tilt > T["tilt_deg"]:
        classes.append("tilt")
    if margin < 0.0:
        classes.append("outside_tray")
    elif margin < T["margin_m"]:
        classes.append("rim_overhang_sub_mm")
    if relaxed_hold < T["stable_s"]:
        classes.append("not_stable")
    if not classes:
        classes.append("official_failure_unclassified" if not official else "none")

    relaxed_success = bool(relaxed_hold >= T["stable_s"] and not verification.get("execution_error")
                           and not verification.get("protection")
                           and verification.get("initial_valid", True)
                           and _passes(final, margin_floor=0.0))
    near_miss = bool(relaxed_success and not official)
    max_lift = max(float(row["cups"]["task_cup"]["lift_m"]) for row in rows)
    return {
        "case": episode.parent.name if episode.name == "episode" else episode.name,
        "episode": str(episode.relative_to(ROOT)),
        "official_success": official,
        "relaxed_margin_success": relaxed_success,
        "near_miss": near_miss,
        "dense_score": round(float(dense), 6),
        "official_terminal_hold_s": official_hold,
        "relaxed_terminal_hold_s": relaxed_hold,
        "relaxed_first_stable_s": relaxed_first,
        "max_lift_m": max_lift,
        "final": {
            "footprint_margin_m": margin, "tray_floor_support_N": support,
            "hand_contact_N": hand, "other_object_contact_N": other,
            "support_height_error_m": float(final["support_height_error_m"]),
            "cup_tilt_deg": tilt, "linear_speed_m_s": linear, "angular_speed_rad_s": angular,
            "pelvis_tilt_deg": pelvis_tilt, "pelvis_drift_m": pelvis_drift,
        },
        "components": {
            "margin": margin_score, "support": support_score, "hand": hand_score,
            "other_contact": other_score, "height": height_score, "tilt": tilt_score,
            "speed": speed_score, "pelvis": pelvis_score, "stable": stable_score,
        },
        "failure_classes": classes,
        "stage_progress": {
            "lifted_10cm": bool(max_lift >= 0.10),
            "reached_tray_zone": bool(any(row["cups"]["task_cup"]["footprint_margin_m"] > -0.02
                                         for row in rows)),
            "released_final": bool(hand < T["hand_N"]),
            "settled_relaxed": bool(relaxed_hold >= T["stable_s"]),
            "official_settled": bool(official_hold >= T["stable_s"]),
        },
        "diagnostic_only": True,
        "official_verdict_changed": False,
    }
