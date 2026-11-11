"""ROS 2 Agent Kernel node above a real lockstep ros2_control/MuJoCo adapter."""
import argparse
import json
from pathlib import Path
import time
import traceback

from experiments.t0_agent_v1.common import ROOT, REFERENCE, read, relative, sha, write_new, append_event
from experiments.t01_revision.native_runtime import NativeControl, bootstrap


def execute(args):
    # Delayed imports: middleware search paths must be set before process startup.
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    from experiments.cordis_t01.worker import SavedInitialRobot
    from experiments.cordis_t01.guard_worker import Session as BaseSession
    from experiments.t01_revision.candidate import RevisionSkills
    from experiments.t0_agent_v1.runtime import CountedPort
    from experiments.t0_agent_v1.tray_verify import verify

    prefix, suite, output = args.build.resolve(), args.suite.resolve(), args.output.resolve()
    original = read(suite / 'registration.json')
    policy = original['policies'][args.policy]
    case = next(c for c in original['cases'] if c['id'] == args.case_id)
    if not (prefix / 'build_result.json').exists():
        raise ValueError('Native control library must be built first')
    output.mkdir(parents=True, exist_ok=False)
    reference = suite / 'episodes' / (args.case_id + '__' + args.policy) / 'result.json'
    source_names = ['candidate.py', 'pipeline.py', 'native_reproduce.py', 'native_runtime.py',
                    'native_control.cpp', 'build_native.py']
    bindings = {**original['source_sha256'], **original['input_sha256']}
    bindings.update({relative(p): sha(p) for p in [suite / 'registration.json', reference,
                   prefix / 'lib/libthesis_kernel.so', prefix / 'native_control.cpp']})
    bindings.update({relative(Path(__file__).with_name(n)): sha(Path(__file__).with_name(n)) for n in source_names})
    write_new(output / 'registration.json', dict(date='2026-10-29', boundary='simulation',
        status='frozen_before_native_physics', runtime='ROS 2 Jazzy + ros2_control + MuJoCo',
        case=case, policy=policy, suite=relative(suite), expected_reference=relative(reference),
        bindings=bindings, physical_episodes=1, model_requests=0,
        upper_layer='ROS 2 node with Skill/Memory/Composition/Revision; in-process skill calls and ROS topic telemetry',
        lower_layer='each actuator reference passes through real CM read/update/write before mj_step',
        action_protocol='generic ExecuteSkill Action transport remains unimplemented',
        robot_description='interface-only URDF; original MuJoCo geometry, joint/torque guards and control law retained'))

    class Robot(SavedInitialRobot):
        def __init__(self, *pos, **kwargs):
            self.kernel = None
            super().__init__(*pos, **kwargs)
            self.kernel = NativeControl(prefix, self.names, float(self.model.opt.timestep))

        def _controller(self):
            super()._controller()
            self.data.ctrl[:] = self.kernel.step(self.data.qpos[self.qids], self.data.qvel[self.vids], self.data.ctrl)

    class Session(BaseSession):
        def __init__(self):
            self.condition = args.policy
            self.output, self.folder = output, output / 'episode'
            self.folder.mkdir(exist_ok=False)
            self.registration, self.case, self.instance = original, case, case['instance']
            self.model = original['models'][case['model_key']]
            self.bindings = bindings
            if not self.unchanged():
                raise ValueError('Frozen reference or source changed')
            self.robot = self.port = self.skills = None
            self.error = self.result = self.failed_tool = None
            self.closed, self.calls, self.started = False, 0, time.monotonic()
            write_new(self.folder / 'instance.json', self.instance)
            write_new(self.folder / 'run_config.json', dict(date='2026-10-29', task='T01',
                boundary='simulation', mode='scripted', driver='ROS 2 Agent Kernel / ros2_control',
                seed=self.instance['seed'], ros2_execution=True, model_requests=0,
                policy_reads_object_truth=False, split='consumed_initial_migration_regression'))

        def initialize(self):
            self.robot = Robot(self.folder, self.instance, initial_state=ROOT / case['initial_source'],
                scene_path=ROOT / self.model['path'], budget=original['simulation_budget_s'])
            self.port = CountedPort(self.robot)
            self.skills = RevisionSkills(self.port, self.folder, gain=policy.get('gain', .5))
            self.robot.advance(.75, 'initial_settling')

        def finalize(self):
            if self.result is not None:
                return self.result
            if not self.robot:
                raise ValueError('No native physical episode initialized')
            if not self.closed:
                self.robot.finish()
                self.closed = True
            error = self.error or (None if self.skills.stage == 'placed' else 'COMPOSITION_NOT_FINISHED')
            verdict = verify(self.folder, execution_error=error)
            expected = read(reference)
            trajectory = sha(self.folder / 'trajectory.npz')
            kernel = self.robot.kernel.summary()
            self.result = dict(case_id=args.case_id, condition=args.policy, boundary='simulation',
                verified_success=verdict['verified_success'], initial_valid=verdict['initial_valid'],
                terminal_stable_s=verdict['terminal_simultaneous_stable_s'],
                execution_error=error, failed_tool=self.failed_tool, stage=self.skills.stage,
                physical_episodes=1, ros2_execution=True, kernel=kernel,
                high_level_tool_calls=self.calls + 1, low_level_command_calls=self.port.command_calls,
                simulation_seconds=float(self.robot.data.time), model_requests=0,
                initial_sha256=sha(self.folder / 'initial_state.npz'), trajectory_sha256=trajectory,
                verdict_sha256=sha(self.folder / 'independent_verification.json'),
                same_reference_initial=sha(self.folder / 'initial_state.npz') == expected['initial_sha256'],
                same_reference_trajectory=trajectory == expected['trajectory_sha256'],
                same_reference_success=verdict['verified_success'] == expected['verified_success'],
                source_unchanged=self.unchanged(), episode=relative(self.folder),
                wall_seconds=time.monotonic() - self.started)
            write_new(output / 'result.json', self.result)
            return self.result

    # These four module roles deliberately share one ROS 2 node/process.
    class Revision:
        def __init__(self):
            self.registry = read(ROOT / 'experiments/t0_agent_v1/skill_registry/T01_visual_handoff_damped_v1.json')
            if not self.registry['formal_promotion']:
                raise ValueError('Validated revision is required')
            policy_path = ROOT / self.registry['artifact']['policy']
            if sha(policy_path) != self.registry['artifact']['policy_sha256']:
                raise ValueError('Validated policy changed')
            frozen_policy = read(policy_path)
            if policy['guard'] and policy['gain'] != frozen_policy['gain']:
                raise ValueError('Revision differs from the validated frozen artifact')

    class Memory:
        def __init__(self, node):
            self.node = node
            self.publisher = node.create_publisher(String, 'skill_events', 10)
            self.received = []
            self.subscriber = node.create_subscription(String, 'skill_events',
                                                       lambda msg: self.received.append(msg.data), 10)

        def record(self, event):
            append_event(output / 'agent_memory.jsonl', event)
            self.publisher.publish(String(data=json.dumps(event, ensure_ascii=False)))
            rclpy.spin_once(self.node, timeout_sec=0.)

    class Skill:
        def __init__(self, session, memory):
            self.session, self.memory = session, memory

        def call(self, tool):
            self.memory.record(dict(event='skill_started', tool=tool))
            result = self.session.call(tool, {})
            # Telemetry uses public tool status; private verdict stays in the evidence files.
            self.memory.record(dict(event='skill_completed', tool=tool, status=result.get('status', 'returned')))
            return result

    class Composition:
        def run(self, skill):
            for tool in ['inspect_scene', 'grasp_cup', 'transfer_to_tray']:
                skill.call(tool)
            if policy['guard']:
                result = skill.call('inspect_alignment')
                if result['status'] == 'CORRECT':
                    skill.call('correct_alignment')
            skill.call('release_in_tray')
            return skill.call('verify_task')

    rclpy.init()
    node = Node('agent_kernel', namespace='/thesis_t01')
    revision, memory, session = Revision(), Memory(node), Session()
    skill, composition = Skill(session, memory), Composition()
    try:
        result = composition.run(skill)
        for _ in range(5):
            rclpy.spin_once(node, timeout_sec=.02)
        write_new(output / 'agent_kernel.json', dict(modules=['Skill', 'Memory', 'Composition', 'Revision'],
            ros_node=node.get_fully_qualified_name(), telemetry_received=len(memory.received),
            revision=revision.registry['skill_id'], model_requests=0,
            interface_boundary='in-process skill calls; ROS 2 telemetry and embedded CM; generic Skill Action pending'))
        print(json.dumps(result), flush=True)
        if not all(result[k] for k in ['verified_success', 'same_reference_initial', 'same_reference_trajectory',
                                      'same_reference_success', 'source_unchanged']):
            raise RuntimeError('Native reproduction failed; evidence retained')
    except Exception:
        traceback.print_exc()
        if session.robot and session.result is None:
            session.finalize()
        raise
    finally:
        if session.robot and session.robot.kernel:
            session.robot.kernel.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--policy', choices=['nominal', 'candidate'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    bootstrap(args.build.resolve(), 'experiments.t01_revision.native_reproduce')
    execute(args)
