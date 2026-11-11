"""Content-addressed artifacts, immutable snapshots, and derived projections.

One writer. Artifact files and snapshot manifests are immutable. ``head.json``
is a pointer and only moves when a snapshot is frozen.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

from .contracts import (
    Artifact,
    CodeModule,
    ContractError,
    MemoryNote,
    Op,
    PolicyArtifact,
    Procedure,
    ProgramArtifact,
    Skill,
    Snapshot,
    SnapshotView,
    Status,
    ValidationReport,
    artifact_from_dict,
)

_ARTIFACT_TYPES = (Op, CodeModule, Skill, Procedure, ProgramArtifact, PolicyArtifact, MemoryNote, ValidationReport)
_PROMOTABLE = (Op, Skill, Procedure, ProgramArtifact, PolicyArtifact, MemoryNote)
_WITH_VALIDATION = (Skill, Procedure, ProgramArtifact, PolicyArtifact)
_OP_TABLE_MODES = {"formal": frozenset({Status.VALIDATED}), "practice": frozenset({Status.CANDIDATE, Status.VALIDATED})}


def _stable_json(data) -> str:
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def _compact_sha256(payload) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _artifact_key(artifact: Artifact) -> str:
    # Op has no id field. op_id is the stable key, so a revision replaces the
    # previous version instead of aliasing it under a versioned ref.
    if isinstance(artifact, Op):
        return artifact.op_id
    return artifact.id


def _artifact_version(artifact: Artifact) -> int | None:
    version = getattr(artifact, "version", None)
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


class Registry:
    """Content-addressed artifact store with an explicit snapshot parent chain."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.artifacts_dir = self.root / "artifacts"
        self.snapshots_dir = self.root / "snapshots"
        self.head_path = self.root / "head.json"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def put(self, artifact: Artifact) -> str:
        if not isinstance(artifact, _ARTIFACT_TYPES):
            raise ContractError("put expects an artifact")
        digest = artifact.digest()
        payload = artifact.to_dict()
        payload["sha256"] = digest
        path = self.artifacts_dir / artifact.kind / f"{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_immutable(path, _stable_json(payload))
        return digest

    def get_by_digest(self, digest: str) -> Artifact:
        paths = self._paths_for_digest(digest)
        if not paths:
            raise KeyError(f"unknown artifact digest: {digest}")
        if len(paths) > 1:
            raise ContractError(f"ambiguous digest: {digest}")
        return self._read_artifact(paths[0])

    def get(self, artifact_id: str, version: int) -> Artifact:
        matches = [
            artifact
            for artifact in self._iter_artifacts()
            if _artifact_key(artifact) == artifact_id and _artifact_version(artifact) == version
        ]
        if not matches:
            raise KeyError(f"unknown artifact: {artifact_id} version {version}")
        if len(matches) > 1:
            raise ContractError(f"ambiguous artifact: {artifact_id} version {version}")
        return matches[0]

    def latest(self, artifact_id: str) -> Artifact:
        matches = [
            artifact
            for artifact in self._iter_artifacts()
            if _artifact_key(artifact) == artifact_id and _artifact_version(artifact) is not None
        ]
        if not matches:
            raise KeyError(f"unknown artifact: {artifact_id}")
        best = max(_artifact_version(artifact) for artifact in matches)
        top = [artifact for artifact in matches if _artifact_version(artifact) == best]
        if len(top) > 1:
            raise ContractError(f"ambiguous artifact: {artifact_id} version {best}")
        return top[0]

    def commit(
        self,
        refs: list[tuple[str, str]] | tuple[tuple[str, str], ...],
        label: str,
        parent: str | None = None,
        frozen: bool = False,
    ) -> Snapshot:
        unique: dict[str, str] = {}
        for item in refs:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ContractError("snapshot ref must be an (artifact_id, digest) pair")
            artifact_id, digest = item
            if artifact_id in unique and unique[artifact_id] != digest:
                raise ContractError(f"conflicting digests for {artifact_id}")
            unique[artifact_id] = digest
        if parent is not None:
            self.load(parent)
        ordered = tuple(sorted(unique.items()))
        snapshot_id = "snap_" + _compact_sha256(
            {
                "refs": [[artifact_id, digest] for artifact_id, digest in ordered],
                "parent": parent,
                "label": label,
                "frozen": frozen,
            }
        )[:16]
        snapshot = Snapshot(
            id=snapshot_id,
            refs=ordered,
            parent=parent,
            label=label,
            frozen=frozen,
        )
        self._write_immutable(self._snapshot_path(snapshot.id), _stable_json(snapshot.to_dict()))
        return snapshot

    def load(self, snapshot_id: str) -> SnapshotView:
        path = self._snapshot_path(snapshot_id)
        if not path.is_file():
            raise KeyError(f"unknown snapshot: {snapshot_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        snapshot = Snapshot.from_dict(data)
        if snapshot.id != snapshot_id:
            raise ContractError(f"snapshot id mismatch: {snapshot_id}")
        artifacts: dict[str, Artifact] = {}
        for ref_id, ref_digest in snapshot.refs:
            artifact = self.get_by_digest(ref_digest)
            if artifact.digest() != ref_digest:
                raise ContractError(f"snapshot {snapshot_id} has stale artifact {ref_id}")
            if _artifact_key(artifact) != ref_id:
                raise ContractError(
                    f"snapshot {snapshot_id} maps {ref_id} to {_artifact_key(artifact)}"
                )
            if ref_id in artifacts:
                raise ContractError(f"snapshot has duplicate artifact id: {ref_id}")
            artifacts[ref_id] = artifact
        ref_ids = [ref_id for ref_id, _digest in snapshot.refs]
        if len(ref_ids) != len(set(ref_ids)) or set(artifacts) != set(ref_ids):
            raise ContractError(f"snapshot {snapshot_id} refs are not present exactly once")
        return SnapshotView(snapshot, artifacts)

    def freeze(self, snapshot_id: str) -> Snapshot:
        view = self.load(snapshot_id)
        if view.snapshot.frozen:
            raise ContractError("cannot freeze a frozen snapshot")
        frozen = self.commit(
            view.snapshot.refs,
            label=f"freeze:{snapshot_id}",
            parent=snapshot_id,
            frozen=True,
        )
        # Hash the written snapshot bytes, not the logical payload, so a rewritten
        # file cannot keep a stale head pointer.
        file_sha = hashlib.sha256(self._snapshot_path(frozen.id).read_bytes()).hexdigest()
        self._write_pointer(
            self.head_path,
            _stable_json({"snapshot_id": frozen.id, "sha256": file_sha}),
        )
        return frozen

    def head(self) -> Snapshot | None:
        if not self.head_path.is_file():
            return None
        problems = self._head_problems()
        if problems:
            raise ContractError(problems[0])
        data = json.loads(self.head_path.read_text(encoding="utf-8"))
        view = self.load(data["snapshot_id"])
        if not view.snapshot.frozen:
            raise ContractError("head snapshot is not frozen")
        return view.snapshot

    def verify(self, snapshot_id: str) -> dict:
        problems: list[str] = []
        seen: set[str] = set()
        self._verify_snapshot(snapshot_id, problems, seen)
        problems.extend(self._head_problems())
        return {"ok": not problems, "problems": problems}

    def promote(self, snapshot_id: str, candidate_id: str, report_id: str) -> Snapshot:
        return self._change_status(snapshot_id, candidate_id, report_id, "promote")

    def demote(self, snapshot_id: str, candidate_id: str, report_id: str) -> Snapshot:
        return self._change_status(snapshot_id, candidate_id, report_id, "demote")

    def retire(self, snapshot_id: str, candidate_id: str, report_id: str) -> Snapshot:
        return self._change_status(snapshot_id, candidate_id, report_id, "retire")

    def add_revision(self, snapshot_id: str, artifact: Artifact) -> Snapshot:
        view = self.load(snapshot_id)
        self._require_mutable(view.snapshot, "revise")
        digest = self.put(artifact)
        refs = dict(view.snapshot.refs)
        key = _artifact_key(artifact)
        refs[key] = digest
        return self.commit(list(refs.items()), label=f"revise:{key}", parent=snapshot_id)

    def op_table(self, snapshot_id: str, mode: str = "formal") -> dict[str, Op]:
        try:
            allowed = _OP_TABLE_MODES[mode]
        except KeyError:
            raise ContractError(f"invalid op table mode: {mode}") from None
        view = self.load(snapshot_id)
        grouped: dict[str, list[Op]] = {}
        for artifact in view.artifacts.values():
            if isinstance(artifact, Op) and artifact.status in allowed:
                grouped.setdefault(artifact.op_id, []).append(artifact)
        table: dict[str, Op] = {}
        for op_id, ops in grouped.items():
            best = max(op.version for op in ops)
            top = [op for op in ops if op.version == best]
            if len({op.digest() for op in top}) > 1:
                raise ContractError(f"ambiguous op {op_id} version {best}")
            table[op_id] = top[0]
        return table

    def code_projection(self, snapshot_id: str) -> dict[str, CodeModule]:
        view = self.load(snapshot_id)
        modules = [artifact for artifact in view.artifacts.values() if isinstance(artifact, CodeModule)]
        projection: dict[str, CodeModule] = {}
        for artifact in view.artifacts.values():
            if not isinstance(artifact, Op) or artifact.builtin:
                continue
            found = [
                module
                for module in modules
                if module.id == artifact.implementation and module.source_sha256 == artifact.implementation_sha256
            ]
            if not found:
                raise KeyError(f"no code module {artifact.implementation} for {artifact.op_id}")
            if len(found) > 1:
                raise ContractError(f"ambiguous code module for {artifact.op_id}")
            projection[artifact.op_id] = found[0]
        return projection

    def skill_graph(self, snapshot_id: str) -> dict:
        view = self.load(snapshot_id)
        nodes = [
            artifact
            for artifact in view.artifacts.values()
            if isinstance(artifact, (Skill, Procedure))
        ]
        nodes.sort(key=lambda node: node.id)
        node_ids = {node.id for node in nodes}
        edges: list[dict] = []
        for source in nodes:
            for target in nodes:
                if source.id == target.id:
                    continue
                posted = {item.name for item in source.post}
                for name in {item.name for item in target.pre} & posted:
                    edges.append(
                        {
                            "from": source.id,
                            "to": target.id,
                            "kind": "pre_post",
                            "predicate": name,
                        }
                    )
            for code, repair_target in source.on_failure:
                if repair_target in node_ids:
                    edges.append(
                        {
                            "from": source.id,
                            "to": repair_target,
                            "kind": "repair",
                            "failure_code": code,
                        }
                    )
        edges.sort(key=lambda edge: (edge["kind"], edge["from"], edge["to"], edge.get("predicate", edge.get("failure_code"))))
        return {
            "nodes": [{"id": node.id, "kind": node.kind} for node in nodes],
            "edges": edges,
        }

    def _change_status(self, snapshot_id: str, candidate_id: str, report_id: str, decision: str) -> Snapshot:
        view = self.load(snapshot_id)
        self._require_mutable(view.snapshot, decision)
        artifact = view.artifacts.get(candidate_id)
        if artifact is None:
            raise ContractError(f"snapshot does not reference {candidate_id}")
        if isinstance(artifact, CodeModule) or not isinstance(artifact, _PROMOTABLE):
            raise ContractError("code module cannot be promoted, demoted, or retired")
        if _artifact_key(artifact) != candidate_id:
            raise ContractError(f"snapshot maps {candidate_id} to {_artifact_key(artifact)}")
        expected = Status.CANDIDATE if decision == "promote" else Status.VALIDATED
        if artifact.status is not expected:
            if decision == "promote":
                raise ContractError(f"{candidate_id} is not a candidate")
            raise ContractError(f"{candidate_id} is not validated")
        report = view.artifacts.get(report_id)
        if not isinstance(report, ValidationReport):
            if report is None:
                raise ContractError(f"snapshot does not reference report {report_id}")
            raise ContractError(f"{report_id} is not a validation report")
        if report.decision != decision:
            raise ContractError(f"report decision {report.decision!r} is not {decision!r}")
        if report.candidate_id != candidate_id:
            raise ContractError(f"report candidate_id does not match {candidate_id}")
        if report.candidate_digest != artifact.digest():
            raise ContractError(f"report candidate_digest does not match {candidate_id}")
        updated = self._transition(artifact, report, decision)
        digest = self.put(updated)
        refs = [
            (ref_id, digest if ref_id == candidate_id else old)
            for ref_id, old in view.snapshot.refs
        ]
        label = (
            f"promote:{candidate_id}:{report.validation.value}"
            if decision == "promote"
            else f"{decision}:{candidate_id}"
        )
        return self.commit(refs, label=label, parent=snapshot_id)

    @staticmethod
    def _transition(artifact: Artifact, report: ValidationReport, decision: str) -> Artifact:
        evidence = artifact.evidence + (report.id,)
        # Skill-like artifacts must carry a level while validated and must clear
        # it when demoted. Op and MemoryNote have no validation field.
        if decision == "promote":
            if isinstance(artifact, _WITH_VALIDATION):
                return replace(artifact, status=Status.VALIDATED, validation=report.validation, evidence=evidence)
            return replace(artifact, status=Status.VALIDATED, evidence=evidence)
        if decision == "demote":
            if isinstance(artifact, _WITH_VALIDATION):
                return replace(artifact, status=Status.CANDIDATE, validation=None, evidence=evidence)
            return replace(artifact, status=Status.CANDIDATE, evidence=evidence)
        if isinstance(artifact, _WITH_VALIDATION):
            return replace(artifact, status=Status.RETIRED, evidence=evidence)
        return replace(artifact, status=Status.RETIRED, evidence=evidence)

    @staticmethod
    def _require_mutable(snapshot: Snapshot, action: str) -> None:
        if snapshot.frozen:
            raise ContractError(f"cannot {action} a frozen snapshot")

    def _iter_artifacts(self) -> list[Artifact]:
        return [self._read_artifact(path) for path in self._artifact_files()]

    def _artifact_files(self) -> list[Path]:
        files: list[Path] = []
        if not self.artifacts_dir.is_dir():
            return files
        for kind_dir in sorted(self.artifacts_dir.iterdir()):
            if not kind_dir.is_dir():
                continue
            files.extend(sorted(path for path in kind_dir.glob("*.json") if path.is_file()))
        return files

    def _paths_for_digest(self, digest: str) -> list[Path]:
        paths: list[Path] = []
        if not self.artifacts_dir.is_dir():
            return paths
        for kind_dir in sorted(self.artifacts_dir.iterdir()):
            if not kind_dir.is_dir():
                continue
            path = kind_dir / f"{digest}.json"
            if path.is_file():
                paths.append(path)
        return paths

    def _read_artifact(self, path: Path) -> Artifact:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContractError(f"artifact file is not JSON: {path.name}") from exc
        if not isinstance(data, dict) or "sha256" not in data:
            raise ContractError(f"artifact file missing sha256: {path.name}")
        stored = data.pop("sha256")
        artifact = artifact_from_dict(data)
        recomputed = artifact.digest()
        if stored != recomputed or path.stem != recomputed:
            raise ContractError(f"artifact digest mismatch: {path.name}")
        return artifact

    def _snapshot_path(self, snapshot_id: str) -> Path:
        return self.snapshots_dir / f"{snapshot_id}.json"

    def _write_immutable(self, path: Path, text: str) -> None:
        if path.exists():
            if path.read_text(encoding="utf-8") != text:
                raise ContractError(f"refusing to overwrite immutable file: {path.name}")
            return
        self._write_pointer(path, text)

    def _write_pointer(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def _head_problems(self) -> list[str]:
        if not self.head_path.is_file():
            return []
        problems: list[str] = []
        try:
            data = json.loads(self.head_path.read_text(encoding="utf-8"))
            snapshot_id = data["snapshot_id"]
            expected = data["sha256"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            return [f"head not loadable: {exc}"]
        path = self._snapshot_path(snapshot_id)
        if not path.is_file():
            return [f"head snapshot missing: {snapshot_id}"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            problems.append("head snapshot hash mismatch")
        try:
            snapshot = Snapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ContractError, KeyError, TypeError) as exc:
            problems.append(f"head snapshot not loadable: {exc}")
            return problems
        if snapshot.id != snapshot_id:
            problems.append("head snapshot id mismatch")
        if not snapshot.frozen:
            problems.append("head snapshot is not frozen")
        return problems

    def _verify_snapshot(self, snapshot_id: str, problems: list[str], seen: set[str]) -> None:
        if snapshot_id in seen:
            problems.append(f"parent cycle: {snapshot_id}")
            return
        seen.add(snapshot_id)
        path = self._snapshot_path(snapshot_id)
        if not path.is_file():
            problems.append(f"missing snapshot: {snapshot_id}")
            return
        try:
            snapshot = Snapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ContractError, KeyError, TypeError) as exc:
            problems.append(f"snapshot not loadable: {snapshot_id}: {exc}")
            return
        if snapshot.id != snapshot_id:
            problems.append(f"snapshot id mismatch: {snapshot_id}")
        ref_ids = [ref_id for ref_id, _digest in snapshot.refs]
        if len(ref_ids) != len(set(ref_ids)):
            problems.append(f"duplicate ref ids in {snapshot_id}")
        for ref_id, ref_digest in snapshot.refs:
            self._verify_ref(ref_id, ref_digest, problems)
        if snapshot.parent is None:
            return
        parent = self._snapshot_path(snapshot.parent)
        if not parent.is_file():
            problems.append(f"missing parent: {snapshot.parent}")
            return
        # Parent age is the pointer. A loadable parent is enough; mtime is not
        # a snapshot clock and would flake when two writes share a timestamp.
        self._verify_snapshot(snapshot.parent, problems, seen)

    def _verify_ref(self, ref_id: str, ref_digest: str, problems: list[str]) -> None:
        paths = self._paths_for_digest(ref_digest)
        if not paths:
            problems.append(f"missing artifact {ref_digest} for {ref_id}")
            return
        if len(paths) > 1:
            problems.append(f"ambiguous digest {ref_digest}")
            return
        try:
            artifact = self._read_artifact(paths[0])
        except (ContractError, KeyError, TypeError, ValueError) as exc:
            problems.append(f"artifact digest mismatch: {ref_digest}: {exc}")
            return
        if artifact.digest() != ref_digest:
            problems.append(f"artifact digest mismatch: {ref_digest}")
        if _artifact_key(artifact) != ref_id:
            problems.append(f"ref {ref_id} does not match artifact {_artifact_key(artifact)}")
