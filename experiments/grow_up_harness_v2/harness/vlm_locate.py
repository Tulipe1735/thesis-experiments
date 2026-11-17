"""K3 VLM locate primitive (GROW_UP_ROOT_DOWN_REVISE_20261113 §5.4 K3), 2D part.

Head RGB plus a query built from the public task -> image point and box, label and
confidence, or an abstention. The model runs in a local ollama server at temperature 0;
replies are cached by (model digest, prompt, query, image hash) so snapshot replays get
the same decision. locate lifts the 2D answer to the target's support-plane bottom with the
depth, support-plane and shape fits of the colour rule; geometry only vetoes, it never picks
another object. In K_v2 the model's confidence is not used (constant 0.0 under this prompt).
"""
import base64
import io
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from experiments.t0_agent_v1.common import write_new

VERSION = 'k3-vlm-locate-2d-20261115'
LIFT = 'k3-lift-20261116b'
# Neighbouring pixels further apart than this in 3D lie on different surfaces (an occlusion edge).
EDGE_M = .02
PROMPT = '''This image comes from a robot's head camera looking at a table.
Find {query}. Answer with JSON only, in this form:
{{"found": true, "point": [x, y], "box": [x1, y1, x2, y2], "label": "short name", "confidence": 0.0}}
Coordinates are integers from 0 to 1000, relative to the image width (x) and height (y).
"point" is the center of the object. "confidence" is between 0 and 1.
If the object is not visible or you are unsure which object is meant, answer {{"found": false}}.'''
# Public colour words for the task's appearance_rgba; the nearest one by RGB distance names the object.
COLOURS = {'red': (.8, .1, .1), 'orange': (1., .55, .05), 'yellow': (.95, .85, .1), 'green': (.15, .6, .2),
           'blue': (.15, .4, .8), 'purple': (.5, .2, .6), 'pink': (.95, .5, .65), 'brown': (.45, .28, .13),
           'white': (.92, .92, .9), 'grey': (.5, .5, .5), 'black': (.08, .08, .08)}
NOUNS = {'cup': 'cup', 'fruit': 'fruit', 'bottle': 'bottle'}


def colour_name(rgba):
    return min(COLOURS, key=lambda name: sum((a - b) ** 2 for a, b in zip(rgba[:3], COLOURS[name])))


def query_text(role):
    """The target role of the public task -> 'the blue cup'."""
    return f"the {colour_name(role['appearance_rgba'])} {NOUNS[role['category']]}"


class ReplayCacheMiss(RuntimeError):
    """A replay found no cached reply; the comparison is untestable, the model is never called again."""


class ModelUnavailable(RuntimeError):
    """The local model server failed or did not answer: a system failure, not a locate outcome."""


