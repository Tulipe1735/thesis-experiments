"""Kernel K_v1: the existing tabletop stages regrouped into tools with boundary records.

Tools only regroup the unchanged AdaptiveGrasp stages and reuse the T03 hand-open,
placement-offset and finish leaves; no controller is rewritten. Truth checks at
tool boundaries are evaluator-side measurement and never reach a policy or agent.
Every stage boundary writes a checkpoint an episode of the same case can resume from.

K_v2 is K_v1 plus the K3 VLM locate primitive (harness/vlm_locate.py): a case with a
locate_query selects its target through the primitive instead of the colour rule; every
other stage is the same code. G0 never passes a query.

With brain set, execute is the Agent column (harness/agent_column.py): the brain picks the
next tool, the same stage code runs it, and checkpoints follow node boundaries. A guard stop
inside a node is the node's failure and goes back to the brain; agent_episode runs each retry
as a resume of the failed node's entry checkpoint, and each grasp variant as a new episode
with the variant bound at configuration.
"""
import gzip
import io
import json
import math
import pickle
import signal
import time
from pathlib import Path

import mujoco
import numpy as np

from . import agent_column as A
from . import hand_support as H
from . import t03_evaluator as E
from . import vlm_locate as V
from .agent import check_source
from .t03_placement import validate as placement_offset
from .t03_runtime import BudgetPlant, platter_from_camera
from experiments.t0_agent_v1.adaptive_reuse_grasp import (AdaptiveGrasp, AdaptivePort, BOUNDS, CATEGORY_KEYS,
                                                          parameters_for, validate_adaptive_recipe)
from experiments.t0_agent_v1.reuse_grasp import PROGRAM, ActionFailure, PerceptionError, ReuseGrasp
from experiments.t0_agent_v1.common import ROOT, write_new, relative
from experiments.t0_agent_v1.diversity_predicates import snapshot
from experiments.t0_agent_v1.tabletop_training_plant import independent_verify, set_left_hand_impedance
from experiments.t0_agent_v1.train_tp01 import body_packet
from experiments.grow_up_v2.isolation.worker import Worker

VERSION = 'K_v1-20261113'
VLM_VERSION = 'K_v2-20261116'
CHECKPOINT = 'kernel-checkpoint-v1-20261114'
INTEGRATION = mujoco.mjtState.mjSTATE_INTEGRATION
TOOLS = {
    'locate': ('locate',),
    'grasp': ('preflight', 'prepare', 'preflight', 'approach', 'close_and_test', 'lift_and_hold'),
    'place': ('transfer', 'lower', 'release_and_retreat'),
}
CHAINS = {'TP01': ('locate', 'grasp'), 'TP03': ('locate', 'grasp', 'place'), 'TP04': ('locate', 'grasp', 'place')}
# Evaluator-side thresholds used only to measure tools, never as a task verdict.
CHECKS = dict(locate_xy_error_m=.015, held_rise_m=.05, hand_contact_N=.1, nonhand_support_N=.1,
              rest_rise_m=.03, upright_tilt_deg=10.)
# Kernel leaf name -> component key of the frozen t03_base bundle.
LEAVES = {'hand_open': 'open_ref', 't03_adaptive_recipe': 'grasp_ref',
          't03_placement_target': 'placement_ref', 't03_post_release_finish': 'finish_ref'}


# Choices and vector limits the frozen adaptive_reuse_grasp._validate enforces, shown on the variant card.
CHOICES = {'closure_mode': ['thumb_lead', 'synchronous'], 'approach_mode': ['palm_backoff', 'pelvis_forward', 'top_down'],
           'grasp_feature': ['body', 'visible_handle', 'visible_neck'], 'pressure_coordination': ['independent', 'coupled']}
VECTORS = {'offset_delta_m': [[-.05, .05], [-.09, .05], [-.05, .08]], 'clear_position_m': [[-.07, .30], [.15, .42], [.23, .38]]}


def variant_card(parameters):
    """Every key a category override may change, with its bounds and the bound value."""
    def bounds(key):
        if key in BOUNDS:
            return list(BOUNDS[key])
        return CHOICES.get(key) or VECTORS.get(key) or [False, True]
    return {k: {'bounds': bounds(k), 'current': parameters[k]} for k in sorted(CATEGORY_KEYS)}


