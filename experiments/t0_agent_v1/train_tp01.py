"""Astra-authored joint skill practice on TP01 training cases only; no test execution."""
import argparse
import ast
import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

from .common import ROOT, REFERENCE, read, relative, sha, write_new, append_event
from .tabletop_dataset import compile_scene
from .tabletop_training_plant import TabletopPlant, execute_case, build_training_scene
from .tabletop_predicates import VERSION as VERIFIER_VERSION
from grasp_optimization.astra_gateway import AstraGateway
from .author_gateway import AuthorGateway

VERSION='tp01-astra-joint-training-v3'
DATASET=ROOT/'experiments/t0_agent_v1/tabletop_dataset_20261026_003'
MAX_VERSIONS=3
EPISODE_SECONDS=60.
NOOP="""def act(observation, task, state):
    if observation['simulation_seconds'] >= .6:
        return {'action': {'op': 'done'}, 'state': state}
    return {'action': {'op': 'wait', 'duration': .2}, 'state': state}
"""
CONTRACT='''你是Astra训练Agent，为MuJoCo中的G1左臂+左Dex3生成一个统一的“指定物抓起并稳持”Python Skill。
只有训练案例。杯、刚体橙子或玻璃瓶之一是目标；另有灰色非目标罐。目标：目标物离开实际初态至少10cm，由手实际承托并末端稳定至少1秒。
只允许使用给出的身体说明、头部RGB-D、本体关节/掌位和匿名手部载荷；自己实现感知、FK/IK及闭环控制。不得导入工程抓取/IK模块；不得访问文件、网络、进程、MuJoCo、仿真对象身份、真值、评价器、其他Skill代码或测试集。腿由固定站立控制器控制；右臂手和腰部目标固定。
你的source运行在已建立seccomp的独立数值进程，只能import math、numpy及numpy.linalg。可定义init(profile)返回JSON状态。必须定义act(observation,task,state)，返回{"action":{...},"state":JSON可序列化状态}；numpy数组要tolist。没有任何现成运动学或机器人动作函数。
动作只有：{"op":"set_joints","targets":左臂或左手关节绝对角字典,"duration":0.2}，或{"op":"wait","duration":0.2}，{"op":"done"}，{"op":"fail","reason":"简短原因"}。duration范围0.02–0.20且为0.002整数倍；每段臂关节目标增量≤0.03rad、手≤0.05rad，且1.5*增量/duration≤0.30rad/s(臂)、0.50rad/s(手)，还要满足各关节机械限位。实测速度、接触、跟踪和底座保护不允许绕过。done之前须已实际完成1秒稳持；不得用done代替验收。
observation字段：simulation_seconds；joints[name]={q,dq,target,torque_Nm}；left_palm={position_m,quaternion_xyzw,frame:'current_pelvis'}；tactile_joint_load_N[左手joint名]；guard；rgbd={rgb:180x320x3整数,depth_m:180x320米或null,K:3x3,T_optical_to_pelvis:4x4,timestamp_s}。图像最多每0.4s更新；合法传感器可用于自主定位，不能从案例编号硬编码物体位置。
task提供target_category、nominal_rgba、minimum_lift_m、stable_s和terminal_mode，无目标坐标。身体links行的静态四元数为wxyz，掌位观测是xyzw；轴和局部平移及父子关系按列说明。位置单位m，角度rad，时间s。
每例至多60s、400次act。同一source必须处理全部案例，禁止按case/seed选择预写轨迹。不要求不可能或不可见目标强行动作；可以返回有依据的fail。
只返回严格JSON {"source":"完整Python程序字符串","explanation":"根据哪些合法信息做了什么","memory":["有证据且有适用范围的候选经验"]}。这是程序合成与训练，存在程序不等于成功；独立验收决定成功。
'''


