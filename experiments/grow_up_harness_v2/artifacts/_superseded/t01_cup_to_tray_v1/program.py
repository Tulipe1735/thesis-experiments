"""T01 cup-to-tray program distilled from the S1C0 success episodes.

Four entry points, not one open-loop list, because the tray band is only
+/-13 mm wide and contact changes the geometry:

- plan()      approach and grasp, choosing the first grasp yaw that passes IK
- grasp_parameters()  freeze the accepted yaw and cup offset for the rest
- lift()      straight up first (a diagonal lift tips a tall thin cup), then across
- correct()   re-centre the cup over the tray from the observation
- release()   descend, open, retreat, finish

No harness import: the module only needs the observation dictionary.
"""

import math

YAW = 0.7
WAIST_PITCH = -0.10
RAISE = (-0.07, 0.34, 0.09)
CLEAR = (-0.04, 0.34, 0.30)
CLOSE = (
    ("left_hand_thumb_0_joint", 0.0),
    ("left_hand_thumb_1_joint", 0.65),
    ("left_hand_thumb_2_joint", 0.65),
    ("left_hand_middle_0_joint", -0.8),
    ("left_hand_middle_1_joint", -0.6),
    ("left_hand_index_0_joint", -0.8),
    ("left_hand_index_1_joint", -0.6),
)
STEP_M = 0.035
RETREAT_M = 0.045
HOLD_BEFORE_OPEN_S = 1.5
SETTLE_AFTER_OPEN_S = 1.5
CORRECTION_STEP_M = 0.04
CORRECTION_TOLERANCE_M = 0.004
PLACE_ABOVE_M = 0.13
PLACE_LOWER_M = 0.03
VERTICAL_CLEAR_M = 0.12


def _walk(start, end, limit=STEP_M):
    """Points from start towards end, none further than limit from the previous."""
    gap = math.dist(start, end)
    count = max(1, math.ceil(gap / limit))
    return [[start[i] + (end[i] - start[i]) * step / count for i in range(3)]
            for step in range(1, count + 1)]


def _move(point, yaw, orientation="yaw", seconds=2.0):
    return {"op": "move", "x": point[0], "y": point[1], "z": point[2],
            "yaw": yaw, "orientation": orientation, "seconds": seconds}


def _chosen_yaw(probe):
    """First candidate whose grasp pose passes the dry-run IK check."""
    for entry in probe["yaws"]:
        if entry.get("grasp", {}).get("status") == "POSE_FEASIBLE":
            return entry
    raise ValueError("GRASP_UNREACHABLE: no candidate yaw passes the IK check")


def plan(observation):
    """Approach and grasp the cup. Ends with the hand closed, cup still low."""
    probe = observation.get("grasp_probe")
    place = observation.get("place_probe")
    if not probe or not place:
        raise ValueError("plan needs grasp_probe and place_probe in the observation")
    chosen = _chosen_yaw(probe)
    grasp_yaw = chosen["palm_yaw_rad"]
    approach = chosen["approach_start_xyz_m"]
    grasp = chosen["grasp_xyz_m"]
    palm = list(observation["left_palm"]["position_m"])

    commands = []
    for point in _walk(palm, RAISE):
        commands.append(_move(point, 0.0, "keep"))
    for point in _walk(RAISE, CLEAR):
        commands.append(_move(point, grasp_yaw))
    waist = chosen.get("waist_pitch_rad", WAIST_PITCH)
    commands.append({"op": "joints", "seconds": 1.0,
                     "targets": [{"joint": "waist_pitch_joint", "radians": waist}]})
    commands.append({"op": "wait", "seconds": 1.0})
    commands.append(_move(CLEAR, grasp_yaw))
    for point in _walk(CLEAR, approach):
        commands.append(_move(point, grasp_yaw))
    for point in _walk(approach, grasp):
        commands.append(_move(point, grasp_yaw))
    commands.append({"op": "joints", "seconds": 2.0,
                     "targets": [{"joint": name, "radians": value} for name, value in CLOSE]})
    commands.append({"op": "wait", "seconds": 0.5})
    return commands


def grasp_parameters(observation):
    """Freeze the accepted grasp yaw and cup offset while the cup is visible."""
    probe = observation.get("grasp_probe")
    tray = observation.get("tray_floor_center_m")
    if not probe or tray is None:
        raise ValueError("grasp_parameters needs grasp_probe and tray_floor_center_m")
    chosen = _chosen_yaw(probe)
    return {"palm_yaw_rad": chosen["palm_yaw_rad"],
            "waist_pitch_rad": chosen.get("waist_pitch_rad", WAIST_PITCH),
            "cup_in_palm_m": list(probe["cup_in_palm_m"]),
            "tray_floor_m": list(tray)}


def _place_palm(params, height_m):
    yaw, (ox, oy, oz) = params["palm_yaw_rad"], params["cup_in_palm_m"]
    rx, ry = math.cos(yaw) * ox - math.sin(yaw) * oy, math.sin(yaw) * ox + math.cos(yaw) * oy
    tray = params["tray_floor_m"]
    return [tray[0] - rx, tray[1] - ry, tray[2] + height_m - oz]


def lift(observation, params):
    """Carry the grasped cup above the tray: straight up first, then across."""
    palm = list(observation["left_palm"]["position_m"])
    yaw = params["palm_yaw_rad"]
    above = _place_palm(params, PLACE_ABOVE_M)
    clear = [palm[0], palm[1], max(palm[2] + VERTICAL_CLEAR_M, above[2])]
    commands = [_move(point, yaw, "keep") for point in _walk(palm, clear)]
    commands += [_move(point, yaw, "keep") for point in _walk(clear, above)]
    return commands


def correct(observation, params):
    """One palm move that brings the observed cup over the tray centre, or []."""
    cups = observation.get("cup_bottoms_m") or []
    tray = params["tray_floor_m"]
    if len(cups) != 1:
        return []
    dx, dy = tray[0] - cups[0][0], tray[1] - cups[0][1]
    if math.hypot(dx, dy) <= CORRECTION_TOLERANCE_M:
        return []
    palm = list(observation["left_palm"]["position_m"])
    gap = math.hypot(dx, dy)
    scale = min(1.0, CORRECTION_STEP_M / gap)
    point = [palm[0] + dx * scale, palm[1] + dy * scale, palm[2]]
    return [_move(point, params["palm_yaw_rad"], "keep", 1.5)]


def release(observation, params):
    """Descend to the placement pose, open, retreat and finish."""
    palm = list(observation["left_palm"]["position_m"])
    yaw = params["palm_yaw_rad"]
    # Descend under the palm the lift actually reached; forcing the nominal x/y
    # here adds a lateral correction of a few millimetres and was enough to flip
    # this state from pass to a 1.4 mm miss (runs _011 vs _012).
    lower = [palm[0], palm[1], _place_palm(params, PLACE_LOWER_M)[2]]
    commands = [_move(point, yaw, "keep") for point in _walk(palm, lower)]
    commands.append({"op": "wait", "seconds": HOLD_BEFORE_OPEN_S})
    commands.append({"op": "joints", "seconds": 2.0,
                     "targets": [{"joint": name, "radians": 0.0} for name, _ in CLOSE]})
    commands.append({"op": "wait", "seconds": SETTLE_AFTER_OPEN_S})
    retreat = list(lower)
    for _ in range(2):
        retreat = [retreat[0], retreat[1], retreat[2] + RETREAT_M]
        commands.append(_move(retreat, yaw, "keep"))
    commands.append({"op": "wait", "seconds": 1.2})
    commands.append({"op": "finish"})
    return commands