def bind_variant(binding, variant):
    """The bound recipe with a variant's keys overridden; the frozen validation raises ValueError outside the envelope."""
    merged = validate_adaptive_recipe({'program': list(PROGRAM), 'parameters': {**binding['parameters'], **variant},
                                       'by_category': {}})['parameters']
    return dict(binding, parameters=merged, variant=variant, base_parameters=binding['parameters'])


def diagnose(plant, controller, port, results, roles):
    """Robot-side records of a failed node the brain may read: the grasp's planned route and the guard's diagnosis."""
    out = {}
    if any(r['stage'] == 'preflight' for r in results) and controller.plan:
        out['route'] = {'selected_yaw_rad': round(controller.plan['selected_yaw_rad'], 4),
                        'waypoints': [[g[0], [round(v, 4) for v in g[1]]] for g in controller.plan['path']['goals']]}
    if plant.guard:
        failure = plant.first_failure
        detail = {'palm_position_pelvis_m': [round(v, 4) for v in port.state()['palms']['left']['position_m']]}
        if failure['forbidden_contacts']:
            bodies = failure['forbidden_contacts'][0]['bodies']
            robot = [b for b in bodies if b.startswith('left_')]
            other = [b for b in bodies if not b.startswith('left_')]
            detail['robot_link'] = robot[0] if robot else None
            detail['touched'] = (other[0] if other and other[0] in roles else 'robot' if not other
                                 else 'table_or_scene')
        if failure['speed_faults']:
            detail['speed_joints'] = [f['joint'] for f in failure['speed_faults']]
        out['guard_detail'] = detail
    return out


def verifier(template, hand_rule=None):
    """TP01 keeps the HeldLifted evaluator; placement uses the authorized fruit-bottom v2.

    hand_rule H.VERSION (K2) books palm-mesh contacts as hand; None is the v1 body-name rule.
    """
    if hand_rule:
        return H.verify(template, rule=hand_rule)
    return independent_verify if template == 'TP01' else E.verify


def recipe(kernel, category, leaf_reply=None):
    if category == 'fruit':
        # Same binding as the T03 parent: defaults plus the frozen recipe leaf, no category overrides.
        return parameters_for({'program': list(PROGRAM), 'parameters': leaf_reply['state']['parameters'],
                               'by_category': {}}, 'fruit')
    return parameters_for(kernel['object_recipe'], category)


def _pelvis(plant, world):
    p = plant.data.xpos[plant.pelvis_id]
    r = plant.data.xmat[plant.pelvis_id].reshape(3, 3)
    return r.T @ (np.asarray(world) - p)


def truth(plant, instance, target, start_z, estimate=None, hand_rule=None):
    """Evaluator-side state at a tool boundary; under the v2 hand rule held_v1 keeps the v1 reading."""
    take = {None: snapshot, H.VERSION: H.snapshot}[hand_rule]
    frame = take(plant.model, plant.data, instance, base=plant.base_reference)
    state = frame['objects'][target['name']]
    support = state['upward_support_N']
    hand = sum(v for k, v in support.items() if '_hand_' in k)
    other = sum(v for k, v in support.items() if '_hand_' not in k)
    w, x, y, z = state['quaternion_wxyz']
    tilt = math.degrees(math.acos(max(-1., min(1., 1 - 2 * (x * x + y * y)))))
    rise = state['position_m'][2] - start_z
    row = dict(rise_m=rise, hand_contact_N=state['hand_contact_N'], hand_support_N=hand,
               nonhand_support_N=other, tilt_deg=tilt, guard=plant.guard)
    row['held'] = bool(rise >= CHECKS['held_rise_m'] and state['hand_contact_N'] >= CHECKS['hand_contact_N']
                       and other < CHECKS['nonhand_support_N'])
    row['at_rest_upright'] = bool(abs(rise) <= CHECKS['rest_rise_m'] and state['hand_contact_N'] < CHECKS['hand_contact_N']
                                  and (target['asset']['kind'] == 'fruit' or tilt <= CHECKS['upright_tilt_deg']))
    if estimate is not None:
        error = np.asarray(estimate)[:2] - _pelvis(plant, state['position_m'])[:2]
        row['locate_xy_error_m'] = float(np.linalg.norm(error))
    if hand_rule:
        row['held_v1'] = truth(plant, instance, target, start_z)['held']
    return row


