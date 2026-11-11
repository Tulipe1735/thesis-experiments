"""Registered T02 object-pose samples; no simulation steps or outcome filtering."""
import copy
import json
from pathlib import Path
import mujoco
import numpy as np
from .task_generator import _sha
from .tp01 import ROOT
SOURCE=ROOT/'experiments/t0_agent_v1/tray_20261025_repair_003/episodes/2401_T02_scripted'
FAMILY={'task_family':'t02_three_cups_v1','task_node':'T02',
 'goal':'Collect all three visible cups into distinct positions in the marked tray, release them, retreat, and leave all three simultaneously supported and stable for >=1 second. Use visual estimates and proprioception only.',
 'observation_notes':'observation.left_palm gives the measured palm pose; joints[name] has q, dq, target, including waist_pitch_joint. cup_bottoms_m and tray are head RGB-D estimates refreshed about once per simulated second and may be stale or empty while the arm occludes them. Command hand joints to grasp and release; left_contact_load_N is the measured hand contact load.',
 'contract':{'pre':['three_cups_on_table','hand_empty','guard_clear'], 'post':['three_cups_stable_in_tray'],
 'params':{'object_count':{'type':'float','description':'待归集杯数'},'hold_s':{'type':'float','description':'三杯共同末段稳持秒数'}},
 'failure_codes':['NOT_REACHED','NOT_HELD','UNSAFE','BUDGET','INTERFACE','WORKER_ERROR']}}


def generate(seed,count,radius_m,*,output):
    if not 0 <= radius_m <= .02 or count < 1:
        raise ValueError('T02 registration uses 0..20 mm planar jitter and count >=1')
    ref=json.loads((SOURCE/'model_reference.json').read_text())
    model=mujoco.MjModel.from_binary_path(str(ROOT/ref['path']))
    rng=np.random.default_rng(seed);tasks=[]
    with np.load(SOURCE/'initial_state.npz',allow_pickle=False) as saved:
        original={k:saved[k].copy() for k in saved.files}
    instance=json.loads((SOURCE/'instance.json').read_text())
    folder=output/'sampled_initials';folder.mkdir(exist_ok=False)
    for i in range(count):
        data=mujoco.MjData(model)
        mujoco.mj_setState(model,data,original['mujoco_integration_state'],mujoco.mjtState.mjSTATE_INTEGRATION)
        sample=copy.deepcopy(instance);sample['seed']=seed*1000+i
        delta=rng.uniform(-radius_m,radius_m,(3,2))
        actual=[]
        for cup,offset in zip(sample['cups'],delta):
            adr=model.jnt_qposadr[model.joint(cup['body']+'_free').id]
            data.qpos[adr:adr+2]+=offset
            cup['cup_table_xy_m']=data.qpos[adr:adr+2].tolist()
            actual.append({'body':cup['body'],'qpos_free':data.qpos[adr:adr+7].tolist()})
        sample['cup_table_xy_m']=sample['cups'][0]['cup_table_xy_m']
        state=np.empty(mujoco.mj_stateSize(model,mujoco.mjtState.mjSTATE_INTEGRATION))
        mujoco.mj_getState(model,data,state,mujoco.mjtState.mjSTATE_INTEGRATION)
        path=folder/f't02_{seed}_{i:03d}.npz'
        with path.open('xb') as f:np.savez_compressed(f,**{**original,'mujoco_integration_state':state})
        tasks.append({'task_id':f't02_{seed}_{i:03d}',
            'public':{'effect':'three_cups_stable_in_tray','object_count':3.,'hold_s':1.},
            'private':{'sampled_arm_q':{},'initial_source':str(path.relative_to(ROOT)),
              'initial_sha256':_sha(path),'instance':sample,'object_free_qpos':actual,
              'sampled_xy_offset_m':delta.tolist(),'task_extent_m':float(np.linalg.norm(delta,axis=1).sum())}})
    return {'generator':FAMILY['task_family'],'family':copy.deepcopy(FAMILY),'seed':seed,'count':count,
        'radius_m':radius_m,'draws':count,'outcome_filter':False,'tasks':tasks,
        'source_initial':{'path':str((SOURCE/'initial_state.npz').relative_to(ROOT)),'sha256':_sha(SOURCE/'initial_state.npz')},
        'plant':{'path':ref['path'],'sha256':_sha(ROOT/ref['path'])}}
