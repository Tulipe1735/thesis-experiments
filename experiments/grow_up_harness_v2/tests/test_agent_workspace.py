"""The Agent workspace is outside the repo and denies every tool."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness import agent_workspace


class WorkspaceTests(unittest.TestCase):
    def test_config_denies_everything_and_mcp(self) -> None:
        config = agent_workspace.CONFIG
        self.assertEqual(
            config["permissions"][-1],
            {"action": "*", "resource": "*", "effect": "deny"},
        )
        policies = {(row["action"], row["resource"]): row["effect"] for row in config["policies"]}
        self.assertEqual(policies[("mcp.use", "*")], "deny")
        self.assertEqual(policies[("skill.use", "*")], "deny")
        self.assertEqual(policies[("plugin.use", "*")], "deny")

    def test_control_config_only_relaxes_external_read(self) -> None:
        actions = [row["action"] for row in agent_workspace.CONTROL_CONFIG["permissions"]]
        self.assertEqual(actions, ["*", "external_directory", "read"])
        self.assertEqual(agent_workspace.CONTROL_CONFIG["policies"], agent_workspace.CONFIG["policies"])

    def test_prepare_workspace_writes_only_the_config(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            workspace = agent_workspace.prepare_workspace(Path(folder) / "run")
            files = sorted(path.name for path in workspace.iterdir())
            written = json.loads(
                (workspace / "opencode.json").read_text(encoding="utf-8")
            )
        self.assertEqual(files, ["opencode.json"])
        self.assertEqual(written, agent_workspace.CONFIG)


if __name__ == "__main__":
    unittest.main()
