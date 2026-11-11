"""One isolated Codex decision with the raw reply retained for audit."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


USAGE_FIELDS = ("input_tokens", "output_tokens", "reasoning_output_tokens")


class CodexDecisionError(RuntimeError):
    """The transport or response failed before the caller could use a decision."""


def _parse_events(stdout: bytes) -> tuple[dict, dict]:
    thread_id = None
    usage = None
    messages = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        kind = event["type"]
        if kind == "thread.started":
            thread_id = event["thread_id"]
        elif kind == "turn.completed":
            usage = event["usage"]
        elif kind.startswith("item."):
            item = event["item"]
            if item["type"] not in {"agent_message", "reasoning"}:
                raise CodexDecisionError(f"Unexpected Codex item: {item['type']}")
            if kind == "item.completed" and item["type"] == "agent_message":
                messages.append(item["text"])
        elif kind != "turn.started":
            raise CodexDecisionError(f"Unexpected Codex event: {kind}")
    if not thread_id or len(messages) != 1 or not isinstance(usage, dict):
        raise CodexDecisionError("Expected one completed Codex decision with token usage")
    if any(type(usage.get(key)) is not int or usage[key] < 0 for key in USAGE_FIELDS):
        raise CodexDecisionError("Codex returned incomplete token usage")
    decision = json.loads(messages[0])
    if not isinstance(decision, dict):
        raise CodexDecisionError("Codex decision is not a JSON object")
    return decision, {"thread_id": thread_id, **usage}


def decide(
    prompt: dict,
    schema: dict,
    output: Path,
    *,
    model: str,
    timeout: float,
) -> tuple[dict, dict]:
    """Start a fresh turn and return its JSON object and recorded usage."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    encoded_prompt = (json.dumps(prompt, ensure_ascii=False, allow_nan=False) + "\n").encode()
    (output / "prompt.json").write_bytes(encoded_prompt)
    schema_path = output / "schema.json"
    schema_path.write_text(json.dumps(schema, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith("OPENAI_") and key not in {"CODEX_API_KEY", "CHATGPT_BASE_URL"}
    }
    started = time.monotonic()
    metadata = {"model": model, "timeout_s": timeout}
    with tempfile.TemporaryDirectory(prefix="growup-codex-") as directory:
        argv = [
            "codex", "exec", "--ignore-user-config", "--ignore-rules",
            "--ephemeral", "--skip-git-repo-check", "--json", "-C", directory,
            "--disable", "apps", "--disable", "plugins", "--disable", "remote_plugin",
            "--disable", "memories", "--disable", "shell_tool",
            "-c", 'approval_policy="never"', "-c", 'web_search="disabled"',
            "-c", "project_doc_max_bytes=0",
            "-c", 'default_permissions="growup"',
            "-c", 'permissions.growup.filesystem={":root"="deny",":minimal"="read"}',
            "-c", "permissions.growup.network.enabled=false",
            "--model", model, "--output-schema", str(schema_path), "-",
        ]
        (output / "command.json").write_text(json.dumps(argv, indent=2) + "\n", encoding="utf-8")
        stdout = stderr = b""
        try:
            try:
                reply = subprocess.run(
                    argv, cwd=directory, env={**env, "PWD": directory},
                    input=encoded_prompt, capture_output=True, timeout=timeout,
                )
            except subprocess.TimeoutExpired as error:
                stdout, stderr = error.stdout or b"", error.stderr or b""
                raise CodexDecisionError(f"Codex timed out after {timeout:g} s") from error
            stdout, stderr = reply.stdout, reply.stderr
            metadata["exit_code"] = reply.returncode
            if any(marker in stderr.lower() for marker in (b"codex_mcp", b"codex_rmcp", b"mcp startup")):
                raise CodexDecisionError("Codex reported connector startup")
            if reply.returncode != 0:
                raise CodexDecisionError(f"Codex exited with code {reply.returncode}")
            decision, usage = _parse_events(stdout)
            metadata.update(usage, status="ok")
            return decision, metadata
        except (OSError, ValueError, KeyError, TypeError, CodexDecisionError) as error:
            metadata.update(status="error", error=str(error))
            raise CodexDecisionError(f"{error}; details in {output}") from error
        finally:
            metadata["wall_seconds"] = time.monotonic() - started
            (output / "events.jsonl").write_bytes(stdout)
            (output / "stderr.log").write_bytes(stderr)
            (output / "metadata.json").write_text(
                json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
            )
