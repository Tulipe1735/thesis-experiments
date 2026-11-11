"""One RGB-D-only locate fallback around the frozen T03 program.

The Worker selects a residual band. The trusted runtime owns segmentation,
refitting, validation and all physical actions. The primary locator runs first.
"""
import math
import types
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.optimize import least_squares

from . import t03_curriculum as C, t03_finish as F
from experiments.grow_up_v2.isolation.worker import Worker
from experiments.t0_agent_v1.common import write_new
from experiments.t0_agent_v1.reuse_grasp import PerceptionError, ReuseGrasp, locate_target, point_cloud
from experiments.t0_agent_v1.train_tp01 import body_packet

LOW_CONFIDENCE = 'Visible sphere fit confidence insufficient'
BAND = (.0015, .0025)
MIN_FRACTION = .90
MIN_POINTS = 50
RADIUS = (.025, .065)


def consensus_input(sensor):
    # Match the primary locator's RGB-D workspace, support and colour gates.
    rgb = np.asarray(sensor['rgb'], float) / 255.
    cloud = point_cloud(sensor['depth_m'], sensor['K'], sensor['T_optical_to_pelvis'])
    x, y, z = np.moveaxis(cloud, -1, 0)
    workspace = (np.isfinite(cloud).all(axis=-1) & (x > .1) & (x < 1.5)
                 & (abs(y) < .85) & (z > -.05) & (z < .5))
    hist, edges = np.histogram(z[workspace], bins=np.arange(-.05, .4, .002))
    support = edges[int(hist.argmax())] + .001
    table = cloud[workspace & (abs(z - support) < .004)]
    plane = np.linalg.lstsq(np.c_[table[:, :2], np.ones(len(table))], table[:, 2], rcond=None)[0]
    height = z - (cloud[..., :2] @ plane[:2] + plane[2])
    r, g, b = np.moveaxis(rgb, -1, 0)
    labels, count = ndimage.label(workspace & (r > 1.25*g) & (g > 1.5*b)
                                   & (g > .1) & (r > .25) & (height > .012) & (height < .25))
    candidates = []
    for label in range(1, count + 1):
        mask = labels == label
        if mask.sum() < 25:
            continue
        points = cloud[mask]
        lo, hi = np.percentile(points, [3, 97], axis=0)
        if .012 < hi[2]-lo[2] < .26 and max(hi[:2]-lo[:2]) < .2:
            candidates.append((float(rgb[mask].mean()), points, lo, hi))
    candidates.sort(key=lambda row: row[0], reverse=True)
    if not candidates or len(candidates) > 1 and candidates[0][0]-candidates[1][0] < .07:
        raise PerceptionError('Locate fallback requires the same unambiguous colour component')
    _, points, lo, hi = candidates[0]
    seed = np.linalg.lstsq(np.c_[2*points, np.ones(len(points))],
                           np.sum(points**2, axis=1), rcond=None)[0]
    radius = np.sqrt(max(.0004, seed[3]+seed[:3]@seed[:3]))
    bounds = (np.r_[lo-.1, RADIUS[0]], np.r_[hi+.1, RADIUS[1]])
    fit = fit_sphere(points, np.r_[seed[:3], np.clip(radius, *RADIUS)], bounds)
    return points, plane, bounds, fit


def fit_sphere(points, start, bounds):
    return least_squares(lambda values: np.linalg.norm(points-values[:3], axis=1)-values[3],
                         start, bounds=bounds, loss='soft_l1', f_scale=.001)


def observation(fit):
    return {'absolute_radial_errors_m': abs(fit.fun).tolist(),
            'primary_rms_m': float(np.sqrt(np.mean(fit.fun**2)))}


def validate_reply(reply):
    if (type(reply) is not dict or set(reply) != {'action', 'state'}
            or reply['action'] != {'op': 'done'} or type(reply['state']) is not dict
            or set(reply['state']) != {'inlier_band_m'}):
        raise ValueError('locate leaf requires exact done and state.inlier_band_m')
    band = reply['state']['inlier_band_m']
    if band is not None and (type(band) not in (float, int) or not math.isfinite(band)
                             or not BAND[0] <= band <= BAND[1]):
        raise ValueError('inlier_band_m must be null or a number in [0.0015,0.0025]')
    return band


