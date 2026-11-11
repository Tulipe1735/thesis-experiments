"""Separate touching image silhouettes using measured RGB-D depth continuity."""
import numpy as np
from PIL import Image
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .common import sha
from .runtime import CountedPort  # frozen imports use the project controller path
from rgbd_cup import estimate, point_cloud, PerceptionError


def separated_cups(observation):
    rgb = np.asarray(Image.open(observation['head_rgb_path']).convert('RGB'))
    depth = np.load(observation['depth_path'], allow_pickle=False)
    cloud = point_cloud(depth, observation['K'], observation['T_optical_to_pelvis'])
    mask = ((rgb.min(axis=-1) > 95) & (np.ptp(rgb.astype(float), axis=-1) < 35)
            & np.isfinite(cloud).all(axis=-1) & (cloud[:, :, 0] > .1) & (cloud[:, :, 0] < .75)
            & (cloud[:, :, 1] > -.12) & (cloud[:, :, 1] < .7)
            & (cloud[:, :, 2] > .18) & (cloud[:, :, 2] < .31))
    index = np.full(mask.shape, -1, dtype=int)
    index[mask] = np.arange(mask.sum())
    if mask.sum() == 0:
        return []
    left, right = [], []
    for a, b in [((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
                 ((slice(None), slice(None, -1)), (slice(None), slice(1, None)))]:
        keep = mask[a] & mask[b] & (np.linalg.norm(cloud[a]-cloud[b], axis=-1) < .012)
        left.extend(index[a][keep])
        right.extend(index[b][keep])
    graph = coo_matrix((np.ones(len(left)), (left, right)), shape=(int(mask.sum()),)*2).tocsr()
    count, labels = connected_components(graph, directed=False)
    image_labels = np.full(mask.shape, -1, dtype=int)
    image_labels[mask] = labels
    sizes = np.bincount(labels)
    found = []
    for label in range(count):
        if sizes[label] < 150:
            continue
        # Only candidate colors are isolated; original depth/calibration and
        # table-plane evidence remain intact. No new sensor images are stored.
        isolated = rgb.copy()
        isolated[mask & (image_labels != label)] = 0
        try:
            item = estimate(isolated, depth, observation['K'], observation['T_optical_to_pelvis'],
                            observation['observation_id'])
        except PerceptionError:
            continue
        item.update(observation_simulation_seconds=observation['simulation_seconds'],
                    segmentation='RGBD adjacent-point distance <12mm; frozen circle-fit confidence unchanged',
                    input_sha256=dict(head_rgb=sha(observation['head_rgb_path']), depth=sha(observation['depth_path'])))
        if not any(np.linalg.norm(np.asarray(item['cup_bottom_position_m'])-
                                  old['cup_bottom_position_m']) < .03 for old in found):
            found.append(item)
    return found
