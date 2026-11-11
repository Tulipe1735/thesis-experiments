"""The Agent workspace: one deny-all OpenCode config, nothing else.

The workspace lives outside the repository so OpenCode cannot discover the
repo's AGENTS.md, skills, commands, or a second opencode.json from an ancestor.
Every tool action is denied; MCP servers, skills and plugins are removed by
policy. The model can only answer the prompt it is given on the command line.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

MODEL = "opencode-go/deepseek-v4.1-flash"

CONFIG = {
    "$schema": "https://opencode.ai/config.json",
    "model": MODEL,
    "permissions": [
        {"action": "*", "resource": "*", "effect": "deny"},
    ],
    "policies": [
        {"action": "mcp.use", "resource": "*", "effect": "deny"},
        {"action": "skill.use", "resource": "*", "effect": "deny"},
        {"action": "plugin.use", "resource": "*", "effect": "deny"},
    ],
    "snapshots": False,
    "formatter": False,
}


CONTROL_CONFIG = {
    **CONFIG,
    # The same config with one exception: read is allowed after the deny-all.
    # The canary control proves the probe can see a readable file; the
    # deny-all workspace proves it cannot.
    "permissions": [
        {"action": "*", "resource": "*", "effect": "deny"},
        {"action": "external_directory", "resource": "*", "effect": "allow"},
        {"action": "read", "resource": "*", "effect": "allow"},
    ],
}


def config_text() -> str:
    return json.dumps(CONFIG, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def control_config_text() -> str:
    return json.dumps(CONTROL_CONFIG, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def config_sha256() -> str:
    return hashlib.sha256(config_text().encode("utf-8")).hexdigest()


def prepare_workspace(root: Path | str) -> Path:
    """Create ``root/workspace`` with the only config the Agent may load."""
    root = Path(root)
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "opencode.json").write_text(config_text(), encoding="utf-8")
    return workspace


def prepare_control_workspace(root: Path | str) -> Path:
    """Create ``root/workspace`` with read allowed and every other tool denied."""
    root = Path(root)
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "opencode.json").write_text(control_config_text(), encoding="utf-8")
    return workspace
