"""OpenCode gateway parsing and strict candidate schemas."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness import agent
from harness.agent import (
    AgentSchemaError,
    GatewayUnavailable,
    OpenCodeGateway,
    check_source,
    parse_events,
    validate_author_ops,
    validate_compose,
    validate_diagnose,
)

SESSION = "ses_e5bc23068ffeoaztult1Z44oU4"


def line(event: dict) -> str:
    return json.dumps(event)


def stream(text: str = "ready", *, session: str = SESSION) -> list[str]:
    return [
        line({"type": "step_start", "sessionID": session, "part": {"messageID": "msg_1"}}),
        line({"type": "text", "sessionID": session, "part": {"messageID": "msg_1", "text": text}}),
        line(
            {
                "type": "step_finish",
                "sessionID": session,
                "part": {
                    "messageID": "msg_1",
                    "tokens": {"input": 10, "output": 2, "reasoning": 4},
                    "cost": 0.001,
                },
            }
        ),
    ]


GOOD_SOURCE = """import math

def act(observation, task, state):
    return {"action": {"op": "done"}, "state": state, "blackboard": {}}
"""


class ParseTests(unittest.TestCase):
    def test_parses_text_tokens_and_session(self) -> None:
        response = parse_events(stream("ready"), prompt="hello")
        self.assertEqual(response.text, "ready")
        self.assertEqual(response.session_id, SESSION)
        self.assertEqual(response.input_tokens, 10)
        self.assertEqual(response.output_tokens, 2)
        self.assertEqual(response.reasoning_tokens, 4)
        self.assertAlmostEqual(response.cost, 0.001)
        self.assertEqual(len(response.response_sha256), 64)
        self.assertEqual(len(response.prompt_sha256), 64)

    def test_error_event_is_unavailable(self) -> None:
        bad = [line({"type": "error", "sessionID": "", "error": {"message": "no model"}})]
        with self.assertRaises(GatewayUnavailable):
            parse_events(bad)

    def test_no_text_is_unavailable(self) -> None:
        with self.assertRaises(GatewayUnavailable):
            parse_events([line({"type": "step_start", "sessionID": SESSION, "part": {}})])

    def test_non_json_is_unavailable(self) -> None:
        with self.assertRaises(GatewayUnavailable):
            parse_events(["not json"])


class ReplyTests(unittest.TestCase):
    def test_leading_prose_around_one_object_is_recovered(self) -> None:
        payload = agent.parse_json_reply('Here is the reply.\n{"ops": {}, "explanation": "x", "memory": []}')
        self.assertEqual(payload["explanation"], "x")

    def test_two_objects_are_not_silently_merged(self) -> None:
        with self.assertRaises(AgentSchemaError):
            agent.parse_json_reply('{"a": 1} then {"b": 2}')


class SourceTests(unittest.TestCase):
    def test_accepts_math_and_numpy(self) -> None:
        check_source(GOOD_SOURCE)
        check_source("import numpy as np\nimport numpy.linalg\n\ndef act(observation, task, state):\n    return {'action': {'op': 'done'}, 'state': state, 'blackboard': {}}\n")

    def test_rejects_forbidden_import(self) -> None:
        with self.assertRaises(AgentSchemaError):
            check_source("import os\ndef act(observation, task, state):\n    return {}\n")

    def test_rejects_forbidden_calls(self) -> None:
        for source in (
            "def act(observation, task, state):\n    return open('/etc/passwd')\n",
            "def act(observation, task, state):\n    return __import__('os')\n",
            "def act(observation, task, state):\n    import os\n    return os.system('id')\n",
            "def act(observation, task, state):\n    return eval('1')\n",
        ):
            with self.subTest(source=source[:40]):
                with self.assertRaises(AgentSchemaError):
                    check_source(source)

    def test_requires_top_level_act(self) -> None:
        with self.assertRaises(AgentSchemaError):
            check_source("def other(observation, task, state):\n    return {}\n")

    def test_rejects_syntax_error(self) -> None:
        with self.assertRaises(AgentSchemaError):
            check_source("def act(:\n")


class SchemaTests(unittest.TestCase):
    def test_author_ops_exact_ops(self) -> None:
        payload = {
            "ops": {op_id: GOOD_SOURCE for op_id in agent.SMALL_OP_IDS},
            "explanation": "bounded",
            "memory": ["a"],
        }
        self.assertEqual(validate_author_ops(payload), payload)
        missing = json.loads(json.dumps(payload))
        missing["ops"].pop(agent.SMALL_OP_IDS[0])
        with self.assertRaises(AgentSchemaError):
            validate_author_ops(missing)
        extra = json.loads(json.dumps(payload))
        extra["ops"]["invented"] = GOOD_SOURCE
        with self.assertRaises(AgentSchemaError):
            validate_author_ops(extra)

    def test_author_ops_rejects_bad_memory(self) -> None:
        payload = {
            "ops": {op_id: GOOD_SOURCE for op_id in agent.SMALL_OP_IDS},
            "explanation": "bounded",
            "memory": "not a list",
        }
        with self.assertRaises(AgentSchemaError):
            validate_author_ops(payload)

    def test_compose_shapes(self) -> None:
        self.assertEqual(validate_compose({"refuse": "unknown"}), {"refuse": "unknown"})
        program = {"program": {"steps": [{"op_id": "locate_target"}]}}
        self.assertEqual(validate_compose(program), program)
        with self.assertRaises(AgentSchemaError):
            validate_compose({"program": {"steps": []}})

    def test_diagnose_shape(self) -> None:
        payload = {"diagnosis": "missed", "repair_boundary": "offset", "memory": ["a"]}
        self.assertEqual(validate_diagnose(payload), payload)
        with self.assertRaises(AgentSchemaError):
            validate_diagnose({"diagnosis": "missed"})


class GatewayTests(unittest.TestCase):
    def test_run_parses_injected_runner(self) -> None:
        def runner(argv, cwd, timeout):
            return subprocess.CompletedProcess(argv, 0, "\n".join(stream("ready")), "")

        with tempfile.TemporaryDirectory() as folder:
            gateway = OpenCodeGateway(folder, runner=runner)
            response = gateway.run("hello")
        self.assertEqual(response.text, "ready")
        self.assertEqual(response.session_id, SESSION)
        self.assertEqual(response.input_tokens, 10)
        self.assertEqual(len(response.response_sha256), 64)

    def test_nonzero_exit_is_unavailable(self) -> None:
        def runner(argv, cwd, timeout):
            return subprocess.CompletedProcess(argv, 2, "", "boom")

        with tempfile.TemporaryDirectory() as folder:
            gateway = OpenCodeGateway(folder, runner=runner)
            with self.assertRaises(GatewayUnavailable):
                gateway.run("hello")

    def test_bad_session_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            gateway = OpenCodeGateway(folder, runner=lambda *args, **kwargs: None)
            with self.assertRaises(AgentSchemaError):
                gateway.run("hello", session="not-a-session")

    def test_standalone_is_inserted_before_run_options(self) -> None:
        seen = {}

        def runner(argv, cwd, timeout):
            seen["argv"] = list(argv)
            return subprocess.CompletedProcess(argv, 0, "\n".join(stream("ready")), "")

        with tempfile.TemporaryDirectory() as folder:
            gateway = OpenCodeGateway(folder, runner=runner, standalone=True)
            gateway.run("hello")
        self.assertEqual(seen["argv"][:3], ["opencode", "run", "--standalone"])
        self.assertEqual(seen["argv"][-1], "hello")

    def test_server_is_inserted_after_run(self) -> None:
        seen = {}

        def runner(argv, cwd, timeout):
            seen["argv"] = list(argv)
            return subprocess.CompletedProcess(argv, 0, "\n".join(stream("ready")), "")

        with tempfile.TemporaryDirectory() as folder:
            gateway = OpenCodeGateway(
                folder, runner=runner, server="http://127.0.0.1:4097"
            )
            gateway.run("hello")
        self.assertEqual(
            seen["argv"][:4],
            ["opencode", "run", "--server", "http://127.0.0.1:4097"],
        )


class PromptTests(unittest.TestCase):
    def test_prompts_are_json(self) -> None:
        task = {"id": "TP01_reach_train_000", "target_category": "cup"}
        for prompt in (
            agent.author_ops_prompt(task, {"simulation_seconds": 0.6}),
            agent.compose_prompt(task, {"a": ["b"]}, {"simulation_seconds": 0.6}),
            agent.diagnose_prompt(task, {"verdict": "failure"}, "reach_target", 2),
        ):
            self.assertIsInstance(json.loads(prompt), dict)

    def test_author_prompt_requires_a_dict_return(self) -> None:
        payload = json.loads(
            agent.author_ops_prompt(
                {"id": "TP01_reach_train_000"}, {"simulation_seconds": 0.0}
            )
        )
        rules = " ".join(payload["rules"])
        self.assertIn('{"action"', rules)
        self.assertIn("tuple is rejected", rules)
        self.assertIn("set_joints", rules)
        self.assertIn("Actions are only", rules)
        self.assertIn("blackboard keys", rules)
        self.assertIn("tolist", rules)
        self.assertIn('observation["blackboard"]', rules)
        self.assertIn("target_estimate_in_palm", rules)

    def test_author_prompt_carries_previous_sources_and_feedback(self) -> None:
        payload = json.loads(
            agent.author_ops_prompt(
                {"id": "TP01_reach_train_000"},
                {"simulation_seconds": 0.6},
                {"failure_code": "GRASP_MISS"},
                previous_ops={"locate_target": "def act(...): ..."},
                feedback={"verdict": "failure", "failure_code": "GRASP_MISS"},
            )
        )
        self.assertEqual(payload["previous_ops"], {"locate_target": "def act(...): ..."})
        self.assertEqual(payload["agent_visible_feedback"]["failure_code"], "GRASP_MISS")
        self.assertTrue(any("Revise previous_ops" in rule for rule in payload["rules"]))


if __name__ == "__main__":
    unittest.main()
