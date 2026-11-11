"""T02-only joint Worker and independent three-cup trajectory verdict."""
import json
import time
import numpy as np
from . import grow_loop as L, tp01
from .local_reach_v3 import timing_quality
from experiments.t0_agent_v1.tray_tools import TrayTaskTools, visible_cups, locate_tray
from experiments.t0_agent_v1.tray_verify import verify, tray_predicate
from experiments.t0_agent_v1.runtime import CountedPort
from experiments.t0_agent_v1.common import append_event
from rgbd_cup import PerceptionError
from run_direct_grasp import ActionFailure


VISION_PERIOD_S=1.


def vision(port):
    raw=port.observe();seen={}
    try:
        cups=visible_cups(raw,expected_count=3)
        seen['cup_bottoms_m']=[c['cup_bottom_position_m'] for c in cups]
    except PerceptionError as error:
        seen['cup_bottoms_m']=[]
        seen['cup_perception_error']=str(error)
    try:seen['tray']=locate_tray(raw)
    except PerceptionError as error:
        seen['tray']=None;seen['tray_perception_error']=str(error)
    return seen


def observe(robot, port, seen=None):
    """Proprioception is always current; pass ``seen`` to reuse the last camera estimates."""
    state=tp01.t01_joint_observation(robot)
    joints=robot.state()['joints']
    state['joints']['waist_pitch_joint']=joints['waist_pitch_joint']
    state.update(vision(port) if seen is None else seen)
    return state


def verdict(episode, error):
    original=verify(episode,execution_error=error)
    rows=json.loads((episode/'verified_samples.json').read_text())
    quality=timing_quality([r['time'] for r in rows])
    since=previous=None
    for row in rows:
        held=(all(tray_predicate(c) for c in row['cups'].values())
              and row['tray_linear_speed_m_s']<=.02 and row['tray_angular_speed_rad_s']<=.2
              and row['tray_tilt_deg']<=5. and row['tray_hand_contact_N']<.1)
        if not held:since=None
        elif since is None or (previous is not None and row['time']-previous>.051):since=row['time']
        previous=row['time']
    hold=0. if since is None or not rows else rows[-1]['time']-since
    strict=(original['verified_success'] and hold>=1.-1e-8)
    return {**original,'reference_verifier_success':original['verified_success'],
        'verified_local_success':bool(strict),'terminal_simultaneous_stable_s':hold,
        'evaluator_version':'t02-three-cup-strict-v1','timing_quality':quality,
        'evidence_status':'success' if strict else 'failure'}


def cup_facts(episode):
    """Per cup: final state, plus motion and hand contact from 1.5 s after first tray-floor support to the end."""
    rows=json.loads((episode/'verified_samples.json').read_text())
    facts={}
    for name in rows[0]['cups']:
        final=rows[-1]['cups'][name]
        times=[r['time'] for r in rows]
        support=next((i for i,r in enumerate(rows) if r['cups'][name]['tray_floor_support_N']>=.5),None)
        entry={'final_tray_xy_m':final['cup_position_tray_m'][:2],'footprint_margin_m':final['footprint_margin_m'],
               'tray_floor_support_N':final['tray_floor_support_N'],'hand_contact_N':final['hand_contact_N'],
               'tilt_deg':final['cup_tilt_deg'],'first_tray_support_s':None,'moved_after_release_m':None,
               'max_hand_contact_after_release_N':None}
        if support is not None:
            start=next(i for i,t in enumerate(times) if t>=times[support]+1.5-1e-9) if times[-1]>=times[support]+1.5 else len(rows)-1
            a=rows[start]['cups'][name]['cup_position_tray_m'];b=final['cup_position_tray_m']
            entry.update(first_tray_support_s=times[support],moved_after_release_m=float(np.hypot(b[0]-a[0],b[1]-a[1])),
                         max_hand_contact_after_release_N=max(r['cups'][name]['hand_contact_N'] for r in rows[start:]))
        facts[name]=entry
    return facts


