"""Self-contained episode directories and hash evidence.

An episode is a directory written once. ``hashes.json`` covers every file in it
except itself; verification requires exact coverage, so a file added after the
hashes fails the check.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Sequence


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def file_hashes(root: Path, *, exclude: Sequence[str] = ("hashes.json",)) -> dict[str, str]:
    root = Path(root)
    skip = set(exclude)
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in skip
    }


def write_hashes(root: Path) -> dict[str, str]:
    root = Path(root)
    hashes = file_hashes(root)
    (root / "hashes.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return hashes


def verify_hashes(root: Path) -> dict:
    root = Path(root)
    path = root / "hashes.json"
    if not path.is_file():
        return {"ok": False, "missing_manifest": True, "mismatched": [], "unlisted": []}
    expected = json.loads(path.read_text(encoding="utf-8"))
    actual = file_hashes(root)
    mismatched = sorted(rel for rel, digest in expected.items() if actual.get(rel) != digest)
    unlisted = sorted(set(actual) - set(expected))
    missing = sorted(set(expected) - set(actual))
    return {
        "ok": not mismatched and not unlisted and not missing,
        "missing_manifest": False,
        "mismatched": mismatched,
        "unlisted": unlisted,
        "missing": missing,
        "files": len(expected),
    }


def check_required(root: Path, names: Iterable[str]) -> dict:
    root = Path(root)
    missing = [name for name in names if not (root / name).is_file()]
    return {"ok": not missing, "missing": missing}


class EpisodeStore:
    """Create one episode directory exclusively and finalize its hashes."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)

    def write_json(self, name: str, value) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return path

    def write_jsonl(self, name: str, rows: Iterable[dict]) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        return path

    def finalize(self) -> dict:
        return write_hashes(self.root)
