"""Bound the legacy RGB-D handoff correction without changing the controller."""
import numpy as np

from experiments.cordis_t01.guard_skills import GuardSkills, ActionFailure
from experiments.cordis_t01.handoff_guard import proposal, PerceptionError
from experiments.t0_agent_v1.common import write_new
from experiments.t0_agent_v1.tray_collision import CupObstaclePlanner


def scale_proposal(original, gain):
    if not 0. < gain <= 1.:
        raise ValueError('Correction gain must be in (0, 1]')
    result = dict(original, correction_gain=gain,
                  revision='bounded_centering_gain_v1', object_truth_used=False)
    if original['status'] == 'CORRECT':
        delta = np.asarray(original['correction_xy_m'], dtype=float)
        if delta.shape != (2,) or not np.isfinite(delta).all():
            raise ValueError('Invalid correction')
        if np.linalg.norm(delta) > .040000001:
            raise ValueError('Legacy correction exceeds frozen 40 mm bound')
        result['original_correction_xy_m'] = delta.tolist()
        result['correction_xy_m'] = (gain * delta).tolist()
        result['reason'] = 'damped public RGB-D centering; original trigger and confidence unchanged'
    return result


class RevisionSkills(GuardSkills):
    def __init__(self, *args, gain):
        super().__init__(*args)
        self.gain = gain

    def inspect_alignment(self):
        self.require('above_tray')
        if self.alignment_checks or self.corrections:
            raise ActionFailure('Alignment checkpoint is allowed only once per placement')
        self.alignment_checks += 1
        observation = self.port.observe()
        try:
            original = proposal(observation, self.controller.offset, self.controller.tray)
            result = scale_proposal(original, self.gain)
        except PerceptionError as error:
            result = dict(status='KEEP_NOMINAL', confidence_passed=False,
                          reason=str(error), object_truth_used=False, correction_gain=self.gain)
        result['observation_id'] = observation['observation_id']
        result['simulation_seconds'] = observation['simulation_seconds']
        if result['status'] == 'CORRECT':
            palm = self.controller.place_palm.copy()
            palm[:2] += np.asarray(result['correction_xy_m'])
            trials = []
            selected = None
            for height in (.12, .09, .06):
                goals = [('visual_centering', palm + [0., 0., height]),
                         ('lower', palm + [0., 0., .004])]
                path = CupObstaclePlanner([]).checked_path(self.port.state(), goals, self.controller.yaw)
                trials.append(dict(clearance_height_m=height, path=path))
                if path['reachable']:
                    selected = height
                    break
            result['preflight_trials'] = trials
            if selected is None:
                result.update(status='KEEP_NOMINAL', reason='damped centering path rejected')
            else:
                result.update(proposed_place_palm_m=palm.tolist(), clearance_height_m=selected)
        self.alignment = result
        write_new(self.folder / 'alignment_check.json', result)
        return result
