"""Recompute every physical verdict and bind Action, immutable code and paired outcomes."""
import argparse
import csv
import json
from pathlib import Path
import tempfile
from collections import Counter
from experiments.t0_agent_v1.common import ROOT,read,relative,sha,write_new
from experiments.t0_agent_v1.tray_verify import verify
from .run import select


def grouped(rows):
    return dict(requests=len(rows),physical_episodes=sum(r['physical_episodes'] for r in rows),
        independent_successes=sum(r['independent_success'] for r in rows),
        public_passes=sum(r['runtime_result']['runtime_check']=='PASS' for r in rows),
        runtime_status_counts=dict(Counter(r['runtime_result']['runtime_check'] for r in rows)),
        runtime_false_failures=sum(r['runtime_result']['runtime_check']=='FAIL' and r['independent_success'] for r in rows),
        false_positive_success=sum(r['runtime_result']['runtime_check']=='PASS' and not r['independent_success'] for r in rows),
        unverified_successes=sum(r['runtime_result']['runtime_check']=='UNVERIFIED' and r['independent_success'] for r in rows),
        execution_rejections=sum(r['runtime_result']['execution_status']=='REJECTED' for r in rows),
        execution_failures=sum(r['runtime_result']['execution_status']=='FAILED' for r in rows),
        simulation_seconds=sum(r['simulation_seconds'] for r in rows),
        low_level_commands=sum(r['low_level_command_calls'] for r in rows))


