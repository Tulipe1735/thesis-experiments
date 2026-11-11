"""Bounded Astra/engineering pilot: observe, act, independently verify, retain evidence."""
import argparse
import base64
import json
import shutil
import sys
import time
from pathlib import Path

from .common import PACKAGE, ROOT, append_event, read, relative, sha, source_hashes, write_new
from .runtime import CountedPort, PilotRobot
from .skills import CupTools, validate_action, validate_program
from .verify import verify
sys.path.insert(0, str(ROOT / 'grasp_optimization'))
from astra_gateway import AstraGateway, GatewayError

CONTRACT = '''你是 MuJoCo G1 + 双 Dex3-1 茶水间开发试验的高层执行者。
任务来自任务树叶节点；本轮只用一个空杯。pick_cup=抓起并稳持；place_cup=为一名茶歇参与者摆放一个空杯。
place_cup 要先抓起并稳持，再按公开的 target_offset_initial_pelvis_m 将杯移至指定相对位置，放下、释放、撤手和放稳。
坐标：米，骨盆 x前 y左 z上；负x是向机器人。偏移是任务指令，不是隐藏物体位置。
只读当前头部图像、RGB-D工程估计、本体与匿名触觉、工具反馈。独立验收在结束后进行，不可自己宣称任务成功。
本轮明确提供既有工程 IK、抓杯和取放工具，包括既有工程参数经验；不是裸模型控制，也不是从零学会抓杯。
每次只返回 JSON {"note":"简短中文行动说明","action":{"tool":"名称","arguments":{}}}，不要输出代码。
locate(): initial/ready 阶段头部RGB-D定位白杯；不读仿真杯位置。
prepare(): initial→ready，工程安全接近准备并重新视觉定位。
preflight(): ready阶段检查工程抓取路径；返回 reachable 和可选腰部调节建议。
adjust_reach(): 仅在 preflight 给出建议时调整，随后必须再次 preflight。
approach(): ready且路径通过后接近；返回 approached。
close_and_test(): approached→tested，匿名触觉检查并试提。
lift_and_hold(): tested→complete，抬升12.5cm并稳持；这只是抓杯动作完成。
transfer(): 仅 place_cup 的 complete→transferred，持杯移动到公开相对目标上方。
lower(): transferred→lowered，按视觉估计的桌面高度下放。
release_and_retreat(): lowered→placed，打开手指、撤手并等待放稳。
observe(): 获取最新观测。finish(): pick_cup在complete，place_cup在placed后结束，等待独立验收。
stop(reason="..."): 不确定或失败时停止。除此之外各工具不接受参数。任何工具失败即终止，不绕开保护。
run_candidate(): 仅当公开任务里给出了 candidate_program 且当前处于 initial 时，可执行这个已有工程组合候选。
候选的每一步仍检查工具前置条件和反馈，遇错即停；它不是正式skill。你可选择复用，也可逐步调用原工具。
模型推理时仿真暂停；这不证明实时执行能力。只能依据已返回的反馈决定下一工具。
既往 memory 只是有适用条件的开发候选；不能用它替代当前观测与工具前置条件。
'''


def parse_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(text)


def retrieve_memory(suite, task, dependencies):
    matches = []
    for path in sorted((suite / 'episodes').glob('*/memory.json')):
        item = read(path)
        if (item['task'] == task and item['split'] == 'development'
                and item['dependencies'] == dependencies and item.get('agent_memory')):
            matches.append(dict(source=relative(path), sha256=sha(path),
                                status=item['status'], memory=item['agent_memory']))
    return matches[-3:]


def scripted_action(controller):
    name = {'initial': 'prepare', 'ready': 'preflight', 'approached': 'close_and_test',
            'tested': 'lift_and_hold', 'complete': 'transfer', 'transferred': 'lower',
            'lowered': 'release_and_retreat', 'placed': 'finish'}[controller.phase]
    if controller.phase == 'initial' and controller.estimate is None:
        name = 'locate'
    if controller.phase == 'complete' and controller.task == 'pick_cup':
        name = 'finish'
    if controller.phase == 'ready' and controller.plan:
        name = 'approach' if controller.plan['selected_yaw_rad'] is not None else 'adjust_reach'
    return dict(note='确定性工程调度；不计作 Astra 决策', action=dict(tool=name, arguments={}))


