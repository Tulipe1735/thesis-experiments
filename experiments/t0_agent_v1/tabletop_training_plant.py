"""Trusted G1 adapter for frozen tabletop states; no authored code runs in this process."""
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

os.environ.setdefault('MUJOCO_GL','egl')
import mujoco
import numpy as np
from PIL import Image

from .common import ROOT, REFERENCE, read, relative, sha, write_new
from .tabletop_dataset import compile_scene
from .diversity_predicates import snapshot
from .tabletop_predicates import evaluate_trace
from experiments.grow_up_v2.plant import Plant, ARM, HAND, ALLOWED, TrackingMonitor
from experiments.grow_up_v2.isolation.worker import Worker, WorkerError

VERSION = 'tabletop-training-plant-v2'


def build_training_scene(instance,path):
    model=compile_scene(instance,path,native=True)
    del model
    tree=ET.parse(path)
    for item in instance['objects']:
        body=tree.getroot().find(f"./worldbody/body[@name='{item['name']}']")
        for geom in body.findall('geom'):
            # Procedural shapes are both visual and physical. The upstream camera
            # hides group 0, which is reserved for invisible collision geometry.
            vendor_collision=(item['asset'].get('prototype_id')=='robosuite_bottle'
                              and geom.get('group','0')=='0' and geom.get('contype','1')!='0')
            if not vendor_collision:
                geom.set('group','2')
    tree.write(path,encoding='utf-8',xml_declaration=True)
    return mujoco.MjModel.from_xml_path(str(path))


@lru_cache(maxsize=1)
def robot_reference():
    model = mujoco.MjModel.from_binary_path(str(REFERENCE/'model.mjb'))
    data = mujoco.MjData(model)
    with np.load(REFERENCE/'initial_state.npz',allow_pickle=False) as saved:
        mujoco.mj_setState(model,data,saved['mujoco_integration_state'],mujoco.mjtState.mjSTATE_INTEGRATION)
        result = {key:saved[key].copy() for key in ('targets','base_reference','kp','kd','torque_limits')}
    joints = {}
    for j in range(model.njnt):
        name = model.joint(j).name
        if name.startswith('task_cup'):
            continue
        nq,nv = (7,6) if model.jnt_type[j]==0 else (4,3) if model.jnt_type[j]==1 else (1,1)
        q,v = model.jnt_qposadr[j],model.jnt_dofadr[j]
        joints[name] = dict(qpos=data.qpos[q:q+nq].copy(),qvel=data.qvel[v:v+nv].copy(),
            range=model.jnt_range[j].copy(),actfrcrange=model.jnt_actfrcrange[j].copy(),
            actfrclimited=model.jnt_actfrclimited[j])
    result['joints'] = joints
    result['actuators'] = {field:getattr(model,field).copy() for field in (
        'actuator_gainprm','actuator_biastype','actuator_biasprm','actuator_ctrllimited',
        'actuator_forcelimited','actuator_forcerange')}
    return result


def configure_robot(model):
    reference=robot_reference()
    for field,value in reference['actuators'].items():
        getattr(model,field)[:]=value
    for name,row in reference['joints'].items():
        j=model.joint(name).id
        model.jnt_range[j]=row['range']
        model.jnt_actfrcrange[j]=row['actfrcrange']
        model.jnt_actfrclimited[j]=row['actfrclimited']


def set_left_hand_impedance(model,kp,kd):
    """Reuse the existing public hand-config envelope without changing limits."""
    if not np.isfinite([kp,kd]).all() or not .5<=kp<=8. or not .03<=kd<=.5:
        raise ValueError('Hand impedance outside documented body limits')
    names=[model.joint(j).name for j in model.actuator_trnid[:,0]]
    indices=[i for i,name in enumerate(names) if name.startswith('left_hand_')]
    if len(indices)!=7:raise ValueError('Expected the fixed left Dex3-1')
    model.actuator_gainprm[indices,0]=kp
    model.actuator_biasprm[indices,1]=-kp
    model.actuator_biasprm[indices,2]=-kd
    return dict(kp=float(kp),kd=float(kd),joints=[names[i] for i in indices],
                source='bounded reuse of PantryRobot.hand_config',torque_limits_unchanged=True,
                right_side_and_waist_unchanged=True)


