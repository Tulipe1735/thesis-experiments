"""Kernel K_v1: the existing tabletop stages regrouped into tools with boundary records.

Tools only regroup the unchanged AdaptiveGrasp stages and reuse the T03 hand-open,
placement-offset and finish leaves; no controller is rewritten. Truth checks at
tool boundaries are evaluator-side measurement and never reach a policy or agent.
Every stage boundary writes a checkpoint an episode of the same case can resume from.
"""
import gzip
import io
import math
import pickle
import signal
import time
from pathlib import Path

import mujoco
import numpy as np

from . import t03_evaluator as E
from .agent import check_source
from .t03_placement import validate as placement_offset
from .t03_runtime import BudgetPlant, platter_from_camera
from experiments.t0_agent_v1.adaptive_reuse_grasp import AdaptiveGrasp, AdaptivePort, parameters_for
from experiments.t0_agent_v1.reuse_grasp import PROGRAM, ActionFailure
from experiments.t0_agent_v1.common import write_new, relative
from experiments.t0_agent_v1.diversity_predicates import snapshot
from experiments.t0_agent_v1.tabletop_training_plant import independent_verify, set_left_hand_impedance
from experiments.t0_agent_v1.train_tp01 import body_packet
from experiments.grow_up_v2.isolation.worker import Worker

VERSION = 'K_v1-20261113'
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


def verifier(template):
    """TP01 keeps the HeldLifted evaluator; placement uses the authorized fruit-bottom v2."""
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


def truth(plant, instance, target, start_z, estimate=None):
    """Evaluator-side state at a tool boundary."""
    frame = snapshot(plant.model, plant.data, instance, base=plant.base_reference)
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


class KernelGrasp(AdaptiveGrasp):
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


def execute(case, out, kernel, caps, resume=None, stop=None, checkpoints=True):
    """One engineering-column episode: the fixed tool chain of the case's template.

    resume is a checkpoint file of an earlier episode of the same case. Configuration is
    rebuilt without stepping physics, the checkpoint is written back and the chain goes on
    at the next stage. The restored trace keeps the source prefix, so the unchanged
    evaluator judges prefix plus resumed suffix; such results are reported separately.
    stop ends the chain after that many flattened stages; checkpoints=False writes none.
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
    snap = read_checkpoint(resume) if resume else None
    if snap and (snap['format'], snap['kernel'], snap['task_id'], snap['template']) != (
            CHECKPOINT, VERSION, instance['id'], template):
        raise ValueError('checkpoint belongs to another kernel, format or case')

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
                      'truth': truth(plant, instance, target, start_z, estimate if tool == 'locate' else None)})

    def checkpoint():
        """MuJoCo integration state, plant/port/controller attributes and the chain's own records."""
        if not checkpoints:
            return
        name = f'{done:02d}_' + ('_'.join(chain[done - 1]) if done else 'configured')
        path = out / 'checkpoints' / (name + '.pkl.gz')
        path.parent.mkdir(exist_ok=True)
        state = np.empty(mujoco.mj_stateSize(model, INTEGRATION))
        mujoco.mj_getState(model, plant.data, state, INTEGRATION)
        objects = io.BytesIO()
        _Freezer(objects, links(), out).dump({'plant': vars(plant), 'port': vars(port), 'controller': vars(controller),
                                              'loop': dict(tools=tools, states=states, security=security,
                                                           calls=calls, results=results)})
        header = {'format': CHECKPOINT, 'kernel': VERSION, 'task_id': instance['id'], 'template': template,
                  'done': done, 'next': chain[done] if done < len(chain) else None,
                  'simulation_s': float(plant.data.time)}
        with gzip.open(path, 'xb', compresslevel=1) as stream:
            pickle.dump({**header, 'recipe_binding': binding, 'mujoco_state': state,
                         'objects': objects.getvalue()}, stream, protocol=5)
        saved.append({**header, 'path': relative(path)})

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
            # The wall budget restarts; simulation and command budgets carry over from the source.
            plant.started = time.monotonic()
            tools, states, security, calls, results = (restored['loop'][k] for k in
                                                        ('tools', 'states', 'security', 'calls', 'results'))
            done = snap['done']
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
        for tool, stage in chain[done:stop]:
            if starts_tool(chain, done):
                results = []
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
            if stage == TOOLS[tool][-1]:
                if tool == 'grasp' and template == 'TP01' and controller.phase != 'complete':
                    raise ActionFailure('HOLD_NOT_COMPLETE')
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
    verdict = verifier(template)(out, instance, model, initial_valid=case['ready'])
    write_new(out / 'verdict.json', verdict)
    final = tools and tools[-1]
    if final and final['tool'] == 'place':
        final['truth_ok'] = tool_truth_ok('place', final['truth'], verdict)
    for row in tools:
        row.setdefault('truth_ok', tool_truth_ok(row['tool'], row['truth'], verdict))
    if final and not final['truth_ok']:
        final['recoverable'] = bool(final['truth']['at_rest_upright'] and not plant.guard)
    write_new(out / 'tools.json', tools)
    result = {'task_id': instance['id'], 'template': template, 'kernel': VERSION, 'success': verdict['verified_task_success'],
              'error': error, 'commands': plant.command_count, 'worker_calls': calls,
              'simulation_s': runtime['simulation_seconds'], 'wall_s': time.monotonic() - plant.started,
              'initial_hash': plant.initial_hash, 'evaluator': verdict.get('evaluator_version'),
              'verdict': relative(out / 'verdict.json'),
              'resumed_from': snap and {'checkpoint': relative(Path(resume)), 'done': snap['done']},
              'stopped_after': list(chain[stop - 1]) if stop else None}
    write_new(out / 'result.json', result)
    return result
