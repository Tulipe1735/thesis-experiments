"""Paths and immutable evidence helpers for the engineering T0 pilot."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
REFERENCE = ROOT / 'grasp_optimization/episodes/final_reference_1000'


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    # Validate serialization before exclusive creation, so invalid values cannot
    # leave a truncated evidence file that looks like a completed record.
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(text)


def append_event(path, value):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')


def source_hashes():
    files = list(PACKAGE.glob('*.py'))
    files += [ROOT / 'grasp_optimization' / name for name in (
        'pantry_robot.py', 'vision_grasp.py', 'vision_grasp_v2.py', 'arm_planner.py',
        'rgbd_cup.py', 'astra_gateway.py', 'verify_grasp.py')]
    return {relative(path): sha(path) for path in sorted(files)}
