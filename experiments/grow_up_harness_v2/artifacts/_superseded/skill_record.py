"""Load, check and digest one skill record.

A record is data, not code: it names a card, a program module and the evidence
that ties them to saved initial states. This module refuses records whose
hashes do not match the bytes on disk, whose evidence paths are missing, whose
program acceptance run disagrees with its declared status, or whose stored
reliability is not what the runs imply.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = Path(__file__).resolve().parents[1] / "skill_schema_v1.json"

SCHEMA_VERSION = "skill_record.v1"
STATUSES = ("candidate", "validated", "rejected", "retired")
VALIDATIONS = ("paired", "repair_lineage", "expanded")
FORMS = ("engineering_composition", "generated_program", "learned_policy")
Z_95 = 1.959963984540054


class SkillRecordError(ValueError):
    """The record is malformed, or its claims do not match the stored evidence."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(record: dict) -> str:
    """Stable hash of the record without its own digest field."""
    body = {key: value for key, value in record.items() if key != "digest"}
    return _sha256_text(_canonical(body))


def wilson_lower(successes: int, episodes: int, z: float = Z_95) -> float:
    """Lower bound of the Wilson score interval. Small samples get a low bound."""
    if episodes <= 0:
        raise SkillRecordError("reliability needs at least one episode")
    p = successes / episodes
    denominator = 1 + z * z / episodes
    centre = (p + z * z / (2 * episodes)) / denominator
    margin = z / denominator * math.sqrt(p * (1 - p) / episodes + z * z / (4 * episodes * episodes))
    return max(0.0, centre - margin)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SkillRecordError(message)


def _text(value, name: str) -> str:
    _require(isinstance(value, str) and value.strip() != "", f"{name} must be non-empty text")
    return value


def _sha(value, name: str) -> str:
    _text(value, name)
    _require(len(value) == 64 and all(c in "0123456789abcdef" for c in value),
             f"{name} must be a lowercase sha256")
    return value


def _int(value, name: str, minimum: int = 0) -> int:
    _require(type(value) is int and value >= minimum, f"{name} must be an integer >= {minimum}")
    return value


def _number(value, name: str) -> float:
    _require(type(value) in (int, float) and math.isfinite(value), f"{name} must be a finite number")
    return float(value)


def _texts(value, name: str, minimum: int = 0) -> list:
    _require(isinstance(value, list) and len(value) >= minimum, f"{name} must be a list")
    for item in value:
        _text(item, name)
    return value


def _resolve(relative: str, name: str) -> Path:
    path = (ROOT / relative).resolve()
    _require(path.is_relative_to(ROOT), f"{name} must stay inside the experiment root")
    _require(path.is_file(), f"{name} does not exist: {relative}")
    return path


def _skill_card_of(run_path: str):
    """The skill_card text recorded beside one evidence run, if any."""
    registration = (ROOT / run_path).resolve().parent / "registration.json"
    if not registration.is_file():
        return None
    value = json.loads(registration.read_text(encoding="utf-8")).get("skill_card")
    return value if isinstance(value, str) else None


def _source_hash_of(acceptance_run: str, module: str):
    """The source hash one acceptance run recorded for the program module."""
    registration = (ROOT / acceptance_run).resolve().parent / "registration.json"
    if not registration.is_file():
        return None
    hashes = json.loads(registration.read_text(encoding="utf-8")).get("source_hashes") or {}
    return hashes.get(module)


@dataclass(frozen=True)
class SkillRecord:
    data: dict
    path: Path

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def status(self) -> str:
        return self.data["status"]

    @property
    def validation(self) -> str:
        return self.data["validation"]

    def digest(self) -> str:
        return digest(self.data)

    def to_dict(self) -> dict:
        return {**self.data, "digest": self.digest()}


