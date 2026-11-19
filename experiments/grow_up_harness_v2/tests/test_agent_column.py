import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness import agent_column as A
from harness.agent import AgentSchemaError, GatewayResponse
from harness.vlm_locate import ReplayCacheMiss

TASK = {'id': 'TP03_near_1', 'template_id': 'TP03', 'instruction': '杯底完整入盘', 'initial_semantics': '一个杯在桌上',
        'goals': [{'predicate': 'SupportedIn', 'object': 'cup_1', 'target': 'tray'}],
        'roles': [{'role': 'tray', 'category': 'tray', 'appearance_rgba': [.39, .24, .12, 1.], 'target': False},
                  {'role': 'cup_1', 'category': 'cup', 'appearance_rgba': [.138, .46, .782, 1.], 'target': True}],
        'current_status': 'prepared'}


def executed(call, ok, args=None, guard=None):
    failure = None if ok else {'type': 'ActionFailure', 'message': 'x', **({'guard': guard} if guard else {})}
    return {'decision': {'call': call, 'args': args or {}}, 'outcome': {'executed': True, 'ok': ok, 'failure': failure}}


def branch(*records, before=()):
    """Records in order, each executed one given the path its kernel would record."""
    history = list(before)
    for r in records:
        if r['outcome']['executed'] and 'call' in r['decision']:
            r = dict(r, path=A.path(r['decision']['call'], r['decision']['args'], history))
        history.append(r)
    return history


def abandoned(history):
    return [dict(d, abandoned=True) for d in history]


RETRY = {'decision': {'retry': True}, 'outcome': {'executed': True, 'ok': True}}
RECIPE = {'backoff_m': {'bounds': [.045, .13], 'current': .13}, 'clear_position_m': {
    'bounds': [[-.07, .3], [.15, .42], [.23, .38]], 'current': [.3, .35, .32]},
    'approach_mode': {'bounds': ['palm_backoff', 'pelvis_forward', 'top_down'], 'current': 'top_down'},
    'preferred_yaw': {'bounds': [-3.14, 3.14], 'current': .7}, 'forward_first': {'bounds': [False, True], 'current': False}}


def vary(parameters, executed=True):
    return {'decision': {'vary': 'grasp', 'parameters': parameters, 'hypothesis': 'h', 'expected': 'e'},
            'outcome': {'executed': executed, 'ok': executed}}


class Gateway:
    def __init__(self, text):
        self.text, self.prompts = text, []

    def run(self, prompt):
        self.prompts.append(prompt)
        return GatewayResponse(text=self.text, session_id='ses_1', message_id='m', model='brain', prompt_sha256='p',
                               response_sha256='r', input_tokens=1, output_tokens=1, cost=0., wall_time_s=.5)


class PackTest(unittest.TestCase):
    def test_pack_follows_the_chain_and_drops_vlm_without_the_primitive(self):
        self.assertEqual(list(A.pack(('locate', 'grasp'), True)), ['locate', 'grasp'])
        plain = A.pack(('locate', 'grasp', 'place'), False)['locate']
        self.assertEqual(list(plain['args']['method']), ['colour'])
        self.assertNotIn('query', plain['args'])
        self.assertIn('query', A.CARDS['locate']['args'])

    def test_public_task_names_colours_and_drops_status(self):
        task = A.public_task(TASK)
        self.assertEqual(task['roles'][1], {'role': 'cup_1', 'category': 'cup', 'colour': 'blue', 'target': True})
        self.assertNotIn('appearance_rgba', json.dumps(task))
        self.assertNotIn('current_status', task)


