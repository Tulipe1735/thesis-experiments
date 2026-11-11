"""One artifact, two projections.

A skill record is the single source of truth. The card is one projection (text
the slow path can read), the program is another (a callable the fast path runs).
Neither projection is edited directly; both are derived from the record, and the
record refuses to load if its bytes disagree with the evidence.

Routing is a binding check, not a name match: a task is FAST only when the
record's scope, plant, evaluator and saved initial state all match the request.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import skill_record

ROOT = Path(__file__).resolve().parents[3]


class Route(str, Enum):
    FAST = "fast"
    REFUSE = "refuse"


@dataclass(frozen=True)
class Binding:
    task: str
    assets: frozenset[str]
    initial_state_sha256: str
    plant_sha256: str
    evaluator_sha256: str


@dataclass(frozen=True)
class Decision:
    route: Route
    reasons: tuple[str, ...]
    record: skill_record.SkillRecord | None


def bind(record: skill_record.SkillRecord, binding: Binding) -> Decision:
    """Decide whether this record covers the request. No guessing from names."""
    data = record.data
    reasons: list[str] = []
    if data["status"] != "validated":
        reasons.append(f"record status is {data['status']}, not validated")
    if data["program"]["status"] != "accepted":
        reasons.append(f"program status is {data['program']['status']}, not accepted")
    if data["scope"]["task"] != binding.task:
        reasons.append(f"task {binding.task} is outside scope {data['scope']['task']}")
    missing = sorted(set(binding.assets) - set(data["scope"]["assets"]))
    if missing:
        reasons.append(f"assets outside scope: {', '.join(missing)}")
    known = {item["sha256"] for item in data["scope"]["initial_states"]}
    if binding.initial_state_sha256 not in known:
        reasons.append("initial state is not one the record was validated on")
    if data["binding"]["plant_sha256"] != binding.plant_sha256:
        reasons.append("plant differs from the bound plant")
    if data["binding"]["evaluator_sha256"] != binding.evaluator_sha256:
        reasons.append("evaluator differs from the bound evaluator")
    route = Route.REFUSE if reasons else Route.FAST
    return Decision(route=route, reasons=tuple(reasons), record=record)


def project_card(record: skill_record.SkillRecord) -> dict:
    """The card projection the slow path reads."""
    card = record.data["card"]
    return {"text": card["text"], "status": card["status"],
            "evidence_arm": card.get("evidence_arm"), "record": record.id,
            "record_version": record.data["version"], "digest": record.digest()}


def project_program(record: skill_record.SkillRecord):
    """The code projection the fast path calls."""
    program = record.data["program"]
    path = (ROOT / program["module"]).resolve()
    spec = importlib.util.spec_from_file_location(f"skill_{record.id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entry = getattr(module, program["entry"], None)
    if entry is None:
        raise AttributeError(f"{program['module']} has no entry {program['entry']}")
    return module


def load_artifact(path: Path | str) -> skill_record.SkillRecord:
    """Load and verify the record; both projections come from the result."""
    return skill_record.load(path)
