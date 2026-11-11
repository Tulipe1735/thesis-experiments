"""Versioned locate adapter: independently re-observe a previous RGB-D sphere."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from . import t03_locate_branch as L
from experiments.t0_agent_v1.common import write_new

VERSION = 't03-temporal-rgbd-consensus-v2'
LOW_CONFIDENCE = L.LOW_CONFIDENCE


def prior_consensus(points, primary, prior):
    """Test a prior only against fresh points, never accept by tracking alone."""
    residuals = np.linalg.norm(points-prior[:3], axis=1)-prior[3]
    count = int(np.count_nonzero(abs(residuals) <= L.BAND[0]))
    primary_count = int(np.count_nonzero(abs(primary.fun) <= L.BAND[1]))
    if (50 <= count < len(points) and 10*count >= 9*len(points)
            and 10*primary_count < 9*len(points)):
        return SimpleNamespace(x=prior.copy(), fun=residuals), count
    return primary, primary_count


def execute(case,out,grasp_source,open_source,placement_source,finish_source,caps,locate_source):
    out = Path(out)
    prior = None
    audit = []

    def primary(sensor,task):
        nonlocal prior
        estimate = L.locate_target(sensor,task)
        prior = np.r_[estimate['visible_center_pelvis_m'],estimate['radius_estimate_m']]
        return estimate

    def candidates(sensor):
        points, plane, bounds, fit = L.consensus_input(sensor)
        if prior is not None:
            seeded, count = prior_consensus(points,fit,prior)
            audit.append({'time_s':sensor['timestamp_s'],'seed':'previous_RGBD_fit' if seeded is not fit else 'fresh_fit',
                          'current_inliers':count,'current_points':len(points),
                          'fresh_fit_rms_m':float(np.sqrt(np.mean(fit.fun**2)))})
            fit = seeded
        return points, plane, bounds, fit

    def refit(points,plane,bounds,fit,band):
        nonlocal prior
        result = L.refit(points,plane,bounds,fit,band)
        prior = np.r_[result[1],result[2]]
        return result

    run = L.rebound(L.execute,locate_target=primary,consensus_input=candidates,refit=refit)
    result = run(case,out,grasp_source,open_source,placement_source,finish_source,caps,locate_source)
    write_new(out/'temporal_seed.json',{'runtime_version':VERSION,'attempts':audit,
              'uses_current_RGBD_confirmation':True,'uses_simulator_truth':False})
    return result