class DecideTest(unittest.TestCase):
    cards = A.pack(('locate', 'grasp', 'place'), True)

    def test_calls_and_stops_in_schema_are_read(self):
        self.assertEqual(A.decide('{"call": "grasp"}', self.cards), {'call': 'grasp', 'args': {}})
        got = A.decide('```json\n{"call": "locate", "args": {"method": "vlm", "query": "the blue cup"}}\n```', self.cards)
        self.assertEqual(got['args']['query'], 'the blue cup')
        self.assertEqual(A.decide('{"stop": "give_up", "reason": "no node"}', self.cards)['stop'], 'give_up')
        self.assertIs(A.decide('{"retry": true, "reason": "change the locate query"}', self.cards)['retry'], True)
        self.assertEqual(A.decide('{"stop": "give_up", "gap": "geometry", "reason": "r"}', self.cards)['gap'], 'geometry')
        cards = A.pack(('locate', 'grasp'), True, RECIPE)
        got = A.decide('{"vary": "grasp", "parameters": {"backoff_m": 0.08}, "hypothesis": "h", "expected": "e"}', cards)
        self.assertEqual(got['parameters'], {'backoff_m': .08})

    def test_replies_outside_the_schema_are_never_guessed(self):
        for text in ('grasp it', '{"call": "push"}', '{"call": "grasp", "args": {"force": 1}}', '{"stop": "maybe"}',
                     '{"call": "locate", "args": {"method": "vlm"}}',
                     '{"call": "locate", "args": {"method": "colour", "query": "the cup"}}',
                     '{"call": "grasp", "extra": 1}', '{"call": "grasp", "reason": 3}', '{"retry": "grasp"}',
                     '{"retry": true, "call": "grasp"}'):
            with self.assertRaises(AgentSchemaError, msg=text):
                A.decide(text, self.cards)
        cards = A.pack(('locate', 'grasp'), True, RECIPE)
        five = {k: RECIPE[k]['current'] for k in RECIPE}
        for value in ({'vary': 'grasp', 'parameters': {'hand_kp': 1}, 'hypothesis': 'h', 'expected': 'e'},
                      {'vary': 'grasp', 'parameters': five, 'hypothesis': 'h', 'expected': 'e'},
                      {'vary': 'grasp', 'parameters': {}, 'hypothesis': 'h', 'expected': 'e'},
                      {'vary': 'place', 'parameters': {'backoff_m': .1}, 'hypothesis': 'h', 'expected': 'e'},
                      {'vary': 'grasp', 'parameters': {'backoff_m': .1}},
                      {'stop': 'done', 'gap': 'geometry'}, {'stop': 'give_up', 'gap': 'luck'}):
            with self.assertRaises(AgentSchemaError, msg=value):
                A.decide(json.dumps(value), cards)
        with self.assertRaises(AgentSchemaError):
            A.decide('{"vary": "grasp", "parameters": {"backoff_m": 0.1}, "hypothesis": "h", "expected": "e"}',
                     self.cards)
        with self.assertRaises(AgentSchemaError):
            A.decide('{"call": "locate", "args": {"method": "vlm", "query": "x"}}', A.pack(('locate',), False))
        with self.assertRaises(AgentSchemaError):
            A.decide('{"call": "place"}', A.pack(('locate', 'grasp'), True))


VLM = {'method': 'vlm', 'query': 'the blue cup'}


