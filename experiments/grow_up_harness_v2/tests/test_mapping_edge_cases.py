"""Regressions from the independent mapping and evidence review."""
import ast
import json
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/grow_up_harness_v2/calibration'))

from harness import artifact_v2 as A, grow_loop as L, t01_episode as T1
from harness.agent import check_source
from harness.llm import Client, LLMReplyError, LLMProviderError
from mapping_holdout import account_model_call
from mapping_export import official_first_success


class ScopeTests(unittest.TestCase):
    def assert_equivalent(self, source):
        check_source(source)
        imports, body, _ = A._namespaced(source, '_L0_')
        mapped = ast.unparse(ast.Module(body=imports + body, type_ignores=[]))
        original, projection = {}, {}
        exec(compile(source, '<leaf>', 'exec'), original)
        exec(compile(mapped, '<projection>', 'exec'), projection)
        self.assertEqual(original['act']({}, {}, None), projection['_L0_act']({}, {}, None))

    def test_comprehension_outer_iterable_uses_enclosing_scope(self):
        for expression in ('[x for x in x]', 'list(x for x in x)', 'sorted({x for x in x})', '{str(x): x for x in x}'):
            with self.subTest(expression=expression):
                self.assert_equivalent('x=[1,2]\ndef act(o,t,s):\n return {"action":{"op":"done"},"state":' + expression + '}\n')

    def test_nested_comprehension_keeps_later_iterables_local(self):
        self.assert_equivalent('x=[[1,2],[3]]\ndef act(o,t,s):\n return {"action":{"op":"done"},"state":[y for x in x for y in x]}\n')

    def test_lambda_defaults_use_enclosing_scope(self):
        for signature in ('x=x', '*, x=x'):
            with self.subTest(signature=signature):
                self.assert_equivalent('x=7\nf=lambda ' + signature + ':x\ndef act(o,t,s):\n return {"action":{"op":"done"},"state":f()}\n')

    def test_read_only_store_does_not_touch_ledger_and_rejects_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tree = {'nodes': [], 'version': 'unit'}
            A.Store(root, tree)
            ledger = root / 'ledger.jsonl'
            before = ledger.stat().st_mtime_ns
            reader = A.Store(root, tree, read_only=True)
            self.assertEqual(reader.refs(), [])
            self.assertEqual(ledger.stat().st_mtime_ns, before)
            with self.assertRaises(PermissionError):
                reader.put_source('text')
            with self.assertRaises(PermissionError):
                reader.snapshot('bad')
            self.assertEqual(ledger.stat().st_mtime_ns, before)

    def test_composite_retains_optional_state_like_a_direct_worker(self):
        from tests.test_artifact_v2 import leaf_data, composite_data, TREE
        source = '''
def init(profile): return {'i': 0}
def act(o,t,s):
    if s['i'] >= 1: return {'action': {'op': 'done'}}
    s['i'] += 1
    return {'action': {'op': 'wait', 'duration': .02}}
'''
        with tempfile.TemporaryDirectory() as directory:
            store = A.Store(Path(directory), TREE)
            leaf = store.add(leaf_data(store, source=source))
            comp = store.add(composite_data([{'use': leaf, 'params': {'n': {'literal': 1}, 'd': {'literal': .02}}}]))
            self.assertTrue(L.dry_run(source, {}, {}, {'joints': {}}, 3)['passed'])
            self.assertTrue(L.dry_run(store.code(comp), {}, {}, {'joints': {}}, 3)['passed'])


