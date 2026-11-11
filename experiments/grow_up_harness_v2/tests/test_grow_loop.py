"""Generated-task loop: action gate mirrors the joint outlet, labels, library, reply parsing."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from harness import grow_loop as L, task_generator  # noqa: E402
from harness.llm import extract_json  # noqa: E402

OBS = {"joints": {"left_elbow_joint": {"q": .1, "dq": 0., "target": .1},
                  "left_hand_index_0_joint": {"q": 0., "dq": 0., "target": 0.}}}
GOOD = "def act(observation, task, state):\n    return {'action': {'op': 'wait', 'duration': 0.2}, 'state': state}\n"


class ActionGateTests(unittest.TestCase):
    def test_valid_actions_pass(self):
        L.check_action({"op": "set_joints", "targets": {"left_elbow_joint": .13}, "duration": .2}, OBS)
        L.check_action({"op": "wait", "duration": .02}, OBS)
        L.check_action({"op": "done"}, OBS)

    def test_alias_key_and_extra_fields_are_rejected(self):
        for action in ({"type": "wait", "duration": .2}, {"op": "wait", "duration": .2, "x": 1},
                       {"op": "move_ee", "pose": []}):
            with self.assertRaisesRegex(ValueError, "ACTION_SCHEMA"):
                L.check_action(action, OBS)

    def test_limits_match_the_joint_outlet(self):
        with self.assertRaisesRegex(ValueError, "LOCAL_JOINT_DELTA"):
            L.check_action({"op": "set_joints", "targets": {"left_elbow_joint": .14}, "duration": .2}, OBS)
        with self.assertRaisesRegex(ValueError, "LOCAL_JOINT_SPEED"):
            L.check_action({"op": "set_joints", "targets": {"left_elbow_joint": .13}, "duration": .1}, OBS)
        with self.assertRaisesRegex(ValueError, "duration"):
            L.check_action({"op": "wait", "duration": .201}, OBS)
        with self.assertRaisesRegex(ValueError, "invalid left joint"):
            L.check_action({"op": "set_joints", "targets": {"waist_yaw_joint": 0.}, "duration": .2}, OBS)

    def test_dry_run_reports_interface_errors_without_physics(self):
        self.assertTrue(L.dry_run(GOOD, {}, {}, OBS, 3)["passed"])
        bad = GOOD.replace("'op'", "'type'")
        self.assertIn("ACTION_SCHEMA", L.dry_run(bad, {}, {}, OBS, 3)["error"])
        self.assertIn("import not allowed", L.dry_run("import os\n" + GOOD, {}, {}, OBS, 3)["error"])


class LabelTests(unittest.TestCase):
    def facts(self, **kw):
        base = {"execution_error": None, "guard": None, "unsafe_frames": 0,
                "final_position_error_m": .001, "final_orientation_error_rad": .01}
        return {**base, **kw}

    def test_rule_labels(self):
        fail = {"verified_local_success": False}
        self.assertIsNone(L.rule_label({"verified_local_success": True}, self.facts()))
        self.assertEqual(L.rule_label(fail, self.facts(execution_error={"type": "ValueError",
                         "message": "ACTION_SCHEMA: x"})), "INTERFACE")
        self.assertEqual(L.rule_label(fail, self.facts(execution_error={"type": "ValueError",
                         "message": "LOCAL_COMMAND_CAP"})), "BUDGET")
        self.assertEqual(L.rule_label(fail, self.facts(guard="SIMULATION_BUDGET_EXHAUSTED")), "BUDGET")
        self.assertEqual(L.rule_label(fail, self.facts(unsafe_frames=3)), "UNSAFE")
        self.assertEqual(L.rule_label(fail, self.facts(final_position_error_m=.02)), "NOT_REACHED")
        self.assertEqual(L.rule_label(fail, self.facts(final_orientation_error_rad=.3)), "ORIENTATION")
        self.assertEqual(L.rule_label(fail, self.facts()), "NOT_HELD")


class RunnerArtifactTests(unittest.TestCase):
    """grow.Run turns proposer replies into artifact.v2 data and picks FAST candidates."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("grow", ROOT / "experiments/grow_up_harness_v2/calibration/grow.py")
        grow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(grow)
        self.grow, self.A = grow, grow.A
        self.tmp = tempfile.TemporaryDirectory()
        self.store = self.A.Store(Path(self.tmp.name), json.loads(grow.TREE.read_text()))
        generated = task_generator.generate(91001, 1, .2)
        self.run = object.__new__(grow.Run)
        self.run.generated, self.run.family = generated, generated["family"]
        self.run.config = {"per_task": {"fast_tries": 2, "library_shown": 3}}
        self.run.proposer = type("P", (), {"model": "unit"})()
        self.task = generated["tasks"][0]

    def tearDown(self):
        self.tmp.cleanup()

    def test_fast_failure_reaches_first_slow_request(self):
        from unittest.mock import Mock
        run = self.run
        run.output = Path(self.tmp.name)
        run.counts = {"gate_rejections": 0}
        run.observation = OBS
        run.plan = {"body_geometry": {}, "caps": {"simulation_s": 1, "commands": 2}}
        run.config.update(controls={"positive": "none"})
        run.config["per_task"].update(max_physical_attempts=1, max_gate_rejections=1, gate_steps=1)
        run.rows = Mock()
        store = Mock()
        store.refs.return_value = ["recorded@abc"]
        store.task_tree.return_value = {}
        run.candidates = Mock(return_value=["recorded@abc"])
        facts = {"rule_label": "NOT_REACHED", "cups": {
            "task_cup_3": {"footprint_margin_m": 8.777654255461703e-05,
                           "moved_after_release_m": .008074879195548241}}}
        def episode(folder, task, **kwargs):
            folder.mkdir(parents=True)
            (folder / "verdict.json").write_text('{}')
            return {"success": False, "facts": facts, "error": None}
        run.episode = episode
        run.library_view = Mock(return_value=[])
        run.proposer_system = Mock(return_value="test")
        packets = []
        def ask(client, system, user, record, kind):
            packets.append(json.loads(user))
            return {"_error": "end test at reply"}
        run.ask = ask
        run.task("train", self.task, store, learn=True, scratch=False)
        history = packets[0]["previous_attempts_on_this_task"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["stage"], "fast")
        self.assertEqual(history[0]["facts"], facts)
        # Scratch must not inherit a different arm's failure facts.
        run.task("scratch", self.task, None, learn=False, scratch=True)
        self.assertEqual(packets[1]["previous_attempts_on_this_task"], [])

    def test_transport_failure_stops_instead_of_retrying(self):
        from unittest.mock import Mock
        run = self.run
        run.counts = {"proposer_calls": 0, "proposer_errors": 0, "llm_wall_s": 0}
        client = Mock()
        client.chat.side_effect = self.grow.LLMError("transport: RemoteDisconnected")
        with self.assertRaises(self.grow.LLMError):
            run.ask(client, "system", "user", Path(self.tmp.name), "proposer")
        self.assertEqual(client.chat.call_count, 1)
        self.assertEqual(run.counts["proposer_errors"], 1)
        client.chat.side_effect = self.grow.LLMReplyError("reply is not one JSON object")
        self.assertIn("_error", run.ask(client, "system", "user", Path(self.tmp.name), "proposer"))

    def test_leaf_reply_then_composite_over_it(self):
        data, code = self.run.artifact_data({"kind": "leaf", "name": "waiter", "summary": "s", "source": GOOD},
                                            self.task, self.store)
        self.assertEqual(code, GOOD)
        self.store.put_source(code)
        leaf = self.store.add(data)
        self.assertEqual(self.run.candidates(self.store, self.task), [leaf])
        binding = {p: {"task": p} for p in self.run.family["contract"]["params"]}
        data, code = self.run.artifact_data({"kind": "composite", "name": "twice", "summary": "s",
                                             "ir": [{"use": leaf, "params": binding}] * 2}, self.task, self.store)
        self.assertTrue(L.dry_run(code, {}, self.run.task_input(self.task), OBS, 3)["passed"])
        self.assertEqual(self.store.code(self.store.add(data)), code)

    def test_bad_replies_are_rejected_before_physics(self):
        for reply in ({"kind": "leaf", "name": "Bad Name", "source": GOOD},
                      {"kind": "leaf", "name": "x_y"},
                      {"kind": "composite", "name": "c_c", "ir": [{"use": "missing@000000000000", "params": {}}]},
                      {"kind": "macro", "name": "m_m"}):
            with self.assertRaises(ValueError):
                self.run.artifact_data(reply, self.task, self.store)
        with self.assertRaises(ValueError):
            self.run.artifact_data({"kind": "composite", "name": "c_c", "ir": []}, self.task, None)

    def test_family_contract_matches_migrated_leaf(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "migrate", ROOT / "experiments/grow_up_harness_v2/calibration/migrate_library_v2.py")
        migrate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migrate)
        self.assertEqual(task_generator.FAMILY["contract"], migrate.REACH_CONTRACT)
        self.assertEqual(task_generator.FAMILY["task_node"], "B2.1")


class ReplyTests(unittest.TestCase):
    def test_json_object_with_optional_fence(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(ValueError):
            extract_json("Sure! {\"a\": 1}")
        with self.assertRaises(ValueError):
            extract_json("[1]")


class GeneratorTests(unittest.TestCase):
    def test_same_seed_same_samples_and_samples_are_saved(self):
        a = task_generator.generate(91001, 2, .2)
        b = task_generator.generate(91001, 2, .2)
        self.assertEqual(a["tasks"], b["tasks"])
        task = a["tasks"][0]
        self.assertEqual(set(task["private"]["sampled_arm_q"]), set(task_generator.ARM_JOINTS))
        self.assertEqual(len(task["public"]["position_m"]), 3)
        self.assertNotIn("sampled_arm_q", task["public"])


if __name__ == "__main__":
    unittest.main()
