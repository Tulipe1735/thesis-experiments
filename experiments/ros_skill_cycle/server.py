"""A cold-start one-goal Action server, loading hash-bound frozen skill code."""
import argparse
import importlib.util
import json
from pathlib import Path
import time
from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new, append_event
from .runtime_env import bootstrap, action_name


def load_frozen(bundle):
    manifest = read(bundle / 'manifest.json')
    for path, digest in manifest['bindings'].items():
        if sha(ROOT / path) != digest:
            raise ValueError('Frozen skill dependency changed: ' + path)
    for name, filename in [('public_check', 'public_check.py'), ('_frozen_execution', 'execution.py')]:
        fullname = 'experiments.ros_skill_cycle.' + name
        spec = importlib.util.spec_from_file_location(fullname, bundle / 'implementation' / filename)
        module = importlib.util.module_from_spec(spec)
        import sys
        sys.modules[fullname] = module
        spec.loader.exec_module(module)
    return module.Execution, manifest


def serve(args):
    bootstrap('experiments.ros_skill_cycle.server')
    import rclpy
    from rclpy.action import ActionServer, GoalResponse, CancelResponse
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from std_msgs.msg import String
    from thesis_skill_interfaces.action import ExecuteSkill
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    context = read(args.context)
    manifest = read(args.bundle / 'manifest.json')
    for path,digest in manifest['bindings'].items():
        if sha(ROOT/path)!=digest:
            raise ValueError('Frozen skill dependency changed: '+path)
    write_new(output / 'request_context.json', context)
    write_new(output / 'execution_binding.json', dict(bundle=relative(args.bundle.resolve()),
              manifest_sha256=sha(args.bundle / 'manifest.json'),
              source='frozen implementation loaded by file path', reference_trajectory_loaded=False,
              ros_action_type='thesis_skill_interfaces/action/ExecuteSkill'))
    rclpy.init()
    node = Node('agent_kernel', namespace='/thesis_skill')
    publisher = node.create_publisher(String, 'events', 100)
    completed = []
    busy = []

    def emit(event):
        append_event(output / 'memory.jsonl', event)
        publisher.publish(String(data=json.dumps(event)))

    def goal(request):
        accepted = (not busy and request.skill_id == manifest['skill_id'] and
                    request.skill_version == manifest['skill_version'] and
                    request.request_id == context['request_id'] and
                    json.loads(request.parameters_json) == dict(target='single_visible_cup_to_marked_tray'))
        emit(dict(event='goal_accepted' if accepted else 'goal_rejected', request_id=request.request_id))
        if accepted:
            busy.append(request.request_id)
        return GoalResponse.ACCEPT if accepted else GoalResponse.REJECT

    def execute(handle):
        def feedback(event):
            emit(event)
            handle.publish_feedback(ExecuteSkill.Feedback(**event))
        try:
            if context.get('non_physical_probe'):
                feedback(dict(stage='transport_probe', event='received', simulation_seconds=0.))
                public = dict(execution_status='COMPLETED', runtime_check='PASS', reason='non-physical Action probe')
                write_new(output / 'probe.json', dict(physics_steps=0, **public))
            else:
                Execution, _ = load_frozen(args.bundle.resolve())
                execution = Execution(context, manifest['policy'], output, feedback)
                public = execution.run()
            response = ExecuteSkill.Result(**public, evidence_id=relative(output))
            if public['runtime_check'] == 'PASS':
                handle.succeed()
            else:
                handle.abort()
            completed.append(time.monotonic())
            return response
        except Exception as error:
            write_new(output / 'infrastructure_failure.json', dict(type=type(error).__name__, message=str(error)))
            handle.abort()
            completed.append(time.monotonic())
            return ExecuteSkill.Result(execution_status='INFRASTRUCTURE_FAILURE', runtime_check='NOT_EVALUATED',
                                       reason=str(error), evidence_id=relative(output))

    endpoint=action_name(context['request_id'])
    action = ActionServer(node, ExecuteSkill, endpoint, execute_callback=execute, goal_callback=goal,
                          cancel_callback=lambda handle: CancelResponse.REJECT,
                          callback_group=ReentrantCallbackGroup())
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    write_new(output / 'ready.json', dict(node=node.get_fully_qualified_name(),
              action=endpoint, modules=['Skill', 'Memory', 'Composition'],
              cancellation='rejected; continuous mid-motion cancellation remains outside this experiment'))
    try:
        while not completed or time.monotonic()-completed[0] < 2.:
            executor.spin_once(timeout_sec=.1)
    finally:
        action.destroy()
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    serve(parser.parse_args())
