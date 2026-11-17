import json
import tempfile
import unittest
from pathlib import Path

from harness import vlm_locate as V


class QueryTest(unittest.TestCase):
    def test_public_colours_name_the_stage_zero_targets(self):
        roles = [({'category': 'fruit', 'appearance_rgba': [.69, .0552, .0368, 1.]}, 'the red fruit'),
                 ({'category': 'cup', 'appearance_rgba': [.138, .46, .782, 1.]}, 'the blue cup'),
                 ({'category': 'cup', 'appearance_rgba': [.9, .9, .86, 1.]}, 'the white cup'),
                 ({'category': 'fruit', 'appearance_rgba': [1., .55, .02, 1.]}, 'the orange fruit')]
        for role, expected in roles:
            self.assertEqual(V.query_text(role), expected)


class ParseTest(unittest.TestCase):
    def test_answer_scales_to_pixels_and_box_gives_missing_point(self):
        got = V.parse(json.dumps({'found': True, 'point': [500, 250], 'box': [400, 200, 600, 300],
                                  'label': 'apple', 'confidence': .9}), 320, 180)
        self.assertEqual((got['outcome'], got['point_px'], got['confidence']), ('answer', [160., 45.], .9))
        got = V.parse(json.dumps({'found': True, 'box': [400, 200, 600, 300], 'confidence': .5}), 320, 180)
        self.assertEqual(got['point_px'], [160., 45.])

    def test_abstain_and_invalid_are_never_guessed(self):
        self.assertEqual(V.parse('{"found": false}', 320, 180), {'outcome': 'abstain'})
        for text in ('not json', '{"point": [1, 2]}', '{"found": true, "point": [1200, 5], "confidence": .9}',
                     '{"found": true, "point": [1, 5]}', '[1, 2]'):
            self.assertEqual(V.parse(text, 320, 180)['outcome'], 'invalid', text)


class CacheTest(unittest.TestCase):
    def test_cached_reply_is_returned_without_a_call(self):
        setup = {'digest': 'd', 'endpoint': 'http://127.0.0.1:9', 'model': 'm'}
        with tempfile.TemporaryDirectory() as folder:
            import hashlib
            key = hashlib.sha256(json.dumps(['d', V.PROMPT, 'the red fruit',
                                             hashlib.sha256(b'png').hexdigest()]).encode()).hexdigest()
            (Path(folder) / f'{key}.json').write_text(json.dumps({'key': key, 'text': '{"found": false}'}))
            got = V.ask(b'png', 'the red fruit', setup, cache=folder)
            self.assertEqual((got['text'], got['cached']), ('{"found": false}', True))

    def test_replay_reads_source_caches_and_a_miss_never_calls_the_model(self):
        setup = {'digest': 'd', 'endpoint': 'http://127.0.0.1:9', 'model': 'm'}
        with tempfile.TemporaryDirectory() as folder:
            import hashlib
            source, own = Path(folder) / 'source', Path(folder) / 'own'
            source.mkdir()
            key = hashlib.sha256(json.dumps(['d', V.PROMPT, 'the red fruit',
                                             hashlib.sha256(b'png').hexdigest()]).encode()).hexdigest()
            (source / f'{key}.json').write_text(json.dumps({'key': key, 'text': '{"found": false}'}))
            got = V.ask(b'png', 'the red fruit', setup, cache=own, sources=[source], replay=True)
            self.assertTrue(got['cached'])
            with self.assertRaisesRegex(V.ReplayCacheMiss, 'REPLAY_CACHE_MISS'):
                V.ask(b'other png', 'the red fruit', setup, cache=own, sources=[source], replay=True)
            self.assertFalse(own.exists())


