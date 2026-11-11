"""Recompute verdicts independently; bind saved initial states, sources and outcomes."""
import argparse
import csv
from pathlib import Path
import tempfile

from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new
from experiments.t0_agent_v1.tray_verify import verify


def audit(suite):
    registration = read(suite / 'registration.json')
    completed = read(suite / 'results.json')['results']
    indexed = {(r['case_id'], r['condition']): r for r in completed}
    expected = {(j['case_id'], j['condition']) for j in registration['schedule']}
    checks = dict(complete_roster=set(indexed) == expected and len(completed) == len(expected),
                  frozen_source_inputs=all(sha(ROOT / p) == h for p, h in
                    {**registration['source_sha256'], **registration['input_sha256']}.items()),
                  initial_gate_passed=read(suite / 'initial_qualification.json')['all_valid'])
    rows, evidence = [], []
    for case in registration['cases']:
        row = dict(case_id=case['id'], role=case['evaluation_role'])
        for condition in registration['policies']:
            result = indexed[(case['id'], condition)]
            episode = ROOT / result['episode']
            original = read(episode / 'independent_verification.json')
            # Temporary recomputation does not overwrite or duplicate stored evidence.
            with tempfile.TemporaryDirectory(prefix='t01-verdict-') as temporary:
                recomputed = verify(episode, execution_error=result['execution_error'], output=Path(temporary))
            bound = dict(case_id=case['id'], condition=condition,
                initial=sha(episode / 'initial_state.npz') == result['initial_sha256'] == sha(ROOT / case['initial_source']),
                trajectory=sha(episode / 'trajectory.npz') == result['trajectory_sha256'] == recomputed['trajectory_sha256'],
                verdict=sha(episode / 'independent_verification.json') == result['verdict_sha256'],
                outcome=result['verified_success'] == original['verified_success'] == recomputed['verified_success'],
                stable_time=abs(result['terminal_stable_s'] - recomputed['terminal_simultaneous_stable_s']) < 1e-9,
                model=read(episode / 'model_reference.json')['sha256'] == registration['models'][case['model_key']]['sha256'],
                valid_initial=recomputed['initial_valid'],
                no_attachment_or_external_force=recomputed['equality_constraints'] == 0 and recomputed['no_external_forces'],
                fixed_sources=result['source_unchanged'], no_paid_models=result['model_requests'] == 0)
            evidence.append(bound)
            row[condition] = result['verified_success']
            row[condition + '_stable_s'] = result['terminal_stable_s']
            row[condition + '_sim_s'] = result['simulation_seconds']
            row[condition + '_commands'] = result['low_level_command_calls']
        row['gain'] = int(row['candidate']) - int(row['nominal'])
        rows.append(row)
    checks['evidence_bound_and_recomputed'] = all(
        all(v for k, v in item.items() if k not in ['case_id', 'condition']) for item in evidence)
    groups = dict(initials=len(rows), physical_episodes=len(completed),
                  successes={arm: sum(r[arm] for r in rows) for arm in registration['policies']},
                  repaired=sum(r['gain'] == 1 for r in rows), regressed=sum(r['gain'] == -1 for r in rows))
    with (suite / 'paired_comparison.csv').open('x', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = dict(date='2026-10-29', boundary='simulation', status='passed' if all(checks.values()) else 'failed',
                  checks=checks, groups=groups, pairs=rows, evidence=evidence,
                  formal_promotion=False, scope='registered instances only; no population or real-robot guarantee')
    write_new(suite / 'audit.json', report)
    print({k: report[k] for k in ['status', 'groups']}, flush=True)
    if not all(checks.values()):
        raise ValueError('Audit failed; original evidence retained')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    audit(parser.parse_args().suite.resolve())
