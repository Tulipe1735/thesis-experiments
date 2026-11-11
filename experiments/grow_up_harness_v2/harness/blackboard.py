"""Episode-local blackboard: values passed between ops, never a verdict.

Two hard rules make the blackboard safe to use:

1. It carries only numbers, strings and flat lists of those. No objects, no
   callables, no ``numpy`` arrays (an array would not survive the worker
   boundary and would fork the hash).
2. It never satisfies a postcondition. ``post`` is decided by
   :mod:`harness.predicates` on plant state; a blackboard entry that looks
   like ``target_lifted`` is just a string key.

The runtime writes every merged snapshot to ``blackboard.jsonl`` so the
evidence shows what crossed between steps.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

KEY = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
MAX_ENTRIES = 32
MAX_LIST = 64
MAX_STRING = 512


class BlackboardError(ValueError):
    """A blackboard entry is not a legal value."""


Scalar = float | str
Value = Scalar | tuple[Scalar, ...]


def _scalar(value: Any) -> Scalar:
    if isinstance(value, str):
        if not value or len(value) > MAX_STRING:
            raise BlackboardError("blackboard strings must be 1..512 chars")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlackboardError("blackboard values must be finite numbers or strings")
    if not math.isfinite(value):
        raise BlackboardError("blackboard numbers must be finite")
    return float(value)


def _value(value: Any) -> Value:
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_LIST:
            raise BlackboardError("blackboard lists max 64 entries")
        return tuple(_scalar(item) for item in value)
    return _scalar(value)


def normalize(data: Any) -> tuple[tuple[str, Value], ...]:
    if not isinstance(data, dict):
        raise BlackboardError("blackboard must be a dict")
    if len(data) > MAX_ENTRIES:
        raise BlackboardError("blackboard max 32 entries")
    entries: list[tuple[str, Value]] = []
    for key, value in data.items():
        if not isinstance(key, str) or KEY.match(key) is None:
            raise BlackboardError(f"illegal blackboard key: {key!r}")
        entries.append((key, _value(value)))
    return tuple(sorted(entries))


@dataclass(frozen=True)
class Blackboard:
    entries: tuple[tuple[str, Value], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", normalize(dict(self.entries)))

    def merge(self, other: "Blackboard | dict") -> "Blackboard":
        update = other if isinstance(other, Blackboard) else Blackboard(normalize(other))
        merged = dict(self.entries)
        merged.update(dict(update.entries))
        return Blackboard(normalize(merged))

    def get(self, key: str, default: Any = None) -> Any:
        return dict(self.entries).get(key, default)

    def to_dict(self) -> dict:
        return {key: list(value) if isinstance(value, tuple) else value for key, value in self.entries}

    @classmethod
    def from_dict(cls, data: Any) -> "Blackboard":
        return cls(normalize(data))

    def jsonl_record(self, *, step: int, op_id: str) -> str:
        payload = {"step": int(step), "op_id": str(op_id), "blackboard": self.to_dict()}
        return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def write_jsonl(path: Any, records: Iterable[str]) -> None:
    """Append already-serialized records; callers own the directory."""
    with open(path, "a", encoding="utf-8") as handle:
        for line in records:
            handle.write(line)