def tool_truth_ok(tool, row, verdict=None):
    if tool == 'locate':
        return row.get('locate_xy_error_m') is not None and row['locate_xy_error_m'] <= CHECKS['locate_xy_error_m']
    if tool == 'grasp':
        return row['held']
    return bool(verdict and verdict['goal_satisfied'])


def stages(template):
    """The template's chain flattened to (tool, stage) pairs; checkpoint k follows the k-th pair."""
    return [(tool, stage) for tool in CHAINS[template] for stage in TOOLS[tool]]


def starts_tool(chain, k):
    """Whether flattened stage k opens its tool; by position, since grasp runs preflight twice."""
    return k == 0 or chain[k - 1][0] != chain[k][0]


class _Freezer(pickle.Pickler):
    """Live episode objects become names and in-episode paths become relative, so a resume rebinds them."""
    def __init__(self, stream, links, out):
        super().__init__(stream, protocol=5)
        self.links, self.out = {id(v): k for k, v in links.items() if v is not None}, out

    def persistent_id(self, obj):
        if id(obj) in self.links:
            return 'link', self.links[id(obj)]
        if isinstance(obj, Path) and obj.is_relative_to(self.out):
            return 'out', str(obj.relative_to(self.out))
        if isinstance(obj, (mujoco.MjModel, mujoco.MjData, mujoco.Renderer)):
            raise TypeError('unlinked MuJoCo object in checkpoint: ' + type(obj).__name__)
        return None


class _Thawer(pickle.Unpickler):
    def __init__(self, stream, links, out):
        super().__init__(stream)
        self.links, self.out = links, out

    def persistent_load(self, pid):
        kind, value = pid
        return self.links[value] if kind == 'link' else self.out / value


def read_checkpoint(path):
    """Checkpoints are harness-written pickles; load only files from a run's own outputs."""
    with gzip.open(path, 'rb') as stream:
        return pickle.load(stream)


def _leaf(kernel, name):
    return kernel['sources'][kernel['leaves'][name]]


def _act_leaf(source, observation, task):
    with Worker(source, body_packet(), wall_timeout=5., cpu_seconds=120) as worker:
        return worker.act(observation, task), worker.security


class _VlmLocate(ReuseGrasp):
    """K_v2: with vlm set, ReuseGrasp.locate takes its estimate from the K3 primitive.

    Sits between AdaptiveGrasp and ReuseGrasp, so AdaptiveGrasp's handle, neck and offset
    steps run unchanged on the primitive's estimate. vlm: query, setup, cache, sources, replay.
    """
    vlm = None
    vlm_records = ()

    def save(self):
        super().save()
        if self.vlm_records:
            # Every model answer, including those whose lift was vetoed; rewritten like the base records.
            (self.folder / 'vlm_calls.json').write_text(json.dumps(self.vlm_records, indent=1))

    def locate(self, pixel_hint=None):
        if self.vlm is None:
            return super().locate(pixel_hint)
        if self.phase not in ('initial', 'ready'):
            raise ActionFailure('Relocalization not allowed during grasp')
        v, sensor = self.vlm, self.port.plant.rgbd()
        record = V.ask_frame(sensor, v['query'], v['setup'], v['cache'], v['sources'], v['replay'])
        self.vlm_records = [*self.vlm_records, record]
        self.save()
        # Whether the reply came from cache is call history, not part of the decision a resume must reproduce.
        decided = dict(record, reply={k: v for k, v in record['reply'].items() if k != 'cached'})
        estimate = dict(V.lift(sensor, record['answer'], self.public_task['target_category']), vlm=decided)
        if self.initial_visual_cup is not None and np.linalg.norm(
                np.asarray(estimate['cup_bottom_position_m']) - self.initial_visual_cup) > .04:
            raise PerceptionError('Selected target moved during preparation')
        self.initial_visual_cup = np.asarray(estimate['cup_bottom_position_m'])
        self.estimate = estimate
        self.estimates.append(estimate)
        self.save()
        return estimate


