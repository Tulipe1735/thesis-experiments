"""Inspect the editable library, or explicitly freeze one program."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'experiments/grow_up_harness_v2')]
from harness import artifact_mapping as M, artifact_v2 as A, artifact as V1
from harness.library import Library, BundleStore, read_bundle, write_bundle


def verify(path):
    bundle = read_bundle(path)
    payload = {k: v for k, v in bundle.items() if k != 'bundle_id'}
    expected = bundle['program'] + '@' + M.digest_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))[:12]
    if bundle['bundle_id'] != expected:
        raise ValueError('bundle content changed under a fixed identity')
    if bundle['family'] == 'T01':
        artifact = V1.Artifact.model_validate(bundle['artifacts'][bundle['ref']])
        if (f'{artifact.id}@{V1.digest(artifact)}' != bundle['ref']
                or V1.generate_code(artifact) != bundle['views']['code']):
            raise ValueError('T01 projection differs from frozen artifact')
    else:
        for ref, data in bundle['artifacts'].items():
            if A.ref(A.parse(data)) != ref:
                raise ValueError(f'artifact changed: {ref}')
    for digest, source in bundle['sources'].items():
        if A.sha_text(source) != digest:
            raise ValueError(f'source changed: {digest}')
    if bundle['family'] != 'T01':
        store = BundleStore({}, bundle['artifacts'], bundle['sources'])
        if store.code(bundle['ref']) != bundle['views']['code']:
            raise ValueError('code projection differs from frozen artifacts')
    return bundle['bundle_id']


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', type=Path, default=ROOT / 'experiments/grow_up_harness_v2/library')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    f = sub.add_parser('freeze')
    f.add_argument('program')
    f.add_argument('--out', type=Path, required=True)
    v = sub.add_parser('verify')
    v.add_argument('bundle', type=Path)
    d = sub.add_parser('diff')
    d.add_argument('before', type=Path)
    d.add_argument('after', type=Path)
    args = p.parse_args(argv)
    if args.command == 'verify':
        print(verify(args.bundle))
    elif args.command == 'diff':
        before, after = read_bundle(args.before), read_bundle(args.after)
        for key in ('ref', 'evaluator', 'components'):
            if before[key] != after[key]:
                print(json.dumps({'field': key, 'before': before[key], 'after': after[key]}, ensure_ascii=False))
        for key in ('code_sha256', 'skill_sha256', 'ir_sha256', 'runtime_interface'):
            a, b = before['views']['manifest'][key], after['views']['manifest'][key]
            if a != b:
                print(json.dumps({'field': key, 'before': a, 'after': b}, ensure_ascii=False))
        if before['bundle_id'] == after['bundle_id']:
            print('identical frozen bundle')
        else:
            print(before['bundle_id'], '->', after['bundle_id'])
    elif args.command == 'list':
        for name, spec in Library(args.library).tree['programs'].items():
            roles = ', '.join(k.removesuffix('_ref') for k in spec.get('components', {}) if k.endswith('_ref'))
            print(f'{name}: {spec["family"]} {roles}')
    else:
        bundle = Library(args.library).freeze(args.program)
        write_bundle(args.out, bundle)
        print(bundle['bundle_id'], args.out)


if __name__ == '__main__':
    main()