class TabletopPlant:
    # Reuse only the reviewed standing controller, sensor projection and guards.
    observation=Plant.observation
    monitor=Plant.monitor
    dispatch=Plant.dispatch

    def __init__(self,instance,case_path,model,output,budget=60.):
        self.model,self.data=model,mujoco.MjData(model)
        self.instance,self.output,self.budget=instance,Path(output),float(budget)
        self.kind='grasp'
        self.context=read(REFERENCE/'runtime_context.json')
        self.profile=read(ROOT/'grasp_optimization/assets/robot_profile.json')['profile']
        self.joint_rows={r[0]:r for r in self.profile['joints']}
        self.joint_ids=model.actuator_trnid[:,0].copy()
        self.qids,self.vids=model.jnt_qposadr[self.joint_ids],model.jnt_dofadr[self.joint_ids]
        self.names=[model.joint(j).name for j in self.joint_ids]
        self.ai={name:i for i,name in enumerate(self.names)}
        configure_robot(model)
        ref=robot_reference()
        for name,row in ref['joints'].items():
            j=model.joint(name).id
            q,v=model.jnt_qposadr[j],model.jnt_dofadr[j]
            self.data.qpos[q:q+len(row['qpos'])]=row['qpos']
            self.data.qvel[v:v+len(row['qvel'])]=row['qvel']
        fixture=mujoco.MjModel.from_xml_path(str(case_path/'qualification.xml'))
        initial=read(case_path/'initial_state.json')
        for j in range(fixture.njnt):
            name=fixture.joint(j).name
            target=model.joint(name).id
            q,v=fixture.jnt_qposadr[j],fixture.jnt_dofadr[j]
            tq,tv=model.jnt_qposadr[target],model.jnt_dofadr[target]
            self.data.qpos[tq:tq+7]=initial['settled_qpos'][q:q+7]
            self.data.qvel[tv:tv+6]=initial['settled_qvel'][v:v+6]
        self.targets=ref['targets'].copy()
        self.base_reference=ref['base_reference'].copy()
        self.kp,self.kd,self.limits=ref['kp'].copy(),ref['kd'].copy(),ref['torque_limits'].copy()
        self.feedforward=np.zeros(model.nu)
        self.fixed_indices=[i for i,n in enumerate(self.names) if n not in ALLOWED]
        self.fixed_targets=self.targets[self.fixed_indices].copy()
        self.pelvis_id=model.body('pelvis').id
        target=next(x for x in instance['objects'] if x['is_target'])
        self.cup_id=model.body(target['name']).id
        self.left_contact_geoms=set()
        for g in range(model.ngeom):
            name=model.body(int(model.geom_bodyid[g])).name or ''
            mesh=int(model.geom_dataid[g])
            mesh_name=model.mesh(mesh).name if mesh>=0 and model.geom_type[g]==mujoco.mjtGeom.mjGEOM_MESH else ''
            if name.startswith('left_hand_') or mesh_name=='left_hand_palm_link':
                self.left_contact_geoms.add(g)
        self.robot_bodies=set()
        for body in range(model.nbody):
            ancestor=body
            while ancestor and ancestor!=self.pelvis_id:
                ancestor=int(model.body_parentid[ancestor])
            if ancestor==self.pelvis_id:
                self.robot_bodies.add(body)
        feet={model.body(side+'_ankle_roll_link').id for side in ('left','right')}
        self.foot_geoms=[g for g in range(model.ngeom) if model.geom_bodyid[g] in feet and model.geom_type[g]==mujoco.mjtGeom.mjGEOM_SPHERE]
        self.floor=self.context['floor_at_robot_m']
        self.floor_geoms=set()
        mujoco.mj_forward(model,self.data)
        for g in range(model.ngeom):
            if (model.geom(g).name or '').startswith('room_contact_'):
                top=self.data.geom_xpos[g,2]+model.geom_size[g,2]
                if -.1<top<.15 and np.all(np.abs(self.data.qpos[:2]-self.data.geom_xpos[g,:2])<model.geom_size[g,:2]):
                    self.floor_geoms.add(g)
        self._mass=np.zeros((model.nv,model.nv))
        self._jac=np.zeros((3,model.nv))
        self._jac_contacts=np.zeros((len(self.foot_geoms)*3,model.nv))
        self.tracking=TrackingMonitor(len(self.names))
        self.guard=None
        self.safety_maxima=dict(tilt_deg=0.,drift_m=0.,tracking_error_rad=0.)
        self.events,self.trace,self.full_states=[],[],[]
        self.renderer=None
        self.next_record=0.
        self.rgbd_cache=None
        self.monitor(advance_tracking=False)
        self.record()
        self.initial_hash=hashlib.sha256(self.data.qpos.tobytes()+self.data.qvel.tobytes()+self.targets.tobytes()).hexdigest()
        write_new(self.output/'initial_pose.json',dict(qpos=self.data.qpos.tolist(),qvel=self.data.qvel.tolist(),
            targets=self.targets.tolist(),initial_hash=self.initial_hash,base_reference=self.base_reference.tolist(),
            dataset_case=instance['id'],robot_reference=relative(REFERENCE/'initial_state.npz')))

    def record(self):
        if self.data.time+1e-9<self.next_record:
            return
        self.next_record+=.05
        state=np.empty(mujoco.mj_stateSize(self.model,mujoco.mjtState.mjSTATE_INTEGRATION))
        mujoco.mj_getState(self.model,self.data,state,mujoco.mjtState.mjSTATE_INTEGRATION)
        self.full_states.append(state)
        self.trace.append(float(self.data.time))

    def rgbd(self):
        if self.rgbd_cache is None or self.data.time-self.rgbd_cache['timestamp_s']>=.4-1e-9:
            self.rgbd_cache=Plant.rgbd(self)
        return self.rgbd_cache

    def head_image(self,path):
        camera=self.rgbd()
        with Path(path).open('xb') as stream:
            Image.fromarray(np.asarray(camera['rgb'],dtype=np.uint8)).save(stream,format='JPEG',quality=88)

    def save(self,error=None,policy_state=None,worker_security=None,policy_calls=0):
        # Include the terminal sample even when the final action stops between ticks.
        if abs(self.trace[-1]-self.data.time)>1e-9:
            self.next_record=self.data.time
            self.record()
        path=self.output/'integration_states.npz'
        with path.open('xb') as stream:
            np.savez_compressed(stream,time=self.trace,integration_state=self.full_states)
        runtime=dict(execution_error=error,guard=self.guard,policy_calls=policy_calls,
            low_level_commands=len(self.events),simulation_seconds=float(self.data.time),
            final_policy_state=policy_state,worker_security=worker_security,safety_maxima=self.safety_maxima)
        write_new(self.output/'execution.json',runtime)
        write_new(self.output/'actions.json',self.events)
        if self.renderer:
            self.head_image(self.output/'final_head.jpg')
            self.renderer.close()
        return runtime