def training_cases(dataset=DATASET):
    dataset=Path(dataset)
    frozen=read(dataset/'freeze_manifest.json')
    manifest=dataset/'train/manifest.json'
    if sha(manifest)!=frozen['artifacts']['train/manifest.json']:
        raise ValueError('Training manifest changed')
    cases=[]
    for row in read(manifest)['instances']:
        if row['template_id']!='TP01':
            continue
        for key,digest_key in [('public_task','public_sha256'),('evaluator_instance','evaluator_sha256'),
                               ('initial_state','initial_state_sha256'),('qualification_xml','qualification_xml_sha256')]:
            path=dataset/row[key]
            if '/test/' in str(path.resolve()) or sha(path)!=row[digest_key]:
                raise ValueError('Training-only artifact guard failed')
        instance=read(dataset/row['evaluator_instance'])
        if instance['split']!='train' or instance['template_id']!='TP01':
            raise ValueError('Unexpected training split/template')
        target=next(x for x in instance['objects'] if x['is_target'])
        task=dict(target_category=target['asset']['kind'],nominal_rgba=target['asset']['rgba'],
                  minimum_lift_m=.10,stable_s=1.,terminal_mode='held')
        cases.append(dict(alias=f'case_{len(cases)+1:02}',record=row,instance=instance,
                          case_path=(dataset/row['evaluator_instance']).resolve().parent,task=task))
    if len(cases)!=8:
        raise ValueError('Exactly eight TP01 training cases required')
    return cases


def body_packet():
    profile=read(ROOT/'grasp_optimization/assets/robot_profile.json')['profile']
    keys=('robot','units','coordinates','link_columns','links','joint_columns','joints','palm_frame',
          'finger_order','tactile_patch_columns','tactile_patches','control','hand_impedance','limitations')
    return {k:profile[k] for k in keys if k in profile}


def source_paths():
    base=Path(__file__).parent
    return [Path(__file__),base/'author_gateway.py',base/'tabletop_training_plant.py',base/'tabletop_predicates.py',
        base/'diversity_predicates.py',base/'tabletop_dataset.py',base/'diversity.py',base/'diversity_assets.py',
        ROOT/'experiments/grow_up_v2/plant.py',ROOT/'experiments/grow_up_v2/isolation/worker.py',
        ROOT/'experiments/grow_up_v2/isolation/_entry.py',ROOT/'grasp_optimization/pantry_robot.py',
        ROOT/'grasp_optimization/astra_gateway.py',ROOT/'grasp_optimization/assets/robot_profile.json']


def prepare(output,dataset=DATASET):
    output=Path(output)
    output=output if output.is_absolute() else ROOT/output
    cases=training_cases(dataset)
    output.mkdir(parents=True,exist_ok=False)
    origin=read(ROOT/'experiments/t0_agent_v1/tray_astra_20261025_002/registration.json')['gateway_origin']
    write_new(output/'registration.json',dict(date='2026-10-26',boundary='simulation',version=VERSION,
        dataset=relative(dataset),template='TP01',stage='training_only',
        cases=[dict(alias=c['alias'],id=c['instance']['id'],seed=c['instance']['seed'],
                    source_case=relative(c['case_path'])) for c in cases],
        max_candidate_versions=MAX_VERSIONS,max_author_requests=MAX_VERSIONS,max_output_tokens_per_request=10000,
        observed_token_stop=150000,token_limit_semantics='stop after returned gateway usage reaches limit; hard request count separately capped',
        max_policy_calls_per_episode=400,max_simulation_seconds=EPISODE_SECONDS,
        max_training_episodes=8*MAX_VERSIONS,engineering_noop_seconds=.6,expected_gateway_origin=origin,
        allowed_model_inputs=['approved body profile','training head images and RGB-D','proprioception',
            'anonymous tactile loads','own candidate code/state','coarse training outcome'],
        forbidden_model_inputs=['dataset coordinates/dimensions/seed tables','simulation model or state','verifier source',
            'spectator images','old engineered grasp or IK source','test cases and feedback','credentials'],
        source_sha256={relative(p):sha(p) for p in source_paths()},
        verifier_version=VERIFIER_VERSION,selection='last valid submitted candidate, not best episode cherry-picking',
        formal_skill_promotion=False,model_weight_training=False))
    write_new(output/'body_packet.json',body_packet())
    (output/'agent_contract.txt').write_text(CONTRACT,encoding='utf-8')
    scenes=output/'scenes'
    scenes.mkdir(exist_ok=False)
    preflight=[]
    for case in cases:
        path=scenes/(case['alias']+'.xml')
        model=build_training_scene(case['instance'],path)
        del model
        write_new(scenes/(case['alias']+'.json'),dict(xml=relative(path),sha256=sha(path),
            instance=relative(case['case_path']/'instance.json'),instance_sha256=sha(case['case_path']/'instance.json')))
        result=execute_case(path,case['instance'],case['case_path'],output/'preflight'/case['alias'],
                            NOOP,body_packet(),case['task'],budget=2.,max_calls=8)
        # Goal failure is expected for stationary engineering checks.
        valid=result['guard'] is None and result['error'] is None
        preflight.append(dict(alias=case['alias'],valid=valid,**result))
        print('PREFLIGHT',case['alias'],valid,result['guard'],result['error'],flush=True)
    write_new(output/'preflight.json',dict(boundary='simulation',ready=all(x['valid'] for x in preflight),
        checks=preflight,policy_source='stationary engineering NOOP; no grasping teacher',astra_requests=0))
    return output


