"""Local SmolVLA process plus named, bounded 30 Hz actions in the physical pantry."""
from datetime import datetime
import json
import math
from pathlib import Path
import queue
import subprocess
import threading
import time

import numpy as np

from experiment_log import ROOT
from vla_paths import WORK

VERSION='g1-smolvla-tool-0.1.0'


def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


class LocalVLAClient:
    def __init__(self,log_folder):
        self.folder=Path(log_folder)
        self.folder.mkdir(parents=True,exist_ok=True)
        self.log=(self.folder/'policy_worker.log').open('w',encoding='utf-8')
        self.messages=queue.Queue()
        self.ready=False
        python=WORK/'vla-env/bin/python'
        print('VLA_LOADING_LOCAL_CHECKPOINT',flush=True)
        self.process=subprocess.Popen([str(python),'-u',str(ROOT/'smolvla_worker.py')],
                                      stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,
                                      text=True,encoding='utf-8',bufsize=1,cwd=str(ROOT))

        def read_packets():
            try:
                for line in self.process.stdout:
                    if line.startswith('VLA_JSON '):
                        self.messages.put(json.loads(line[len('VLA_JSON '):]))
                    else:
                        self.log.write(line);self.log.flush()
            finally:
                self.messages.put(dict(status='PROCESS_EXITED'))

        self.reader=threading.Thread(target=read_packets,daemon=True)
        self.reader.start()
        self.info=self.receive(600)
        if self.info.get('status')!='READY':
            self.close()
            raise RuntimeError('Local VLA failed to load: '+json.dumps(self.info,ensure_ascii=False))
        if self.info['action_semantics']!='absolute_joint_radians_after_native_postprocessor':
            self.close();raise ValueError('Unsupported VLA action semantics')
        self.ready=True
        self.calls=0
        write_json(self.folder/'policy_runtime.json',dict(adapter_version=VERSION,**self.info))
        print('VLA_READY',self.info['model_id'],self.info['policy_fps'],'Hz',flush=True)

    def receive(self,timeout):
        try:
            return self.messages.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError('VLA worker timed out; see policy_worker.log') from None

    def predict(self,observation,instruction,output_file,rng_seed=None):
        if not self.ready or self.process.poll() is not None:
            raise RuntimeError('The local VLA worker is not ready')
        start=time.monotonic()
        self.process.stdin.write(json.dumps(dict(op='predict',observation=observation,instruction=instruction,
                                                output_file=str(output_file),rng_seed=rng_seed),ensure_ascii=False)+'\n')
        self.process.stdin.flush()
        result=self.receive(180)
        elapsed=time.monotonic()-start
        self.calls+=1
        result['request_wall_seconds']=elapsed
        if result.get('status')!='PREDICTED':
            raise RuntimeError('VLA inference failed: '+json.dumps(result,ensure_ascii=False))
        return result

    def close(self):
        self.ready=False
        if self.process.poll() is None:
            try:
                self.process.stdin.write('{"op":"close"}\n');self.process.stdin.flush()
                self.process.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired):
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.log.close()


