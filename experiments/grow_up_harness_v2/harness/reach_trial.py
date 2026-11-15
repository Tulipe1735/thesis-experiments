"""Evaluator-side reach trial and gap attribution (GROW_UP_ROOT_DOWN_REVISE_20261113 §2.1.1 step 1).

After a node fails, the K_v1 reference runs once from that node's entry checkpoint to the
end of the node's tool and is judged by the tool boundary check. A failed trial moves the
gap to the node upstream. No policy sees a trial and no column counts it as success.

The reference is the same K_v1 stage code, without truth. A trial therefore tests nothing
when the failed executor is K_v1 itself (it replays the failure), and attribution applies
only to nodes whose registered calibration on non-reference executors enables it.
"""
from pathlib import Path

from . import kernel as K
from experiments.t0_agent_v1.common import read, relative


def node_label(template, index):
    """Checkpoint k is the entry of chain node k; labels match the checkpoint names."""
    tool, stage = K.stages(template)[index]
    return f'{index:02d}_{tool}_{stage}'


def reach_trial(case, entry, out, kernel, caps):
    snap = K.read_checkpoint(entry)
    if snap['next'] is None:
        raise ValueError('checkpoint closes the chain; there is no node to trial')
    chain = K.stages(snap['template'])
    tool = snap['next'][0]
    stop = max(i for i, (t, _) in enumerate(chain) if t == tool) + 1
    result = K.execute(case, out, kernel, caps, resume=entry, stop=stop, checkpoints=False)
    rows = read(Path(out) / 'tools.json')
    # One boundary row per earlier tool, then the trial's own row.
    if len(rows) != K.CHAINS[snap['template']].index(tool) + 1:
        raise RuntimeError(f'trial left no {tool} boundary: {result["error"]}')
    return {'entry': relative(Path(entry)), 'node': snap['done'], 'label': node_label(snap['template'], snap['done']),
            'tool': tool, 'reference': K.VERSION, 'reachable': bool(rows[-1]['truth_ok']),
            'trial_error': result['error'], 'boundary': rows[-1], 'episode': relative(Path(out))}


def calibrate(rows, limit, min_trials):
    """Per-node false "unreachable" rate on entries the failed-side executor got through.

    rows: {'node', 'reachable', 'entry_passed'}; entry_passed means a non-reference
    executor passed the node from that same entry. A node is enabled with at least
    min_trials such trials and a rate <= limit; above the limit the reference cannot be
    trusted there (untestable); below min_trials it is uncalibrated.
    """
    table = {}
    for row in rows:
        if row['entry_passed']:
            t = table.setdefault(row['node'], dict(trials=0, unreachable=0))
            t['trials'] += 1
            t['unreachable'] += not row['reachable']
    for t in table.values():
        t['false_unreachable_rate'] = t['unreachable'] / t['trials']
        t['status'] = ('uncalibrated' if t['trials'] < min_trials
                       else 'enabled' if t['false_unreachable_rate'] <= limit else 'untestable')
    return table


def attribute(trial, executor_is_reference, calibration):
    """Gap class of one failed node: node, upstream, kernel_gap, untestable or uncalibrated."""
    if executor_is_reference:
        return {'class': 'untestable', 'reason': 'reference is the failed executor; the trial is a replay'}
    status = calibration.get(trial['node'], {}).get('status', 'uncalibrated')
    if status != 'enabled':
        return {'class': status, 'reason': f'node calibration status {status}'}
    if trial['reachable']:
        return {'class': 'node', 'reason': 'reference passes from this entry'}
    if trial['node'] == 0:
        return {'class': 'kernel_gap', 'reason': 'reference fails at the first node of the chain'}
    return {'class': 'upstream', 'reason': 'reference fails from this entry', 'to': trial['node'] - 1}


def attributed_rates(rows):
    """Raw and attributed pass rates per node; denominators stay the raw reach counts.

    rows: {'node', 'passed', 'attribution'} for every node an episode reached. A failure
    classed upstream counts against the node before it; every other class stays put.
    """
    table = {}
    for row in rows:
        table.setdefault(row['node'], dict(reached=0, raw_failed=0, attributed_failed=0))['reached'] += 1
    for row in rows:
        if row['passed']:
            continue
        table[row['node']]['raw_failed'] += 1
        moved = (row.get('attribution') or {}).get('class') == 'upstream'
        target = table.setdefault(row['node'] - 1 if moved else row['node'],
                                  dict(reached=0, raw_failed=0, attributed_failed=0))
        target['attributed_failed'] += 1
    for t in table.values():
        t['raw_p'] = (t['reached'] - t['raw_failed']) / t['reached'] if t['reached'] else None
        t['attributed_p'] = (t['reached'] - t['attributed_failed']) / t['reached'] if t['reached'] else None
    return table
