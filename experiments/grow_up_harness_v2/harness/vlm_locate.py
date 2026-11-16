"""K3 VLM locate primitive (GROW_UP_ROOT_DOWN_REVISE_20261113 §5.4 K3), 2D part.

Head RGB plus a query built from the public task -> image point and box, label and
confidence, or an abstention. The model runs in a local ollama server at temperature 0;
replies are cached by (model digest, prompt, query, image hash) so snapshot replays get
the same decision. Depth lifting and geometric veto are not here yet: the offline
feasibility test registered before K_v2 measures the 2D answer only.
"""
import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from experiments.t0_agent_v1.common import write_new

VERSION = 'k3-vlm-locate-2d-20261115'
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


def _call(endpoint, path, payload=None, timeout=30.):
    request = urllib.request.Request(endpoint.rstrip('/') + path, method='POST' if payload is not None else 'GET',
                                     data=None if payload is None else json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        # urllib drops the body, which is where ollama states why it failed.
        raise RuntimeError(f'ollama {path} HTTP {error.code}: {error.read().decode(errors="replace")[:2000]}') from error


def identity(endpoint, model):
    """Model tag, weight digest and server version, recorded once per run."""
    tags = _call(endpoint, '/api/tags')['models']
    entry = next(m for m in tags if m['name'] == model)
    show = _call(endpoint, '/api/show', {'model': model})
    return {'model': model, 'digest': entry['digest'], 'size': entry.get('size'), 'details': entry.get('details'),
            'parameters': show.get('parameters'), 'ollama': _call(endpoint, '/api/version')['version'],
            'primitive': VERSION, 'prompt_sha256': hashlib.sha256(PROMPT.encode()).hexdigest()}


def ask(png, query, setup, cache=None):
    """One model call, or the cached reply for the same digest, prompt, query and image.

    setup: endpoint, model, digest, options (temperature 0, seed), think, timeout_s.
    """
    key = hashlib.sha256(json.dumps([setup['digest'], PROMPT, query, hashlib.sha256(png).hexdigest()]).encode()).hexdigest()
    if cache is not None and (Path(cache) / f'{key}.json').exists():
        return dict(json.loads((Path(cache) / f'{key}.json').read_text()), cached=True)
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
