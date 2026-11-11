import math


def init(profile=None):
    return {"start_s": None, "last_s": None, "calls": 0}


def act(observation, task, state):
    # Reusable numeric finish policy: bounded stationary dwell after the
    # already-executed release and 8cm backward retreat. No joint actions.
    if not isinstance(state, dict):
        state = {}
    calls = int(state.get("calls", 0)) + 1
    if calls > 32:
        return {"action": {"op": "fail", "reason": "DWELL_CALL_BUDGET"},
                "state": {"calls": calls}}

    now = float(observation.get("simulation_seconds", 0.0))
    start = state.get("start_s")
    if start is None:
        start = now
    start = float(start)
    elapsed = now - start

    # Public protection checks: guard must stay clear and no unexpected
    # remaining hand load on the released fruit.
    guard = observation.get("guard")
    if isinstance(guard, dict):
        if guard.get("contact") or guard.get("forbidden_contact") or guard.get("tripped"):
            return {"action": {"op": "fail", "reason": "GUARD"},
                    "state": {"start_s": start, "calls": calls}}
    elif guard not in (None, False, "clear", "CLEAR", "ok", "OK"):
        return {"action": {"op": "fail", "reason": "GUARD"},
                "state": {"start_s": start, "calls": calls}}

    load = observation.get("tactile_joint_load_N")
    if load is not None:
        try:
            if isinstance(load, dict):
                vals = [abs(float(v)) for v in load.values()]
            else:
                vals = [abs(float(v)) for v in load]
            if vals and max(vals) > 0.5:
                return {"action": {"op": "fail", "reason": "HAND_LOAD"},
                        "state": {"start_s": start, "calls": calls}}
        except (TypeError, ValueError):
            pass

    hold_s = 1.5
    try:
        hold_s = float(task.get("hold_s", 1.5)) if isinstance(task, dict) else 1.5
    except (TypeError, ValueError):
        hold_s = 1.5
    hold_s = min(3.0, max(1.0, hold_s))

    if elapsed >= hold_s:
        return {"action": {"op": "done"},
                "state": {"start_s": start, "calls": calls, "elapsed_s": elapsed}}

    remaining = hold_s - elapsed
    dur = min(0.20, max(0.02, remaining))
    # Snap to 0.002 grid.
    dur = round(dur / 0.002) * 0.002
    dur = min(0.20, max(0.02, dur))
    return {"action": {"op": "wait", "duration": dur},
            "state": {"start_s": start, "calls": calls, "elapsed_s": elapsed}}
