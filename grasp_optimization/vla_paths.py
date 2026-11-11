"""Read existing VLA assets; keep all runtime caches inside writable temporary storage."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREVIOUS = Path(json.loads((ROOT/'source_provenance.json').read_text())['source_root'])
WORK = Path(os.environ.get('G1_VLA_WORK', str(PREVIOUS.parent.parent/'work')))
CACHE = Path(os.environ.get('G1_VLA_CACHE', '/tmp/grasp-vla-runtime'))


def configure_cache():
    for name, folder in [('HF_HOME', 'hf-cache'), ('TORCH_HOME', 'torch-cache'),
                         ('TRITON_CACHE_DIR', 'triton-cache'), ('TORCHINDUCTOR_CACHE_DIR', 'torchinductor-cache'),
                         ('XDG_CACHE_HOME', 'runtime-cache')]:
        os.environ[name] = str(CACHE/folder)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
    os.environ['WANDB_MODE'] = 'disabled'
