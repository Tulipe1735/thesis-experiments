import unittest

import numpy as np

from harness import t03_obstacle_approach as O


class TestObstacleApproach(unittest.TestCase):
    def test_capped_cylinder_distance_detects_side_top_and_inside(self):
        obstacle={'center_xy_m':[0.,0.],'radius_m':.03,'bottom_m':0.,'top_m':.10}
        points=np.array([[.03,0.,.05],[.04,0.,.05],[0.,0.,.12],[0.,0.,.05]])
        np.testing.assert_allclose(O.cylinder_distance(points,obstacle),[0.,.01,.02,-.03],atol=1e-12)

    def test_worker_cannot_choose_unsafe_or_unknown_route(self):
        candidates={'blocked':{'public':{'reachable':True,'obstacle_clearance_m':-.01,'table_clearance_m':.01}}}
        def reply(name):
            return {'action':{'op':'done'},'state':{'route_id':name}}
        with self.assertRaisesRegex(ValueError,'clearance'):
            O.validate_reply(reply('blocked'),candidates)
        with self.assertRaisesRegex(ValueError,'unknown'):
            O.validate_reply(reply('unregistered'),candidates)
        with self.assertRaisesRegex(O.ActionFailure,'NO_OBSERVED_CLEAR_APPROACH'):
            O.validate_reply(reply(None),candidates)