class Episode:
    def __init__(self,output,plan,caps,task):
        self.output,self.plan,self.caps,self.task=output,plan,caps,task

    def run(self,contract,*,mode,source=None,sampled_q=None,task_input=None):
        out=self.output;out.mkdir(parents=True,exist_ok=False);episode=out/'episode';episode.mkdir()
        instance=self.task['private']['instance']
        L.write_new(episode/'instance.json',instance)
        robot=tp01.TickRecordedRobot(episode,instance,budget=L.SETTLE_S+self.caps['simulation_s'],
            scene_path=tp01.ROOT/self.plan['plant']['path'],initial_state=tp01.ROOT/self.task['private']['initial_source'])
        port=CountedPort(robot);wall=time.monotonic();worker=None;error=None;calls=commands=0
        deadline=L.SETTLE_S+self.caps['simulation_s']
        try:
            robot.advance(L.SETTLE_S,'initial_settling')
            observation=observe(robot,port)
            L.write_new(out/'public_initial.json',observation)
            if mode=='wait':
                for _ in range(10):
                    robot.advance(.2,'wait');commands+=1
            elif mode=='engineering':
                if self.plan.get('positive_reference') == 'recorded_motor_targets':
                    from .t02_generator import SOURCE
                    events=json.loads((SOURCE/'physics_events.json').read_text())[1:]
                    actions=[a for p in sorted(SOURCE.glob('cup_attempt_*/actions.json'))
                             for a in json.loads(p.read_text()) if 'result' in a and 'simulation_seconds' in a['result']]
                    if len(actions)!=len(events):raise ValueError('positive request/event count mismatch')
                    for action,event in zip(actions,events):
                        if abs(action['result']['simulation_seconds']-event['simulation_seconds'])>1e-8:raise ValueError('positive request/event alignment mismatch')
                        if time.monotonic()-wall>self.caps['wall_s']:raise ValueError('LOCAL_WALL_CAP')
                        if commands>=self.caps['commands']:raise ValueError('LOCAL_COMMAND_CAP')
                        if event['category']=='action':
                            response=robot.set_joints(event['joints'],duration=action['arguments']['duration'])
                            if response['status']!='EXECUTED':raise ValueError('GUARD: '+response['status'])
                        else:robot.advance(action['arguments']['seconds'],'reference_wait')
                        commands+=1
                else:
                    tools=TrayTaskTools(port,episode,3)
                    tools.inspect()
                    for _ in range(3):
                        if time.monotonic()-wall>self.caps['wall_s']:raise ValueError('LOCAL_WALL_CAP')
                        tools.collect_next()
                    tools.finish()
                    commands=port.command_calls
            elif mode=='worker':
                L.check_source(source)
                worker=L.Worker(source,self.plan['body_geometry'],cpu_seconds=30,wall_timeout=2.)
                # Camera estimates refresh about once per simulated second; no scene object state is exposed.
                seen={k:observation[k] for k in observation if k.startswith(('cup_','tray'))};seen_at=robot.data.time
                while True:
                    if time.monotonic()-wall>self.caps['wall_s']:raise ValueError('LOCAL_WALL_CAP')
                    calls+=1
                    action=L.check_action(worker.act(observation,task_input)['action'],observation)
                    if action['op']=='done':break
                    if action['op']=='fail':raise ValueError('POLICY_FAIL: '+str(action['reason']))
                    if commands>=self.caps['commands']:raise ValueError('LOCAL_COMMAND_CAP')
                    if action['op']=='wait':response=robot.advance(action['duration'],'joint_wait')
                    else:response=robot.set_joints(action['targets'],duration=action['duration'])
                    commands+=1
                    append_event(out/'actions.jsonl',{'request':action,'response':response})
                    if robot.guard or response.get('status','EXECUTED')!='EXECUTED':raise ValueError('GUARD: '+str(response.get('status',robot.guard)))
                    if robot.data.time>deadline+1e-8:raise ValueError('LOCAL_BUDGET')
                    if robot.data.time-seen_at>=VISION_PERIOD_S:
                        seen=vision(port);seen_at=robot.data.time
                    observation=observe(robot,port,seen)
            else:raise ValueError(mode)
        except (ValueError,KeyError,TypeError,L.WorkerError,L.AgentSchemaError,PerceptionError,ActionFailure) as exc:
            error={'type':type(exc).__name__,'message':str(exc)[:600]}
        finally:
            if worker is not None:worker.close()
            environment=robot.finish()
        checked=verdict(episode,error)
        L.write_new(out/'verdict.json',checked)
        label=None if checked['verified_local_success'] else ('UNSAFE' if robot.guard else 'NOT_REACHED')
        if error:
            label='BUDGET' if error['message'].startswith(('LOCAL_WALL','LOCAL_COMMAND','LOCAL_BUDGET')) else 'WORKER_ERROR'
        facts={'rule_label':label,'execution_error':error,'guard':robot.guard,
            'terminal_hold_s':checked['terminal_simultaneous_stable_s'],
            'supported_cup_count':sum(tray_predicate(c) for c in checked['final']['cups'].values()),
            'timing_quality':checked['timing_quality'],
            'all_target_count':3,'initial_valid':checked['initial_valid'],'cups':cup_facts(episode)}
        result={'mode':mode,'success':checked['verified_local_success'],'error':error,
            'commands':commands,'worker_calls':calls,'simulation_seconds':environment['simulation_seconds'],
            'wall_seconds':time.monotonic()-wall,'facts':facts,'source_sha256':L.sha_text(source) if source else None}
        L.write_new(out/'result.json',result)
        return result
