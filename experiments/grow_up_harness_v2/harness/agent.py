"""OpenCode gateway and strict request/response schemas.

The gateway runs ``opencode run --format json`` in an isolated workspace. It
parses ``text`` parts as the reply and the final ``step_finish`` for tokens and
cost. Candidate sources are checked with an AST whitelist before they can reach
the Worker; the Worker re-checks imports at runtime.

Nothing here fabricates a model reply. If the CLI is absent or exits non-zero,
the call raises and the caller must stop.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .contracts import ALLOWED_IMPORTS, ContractError
from .ops import SMALL_OPS, spec as op_spec

MODEL = "opencode-go/deepseek-v4.1-flash"
DEFAULT_COMMAND = ("opencode", "run", "--format", "json", "--auto", "--model", MODEL)
MAX_SOURCE_BYTES = 64 * 1024
FORBIDDEN_NAMES = frozenset(
    {
        "__builtins__",
        "__import__",
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "breakpoint",
    }
)
FORBIDDEN_MODULES = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "pathlib",
        "shutil",
        "socket",
        "ctypes",
        "importlib",
        "builtins",
        "pickle",
        "marshal",
    }
)
SMALL_OP_IDS = tuple(item.op_id for item in SMALL_OPS)


class GatewayUnavailable(RuntimeError):
    """The OpenCode CLI is absent, failed, or returned no usable reply."""


class AgentSchemaError(ContractError):
    """The model reply does not match the registered request schema."""


@dataclass(frozen=True)
class GatewayResponse:
    text: str
    session_id: str
    message_id: str
    model: str
    prompt_sha256: str
    response_sha256: str
    input_tokens: int
    output_tokens: int
    cost: float
    wall_time_s: float
    reasoning_tokens: int = 0
    events: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "model": self.model,
            "prompt_sha256": self.prompt_sha256,
            "response_sha256": self.response_sha256,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cost": self.cost,
            "wall_time_s": self.wall_time_s,
        }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_events(lines: Sequence[str], *, model: str = MODEL, prompt: str = "") -> GatewayResponse:
    """Parse ``opencode run --format json`` JSONL into one response."""
    texts: list[str] = []
    events: list[dict] = []
    session_id = ""
    message_id = ""
    input_tokens = output_tokens = reasoning_tokens = 0
    cost = 0.0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise GatewayUnavailable(f"gateway emitted non-JSON: {error}") from None
        if not isinstance(event, dict):
            raise GatewayUnavailable("gateway event is not an object")
        events.append(event)
        if event.get("type") == "error":
            message = event.get("error", {}).get("message", "gateway error")
            raise GatewayUnavailable(str(message)[:400])
        part = event.get("part") or {}
        session_id = str(event.get("sessionID") or part.get("sessionID") or session_id)
        message_id = str(part.get("messageID") or message_id)
        if event.get("type") == "text":
            texts.append(str(part.get("text", "")))
        elif event.get("type") == "step_finish":
            tokens = part.get("tokens") or {}
            input_tokens = int(tokens.get("input", 0))
            output_tokens = int(tokens.get("output", 0))
            reasoning_tokens = int(tokens.get("reasoning", 0))
            cost = float(part.get("cost", 0.0))
    text = "".join(texts).strip()
    if not text:
        raise GatewayUnavailable("gateway returned no text part")
    if not session_id.startswith("ses"):
        raise GatewayUnavailable("gateway returned no session id")
    return GatewayResponse(
        text=text,
        session_id=session_id,
        message_id=message_id,
        model=model,
        prompt_sha256=_sha(prompt),
        response_sha256=_sha(text),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        wall_time_s=0.0,
        reasoning_tokens=reasoning_tokens,
        events=tuple(events),
    )


class OpenCodeGateway:
    """One OpenCode session, with an injectable runner for tests."""

    def __init__(
        self,
        workspace: Path | str,
        *,
        model: str = MODEL,
        command: Sequence[str] | None = None,
        runner: Callable[..., subprocess.CompletedProcess] | None = None,
        timeout_s: float = 180.0,
        standalone: bool = False,
        server: str | None = None,
        env: dict | None = None,
    ):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.command = tuple(command or DEFAULT_COMMAND)
        self.runner = runner
        self.timeout_s = float(timeout_s)
        self.standalone = bool(standalone)
        self.server = server
        self.env = dict(env or {})

    def available(self) -> bool:
        return self.runner is not None or shutil.which("opencode") is not None

    def run(self, prompt: str, *, session: str | None = None) -> GatewayResponse:
        if not self.available():
            raise GatewayUnavailable("opencode CLI is not installed")
        if not isinstance(prompt, str) or not prompt:
            raise AgentSchemaError("prompt must be non-empty text")
        argv = list(self.command)
        if self.standalone:
            # Kept for callers that can afford the flag; the P2 driver uses an
            # explicit private server instead so the project is the workspace
            # from the first request.
            argv.insert(2, "--standalone")
        if self.server is not None:
            argv[2:2] = ["--server", self.server]
        if session is not None:
            if not session.startswith("ses"):
                raise AgentSchemaError("session id must start with ses")
            argv.extend(["--session", session])
        argv.append(prompt)
        started = time.monotonic()
        try:
            if self.runner is not None:
                completed = self.runner(argv, cwd=self.workspace, timeout=self.timeout_s)
            else:
                completed = subprocess.run(
                    argv,
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                    # OpenCode resolves its project from PWD. subprocess cwd
                    # alone leaves PWD at the parent, which silently loads the
                    # repository config instead of the Agent workspace.
                    env={**os.environ, "PWD": str(self.workspace), **self.env},
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GatewayUnavailable(f"gateway process failed: {error}") from None
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "")[:600].strip()
            raise GatewayUnavailable(f"gateway exited {completed.returncode}: {detail}")
        response = parse_events(
            (completed.stdout or "").splitlines(), model=self.model, prompt=prompt
        )
        return GatewayResponse(**{**response.to_dict(), "events": response.events, "wall_time_s": time.monotonic() - started})


def strip_fences(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return value


def parse_json_reply(text: str) -> dict:
    value = strip_fences(text)
    try:
        payload = json.loads(value)
    except ValueError as error:
        # Models sometimes prepend one sentence to an otherwise valid object.
        # Recover a single object span; the schema checks still reject extras.
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise AgentSchemaError(f"reply is not strict JSON: {error}") from None
        try:
            payload = json.loads(value[start : end + 1])
        except ValueError as inner:
            raise AgentSchemaError(f"reply is not strict JSON: {inner}") from None
    if not isinstance(payload, dict):
        raise AgentSchemaError("reply must be a JSON object")
    return payload


def check_source(source: str) -> None:
    """AST whitelist for one candidate op source."""
    if not isinstance(source, str) or not source.strip():
        raise AgentSchemaError("candidate source must be non-empty text")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise AgentSchemaError("candidate source exceeds 64 KiB")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise AgentSchemaError(f"candidate source does not parse: {error}") from None
    if not any(isinstance(node, ast.FunctionDef) and node.name == "act" for node in tree.body):
        raise AgentSchemaError("candidate source must define a top-level act")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    raise AgentSchemaError(f"import not allowed in worker: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module not in ALLOWED_IMPORTS or node.level != 0:
                raise AgentSchemaError(f"import not allowed in worker: {node.module}")
            if any(alias.name == "*" for alias in node.names):
                raise AgentSchemaError("star imports are not allowed")
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in FORBIDDEN_NAMES:
                raise AgentSchemaError(f"call not allowed in worker: {name}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise AgentSchemaError(f"name not allowed in worker: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise AgentSchemaError(f"dunder attribute not allowed: {node.attr}")
            root = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in FORBIDDEN_MODULES:
                raise AgentSchemaError(f"module not allowed in worker: {root.id}")


def validate_author_ops(payload: dict, expected: Sequence[str] = SMALL_OP_IDS) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"ops", "explanation", "memory"}:
        raise AgentSchemaError("author_ops must have exactly ops, explanation, memory")
    ops = payload["ops"]
    if not isinstance(ops, dict) or set(ops) != set(expected):
        raise AgentSchemaError(f"author_ops must cover exactly {sorted(expected)}")
    for op_id in expected:
        check_source(ops[op_id])
    if not isinstance(payload["explanation"], str) or not payload["explanation"].strip():
        raise AgentSchemaError("explanation must be non-empty text")
    memory = payload["memory"]
    if not isinstance(memory, list) or any(not isinstance(item, str) or not item.strip() for item in memory):
        raise AgentSchemaError("memory must be a list of non-empty strings")
    return payload


def validate_compose(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AgentSchemaError("compose reply must be an object")
    if set(payload) == {"refuse"}:
        if not isinstance(payload["refuse"], str) or not payload["refuse"].strip():
            raise AgentSchemaError("refuse must be non-empty text")
        return payload
    if set(payload) == {"program"} and isinstance(payload["program"], dict):
        program = payload["program"]
        if not isinstance(program.get("steps"), list) or not program["steps"]:
            raise AgentSchemaError("program.steps must be a non-empty list")
        return payload
    raise AgentSchemaError("compose must be {program} or {refuse}")


def validate_diagnose(payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"diagnosis", "repair_boundary", "memory"}:
        raise AgentSchemaError("diagnose must have exactly diagnosis, repair_boundary, memory")
    for key in ("diagnosis", "repair_boundary"):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise AgentSchemaError(f"{key} must be non-empty text")
    memory = payload["memory"]
    if not isinstance(memory, list) or any(not isinstance(item, str) or not item.strip() for item in memory):
        raise AgentSchemaError("memory must be a list of non-empty strings")
    return payload


def _public_op_table() -> list[dict]:
    rows = []
    for item in SMALL_OPS:
        rows.append(
            {
                "op_id": item.op_id,
                "pre": [predicate.name for predicate in item.pre],
                "post": [predicate.name for predicate in item.post],
                "budget_s": item.budget_s,
                "failure_codes": list(item.failure_codes),
                "arg_keys": list(item.arg_keys),
                "required_arg_keys": list(item.required_arg_keys),
            }
        )
    return rows


def author_ops_prompt(
    task: dict,
    observation: dict,
    diagnosis: dict | None = None,
    *,
    previous_ops: dict | None = None,
    feedback: dict | None = None,
) -> str:
    payload = {
        "request": "author_ops",
        "public_task": task,
        "legal_observation": observation,
        "op_table": _public_op_table(),
        "failure_diagnosis": diagnosis,
        "output_schema": {"ops": {op_id: "<python source>" for op_id in SMALL_OP_IDS}, "explanation": "<text>", "memory": ["<text>"]},
        "rules": [
            "Reply with strict JSON and nothing else.",
            "Each source must define act(observation, task, state) and return a dict {\"action\": ..., \"state\": ..., \"blackboard\": {...}}; a tuple is rejected.",
            "Actions are only {\"op\":\"set_joints\",\"targets\":{joint_name:absolute_rad},\"duration\":0.02-0.20}, {\"op\":\"wait\",\"duration\":0.02-0.20}, {\"op\":\"done\"}, or {\"op\":\"fail\",\"reason\":\"a declared failure code\"}. Use 1 to 14 targets for set_joints; use wait to make no change. Duration must be a multiple of 0.002 s. Each observation[\"joints\"][name] is an object with q and target in radians. The guards use delta from target, not from q: max increment 0.03 rad arm / 0.05 rad hand, and 1.5 * abs(delta) / duration <= min(joint velocity limit, 0.30 rad/s arm or 0.50 rad/s hand).",
            "blackboard keys match [a-z][a-z0-9_]{0,63}; values are finite numbers, strings, or flat lists (at most 64 items); at most 32 entries; convert numpy arrays with .tolist().",
            "Op-local state starts fresh per Worker. Read previous successful ops' data from observation[\"blackboard\"]. A delta is committed only on done after the postcondition passes. Return every value needed by later ops in the final blackboard delta, not just in state or an intermediate action.",
            "For locate_target, done must include blackboard keys target_estimate_in_palm (three coordinates in metres in the current pelvis frame, despite the legacy name) and confidence (0.5 to 1.0 when supported by the observation). If localization is unavailable or low-confidence, return a declared failure. Other key names do not satisfy target_localized.",
            "Only imports in math, numpy, numpy.linalg, numpy.random, numpy.fft are allowed.",
            "Do not read object truth, evaluator thresholds, the test split, or the file system.",
            "The five op ids must be exactly the op_table ids.",
            "rgbd.rgb and rgbd.depth_m are shape descriptors here; at runtime they are the arrays with the named shape and dtype.",
        ],
    }
    if previous_ops is not None:
        payload["previous_ops"] = previous_ops
        payload["rules"].append("Revise previous_ops in place; keep the same five op ids.")
    if feedback is not None:
        payload["agent_visible_feedback"] = feedback
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def compose_prompt(task: dict, skill_graph: dict, observation: dict) -> str:
    payload = {
        "request": "compose",
        "public_task": task,
        "formal_op_table": _public_op_table(),
        "skill_graph": skill_graph,
        "legal_observation": observation,
        "output_schema": "either {\"program\":{\"steps\":[...]}} or {\"refuse\":\"...\"}",
        "rules": [
            "Reply with strict JSON {program} or {refuse}.",
            "Use only formal ops in the table; never invent an op.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def diagnose_prompt(task: dict, feedback: dict, failed_op: str, failed_step: int) -> str:
    payload = {
        "request": "diagnose",
        "public_task": task,
        "agent_visible_feedback": feedback,
        "failed_op": failed_op,
        "failed_step": failed_step,
        "output_schema": {"diagnosis": "<mechanism>", "repair_boundary": "<bounded repair>", "memory": ["<candidate memory>"]},
        "rules": [
            "Use only agent-visible feedback and printed task facts.",
            "Do not request evaluator truth, object poses, thresholds, or the test split.",
            "Keep the repair bounded; do not relax the goal, safety or budget.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