class PreconditionTest(unittest.TestCase):
    def test_order_follows_the_executed_records(self):
        self.assertIsNone(A.unmet('locate', {}, []))
        self.assertIn('grasp', A.unmet('grasp', {}, []))
        self.assertIn('grasp', A.unmet('grasp', {}, branch(executed('locate', False))))
        self.assertIsNone(A.unmet('grasp', {}, branch(executed('locate', False), executed('locate', True, VLM))))
        self.assertIsNone(A.unmet('locate', VLM, branch(executed('locate', True))))
        located = branch(executed('locate', True), executed('grasp', False))
        self.assertIn('locate', A.unmet('locate', VLM, located))
        self.assertIn('once', A.unmet('grasp', {}, located))
        self.assertIn('place', A.unmet('place', {}, located))
        self.assertIsNone(A.unmet('place', {}, branch(executed('locate', True), executed('grasp', True))))

    def test_a_refused_call_is_not_an_executed_one(self):
        refused = {'decision': {'call': 'grasp', 'args': {}}, 'outcome': {'executed': False, 'ok': False}}
        self.assertIsNone(A.unmet('grasp', {}, branch(executed('locate', True), refused)))

    def test_a_guard_stop_leaves_only_retry_or_give_up(self):
        stopped = branch(executed('locate', True), executed('grasp', False, guard='FORBIDDEN_CONTACT'))
        for call, args in (('place', {}), ('locate', VLM), ('grasp', {})):
            self.assertIn('guard', A.unmet(call, args, stopped))
        self.assertIsNone(A.unmet_retry(stopped, 2))

    def test_retry_needs_a_failed_node_and_a_fork(self):
        self.assertIn('failed', A.unmet_retry([], 2))
        self.assertIn('failed', A.unmet_retry(branch(executed('locate', True)), 2))
        failed = branch(executed('locate', True), executed('grasp', False))
        self.assertIsNone(A.unmet_retry(failed, 1))
        self.assertIn('no retries', A.unmet_retry(failed, 0))
        refused_retry = {'decision': {'retry': True}, 'outcome': {'executed': False, 'ok': False}}
        self.assertEqual(A.retries([*failed, refused_retry]), 0)
        again = branch(executed('grasp', False), before=[failed[0], *abandoned(failed[1:]), RETRY])
        self.assertEqual(A.retries(again), 1)
        self.assertIn('no retries', A.unmet_retry(again, 1))
        self.assertIsNone(A.unmet_retry(again, 2))

    def test_vary_follows_a_failed_grasp_shares_forks_and_never_repeats(self):
        self.assertIn('failed grasp', A.unmet_vary({'backoff_m': .1}, branch(executed('locate', False)), 2))
        self.assertIn('failed grasp', A.unmet_vary({'backoff_m': .1}, branch(executed('locate', True)), 2))
        failed = branch(executed('locate', True), executed('grasp', False, guard='FORBIDDEN_CONTACT'))
        self.assertIsNone(A.unmet_vary({'backoff_m': .1}, failed, 1))
        # A retry resumed before the failed grasp (now abandoned) and relocated: the variant is still allowed.
        resumed = branch(executed('locate', True, VLM), before=[failed[0], *abandoned(failed[1:]), RETRY])
        self.assertIsNone(A.unmet_vary({'backoff_m': .1}, resumed, 2))
        self.assertIn('no retries', A.unmet_vary({'backoff_m': .1}, resumed, 1))
        # Restarted with the variant bound: every earlier decision is abandoned, the fork is spent.
        restarted = branch(executed('locate', True), executed('grasp', False),
                           before=[*abandoned(failed), vary({'backoff_m': .1})])
        self.assertEqual(A.retries(restarted), 1)
        self.assertIn('already ran', A.unmet_vary({'backoff_m': .1}, restarted, 3))
        self.assertIsNone(A.unmet_vary({'backoff_m': .08}, restarted, 3))
        self.assertIn('no retries', A.unmet_vary({'backoff_m': .08}, restarted, 1))
        self.assertIn('no retries', A.unmet_retry(restarted, 1))

    def test_a_variant_roots_the_path_so_its_calls_are_not_repeats(self):
        first = branch(executed('locate', True), executed('grasp', False))
        history = [*abandoned(first), vary({'backoff_m': .1})]
        self.assertIsNone(A.unmet('locate', {}, history, {'backoff_m': .1}))
        self.assertIn('repeat', A.unmet('locate', {}, history))
        self.assertEqual(A.path('locate', {}, history, {'backoff_m': .1}),
                         [['vary', {'backoff_m': .1}], ['locate', {}]])

    def test_after_a_retry_the_branch_restarts_its_rules_and_refuses_a_repeat(self):
        # Resumed at the grasp entry: the restored locate stays, the failed grasp is abandoned.
        located = branch(executed('locate', True))
        resumed = [*located, *abandoned(branch(executed('grasp', False), before=located)[1:]), RETRY]
        self.assertIn('repeat', A.unmet('grasp', {}, resumed))
        self.assertIsNone(A.unmet('locate', VLM, resumed))
        relocated = branch(executed('locate', True, VLM), before=resumed)
        self.assertIsNone(A.unmet('grasp', {}, relocated))
        self.assertEqual(relocated[-1]['path'], [['locate', {}], ['locate', VLM]])


