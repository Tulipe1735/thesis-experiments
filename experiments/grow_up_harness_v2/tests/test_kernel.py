import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import mujoco

from harness import kernel as K

XML = '<mujoco><worldbody><body><freejoint/><geom size=".1"/></body></worldbody></mujoco>'


class StagesTest(unittest.TestCase):
    def test_chain_flattens_tools_in_order_with_both_preflights(self):
        tp01, tp04 = K.stages('TP01'), K.stages('TP04')
        self.assertEqual(tp01[:2], [('locate', 'locate'), ('grasp', 'preflight')])
        self.assertEqual([s for _, s in tp01].count('preflight'), 2)
        self.assertEqual(tp04[:len(tp01)], tp01)
        self.assertEqual(tp04[-1], ('place', 'release_and_retreat'))
        self.assertEqual(len(tp04), sum(len(K.TOOLS[t]) for t in K.CHAINS['TP04']))

    def test_only_the_first_stage_of_each_tool_opens_it(self):
        chain = K.stages('TP04')
        opened = [stage for k, (_, stage) in enumerate(chain) if K.starts_tool(chain, k)]
        self.assertEqual(opened, ['locate', 'preflight', 'transfer'])
        self.assertFalse(K.starts_tool(chain, chain.index(('grasp', 'prepare')) + 1))


class FreezeTest(unittest.TestCase):
    def roundtrip(self, value, links, out, live, new_out):
        stream = io.BytesIO()
        K._Freezer(stream, links, out).dump(value)
        return K._Thawer(io.BytesIO(stream.getvalue()), live, new_out).load()

    def test_links_rebind_paths_move_and_sharing_survives(self):
        model = mujoco.MjModel.from_xml_string(XML)
        old, new = mujoco.MjData(model), mujoco.MjData(model)
        shared = [1, 2]
        value = {'data': old, 'model': model, 'a': shared, 'b': shared, 'none': None,
                 'folder': Path('/run/source/tools'), 'memory': Path('/repo/memory.json')}
        back = self.roundtrip(value, {'data': old, 'model': model, 'renderer': None}, Path('/run/source'),
                              {'data': new, 'model': model}, Path('/run/resume'))
        self.assertIs(back['data'], new)
        self.assertIs(back['model'], model)
        self.assertIs(back['a'], back['b'])
        self.assertIsNone(back['none'])
        self.assertEqual(back['folder'], Path('/run/resume/tools'))
        self.assertEqual(back['memory'], Path('/repo/memory.json'))

    def test_unlinked_mujoco_object_is_refused(self):
        model = mujoco.MjModel.from_xml_string(XML)
        with self.assertRaisesRegex(TypeError, 'unlinked MuJoCo object'):
            K._Freezer(io.BytesIO(), {'model': model}, Path('/run')).dump({'extra': mujoco.MjData(model)})


if __name__ == '__main__':
    unittest.main()


class AgentEpisodeTest(unittest.TestCase):
    def test_each_retry_resumes_the_entry_in_a_new_branch_carrying_the_abandoned_decisions(self):
        calls = []

        def execute(case, out, kernel, caps, resume=None, brain=None, carry=(), variant=None):
            calls.append({'out': out, 'resume': resume, 'carry': carry})
            out.mkdir(parents=True)
            retrying = len(calls) < 3
            entry = {'checkpoint': K.relative(out / 'checkpoints/01_locate.pkl.gz'), 'decisions': 1}
            (out / 'decisions.json').write_text(json.dumps([{'index': 0}, {'index': len(calls)}, {'retry': True}]))
            result = {'success': not retrying, 'error': None,
                      'agent': {'stop': 'retry' if retrying else 'done', 'retry': entry if retrying else None,
                                'vary': None}}
            (out / 'result.json').write_text(json.dumps(result))
            return result

        with tempfile.TemporaryDirectory(dir=K.ROOT / 'outputs') as folder, mock.patch.object(K, 'execute', execute):
            out = Path(folder) / 'agent'
            result = K.agent_episode({}, out, {}, {}, brain='b')
            self.assertTrue(result['success'])
            self.assertEqual([c['out'] for c in calls], [out, out / 'branches/01', out / 'branches/02'])
            self.assertEqual(calls[1]['resume'], out / 'checkpoints/01_locate.pkl.gz')
            self.assertEqual(calls[2]['resume'], out / 'branches/01/checkpoints/01_locate.pkl.gz')
            self.assertEqual(calls[1]['carry'], [{'index': 1}, {'retry': True}])
            retried = json.loads((out / 'retry.json').read_text())
            self.assertEqual([b['folder'] for b in retried['branches']],
                             [K.relative(out / 'branches/01'), K.relative(out / 'branches/02')])
            self.assertEqual((retried['success'], retried['final']), (True, K.relative(out / 'branches/02/result.json')))

    def test_a_variant_restarts_the_case_with_it_bound_and_carries_the_whole_history(self):
        calls = []

        def execute(case, out, kernel, caps, resume=None, brain=None, carry=(), variant=None):
            calls.append({'resume': resume, 'carry': carry, 'variant': variant})
            out.mkdir(parents=True)
            first = len(calls) == 1
            (out / 'decisions.json').write_text(json.dumps([{'index': 0}, {'vary': 'grasp'}] if first else []))
            result = {'success': not first, 'error': None, 'agent': {
                'stop': 'vary' if first else 'done', 'retry': None, 'vary': {'backoff_m': .08} if first else None}}
            (out / 'result.json').write_text(json.dumps(result))
            return result

        with tempfile.TemporaryDirectory(dir=K.ROOT / 'outputs') as folder, mock.patch.object(K, 'execute', execute):
            out = Path(folder) / 'agent'
            K.agent_episode({}, out, {}, {}, brain='b')
            self.assertEqual(calls[1], {'resume': None, 'carry': [{'index': 0}, {'vary': 'grasp'}],
                                        'variant': {'backoff_m': .08}})
            (branch,) = json.loads((out / 'retry.json').read_text())['branches']
            self.assertEqual((branch['resumed'], branch['variant']), (None, {'backoff_m': .08}))


