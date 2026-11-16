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


if __name__ == '__main__':
    unittest.main()
