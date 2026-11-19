"""Agent column of the tabletop flow: the brain calls G0 nodes one at a time at P3 (stage 0.5 item 4).

GROW_UP_ROOT_DOWN_REVISE_20261113 §2.1 step 1. The brain sees the public task, the skill
pack (P2 call cards of the template's G0 nodes) and its own decision history with each
node's self-report; never evaluator truth. Each decision is one stateless gateway call whose
prompt holds the whole history, so a reply is a function of the prompt: replies are cached
by (brain identity, prompt) and a checkpoint resume replays them, the way K3 replays VLM
replies. kernel.execute runs the chosen node with the engineering column's stage code and
writes a checkpoint at every node boundary.

Nodes are the K_v1 tools. Configuration (recipe binding, impedance, hand_open) stays before
the first decision as in the engineering column. Preconditions are checked on the brain's
own records of the current branch before any physics: locate only before grasp, grasp once
after a successful locate, place once after a successful grasp, nothing after a guard stop.
An unmet precondition is fed back without stepping physics.

Retry (user decision 2026-11-18): after a failed node, including a guard stop, the brain may
reply retry. The plant latches a guard (grow_up_v2/plant.py), so a retry never continues in
place: kernel.agent_episode resumes the failed node's entry checkpoint in a new branch, with
the failed attempt kept in the history and marked abandoned. Physics is deterministic, so a
node call that would repeat an executed path from the episode start is refused.

Variant (user decision 2026-11-18, §2.1.1 step 4 in its bounded form): after a failed grasp
the brain may reply vary with at most 4 grasp parameters. A variant is the category's bound
recipe with those keys overridden inside the frozen recipe envelope (adaptive_reuse_grasp
CATEGORY_KEYS and _validate); the stage code is unchanged. The recipe binds at configuration,
so agent_episode restarts the episode with the variant bound and every earlier decision
abandoned. Retries and variants share the fork budget. After a node the brain sees its own
outputs: the locate fit and the K3 answer, the grasp's planned route and, after a guard, the
robot's guard diagnosis (link, touched role, palm position): an aid reported with the results.
"""
import hashlib
import http.client
import json
import time
from contextlib import closing
from pathlib import Path

from experiments.t0_agent_v1.common import write_new
from .agent import AgentSchemaError, GatewayResponse, GatewayUnavailable, parse_json_reply
from .vlm_locate import ReplayCacheMiss, colour_name

VERSION = 'agent-column-p3-g0-vary2-20261118'


class MagpieBrainGateway:
    """One stateless Astra decision through the local Magpie Responses endpoint."""

    MODEL = 'gpt-6.2-astra'

    EFFORTS = ('default', 'low', 'medium', 'high')

    def __init__(self, timeout_s, reasoning='default'):
        if reasoning not in self.EFFORTS:
            raise ValueError(f'reasoning must be one of {self.EFFORTS}')
        self.timeout_s, self.reasoning = timeout_s, reasoning

    def run(self, prompt):
        started = time.monotonic()
        request = {'model': self.MODEL, 'input': prompt, 'tools': [], 'store': False, 'stream': False,
                   **({'reasoning': {'effort': self.reasoning}} if self.reasoning != 'default' else {})}
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer magpie',
                   'x-openai-actor-authorization': 'magpie'}
        try:
            with closing(http.client.HTTPConnection('127.0.0.1', 3425, timeout=self.timeout_s)) as connection:
                connection.request('POST', '/v1/responses', json.dumps(request), headers)
                response = connection.getresponse()
                if response.status != 200:
                    raise GatewayUnavailable(f'Magpie HTTP {response.status} {response.reason}')
                reply = json.load(response)
        except (OSError, http.client.HTTPException, ValueError) as error:
            raise GatewayUnavailable(f'Magpie request failed: {error}') from error

        if not isinstance(reply, dict) or reply.get('status') != 'completed' or reply.get('model') != self.MODEL:
            raise GatewayUnavailable(f'Magpie did not complete a {self.MODEL} response')
        try:
            text = ''.join(part['text'] for item in reply['output']
                           if item.get('type') == 'message' and item.get('role') == 'assistant'
                           for part in item['content'] if part.get('type') == 'output_text').strip()
            response_id = reply['id']
            usage = reply['usage']
            input_tokens, output_tokens = usage['input_tokens'], usage['output_tokens']
            reasoning_tokens = (usage.get('output_tokens_details') or {}).get('reasoning_tokens', 0)
        except (AttributeError, KeyError, TypeError) as error:
            raise GatewayUnavailable('Magpie returned an invalid Responses payload') from error
        if not text:
            raise GatewayUnavailable('Magpie returned no assistant text')
        return GatewayResponse(text=text, session_id='', message_id=response_id, model=reply['model'],
                               prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                               response_sha256=hashlib.sha256(text.encode()).hexdigest(),
                               input_tokens=input_tokens, output_tokens=output_tokens, reasoning_tokens=reasoning_tokens,
                               cost=None, wall_time_s=time.monotonic() - started, events=(reply,))