def run_vla_motion(robot,subgoal,max_seconds=.5):
    """Execute short prefixes, reobserve and replan; the caller remains the high-level agent."""
    client=robot.vla
    if client is None or not client.ready:
        return dict(status='VLA_NOT_CONNECTED',executed=False)
    if not isinstance(subgoal,str) or not 1<=len(subgoal.strip())<=500:
        raise ValueError('A nonempty subgoal of at most 500 characters is required')
    if not isinstance(max_seconds,(int,float)) or not math.isfinite(max_seconds) or not .1<=max_seconds<=3:
        raise ValueError('VLA action-time budget must be 0.1 to 3 seconds')
    if robot.guard:
        return dict(status='VLA_NOT_EXECUTED_BASE_PROTECTION',executed=False,protection=robot.guard)
    names=client.info['joint_names']
    if len(names)!=28 or len(set(names))!=28 or any(name not in robot.ai for name in names):
        raise ValueError('The 28 named G1 arm/hand joints do not match the physical model')
    if any(not any(part in name for part in ('shoulder','elbow','wrist','_hand_')) for name in names):
        raise ValueError('VLA cannot command the legs or waist')
    fps=int(client.info['policy_fps'])
    if fps!=30:
        raise ValueError('This action adapter is configured for the audited 30 Hz checkpoint')
    indices=np.array([robot.ai[name] for name in names])
    qids=robot.qids[indices]
    bounds=robot.model.jnt_range[robot.joint_ids[indices]]
    velocities=np.array([min(robot.joint_rows[name][5],1.0 if '_hand_' in name else .75) for name in names])
    planned_frames=max(1,int(math.floor(max_seconds*fps+1e-8)))
    prefix_frames=5
    robot.vla_tool_calls+=1
    folder=robot.folder/f'vla_tool_{robot.vla_tool_calls:03}'
    folder.mkdir(parents=True,exist_ok=False)
    applied=0
    chunks=[]
    start=float(robot.data.time)
    status='VLA_ACTION_BUDGET_COMPLETE'
    for chunk_number in range(1,math.ceil(planned_frames/prefix_frames)+1):
        if robot.guard:
            status='VLA_PHYSICS_PROTECTION';break
        observation=robot.observe()
        chunk_path=folder/f'chunk_{chunk_number:03}_native_absolute.npy'
        print('VLA_INFER',robot.vla_tool_calls,chunk_number,observation['observation_id'],flush=True)
        inference=client.predict(observation,subgoal.strip(),chunk_path)
        robot.advance(inference['request_wall_seconds'],'vla_inference_wait')
        chunk=dict(chunk=chunk_number,observation_id=observation['observation_id'],
                   observation_simulation_seconds=observation['simulation_seconds'],inference=inference,
                   projection_count=0,slew_limit_count=0,applied_frames=0)
        chunks.append(chunk)
        if robot.guard:
            status='VLA_PHYSICS_PROTECTION';break
        raw=np.load(chunk_path,allow_pickle=False)
        if raw.shape!=(1,50,28) or not np.isfinite(raw).all():
            raise ValueError('VLA actions must be finite native (1,50,28) absolute radians')
        count=min(prefix_frames,planned_frames-applied)
        clock_start=float(robot.data.time)
        rows=[]
        for frame in range(count):
            target_raw=raw[0,frame].astype(float)
            in_range=np.clip(target_raw,bounds[:,0],bounds[:,1])
            previous=robot.targets[indices].copy()
            end=clock_start+(frame+1)/fps
            duration=max(float(robot.model.opt.timestep),end-float(robot.data.time))
            limited=previous+np.clip(in_range-previous,-velocities*duration,velocities*duration)
            chunk['projection_count']+=int(np.count_nonzero(abs(in_range-target_raw)>1e-7))
            chunk['slew_limit_count']+=int(np.count_nonzero(abs(limited-in_range)>1e-7))
            t0=float(robot.data.time)
            while robot.data.time<end-1e-9 and not robot.guard:
                fraction=min(1.,(float(robot.data.time)-t0+robot.model.opt.timestep)/duration)
                robot.targets[indices]=previous+(limited-previous)*fraction
                robot._step()
            actual=robot.data.qpos[qids].copy()
            rows.append((float(robot.data.time),target_raw.copy(),limited.copy(),actual))
            applied+=1;chunk['applied_frames']+=1;robot.vla_applied_frames+=1
            arms=[i for i,name in enumerate(names) if '_hand_' not in name]
            tracking=float(np.max(np.abs(actual[arms]-robot.targets[indices][arms])))
            if robot.guard or tracking>.45:
                if tracking>.45:
                    robot.targets[indices]=actual
                    status='VLA_TRACKING_PROTECTION'
                else:status='VLA_PHYSICS_PROTECTION'
                chunk['tracking_error_rad']=tracking
                break
        if rows:
            applied_file=folder/f'chunk_{chunk_number:03}_applied.npz'
            np.savez_compressed(applied_file,time=[r[0] for r in rows],raw_target=[r[1] for r in rows],
                                command_target=[r[2] for r in rows],actual_joint_q=[r[3] for r in rows])
            chunk['applied_file']=str(applied_file.relative_to(ROOT))
        write_json(folder/f'chunk_{chunk_number:03}.json',chunk)
        if status!='VLA_ACTION_BUDGET_COMPLETE':break
    result=dict(status=status,executed=applied>0,subgoal=subgoal,adapter_version=VERSION,
                model_id=client.info['model_id'],revision=client.info['revision'],
                inference_calls=len(chunks),applied_action_frames=applied,
                nominal_action_seconds=applied/fps,physical_seconds=float(robot.data.time)-start,
                native_output_shape=[1,50,28],native_policy_fps=fps,executed_prefix_frames=prefix_frames,
                joint_names=names,action_units='absolute_joint_radians',current_q_added_again=False,
                native_postprocessing_applied=True,waist_and_legs_commanded_by_vla=False,
                limit_projection_count=sum(c['projection_count'] for c in chunks),
                slew_limit_count=sum(c['slew_limit_count'] for c in chunks),
                speed_caps_rad_s=dict(zip(names,map(float,velocities))),
                camera_variant='single_real_head_missing_training_views_omitted',
                training_task='toasted bread; cup transfer ability unverified',
                log_folder=str(folder.relative_to(ROOT)),feedback=robot.state())
    write_json(folder/'result.json',result)
    robot.events.append(dict(category='vla_tool',status=status,inference_calls=len(chunks),
                             applied_frames=applied,simulation_seconds=float(robot.data.time)))
    print('VLA_RETURN',status,applied,'frames',flush=True)
    return result
