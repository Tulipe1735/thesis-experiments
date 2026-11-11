import math

JOINTS = ["left_elbow_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_wrist_pitch_joint", "left_wrist_roll_joint", "left_wrist_yaw_joint"]
PLAN = [["m",[[0,-0.57249],[1,-0.07828],[2,0.52617],[3,0.14263],[4,0.77711],[5,-0.68587],[6,0.25704]]],["m",[[0,-0.67158],[1,0.01093],[2,0.54121],[3,0.20496],[4,0.80019],[5,-0.73224],[6,0.25531]]],["m",[[0,-0.76276],[1,0.10657],[2,0.55215],[3,0.27728],[4,0.81305],[5,-0.77966],[6,0.2447]]],["m",[[0,-0.84384],[1,0.20839],[2,0.55747],[3,0.35808],[4,0.81428],[5,-0.82628],[6,0.22267]]],["m",[[0,-0.87559],[1,0.13284],[2,0.58645],[3,0.42763],[4,0.92813],[5,-0.94413],[6,0.28699]]],["m",[[0,-0.87679],[1,-0.00016],[2,0.63022],[3,0.53327],[4,1.08699],[5,-1.15317],[6,0.4128]]],["m",[[0,-0.84365],[1,-0.12344],[2,0.68019],[3,0.5999],[4,1.19836],[5,-1.35598],[6,0.55659]]],["m",[[0,-0.78058],[1,-0.23679],[2,0.75027],[3,0.62633],[4,1.25709],[5,-1.56619],[6,0.72429]]],["w",10]]
STEP_S = 0.15
WAIT_S = 0.2


def init(profile):
    return {"i": 0, "w": 0}


def act(observation, task, state):
    joints = observation["joints"]
    while state["i"] < len(PLAN):
        kind, value = PLAN[state["i"]]
        if kind == "w":
            if state["w"] < value:
                state["w"] += 1
                return {"action": {"op": "wait", "duration": WAIT_S}, "state": state}
            state["i"] += 1
            state["w"] = 0
            continue
        steps = 0
        for index, goal in value:
            name = JOINTS[index]
            limit = 0.05 if "_hand_" in name else 0.03
            steps = max(steps, math.ceil(abs(goal - joints[name]["target"]) / limit - 1e-9))
        if steps == 0:
            state["i"] += 1
            continue
        targets = {}
        for index, goal in value:
            name = JOINTS[index]
            current = joints[name]["target"]
            if abs(goal - current) > 1e-12:
                targets[name] = current + (goal - current) / steps
        return {"action": {"op": "set_joints", "targets": targets, "duration": STEP_S}, "state": state}
    return {"action": {"op": "done"}, "state": state}
