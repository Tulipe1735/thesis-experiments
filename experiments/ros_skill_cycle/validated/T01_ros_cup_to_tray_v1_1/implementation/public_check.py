"""Conservative task evidence from public RGB-D and measured robot state only."""
import numpy as np
from PIL import Image
from scipy import ndimage
from experiments.cordis_t01.handoff_guard import circle, robot_self_mask
from experiments.t0_agent_v1.tray_tools import locate_tray
from rgbd_cup import point_cloud, PerceptionError

RADIUS = .041
MARGIN_M = .003
STABILITY_M = .003
VERSION = 'public-two-band-tray-check-v1'


def locate_post_tray(observation):
    """Three current colored corners determine the fourth by the calibrated rectangle."""
    rgb = np.asarray(Image.open(observation['head_rgb_path']).convert('RGB'), dtype=float)
    cloud = point_cloud(np.load(observation['depth_path'], allow_pickle=False), observation['K'],
                        observation['T_optical_to_pelvis'])
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    masks = dict(red=(r > 1.5*g) & (r > 1.5*b) & (r > 60),
                 green=(g > 1.5*r) & (g > 1.5*b) & (g > 60),
                 yellow=(r > 1.6*b) & (g > 1.6*b) & (r > .7*g) & (g > .7*r) & (r > 60),
                 magenta=(r > 1.5*g) & (b > 1.5*g) & (r > .6*b) & (b > .6*r) & (b > 60))
    valid = (np.isfinite(cloud).all(axis=-1) & (cloud[..., 0] > .1) & (cloud[..., 0] < .7)
             & (cloud[..., 1] > -.12) & (cloud[..., 1] < .7) & (cloud[..., 2] > .1) & (cloud[..., 2] < .24))
    found = {}
    for name, mask in masks.items():
        labels, count = ndimage.label(mask & valid)
        sizes = np.bincount(labels.ravel())
        if count and sizes[1:].max() >= 10:
            found[name] = np.median(cloud[labels == 1 + int(sizes[1:].argmax())], axis=0)
    if len(found) < 3:
        raise PerceptionError('Fewer than three current visible tray markers')
    inferred = []
    if len(found) == 3:
        name = next(k for k in masks if k not in found)
        equations = dict(red=('green', 'magenta', 'yellow'), green=('red', 'yellow', 'magenta'),
                         yellow=('green', 'magenta', 'red'), magenta=('red', 'yellow', 'green'))
        a, b, c = equations[name]
        found[name] = found[a] + found[b] - found[c]
        inferred.append(name)
    a, b, c, d = [found[k] for k in ('red', 'green', 'yellow', 'magenta')]
    long, short = (b-a+c-d)/2, (d-a+c-b)/2
    if not (.375 < np.linalg.norm(long) < .410 and .055 < np.linalg.norm(short) < .090):
        raise PerceptionError('Postcondition marker geometry outside calibrated prior')
    long /= np.linalg.norm(long)
    short -= long * (short @ long)
    short /= np.linalg.norm(short)
    normal = np.cross(long, short)
    if normal[2] < .98:
        raise PerceptionError('Postcondition tray normal rejected')
    return dict(center_floor_pelvis_m=(np.mean([a,b,c,d], axis=0)-normal*.0004).tolist(),
                axis_long=long.tolist(), axis_short=short.tolist(), normal=normal.tolist(),
                inner_half_xy_m=[.214, .054], inferred_marker=inferred,
                ground_truth_used=False)


def observe_evidence(observation):
    tray = locate_post_tray(observation)
    rgb = np.asarray(Image.open(observation['head_rgb_path']).convert('RGB'), dtype=float)
    depth = np.load(observation['depth_path'], allow_pickle=False)
    cloud = point_cloud(depth, observation['K'], observation['T_optical_to_pelvis'])
    center = np.asarray(tray['center_floor_pelvis_m'])
    long, short = np.asarray(tray['axis_long']), np.asarray(tray['axis_short'])
    local = cloud - center
    x, y, z = local @ long, local @ short, local @ np.asarray(tray['normal'])
    mask = (np.isfinite(cloud).all(axis=-1) & (rgb.min(axis=-1) > 95)
            & (np.ptp(rgb, axis=-1) < 35) & (np.abs(x) < .24) & (np.abs(y) < .12)
            & ~robot_self_mask(observation, depth))
    fits = []
    for low, high in [(.025, .05), (.06, .085)]:
        points = cloud[mask & (z > low) & (z < high), :2]
        fits.append(circle(points, center[:2]))
    positions = np.asarray([f['center_xy_m'] for f in fits])
    disagreement = float(np.linalg.norm(positions[0] - positions[1]))
    xy = positions.mean(axis=0)
    delta = np.r_[xy - center[:2], 0.]
    local_xy = np.array([delta @ long, delta @ short])
    margin = float(np.min(np.asarray(tray['inner_half_xy_m']) - np.abs(local_xy) - RADIUS))
    palm = np.asarray(observation['body_state']['palms']['left']['position_m'])
    separation = float(np.linalg.norm(palm - np.r_[xy, center[2] + .06]))
    return dict(version=VERSION, observation_id=observation['observation_id'],
                simulation_seconds=observation['simulation_seconds'],
                center_in_tray_xy_m=local_xy.tolist(), conservative_base_margin_m=margin,
                two_height_band_disagreement_m=disagreement, palm_distance_m=separation,
                fits=fits, instantaneous_pass=bool(margin >= MARGIN_M and disagreement <= .005 and separation >= .12),
                source='public_head_RGBD_K_T_and_measured_robot_joints', object_truth_used=False,
                scope='visual proxy for upright compatible cup; physical support/contact verified independently')


def verdict(samples):
    if len(samples) < 3 or any('error' in s for s in samples):
        return dict(status='UNVERIFIED', reason='insufficient confident public postcondition evidence', samples=samples)
    span = samples[-1]['simulation_seconds'] - samples[0]['simulation_seconds']
    positions = np.asarray([s['center_in_tray_xy_m'] for s in samples])
    drift = float(np.max(np.linalg.norm(positions - positions[0], axis=1)))
    passed = span >= .999 and drift <= STABILITY_M and all(s['instantaneous_pass'] for s in samples)
    return dict(status='PASS' if passed else 'FAIL', reason='public stability, containment, upright and hand-separation proxy',
                span_s=span, maximum_visual_drift_m=drift, samples=samples,
                independent_physical_verification=False)
