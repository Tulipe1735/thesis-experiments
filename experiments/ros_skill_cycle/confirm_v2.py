"""One consumed-initial paired confirmation for the unchanged frozen v1.1 recipe."""
import argparse
from copy import deepcopy
from pathlib import Path
import tempfile
from experiments.t0_agent_v1.common import ROOT,read,relative,sha,write_new
from experiments.cordis_t01.qualify_guard_initials import qualify
from experiments.t0_agent_v1.tray_verify import verify
from .run import jobs
from .runtime_env import bootstrap


def main(parent,cycle,output):
    bootstrap('experiments.ros_skill_cycle.confirm_v2')
    output.mkdir(parents=True,exist_ok=False)
    original=read(parent/'registration.json')
    case=deepcopy(next(c for c in original['cases'] if c['id']=='orientation_280201'))
    case['evaluation_role']='consumed_paired_registration_confirmation'
    baseline=next(r for r in read(parent/'development_results.json')['rows']
                  if r['case_id']==case['id'] and r['arm']=='nominal')
    recipe=cycle/'recipe';manifest=read(recipe/'manifest.json')
    if manifest['skill_version']!='1.1.0' or baseline['independent_success']:
        raise ValueError('Frozen v1.1 and retained failed baseline required')
    bindings=dict(manifest['bindings'])
    bindings[relative(Path(__file__))]=sha(Path(__file__))
    write_new(output/'registration.json',dict(date='2026-10-29',phase='paired_registration_confirmation',
        cases=[case],models=original['models'],source_sha256=bindings,
        input_sha256={case['initial_source']:sha(ROOT/case['initial_source']),
                      **{r['path']:r['sha256'] for r in original['models'].values()}},
        schedule=[dict(case_id=case['id'],arm='active_view')],maximum_physical_episodes=1,
        baseline=baseline,baseline_result_sha256=sha(ROOT/baseline['job']/'execution/result.json'),
        test_outcomes_do_not_modify_frozen_program=True,new_generalization_initials=0))
    qualified=qualify(output);write_new(output/'initial_qualification.json',qualified)
    if not qualified['all_valid']:raise ValueError('Confirmation initial invalid')
    rows=jobs(output,output,dict(active_view=recipe),lambda event:None)
    write_new(output/'results.json',dict(rows=rows))
    current=rows[0];episode=ROOT/current['episode']
    with tempfile.TemporaryDirectory(prefix='ros-paired-confirm-') as temporary:
        recomputed=verify(episode,execution_error=current['execution_error'],output=Path(temporary))
    checks=dict(same_initial=current['initial_sha256']==baseline['initial_sha256']==sha(ROOT/case['initial_source']),
        baseline_failed=not baseline['independent_success'],candidate_success=current['independent_success'],
        independent_recomputed=recomputed['verified_success']==current['independent_success'],
        frozen_source=all(sha(ROOT/p)==h for p,h in bindings.items()),
        no_model_requests=current['model_requests']==current['weight_updates']==0)
    write_new(output/'audit.json',dict(date='2026-10-29',status='passed' if all(checks.values()) else 'failed',
        checks=checks,paired_repair=all(checks.values()),baseline_job=baseline['job'],candidate_job=current['job'],
        actual_initial_sha256=current['initial_sha256'],new_physical_episodes=1,
        reused_baseline_evidence=1,new_generalization_initials=0,candidate=current))
    print(dict(checks=checks,physical_episodes=1),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--cycle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.parent.resolve(),a.cycle.resolve(),a.output.resolve())