def prepare_continuation(output,parent):
    output,parent=Path(output),Path(parent)
    output=output if output.is_absolute() else ROOT/output
    parent=parent if parent.is_absolute() else ROOT/parent
    if not (parent/'results.json').exists():
        raise ValueError('Parent author request may still be running')
    old=read(parent/'registration.json')
    events=[json.loads(line) for line in (parent/'requests.jsonl').read_text().splitlines()]
    used=old.get('prior_author_requests',0)+sum(e.get('state')=='started' for e in events)
    if not 0<used<MAX_VERSIONS:
        raise ValueError('No authorized author requests remaining')
    if not read(parent/'preflight.json')['ready']:
        raise ValueError('Parent engineering preflight invalid')
    output.mkdir(parents=True,exist_ok=False)
    reg=dict(old)
    reg.update(version=VERSION,previous_run=relative(parent),prior_author_requests=used,
        max_candidate_versions=MAX_VERSIONS-used,max_author_requests=MAX_VERSIONS-used,
        total_author_request_limit=MAX_VERSIONS,author_timeout_seconds=180,
        scene_source=old.get('scene_source',relative(parent/'scenes')),
        preflight_source=old.get('preflight_source',relative(parent/'preflight')),
        source_sha256={relative(p):sha(p) for p in source_paths()},
        transport_revision='GET models returned in about 1s; retain failed 55s generation and extend authoring response timeout only',
        prior_usage_unknown=True)
    write_new(output/'registration.json',reg)
    write_new(output/'preflight.json',dict(ready=True,source=relative(parent/'preflight.json'),
        sha256=sha(parent/'preflight.json'),reused=True,new_physics_episodes=0))
    write_new(output/'body_packet.json',body_packet())
    for name in ('gateway_export_approval.json','outbound_review.json'):
        write_new(output/name,dict(source=relative(parent/name),sha256=sha(parent/name),continued_same_approved_scope=True))
    with (output/'agent_contract.txt').open('x',encoding='utf-8') as stream:
        stream.write(CONTRACT)
    return output


def parse_candidate(text):
    value=text.strip()
    if value.startswith('```'):
        value='\n'.join(value.splitlines()[1:-1])
    candidate=json.loads(value)
    if set(candidate)!={'source','explanation','memory'} or not isinstance(candidate['source'],str):
        raise ValueError('Candidate schema')
    if not isinstance(candidate['explanation'],str) or not isinstance(candidate['memory'],list):
        raise ValueError('Candidate explanation/memory schema')
    tree=ast.parse(candidate['source'])
    if not any(isinstance(n,ast.FunctionDef) and n.name=='act' for n in tree.body):
        raise ValueError('Candidate missing act')
    return candidate


