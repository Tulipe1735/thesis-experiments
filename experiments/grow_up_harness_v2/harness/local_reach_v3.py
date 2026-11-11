"""Strict v3: unchanged physical rules, explicit timestamp and evidence quality.

No interpolation, gap bridging or relaxation of v2's 0.051 second bound.
"""
import numpy as np
from . import local_reach

VERSION = "explicit-pose-replay-v3"
MAX_GAP_S = .051


def timing_quality(times):
    times = np.asarray(times, dtype=float)
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("trajectory timestamps must be finite and strictly increasing")
    gaps = [{"from_s": float(a), "to_s": float(b), "gap_s": float(b-a)}
            for a, b in zip(times[:-1], times[1:]) if b-a > MAX_GAP_S]
    return {"sample_gap_max_s": MAX_GAP_S, "gaps": gaps, "samples": len(times),
            "max_observed_gap_s": float(np.diff(times).max()) if len(times)>1 else None}


def evaluate(episode, contract, **kwargs):
    with np.load(episode / "trajectory.npz", allow_pickle=False) as trace:
        quality = timing_quality(trace["time"])
        lengths = [len(trace[k]) for k in ("time", "qpos", "qvel", "actuator_force")]
        if len(set(lengths)) != 1:
            raise ValueError("trajectory arrays have unequal lengths")
    result = local_reach.evaluate(episode, contract, **kwargs)
    rows = result["rows"]
    end = rows[-1]["time"] if rows else None
    terminal_gaps = [g for g in quality["gaps"] if end is not None
                     and g["to_s"] > max(kwargs.get("start_s", 0.), end-contract["hold_s"])
                     and g["from_s"] < end]
    result.update(evaluator_version=VERSION, timing_quality=quality,
                  terminal_window_gaps=terminal_gaps,
                  evidence_status=("success" if result["verified_local_success"] else
                                   "insufficient_sampling" if terminal_gaps and result["all_frames_safe"]
                                   and all(r["at_pose"] for r in rows if r["time"] >= end-contract["hold_s"])
                                   and not result["execution_error"] and not result["guard"] else "failure"))
    return result
