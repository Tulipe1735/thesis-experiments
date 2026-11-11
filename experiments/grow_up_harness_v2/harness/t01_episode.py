"""Saved T01 holdout poses and the existing Cartesian interface in a Worker."""
import copy
import json
import time
from pathlib import Path

import mujoco
import numpy as np

from . import grow_loop as L, tp01
from .agent import AgentSchemaError, check_source
from .dense_eval import score_case
from experiments.cordis_t01.worker import SOURCE
from experiments.cordis_t01.skills import T01Skills
from experiments.t0_agent_v1.runtime import CountedPort
from experiments.t0_agent_v1.tray_verify import verify
from rgbd_cup import PerceptionError
from run_direct_grasp import ActionFailure

PHASE_ADAPTER = '''
def act(observation, task, state):
    phase = task['phase']
    if phase == 'plan':
        params = grasp_parameters(observation)
        commands = plan(observation)
    else:
        params = task['params']
        if phase == 'lift':
            commands = lift(observation, params)
        elif phase == 'correct':
            commands = correct(observation, params)
        elif phase == 'release':
            commands = release(observation, params)
        else:
            raise ValueError('unknown phase')
    return {'action': {'op': 'done'}, 'commands': commands, 'params': params}
'''

JOINT_PHASE_INTERFACE = '''Do not write act(). Define these five top-level functions:
grasp_parameters(observation) -> dict;
plan(observation), lift(observation, params), correct(observation, params),
release(observation, params) -> list of commands.
The harness wraps these functions in act() and refreshes observation before each phase.
Each phase returns at most 256 commands; correct may run up to 6 times until it returns [].
Commands may ONLY be:
{"op":"set_joints","targets":{"left_joint_name":float},"duration":float}
{"op":"wait","duration":float}.
Targets contain only observed LEFT arm/hand joint names, never waist or right joints.
Duration is 0.02..0.20 seconds on a 0.002-second grid. At most 14 targets per command.
Increment from the preceding target <=0.03 rad arm / 0.05 rad hand;
1.5*abs(increment)/duration <=0.30 rad/s arm / 0.50 rad/s hand.
Respect observation.joints[name].range_rad. For a sequence, update a local target cursor.
Return [] to end a phase. No move, move_linear, joints, finish, done or fail commands.
The supplied procedure describes Cartesian motions and waist use from a different interface;
implement only motions expressible through the left arm/hand joint outlet above.
'''


def phase_source(source):
    import ast
    tree = ast.parse(source)
    functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    required = {'grasp_parameters', 'plan', 'lift', 'correct', 'release'}
    if not required <= functions or 'act' in functions:
        raise ValueError('T01 source must define grasp_parameters/plan/lift/correct/release, without act')
    wrapped = source + '\n' + PHASE_ADAPTER
    check_source(wrapped)
    return wrapped


def generate(seed, count, radius_m, *, output):
    if not 0 <= radius_m <= .02 or count < 1:
        raise ValueError('T01 requires 0..20 mm planar jitter and count >= 1')
    reference = json.loads((SOURCE / 'model_reference.json').read_text())
    model = mujoco.MjModel.from_binary_path(str(tp01.ROOT / reference['path']))
    with np.load(SOURCE / 'initial_state.npz', allow_pickle=False) as saved:
        original = {k: saved[k].copy() for k in saved.files}
    instance = json.loads((SOURCE / 'instance.json').read_text())
    rng = np.random.default_rng(seed)
    folder = output / 'sampled_initials'
    folder.mkdir(exist_ok=False)
    tasks = []
    for i in range(count):
        data = mujoco.MjData(model)
        mujoco.mj_setState(model, data, original['mujoco_integration_state'], mujoco.mjtState.mjSTATE_INTEGRATION)
        adr = model.jnt_qposadr[model.joint('task_cup_free').id]
        offset = rng.uniform(-radius_m, radius_m, 2)
        data.qpos[adr:adr + 2] += offset
        sample = copy.deepcopy(instance)
        sample['seed'] = seed * 1000 + i
        sample['cup_table_xy_m'] = data.qpos[adr:adr + 2].tolist()
        state = np.empty(mujoco.mj_stateSize(model, mujoco.mjtState.mjSTATE_INTEGRATION))
        mujoco.mj_getState(model, data, state, mujoco.mjtState.mjSTATE_INTEGRATION)
        path = folder / f't01_{seed}_{i:03d}.npz'
        with path.open('xb') as handle:
            np.savez_compressed(handle, **{**original, 'mujoco_integration_state': state})
        tasks.append({'task_id': f't01_{seed}_{i:03d}', 'public': {'object_count': 1, 'hold_s': 1.},
                      'private': {'initial_source': str(path.relative_to(tp01.ROOT)),
                                  'initial_sha256': L.tp01._sha256_file(path), 'instance': sample,
                                  'sampled_xy_offset_m': offset.tolist(),
                                  'object_free_qpos': data.qpos[adr:adr + 7].tolist()}})
    return {'generator': 't01_saved_cup_planar_v1', 'seed': seed, 'count': count, 'radius_m': radius_m,
            'outcome_filter': False, 'tasks': tasks,
            'plant': {'path': reference['path'], 'sha256': tp01._sha256_file(tp01.ROOT / reference['path'])},
            'source_initial': {'path': str((SOURCE / 'initial_state.npz').relative_to(tp01.ROOT)),
                               'sha256': tp01._sha256_file(SOURCE / 'initial_state.npz')}}