def _call(endpoint, path, payload=None, timeout=30.):
    request = urllib.request.Request(endpoint.rstrip('/') + path, method='POST' if payload is not None else 'GET',
                                     data=None if payload is None else json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        # urllib drops the body, which is where ollama states why it failed.
        raise ModelUnavailable(f'ollama {path} HTTP {error.code}: {error.read().decode(errors="replace")[:2000]}') from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ModelUnavailable(f'ollama {path}: {error}') from error


def identity(endpoint, model):
    """Model tag, weight digest and server version, recorded once per run."""
    tags = _call(endpoint, '/api/tags')['models']
    entry = next(m for m in tags if m['name'] == model)
    show = _call(endpoint, '/api/show', {'model': model})
    return {'model': model, 'digest': entry['digest'], 'size': entry.get('size'), 'details': entry.get('details'),
            'parameters': show.get('parameters'), 'ollama': _call(endpoint, '/api/version')['version'],
            'primitive': VERSION, 'prompt_sha256': hashlib.sha256(PROMPT.encode()).hexdigest()}


def ask(png, query, setup, cache=None, sources=(), replay=False):
    """One model call, or the cached reply for the same digest, prompt, query and image.

    setup: endpoint, model, digest, options (temperature 0, seed), think, timeout_s.
    cache is written; sources are earlier caches read only (a resumed episode's source).
    replay: a miss raises ReplayCacheMiss instead of calling the model.
    """
    key = hashlib.sha256(json.dumps([setup['digest'], PROMPT, query, hashlib.sha256(png).hexdigest()]).encode()).hexdigest()
    for folder in ([cache] if cache is not None else []) + list(sources):
        if (Path(folder) / f'{key}.json').exists():
            return dict(json.loads((Path(folder) / f'{key}.json').read_text()), cached=True)
    if replay:
        raise ReplayCacheMiss(f'REPLAY_CACHE_MISS: {query!r} on image {hashlib.sha256(png).hexdigest()[:12]}')
    payload = {'model': setup['model'], 'stream': False, 'format': 'json', 'think': setup['think'],
               'options': setup['options'], 'keep_alive': '30m',
               'messages': [{'role': 'user', 'content': PROMPT.format(query=query),
                             'images': [base64.b64encode(png).decode()]}]}
    start = time.monotonic()
    reply = _call(setup['endpoint'], '/api/chat', payload, timeout=setup['timeout_s'])
    record = {'key': key, 'query': query, 'text': reply['message']['content'], 'latency_s': time.monotonic() - start,
              'eval_count': reply.get('eval_count'), 'model': reply.get('model')}
    if cache is not None:
        Path(cache).mkdir(parents=True, exist_ok=True)
        write_new(Path(cache) / f'{key}.json', record)
    return dict(record, cached=False)


def parse(text, width, height):
    """Model text -> answer in pixels. Malformed replies are 'invalid', never guessed."""
    try:
        value = json.loads(text)
    except ValueError:
        return {'outcome': 'invalid', 'reason': 'not JSON'}
    if type(value) is not dict or type(value.get('found')) is not bool:
        return {'outcome': 'invalid', 'reason': 'found must be true or false'}
    if not value['found']:
        return {'outcome': 'abstain'}

    def coords(name, count):
        v = value.get(name)
        if type(v) is not list or len(v) != count or any(type(c) not in (int, float) or not 0 <= c <= 1000 for c in v):
            return None
        return [c / 1000 * (width if i % 2 == 0 else height) for i, c in enumerate(v)]
    point, box = coords('point', 2), coords('box', 4)
    confidence = value.get('confidence')
    if point is None and box is not None:
        point = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
    if point is None or type(confidence) not in (int, float) or not 0 <= confidence <= 1:
        return {'outcome': 'invalid', 'reason': 'needs point or box in 0..1000 and confidence in 0..1'}
    return {'outcome': 'answer', 'point_px': point, 'box_px': box, 'label': value.get('label'),
            'confidence': float(confidence)}


def lift(sensor, answer, category):
    """2D answer -> target estimate in the colour rule's schema (pelvis frame), or a declared PerceptionError.

    The object is the above-table depth component under the answered point, or else the one
    covering most of the answered box; components are cut at depth jumps, so objects that touch
    in the image stay apart (k3-lift-20261116 joined an orange to the bottle behind it). Depth projection, support plane and the sphere (fruit) or
    cylinder-wall fit repeat reuse_grasp.locate_target, which ties them to its colour selection
    and is frozen. Vetoes: workspace, support tilt, component size and the shape fits.
    """
    import numpy as np
    from scipy import ndimage
    from scipy.optimize import least_squares
    from experiments.t0_agent_v1.reuse_grasp import PerceptionError, point_cloud
    if answer['outcome'] == 'abstain':
        raise PerceptionError('VLM_ABSTAIN: the model did not find the queried object')
    if answer['outcome'] != 'answer':
        raise PerceptionError('VLM_INVALID: ' + answer.get('reason', ''))
    cloud = point_cloud(sensor['depth_m'], sensor['K'], sensor['T_optical_to_pelvis'])
    workspace = (np.isfinite(cloud).all(axis=-1) & (cloud[..., 0] > .1) & (cloud[..., 0] < 1.5)
                 & (abs(cloud[..., 1]) < .85) & (cloud[..., 2] > -.05) & (cloud[..., 2] < .5))
    heights = cloud[..., 2][workspace]
    if len(heights) < 100:
        raise PerceptionError('Insufficient visible depth')
    hist, edges = np.histogram(heights, bins=np.arange(-.05, .4, .002))
    support = edges[int(hist.argmax())] + .001
    points = cloud[workspace & (abs(cloud[..., 2] - support) < .004)]
    plane = np.linalg.lstsq(np.c_[points[:, :2], np.ones(len(points))], points[:, 2], rcond=None)[0]
    if np.linalg.norm(plane[:2]) > .12:
        raise PerceptionError('VETO_SUPPORT: visible support plane too tilted')
    height = cloud[..., 2] - (cloud[..., :2] @ plane[:2] + plane[2])
    edge = np.zeros(height.shape, bool)
    for axis in (0, 1):
        jump = np.linalg.norm(np.diff(cloud, axis=axis), axis=-1) > EDGE_M
        edge[tuple(slice(None, -1) if a == axis else slice(None) for a in (0, 1))] |= jump
        edge[tuple(slice(1, None) if a == axis else slice(None) for a in (0, 1))] |= jump
    labels, _ = ndimage.label(workspace & (height > .012) & (height < .25) & ~edge)
    x, y = answer['point_px']
    i, j = int(y), int(x)
    label = int(labels[i, j]) if 0 <= i < labels.shape[0] and 0 <= j < labels.shape[1] else 0
    if not label and answer.get('box_px'):
        x1, y1, x2, y2 = (int(v) for v in answer['box_px'])
        inside = labels[max(y1, 0):max(y2, 0) + 1, max(x1, 0):max(x2, 0) + 1]
        counts = np.bincount(inside.ravel(), minlength=2)[1:]
        label = int(np.argmax(counts)) + 1 if counts.size and counts.max() else 0
    if not label:
        raise PerceptionError('VLM_POINT_OFF_OBJECT: no above-table depth under the answered point or box')
    selected = labels == label
    if selected.sum() < 25:
        raise PerceptionError(f'VETO_SIZE: {int(selected.sum())} pixels')
    points = cloud[selected]
    lo, hi = np.percentile(points, [3, 97], axis=0)
    if not (.012 < hi[2] - lo[2] < .26 and max(hi[:2] - lo[:2]) < .2):
        raise PerceptionError(f'VETO_SIZE: extent {np.round(hi - lo, 3).tolist()} m outside the tabletop object range')
    center = (lo + hi) / 2
    radius, rms = .04, None
    if category == 'fruit':
        seed = np.linalg.lstsq(np.c_[2 * points, np.ones(len(points))], np.sum(points ** 2, axis=1), rcond=None)[0]
        radius = float(np.sqrt(max(.0004, seed[3] + seed[:3] @ seed[:3])))
        fit = least_squares(lambda values: np.linalg.norm(points - values[:3], axis=1) - values[3],
                            np.r_[seed[:3], np.clip(radius, .025, .065)],
                            bounds=(np.r_[lo - .1, .025], np.r_[hi + .1, .065]), loss='soft_l1', f_scale=.001)
        center, radius = fit.x[:3], float(fit.x[3])
        rms = float(np.sqrt(np.mean((np.linalg.norm(points - center, axis=1) - radius) ** 2)))
        if rms > .003:
            raise PerceptionError('Visible sphere fit confidence insufficient')
    else:
        wall = points[(points[:, 2] > plane[2] + .016) & (points[:, 2] < plane[2] + .075), :2]
        if len(wall) < 25:
            raise PerceptionError('Insufficient visible cylindrical wall points')
        fits = []
        for forward in (0., .03, .06):
            start = np.r_[np.median(wall, axis=0) + [forward, 0.], .04]
            fit = least_squares(lambda values: np.linalg.norm(wall - values[:2], axis=1) - values[2],
                                start, bounds=(np.r_[lo[:2] - .1, .02], np.r_[hi[:2] + .1, .075]),
                                loss='soft_l1', f_scale=.001)
            error = abs(np.linalg.norm(wall - fit.x[:2], axis=1) - fit.x[2])
            fits.append((float(np.median(error)), fit.x, float(np.mean(error < .003))))
        residual, values, inliers = min(fits, key=lambda row: row[0])
        if residual > .004 or inliers < .5:
            raise PerceptionError('Cylindrical wall fit confidence insufficient')
        center[:2], radius = values[:2], float(values[2])
        if radius < .0205 or radius > .0745:
            raise PerceptionError('Cylindrical radius at class bound; occluded arc cannot locate center reliably')
    bottom = np.r_[center[:2], plane @ np.r_[center[:2], 1.]]
    return dict(cup_bottom_position_m=bottom.tolist(), visible_center_pelvis_m=center.tolist(),
                radius_estimate_m=radius, fit_rms_m=rms, table_plane=plane.tolist(),
                observation_id=f"head_{sensor['timestamp_s']:.3f}", observation_simulation_seconds=sensor['timestamp_s'],
                source='head_RGBD_vlm_lift', lift=LIFT, target_category=category, ground_truth_used=False,
                component_pixels=int(selected.sum()))


def ask_frame(sensor, query, setup, cache=None, sources=(), replay=False):
    """The model's parsed answer on the head RGB frame, with the reply it came from."""
    import numpy as np
    from PIL import Image
    rgb = np.asarray(sensor['rgb'], np.uint8)
    stream = io.BytesIO()
    Image.fromarray(rgb).save(stream, format='PNG')
    reply = ask(stream.getvalue(), query, setup, cache, sources, replay)
    return {'query': query, 'reply': reply, 'answer': parse(reply['text'], rgb.shape[1], rgb.shape[0]),
            'primitive': VERSION, 'observation_simulation_seconds': sensor['timestamp_s']}


def locate(sensor, query, category, setup, cache=None, sources=(), replay=False):
    """K3 primitive: head RGB-D and a public query -> target estimate carrying the model record it rests on."""
    record = ask_frame(sensor, query, setup, cache, sources, replay)
    return dict(lift(sensor, record['answer'], category), vlm=record)
