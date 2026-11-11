"""One registered variation case; the unchanged T01 skills share one live state."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback

from experiments.t0_agent_v1.common import ROOT, REFERENCE, read, relative, sha, write_new, append_event
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot, np
from experiments.t0_agent_v1.tray_verify import verify
from .skills import T01Skills
from .worker import SavedInitialRobot


class Session:
    def __init__(self, output, suite, case_id):
        self.output, self.folder = output, output/'episode'
        self.folder.mkdir(exist_ok=False)
        self.registration = read(suite/'registration.json')
        self.case = next(c for c in self.registration['cases'] if c['id'] == case_id)
        self.instance = self.case['instance']
        self.model = self.registration['models'][self.case['model_key']]
        self.bindings = {**self.registration['source_sha256'], **self.registration['input_sha256']}
        self.bindings.update({relative(p):sha(p) for p in [suite/'registration.json', suite/'design.json',
            REFERENCE/'initial_state.npz', REFERENCE/'runtime_context.json', REFERENCE/'episode_memory.json',
            ROOT/'grasp_optimization/assets/robot_profile.json']})
        if not self.unchanged():
            raise ValueError('Registered source or model changed')
        self.robot = self.port = self.skills = None
        self.error = self.result = self.failed_tool = None
        self.closed = False
        self.calls = 0
        self.started = time.monotonic()
        write_new(output/'registration.json', dict(case=self.case, suite=relative(suite),
            model=self.model, bindings=self.bindings, boundary='simulation', max_episodes=1))
        write_new(self.folder/'instance.json', self.instance)
        write_new(self.folder/'run_config.json', dict(date='2026-10-28', task='T01', mode='scripted',
            driver='Cordis variation suite', seed=self.instance['seed'], target_count=1,
            split='known_control' if self.case['group']=='control' else 'development_extension',
            group=self.case['group'], case_id=case_id, boundary='simulation',
            policy_reads_object_truth=False, spectator_used_by_policy=False, model_requests=0))

    def unchanged(self):
        return all(sha(ROOT/p) == digest for p, digest in self.bindings.items())

    def initialize(self):
        kwargs = dict(scene_path=ROOT/self.model['path'], budget=self.registration['simulation_budget_s'])
        if self.case['initial_source']:
            self.robot = SavedInitialRobot(self.folder, self.instance,
                initial_state=ROOT/self.case['initial_source'], **kwargs)
        else:
            self.robot = PilotRobot(self.folder, self.instance, **kwargs)
        self.port, self.skills = CountedPort(self.robot), None
        self.skills = T01Skills(self.port, self.folder)
        # Qualification is private initialization evidence, never a tool input.
        tray = self.instance['tray']
        yaw = tray['yaw_rad']
        rotation = np.array([[np.cos(yaw), -np.sin(yaw)], [np.sin(yaw), np.cos(yaw)]])
        corners = np.asarray(tray['xy_m'])+np.array([[x,y] for x in (-1,1) for y in (-1,1)])*tray['half_size_xy_m'] @ rotation.T
        within = bool(np.all(np.abs(corners)+.001 < np.array([.66,.46])))
        write_new(self.output/'initial_state_audit.json', dict(
            actual_initial_state_sha256=sha(self.folder/'initial_state.npz'),
            tray_inside_declared_table_bounds=within, tray_corners_world_xy_m=corners.tolist(),
            same_as_control_source=(sha(self.folder/'initial_state.npz') == sha(ROOT/self.case['initial_source']))
                if self.case['initial_source'] else None,
            private_initialization_only=True, resampled=False))
        if not within:
            raise ValueError('Tray footprint outside registered table workspace')
        self.robot.advance(.75, 'initial_settling')

    def call(self, tool, args):
        if type(args) is not dict or args or tool not in self.registration['expected_program']:
            raise ValueError('Unsupported tool or arguments')
        if tool == 'verify_task':
            return self.finalize()
        if self.error or self.closed:
            raise ValueError('Episode stopped; independent verification remains available')
        self.calls += 1
        try:
            if tool == 'inspect_scene':
                if self.robot is not None:
                    raise ValueError('Scene already initialized')
                self.initialize()
            elif self.skills is None:
                raise ValueError('Inspect scene first')
            result = getattr(self.skills, tool)()
            append_event(self.output/'worker-tools.jsonl', dict(tool=tool, result=result,
                         simulation_seconds=float(self.robot.data.time)))
            return result
        except Exception as exc:
            self.error = dict(type=type(exc).__name__, message=str(exc))
            self.failed_tool = tool
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
        self.result = dict(case_id=self.case['id'], group=self.case['group'], task='T01', boundary='simulation',
            cup_asset=self.case['cup_asset'], tray_asset=self.case['tray_asset'],
            verified_success=verdict['verified_success'], initial_valid=verdict['initial_valid'],
            terminal_stable_s=verdict['terminal_simultaneous_stable_s'],
            stage=self.skills.stage if self.skills else None, failed_tool=self.failed_tool,
            episode=relative(self.folder), simulation_seconds=float(self.robot.data.time), physical_episodes=1,
            cordis_tool_calls=self.calls+1, controller_tool_steps=self.skills.tool_steps if self.skills else 0,
            low_level_command_calls=self.port.command_calls if self.port else 0,
            model_requests=0, formal_skill_promotions=0, source_unchanged=self.unchanged(), execution_error=error,
            actual_initial_state_sha256=sha(self.folder/'initial_state.npz'),
            trajectory_sha256=sha(self.folder/'trajectory.npz'),
            verification_sha256=sha(self.folder/'independent_verification.json'),
            wall_seconds=time.monotonic()-self.started)
        write_new(self.output/'result.json', self.result)
        return self.result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    args = parser.parse_args()
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), 'w', encoding='utf-8', buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    session = None
    try:
        for line in sys.stdin:
            request = json.loads(line)
            try:
                if session is None:
                    session = Session(args.output, args.suite, args.case_id)
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
