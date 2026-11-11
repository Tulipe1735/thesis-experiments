"""Check Codex connectivity with synthetic JSON only, never with research inputs."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


PROMPT = 'Synthetic connection check. Use no tools. Return only {"status":"ok"}.'
SCHEMA = {
    "type": "object", "properties": {"status": {"type": "string", "enum": ["ok"]}},
    "required": ["status"], "additionalProperties": False,
}


def run(output: Path, model: str = "gpt-5.6-sol") -> bool:
    output.mkdir(parents=True, exist_ok=False)
    (output / "schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    (output / "prompt.txt").write_text(PROMPT + "\n", encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key not in {
        "OPENAI_API_KEY", "CODEX_API_KEY",
    }}
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
            "--model", model, "--output-schema", str(output / "schema.json"), PROMPT,
        ]
        (output / "command.json").write_text(json.dumps(argv, indent=2), encoding="utf-8")
        try:
            reply = subprocess.run(
                argv, cwd=directory, env={**env, "PWD": directory},
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            (output / "results.json").write_text(json.dumps({
                "connected": False, "error": type(error).__name__, "research_inputs_sent": False,
            }), encoding="utf-8")
            return False
    (output / "events.jsonl").write_text(reply.stdout, encoding="utf-8")
    events = [json.loads(line) for line in reply.stdout.splitlines() if line.startswith("{")]
    items = [row.get("item", {}) for row in events if row.get("type") == "item.completed"]
    messages = [item["text"] for item in items if item.get("type") == "agent_message"]
    tool_items = [item.get("type") for item in items if item.get("type") not in {
        "agent_message", "reasoning", "error",
    }]
    usage = next((row.get("usage") for row in reversed(events) if row.get("type") == "turn.completed"), None)
    try:
        schema_ok = bool(messages) and json.loads(messages[-1]) == {"status": "ok"}
    except json.JSONDecodeError:
        schema_ok = False
    result = {
        "model": model,
        "connected": reply.returncode == 0 and schema_ok and usage is not None,
        "exit_code": reply.returncode, "schema_ok": schema_ok,
        "tool_items": tool_items, "usage": usage,
        "connector_startup_warning": any(
            marker in reply.stderr for marker in ("codex_mcp", "codex_rmcp", "MCP startup")
        ),
        "stderr_tail": reply.stderr[-1800:],
        "research_inputs_sent": False,
        "qualified_for_research": False,
    }
    (output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result["connected"] and not tool_items


def check_read_boundary(output: Path, native_bin_dir: Path) -> bool:
    """Prove the shell boundary with an actual synthetic file and a readable control."""
    native_bin_dir = native_bin_dir.resolve(strict=True)
    if not (native_bin_dir / "codex").is_file():
        raise ValueError("Expected the directory containing the native Codex binary")
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="growup-codex-canary-") as directory:
        parent = Path(directory)
        workspace = parent / "agent"
        workspace.mkdir()
        canary = parent / "canary"
        canary.write_text("Synthetic outside-workspace canary.\n", encoding="utf-8")
        filesystem = '{":root"="deny",":minimal"="read",' + json.dumps(str(native_bin_dir)) + '="read"}'
        variants = {
            "deny": [
                "-P", "growup", "-c", f"permissions.growup.filesystem={filesystem}",
                "-c", "permissions.growup.network.enabled=false",
            ],
            "control": ["-P", ":read-only"],
        }
        rows = {}
        for name, flags in variants.items():
            argv = ["codex", "sandbox", *flags, "--", "/usr/bin/test", "-r", str(canary)]
            reply = subprocess.run(
                argv, cwd=workspace, env={**os.environ, "PWD": str(workspace)},
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
            )
            rows[name] = {
                "command": argv, "exit_code": reply.returncode, "stderr": reply.stderr[-1800:],
            }
    passed = (
        rows["deny"]["exit_code"] == 1 and rows["control"]["exit_code"] == 0
        and not any(row["stderr"].strip() for row in rows.values())
    )
    (output / "results.json").write_text(json.dumps({
        "passed": passed, "local_file_read_boundary": rows, "model_requests": 0,
        "qualified_for_research": False,
    }, indent=2), encoding="utf-8")
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--check-read-boundary", type=Path, metavar="NATIVE_CODEX_BIN_DIR")
    args = parser.parse_args()
    if args.check_read_boundary:
        passed = check_read_boundary(args.output.resolve(), args.check_read_boundary)
    else:
        passed = run(args.output.resolve(), args.model)
    raise SystemExit(0 if passed else 1)