class ScriptGateway:
    """A zero-token brain for variant screens: fixed locate calls, then every remaining node in order, then stop.

    locates: the locate args to replay (a source episode's first pass). After a failed node it gives up,
    so one episode tests one bound recipe; it never retries or varies.
    """

    MODEL = 'script'

    def __init__(self, locates):
        self.locates = [dict(a) for a in locates]

    def run(self, prompt):
        payload = json.loads(prompt)
        ran = [h for h in payload['history'] if 'call' in h and h['outcome'] and h['outcome'].get('executed')]
        nodes = [n for n in ('grasp', 'place') if n in payload['skill_pack']]
        if len(ran) < len(self.locates):
            reply = {'call': 'locate', 'args': self.locates[len(ran)], 'reason': 'script'}
        elif ran and not ran[-1]['outcome']['ok']:
            reply = {'stop': 'give_up', 'gap': 'perception' if ran[-1]['call'] == 'locate' else 'kernel',
                     'reason': 'script'}
        elif len(ran) - len(self.locates) < len(nodes):
            reply = {'call': nodes[len(ran) - len(self.locates)], 'args': {}, 'reason': 'script'}
        else:
            reply = {'stop': 'done', 'reason': 'script'}
        text = json.dumps(reply, sort_keys=True)
        return GatewayResponse(text=text, session_id='', message_id='script', model=self.MODEL,
                               prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                               response_sha256=hashlib.sha256(text.encode()).hexdigest(),
                               input_tokens=0, output_tokens=0, cost=None, wall_time_s=0.)