class AccountingTests(unittest.TestCase):
    def test_provider_error_inside_successful_http_stream_stops_as_provider_failure(self):
        stream = b'data: {"error":{"type":"insufficient_quota","message":"provider quota exhausted"}}\n\ndata: [DONE]\n'
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'OPENCODE_API_KEY': 'unit-key'}):
            record = Path(directory) / 'model'
            client = Client('opencode_go', 'deepseek-v4.1-flash')
            with patch('urllib.request.urlopen', return_value=io.BytesIO(stream)):
                with self.assertRaises(LLMProviderError):
                    client.chat('Return JSON.', 'Ready?', record)
            meta = json.loads((record / 'metadata.json').read_text())
            self.assertEqual(meta['failure_kind'], 'provider')
            self.assertIn('insufficient_quota', (record / 'stream.jsonl').read_text())

    def test_direct_json_options_are_recorded_in_actual_request(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'OPENCODE_API_KEY': 'unit-key'}):
            record = Path(directory) / 'model'
            client = Client('opencode_go', 'deepseek-v4.1-flash', thinking='disabled', json_mode=True)
            with patch.object(client, '_stream', return_value=('{"ready":true}', {}, 'stop')):
                reply, _ = client.chat('Return JSON.', 'Ready?', record)
            self.assertEqual(reply, {'ready': True})
            request = json.loads((record / 'request.json').read_text())
            self.assertEqual(request['thinking'], {'type': 'disabled'})
            self.assertEqual(request['response_format'], {'type': 'json_object'})

    def test_generation_failure_keeps_usage_and_is_not_transport_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'OPENCODE_API_KEY': 'unit-key'}):
            folder = Path(directory) / 'attempt'
            client = Client('opencode_go', 'deepseek-v4.1-flash', max_tokens=14000)
            usage = {'prompt_tokens': 4261, 'completion_tokens': 14000}
            with patch.object(client, '_stream', return_value=('', usage, 'length')):
                with self.assertRaises(LLMReplyError):
                    client.chat('system', 'task', folder / 'model')
            meta = json.loads((folder / 'model/metadata.json').read_text())
            self.assertEqual(meta['failure_kind'], 'generation_limit')
            self.assertEqual(meta['usage'], usage)
            counts = {'llm_wall_s': 0., 'prompt_tokens': 0, 'completion_tokens': 0}
            account_model_call(counts, folder)
            self.assertEqual(counts['prompt_tokens'], 4261)
            self.assertEqual(counts['completion_tokens'], 14000)
            self.assertEqual(counts['llm_wall_s'], meta['wall_seconds'])
            self.assertNotIn('unit-key', (folder / 'model/request.json').read_text())

    def test_joint_gate_records_attempted_calls_and_seccomp(self):
        for action, passed in [({'op': 'done'}, True), ({'op': 'unknown'}, False)]:
            with self.subTest(action=action):
                source = f'def act(o,t,s):\n return {{"action":{action!r},"state":None}}\n'
                result = L.dry_run(source, {}, {}, {'joints': {}}, 8)
                self.assertEqual(result['passed'], passed)
                self.assertEqual(result['worker_calls'], 1)
                self.assertTrue(result['security']['seccomp'])

    def test_cartesian_gate_counts_rejected_phase_call(self):
        source = '''
def grasp_parameters(o): return {}
def plan(o): return []
def lift(o,p): return 'invalid commands'
def correct(o,p): return []
def release(o,p): return []
'''
        result = T1.dry_run(source, {'joints': {}})
        self.assertFalse(result['passed'])
        self.assertEqual(result['worker_calls'], 2)
        self.assertTrue(result['security']['seccomp'])

    def test_completion_time_uses_strict_official_one_second_boundary(self):
        cup = {'footprint_margin_m': .01, 'tray_floor_support_N': 1., 'hand_contact_N': 0.,
               'other_object_contact_N': 0., 'support_height_error_m': 0., 'cup_tilt_deg': 0.,
               'linear_speed_m_s': 0., 'angular_speed_rad_s': 0., 'pelvis_tilt_deg': 0., 'pelvis_drift_m': 0.}
        times = [10. + i * .05 for i in range(20)] + [11. - 1e-10, 11.05]
        rows = [{'time': t, 'cups': {'task_cup': cup}, 'tray_linear_speed_m_s': 0.,
                 'tray_angular_speed_rad_s': 0., 'tray_tilt_deg': 0., 'tray_hand_contact_N': 0.} for t in times]
        with tempfile.TemporaryDirectory() as directory:
            episode = Path(directory)
            (episode / 'verified_samples.json').write_text(json.dumps(rows))
            verdict = {'execution_error': None, 'protection': None, 'initial_valid': True}
            self.assertEqual(official_first_success(episode, verdict), 11.05)
