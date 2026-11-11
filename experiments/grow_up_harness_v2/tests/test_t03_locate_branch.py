import unittest
from types import SimpleNamespace

import numpy as np

from harness import t03_locate_branch as L
from harness import t03_locate_temporal as T


class TestLocateConsensus(unittest.TestCase):
    def test_sparse_outliers_can_be_removed_without_moving_sphere(self):
        rng = np.random.default_rng(2)
        center = np.array([.35, .4, .204])
        directions = rng.normal(size=(127,3))
        directions /= np.linalg.norm(directions,axis=1)[:,None]
        points = center+.034*directions
        points = np.vstack([points, center+[[0,.10,0],[.08,0,0],[.06,0,.04]]])
        bounds = (np.r_[center-.1,.025],np.r_[center+.1,.065])
        fit = L.fit_sphere(points,np.r_[center,.034],bounds)
        self.assertGreater(L.observation(fit)['primary_rms_m'],.003)
        bottom,recovered,radius,rms,n = L.refit(points,[0,0,.17],bounds,fit,.002)
        self.assertEqual(n,127)
        np.testing.assert_allclose(recovered,center,atol=1e-6)
        self.assertAlmostEqual(radius,.034,places=6)
        self.assertAlmostEqual(bottom[2],.17)
        self.assertLess(rms,1e-6)

    def test_declines_weak_consensus_and_rejects_unbounded_schema(self):
        fit = type('Fit',(),{'fun':np.r_[np.zeros(60),np.ones(20)*.03]})()
        with self.assertRaisesRegex(L.PerceptionError,'strong consensus'):
            L.refit(None,None,None,fit,.002)
        with self.assertRaisesRegex(ValueError,'inlier_band_m'):
            L.validate_reply({'action':{'op':'done'},'state':{'inlier_band_m':.03}})
        with self.assertRaisesRegex(ValueError,'exact'):
            L.validate_reply({'action':{'op':'wait'},'state':{'inlier_band_m':.002}})

    def test_prior_only_seeds_with_fresh_geometric_consensus(self):
        angles = np.linspace(0, 2*np.pi, 60, endpoint=False)
        points = np.c_[.034*np.cos(angles), .034*np.sin(angles), np.zeros(60)]
        points = np.vstack([points, [.1,.1,.1]])
        current = SimpleNamespace(x=np.array([0.,0.,0.,.060]), fun=np.ones(61)*.026)
        prior = np.array([0.,0.,0.,.034])
        seeded,count = T.prior_consensus(points,current,prior)
        self.assertEqual(count,60)
        np.testing.assert_array_equal(seeded.x,prior)
        rejected,_ = T.prior_consensus(points+[0,0,.1],current,prior)
        self.assertIs(rejected,current)