# A reply is read from the stdout of one gateway call; every key below is the whole schema.
CALL_KEYS, STOP_KEYS, RETRY_KEYS = {'call', 'args', 'reason'}, {'stop', 'gap', 'reason'}, {'retry', 'reason'}
VARY_KEYS = {'vary', 'parameters', 'hypothesis', 'expected'}
STOPS, GAPS, VARY_MAX_KEYS = ('done', 'give_up'), ('perception', 'geometry', 'contact', 'kernel'), 4
# What each recipe key does and the grasp stage it acts on (adaptive_reuse_grasp); bounds come from the frozen module.
PARAMETERS = {
    'clear_position_m': ('prepare/translate_clear: palm point [x, y, z] the hand moves to before the route; '
                         'also the start of orient_clear and the height of behind_high', 'prepare'),
    'preclose_fraction': ('prepare: fraction of the closed index/middle pose preshaped in free space', 'prepare'),
    'approach_mode': ('route shape: palm_backoff (come in along the palm direction from backoff_m behind), '
                      'pelvis_forward (come in along +x), top_down (descend from backoff_m above)', 'approach'),
    'forward_first': ('palm_backoff/pelvis_forward: insert forward_clear (move forward at clear height) before '
                      'behind_high', 'approach'),
    'backoff_m': ('distance of the pre-grasp point behind (or above, top_down) the palm goal', 'approach'),
    'preferred_yaw': ('first hand yaw (rad) preflight tries; later candidates follow a fixed list', 'preflight'),
    'offset_delta_m': ('shift [x, y, z] of the palm goal relative to the object, in the palm frame', 'preflight'),
    'palm_pitch_rad': ('palm pitch of the grasp pose', 'approach'),
    'palm_roll_rad': ('palm roll of the grasp pose', 'approach'),
    'cartesian_step_m': ('step length of every straight-line segment of the route', 'approach'),
    'approach_contact_stop_N': ('stop approach_open early when index and middle loads reach this (0 = off)',
                                'approach'),
    'grasp_feature': ('anchor the grasp on the body, a visible handle or a visible neck', 'preflight'),
    'handle_aware': ('drop yaws that put a visible handle under the palm side', 'preflight'),
    'auto_sphere_height': ('fruit: set grasp height from the estimated radius', 'locate'),
    'closure_mode': ('thumb_lead or synchronous finger closure', 'close_and_test'),
    'thumb_scale': ('scale of the thumb closing pose', 'close_and_test'),
    'thumb_distal_scale': ('scale of the distal thumb joint closing pose', 'close_and_test'),
    'thumb_pitch_rad': ('thumb base pitch of the closing pose', 'close_and_test'),
    'finger_scale': ('scale of the index/middle closing pose', 'close_and_test'),
    'finger_proximal_scale': ('extra scale of the proximal finger joints', 'close_and_test'),
    'finger_distal_scale': ('extra scale of the distal finger joints', 'close_and_test'),
    'index_scale': ('extra scale of the index finger', 'close_and_test'),
    'contact_stop_N': ('load at which closure stops pressing', 'close_and_test'),
    'hand_step_rad': ('hand joint increment per 0.2 s of closure', 'close_and_test'),
    'hand_lead_rad': ('how far commanded digits may lead their measured position', 'close_and_test'),
    'pressure_coordination': ('independent or coupled pressure control of thumb and fingers', 'close_and_test'),
    'hand_kp': ('left hand joint stiffness (bound at configuration)', 'configure'),
    'hand_kd': ('left hand joint damping (bound at configuration)', 'configure'),
    'lift_height_m': ('main_lift height above the grasp point', 'lift_and_hold'),
    'lift_retreat_m': ('main_lift backward (-x) retreat', 'lift_and_hold'),
    'lift_roll_delta_rad': ('palm roll change spread over the main lift', 'lift_and_hold'),
    'grip_hold': ('keep pressing during test_lift and main_lift', 'lift_and_hold'),
    'pressure_target_N': ('thumb and finger load the grip hold aims for', 'lift_and_hold'),
    'pressure_recovery_s': ('longest grip-hold correction per lift step', 'lift_and_hold'),
    'servo_period_s': ('duration of one grip-hold servo command', 'lift_and_hold'),
    'hold_seconds': ('hold duration at the top of the lift', 'lift_and_hold'),
    'active_wait_hold': ('servo the grip during waits instead of holding targets', 'lift_and_hold'),
    'load_compensation': ('compensate the held load in the arm targets', 'lift_and_hold'),
}
CARDS = {
    'locate': {
        'signature': 'locate(method, query?)',
        'applies': 'Find the task target on the table in the head RGB-D image and estimate where it stands. '
                   'Callable again before grasp, for instance with another method or query.',
        'pre': ['target_visible'], 'post': ['target_localized'],
        'args': {'method': {'colour': 'the registered colour rule on the target appearance',
                            'vlm': 'the vision-language locate primitive answering your query'},
                 'query': 'vlm only: a short English noun phrase naming the target, e.g. "the blue cup"'},
        'failures': ['PerceptionError (nothing found, ambiguous, fit or veto failed)', 'ActionFailure']},
    'grasp': {
        'signature': 'grasp()',
        'applies': 'Reach, close the left hand on the located target and lift it. Runs at most once per episode.',
        'pre': ['target_localized', 'hand_open'], 'post': ['holding_target', 'target_lifted'],
        'args': {}, 'failures': ['ActionFailure (unreachable, touch or lift failed, guard)']},
    'place': {
        'signature': 'place()',
        'applies': 'Carry the held target over the visible container, lower it, release and retreat. '
                   'Runs at most once per episode, after a successful grasp.',
        'pre': ['holding_target'], 'post': ['hand_empty', 'target_stable'],
        'args': {}, 'failures': ['ActionFailure (transfer, lower or release failed, guard)']},
}


