"""Read-only attention tooling for T03 rounds.

Two modes, neither of which executes physics or writes into a run directory:

    python -B calibration/t03_focus.py precheck configs/<next>.json [--previous runs/<last>]
    python -B calibration/t03_focus.py report   runs/<run> [--config <cfg>] [--write out.md]

`precheck` exits non-zero when the round cannot be attributed: no focus stages,
a focus without its own trigger, or undeclared handoff evidence. Several focus
stages may be open at once — the gate checks attribution, not count.

`report` prints the focus card for a finished run: per-focus reached / invoked /
fired / succeeded, where episodes stopped, and what the next round should do.
Use `--packet --config <next>.json` to emit the author-packet block instead.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'experiments/grow_up_harness_v2')]
from harness import t03_handoff as H


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def episodes(run):
    rows = []
    for vp in sorted(run.rglob('verdict.json')):
        v = read(vp)
        parts = vp.relative_to(run).parts
        if 'negative' in parts or 'control_negative' in parts:
            continue
        arm = parts[-2] if len(parts) >= 2 else 'unknown'
        decisions = H.read_decisions(vp.parent)
        binding = vp.parent / 'root_binding.json'
        if binding.exists():
            stages = read(binding).get('decision_stages', {})
            decisions = {stages.get(stage, stage): value for stage, value in decisions.items()}
        err = v.get('execution_error') or {}
        rows.append({
            'task': parts[-3] if len(parts) >= 3 else vp.parent.name,
            'arm': arm,
            'success': v.get('verified_task_success'),
            'stage': err.get('stage'),
            'message': err.get('message'),
            'leaf_invoked': [s for s, (inv, _f) in decisions.items() if inv],
            'triggered': [s for s, (_i, fired) in decisions.items() if fired],
        })
    return rows


def infer_stages(run, rows):
    """Fallback for runs that predate `focuses`: stages that wrote a decision record.

    Never infer from failures: an early locate failure would make the whole run
    look like a locate study.
    """
    stages = {H.decision_stage(p.parent) for p in run.rglob('verdict.json')}
    stages = [s for s in stages if s]
    if stages:
        return sorted(set(stages), key=H.stage_index)
    seen = {r['stage'] for r in rows if r['stage']}
    return sorted(seen, key=H.stage_index)[:1] or [H.STAGES[-1]]


def focus_card(run, config=None, stages=None):
    run = Path(run)
    cfg = read(config) if config else (read(run / 'config.json') if (run / 'config.json').exists() else {})
    rows = H.summarize(episodes(run))
    if not rows:
        raise SystemExit('no verdict.json under %s' % run)
    declared = stages or [f['stage'] for f in (cfg.get('focuses') or [])]
    origin = 'declared' if declared else 'inferred: stages that wrote a decision record'
    stages = declared or infer_stages(run, rows)
    f = H.focus(rows, stages, H.handoff_gaps(cfg))
    return f, H.card(f, notes=[
        'focus stages: %s (%s)' % (', '.join(stages), origin),
        'source: %s (read-only; no physics, no verdict rewritten)' % run.name,
    ])


def precheck(config, previous):
    cfg = read(config)
    gate = H.validate_registration(cfg)
    lines = ['# precheck: %s' % Path(config).name, '']
    for i, f in enumerate(cfg.get('focuses') or [], 1):
        lines.append('%d. %s — %s' % (i, f.get('stage', 'MISSING'), f.get('mechanism_trigger', 'MISSING')))
    for stage, fields in (cfg.get('handoff') or {}).items():
        lines.append('handoff[%s]: %s' % (stage, ', '.join(fields)))
    if gate['handoff_missing']:
        lines.append('handoff undeclared: %s' % ', '.join(gate['handoff_missing']))
    if previous:
        _f, card = focus_card(previous)
        lines += ['', H.packet_block(cfg, card)]
    else:
        lines += ['', H.packet_block(cfg)]
    print('\n'.join(lines))
    if not gate['ok']:
        print('\nBLOCKED: %s' % '; '.join(gate['errors']), file=sys.stderr)
        raise SystemExit(2)
    print('\nOK: attributable round', file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='mode', required=True)

    a = sub.add_parser('precheck', help='gate a new round config before it runs')
    a.add_argument('config', type=Path)
    a.add_argument('--previous', type=Path, help='finished run whose stage distribution feeds the packet')

    b = sub.add_parser('report', help='focus card for a finished run')
    b.add_argument('run', type=Path)
    b.add_argument('--config', type=Path)
    b.add_argument('--stage', action='append', choices=H.STAGES,
                   help='focus stage to attribute; repeatable')
    b.add_argument('--write', type=Path)
    b.add_argument('--packet', action='store_true',
                   help='emit the author-packet block for --config (the NEXT round)')

    args = p.parse_args(argv)
    if args.mode == 'precheck':
        precheck(args.config, args.previous)
        return
    f, card = focus_card(args.run, args.config, args.stage)
    text = card
    if args.packet:
        if not args.config:
            raise SystemExit('--packet needs --config <next round config>')
        text = H.packet_block(read(args.config), card)
    if args.write:
        Path(args.write).write_text(text + '\n', encoding='utf-8')
        print('wrote', args.write)
    print(text)


if __name__ == '__main__':
    main()
