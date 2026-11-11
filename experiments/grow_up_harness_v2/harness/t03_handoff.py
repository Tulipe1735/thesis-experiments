"""Where a T03 leaf stops, and what the next stage needs to receive.

Read-only analysis of already-produced episodes. This module never judges a
task: success stays with the independent evaluator. It only reports whether a
batch could have measured the mechanism under test, and which stage blocked it.

Stage order follows the executed T03 runtime loop
(`harness/t03_runtime.py`, `for stage in [...]`). A leaf declared at
`leaf_stage` can only act once execution reaches that stage, so a failure
strictly earlier means the leaf was never invoked and the batch says nothing
about it.
"""
import json
from pathlib import Path

STAGES = (
    'locate',
    'preflight',
    'prepare',
    'approach',
    'close_and_test',
    'lift_and_hold',
    'transfer',
    'lower',
    'release_and_retreat',
)

# Entry evidence a downstream stage needs before a leaf may claim the stage
# before it. Declared here so a config can be checked, not silently assumed.
HANDOFF = {
    'approach': ('closed_hand_clearance_at_arrival', 'retreat_path_clearance_at_arrival'),
    'close_and_test': ('thumb_finger_alignment_at_arrival', 'grip_settle_force_window'),
    'lift_and_hold': ('lift_clearance_margin', 'regrasp_recovery_available'),
    'release_and_retreat': ('release_height_margin', 'retreat_clearance_margin'),
}

# Recorded decision artifacts: file -> (list field, key holding the chosen route),
# and the value that means "the original behaviour ran, the new branch did not".
DECISION_RECORDS = {
    'locate_branch.json': {'list': 'attempts', 'key': 'route', 'baseline': 'primary', 'stage': 'locate'},
    'obstacle_approach.json': {'list': 'calls', 'key': 'selected', 'baseline': 'default', 'stage': 'approach'},
}


def read_decisions(folder):
    """Per-stage (leaf_invoked, branch_fired) from recorded decision artifacts.

    `leaf_invoked` means a decision record exists for that stage and holds at
    least one attempt. `branch_fired` means at least one attempt left the
    baseline route, so a leaf that was consulted and declined counts as
    invoked, not triggered.
    """
    out = {}
    for name, spec in DECISION_RECORDS.items():
        p = Path(folder) / name
        if not p.exists():
            continue
        attempts = (json.loads(p.read_text(encoding='utf-8')).get(spec['list']) or [])
        if not attempts:
            continue
        stage = spec['stage']
        invoked, fired = out.get(stage, (False, False))
        fired = fired or any(a.get(spec['key']) not in (spec['baseline'], None) for a in attempts)
        out[stage] = (True, fired)
    return out


def decision_stage(folder):
    """Deepest runtime stage that wrote a decision record, or None."""
    seen = [s for s, _ in read_decisions(folder).items()]
    return max(seen, key=stage_index) if seen else None


def stage_index(stage):
    if stage not in STAGES:
        raise ValueError('unknown stage: %r' % (stage,))
    return STAGES.index(stage)


def handoff_gaps(config):
    """Stages a focus list claims to advance but has not declared entry evidence for."""
    focuses = config.get('focuses') or []
    if not focuses:
        return sorted(HANDOFF)
    declared = config.get('handoff') or {}
    upto = max(stage_index(f['stage']) for f in focuses)
    return [s for s in STAGES[:upto + 1] if s in HANDOFF and s not in declared]


def validate_registration(config):
    """Pre-run gate for a T03 round. Returns findings; never raises on content.

    A round that cannot name which stages its work targets, or the entry
    evidence those stages need, is not registrable: its result could not be
    attributed either way.

    Several focuses are allowed and expected when a batch loses episodes at
    more than one stage. The limit is attribution, not count: each focus needs
    its own trigger, and per-focus results must stay separable.
    """
    errors = []
    focuses = config.get('focuses') or []
    if not focuses:
        errors.append('focuses_missing')
    stages = []
    for i, f in enumerate(focuses):
        stage = f.get('stage')
        if stage is None:
            errors.append('focus[%d].stage_missing' % i)
            continue
        stage_index(stage)
        stages.append(stage)
        if not f.get('mechanism_trigger'):
            errors.append('focus[%d].mechanism_trigger_missing' % i)
    if len(set(stages)) != len(stages):
        errors.append('duplicate_focus_stage')
    if len(stages) > config.get('focus_cap', 3):
        errors.append('too_many_focuses')
    gaps = handoff_gaps(config)
    if gaps:
        errors.append('handoff_undeclared:' + ','.join(gaps))
    return {'ok': not errors, 'focus_stages': stages, 'handoff_missing': gaps, 'errors': errors}