def independent_verify(folder,instance,model,initial_valid=True):
    folder=Path(folder)
    runtime=read(folder/'execution.json')
    initial=read(folder/'initial_pose.json')
    configure_robot(model)
    config_path=folder/'left_hand_impedance.json'
    if config_path.exists():
        config=read(config_path)
        applied=set_left_hand_impedance(model,config['kp'],config['kd'])
        if applied!=config:raise ValueError('Recorded motor configuration differs')
    data=mujoco.MjData(model)
    rows=[]
    with np.load(folder/'integration_states.npz',allow_pickle=False) as trace:
        for state in trace['integration_state']:
            mujoco.mj_setState(model,data,state,mujoco.mjtState.mjSTATE_INTEGRATION)
            mujoco.mj_forward(model,data)
            rows.append(snapshot(model,data,instance,base=initial['base_reference']))
    result=evaluate_trace(instance,rows,initial_valid=initial_valid,
                          execution_error=runtime['execution_error'],protection=runtime['guard'])
    result.update(trajectory_sha256=sha(folder/'integration_states.npz'),boundary='simulation',
                  independent_replay=True,formal_skill_promotion=False,
                  motor_configuration_sha256=sha(config_path) if config_path.exists() else None)
    write_new(folder/'independent_verification.json',result)
    # Evaluator-private: never add these geometric/contact values to Astra feedback.
    write_new(folder/'verified_samples.json',rows)
    return result


def execute_case(scene,instance,case_path,output,source,profile,task,budget=60.,max_calls=400):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    model=mujoco.MjModel.from_xml_path(str(scene))
    plant=TabletopPlant(instance,case_path,model,output,budget)
    plant.head_image(output/'initial_head.jpg')
    error=None
    state=None
    security=None
    calls=0
    done=False
    try:
        with Worker(source,profile,wall_timeout=5.,cpu_seconds=120) as worker:
            security=worker.security
            while calls<max_calls and not plant.guard and plant.data.time<budget-1e-8:
                obs=plant.observation()
                obs['rgbd']=plant.rgbd()
                result=worker.act(obs,task)
                calls+=1
                state=result['state']
                action=result['action']
                if action.get('op')=='done':
                    done=True
                    break
                if action.get('op')=='fail':
                    error=dict(type='PolicyFailure',message=str(action.get('reason','unspecified'))[:400])
                    break
                response=plant.dispatch(action)
                if response['status']!='EXECUTED':
                    error=dict(type='ActionRejected',message=str(response.get('reason') or response['status']))
                    break
            if not done and error is None and not plant.guard:
                error=dict(type='PolicyBudgetExceeded',message='policy did not finish within the registered budget')
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc)[:600])
    finally:
        runtime=plant.save(error,state,security,calls)
    verdict=independent_verify(output,instance,model,initial_valid=True)
    return dict(verified_task_success=verdict['verified_task_success'],
        terminal_stable_s=verdict['terminal_simultaneous_stable_s'],
        simulation_seconds=runtime['simulation_seconds'],policy_calls=calls,
        low_level_commands=runtime['low_level_commands'],guard=plant.guard,error=error,
        initial_hash=plant.initial_hash,final_policy_state=state,folder=relative(output))
