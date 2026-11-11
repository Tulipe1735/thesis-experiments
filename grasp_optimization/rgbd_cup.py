"""Estimate an upright white cup using only head RGB-D and camera calibration."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.optimize import least_squares


class PerceptionError(ValueError):
    pass


def point_cloud(depth, intrinsics, transform):
    depth = np.asarray(depth, float)
    k, t = np.asarray(intrinsics, float), np.asarray(transform, float)
    if depth.ndim != 2 or k.shape != (3, 3) or t.shape != (4, 4):
        raise PerceptionError('Invalid RGB-D calibration shapes')
    if not np.isfinite(k).all() or not np.isfinite(t).all() or min(k[0, 0], k[1, 1]) <= 0:
        raise PerceptionError('Invalid RGB-D calibration values')
    v, u = np.indices(depth.shape)
    optical = np.stack(((u-k[0, 2])*depth/k[0, 0],
                        (v-k[1, 2])*depth/k[1, 1], depth), axis=-1)
    return optical @ t[:3, :3].T + t[:3, 3]


def estimate(rgb, depth, intrinsics, transform, observation_id, pixel_hint=None, radius=.041):
    """Known radius is an object-class prior, never a queried scene dimension."""
    rgb = np.asarray(rgb, float)
    cloud = point_cloud(depth, intrinsics, transform)
    if rgb.shape != (*cloud.shape[:2], 3):
        raise PerceptionError('RGB and depth must be aligned')
    finite = np.isfinite(cloud).all(axis=-1)
    workspace = (finite & (cloud[:, :, 0] > .1) & (cloud[:, :, 0] < .75)
                 & (cloud[:, :, 1] > -.12) & (cloud[:, :, 1] < .7))
    if workspace.sum() < 500:
        raise PerceptionError('Insufficient visible workspace depth')
    heights = cloud[:, :, 2][workspace]
    hist, edges = np.histogram(heights, bins=np.arange(-.1, .51, .002))
    if hist.max() < 400:
        raise PerceptionError('No dominant horizontal support plane')
    mode = edges[int(hist.argmax())]+.001
    plane_mask = workspace & (np.abs(cloud[:, :, 2]-mode) < .004)
    points = cloud[plane_mask][::4]
    plane = np.linalg.lstsq(np.c_[points[:, :2], np.ones(len(points))], points[:, 2], rcond=None)[0]
    residual = points[:, 2]-np.c_[points[:, :2], np.ones(len(points))]@plane
    plane_rms = float(np.sqrt(np.mean(residual**2)))
    if plane_rms > .0025 or np.linalg.norm(plane[:2]) > .12:
        raise PerceptionError('Uncertain or nonhorizontal support plane')
    height = cloud[:, :, 2] - (cloud[:, :, :2]@plane[:2]+plane[2])
    white = (rgb.min(axis=-1) > 95) & (np.ptp(rgb, axis=-1) < 35)
    mask = workspace & white & (height > .012) & (height < .115)
    labels, count = ndimage.label(mask)
    sizes = np.bincount(labels.ravel())
    candidates = []
    for label in range(1, count+1):
        if sizes[label] < 150:
            continue
        v, u = np.where(labels == label)
        bbox = [int(u.min()), int(v.min()), int(u.max()+1), int(v.max()+1)]
        if pixel_hint is not None:
            x, y = pixel_hint
            if not (bbox[0]-12 <= x <= bbox[2]+12 and bbox[1]-12 <= y <= bbox[3]+12):
                continue
        candidates.append((label, bbox, int(sizes[label])))
    if len(candidates) != 1:
        raise PerceptionError(f'Expected one white cup candidate, found {len(candidates)}')
    label, bbox, pixel_count = candidates[0]
    wall_mask = (labels == label) & (height > .016) & (height < .075)
    wall = cloud[wall_mask, :2][::3]
    if len(wall) < 100:
        raise PerceptionError('Insufficient cup-wall depth points')
    rng = np.random.default_rng(1000)
    best = None
    for _ in range(300):
        a, b = wall[rng.choice(len(wall), 2, replace=False)]
        delta = b-a
        distance = np.linalg.norm(delta)
        if not .008 < distance < 2*radius:
            continue
        perpendicular = np.array([-delta[1], delta[0]])/distance
        shift = perpendicular*np.sqrt(radius**2-distance**2/4)
        for center in ((a+b)/2+shift, (a+b)/2-shift):
            error = np.abs(np.linalg.norm(wall-center, axis=1)-radius)
            score = int(np.sum(error < .0025))
            if best is None or score > best[0]:
                best = (score, center)
    if best is None:
        raise PerceptionError('No consistent cup circle')
    center = best[1]
    for _ in range(3):
        inliers = np.abs(np.linalg.norm(wall-center, axis=1)-radius) < .003
        if inliers.sum() < 100:
            raise PerceptionError('Too few cylindrical wall inliers')
        fit = least_squares(lambda xy: np.linalg.norm(wall[inliers]-xy, axis=1)-radius,
                            center, loss='soft_l1', f_scale=.001)
        center = fit.x
    error = np.linalg.norm(wall[inliers]-center, axis=1)-radius
    rms = float(np.sqrt(np.mean(error**2)))
    fraction = float(np.mean(inliers))
    angles = np.arctan2(wall[inliers, 1]-center[1], wall[inliers, 0]-center[0])
    resultant = float(np.abs(np.mean(np.exp(1j*angles))))
    if rms > .002 or fraction < .55 or resultant > .98:
        raise PerceptionError('Cup fit failed confidence checks')
    z = float(plane@np.r_[center, 1.])
    return dict(observation_id=observation_id, frame='observation_pelvis',
                cup_bottom_position_m=[float(center[0]), float(center[1]), z],
                table_plane_z_from_xy=plane.tolist(), radius_prior_m=radius,
                bbox_xyxy=bbox, white_pixels=pixel_count, wall_points=len(wall),
                wall_inlier_fraction=fraction, circle_fit_rms_m=rms,
                table_fit_rms_m=plane_rms, yaw_estimated=False,
                source='head_rgb_aligned_depth_K_T_only', ground_truth_used=False,
                limitations=['upright white cup', 'known radius class prior', 'fixed simulated lighting',
                             'visible horizontal support required; no segmentation-ID access'])


def from_observation(observation, pixel_hint=None):
    # Deliberately select fields instead of passing a simulator object to perception.
    rgb_path, depth_path = Path(observation['head_rgb_path']), Path(observation['depth_path'])
    result = estimate(np.asarray(Image.open(rgb_path).convert('RGB')),
                      np.load(depth_path, allow_pickle=False), observation['K'],
                      observation['T_optical_to_pelvis'], observation['observation_id'], pixel_hint)
    result['observation_simulation_seconds'] = observation['simulation_seconds']
    result['input_sha256'] = {key: hashlib.sha256(path.read_bytes()).hexdigest()
                              for key, path in [('head_rgb', rgb_path), ('depth', depth_path)]}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observation', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = from_observation(json.loads(args.observation.read_text()))
    if args.output:
        args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