class PromptTest(unittest.TestCase):
    def test_prompt_is_a_function_of_decisions_and_outcomes_only(self):
        cards, task = A.pack(('locate', 'grasp'), False), A.public_task(TASK)
        row = {**executed('locate', True), 'text': 'raw', 'cached': False, 'wall_time_s': 3., 'key': 'k'}
        again = {**row, 'cached': True, 'wall_time_s': 0., 'text': 'other'}
        self.assertEqual(A.prompt(task, cards, [row], 3, 1), A.prompt(task, cards, [again], 3, 1))
        self.assertNotEqual(A.prompt(task, cards, [row], 3, 1), A.prompt(task, cards, [row], 2, 1))
        self.assertNotEqual(A.prompt(task, cards, [row], 3, 1), A.prompt(task, cards, [row], 3, 0))

    def test_variant_card_and_vary_schema_appear_only_with_a_recipe(self):
        task = A.public_task(TASK)
        plain = json.loads(A.prompt(task, A.pack(('locate', 'grasp'), True), [], 4, 2))
        self.assertFalse(any('vary' in form for form in plain['output_schema']))
        self.assertFalse(any('vary' in rule for rule in plain['rules']))
        cards = A.pack(('locate', 'grasp'), True, RECIPE)
        self.assertEqual(cards['grasp_variant']['parameters']['backoff_m'],
                         {'meaning': A.PARAMETERS['backoff_m'][0], 'stage': 'approach', 'bounds': [.045, .13],
                          'current': .13})
        payload = json.loads(A.prompt(task, cards, [vary({'backoff_m': .1})], 4, 1))
        self.assertTrue(any(form.startswith('{"vary"') for form in payload['output_schema']))
        self.assertEqual(payload['history'][0]['parameters'], {'backoff_m': .1})
        # The guard rule offers vary, and changing parameters goes through vary rather than retry.
        self.assertTrue(any(rule.startswith('A guard stop') and 'retry, vary or give_up' in rule
                            for rule in payload['rules']))
        self.assertTrue(any(rule.startswith('To change grasp_variant parameters answer vary directly')
                            for rule in payload['rules']))
        self.assertLessEqual(set(RECIPE), set(A.PARAMETERS))

    def test_prompt_marks_abandoned_attempts_and_retries(self):
        cards, task = A.pack(('locate', 'grasp'), True), A.public_task(TASK)
        history = json.loads(A.prompt(task, cards, [{**executed('grasp', False), 'abandoned': True}, RETRY], 4, 1))
        self.assertEqual([sorted(h) for h in history['history']],
                         [['abandoned', 'args', 'call', 'outcome'], ['outcome', 'retry']])
        self.assertIn('{"retry": true, "reason": "<one sentence>"}', history['output_schema'])

    def test_self_report_keeps_the_estimate_and_drops_evaluator_truth(self):
        answer = {'outcome': 'answer', 'point_px': [128., 99.], 'box_px': [120., 90., 144., 117.], 'label': 'red cup',
                  'confidence': 0.}
        results = [{'stage': 'locate', 'phase': 'initial',
                    'result': {'cup_bottom_position_m': [.40581, .40171, .17002], 'source': 'head_RGBD_vlm_lift',
                               'radius_estimate_m': .03812, 'visible_center_pelvis_m': [.41, .4, .22], 'fit_rms_m': None,
                               'vlm': {'query': 'the red cup', 'reply': {'text': 'raw'}, 'answer': answer}}}]
        report = A.self_report('locate', True, results, None, 'initial')
        diagnosis = {'guard_detail': {'robot_link': 'left_hand_index_1_link', 'touched': 'distractor_2'}}
        stopped = A.self_report('grasp', False, [], {'type': 'ActionFailure', 'message': 'translate_clear: STOPPED'},
                                'located', 'FORBIDDEN_CONTACT', diagnosis)
        self.assertEqual(stopped['failure']['guard'], 'FORBIDDEN_CONTACT')
        self.assertEqual(stopped['diagnosis'], diagnosis)
        self.assertEqual(report['estimate'], {
            'bottom_position_pelvis_m': [.4058, .4017, .17], 'source': 'head_RGBD_vlm_lift', 'radius_m': .0381,
            'visible_center_pelvis_m': [.41, .4, .22],
            'vlm': {'query': 'the red cup', 'point_px': [128., 99.], 'box_px': [120., 90., 144., 117.],
                    'label': 'red cup', 'confidence': 0.}})
        failed = A.self_report('grasp', False, [{'stage': 'preflight', 'result': {}, 'phase': 'located'}],
                               {'type': 'ActionFailure', 'message': 'x' * 900, 'stage': 'preflight', 'tool': 'grasp'},
                               'located')
        self.assertEqual(set(failed), {'executed', 'ok', 'stages', 'phase', 'failure'})
        self.assertEqual(len(failed['failure']['message']), 300)