def check(data: dict) -> dict:
    """Validate one record against the stored bytes and return its digest."""
    _require(isinstance(data, dict), "record must be an object")
    _require(data.get("schema_version") == SCHEMA_VERSION,
             f"schema_version must be {SCHEMA_VERSION}")
    _text(data.get("id"), "id")
    _int(data.get("version"), "version", 1)
    _require(data.get("status") in STATUSES, "unknown status")
    _require(data.get("validation") in VALIDATIONS, "unknown validation")

    provenance = data.get("provenance") or {}
    _require(provenance.get("form") in FORMS, "unknown provenance.form")
    _text(provenance.get("author"), "provenance.author")
    _text(provenance.get("first_run"), "provenance.first_run")

    scope = data.get("scope") or {}
    _text(scope.get("task"), "scope.task")
    _texts(scope.get("assets"), "scope.assets", 1)
    states = scope.get("initial_states")
    _require(isinstance(states, list) and states, "scope.initial_states must be non-empty")
    for index, item in enumerate(states):
        path = _resolve(_text(item.get("path"), f"initial_states[{index}].path"),
                        f"initial_states[{index}].path")
        _require(_sha256_bytes(path.read_bytes()) == _sha(item.get("sha256"),
                                                          f"initial_states[{index}].sha256"),
                 f"initial_states[{index}].sha256 does not match the saved state")

    retrieval = data.get("retrieval") or {}
    _text(retrieval.get("description"), "retrieval.description")
    _texts(retrieval.get("keywords"), "retrieval.keywords", 1)

    _texts(data.get("preconditions"), "preconditions", 1)
    _texts(data.get("postconditions"), "postconditions", 1)
    exits = data.get("failure_exits")
    _require(isinstance(exits, list) and exits, "failure_exits must be non-empty")
    for index, exit_row in enumerate(exits):
        _text(exit_row.get("code"), f"failure_exits[{index}].code")
        _text(exit_row.get("condition"), f"failure_exits[{index}].condition")

    constraints = data.get("physical_constraints") or {}
    _require(_number(constraints.get("max_single_move_m"), "max_single_move_m") > 0,
             "max_single_move_m must be > 0")
    _require(_number(constraints.get("release_height_m"), "release_height_m") > 0,
             "release_height_m must be > 0")

    card = data.get("card") or {}
    _text(card.get("text"), "card.text")
    if card.get("sha256") is not None:
        _require(_sha256_text(card["text"]) == _sha(card["sha256"], "card.sha256"),
                 "card.sha256 does not match card.text")
    _require(card.get("status") in ("untested", "validated", "rejected"), "unknown card.status")

    program = data.get("program") or {}
    module = _resolve(_text(program.get("module"), "program.module"), "program.module")
    if program.get("sha256") is not None:
        _require(_sha256_bytes(module.read_bytes()) == _sha(program["sha256"], "program.sha256"),
                 "program.sha256 does not match the module bytes")
    _text(program.get("entry"), "program.entry")
    _require(program.get("status") in ("untested", "accepted", "rejected"), "unknown program.status")

    composition = data.get("composition") or {}
    _texts(composition.get("uses"), "composition.uses")
    _texts(composition.get("used_by"), "composition.used_by")

    binding = data.get("binding") or {}
    _sha(binding.get("plant_sha256"), "binding.plant_sha256")
    _sha(binding.get("evaluator_sha256"), "binding.evaluator_sha256")
    _require(_number(binding.get("simulation_budget_s"), "simulation_budget_s") > 0,
             "binding.simulation_budget_s must be > 0")

    evidence = data.get("evidence") or {}
    arms = {}
    for side in ("without", "with"):
        arm = (evidence.get("paired") or {}).get(side) or {}
        _text(arm.get("arm"), f"paired.{side}.arm")
        episodes = _int(arm.get("episodes"), f"paired.{side}.episodes", 1)
        successes = _int(arm.get("successes"), f"paired.{side}.successes")
        _require(successes <= episodes, f"paired.{side}.successes exceeds episodes")
        arms[side] = (episodes, successes)
    runs = evidence.get("runs")
    _require(isinstance(runs, list) and runs, "evidence.runs must be non-empty")
    successes = 0
    for index, run in enumerate(runs):
        _text(run.get("path"), f"runs[{index}].path")
        _text(run.get("arm"), f"runs[{index}].arm")
        _require(type(run.get("verified_success")) is bool,
                 f"runs[{index}].verified_success must be a bool")
        successes += int(run["verified_success"])
        if run.get("margin_m") is not None:
            _number(run["margin_m"], f"runs[{index}].margin_m")
    _require(successes == arms["with"][1],
             "evidence.runs disagree with paired.with.successes")

    reliability = data.get("reliability") or {}
    episodes = _int(reliability.get("episodes"), "reliability.episodes", 1)
    _require(episodes == len(runs), "reliability.episodes must equal the number of runs")
    _require(_int(reliability.get("successes"), "reliability.successes") == successes,
             "reliability.successes must equal the successful runs")
    _require(abs(_number(reliability.get("rate"), "reliability.rate")
                 - successes / episodes) < 1e-9, "reliability.rate does not match the runs")
    _require(abs(_number(reliability.get("wilson_lower_95"), "reliability.wilson_lower_95")
                 - wilson_lower(successes, episodes)) < 1e-9,
             "reliability.wilson_lower_95 does not match the runs")

    # The card text must be the text the evidence run actually used, not a
    # retyped copy. Each run directory keeps it in the parent registration.
    registered = _skill_card_of(runs[0]["path"])
    if registered is not None:
        _require(card["text"] == registered,
                 "card.text differs from the skill_card recorded by the evidence run; "
                 "re-run the evidence or bump the version")

    if program["status"] != "untested":
        _text(program.get("acceptance_run"), "program.acceptance_run")
        result = _resolve(program["acceptance_run"], "program.acceptance_run")
        actual = json.loads(result.read_text(encoding="utf-8")).get("verified_success")
        _require(actual is (program["status"] == "accepted"),
                 "program.status disagrees with its acceptance run")
        recorded = _source_hash_of(program["acceptance_run"], program["module"])
        _require(recorded is not None,
                 "the acceptance run did not record a source hash for program.module")
        _require(recorded == _sha256_bytes(module.read_bytes()),
                 "program bytes differ from the module the acceptance run recorded")

    _texts(data.get("limits"), "limits", 1)

    if card["status"] == "validated":
        _require(arms["with"][1] > 0, "a validated card needs at least one success with it")
    if data["status"] == "validated":
        _require(card["status"] == "validated",
                 "validated record needs a validated card")
        _require(arms["with"][1] > arms["without"][1],
                 "validated record needs more successes with the skill than without it")
        _require(program["status"] == "accepted",
                 "validated record needs an accepted program, not only a card")

    return digest(data)


def load(path: Path | str) -> SkillRecord:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    check(data)
    return SkillRecord(data=data, path=path)
