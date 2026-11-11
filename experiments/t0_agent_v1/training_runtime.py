"""Load hash-verified registered runtime sources from a small local snapshot.

Only small trusted source files are read. Historical data and the checkout are
left untouched; the numeric worker entry lives in a disposable temporary folder.
"""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import types

from .common import ROOT, read

_cache = None
_provenance = None


def ensure_runtime():
    global _cache, _provenance
    if _provenance is not None:
        return _provenance
    registry = read(ROOT/'experiments/t0_agent_v1/tp01_training_20261026_003/registration.json')
    names = ('plant.py', 'isolation/worker.py', 'isolation/_entry.py')
    sources, records = {}, []
    reference = ROOT/'experiments/t0_agent_v1/runtime_reference_v2'
    commit = None
    for name in names:
        path = 'experiments/grow_up_v2/'+name
        file = ROOT/path
        snapshot = reference/name
        if file.exists():
            source, origin = file.read_bytes(), 'working_tree'
        elif snapshot.exists():
            source, origin = snapshot.read_bytes(), 'verified_local_snapshot'
        else:
            if commit is None:
                commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            source = subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
            origin = 'git:'+commit
        digest = hashlib.sha256(source).hexdigest()
        if digest != registry['source_sha256'][path]:
            raise ValueError('Trusted runtime hash mismatch: '+path)
        sources[name] = source
        records.append(dict(path=path, sha256=digest, source=origin))
    _cache = tempfile.TemporaryDirectory(prefix='tp01-trusted-runtime-')
    temporary = Path(_cache.name)
    (temporary/'_entry.py').write_bytes(sources['isolation/_entry.py'])
    for package in ('experiments.grow_up_v2', 'experiments.grow_up_v2.isolation'):
        if package not in sys.modules:
            module = types.ModuleType(package)
            module.__path__ = []
            sys.modules[package] = module
    for module_name, source_name, file in (
        ('experiments.grow_up_v2.plant', 'plant.py', ROOT/'experiments/grow_up_v2/plant.py'),
        ('experiments.grow_up_v2.isolation.worker', 'isolation/worker.py', temporary/'worker.py'),
    ):
        module = types.ModuleType(module_name)
        module.__file__ = str(file)
        module.__package__ = module_name.rsplit('.', 1)[0]
        sys.modules[module_name] = module
        exec(compile(sources[source_name], str(file), 'exec'), module.__dict__)
    _provenance = dict(exact_registered_sources=True, sources=records,
        workspace_restored=False, historical_data_copied=False, temporary_worker_source=True)
    return _provenance
