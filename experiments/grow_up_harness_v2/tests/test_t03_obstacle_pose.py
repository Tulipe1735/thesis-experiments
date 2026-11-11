import unittest
from types import SimpleNamespace

import numpy as np

from harness import t03_obstacle_pose as P
from experiments.t0_agent_v1.adaptive_reuse_grasp import DEFAULTS,grasp_rotation


class TestPoseCandidates(unittest.TestCase):
    def test_candidates_stay_in_native_bounds_and_follow_observed_obstacle(self):
        params={**DEFAULTS,'offset_delta_m':[0.,0.,-.014]}
        yaw=1.
        original=np.array([.045,-.055,-.047])
        controller=SimpleNamespace(plan={'selected_yaw_rad':yaw,'path':{'goals':[]}},
            offset=original,grasp_anchor=np.array([.34,.41,.17]),adaptive=params)
        start=controller.grasp_anchor-grasp_rotation(yaw,params)@original
        obstacle={'center_xy_m':(start[:2]-[0.,.06]).tolist()}
        candidates=list(P.offset_candidates(controller,[obstacle]))
        self.assertGreater(len(candidates),2)
        for name,configuration,offset,goals in candidates[2:]:
            self.assertGreaterEqual(configuration['offset_delta_m'][0],-.05)
            self.assertLessEqual(configuration['offset_delta_m'][0],.05)
            self.assertGreaterEqual(configuration['offset_delta_m'][1],-.09)
            self.assertLessEqual(configuration['offset_delta_m'][1],.05)
            end=controller.grasp_anchor-grasp_rotation(yaw,params)@offset
            self.assertGreaterEqual(end[1]-start[1],.019999)
            self.assertLessEqual(np.linalg.norm(end-start),.068)
        np.testing.assert_array_equal(controller.offset,original)
        self.assertEqual(params['offset_delta_m'],[0.,0.,-.014])