def observation_payload(observation, phase, feedback):
    state = observation['body_state']
    return dict(observation_id=observation['observation_id'], phase=phase, feedback=feedback,
                simulation_seconds=state['simulation_seconds'], palms=state['palms'],
                approximate_contact_load_N=state['approximate_contact_load_N'],
                controller=state['controller'], resolution_wh=observation['resolution_wh'])


def run(suite, seed, mode, gateway_source=None, candidate_path=None):
    suite = Path(suite)
    registration = read(suite / 'registration.json')
    instances = read(suite / 'instances.json')
    instance = next((row for row in instances if row['seed'] == seed), None)
    if instance is None:
        raise ValueError('Seed not preregistered')
    episodes = suite / 'episodes'
    episodes.mkdir(exist_ok=True)
    if len(list(episodes.iterdir())) >= registration['max_physical_episodes']:
        raise ValueError('Registered pilot episode budget exhausted')
    if list(episodes.glob(f'{seed}_*')):
        raise ValueError('This registered instance already has an attempt; do not overwrite or silently repeat')
    if sha(ROOT / registration['source_model']) != registration['source_model_sha256']:
        raise ValueError('Registered physical model changed')
    folder = episodes / f'{seed}_{mode}'
    folder.mkdir(exist_ok=False)
    sources = source_hashes()
    dependencies = {key: value for key, value in sources.items()
                    if key.endswith(('skills.py', 'vision_grasp.py', 'vision_grasp_v2.py',
                                     'pantry_robot.py', 'arm_planner.py', 'rgbd_cup.py'))}
    # Small source snapshots only. Models, trajectories and raw frames are never copied.
    (folder / 'sources').mkdir()
    for path in PACKAGE.glob('*.py'):
        shutil.copyfile(path, folder / 'sources' / path.name)
    write_new(folder / 'instance.json', instance)
    memory = retrieve_memory(suite, instance['task'], dependencies)
    write_new(folder / 'retrieved_memory.json', memory)
    candidate = read(candidate_path) if candidate_path else None
    if candidate is not None or mode == 'candidate':
        if (not candidate or candidate['status'] != 'engineering_composition_candidate'
                or candidate['dependencies'] != dependencies or candidate['task'] != instance['task']):
            raise ValueError('Candidate identity/dependency mismatch')
        candidate_program = validate_program(candidate['program'])
        write_new(folder / 'candidate_reference.json', dict(path=relative(candidate_path), sha256=sha(candidate_path)))
    else:
        candidate_program = None
    program = candidate_program if mode == 'candidate' else None
    client = None
    if mode == 'astra':
        if not gateway_source:
            raise ValueError('Existing authorized Astra gateway configuration required')
        client = AstraGateway.from_example(gateway_source)
    config = dict(date='2026-10-25', mode=mode, model=client.model if client else None,
                  source_sha256=sources, dependencies=dependencies, task=instance['task'],
                  seed=seed, boundary='simulation', split='development',
                  engineered_tools=True, autonomous_joint_skill_synthesis=False,
                  policy_reads_object_truth=False, spectator_used_by_policy=False,
                  model_latency='simulation_paused', max_decision_calls=registration['max_decision_calls'],
                  max_reflection_calls=1, memory_candidates_retrieved=len(memory))
    write_new(folder / 'run_config.json', config)
    (folder / 'agent_contract.txt').write_text(CONTRACT, encoding='utf-8')
    robot = controller = None
    decisions, request_count, reflection_count, finished, error = [], 0, 0, False, None
    candidate_calls = []
    wall_start = time.monotonic()
    try:
        robot = PilotRobot(folder, instance, registration['simulation_budget_s'])
        port = CountedPort(robot)
        controller = CupTools(port, folder, instance['task'], instance['target_offset_initial_pelvis_m'])
        robot.advance(.75, 'initial_settling')
        task_context = dict(task=instance['leaf_label'], task_id=instance['task'], participants=1,
                            target_offset_initial_pelvis_m=instance['target_offset_initial_pelvis_m'],
                            memory_candidates=memory, engineering_reference=controller.memory_reference,
                            candidate_program=candidate_program)
        write_new(folder / 'public_task.json', task_context)
        messages = [dict(role='system', content=CONTRACT),
                    dict(role='user', content=json.dumps(task_context, ensure_ascii=False))]
        feedback = None
        for step in range(registration['max_decision_calls']):
            if finished or robot.guard or robot.stop_reason:
                break
            observation = port.observe()
            public = observation_payload(observation, controller.phase, feedback)
            rgb_path = Path(observation['head_rgb_path'])
            append_event(folder / 'model_input_manifest.jsonl', dict(step=step, public=public,
                         head_image_path=relative(rgb_path), head_image_sha256=sha(rgb_path),
                         simulator_truth_included=False, spectator_included=False, sent_to_model=mode == 'astra'))
            if client:
                encoded = base64.b64encode(rgb_path.read_bytes()).decode('ascii')
                messages.append(dict(role='user', content=[dict(type='text', text=json.dumps(public, ensure_ascii=False)),
                                dict(type='image_url', image_url=dict(url='data:image/jpeg;base64,' + encoded, detail='high'))]))
                request_count += 1
                append_event(folder / 'requests.jsonl', dict(kind='decision', index=request_count, state='started'))
                response, latency = client.chat(messages, max_tokens=1000)
                text = response['choices'][0]['message'].get('content') or ''
                append_event(folder / 'requests.jsonl', dict(kind='decision', index=request_count,
                             state='returned', wall_seconds=latency, usage=response.get('usage'), response=text))
                messages.append(dict(role='assistant', content=text))
                plan = parse_json(text)
            elif program is not None:
                if step >= len(program):
                    raise ValueError('Candidate ended without finish')
                plan = dict(note='执行 Astra 产生的工程组合候选', action=dict(tool=program[step], arguments={}))
            else:
                plan = scripted_action(controller)
            if type(plan) is not dict or set(plan) != {'note', 'action'} or not isinstance(plan['note'], str):
                raise ValueError('Invalid decision schema')
            name, args = validate_action(plan['action'])
            row = dict(id=f'decision_{step + 1:02}', phase_before=controller.phase, plan=plan)
            decisions.append(row)
            print('PILOT_TOOL', step + 1, name, plan['note'], flush=True)
            if name == 'stop':
                feedback = robot.stop(args['reason'])
            elif name == 'finish':
                required = 'complete' if instance['task'] == 'pick_cup' else 'placed'
                if controller.phase != required:
                    raise ValueError('Premature finish')
                finished = True
                feedback = dict(status='ENDED_FOR_INDEPENDENT_VERIFICATION')
            elif name == 'run_candidate':
                if not candidate_program or controller.phase != 'initial':
                    raise ValueError('No compatible candidate available at this phase')
                for operation in candidate_program:
                    if robot.guard or robot.stop_reason:
                        raise ValueError('Candidate interrupted by protection')
                    if operation == 'finish':
                        required = 'complete' if instance['task'] == 'pick_cup' else 'placed'
                        if controller.phase != required:
                            raise ValueError('Candidate attempted premature finish')
                        finished = True
                        result = dict(status='ENDED_FOR_INDEPENDENT_VERIFICATION')
                    else:
                        result = getattr(controller, operation)()
                    item = dict(tool=operation, result=result, phase_after=controller.phase)
                    candidate_calls.append(item)
                    append_event(folder / 'candidate_execution.jsonl', item)
                feedback = dict(status='CANDIDATE_EXECUTED_AWAIT_VERIFICATION', tools=candidate_calls)
            elif name == 'observe':
                feedback = dict(status='OBSERVED', body_state=port.state())
            else:
                feedback = getattr(controller, name)(**args)
            row.update(result=feedback, phase_after=controller.phase)
            write_new(folder / f'{row["id"]}.json', row)
        if not finished and not robot.guard and not robot.stop_reason:
            robot.stop('DECISION_BUDGET_EXHAUSTED')
    except Exception as exc:
        # Gateway's implementation redacts its credential before raising.
        error = dict(type=type(exc).__name__, message=str(exc))
        if robot:
            robot.stop(type(exc).__name__ + ': ' + str(exc)[:250])
        if isinstance(exc, GatewayError):
            append_event(folder / 'requests.jsonl', dict(kind='decision', index=request_count,
                         state='failed', status=exc.status, wall_seconds=exc.seconds))
        print('PILOT_ERROR', error, flush=True)
    finally:
        if controller:
            controller.save()
        if robot:
            robot.finish()
        write_new(folder / 'decisions.json', decisions)
    if robot:
        verification = verify(folder, execution_error=error or (None if finished else 'EXECUTION_NOT_FINISHED'))
    else:
        verification = dict(verified_success=False, grasp_passed=False, placement_passed=False,
                            execution_error=error, physical_initialization_failed=True)
        write_new(folder / 'independent_verification.json', verification)
    memory_record = dict(task=instance['task'], split='development', dependencies=dependencies,
                         source_episode=relative(folder), verified_success=verification['verified_success'],
                         status='observed_development_record_not_validated_memory', agent_memory=None)
    # No truth coordinates/contact identities pass to the model, including reflection.
    if client and error is None:
        reflection_count = 1
        reflection_input = dict(task=instance['task'], decisions=decisions,
                                verification={k: verification[k] for k in ('verified_success', 'grasp_passed', 'placement_passed')})
        write_new(folder / 'reflection_input.json', reflection_input)
        prompt = ('依据已结束仿真提炼中文经验。只返回JSON，字段为 lessons(字符串数组), applicability(字符串), '
                  'evidence_ids(使用 decision_XX 或 verification), program(工具名数组)。program是下次可执行的工程工具组合，'
                  '仅用locate/prepare/preflight/approach/close_and_test/lift_and_hold/transfer/lower/'
                  'release_and_retreat/finish这些工具，无参数，不含run_candidate或任何递归调用，最后必须是finish。'
                  '不要把工程工具组合称为从零学会或正式skill，不断言跨种子泛化。失败时保留具体限制。')
        try:
            append_event(folder / 'requests.jsonl', dict(kind='reflection', index=1, state='started'))
            response, latency = client.chat([dict(role='system', content=prompt),
                dict(role='user', content=json.dumps(reflection_input, ensure_ascii=False))], max_tokens=1700)
            text = response['choices'][0]['message'].get('content') or ''
            append_event(folder / 'requests.jsonl', dict(kind='reflection', index=1, state='returned',
                         wall_seconds=latency, usage=response.get('usage'), response=text))
            reflection = parse_json(text)
            if set(reflection) != {'lessons', 'applicability', 'evidence_ids', 'program'}:
                raise ValueError('Invalid reflection fields')
            if (not isinstance(reflection['lessons'], list) or not reflection['lessons']
                    or not all(isinstance(x, str) for x in reflection['lessons'])
                    or not isinstance(reflection['applicability'], str)
                    or not isinstance(reflection['evidence_ids'], list) or not reflection['evidence_ids']
                    or not set(reflection['evidence_ids']) <= {x['id'] for x in decisions} | {'verification'}):
                raise ValueError('Ungrounded memory or invalid schema')
            validate_program(reflection['program'])
            memory_record.update(status='agent_authored_memory_candidate',
                                 agent_memory={key: reflection[key] for key in ('lessons', 'applicability', 'evidence_ids')})
            write_new(folder / 'skill_candidate.json', dict(status='engineering_composition_candidate',
                      task=instance['task'], program=reflection['program'], dependencies=dependencies,
                      author='Astra', source_episode=relative(folder), formal_promotion=False,
                      verified_on_source_episode=False,
                      note='Composed after episode; the candidate program itself needs a separate execution.'))
        except Exception as exc:
            memory_record['reflection_error'] = dict(type=type(exc).__name__, message=str(exc))
            append_event(folder / 'requests.jsonl', dict(kind='reflection', index=1, state='failed', error=type(exc).__name__))
    write_new(folder / 'memory.json', memory_record)
    result = dict(episode=relative(folder), task=instance['task'], seed=seed, mode=mode,
                  verified_success=verification['verified_success'], grasp_passed=verification['grasp_passed'],
                  placement_passed=verification['placement_passed'], final_phase=controller.phase if controller else None,
                  actual_model_requests=request_count + reflection_count, decision_requests=request_count,
                  reflection_requests=reflection_count, high_level_tool_calls=len(decisions),
                  low_level_command_calls=port.command_calls if robot and controller else 0,
                  candidate_tool_calls=len(candidate_calls),
                  candidate_invocations=sum(x['plan']['action']['tool'] == 'run_candidate' for x in decisions),
                  vla_inference_calls=0, memories_retrieved=len(memory), formal_skills=0,
                  wall_seconds=time.monotonic() - wall_start, error=error,
                  reflection_error=memory_record.get('reflection_error'), source_unchanged=sources == source_hashes())
    write_new(folder / 'result.json', result)
    print('PILOT_RESULT', json.dumps(result, ensure_ascii=False), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--mode', choices=['scripted', 'astra', 'candidate'], required=True)
    parser.add_argument('--gateway-source', type=Path)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    result = run(args.suite, args.seed, args.mode, args.gateway_source, args.candidate)
    raise SystemExit(0 if result['verified_success'] else 1)