class KernelGrasp(AdaptiveGrasp, _VlmLocate):
    """Replaces only the optional raise_clear_of_tray segment with the wait-only finish leaf."""
    finish_source = None
    finish_record = None

    def linear(self, stage, position, duration):
        if stage != 'raise_clear_of_tray' or self.finish_source is None:
            return super().linear(stage, position, duration)
        plant = self.port.plant
        start, calls = float(plant.data.time), []
        with Worker(self.finish_source, body_packet(), wall_timeout=5., cpu_seconds=120) as worker:
            for _ in range(32):
                obs = plant.observation()
                reply = worker.act(obs, {'phase': 'post_release_finish', 'hold_s': 1.,
                                         'released_and_backward_retreat_executed': True})
                if type(reply) is not dict or set(reply) != {'action', 'state'}:
                    raise ValueError('finish requires exactly action/state')
                action = reply['action']
                calls.append({'time_s': obs['simulation_seconds'], 'reply': reply})
                if action.get('op') == 'done':
                    if plant.data.time - start < 1. - 1e-8:
                        raise ValueError('finish must physically dwell >=1s')
                    self.finish_record = {'calls': calls, 'dwell_s': plant.data.time - start}
                    return
                if action.get('op') == 'fail':
                    raise RuntimeError('FINISH_REJECTED:' + str(action.get('reason')))
                if set(action) != {'op', 'duration'} or action['op'] != 'wait':
                    raise ValueError('finish leaf may only wait, done or fail')
                if plant.data.time - start + action['duration'] > 3. + 1e-8:
                    raise RuntimeError('FINISH_3S_BUDGET')
                response = plant.dispatch(action)
                if response['status'] != 'EXECUTED':
                    raise RuntimeError('FINISH_WAIT:' + str(response))
        raise RuntimeError('FINISH_CALL_BUDGET')


def container_target(plant, instance, kernel, out):
    goal = next(o for o in instance['objects'] if o['asset']['kind'] in ('tray', 'platter'))
    center = platter_from_camera(plant, goal['asset'])
    observation = {'robot': plant.observation(), 'platter_center_pelvis_m': center.tolist(), 'max_fruit_radius_m': .041}
    reply, security = _act_leaf(_leaf(kernel, 't03_placement_target'), observation,
                                {'phase': 'placement_target', 'object_count': 1, 'hold_s': 1.})
    offset = placement_offset(reply)
    write_new(out / 'placement_invocation.json', {'container': goal['asset']['kind'], 'observation': observation,
                                                  'reply': reply, 'worker_security': security})
    return center + offset