def validate_commands(commands, joints):
    from calibration import t01_agent_pilot as pilot
    if not isinstance(commands, list) or len(commands) > 256:
        raise ValueError('phase commands must be a list of at most 256 commands')
    if any(c.get('op') == 'finish' for c in commands[:-1]):
        raise ValueError('finish must be last in its phase')
    for start in range(0, len(commands), pilot.ACTIONS_PER_TURN):
        pilot.parse_commands({'actions': commands[start:start + pilot.ACTIONS_PER_TURN], 'reason': 'worker phase'},
                             pilot.action_schema(True), joints)
    return commands


def validate_joint_commands(commands, joints):
    if not isinstance(commands, list) or len(commands) > 256:
        raise ValueError('phase commands must be a list of at most 256 commands')
    cursor = {n: dict(v) for n, v in joints.items() if n.startswith('left_')}
    for command in commands:
        if not isinstance(command, dict) or command.get('op') not in ('set_joints', 'wait'):
            raise ValueError('T01 phase commands must be set_joints or wait')
        L.check_action(command, {'joints': cursor})
        for name, value in command.get('targets', {}).items():
            lo, hi = cursor[name]['range_rad']
            if not lo <= value <= hi:
                raise ValueError('joint target outside range_rad')
            cursor[name]['target'] = value
    return commands


def execute_joint_command(port, command, robot, tray_floor_m, session):
    from calibration import t01_agent_pilot as pilot
    joints = {n: {**v, 'range_rad': pilot.t01_motion.joint_bounds(robot, n)['range_rad']}
              for n, v in port.state()['joints'].items() if n.startswith('left_') and pilot.controllable(n)}
    validate_joint_commands([command], joints)
    if command['op'] == 'set_joints':
        translated = {'op': 'joints', 'seconds': command['duration'],
                      'targets': [{'joint': n, 'radians': v} for n, v in command['targets'].items()]}
    else:
        translated = {'op': 'wait', 'seconds': command['duration']}
    return pilot.execute(port, translated, robot, tray_floor_m, session)


def dry_run(source, observation, *, joint_commands=False):
    calls, security = 0, {}
    try:
        with L.Worker(phase_source(source), {}, cpu_seconds=30, wall_timeout=2.) as worker:
            security = worker.security
            calls += 1
            result = worker.act(observation, {'phase': 'plan'})
            validate = validate_joint_commands if joint_commands else validate_commands
            validate(result['commands'], observation['joints'])
            params = result['params']
            if not isinstance(params, dict):
                raise ValueError('grasp_parameters(observation) must return dict')
            for phase in ('lift', 'correct', 'release'):
                calls += 1
                result = worker.act(observation, {'phase': phase, 'params': params})
                validate(result['commands'], observation['joints'])
    except (ValueError, KeyError, TypeError, SyntaxError, L.WorkerError, AgentSchemaError) as error:
        return {'passed': False, 'error': f'{type(error).__name__}: {error}',
                'worker_calls': calls, 'security': security}
    return {'passed': True, 'security': security, 'phases_checked': 4, 'worker_calls': calls}


