"""Independent physical and interface audit of the separate observation supplement."""
import argparse
import csv
from pathlib import Path
import tempfile
from experiments.t0_agent_v1.common import ROOT,read,relative,sha,write_new
from experiments.t0_agent_v1.tray_verify import verify
from .audit_cycle import grouped
from .public_check import verdict


def audit(cycle,output):
    output.mkdir(parents=True,exist_ok=False)
    completion=read(cycle/'completion.json')
    gate=read(cycle/'development_gate.json')
    checks=dict(development_gate=gate['passed'],physical_budget=completion['physical_episodes']<=12)
    evidence=[];groups={};all_rows=[]
    for phase in ['development','frozen_test','boundary']:
        suite=cycle/phase;reg=read(suite/'registration.json');rows=read(suite/'results.json')['rows']
        cases={c['id']:c for c in reg['cases']}
        checks[phase+'_roster']={(r['case_id'],r['arm']) for r in rows}=={(j['case_id'],j['arm']) for j in reg['schedule']} and len(rows)==len(reg['schedule'])
        checks[phase+'_bindings']=all(sha(ROOT/p)==h for p,h in {**reg['source_sha256'],**reg['input_sha256']}.items())
        checks[phase+'_qualification']=read(suite/'initial_qualification.json')['all_valid']
        groups[phase]=grouped(rows);all_rows+=rows
        for row in rows:
            job=ROOT/row['job'];episode=ROOT/row['episode'];client=read(job/'client_result.json')
            public=read(job/'execution/public_result.json');binding=read(job/'execution/execution_binding.json')
            artifact=ROOT/binding['bundle'];manifest=read(artifact/'manifest.json')
            with tempfile.TemporaryDirectory(prefix='ros-active-verdict-') as temporary:
                recomputed=verify(episode,execution_error=row['execution_error'],output=Path(temporary))
            observed=read(job/'execution/runtime_verification.json') if (job/'execution/runtime_verification.json').exists() else None
            active=read(job/'execution/active_verification.json') if (job/'execution/active_verification.json').exists() else None
            evidence.append(dict(case_id=row['case_id'],phase=phase,
                actual_initial=sha(episode/'initial_state.npz')==row['initial_sha256']==sha(ROOT/cases[row['case_id']]['initial_source']),
                trajectory=sha(episode/'trajectory.npz')==row['trajectory_sha256']==recomputed['trajectory_sha256'],
                verdict=sha(episode/'independent_verification.json')==row['verdict_sha256'],
                outcome=recomputed['verified_success']==row['independent_success'],
                stability=abs(recomputed['terminal_simultaneous_stable_s']-row['terminal_stable_s'])<1e-8,
                initial_valid=recomputed['initial_valid'],no_attachment=recomputed['equality_constraints']==0,
                public_sealed=sha(job/'execution/public_result.json')==row['public_result_sha256'],
                public_rule=observed is None or verdict(observed['samples'])['status']==public['runtime_check'],
                action_matches=all(client[k]==public[k] for k in ['execution_status','runtime_check','reason']),
                terminal=client['action_terminal_status']==(4 if public['runtime_check']=='PASS' else 6),
                feedback=client['feedback_count']>0,cross_process=client['independent_process'] and not client['private_physical_verdict_received'],
                artifact=sha(artifact/'manifest.json')==binding['manifest_sha256'] and all(sha(ROOT/p)==h for p,h in manifest['bindings'].items()),
                version=manifest['skill_version']=='1.1.0',
                bounded_view=active is None or (active['additional_motion_limit']==1 and active['delta_from_current_palm_m']==[0.,.04,.04]
                    and (not active['attempted'] or active['plan']['reachable'])),
                native=row['kernel']['actuator_count']==43 and row['kernel']['read_update_write_steps']==row['physics_steps'] and row['kernel']['reference_identity_checked_every_step'],
                no_models=row['model_requests']==row['weight_updates']==0))
    checks['all_evidence']=all(all(v for k,v in r.items() if k not in ['case_id','phase']) for r in evidence)
    report=dict(date='2026-10-29',boundary='simulation',status='passed' if all(checks.values()) else 'failed',
        cycle=relative(cycle),checks=checks,groups=groups,evidence=evidence,gate=gate,
        total_physical_episodes=sum(r['physical_episodes'] for r in all_rows),new_physics_steps=0,
        cohort_note='8 new initials belong to v1.1; do not merge with parent12 or infer a causal between-cohort success difference',
        external_force_note='2 boundary trials intentionally apply declared environmental disturbances after placement')
    with (output/'all_requests.csv').open('x',newline='',encoding='utf-8-sig') as stream:
        fields=['phase','case_id','independent_success','runtime_check','failed_tool','simulation_seconds']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in all_rows:writer.writerow({**{k:row[k] for k in fields if k in row},'runtime_check':row['runtime_result']['runtime_check']})
    write_new(output/'audit.json',report)
    print(dict(status=report['status'],groups=groups),flush=True)
    if not all(checks.values()):raise ValueError('Supplement audit failed; evidence retained')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cycle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();audit(a.cycle.resolve(),a.output.resolve())