def image_part(path):
    return dict(type='image_url',image_url=dict(url='data:image/jpeg;base64,'+
        base64.b64encode(Path(path).read_bytes()).decode('ascii'),detail='high'))


def train(output,gateway_source):
    output=Path(output)
    output=output if output.is_absolute() else ROOT/output
    registration=read(output/'registration.json')
    if not read(output/'preflight.json')['ready']:
        raise ValueError('Engineering preflight not ready')
    for path,digest in registration['source_sha256'].items():
        if sha(ROOT/path)!=digest:
            raise ValueError('Registered runtime changed: '+path)
    if (output/'requests.jsonl').exists():
        raise FileExistsError('Astra authoring already started; do not silently repeat')
    client=(AuthorGateway if registration.get('author_timeout_seconds') else AstraGateway).from_example(Path(gateway_source))
    origin=urlsplit(client.base_url)
    if f'{origin.scheme}://{origin.netloc}'!=registration['expected_gateway_origin']:
        raise ValueError('Unexpected gateway origin')
    write_new(output/'gateway_metadata.json',dict(model=client.model,origin=registration['expected_gateway_origin'],
        credential_persisted=False,authorized_scope='user requested first-task training using the existing online Astra workflow'))
    cases=training_cases(ROOT/registration['dataset'])
    scene_root=ROOT/registration.get('scene_source',relative(output/'scenes'))
    preflight_root=ROOT/registration.get('preflight_source',relative(output/'preflight'))
    content=[dict(type='text',text=json.dumps(dict(body_profile=body_packet(),
        training_tasks=[dict(alias=c['alias'],task=c['task']) for c in cases]),ensure_ascii=False))]
    for case in cases:
        image=preflight_root/case['alias']/'initial_head.jpg'
        content.extend([dict(type='text',text='训练合法头部观测 '+case['alias']),image_part(image)])
    messages=[dict(role='system',content=CONTRACT),dict(role='user',content=content)]
    tokens=0
    versions=[]
    last_source=None
    for version in range(1,registration['max_candidate_versions']+1):
        # Persist exactly which allowed information leaves the host.
        write_new(output/f'model_input_v{version}.json',dict(messages=messages,
            scope='training legal observations and own program only; no evaluator state',credential_included=False))
        append_event(output/'requests.jsonl',dict(version=version,state='started',kind='skill_authoring',
            cumulative_request=registration.get('prior_author_requests',0)+version))
        try:
            response,latency=client.chat(messages,max_tokens=10000)
        except Exception as exc:
            append_event(output/'requests.jsonl',dict(version=version,state='failed',error_type=type(exc).__name__,message=str(exc)[:500]))
            write_new(output/'network_failure.json',dict(version=version,type=type(exc).__name__,message=str(exc)[:500],
                action='training stopped; no fallback or automatic retry'))
            break
        text=response['choices'][0]['message'].get('content') or ''
        usage=response.get('usage') or {}
        tokens+=int(usage.get('total_tokens',0))
        append_event(output/'requests.jsonl',dict(version=version,state='returned',kind='skill_authoring',
            usage=usage,wall_seconds=latency,response=text))
        messages.append(dict(role='assistant',content=text))
        try:
            candidate=parse_candidate(text)
        except Exception as exc:
            versions.append(dict(version=version,valid_source=False,error=f'{type(exc).__name__}: {exc}',episodes=[]))
            messages.append(dict(role='user',content='程序未执行，候选格式或语法检查拒绝：'+str(exc)+'。请返回相同schema的完整修复程序。'))
            if tokens>=registration['observed_token_stop']:
                break
            continue
        path=output/f'candidate_v{version}.py'
        with path.open('x',encoding='utf-8') as stream:
            stream.write(candidate['source'])
        write_new(output/f'candidate_v{version}.json',dict(version=version,status='candidate_only',
            source=relative(path),sha256=sha(path),explanation=candidate['explanation'],memory_candidate=candidate['memory']))
        episodes=[]
        for case in cases:
            print('TRAINING',version,case['alias'],flush=True)
            result=execute_case(scene_root/(case['alias']+'.xml'),case['instance'],case['case_path'],
                output/f'practice_v{version}'/case['alias'],candidate['source'],body_packet(),case['task'])
            episodes.append(dict(alias=case['alias'],**result))
            print('OUTCOME',version,case['alias'],result['verified_task_success'],result['error'],result['guard'],flush=True)
        versions.append(dict(version=version,valid_source=True,episodes=episodes,
            success=sum(e['verified_task_success'] for e in episodes),source=relative(path),sha256=sha(path)))
        write_new(output/f'practice_v{version}_results.json',versions[-1])
        last_source=path
        feedback=[]
        for episode in episodes:
            state=episode['final_policy_state']
            # Candidate state comes only from allowed observations and body data.
            short_state=({k:v for k,v in state.items() if k in ('phase','reason','halt_reason','status','pose_error','perception','error')}
                         if isinstance(state,dict) else state)
            feedback.append(dict(alias=episode['alias'],passed=episode['verified_task_success'],
                guard=episode['guard'],error=episode['error'],simulation_seconds=episode['simulation_seconds'],
                own_policy_state=short_state))
        content=[dict(type='text',text=json.dumps(dict(training_feedback=feedback,
            instruction='只根据合法训练反馈改进同一个参数化Skill。保留物理与接口约束，不按案例硬编码坐标，返回完整程序。'),ensure_ascii=False))]
        for episode in episodes:
            image=ROOT/episode['folder']/'final_head.jpg'
            if image.exists():
                content.extend([dict(type='text',text='训练结束头部观测 '+episode['alias']),image_part(image)])
        messages.append(dict(role='user',content=content))
        if tokens>=registration['observed_token_stop'] or all(e['verified_task_success'] for e in episodes):
            break
    valid=[v for v in versions if v.get('valid_source')]
    final=valid[-1] if valid else None
    summary=dict(date='2026-10-26',boundary='simulation',template='TP01',stage='training_only',
        versions=versions,final_candidate=relative(last_source) if last_source else None,
        final_training_success=final['success'] if final else 0,training_instances=8,
        physics_episodes=sum(len(v.get('episodes',[])) for v in versions),
        actual_astra_requests=len([r for r in (output/'requests.jsonl').read_text().splitlines() if json.loads(r).get('state')=='started']),
        reported_tokens=tokens,test_instances_executed=0,model_weight_updates=0,
        prior_author_requests=registration.get('prior_author_requests',0),prior_usage_unknown=registration.get('prior_usage_unknown',False),
        formal_skill_promotions=0,selection='last valid candidate',
        status='practice_completed' if final and len(final['episodes'])==8 else 'authoring_or_transport_incomplete')
    write_new(output/'results.json',summary)
    if final:
        write_new(output/'skill_candidate.json',dict(family='tabletop_pick_place',task='TP01',status='candidate_only',
            source=final['source'],sha256=final['sha256'],training_success=final['success'],training_cases=8,
            held_out_tested=False,formal_promotion=False,author='Astra online gateway',runtime='isolated numerical joint program'))
    print('TRAINING_RESULT',json.dumps({k:v for k,v in summary.items() if k!='versions'},ensure_ascii=False),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('--output',type=Path,required=True)
    p=commands.add_parser('continue');p.add_argument('--output',type=Path,required=True);p.add_argument('--parent',type=Path,required=True)
    p=commands.add_parser('train');p.add_argument('--output',type=Path,required=True);p.add_argument('--gateway-source',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':
        prepare(args.output)
    elif args.command=='continue':
        prepare_continuation(args.output,args.parent)
    else:
        train(args.output,args.gateway_source)
