"""One bounded, publicly triggered retreat for postcondition observability."""
import numpy as np
from experiments.t0_agent_v1.common import write_new
from experiments.t0_agent_v1.tray_collision import CupObstaclePlanner
from .execution import Execution as BaseExecution
from .public_check import observe_evidence

VIEW_DELTA_M = np.array([0., .04, .04])
VIEW_DURATION_S = 2.


class Execution(BaseExecution):
    def call(self, tool):
        result = super().call(tool)
        if tool != 'release_in_tray' or not self.policy.get('active_verification', False):
            return result
        observation = self.port.observe()
        try:
            before = observe_evidence(observation)
        except Exception as error:
            before = dict(observation_id=observation['observation_id'], error=str(error))
        record = dict(before=before, attempted=False, additional_motion_limit=1,
                      delta_from_current_palm_m=VIEW_DELTA_M.tolist(), duration_s=VIEW_DURATION_S,
                      source='public_head_RGBD_and_measured_FK_only', object_truth_used=False)
        if before.get('instantaneous_pass', False):
            record['reason'] = 'current public evidence already sufficient'
        else:
            state = self.port.state()
            goal = np.asarray(state['palms']['left']['position_m']) + VIEW_DELTA_M
            plan = CupObstaclePlanner([]).checked_path(state, [('verification_retreat', goal)], self.skills.controller.yaw)
            record.update(plan=plan, target_palm_m=goal.tolist())
            if plan['reachable']:
                self.event('verification_retreat', 'started')
                record['attempted'] = True
                self.skills.controller.linear('verification_retreat', goal, VIEW_DURATION_S)
                self.skills.controller.save()
                self.event('verification_retreat', 'completed')
            else:
                record['reason'] = 'bounded observation path rejected; no alternate path search'
        write_new(self.output / 'active_verification.json', record)
        return result