def execute(case, out, kernel, caps, resume=None, stop=None, checkpoints=True, replay=False, brain=None, carry=(),
            variant=None):
    """One engineering-column episode: the fixed tool chain of the case's template.

    resume is a checkpoint file of an earlier episode of the same case. Configuration is
    rebuilt without stepping physics, the checkpoint is written back and the chain goes on
    at the next stage. The restored trace keeps the source prefix, so the unchanged
    evaluator judges prefix plus resumed suffix; such results are reported separately.
    stop ends the chain after that many flattened stages; checkpoints=False writes none.
    case['locate_query'] (K_v2 only) routes locate through the VLM primitive; replies are cached
    in out/vlm_cache, a resume also reads its source episode's cache, and replay=True turns a
    cache miss into ReplayCacheMiss instead of a model call.
    brain (agent_column.Brain) makes this an Agent-column episode: case['public_task'] is the
    task the brain reads, caps['brain_calls'] bounds its decisions, locate goes through the K3
    primitive only when the brain asks for it, and checkpoint k follows the k-th executed node.
    Replies are cached in out/brain_cache; replay=True covers them as it covers VLM replies.
    case['vlm_sources'] (with brain): further VLM caches the brain's locate calls read, e.g. a source episode's.
    carry (with brain): decision records of an abandoned branch, marked abandoned; with resume
    they follow the restored history. caps['forks'] bounds retries and variants together.
    variant (with brain, no resume): grasp recipe keys bound over the category's recipe.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    for name in LEAVES:
        check_source(_leaf(kernel, name))
    instance, template = case['instance'], case['template']
    target = next(o for o in instance['objects'] if o['is_target'])
    category = target['asset']['kind']
    public = {'target_category': category, 'nominal_rgba': target['asset']['rgba']}
    model = mujoco.MjModel.from_xml_path(str(case['folder'] / 'pantry_G1.xml'))
    # Scene XML lives in the run; the frozen fixture and initial state are read in place.
    plant = BudgetPlant(instance, case['source'], model, out, caps['simulation_s'])
    plant.command_count, plant.caps, plant.started = 0, caps, time.monotonic()
    start_z = snapshot(model, plant.data, instance, base=plant.base_reference)['objects'][target['name']]['position_m'][2]
    chain = stages(template)
    tools, states, security, calls, results, done, saved = [], [], {}, 0, [], 0, []
    error, stage, controller, port, binding = None, 'configure', None, None, None
    hand_rule = kernel.get('hand_rule')
    snap = read_checkpoint(resume) if resume else None
    if case.get('locate_query') and 'vlm' not in kernel:
        raise ValueError(kernel['version'] + ' has no VLM locate primitive')
    if brain and (case.get('locate_query') or stop):
        raise ValueError('the Agent column takes neither a harness locate query nor stop')
    if brain and not checkpoints:
        raise ValueError('the Agent column retries from checkpoints, so it always writes them')
    if carry and not brain or variant and (not brain or snap):
        raise ValueError('carried decisions and variants belong to Agent-column episodes; a variant binds at configuration')
    column = 'agent' if brain else 'engineering'
    # entries[i]: the checkpoint before nodes[i] and the decision count it holds; latest: the newest checkpoint.
    decisions, nodes, entries, latest, retry, vary = [dict(d, abandoned=True) for d in carry], [], [], None, None, None
    if snap and (snap['format'], snap['kernel'], snap.get('hand_rule'), snap.get('column', 'engineering'),
                 snap['task_id'], snap['template']) != (
            CHECKPOINT, kernel['version'], hand_rule, column, instance['id'], template):
        raise ValueError('checkpoint belongs to another kernel, hand rule, column, format or case')

    def links():
        return {'instance': instance, 'plant': plant, 'port': port, 'controller': controller, 'model': model,
                'data': plant.data, 'renderer': plant.renderer, 'kinematics': port.kinematics}

    def boundary(tool, visible_ok, results, failure=None):
        state = np.empty(mujoco.mj_stateSize(model, INTEGRATION))
        mujoco.mj_getState(model, plant.data, state, INTEGRATION)
        states.append(state)
        located = getattr(controller, 'estimate', None)
        estimate = located['cup_bottom_position_m'] if located else None
        tools.append({'tool': tool, 'visible_ok': visible_ok, 'failure': failure, 'stages': results,
                      'simulation_s': float(plant.data.time), 'state_index': len(states) - 1,
                      'truth': truth(plant, instance, target, start_z, estimate if tool == 'locate' else None,
                                     hand_rule)})

    def checkpoint():
        """MuJoCo integration state, plant/port/controller attributes and the chain's own records."""
        nonlocal latest
        if not checkpoints:
            return
        if brain:
            name = f'{done:02d}_' + (nodes[done - 1] if done else 'configured')
        else:
            name = f'{done:02d}_' + ('_'.join(chain[done - 1]) if done else 'configured')
        path = out / 'checkpoints' / (name + '.pkl.gz')
        path.parent.mkdir(exist_ok=True)
        state = np.empty(mujoco.mj_stateSize(model, INTEGRATION))
        mujoco.mj_getState(model, plant.data, state, INTEGRATION)
        objects = io.BytesIO()
        loop = dict(tools=tools, states=states, security=security, calls=calls, results=results)
        if brain:
            loop.update(decisions=decisions, nodes=nodes, entries=entries)
        _Freezer(objects, links(), out).dump({'plant': vars(plant), 'port': vars(port), 'controller': vars(controller),
                                              'loop': loop})
        header = {'format': CHECKPOINT, 'kernel': kernel['version'], 'task_id': instance['id'], 'template': template,
                  **({'hand_rule': hand_rule} if hand_rule else {}), **({'column': column} if brain else {}),
                  'done': done, 'next': None if brain else chain[done] if done < len(chain) else None,
                  'simulation_s': float(plant.data.time)}
        with gzip.open(path, 'xb', compresslevel=1) as stream:
            pickle.dump({**header, 'recipe_binding': binding, 'mujoco_state': state,
                         'objects': objects.getvalue()}, stream, protocol=5)
        saved.append({**header, 'path': relative(path)})
        latest = {'checkpoint': relative(path), 'decisions': len(decisions)}

    previous = signal.getsignal(signal.SIGALRM)

    def timeout(signum, frame):
        raise TimeoutError('EPISODE_WALL_BUDGET_EXCEEDED')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, caps['wall_s'])
    tool = None
    try:
        plant.head_image(out / 'initial_head.jpg')
        if snap:
            binding = snap['recipe_binding']
        else:
            leaf_reply = None
            if category == 'fruit':
                leaf_reply, security['recipe'] = _act_leaf(_leaf(kernel, 't03_adaptive_recipe'), plant.observation(),
                                                           {'phase': 'configure', 'target_category': 'fruit'})
                calls += 1
            binding = {'category': category, 'leaf_reply': leaf_reply, 'parameters': recipe(kernel, category, leaf_reply)}
            if variant:
                binding = bind_variant(binding, variant)
        params = binding['parameters']
        write_new(out / 'recipe_binding.json', binding)
        impedance = set_left_hand_impedance(plant.model, params['hand_kp'], params['hand_kd'])
        for name in impedance['joints']:
            i = plant.ai[name]
            plant.kp[i], plant.kd[i] = params['hand_kp'], params['hand_kd']
        write_new(out / 'left_hand_impedance.json', impedance)
        port = AdaptivePort(plant, params)
        folder = out / 'tools'
        folder.mkdir()
        controller = KernelGrasp(port, folder, public, params)
        controller.finish_source = _leaf(kernel, 't03_post_release_finish')
        if case.get('locate_query'):
            controller.vlm = {'query': case['locate_query'], 'setup': kernel['vlm'], 'cache': out / 'vlm_cache',
                              'sources': [], 'replay': replay}
        if snap:
            restored = _Thawer(io.BytesIO(snap['objects']), links(), out).load()
            if restored['plant']['initial_hash'] != plant.initial_hash:
                raise ValueError('checkpoint initial state differs from this case')
            mujoco.mj_setState(model, plant.data, snap['mujoco_state'], INTEGRATION)
            # Every dispatch ends with mj_forward, so derived data is a function of the state.
            mujoco.mj_forward(model, plant.data)
            for live, name in ((plant, 'plant'), (port, 'port'), (controller, 'controller')):
                live.__dict__.clear()
                live.__dict__.update(restored[name])
            if controller.vlm:
                # The thawed cache path already points into this episode; the source's stays readable.
                source = Path(resume).parents[1] / 'vlm_cache'
                controller.vlm = dict(controller.vlm, sources=[source, *controller.vlm['sources']], replay=replay)
            # The wall budget restarts; simulation and command budgets carry over from the source.
            plant.started = time.monotonic()
            tools, states, security, calls, results = (restored['loop'][k] for k in
                                                        ('tools', 'states', 'security', 'calls', 'results'))
            done = snap['done']
            if brain:
                decisions, nodes, entries = (restored['loop'][k] for k in ('decisions', 'nodes', 'entries'))
                latest = {'checkpoint': relative(Path(resume)), 'decisions': len(decisions)}
                decisions = [*decisions, *(dict(d, abandoned=True) for d in carry)]
                stage = TOOLS[nodes[-1]][-1] if done else 'hand_open'
            else:
                stage = chain[done - 1][1] if done else 'hand_open'
        else:
            stage = 'hand_open'
            with Worker(_leaf(kernel, 'hand_open'), body_packet(), wall_timeout=5., cpu_seconds=120) as worker:
                security['hand_open'] = worker.security
                for _ in range(60):
                    reply = worker.act(plant.observation(), {})
                    calls += 1
                    if reply['action']['op'] == 'done':
                        break
                    if plant.dispatch(reply['action'])['status'] != 'EXECUTED':
                        raise ActionFailure('HAND_OPEN_REJECTED')
                else:
                    raise RuntimeError('HAND_OPEN_BUDGET')
            port.invoke('wait', {'seconds': .6})
            checkpoint()

        def run_stage(tool, stage):
            if stage == 'transfer':
                controller.target = container_target(plant, instance, kernel, out)
                controller.tray = {'source': 'head_RGBD_visible_container'}
            if stage == 'release_and_retreat':
                port.hold_targets = None
            result = getattr(controller, stage)()
            results.append({'stage': stage, 'result': result, 'phase': controller.phase})
            if stage == 'preflight' and not result['reachable']:
                raise ActionFailure('APPROACH_PREFLIGHT_REJECTED')
            if plant.guard:
                raise ActionFailure('ROBOT_GUARD:' + plant.guard)
            if stage == TOOLS[tool][-1] and tool == 'grasp' and template == 'TP01' and controller.phase != 'complete':
                raise ActionFailure('HOLD_NOT_COMPLETE')

        if brain:
            cards = A.pack(CHAINS[template], 'vlm' in kernel,
                           variant_card(binding.get('base_parameters', binding['parameters'])))
            task = A.public_task(case['public_task'])
            roles = {r['role'] for r in case['public_task']['roles']}
            bound = binding.get('variant')
            sources = [Path(resume).parents[1] / 'brain_cache'] if resume else []
            while True:
                stage, tool = 'decide', None
                if len(decisions) >= caps['brain_calls']:
                    raise RuntimeError('BRAIN_CALL_BUDGET')
                reply = brain.ask(A.prompt(task, cards, decisions, caps['brain_calls'] - len(decisions),
                                           caps['forks'] - A.retries(decisions)), out / 'brain_cache', sources, replay)
                record = {'index': len(decisions), 'key': reply['key'], 'text': reply['text'], 'model': reply['model'],
                          'session_id': reply['session_id'], 'cached': reply['cached'],
                          'wall_time_s': reply['wall_time_s'], 'decision': None, 'outcome': None}
                decisions.append(record)
                record['decision'] = A.decide(reply['text'], cards)
                if 'stop' in record['decision']:
                    break
                if 'retry' in record['decision']:
                    blocked = A.unmet_retry(decisions[:-1], caps['forks'])
                    record['outcome'] = {'executed': not blocked, 'ok': not blocked,
                                         **({'failure': {'type': 'Precondition', 'message': blocked}} if blocked else {})}
                    if blocked:
                        continue
                    retry = entries[-1]
                    break
                if 'vary' in record['decision']:
                    blocked = A.unmet_vary(record['decision']['parameters'], decisions[:-1], caps['forks'])
                    if not blocked:
                        try:
                            bind_variant({'parameters': binding.get('base_parameters', binding['parameters'])},
                                         record['decision']['parameters'])
                        except ValueError as exc:
                            # The frozen recipe envelope refuses the values; fed back like a precondition, no physics.
                            blocked = 'VARIANT_INVALID: ' + str(exc)
                    record['outcome'] = {'executed': not blocked, 'ok': not blocked,
                                         **({'failure': {'type': 'Precondition', 'message': blocked}} if blocked else {})}
                    if blocked:
                        continue
                    vary = record['decision']['parameters']
                    break
                tool = record['decision']['call']
                blocked = A.unmet(tool, record['decision']['args'], decisions[:-1], bound)
                if blocked:
                    record['outcome'] = {'executed': False, 'ok': False, 'failure': {'type': 'Precondition',
                                                                                     'message': blocked}}
                    continue
                if tool == 'locate':
                    args = record['decision']['args']
                    controller.vlm = None if args['method'] == 'colour' else {
                        'query': args['query'], 'setup': kernel['vlm'], 'cache': out / 'vlm_cache',
                        'sources': [*([Path(resume).parents[1] / 'vlm_cache'] if resume else []),
                                    *case.get('vlm_sources', ())], 'replay': replay}
                results, failure = [], None
                entries.append(latest)
                record['path'] = A.path(tool, record['decision']['args'], decisions[:-1], bound)
                try:
                    for stage in TOOLS[tool]:
                        run_stage(tool, stage)
                except (ActionFailure, PerceptionError) as exc:
                    # A guard latches the plant: the node fails, and only a retry from a checkpoint moves the robot again.
                    failure = {'type': type(exc).__name__, 'message': str(exc)[:700], 'stage': stage, 'tool': tool}
                boundary(tool, failure is None, results, failure)
                record['outcome'] = A.self_report(tool, failure is None, results, failure, controller.phase, plant.guard,
                                                  failure and diagnose(plant, controller, port, results, roles))
                nodes.append(tool)
                done += 1
                checkpoint()
            tool = None
        for tool, stage in [] if brain else chain[done:stop]:
            if starts_tool(chain, done):
                results = []
            run_stage(tool, stage)
            if stage == TOOLS[tool][-1]:
                boundary(tool, True, results)
                tool = None
            done += 1
            checkpoint()
        tool = None
    except Exception as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)[:700], 'stage': stage, 'tool': tool}
        if tool is not None:
            boundary(tool, False, results, error)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if controller:
            controller.save()
            if controller.finish_record:
                write_new(out / 'finish_invocation.json', controller.finish_record)
        runtime = plant.save(error, {'stage': stage, 'phase': controller.phase if controller else None}, security, calls)
    with (out / 'boundary_states.npz').open('xb') as stream:
        np.savez_compressed(stream, state=np.asarray(states) if states else np.zeros((0, 0)))
    write_new(out / 'checkpoints.json', saved)
    verdict = verifier(template, hand_rule)(out, instance, model, initial_valid=case['ready'])
    write_new(out / 'verdict.json', verdict)
    if hand_rule:
        verdict_v1 = verifier(template)(out, instance, model, initial_valid=case['ready'])
        write_new(out / 'verdict_v1.json', verdict_v1)
    final = tools and tools[-1]
    if final and final['tool'] == 'place':
        final['truth_ok'] = tool_truth_ok('place', final['truth'], verdict)
    for row in tools:
        row.setdefault('truth_ok', tool_truth_ok(row['tool'], row['truth'], verdict))
    if final and not final['truth_ok']:
        final['recoverable'] = bool(final['truth']['at_rest_upright'] and not plant.guard)
    write_new(out / 'tools.json', tools)
    if brain:
        write_new(out / 'decisions.json', decisions)
    result = {'task_id': instance['id'], 'template': template, 'kernel': kernel['version'], 'success': verdict['verified_task_success'],
              'error': error, 'commands': plant.command_count, 'worker_calls': calls,
              'simulation_s': runtime['simulation_seconds'], 'wall_s': time.monotonic() - plant.started,
              'initial_hash': plant.initial_hash, 'evaluator': verdict.get('evaluator_version'),
              'verdict': relative(out / 'verdict.json'),
              **({'success_v1': verdict_v1['verified_task_success']} if hand_rule else {}),
              'resumed_from': snap and {'checkpoint': relative(Path(resume)), 'done': snap['done']},
              'stopped_after': list(chain[stop - 1]) if stop else None}
    if brain:
        last = decisions[-1]['decision'] if decisions else None
        result.update(column='agent', agent={
            'version': A.VERSION, 'identity': brain.identity, 'nodes': nodes, 'brain_calls': len(decisions),
            'cached_calls': sum(d['cached'] for d in decisions),
            'stop': 'retry' if retry else 'vary' if vary else last and last.get('stop'), 'retry': retry, 'vary': vary,
            'variant': binding and binding.get('variant'),
            'gap': last and last.get('gap'),
            'brain_wall_s': sum(d['wall_time_s'] for d in decisions if not d['cached'])})
    write_new(out / 'result.json', result)
    return result