class VariantTest(unittest.TestCase):
    def test_the_card_lists_every_override_key_with_a_meaning_bounds_and_the_bound_value(self):
        from harness import agent_column as A
        from experiments.t0_agent_v1.adaptive_reuse_grasp import CATEGORY_KEYS, DEFAULTS
        card = K.variant_card(DEFAULTS)
        self.assertEqual(set(card), CATEGORY_KEYS)
        self.assertEqual(set(A.PARAMETERS), CATEGORY_KEYS)
        self.assertEqual(card['backoff_m'], {'bounds': [.045, .13], 'current': DEFAULTS['backoff_m']})
        self.assertEqual(card['approach_mode']['bounds'], ['palm_backoff', 'pelvis_forward', 'top_down'])
        self.assertEqual(card['forward_first']['bounds'], [False, True])

    def test_a_variant_binds_inside_the_frozen_envelope_only(self):
        from experiments.t0_agent_v1.adaptive_reuse_grasp import DEFAULTS
        base = {'category': 'cup', 'leaf_reply': None, 'parameters': dict(DEFAULTS)}
        bound = K.bind_variant(base, {'clear_position_m': [.2, .35, .36], 'backoff_m': .08})
        self.assertEqual((bound['parameters']['clear_position_m'], bound['parameters']['backoff_m']), ([.2, .35, .36], .08))
        self.assertEqual((bound['base_parameters'], bound['variant']['backoff_m']), (DEFAULTS, .08))
        for bad in ({'backoff_m': .5}, {'clear_position_m': [.2, .35, .5]}, {'approach_mode': 'sideways'},
                    {'servo_period_s': .033}):
            with self.assertRaises(ValueError, msg=bad):
                K.bind_variant(base, bad)

    def test_diagnosis_names_the_link_the_role_touched_and_the_route(self):
        plant = mock.Mock(guard='FORBIDDEN_CONTACT', first_failure={
            'forbidden_contacts': [{'bodies': ['left_hand_index_1_link', 'distractor_2']}], 'speed_faults': []})
        port = mock.Mock()
        port.state.return_value = {'palms': {'left': {'position_m': [.31234, .35, .3]}}}
        controller = mock.Mock(plan={'selected_yaw_rad': .7, 'path': {'goals': [['orient_clear', [.3, .35, .32]]]}})
        got = K.diagnose(plant, controller, port, [{'stage': 'preflight'}], {'distractor_2', 'cup_1'})
        self.assertEqual(got, {'route': {'selected_yaw_rad': .7, 'waypoints': [['orient_clear', [.3, .35, .32]]]},
                               'guard_detail': {'palm_position_pelvis_m': [.3123, .35, .3],
                                                'robot_link': 'left_hand_index_1_link', 'touched': 'distractor_2'}})
        plant.first_failure['forbidden_contacts'][0]['bodies'] = ['left_elbow_link', 'table']
        self.assertEqual(K.diagnose(plant, controller, port, [], set())['guard_detail']['touched'], 'table_or_scene')
