"""T02-specific slot binding and fail-closed batch execution."""
from harness import artifact as A


def bind_slot(record, slot):
    if slot not in record.ir.slots:
        raise ValueError(f'unknown tray slot {slot}')
    data=record.model_dump(mode='json')
    bound=0
    for phase in data['ir']['phases'].values():
        for step in phase:
            if 'slot' in step.get('to',{}):
                step['to']['slot']=slot
                bound+=1
    if not bound:
        raise ValueError('artifact has no slot-bearing motion to bind')
    return A.Artifact.model_validate(data)


def execute_batch(commands, execute, *, phase, log):
    for command in commands:
        if command['op']=='finish':return None
        replies=execute(command)
        log({'phase':phase,'command':command,'replies':replies})
        failed=next((r for r in replies
                     if (r.get('guard') or (r.get('status') if command['op'] != 'wait'
                                            else r.get('status', 'EXECUTED')))
                     not in ('EXECUTED','POSE_FEASIBLE')),None)
        if failed is not None:
            return {'phase':phase,'command':command,'reason':'command returned non-success status','response':failed}
    return None


def stable_slot(rows, cup_body, slot_xy, tolerance_m=.015, hold_s=1.):
    """A terminal one-second window must satisfy both tray and slot predicates."""
    from experiments.t0_agent_v1.tray_verify import tray_predicate
    from harness.local_reach_v3 import timing_quality
    import math
    timing_quality([r['time'] for r in rows])
    since = previous = None
    for row in rows:
        cup = row['cups'][cup_body]
        at_slot = (tray_predicate(cup) and cup['cup_tilt_deg'] <= 5.
                   and math.dist(cup['cup_position_tray_m'][:2],slot_xy) <= tolerance_m)
        if not at_slot:
            since = None
        elif since is None or (previous is not None and row['time']-previous > .051):
            since = row['time']
        previous = row['time']
    duration = 0. if since is None or not rows else rows[-1]['time']-since
    return {'terminal_slot_hold_s':duration, 'stable_slot_success':duration >= hold_s-1e-8}