def pack(chain, vlm, recipe=None):
    """P2 call cards of the template's nodes; without the K3 primitive locate has only the colour rule.

    recipe: {key: {'bounds', 'current'}} of the bound grasp recipe (kernel.variant_card) adds the
    grasp_variant card; meanings and stages come from PARAMETERS.
    """
    cards = {name: json.loads(json.dumps(CARDS[name])) for name in chain}
    if 'locate' in cards and not vlm:
        cards['locate']['signature'] = 'locate(method)'
        del cards['locate']['args']['method']['vlm'], cards['locate']['args']['query']
    if recipe:
        cards['grasp_variant'] = {
            'signature': 'vary(node="grasp", parameters={key: value})',
            'applies': 'After a failed grasp: bind grasp with some recipe parameters changed. The episode restarts '
                       'from the configured state (hand open, nothing located) with the variant bound; call locate '
                       'and grasp again. Same contract as grasp. Each variant is relative to the current values.',
            'pre': ['last executed node is a failed grasp', 'retries_remaining > 0'],
            'post': ['configured state with the variant bound'],
            'stages': {'prepare': 'raise_front -> raise_clear -> translate_clear (to clear_position_m)',
                       'preflight': 'plans a route for the first reachable yaw from preferred_yaw',
                       'approach palm_backoff/pelvis_forward': 'orient_clear -> forward_clear (if forward_first) '
                       '-> behind_high -> lower_behind -> approach_open',
                       'approach top_down': 'orient_clear -> above_target -> approach_open',
                       'close_and_test': 'close the hand, test the grip',
                       'lift_and_hold': 'test_lift 2 cm, main_lift, hold'},
            'frame': 'pelvis: x forward, y left, z up; the table top is near z = 0.17 m',
            'parameters': {k: {'meaning': PARAMETERS[k][0], 'stage': PARAMETERS[k][1], **v}
                           for k, v in sorted(recipe.items())},
            'limits': f'at most {VARY_MAX_KEYS} keys, each inside its bounds; guards cannot be changed',
            'failures': ['VARIANT_INVALID (outside the recipe envelope, refused without physics)']}
    return cards


def public_task(task):
    """The printed task: instruction, goals and roles named by category and colour word only."""
    roles = [{'role': r['role'], 'category': r['category'], 'colour': colour_name(r['appearance_rgba']),
              'target': r['target']} for r in task['roles']]
    return {'template': task['template_id'], 'instruction': task['instruction'],
            'initial_semantics': task['initial_semantics'], 'goals': task['goals'], 'roles': roles}


