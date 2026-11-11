"""Two views of one artifact: executable code and an immutable callable skill card."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from . import artifact as V1, artifact_v2 as V2

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = 'artifact.mapping.v1'


def digest_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Views:
    family: str
    ref: str
    code: str
    card: str
    manifest: dict

    def resolve(self, call, public_params):
        if not isinstance(call, dict) or set(call) != {'artifact_ref', 'params'}:
            raise ValueError('skill call requires exactly artifact_ref and params; source/code is not accepted')
        if call['artifact_ref'] != self.ref:
            raise ValueError(f'artifact_ref must be {self.ref}')
        if not isinstance(call['params'], dict) or set(call['params']) != {'object_count', 'hold_s'}:
            raise ValueError('params requires exactly object_count and hold_s')
        for key in ('object_count', 'hold_s'):
            if type(call['params'][key]) not in (int, float) or call['params'][key] != public_params[key]:
                raise ValueError(f'params.{key} must equal the public task binding')
        if digest_text(self.code) != self.manifest['code_sha256']:
            raise ValueError('bound code differs from the mapped artifact')
        return self.code


def project(family, spec):
    if 'bundle' in spec:
        from .library import read_bundle
        bundle = read_bundle(ROOT / Path(spec['bundle']))
        if bundle['family'] != family:
            raise ValueError('bundle family does not match requested family')
        return Views(family, bundle['ref'], **bundle['views'])
    if family == 'T01':
        path = ROOT / spec['artifact']
        artifact = V1.load(path)
        ref = f'{artifact.id}@{V1.digest(artifact)}'
        code, description = V1.generate_code(artifact), V1.generate_skill(artifact)
        ir = artifact.ir.model_dump(mode='json')
        native = 'T01 five-function Cartesian/waist interface, preserved exactly from artifact code'
        provenance = {'artifact': spec['artifact'], 'artifact_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'artifact_schema': V1.SCHEMA_VERSION, 'artifact_digest': V1.digest(artifact)}
    elif family in ('T02', 'T03'):
        tree = json.loads((ROOT / spec.get('tree', 'experiments/grow_up_harness_v2/artifacts_v2/task_tree_v2.json')).read_text())
        store = V2.Store(ROOT / spec['store'], tree, read_only=True)
        ref = spec['artifact_ref']
        artifact = store.load(ref)
        code, description = store.code(ref), store.skill(ref)
        ir = artifact.model_dump(mode='json', by_alias=True)
        native = ('T02 init/act bounded-joint interface, preserved exactly from artifact code' if family == 'T02' else
                  'T03 numeric init/act route provider; trusted t03_runtime checks IK and reuses unchanged grasp/place stages')
        native = spec.get('runtime_interface', native)
        provenance = {'store': spec['store'], 'artifact_schema': V2.SCHEMA, 'artifact_ref': ref,
                      'source_ledger_sha256': hashlib.sha256((ROOT / spec['store'] / 'ledger.jsonl').read_bytes()).hexdigest()}
    else:
        raise ValueError(f'unsupported family {family}')
    return mapped_views(family, ref, code, description, ir, native, provenance)


def mapped_views(family, ref, code, description, ir, native, provenance):
    """One mapping algorithm for legacy stores and the portable library."""
    binding = {'artifact_ref': ref, 'params': {'object_count': 3 if family == 'T02' else 1, 'hold_s': 1.0}}
    manifest = {'schema': SCHEMA, 'family': family, 'artifact_ref': ref,
                'ir_sha256': digest_text(json.dumps(ir, sort_keys=True, ensure_ascii=False)),
                'code_sha256': digest_text(code), 'runtime_interface': native, 'provenance': provenance}
    card = ('# Callable artifact skill\n\n' + description + '\n## Invocation binding\n\n'
            + 'Select this exact artifact_ref and bind the public task parameters. The runtime invokes the frozen '
            + 'implementation; do not translate the prose into new control code.\n'
            + 'Runtime interface: ' + native + '\nCode SHA256: ' + manifest['code_sha256']
            + '\nIR SHA256: ' + manifest['ir_sha256'] + '\n\n```json\n'
            + json.dumps(binding, ensure_ascii=False, indent=2) + '\n```\n')
    manifest['skill_sha256'] = digest_text(card)
    return Views(family, ref, code, card, manifest)