class ScriptGatewayTest(unittest.TestCase):
    def test_replays_locates_then_runs_the_chain_and_gives_up_after_a_failed_node(self):
        cards, task = A.pack(('locate', 'grasp', 'place'), True), A.public_task(TASK)
        script = A.ScriptGateway([{'method': 'colour'}, VLM])

        def reply(history):
            return A.decide(script.run(A.prompt(task, cards, history, 9, 0)).text, cards)
        self.assertEqual(reply([]), {'call': 'locate', 'args': {'method': 'colour'}, 'reason': 'script'})
        missed = [executed('locate', False)]
        self.assertEqual(reply(missed)['args'], VLM)
        located = [*missed, executed('locate', True, VLM)]
        self.assertEqual(reply(located)['call'], 'grasp')
        self.assertEqual(reply([*located, executed('grasp', True)])['call'], 'place')
        self.assertEqual(reply([*located, executed('grasp', True), executed('place', True)])['stop'], 'done')
        self.assertEqual(reply([*located, executed('grasp', False, guard='FORBIDDEN_CONTACT')]),
                         {'stop': 'give_up', 'gap': 'kernel', 'reason': 'script'})
        self.assertEqual(reply([*missed, executed('locate', False, VLM)])['gap'], 'perception')
        response = script.run(A.prompt(task, cards, [], 9, 0))
        self.assertEqual((response.model, response.input_tokens, response.output_tokens), ('script', 0, 0))


class MagpieTest(unittest.TestCase):
    def reply(self):
        return {'status': 'completed', 'model': A.MagpieBrainGateway.MODEL, 'id': 'resp_1',
                'output': [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': '{}'}]}],
                'usage': {'input_tokens': 3, 'output_tokens': 2, 'output_tokens_details': {'reasoning_tokens': 9}}}

    def sent(self, reasoning):
        connection = mock.MagicMock()
        connection.getresponse.return_value.status = 200
        with mock.patch.object(A.http.client, 'HTTPConnection', return_value=connection), \
                mock.patch.object(A.json, 'load', return_value=self.reply()):
            response = A.MagpieBrainGateway(5, reasoning).run('p')
        return json.loads(connection.request.call_args[0][2]), response

    def test_effort_is_sent_only_when_registered(self):
        request, response = self.sent('high')
        self.assertEqual((request['reasoning'], request['tools']), ({'effort': 'high'}, []))
        self.assertEqual(response.reasoning_tokens, 9)
        self.assertNotIn('reasoning', self.sent('default')[0])
        with self.assertRaises(ValueError):
            A.MagpieBrainGateway(5, 'max')


class BrainTest(unittest.TestCase):
    def test_cache_answers_a_repeated_prompt_and_a_replay_never_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            gateway = Gateway('{"call": "grasp"}')
            brain = A.Brain(gateway, {'model': 'brain'})
            first = brain.ask('p', Path(tmp) / 'source')
            self.assertFalse(first['cached'])
            resumed = brain.ask('p', Path(tmp) / 'resume', [Path(tmp) / 'source'], replay=True)
            self.assertTrue(resumed['cached'])
            self.assertEqual(resumed['text'], first['text'])
            with self.assertRaises(ReplayCacheMiss):
                brain.ask('q', Path(tmp) / 'resume', [Path(tmp) / 'source'], replay=True)
            self.assertEqual(gateway.prompts, ['p'])
            other = A.Brain(gateway, {'model': 'other'})
            self.assertFalse(other.ask('p', Path(tmp) / 'source')['cached'])

    def test_decision_logs_compare_without_cache_use_and_timing(self):
        row = {'index': 0, 'text': 't', 'cached': False, 'wall_time_s': 2.}
        self.assertTrue(A.same_decisions([row], [{**row, 'cached': True, 'wall_time_s': 0.}]))
        self.assertFalse(A.same_decisions([row], [{**row, 'text': 'u'}]))


if __name__ == '__main__':
    unittest.main()
