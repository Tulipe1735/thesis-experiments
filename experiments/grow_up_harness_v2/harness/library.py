"""Editable artifacts; explicit, portable freezes of only the selected program.

Only ``freeze`` computes release identities. Reading a frozen bundle never scans a
repository, follows an old run, or consults a mutable library.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from . import artifact as V1, artifact_v2 as V2, artifact_mapping as M

SCHEMA = 'artifact.bundle.v1'


def read_bundle(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data['schema'] != SCHEMA:
        raise ValueError('unsupported artifact bundle schema')
    return data


class BundleStore(V2.Store):
    """Reuse the existing compiler against an in-memory artifact closure."""
    def __init__(self, tree, artifacts, sources):
        self.tree, self.artifacts, self.sources = tree, artifacts, sources
        self.nodes = {node['id']: node for node in tree.get('nodes', [])}
        self.read_only = True

    def load(self, artifact_ref):
        return V2.parse(self.artifacts[artifact_ref])

    def source(self, digest):
        return self.sources[digest]

    def refs(self):
        return sorted(self.artifacts)

    def stats(self, artifact_ref):
        return {'status': 'candidate', 'uses': 0, 'successes': 0, 'evidence': []}


class Library:
    def __init__(self, root):
        self.root = Path(root)
        self.tree = yaml.safe_load((self.root / 'tree.yaml').read_text(encoding='utf-8'))

    def freeze(self, name):
        """Compile editable leaves once; paths are excluded from the identity."""
        spec = self.tree['programs'][name]
        if spec['family'] == 'T01':
            artifact = V1.Artifact.model_validate(yaml.safe_load(
                (self.root / spec['artifact']).read_text(encoding='utf-8')))
            ref = f'{artifact.id}@{V1.digest(artifact)}'
            view = M.mapped_views('T01', ref, V1.generate_code(artifact), V1.generate_skill(artifact),
                artifact.ir.model_dump(mode='json'), spec['runtime_interface'],
                {'artifact_schema': V1.SCHEMA_VERSION, 'artifact_digest': V1.digest(artifact)})
            artifacts = {ref: artifact.model_dump(mode='json', by_alias=True)}
            sources, components = {}, {}
        else:
            artifacts, sources, resolved = {}, {}, {}
            active = set()

            def compile_artifact(key, root_source=None):
                if key in active:
                    raise ValueError(f'artifact cycle through {key}')
                if key in resolved:
                    return resolved[key]
                active.add(key)
                path = self.root / self.tree['artifacts'][key]
                data = yaml.safe_load(path.read_text(encoding='utf-8'))
                if data['kind'] == 'leaf':
                    source = root_source if root_source is not None else (
                        path.parent / data['implementation']['source']).read_text(encoding='utf-8')
                    digest = V2.sha_text(source)
                    sources[digest] = source
                    data['implementation'] = {'language': 'python', 'source_sha256': digest}
                else:
                    for step in data['ir']:
                        step['use'] = compile_artifact(step['use'])
                artifact = V2.parse(data)
                if artifact.task_node not in {n['id'] for n in self.tree['nodes']}:
                    raise ValueError(f'unknown task node {artifact.task_node}')
                artifact_ref = V2.ref(artifact)
                artifacts[artifact_ref] = artifact.model_dump(mode='json', by_alias=True)
                resolved[key] = artifact_ref
                active.remove(key)
                return artifact_ref

            components = {k: compile_artifact(v) if k.endswith('_ref') else v
                          for k, v in spec.get('components', {}).items()}
            root_source = None
            if components:
                root_source = ('def act(observation, task, state):\n'
                    '    return {"action":{"op":"done"},"state":' + repr(components) + '}\n')
            ref = compile_artifact(spec['root'], root_source)
            store = BundleStore(self.tree, artifacts, sources)
            view = M.mapped_views(spec['family'], ref, store.code(ref), store.skill(ref),
                store.load(ref).model_dump(mode='json', by_alias=True), spec['runtime_interface'],
                {'artifact_schema': V2.SCHEMA, 'artifact_ref': ref})
        payload = {'schema': SCHEMA, 'program': name, 'family': spec['family'], 'ref': ref,
            'components': components, 'evaluator': spec.get('evaluator'),
            'artifacts': artifacts, 'sources': sources,
            'views': {'code': view.code, 'card': view.card, 'manifest': view.manifest}}
        # Mapping and runtime/evaluator contracts belong to a release as well.
        identity = M.digest_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        return {'bundle_id': f'{name}@{identity[:12]}', **payload}

    def save_tree(self):
        (self.root / 'tree.yaml').write_text(yaml.safe_dump(self.tree, allow_unicode=True,
                                                        sort_keys=False), encoding='utf-8')


def write_bundle(path, bundle):
    """A release is a single file, created exclusively."""
    text = json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with Path(path).open('x', encoding='utf-8') as handle:
        handle.write(text)