def agent_episode(case, out, kernel, caps, brain):
    """One Agent-column episode with its retries and variants; each is a branch out/branches/NN.

    A retry resumes the failed node's entry checkpoint and carries the decisions made after it;
    a variant starts a new episode of the case with the variant bound and carries every earlier
    decision. Carried decisions are marked abandoned, so the brain sees every attempt. The first
    pass is out itself; the last branch holds the episode's outcome. retry.json lists the branches.
    A retry branch's simulation and command budgets carry over from its source; a variant's restart.
    """
    out = Path(out)
    result, folder, branches = execute(case, out, kernel, caps, brain=brain), out, []
    while result['agent']['stop'] in ('retry', 'vary'):
        fork, variant = result['agent']['retry'], result['agent']['vary']
        history = json.loads((folder / 'decisions.json').read_text())
        folder = out / 'branches' / f'{len(branches) + 1:02d}'
        if variant:
            branches.append({'folder': relative(folder), 'resumed': None, 'variant': variant})
            result = execute(case, folder, kernel, caps, brain=brain, carry=history, variant=variant)
        else:
            branches.append({'folder': relative(folder), 'resumed': fork['checkpoint'], 'variant': None})
            result = execute(case, folder, kernel, caps, resume=ROOT / fork['checkpoint'], brain=brain,
                             carry=history[fork['decisions']:])
    write_new(out / 'retry.json', {'branches': branches, 'success': result['success'], 'error': result['error'],
                                   'final': relative(folder / 'result.json')})
    return result