def scene(objects, width=320, height=180, focal=200., camera=(.4, 0., .6)):
    """Depth of a table (z = 0, pelvis frame) and objects, seen by a camera looking straight down.

    objects: ('sphere', centre, radius) or ('box', low corner, high corner).
    """
    import numpy as np
    rotation = np.array([[0., -1., 0.], [-1., 0., 0.], [0., 0., -1.]])
    K = np.array([[focal, 0., width / 2], [0., focal, height / 2], [0., 0., 1.]])
    v, u = np.indices((height, width))
    rays = np.stack(((u - K[0, 2]) / focal, (v - K[1, 2]) / focal, np.ones(u.shape)), axis=-1) @ rotation.T
    eye = np.asarray(camera)
    depth = np.full(u.shape, eye[2])
    for kind, a, b in objects:
        a = np.asarray(a, float)
        if kind == 'sphere':
            o = eye - a
            bb, cc = rays @ o, o @ o - b * b
            disc = bb * bb - (rays * rays).sum(-1) * cc
            t = (-bb - np.sqrt(np.maximum(disc, 0))) / (rays * rays).sum(-1)
            depth = np.where((disc > 0) & (t > 0), np.minimum(depth, t), depth)
        else:
            b = np.asarray(b, float)
            t = (eye[2] - b[2]) * np.ones(u.shape)
            hit = eye + rays * t[..., None]
            inside = (hit[..., 0] >= a[0]) & (hit[..., 0] <= b[0]) & (hit[..., 1] >= a[1]) & (hit[..., 1] <= b[1])
            depth = np.where(inside, np.minimum(depth, t), depth)
    transform = np.eye(4)
    transform[:3, :3], transform[:3, 3] = rotation, eye
    return {'rgb': np.zeros((height, width, 3), np.uint8), 'depth_m': depth, 'K': K,
            'T_optical_to_pelvis': transform, 'timestamp_s': 1.25}


def pixel(sensor, point):
    import numpy as np
    optical = np.linalg.inv(sensor['T_optical_to_pelvis'][:3, :3]) @ (np.asarray(point) - sensor['T_optical_to_pelvis'][:3, 3])
    return [float(sensor['K'][0, 0] * optical[0] / optical[2] + sensor['K'][0, 2]),
            float(sensor['K'][1, 1] * optical[1] / optical[2] + sensor['K'][1, 2])]


class LiftTest(unittest.TestCase):
    def setUp(self):
        self.sensor = scene([('sphere', (.4, .05, .035), .035), ('sphere', (.3, -.1, .03), .03),
                             ('box', (.5, -.25, 0.), (.75, .05, .05))])

    def answer(self, point, box=None):
        return {'outcome': 'answer', 'point_px': point, 'box_px': box, 'confidence': 0.}

    def test_point_on_a_fruit_gives_its_bottom_on_the_table(self):
        got = V.lift(self.sensor, self.answer(pixel(self.sensor, (.4, .05, .07))), 'fruit')
        self.assertLess(abs(got['cup_bottom_position_m'][0] - .4) + abs(got['cup_bottom_position_m'][1] - .05), .004)
        self.assertLess(abs(got['cup_bottom_position_m'][2]), .002)
        self.assertAlmostEqual(got['radius_estimate_m'], .035, delta=.003)
        self.assertEqual(got['source'], 'head_RGBD_vlm_lift')

    def test_fruit_touching_a_taller_object_in_the_image_is_fitted_alone(self):
        # The box top hides the sphere's edge from the camera, so the two touch in the image.
        sensor = scene([('sphere', (.4, .05, .035), .035), ('box', (.36, .07, 0.), (.44, .13, .1))])
        got = V.lift(sensor, self.answer(pixel(sensor, (.4, .05, .07))), 'fruit')
        self.assertLess(abs(got['cup_bottom_position_m'][0] - .4) + abs(got['cup_bottom_position_m'][1] - .05), .004)

    def test_box_picks_the_object_when_the_point_is_on_the_table(self):
        u, v = pixel(self.sensor, (.3, -.1, .06))
        got = V.lift(self.sensor, self.answer([u + 30, v], [u - 15, v - 15, u + 15, v + 15]), 'fruit')
        self.assertLess(abs(got['cup_bottom_position_m'][0] - .3) + abs(got['cup_bottom_position_m'][1] + .1), .004)

    def test_declared_failures_instead_of_guesses(self):
        cases = [({'outcome': 'abstain'}, 'VLM_ABSTAIN'), ({'outcome': 'invalid', 'reason': 'not JSON'}, 'VLM_INVALID'),
                 (self.answer(pixel(self.sensor, (.2, .3, 0.))), 'VLM_POINT_OFF_OBJECT'),
                 (self.answer(pixel(self.sensor, (.6, -.1, .05))), 'VETO_SIZE')]
        for answer, code in cases:
            with self.assertRaisesRegex(ValueError, code):
                V.lift(self.sensor, answer, 'fruit')


if __name__ == '__main__':
    unittest.main()
