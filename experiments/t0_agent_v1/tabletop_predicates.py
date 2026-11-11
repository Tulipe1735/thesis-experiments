"""Tabletop task predicates; preserve the existing placement evaluator unchanged."""
from copy import deepcopy
import math

from .diversity_predicates import LIMITS, evaluate_trace as placement_trace
from .diversity_predicates import frame_predicates as placement_frame

VERSION = 'tabletop-predicates-v1'


def frame_predicates(instance, frame):
    held = [g for g in instance['goals'] if g['predicate'] == 'HeldLifted']
    if not held:
        return placement_frame(instance, frame)
    if len(held) != 1 or len(instance['goals']) != 1:
        raise ValueError('First tabletop release supports one held target per grasp task')
    goal = held[0]
    item = next(x for x in instance['objects'] if x['name'] == goal['object'])
    state = frame['objects'][item['name']]
    supports = state['upward_support_N']
    hand_support = sum(v for k,v in supports.items() if '_hand_' in k)
    nonhand_support = sum(v for k,v in supports.items() if '_hand_' not in k)
    return bool(state['position_m'][2]-goal['initial_bottom_z_m'] >= goal['minimum_lift_m']
        and hand_support >= .25*item['asset']['mass_kg']*9.81
        and nonhand_support < .1 and state['hand_contact_N'] >= .1
        and state['linear_speed_m_s'] <= LIMITS['linear_speed_m_s']
        and state['angular_speed_rad_s'] <= LIMITS['angular_speed_rad_s']
        and all(frame['objects'][x['name']]['hand_contact_N'] < .1
                for x in instance['objects'] if x['name'] != item['name']))


def evaluate_trace(instance, frames, *, initial_valid=False, execution_error=None, protection=None):
    if not any(g['predicate'] == 'HeldLifted' for g in instance['goals']):
        result = placement_trace(instance, frames, initial_valid=initial_valid,
                                 execution_error=execution_error, protection=protection)
        result['evaluator_version'] = VERSION
        return result
    if not frames:
        raise ValueError('Missing independent evidence')
    instance = deepcopy(instance)
    # Lift is measured from the actual accepted episode initial state.
    for goal in instance['goals']:
        goal['initial_bottom_z_m'] = frames[0]['objects'][goal['object']]['position_m'][2]
    start, previous, stable, robot_valid = None, None, 0., True
    for frame in frames:
        time = frame['time']
        if not math.isfinite(time) or previous is not None and time <= previous:
            raise ValueError('Evidence times must increase')
        gap = previous is not None and time-previous > LIMITS['max_sample_gap_s']
        if frame_predicates(instance, frame):
            start = time if start is None or gap else start
            stable = time-start
        else:
            start, stable = None, 0.
        robot = frame['robot']
        robot_valid = (robot_valid and robot is not None and robot['tilt_deg'] <= 5.
                       and robot['drift_m'] <= .03 and not frame['external_forces']
                       and frame['equality_constraints'] == 0)
        previous = time
    goal = stable+1e-9 >= LIMITS['stable_s']
    return dict(goal_satisfied=goal, terminal_simultaneous_stable_s=stable,
                robot_evidence_valid=bool(robot_valid), initial_valid=initial_valid,
                verified_task_success=bool(goal and robot_valid and initial_valid
                                           and not execution_error and not protection),
                execution_error=execution_error, protection=protection, evaluator_version=VERSION,
                sampled_evidence=True)