def summarize(episodes):
    """Normalize episode dicts; validate every stage name against the runtime order.

    `leaf_invoked` / `triggered` are sets of stage names, so one episode can be
    invoked at locate and triggered at approach at the same time.
    """
    rows = []
    for e in episodes:
        row = {
            'task': e['task'],
            'arm': e['arm'],
            'success': bool(e.get('success')),
            'stage': e.get('stage') or None,
            'message': e.get('message') or None,
            'leaf_invoked': set(e.get('leaf_invoked') or ()),
            'triggered': set(e.get('triggered') or ()),
        }
        if row['stage'] is not None:
            stage_index(row['stage'])
        for s in row['leaf_invoked'] | row['triggered']:
            stage_index(s)
        rows.append(row)
    return rows


def by_stage(rows):
    counts = {}
    for r in rows:
        if r['success']:
            continue
        counts[r['stage']] = counts.get(r['stage'], 0) + 1
    return counts


def by_arm(rows, stages=None):
    """Per-arm counts, restricted to `stages` when given (per-focus attribution)."""
    stages = set(stages) if stages else None
    out = {}
    for r in rows:
        a = out.setdefault(r['arm'], {'episodes': 0, 'success': 0,
                                      'leaf_invoked': 0, 'triggered': 0, 'tasks': set()})
        a['episodes'] += 1
        a['success'] += int(r['success'])
        inv = r['leaf_invoked'] & stages if stages else r['leaf_invoked']
        fir = r['triggered'] & stages if stages else r['triggered']
        a['leaf_invoked'] += int(bool(inv))
        a['triggered'] += int(bool(fir))
        a['tasks'].add(r['task'])
    for a in out.values():
        a['tasks'] = sorted(a['tasks'])
    return out


def focus(rows, stages, handoff_missing=None):
    """Per-stage attribution for one or more focuses.

    `stages` is the ordered list of stages this batch is allowed to claim
    evidence about. A stage's own counts only include episodes that got there,
    so an upstream failure is reported as a blocker rather than as a failure of
    every downstream focus.
    """
    stages = list(stages)
    if not stages:
        raise ValueError('at least one focus stage is required')
    for s in stages:
        stage_index(s)
    k_first = min(stage_index(s) for s in stages)
    k_last = max(stage_index(s) for s in stages)
    failed = [r for r in rows if not r['success']]
    upstream = [r for r in failed if r['stage'] is not None and stage_index(r['stage']) < k_first]
    downstream = [r for r in failed if r['stage'] is not None and stage_index(r['stage']) > k_last]
    per = {}
    for s in stages:
        k = stage_index(s)
        here = [r for r in rows if r['stage'] is None or stage_index(r['stage']) >= k]
        fired = [r for r in here if s in r['triggered']]
        per[s] = {
            'reached': len(here),
            'invoked': sum(int(s in r['leaf_invoked']) for r in here),
            'triggered': len(fired),
            'triggered_succeeded': sum(int(r['success']) for r in fired),
            'arms': by_arm(here, [s]),
        }
    return {
        'stages': stages,
        'episodes': len(rows),
        'success': sum(int(r['success']) for r in rows),
        'upstream_blocked': len(upstream),
        'upstream_stages': sorted({r['stage'] for r in upstream}, key=stage_index),
        'downstream_failed': len(downstream),
        'downstream_stages': sorted({r['stage'] for r in downstream}, key=stage_index),
        'by_focus': per,
        'failures': by_stage(rows),
        'arms': by_arm(rows),
        'handoff_missing': list(handoff_missing or []),
    }