def audit(cycle,output):
    output.mkdir(parents=True,exist_ok=False)
    completed=read(cycle/'completion.json')
    phases=[cycle,cycle/'frozen_test',cycle/'boundary']
    all_rows,evidence,checks=[],[],{}
    for suite in phases:
        reg=read(suite/'registration.json')
        saved=read(suite/('development_results.json' if suite==cycle else 'results.json'))['rows']
        indexed={(r['case_id'],r['arm']):r for r in saved}
        expected={(j['case_id'],j['arm']) for j in reg['schedule']}
        checks[reg['phase']+'_complete']=set(indexed)==expected and len(saved)==len(expected)
        checks[reg['phase']+'_bindings']=all(sha(ROOT/p)==h for p,h in
            {**reg['source_sha256'],**reg['input_sha256']}.items())
        checks[reg['phase']+'_qualified']=read(suite/'initial_qualification.json')['all_valid']
        cases={c['id']:c for c in reg['cases']}
        for row in saved:
            job=ROOT/row['job'];episode=ROOT/row['episode'];case=cases[row['case_id']]
            public=read(job/'execution/public_result.json');client=read(job/'client_result.json')
            binding=read(job/'execution/execution_binding.json')
            artifact=ROOT/binding['bundle']
            manifest=read(artifact/'manifest.json')
            decision_consistent=True
            if (job/'execution/runtime_verification.json').exists():
                from .public_check import verdict as public_verdict
                observed=read(job/'execution/runtime_verification.json')
                decision_consistent=public_verdict(observed['samples'])['status']==public['runtime_check']
            with tempfile.TemporaryDirectory(prefix='ros-skill-recompute-') as tmp:
                recomputed=verify(episode,execution_error=row['execution_error'],output=Path(tmp))
            item=dict(case_id=row['case_id'],arm=row['arm'],phase=reg['phase'],
                actual_initial=sha(episode/'initial_state.npz')==row['initial_sha256']==sha(ROOT/case['initial_source']),
                trajectory=sha(episode/'trajectory.npz')==row['trajectory_sha256']==recomputed['trajectory_sha256'],
                verdict=sha(episode/'independent_verification.json')==row['verdict_sha256'],
                outcome=row['independent_success']==recomputed['verified_success'],
                stable_time=abs(row['terminal_stable_s']-recomputed['terminal_simultaneous_stable_s'])<1e-8,
                public_sealed=sha(job/'execution/public_result.json')==row['public_result_sha256'],
                public_rule_recomputed=decision_consistent,
                artifact_manifest=sha(artifact/'manifest.json')==binding['manifest_sha256'],
                frozen_executable=all(sha(ROOT/p)==h for p,h in manifest['bindings'].items()),
                action_matches=all(client[k]==public[k] for k in ['execution_status','runtime_check','reason']),
                action_terminal=client['action_terminal_status']==(4 if public['runtime_check']=='PASS' else 6),
                cross_process=client['independent_process'] and not client['private_physical_verdict_received'],
                feedback_received=client['feedback_count']>0,
                native_control=row['kernel']['read_update_write_steps']==row['physics_steps'] and
                    row['kernel']['actuator_count']==43 and row['kernel']['reference_identity_checked_every_step'],
                zero_model_calls=row['model_requests']==row['weight_updates']==0,
                initial_valid=recomputed['initial_valid'],no_attachment=recomputed['equality_constraints']==0)
            evidence.append(item)
        all_rows+=saved
    checks['all_evidence_recomputed']=all(all(v for k,v in e.items() if k not in ['case_id','arm','phase']) for e in evidence)
    drivers=read(cycle/'driver_binding.json')['sources']
    checks['driver_frozen']=all(sha(ROOT/p)==h for p,h in drivers.items())
    dev=read(cycle/'development_results.json')['rows'];selection=select(dev)
    checks['selection_recomputed']=selection==read(cycle/'selection.json')
    tests=read(cycle/'frozen_test/results.json')['rows'];pairs=[]
    for c in read(cycle/'frozen_test/registration.json')['cases']:
        a=next(r for r in tests if r['case_id']==c['id'] and r['arm']=='nominal')
        b=next(r for r in tests if r['case_id']==c['id'] and r['arm']=='selected')
        pairs.append(dict(case_id=c['id'],group=c['group'],nominal=a['independent_success'],selected=b['independent_success'],
            repaired=b['independent_success'] and not a['independent_success'],
            regressed=a['independent_success'] and not b['independent_success'],
            same_actual_initial=a['initial_sha256']==b['initial_sha256'],
            nominal_public=a['runtime_result']['runtime_check'],selected_public=b['runtime_result']['runtime_check']))
    checks['pairs_same_initial']=all(p['same_actual_initial'] for p in pairs)
    checks['physical_budget']=sum(r['physical_episodes'] for r in all_rows)<=46
    groups=dict(development={arm:grouped([r for r in dev if r['arm']==arm]) for arm in ['nominal','gain025','gain050','gain075']},
        frozen={arm:grouped([r for r in tests if r['arm']==arm]) for arm in ['nominal','selected']},
        boundary=grouped(read(cycle/'boundary/results.json')['rows']),
        frozen_repaired=sum(p['repaired'] for p in pairs),frozen_regressed=sum(p['regressed'] for p in pairs),
        total_physical_episodes=sum(r['physical_episodes'] for r in all_rows),total_requests=len(all_rows))
    with (output/'paired_comparison.csv').open('x',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(pairs[0]));writer.writeheader();writer.writerows(pairs)
    with (output/'all_requests.csv').open('x',newline='',encoding='utf-8-sig') as stream:
        fields=['phase','case_id','arm','independent_success','public_check','execution_status','physical_episodes','physics_steps','simulation_seconds','failed_tool']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for r in all_rows:
            writer.writerow({**{k:r[k] for k in fields if k in r},
                'public_check':r['runtime_result']['runtime_check'],'execution_status':r['runtime_result']['execution_status']})
    report=dict(date='2026-10-29',status='passed' if all(checks.values()) else 'failed',boundary='simulation',
        cycle=relative(cycle),checks=checks,groups=groups,selection=selection,evidence=evidence,pairs=pairs,
        new_physics_steps=0,new_model_requests=0,weights_updated=0,
        qualification='all actual states valid; challenges include declared sensor faults and external forces',
        external_force_note='Two boundary trials intentionally apply declared environmental forces; replay no_external_forces is not a history claim')
    write_new(output/'audit.json',report)
    print(json.dumps(dict(status=report['status'],groups=groups)),flush=True)
    if not all(checks.values()):raise ValueError('Independent audit failed; evidence retained')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cycle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();audit(a.cycle.resolve(),a.output.resolve())
