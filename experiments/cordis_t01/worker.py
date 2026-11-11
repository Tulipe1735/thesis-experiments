"""One persistent MuJoCo episode behind the Cordis script; zero model requests."""
import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

from experiments.t0_agent_v1.common import ROOT, REFERENCE, read, relative, sha, source_hashes, write_new, append_event
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot, mujoco, np
from experiments.t0_agent_v1.tray_verify import verify
from .skills import T01Skills

SOURCE = ROOT/'experiments/t0_agent_v1/tray_astra_20261025_002/episodes/2500_T01_astra'
REGISTRY = ROOT/'experiments/t0_agent_v1/skill_registry/T01_tray_place_repair_v1.json'


class SavedInitialRobot(PilotRobot):
    """Restore a saved integration state only during private episode initialization."""
    def __init__(self, *args, initial_state, **kwargs):
        self.saved_initial = initial_state
        super().__init__(*args, **kwargs)

    def _save_state(self, name):
        if name == 'initial_state':
            with np.load(self.saved_initial, allow_pickle=False) as state:
                mujoco.mj_setState(self.model, self.data, state['mujoco_integration_state'],
                                   mujoco.mjtState.mjSTATE_INTEGRATION)
                for attribute, key in [('targets', 'targets'), ('base_reference', 'base_reference'),
                                       ('kp', 'kp'), ('kd', 'kd'), ('limits', 'torque_limits')]:
                    setattr(self, attribute, state[key].copy())
            mujoco.mj_forward(self.model, self.data)
            self.cup_initial_z = float(self.data.xpos[self.cup_id, 2])
        super()._save_state(name)


