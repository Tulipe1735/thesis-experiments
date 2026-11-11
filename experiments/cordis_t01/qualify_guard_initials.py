"""Private initial-state eligibility gate, before any policy or optional launch."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import os
import mujoco
import numpy as np
from experiments.t0_agent_v1.common import ROOT,REFERENCE,read,sha,write_new,relative


def qualify(suite):
    registration=read(suite/'registration.json')
    table_z=read(REFERENCE/'runtime_context.json')['table_height_m']
    models={};rows=[]
    for case in registration['cases']:
        initial_sha=sha(ROOT/case['initial_source'])
        if initial_sha!=registration['input_sha256'][case['initial_source']]:
            raise ValueError('Frozen initial state changed')
        ref=registration['models'][case['model_key']]
        if sha(ROOT/ref['path'])!=ref['sha256']:raise ValueError('Frozen model changed')
        if ref['path'] not in models:models[ref['path']]=mujoco.MjModel.from_binary_path(str(ROOT/ref['path']))
        model=models[ref['path']];data=mujoco.MjData(model)
        with np.load(ROOT/case['initial_source'],allow_pickle=False) as state:
            mujoco.mj_setState(model,data,state['mujoco_integration_state'],mujoco.mjtState.mjSTATE_INTEGRATION)
        mujoco.mj_forward(model,data)
        instance=case['instance'];tray=model.body('task_tray').id
        inner=np.asarray(instance['tray']['half_size_xy_m'])-instance['tray']['rim_thickness_m']
        target_names=[x['body'] for x in instance['cups']]
        initial={}
        for name in target_names:
            position=data.xpos[model.body(name).id]
            local=data.xmat[tray].reshape(3,3).T@(position-data.xpos[tray])
            initial[name]=dict(on_table_height=bool(abs(position[2]-table_z)<=.002),
                               starts_outside_tray=bool(np.any(np.abs(local[:2])>inner)))
        penetrations=[]
        for i in range(data.ncon):
            c=data.contact[i]
            bodies=[model.body(int(model.geom_bodyid[g])).name for g in (c.geom1,c.geom2)]
            if any(name in bodies for name in target_names+['task_tray']) and c.dist<-.001:
                penetrations.append(dict(bodies=bodies,penetration_m=-float(c.dist)))
        valid=all(x['on_table_height'] and x['starts_outside_tray'] for x in initial.values()) and not penetrations
        rows.append(dict(case_id=case['id'],role=case['evaluation_role'],valid=valid,
                         initial_checks=initial,penetrations=penetrations,initial_sha256=initial_sha))
    return dict(boundary='simulation',physics_steps=0,policy_executed=False,rows=rows,
                all_valid=all(r['valid'] for r in rows),valid_cases=sum(r['valid'] for r in rows),total_cases=len(rows),
                replaced_cases=0,criterion='same frozen initial predicates as tray_verify; penetration >1mm fails')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--launch',action='store_true')
    args=parser.parse_args();suite=args.suite.resolve();result=qualify(suite)
    write_new(args.output,result)
    print(json.dumps(dict(all_valid=result['all_valid'],valid_cases=result['valid_cases'],total_cases=result['total_cases'])))
    if args.launch:
        if not result['all_valid']:raise SystemExit('Launch blocked: invalid initial states retained; no replacements performed')
        env=dict(os.environ,G1_PYTHON=os.environ.get('G1_PYTHON',sys.executable),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1')
        subprocess.run(['node','experiments/cordis_t01/evaluate_guard.mjs','--suite',relative(suite)],cwd=ROOT,env=env,check=True)
