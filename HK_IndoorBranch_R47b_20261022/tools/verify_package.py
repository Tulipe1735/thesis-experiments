"""Verify an extracted handoff folder or its ZIP without extracting it.

Usage: python -B tools/verify_package.py [folder-or-zip]
Only Python's standard library is required. Does not modify scene files.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import sys
import zipfile


def safe_name(name):
    path = PurePosixPath(name)
    if (not name or "\\" in name or path.is_absolute()
            or any(p in (".", "..") or ":" in p for p in path.parts)
            or str(path) != name):
        raise ValueError("Unsafe package path: " + repr(name))
    return name


def digest(stream):
    sha = hashlib.sha256()
    size = 0
    while True:
        block = stream.read(8 * 1024 * 1024)
        if not block:
            return size, sha.hexdigest()
        sha.update(block)
        size += len(block)


def verify(target):
    archive = None
    if target.is_file():
        archive = zipfile.ZipFile(target)
        names = [i.filename for i in archive.infolist() if not i.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entries")
        for name in names:
            safe_name(name)
        manifests = [n for n in names if n.endswith("/MANIFEST.json")]
        if len(manifests) != 1:
            raise ValueError("Expected exactly one root MANIFEST.json")
        prefix = manifests[0][:-len("MANIFEST.json")]
        if any(not n.startswith(prefix) for n in names):
            raise ValueError("ZIP contains entries outside the package root")
        present = {n[len(prefix):] for n in names}

        def open_file(name):
            return archive.open(prefix + safe_name(name))
    else:
        root = target.resolve(strict=True)
        present = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}

        def open_file(name):
            path = (root / safe_name(name)).resolve(strict=True)
            if not path.is_relative_to(root):
                raise ValueError("File resolves outside package: " + name)
            return path.open("rb")

    try:
        with open_file("MANIFEST.json") as file:
            manifest_raw = file.read()
        manifest = json.loads(manifest_raw)
        if manifest.get("format") != "HK_INDOOR_HANDOFF_MANIFEST_V1":
            raise ValueError("Unsupported manifest")
        files = manifest["files"]
        for name in files:
            safe_name(name)
        expected = set(files) | {"MANIFEST.json", "SHA256SUMS.txt"}
        missing = expected - present
        if missing:
            raise ValueError("Missing files: " + ", ".join(sorted(missing)))
        with open_file("SHA256SUMS.txt") as file:
            sums = {}
            for line in file.read().decode("utf-8").splitlines():
                value, name = line.split("  ", 1)
                safe_name(name)
                if name in sums:
                    raise ValueError("Duplicate checksum entry")
                sums[name] = value
        if set(sums) != set(files) | {"MANIFEST.json"}:
            raise ValueError("Checksum list differs from manifest")
        if sums["MANIFEST.json"] != hashlib.sha256(manifest_raw).hexdigest():
            raise ValueError("Manifest checksum mismatch")
        total = 0
        for name, record in sorted(files.items()):
            with open_file(name) as file:
                size, value = digest(file)
            if size != record["bytes"] or value != record["sha256"] or value != sums[name]:
                raise ValueError("File size or SHA-256 mismatch: " + name)
            total += size
            print("OK  " + name, flush=True)
        extras = sorted(present - expected)
        if extras:
            print("Additional files (not part of frozen baseline): " + ", ".join(extras))
        result = {"verified": True, "files": len(files), "payload_bytes": total,
                  "baseline": manifest["baseline"], "additional_files": extras}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    finally:
        if archive:
            archive.close()


if __name__ == "__main__":
    try:
        target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
        verify(target)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print("VERIFICATION FAILED: " + str(error), file=sys.stderr)
        sys.exit(1)