class Session:
    def __init__(self, output):
        self.output = output
        self.folder = output/'episode'
        self.folder.mkdir(exist_ok=False)
        self.robot = self.port = self.skills = None
        self.error = self.result = None
        self.closed = False
        self.started = time.monotonic()
        self.calls = 0
        self.sources = source_hashes()
        self.sources.update({relative(path): sha(path) for path in Path(__file__).parent.glob('*.py')})
        registry = read(REGISTRY)
        ref = read(SOURCE/'model_reference.json')
        for item in registry['frozen_dependencies'].values():
            if sha(ROOT/item['path']) != item['sha256']:
                raise ValueError('Frozen T01 dependency changed: '+item['path'])
        for key, live in [('tray_tools', 'tray_tools.py'), ('independent_verifier', 'tray_verify.py')]:
            if sha(ROOT/'experiments/t0_agent_v1'/live) != registry['frozen_dependencies'][key]['sha256']:
                raise ValueError('Live T01 controller/evaluator differs from the validated version')
        if sha(ROOT/ref['path']) != ref['sha256'] or sha(SOURCE/'initial_state.npz') != ref['initial_state_sha256']:
            raise ValueError('Saved model or actual initial state changed')
        self.model_path = ROOT/ref['path']
        self.inputs = {relative(path): sha(path) for path in [REGISTRY, self.model_path,
                       SOURCE/'instance.json', SOURCE/'initial_state.npz', SOURCE/'model_reference.json',
                       REFERENCE/'initial_state.npz', REFERENCE/'runtime_context.json',
                       REFERENCE/'episode_memory.json', ROOT/'grasp_optimization/assets/robot_profile.json']}
        self.instance = read(SOURCE/'instance.json')
        write_new(output/'registration.json', dict(date='2026-10-28', status='registered_before_execution',
                  task='T01', boundary='simulation', split='known_development_initial', max_physical_episodes=1,
                  source_episode=relative(SOURCE), actual_initial_state_sha256=sha(SOURCE/'initial_state.npz'),
                  model_reference=ref, input_sha256=self.inputs, source_sha256=self.sources,
                  program=['inspect_scene', 'grasp_cup', 'place_in_tray', 'verify_task'],
                  controller_changes=False, evaluator_changes=False, model_requests=0,
                  scope='one previously validated initial; no randomized or unseen-asset evaluation'))
        write_new(self.folder/'instance.json', self.instance)
        write_new(self.folder/'run_config.json', dict(date='2026-10-28', task='T01', mode='scripted',
                  driver='Cordis skill composition', seed=self.instance['seed'], target_count=1,
                  split='known_development_initial', boundary='simulation', source_sha256=self.sources,
                  policy_reads_object_truth=False, spectator_used_by_policy=False,
                  model_requests=0, formal_skill_promotions=0))

    def call(self, tool, args):
        if type(args) is not dict or args or tool not in ('inspect_scene', 'grasp_cup', 'place_in_tray', 'verify_task'):
            raise ValueError('Unsupported tool or arguments')
        if tool == 'verify_task':
            return self.finalize()
        if self.error or self.closed:
            raise ValueError('Episode stopped; only independent verification is available')
        self.calls += 1
        try:
            if tool == 'inspect_scene':
                if self.robot is not None:
                    raise ValueError('Scene already initialized')
                self.robot = SavedInitialRobot(self.folder, self.instance, budget=180.,
                                              scene_path=self.model_path, initial_state=SOURCE/'initial_state.npz')
                with np.load(SOURCE/'initial_state.npz', allow_pickle=False) as old, \
                     np.load(self.folder/'initial_state.npz', allow_pickle=False) as new:
                    same = set(old.files) == set(new.files) and all(np.array_equal(old[k], new[k]) for k in old.files)
                write_new(self.output/'initial_state_audit.json', dict(all_arrays_exactly_equal=same,
                          source_sha256=sha(SOURCE/'initial_state.npz'),
                          actual_sha256=sha(self.folder/'initial_state.npz'), private_initialization_only=True))
                if not same:
                    raise ValueError('Actual initial state differs from registered state')
                self.port = CountedPort(self.robot)
                self.skills = T01Skills(self.port, self.folder)
                self.robot.advance(.75, 'initial_settling')
            elif self.skills is None:
                raise ValueError('Inspect scene first')
            result = getattr(self.skills, tool)()
            append_event(self.output/'worker-tools.jsonl', dict(tool=tool, result=result,
                         simulation_seconds=float(self.robot.data.time)))
            return result
        except Exception as exc:
            self.error = dict(type=type(exc).__name__, message=str(exc))
            if self.robot:
                self.robot.stop(str(exc)[:300])
            append_event(self.output/'worker-tools.jsonl', dict(tool=tool, error=self.error))
            raise

    def finalize(self):
        if self.result is not None:
            return self.result
        if not self.robot:
            raise ValueError('No physical episode initialized')
        if not self.closed:
            self.robot.finish()
            self.closed = True
        finished = self.skills is not None and self.skills.stage == 'placed'
        error = self.error or (None if finished else 'COMPOSITION_NOT_FINISHED')
        verdict = verify(self.folder, execution_error=error)
        unchanged = all(sha(ROOT/path) == digest for path, digest in {**self.sources, **self.inputs}.items())
        self.result = dict(task='T01', boundary='simulation', split='known_development_initial',
                          verified_success=verdict['verified_success'], independent_of_controller_result=True,
                          terminal_simultaneous_stable_s=verdict['terminal_simultaneous_stable_s'],
                          stage=self.skills.stage if self.skills else None,
                          episode=relative(self.folder), simulation_seconds=float(self.robot.data.time),
                          physical_episodes=1, cordis_tool_calls=self.calls+1,
                          controller_tool_steps=self.skills.tool_steps if self.skills else 0,
                          low_level_command_calls=self.port.command_calls if self.port else 0,
                          model_requests=0, vla_inference_calls=0, formal_skill_promotions=0,
                          source_unchanged=unchanged, execution_error=error,
                          verification_sha256=sha(self.folder/'independent_verification.json'),
                          wall_seconds=time.monotonic()-self.started)
        write_new(self.output/'result.json', self.result)
        return self.result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), 'w', encoding='utf-8', buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    session = None
    try:
        for line in sys.stdin:
            request = json.loads(line)
            try:
                if session is None:
                    session = Session(args.output)
                result = session.call(request['tool'], request.get('arguments', {}))
                response = dict(id=request['id'], ok=True, result=result)
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                response = dict(id=request['id'], ok=False, error=dict(type=type(exc).__name__, message=str(exc)))
            protocol.write(json.dumps(response, ensure_ascii=False, allow_nan=False)+'\n')
    finally:
        if session and session.robot and session.result is None:
            session.finalize()


if __name__ == '__main__':
    main()