def priorities(f):
    """Ordered findings. Each is a measured fact plus the action it forces."""
    out = []
    if f['handoff_missing']:
        out.append({
            'level': 'high',
            'finding': 'handoff evidence not declared for: ' + ', '.join(f['handoff_missing']),
            'action': 'declare entry evidence for those stages in config.handoff before the round runs',
        })
    if f['upstream_blocked']:
        out.append({
            'level': 'high',
            'finding': '%d/%d episodes stopped before the earliest focus and are unattributed (%s)'
                       % (f['upstream_blocked'], f['episodes'], ', '.join(f['upstream_stages'])),
            'action': 'these stages are unattributed; give them their own focus or their own round, '
                      'do not read them as evidence about the registered focuses',
        })
    for stage, v in f['by_focus'].items():
        if v['invoked'] and v['triggered'] == 0:
            out.append({
                'level': 'high',
                'finding': '%s: leaf invoked in %d episodes, branch fired in 0' % (stage, v['invoked']),
                'action': 'register a trigger-conditioned test with a pre-declared observable trigger; '
                          'an untriggered batch cannot measure this stage',
            })
        elif v['triggered'] and v['triggered_succeeded'] == 0:
            out.append({
                'level': 'high',
                'finding': '%s: branch fired %d times, 0 reached full success' % (stage, v['triggered']),
                'action': 'read the post-trigger trajectory before changing the leaf again; '
                          'the failure may now sit downstream of this stage',
            })
        elif v['triggered']:
            out.append({
                'level': 'info',
                'finding': '%s: branch fired %d times, %d full success'
                           % (stage, v['triggered'], v['triggered_succeeded']),
                'action': 'this stage has usable evidence; keep it and move the budget to the next blocker',
            })
    if f['downstream_failed']:
        out.append({
            'level': 'high',
            'finding': '%d episodes failed after the last focus (%s)'
                       % (f['downstream_failed'], ', '.join(f['downstream_stages'])),
            'action': 'check the declared handoff evidence at the focus exit; add that stage as a new focus '
                      'rather than widening the current one',
        })
    arms = f['arms']
    if 'code' in arms and 'skill' in arms:
        out.append({
            'level': 'medium',
            'finding': 'code %d/%d and skill %d/%d on the same tasks'
                       % (arms['code']['success'], arms['code']['episodes'],
                          arms['skill']['success'], arms['skill']['episodes']),
            'action': 'keep one binding regression; spend the rest on parent-vs-new paired comparison',
        })
    if not out:
        out.append({'level': 'info',
                    'finding': 'batch reached and triggered every registered focus',
                    'action': 'compare new vs parent on the same tasks before widening scope'})
    return out


def packet_block(config, focus_card=None):
    """Text for the author packet: which stages this round may change, and why.

    Several stages may be open at once. What is fixed is the boundary: each
    focus has its own trigger, and each focus must stay separable in the
    results, so a later round can still tell which change did what.
    """
    gate = validate_registration(config)
    lines = ['## stages open in this round', '']
    for i, f in enumerate(config.get('focuses') or [], 1):
        lines.append('%d. %s — trigger: %s' % (i, f.get('stage', 'UNSET'), f.get('mechanism_trigger', 'UNSET')))
    if not (config.get('focuses') or []):
        lines.append('1. UNSET')
    if gate['handoff_missing']:
        lines.append('- handoff evidence still undeclared: %s' % ', '.join(gate['handoff_missing']))
    lines.append('- closed: evaluator, guards, budgets, task set')
    lines.append('')
    lines.append('Each open stage must record its own trigger and be reported separately. '
                 'A stage whose branch never fires, or whose episodes stop before it, is not evidence '
                 'about the change made there — say so instead of counting it either way.')
    lines.append('Stages outside this list stay unchanged. If a blocking stage is not open, report it '
                 'as a blocker rather than fixing it in this round.')
    if focus_card:
        lines += ['', '## measured stage distribution (last round, read-only)', '', focus_card.strip()]
    return '\n'.join(lines)


def card(f, notes=()):
    lines = ['# focus card: %s' % ', '.join(f['stages']), '']
    lines.append('episodes %d | success %d' % (f['episodes'], f['success']))
    lines.append('')
    lines.append('| focus stage | reached | invoked | branch fired | full success after firing |')
    lines.append('|---|---:|---:|---:|---:|')
    for s in f['stages']:
        v = f['by_focus'][s]
        lines.append('| %s | %d | %d | %d | %d |'
                     % (s, v['reached'], v['invoked'], v['triggered'], v['triggered_succeeded']))
    lines.append('')
    lines.append('| failed at stage | episodes |')
    lines.append('|---|---:|')
    for s in STAGES:
        if f['failures'].get(s):
            lines.append('| %s | %d |' % (s, f['failures'][s]))
    lines.append('')
    lines.append('| arm | episodes | success |')
    lines.append('|---|---:|---:|')
    for a in sorted(f['arms']):
        v = f['arms'][a]
        lines.append('| %s | %d | %d |' % (a, v['episodes'], v['success']))
    lines.append('')
    for i, p in enumerate(priorities(f), 1):
        lines.append('%d. [%s] %s' % (i, p['level'], p['finding']))
        lines.append('   -> %s' % p['action'])
    for n in notes:
        lines.append('')
        lines.append(n)
    return '\n'.join(lines)
