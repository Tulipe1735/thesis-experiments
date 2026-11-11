"""Read-only probes for the frozen palm controller and public joint limits."""

import math

from experiments.cordis_t01.worker import SavedInitialRobot

# Yaw candidates and approach backoff used only to report dry-run IK feasibility.
GRASP_YAWS = (0.7, 0.0, -0.7, 1.2, -1.2, 1.8)
# Waist pitches tried for the grasp pose, in preference order after the current one.
GRASP_WAISTS = (-0.10, 0.0, -0.05, 0.05, 0.10, -0.15)
GRASP_BACKOFF_M = 0.13
# Cup bottom heights used for the placement palm targets, relative to the tray floor.
PLACE_ABOVE_M = 0.13
PLACE_LOWER_M = 0.03
# Opening the hand with the palm higher than this above the tray floor is refused.
RELEASE_MAX_PALM_ABOVE_TRAY_M = 0.12


class PoseProbe:
    def __init__(self, robot):
        self.robot = robot
        self.model, self.data, self.pelvis_id = robot.model, robot.data, robot.pelvis_id
        self.minimum_seconds = None

    def set_joints(self, targets, duration):
        self.minimum_seconds = max(
            .02,
            max(1.5 * abs(value - self.robot.targets[self.robot.ai[name]]) /
                self.robot.joint_rows[name][5] for name, value in targets.items()),
        )
        return {"status": "POSE_FEASIBLE"}

    def fk(self, side):
        return self.robot.fk(side)


def check_pose(robot, position, quaternion, seconds):
    # Use the identical IK solver and branch thresholds, substituting a sink
    # for its final joint dispatch. It copies qpos into a fresh MjData.
    probe = PoseProbe(robot)
    reply = SavedInitialRobot.move_ee(probe, "left", position, quaternion, seconds)
    if reply["status"] == "POSE_IK_REJECTED":
        return {"status": "POSE_IK_REJECTED",
                "position_error_m": round(float(reply["position_error_m"]), 5),
                "orientation_error_rad": round(float(reply["orientation_error_rad"]), 5)}
    return {
        "status": "POSE_FEASIBLE" if probe.minimum_seconds <= seconds + 1e-9
                  else "DURATION_TOO_SHORT",
        "ik_position_error_m": round(float(reply["ik_position_error_m"]), 5),
        "ik_orientation_error_rad": round(float(reply["ik_orientation_error_rad"]), 5),
        "minimum_seconds": round(float(probe.minimum_seconds), 4),
    }


def quaternion_for(action):
    if action["orientation"] == "keep":
        return None
    yaw = action["yaw"]
    return [0., 0., math.sin(yaw / 2), math.cos(yaw / 2)]


def yaw_quaternion(yaw):
    return [0., 0., math.sin(yaw / 2), math.cos(yaw / 2)]


def _yaw_rotate(yaw, vector):
    c, s = math.cos(yaw), math.sin(yaw)
    x, y, z = vector
    return [c * x - s * y, s * x + c * y, z]


def _sub(a, b):
    return [float(a[i]) - float(b[i]) for i in range(3)]


def _round(values, digits=5):
    return [round(float(value), digits) for value in values]


def grasp_probe(robot, cup_bottom_m, cup_in_palm_m, yaws=GRASP_YAWS, waists=GRASP_WAISTS):
    """Dry-run IK for a grasp pose and its approach start.

    Two things vary together here. The palm site sits `cup_in_palm_m` from the
    cup's grasp point, rotated about +Z by the grasp yaw; and the arm may only
    reach that pose at a different waist pitch. The reference controller has the
    same dependency (`adjust_reach`), and runs _repl2 show cups that are
    unreachable at -0.15 and reachable at 0.0. The probe tries the current waist
    first, then `waists`, and stops at the first feasible (waist, yaw). Nothing
    is executed and the waist is restored.
    """
    qadr = robot.model.jnt_qposadr[robot.model.joint("waist_pitch_joint").id]
    original = float(robot.data.qpos[qadr])
    try:
        current = round(original, 4)
        # The lean is the reference posture for the approach path, so prefer it
        # over whatever the arm is doing now; the current pitch is second.
        order = list(dict.fromkeys([-0.10, current, *waists]))
        attempts = []
        for waist in order:
            robot.data.qpos[qadr] = waist
            for yaw in yaws:
                rotated = _yaw_rotate(yaw, cup_in_palm_m)
                grasp = _sub(cup_bottom_m, rotated)
                behind = _sub(grasp, _yaw_rotate(yaw, (GRASP_BACKOFF_M, 0., 0.)))
                quaternion = yaw_quaternion(yaw)
                entry = {
                    "palm_yaw_rad": yaw,
                    "waist_pitch_rad": waist,
                    "quaternion_xyzw": _round(quaternion, 4),
                    "grasp_xyz_m": _round(grasp),
                    "approach_start_xyz_m": _round(behind),
                }
                for name, point in (("grasp", grasp), ("approach_start", behind)):
                    entry[name] = check_pose(robot, point, quaternion, 3.)
                attempts.append({"waist_pitch_rad": waist, "palm_yaw_rad": yaw,
                                 "grasp": entry["grasp"]["status"]})
                if entry["grasp"]["status"] == "POSE_FEASIBLE":
                    return {"cup_in_palm_m": _round(cup_in_palm_m),
                            "backoff_m": GRASP_BACKOFF_M, "yaws": [entry],
                            "attempts": attempts}
        return {"cup_in_palm_m": _round(cup_in_palm_m), "backoff_m": GRASP_BACKOFF_M,
                "yaws": [], "attempts": attempts}
    finally:
        robot.data.qpos[qadr] = original


def place_probe(tray_floor_m, cup_in_palm_m, yaw=GRASP_YAWS[0]):
    """Palm poses that put the cup bottom over the tray centre.

    Uses the same rigid transform as the grasp. Aiming the palm at the tray
    centre leaves the cup one `cup_in_palm_m` away, which is the placement
    offset observed in runs/t01_agent_pilot_20261104_003 and _20261104_004.
    """
    rotated = _yaw_rotate(yaw, cup_in_palm_m)
    return {
        "palm_yaw_rad": yaw,
        "above_xyz_m": _round([tray_floor_m[0] - rotated[0],
                               tray_floor_m[1] - rotated[1],
                               tray_floor_m[2] + PLACE_ABOVE_M - rotated[2]]),
        "lower_xyz_m": _round([tray_floor_m[0] - rotated[0],
                               tray_floor_m[1] - rotated[1],
                               tray_floor_m[2] + PLACE_LOWER_M - rotated[2]]),
        "cup_bottom_at_lower_m": round(tray_floor_m[2] + PLACE_LOWER_M, 4),
        "release_palm_below_z_m": round(tray_floor_m[2] + RELEASE_MAX_PALM_ABOVE_TRAY_M, 4),
    }


def joint_bounds(robot, name):
    i = robot.ai[name]
    lo, hi = robot.model.jnt_range[robot.joint_ids[i]]
    return {"range_rad": [float(lo), float(hi)], "velocity_limit_rad_s": robot.joint_rows[name][5]}