class Episode:
    def __init__(self, output, generated, caps, task):
        self.output, self.generated, self.caps, self.task = output, generated, caps, task

    def run(self, *, mode, source=None):
        from calibration import t01_agent_pilot as pilot
        from calibration.t02_execution import execute_batch
        out = self.output
        out.mkdir(parents=True, exist_ok=False)
        episode = out / 'episode'
        episode.mkdir()
        L.write_new(episode / 'instance.json', self.task['private']['instance'])
        robot = tp01.TickRecordedRobot(episode, self.task['private']['instance'],
                                      budget=self.caps['simulation_s'],
                                      scene_path=tp01.ROOT / self.generated['plant']['path'],
                                      initial_state=tp01.ROOT / self.task['private']['initial_source'])
        port = CountedPort(robot)
        started, calls, error, worker = time.monotonic(), 0, None, None
        initial_path = tp01.ROOT / self.task['private']['initial_source']
        with np.load(initial_path, allow_pickle=False) as a, np.load(episode / 'initial_state.npz', allow_pickle=False) as b:
            same = set(a.files) == set(b.files) and all(np.array_equal(a[k], b[k]) for k in a.files)
        if not same:
            raise ValueError('restored T01 initial arrays differ from registered sample')
        L.write_new(out / 'initial_audit.json', {'all_arrays_equal': same, 'registered_sha256': tp01._sha256_file(initial_path)})
        try:
            robot.advance(.75, 'initial_settling')
            observation = pilot.observe(port, robot)
            L.write_new(out / 'public_initial.json', observation)
            if mode == 'wait':
                robot.advance(2., 'negative_wait')
            elif mode == 'engineering':
                skills = T01Skills(port, episode)
                skills.inspect_scene()
                skills.grasp_cup()
                skills.place_in_tray()
            elif mode in ('worker', 'joint_worker'):
                worker = L.Worker(phase_source(source), {}, cpu_seconds=30, wall_timeout=2.)
                L.write_new(out / 'worker_security.json', worker.security)
                params, session = None, {}
                for phase in ('plan', 'lift', 'correct', 'release'):
                    for iteration in range(6 if phase == 'correct' else 1):
                        if time.monotonic() - started > self.caps['wall_s']:
                            raise ValueError('LOCAL_WALL_CAP')
                        observation = pilot.observe(port, robot)
                        result = worker.act(observation, {'phase': phase, 'params': params})
                        calls += 1
                        if phase == 'plan':
                            params = result['params']
                        validate = validate_joint_commands if mode == 'joint_worker' else validate_commands
                        commands = validate(result['commands'], observation['joints'])
                        if not commands:
                            break
                        def execute(command):
                            if port.command_calls >= self.caps['commands']:
                                raise ValueError('LOCAL_COMMAND_CAP')
                            if mode == 'joint_worker':
                                return execute_joint_command(port, command, robot, observation['tray_floor_center_m'], session)
                            return pilot.execute(port, command, robot, observation['tray_floor_center_m'], session)
                        def log(row):
                            from experiments.t0_agent_v1.common import append_event
                            append_event(out / 'actions.jsonl', row)
                        rejection = execute_batch(commands, execute, phase=phase, log=log)
                        if rejection:
                            raise ValueError(json.dumps(rejection))
                        if robot.guard:
                            raise ValueError('GUARD: ' + str(robot.guard))
            else:
                raise ValueError(mode)
        except (ValueError, KeyError, TypeError, L.WorkerError, AgentSchemaError, PerceptionError, ActionFailure) as exc:
            error = {'type': type(exc).__name__, 'message': str(exc)[:600]}
        finally:
            if worker is not None:
                worker.close()
            environment = robot.finish()
        verdict = verify(episode, execution_error=error)
        L.write_new(out / 'verdict.json', verdict)
        dense = score_case(episode / 'independent_verification.json')
        L.write_new(out / 'dense_score.json', dense)
        result = {'mode': mode, 'success': verdict['verified_success'], 'error': error,
                  'commands': port.command_calls, 'worker_calls': calls,
                  'simulation_seconds': environment['simulation_seconds'], 'wall_seconds': time.monotonic() - started,
                  'score': dense['dense_score'], 'source_sha256': L.sha_text(source) if source else None}
        L.write_new(out / 'result.json', result)
        return result
