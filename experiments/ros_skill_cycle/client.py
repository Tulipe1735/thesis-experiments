"""Independent ROS Action caller; receives only runtime evidence, never private verdicts."""
import argparse
import json
import time
from pathlib import Path
from experiments.t0_agent_v1.common import read, write_new
from .runtime_env import bootstrap, action_name


def main(args):
    bootstrap('experiments.ros_skill_cycle.client')
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from thesis_skill_interfaces.action import ExecuteSkill
    rclpy.init()
    node = Node('composition_client', namespace='/thesis_skill')
    client = ActionClient(node, ExecuteSkill, action_name(args.request_id))
    deadline=time.monotonic()+30.
    while not client.server_is_ready() and time.monotonic()<deadline:
        rclpy.spin_once(node,timeout_sec=.1)
    if not client.server_is_ready():
        raise RuntimeError('ROS Skill Action server unavailable')
    manifest = read(args.bundle / 'manifest.json')
    feedback = []
    goal = ExecuteSkill.Goal(skill_id=manifest['skill_id'], skill_version=manifest['skill_version'],
              request_id=args.request_id,
              parameters_json=json.dumps(dict(target='single_visible_cup_to_marked_tray')))
    future = client.send_goal_async(goal, feedback_callback=lambda msg: feedback.append(dict(
        stage=msg.feedback.stage, event=msg.feedback.event, simulation_seconds=msg.feedback.simulation_seconds)))
    rclpy.spin_until_future_complete(node, future, timeout_sec=40.)
    handle = future.result()
    if handle is None or not handle.accepted:
        raise RuntimeError('Action goal rejected or timed out')
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=420.)
    result = result_future.result()
    if result is None:
        raise RuntimeError('Action result timeout; no automatic retry')
    payload = dict(accepted=True, action_terminal_status=result.status,
                  execution_status=result.result.execution_status, runtime_check=result.result.runtime_check,
                  reason=result.result.reason, evidence_id=result.result.evidence_id, feedback=feedback,
                  feedback_count=len(feedback), private_physical_verdict_received=False,
                  independent_process=True)
    write_new(args.output, payload)
    print(json.dumps({k:v for k,v in payload.items() if k != 'feedback'}), flush=True)
    client.destroy()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