def refit(points, plane, bounds, fit, band):
    if band is None:
        raise PerceptionError('Locate leaf declined the residual distribution')
    mask = abs(fit.fun) <= band
    n = int(mask.sum())
    if n < MIN_POINTS or n < MIN_FRACTION * len(mask) or n == len(mask):
        raise PerceptionError('Locate leaf requires strong consensus with outliers')
    result = fit_sphere(points[mask], fit.x, bounds)
    center, radius = result.x[:3], float(result.x[3])
    bottom = np.r_[center[:2], plane @ np.r_[center[:2], 1.]]
    rms = float(np.sqrt(np.mean(result.fun**2)))
    singular = np.linalg.svd(result.jac, compute_uv=False)
    if (not result.success or rms > .003 or singular[-1] < .02 * singular[0]
            or abs(center[2]-radius-bottom[2]) > .005
            or np.linalg.norm(center-fit.x[:3]) > .006 or abs(radius-fit.x[3]) > .004
            or not RADIUS[0]+.0005 < radius < RADIUS[1]-.0005):
        raise PerceptionError('Refitted sphere failed geometric checks')
    return bottom, center, radius, rms, n


def rebound(function, **overrides):
    return types.FunctionType(function.__code__, {**function.__globals__, **overrides},
                              function.__name__, function.__defaults__, function.__closure__)


def execute(case, out, grasp_source, open_source, placement_source, finish_source, caps, locate_source):
    out = Path(out)
    attempts = []

    def locate_with_leaf(sensor, task):
        try:
            estimate = locate_target(sensor, task)
        except PerceptionError as exc:
            if str(exc) != LOW_CONFIDENCE or task['target_category'] != 'fruit':
                raise
        else:
            attempts.append({'time_s': sensor['timestamp_s'], 'route': 'primary'})
            return estimate
        row = {'time_s': sensor['timestamp_s'], 'route': 'leaf', 'trigger': LOW_CONFIDENCE}
        attempts.append(row)
        points, plane, bounds, fit = consensus_input(sensor)
        obs = observation(fit)
        with Worker(locate_source, body_packet(), wall_timeout=5., cpu_seconds=120) as worker:
            reply = worker.act(obs, {'phase': 'sphere_residual_consensus'})
            row.update(observation=obs, reply=reply, worker_security=worker.security)
        band = validate_reply(reply)
        bottom, center, radius, rms, n = refit(points, plane, bounds, fit, band)
        row.update(accepted=True, n_inliers=n, fit_rms_m=rms,
                   original_center_m=fit.x[:3].tolist(), refitted_center_m=center.tolist())
        return {'cup_bottom_position_m': bottom.tolist(), 'visible_center_pelvis_m': center.tolist(),
                'radius_estimate_m': radius, 'fit_rms_m': rms, 'table_plane': plane.tolist(),
                'observation_id': f"head_{sensor['timestamp_s']:.3f}",
                'observation_simulation_seconds': sensor['timestamp_s'],
                'source': 'head_RGBD_sphere_consensus_leaf', 'target_category': 'fruit',
                'ground_truth_used': False, 'limitation': 'Robust sphere fit for rigid orange proxy'}

    class LocateReuse(ReuseGrasp):
        def locate(self, pixel_hint=None):
            locator = locate_target if self.port.plant.guard else locate_with_leaf
            return rebound(ReuseGrasp.locate, locate_target=locator)(self, pixel_hint)

    class LocateGrasp(C.AdaptiveGrasp, LocateReuse):
        pass

    # The MRO inserts only the frozen ReuseGrasp.locate with a new local
    # locator. AdaptiveGrasp still owns offsets, preflight and physical stages.
    curriculum = types.SimpleNamespace(
        AdaptiveGrasp=LocateGrasp, execute=C.execute)
    run = rebound(F.execute, C=curriculum)
    result = run(case, out, grasp_source, open_source, placement_source, finish_source, caps)
    write_new(out/'locate_branch.json', {'attempts': attempts,
              'worker_calls': sum('reply' in row for row in attempts),
              'hidden_resets': 0, 'physical_actions_by_leaf': 0})
    return result
