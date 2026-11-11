OPEN_JOINTS = ["left_hand_thumb_0_joint", "left_hand_thumb_1_joint",
               "left_hand_thumb_2_joint", "left_hand_middle_0_joint",
               "left_hand_middle_1_joint", "left_hand_index_0_joint",
               "left_hand_index_1_joint"]


def init(profile):
    return {"phase": "open"}


def act(observation, task, state):
    if not isinstance(state, dict) or "phase" not in state:
        state = {"phase": "open"}
    if state["phase"] == "done":
        return {"action": {"op": "done"}, "state": state}
    joints = observation.get("joints") or {}
    targets = {}
    for name in OPEN_JOINTS:
        if name not in joints:
            continue
        joint = joints[name]
        current = float(joint.get("target", joint.get("q", 0.0)))
        if abs(current) <= 0.01:
            continue
        targets[name] = current + max(-0.04, min(0.04, -current))
    if not targets:
        state["phase"] = "done"
        return {"action": {"op": "done"}, "state": state}
    return {"action": {"op": "set_joints", "targets": targets, "duration": 0.2}, "state": state}
