import math

JOINTS = ["left_elbow_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_wrist_pitch_joint", "left_wrist_roll_joint", "left_wrist_yaw_joint"]
PLAN = [["m",[[0,-0.38025],[1,-0.11972],[2,0.6196],[3,0.49371],[4,0.70626],[5,-0.63303],[6,0.29063]]],["m",[[0,-0.45511],[1,-0.03074],[2,0.61932],[3,0.56668],[4,0.72216],[5,-0.67484],[6,0.26826]]],["m",[[0,-0.52048],[1,0.06046],[2,0.61325],[3,0.64643],[4,0.7301],[5,-0.71607],[6,0.23743]]],["m",[[0,-0.57406],[1,0.1509],[2,0.60089],[3,0.72889],[4,0.72995],[5,-0.75527],[6,0.19749]]],["m",[[0,-0.60781],[1,0.10345],[2,0.65925],[3,0.78828],[4,0.84372],[5,-0.84236],[6,0.24449]]],["m",[[0,-0.61954],[1,0.04355],[2,0.72451],[3,0.85328],[4,0.95806],[5,-0.93727],[6,0.29648]]],["m",[[0,-0.61102],[1,-0.031],[2,0.79571],[3,0.90812],[4,1.06977],[5,-1.03423],[6,0.35606]]],["m",[[0,-0.58232],[1,-0.11612],[2,0.86993],[3,0.95035],[4,1.17406],[5,-1.13041],[6,0.42144]]],["w",10]]
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