def prompt(task, cards, history, remaining, retries):
    """One decision request; deterministic in its inputs so the reply cache key is stable."""
    payload = {
        'request': 'next_node',
        'public_task': task,
        'skill_pack': cards,
        'history': [{**({'retry': True} if 'retry' in d['decision'] else
                        {'vary': 'grasp', 'parameters': d['decision']['parameters']} if 'vary' in d['decision'] else
                        {'call': d['decision'].get('call'), 'args': d['decision'].get('args')}),
                     'outcome': d['outcome'], **({'abandoned': True} if d.get('abandoned') else {})}
                    for d in history],
        'brain_calls_remaining': remaining,
        'retries_remaining': retries,
        'output_schema': ['{"call": "<node>", "args": {...}, "reason": "<one sentence>"}',
                          '{"retry": true, "reason": "<one sentence>"}',
                          *(['{"vary": "grasp", "parameters": {"<key>": <value>}, "hypothesis": "<cause of the '
                             'failure>", "expected": "<what the change should alter>"}'] if 'grasp_variant' in cards
                            else []),
                          '{"stop": "done", "reason": "<one sentence>"}',
                          '{"stop": "give_up", "gap": "perception" | "geometry" | "contact" | "kernel", '
                          '"reason": "<one sentence>"}'],
        'rules': ['Reply with strict JSON in one of the output_schema forms and nothing else.',
                  'Call only nodes in skill_pack, with the args its card lists.',
                  'The robot acts only through the nodes; an independent evaluator judges the task after you stop.',
                  'A guard stop (outcome.failure.guard) halts the robot; after it only '
                  f'{"retry, vary" if "grasp_variant" in cards else "retry"} or give_up are possible.',
                  'retry, after a failed node and while retries remain, restores the simulation to that node\'s entry '
                  'with the same grasp recipe; the failed attempt stays in history marked abandoned.',
                  'The simulation is deterministic: repeating the same calls from the same state repeats the result, '
                  'so after a retry change something, such as the locate method or query.',
                  *(['To change grasp_variant parameters answer vary directly, not retry: vary restarts the episode '
                     'from the configured state with the variant bound.',
                     'vary explains a failure: give the hypothesis and change only keys acting on the failed stage '
                     '(failure.message names the stage step); let failure.diagnosis (guard link, touched role, palm '
                     'position, planned route) and the locate estimate set the direction of the change.',
                     'Retries and variants share retries_remaining; do not repeat a variant already in history.']
                    if 'grasp_variant' in cards else []),
                  'Stop with done once you believe the goals hold, or give_up when no node can help, naming the gap: '
                  'perception (the target estimate is wrong or missing), geometry (route or reach), contact '
                  '(closing, holding or lifting), kernel (nothing the nodes or variants can change).'],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def decide(text, cards):
    """Brain reply -> decision; anything outside the schema raises AgentSchemaError, never guessed."""
    value = parse_json_reply(text)
    if 'vary' in value:
        recipe = cards.get('grasp_variant', {}).get('parameters', {})
        if (set(value) - VARY_KEYS or value['vary'] != 'grasp' or type(value.get('parameters')) is not dict
                or not 0 < len(value['parameters']) <= VARY_MAX_KEYS or set(value['parameters']) - set(recipe)
                or any(type(value.get(k)) is not str for k in ('hypothesis', 'expected'))):
            raise AgentSchemaError(f'vary reply must be {{"vary": "grasp", "parameters": 1-{VARY_MAX_KEYS} keys of '
                                   'grasp_variant, "hypothesis", "expected"}')
        return value
    if 'retry' in value:
        if set(value) - RETRY_KEYS or value['retry'] is not True:
            raise AgentSchemaError('retry reply must be {"retry": true, "reason"}')
        return value
    if 'stop' in value:
        if set(value) - STOP_KEYS or value['stop'] not in STOPS or (
                'gap' in value and (value['stop'] != 'give_up' or value['gap'] not in GAPS)):
            raise AgentSchemaError('stop reply must be {"stop": "done"|"give_up", "gap" (give_up only), "reason"}')
        return value
    if 'call' not in value or set(value) - CALL_KEYS or value['call'] not in cards:
        raise AgentSchemaError('call reply must name a node of the skill pack, with only args and reason')
    args = value.setdefault('args', {})
    if type(args) is not dict:
        raise AgentSchemaError('args must be an object')
    if value['call'] == 'locate':
        methods = tuple(cards['locate']['args']['method'])
        if args.get('method') not in methods or set(args) - {'method', 'query'}:
            raise AgentSchemaError(f'locate needs method in {methods}')
        if (args['method'] == 'vlm') != (type(args.get('query')) is str and bool(args['query'].strip())):
            raise AgentSchemaError('locate with vlm needs a non-empty query, colour takes none')
    elif args:
        raise AgentSchemaError(value['call'] + ' takes no args')
    if 'reason' in value and type(value['reason']) is not str:
        raise AgentSchemaError('reason must be text')
    return value


def lineage(history):
    """Executed node records of the current branch; earlier branches' records are abandoned."""
    return [d for d in history if d['outcome'] and d['outcome'].get('executed') and 'call' in d['decision']
            and not d.get('abandoned')]


def path(call, args, history, variant=None):
    """The executed calls from the episode start, under the bound variant, that this call would complete."""
    ran = lineage(history)
    return [*(ran[-1]['path'] if ran else [['vary', variant]] if variant else []), [call, args]]


def unmet(call, args, history, variant=None):
    """Precondition of a node on the brain's own executed records; None when it may run."""
    ran = lineage(history)
    if ran and (ran[-1]['outcome']['failure'] or {}).get('guard'):
        return 'PRECONDITION_UNMET: a guard stopped the robot; only retry, vary or give_up'
    if any(d.get('path') == path(call, args, history, variant) for d in history):
        return 'PRECONDITION_UNMET: these calls already ran from this state and would repeat their result'
    last = {d['decision']['call']: d['outcome']['ok'] for d in ran}
    if call == 'locate' and 'grasp' in last:
        return 'PRECONDITION_UNMET: locate only before grasp'
    if call == 'grasp' and ('grasp' in last or not last.get('locate')):
        return 'PRECONDITION_UNMET: grasp runs once, after a successful locate'
    if call == 'place' and ('place' in last or not last.get('grasp')):
        return 'PRECONDITION_UNMET: place runs once, after a successful grasp'
    return None


def retries(history):
    """Forks used: executed retries and variants."""
    return sum(('retry' in d['decision'] or 'vary' in d['decision']) and bool(d['outcome'] and d['outcome']['executed'])
               for d in history)


def unmet_retry(history, forks):
    """Retry needs a failed node in the current branch and an unused fork."""
    ran = lineage(history)
    if not ran or ran[-1]['outcome']['ok']:
        return 'PRECONDITION_UNMET: retry follows a failed node'
    if retries(history) >= forks:
        return 'PRECONDITION_UNMET: no retries remain'
    return None


def unmet_vary(parameters, history, forks):
    """A variant follows a failed grasp, uses a fork and is new in this episode.

    The grasp is the episode's latest executed one, abandoned or not: a retry that resumed before it may still vary.
    """
    grasps = [d for d in history if d['outcome'] and d['outcome'].get('executed') and d['decision'].get('call') == 'grasp']
    if not grasps or grasps[-1]['outcome']['ok']:
        return 'PRECONDITION_UNMET: vary follows a failed grasp'
    if retries(history) >= forks:
        return 'PRECONDITION_UNMET: no retries remain'
    if any('vary' in d['decision'] and d['decision']['parameters'] == parameters and d['outcome']['executed']
           for d in history):
        return 'PRECONDITION_UNMET: this variant already ran in this episode'
    return None


def _round(value):
    return round(value, 4) if type(value) is float else [_round(v) for v in value] if type(value) is list else value


def self_report(tool, ok, results, failure, phase, guard=None, diagnosis=None):
    """What the brain may see after a node: its own outputs and the robot's guard, never the evaluator-side truth.

    diagnosis (kernel.diagnose): the grasp's planned route and the guard's link, touched role and palm position.
    """
    report = {'executed': True, 'ok': ok, 'stages': [r['stage'] for r in results], 'phase': phase,
              'failure': failure and {'type': failure['type'], 'message': failure['message'][:300],
                                      **({'guard': guard} if guard else {})}}
    if diagnosis:
        report['diagnosis'] = diagnosis
    if tool == 'locate' and ok:
        estimate = results[-1]['result']
        report['estimate'] = {'bottom_position_pelvis_m': _round(estimate['cup_bottom_position_m']),
                              'source': estimate.get('source'), 'radius_m': _round(estimate.get('radius_estimate_m')),
                              **({'visible_center_pelvis_m': _round(estimate['visible_center_pelvis_m'])}
                                 if 'visible_center_pelvis_m' in estimate else {}),
                              **({'fit_rms_m': _round(estimate['fit_rms_m'])} if estimate.get('fit_rms_m') else {})}
        if 'vlm' in estimate:
            answer = estimate['vlm']['answer']
            report['estimate']['vlm'] = {'query': estimate['vlm']['query'],
                                         **{k: answer.get(k) for k in ('point_px', 'box_px', 'label', 'confidence')}}
    return report


class Brain:
    """The fixed brain model behind a gateway, with a reply cache keyed by identity and prompt.

    gateway: a provider with run(prompt); identity records the model, provider configuration
    and this module's VERSION as part of the run.
    """

    def __init__(self, gateway, identity):
        self.gateway, self.identity = gateway, identity

    def ask(self, text, cache, sources=(), replay=False):
        key = hashlib.sha256(json.dumps([self.identity, text], sort_keys=True).encode()).hexdigest()
        for folder in [cache, *sources]:
            if (Path(folder) / f'{key}.json').exists():
                return dict(json.loads((Path(folder) / f'{key}.json').read_text()), cached=True)
        if replay:
            raise ReplayCacheMiss(f'REPLAY_CACHE_MISS: brain prompt {key[:12]}')
        response = self.gateway.run(text)
        record = {'key': key, **response.to_dict(), 'events': list(response.events)}
        Path(cache).mkdir(parents=True, exist_ok=True)
        write_new(Path(cache) / f'{key}.json', record)
        return dict(record, cached=False)


def same_decisions(a, b):
    """Decision logs equal up to call history: cache use and timing differ between a source and its resume."""
    def plain(rows):
        return [{k: v for k, v in r.items() if k not in ('cached', 'wall_time_s')} for r in rows]
    return plain(a) == plain(b)
