"""T02 adapter: FAST candidate filter, inline new leaves, and no store writes before success."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2/calibration"))

import grow_t02  # noqa: E402
from harness import artifact_v2 as A, t02_generator as G  # noqa: E402

SPLIT = ROOT / "experiments/grow_up_harness_v2/runs/t02_split_store_20261107_001/store"
TREE = ROOT / "experiments/grow_up_harness_v2/artifacts_v2/task_tree_v2.json"
LEAF = '''def act(observation, task, state):
    return {"action": {"op": "done"}, "state": state}
'''


class _Proposer:
    model = "stub"


@unittest.skipUnless(SPLIT.exists(), "split store not built")
class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(dir=ROOT))
        shutil.copytree(SPLIT, self.tmp / "store")
        self.store = A.Store(self.tmp / "store", json.loads(TREE.read_text()))
        run = grow_t02.Run.__new__(grow_t02.Run)
        run.output, run.proposer, run.config = self.tmp, _Proposer(), {"per_task": {"library_shown": 8}}
        scope = self.store.load(self.store.refs()[0]).scope
        run.family = G.FAMILY
        run.generated = {"plant": {"sha256": scope.plant_sha256}, "source_initial": {"sha256": scope.initial_sha256[0]}}
        self.run, self.task = run, {"task_id": "t", "public": {"object_count": 3., "hold_s": 1.},
                                    "private": {"initial_sha256": "0" * 64}}
        self.refs = self.store.refs()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_fast_candidates_are_whole_task_only(self):
        self.assertEqual(self.run.candidates(self.store, self.task), ["t02_three_cup_split@4b15b7d17f6e"])

    def test_library_view_lists_whole_task_first_then_parts_with_code(self):
        view = self.run.library_view(self.store, self.task)
        self.assertEqual(view[0]["ref"], "t02_three_cup_split@4b15b7d17f6e")
        self.assertEqual(len(view), 7)
        self.assertTrue(all("code" in v for v in view[1:]))

    def test_inline_leaf_compiles_without_touching_the_store(self):
        params = {k: {"task": k} for k in G.FAMILY["contract"]["params"]}
        steps = [r for r in self.refs if r.startswith("t02_cup")]
        ir = [{"use": r, "params": params} for r in steps[:5]] + [{"use": "new:soft_retreat", "params": params}]
        decision = {"kind": "composite", "name": "t02_soft_retreat", "summary": "s", "parents": [], "ir": ir,
                    "new_leaves": [{"name": "soft_retreat", "summary": "s", "task_node": "B2.4",
                                    "pre": [], "post": [], "source": LEAF}]}
        data, code = self.run.artifact_data(decision, self.task, self.store)
        compile(code, "<composite>", "exec")
        self.assertEqual(self.store.refs(), self.refs)
        self.assertEqual(len(self.run.pending), 1)
        self.assertFalse(list(self.tmp.glob("preview_*")))
        self.run.before_store_add(self.store, data)
        self.assertEqual(len(self.store.add(data).split("@")), 2)
        self.assertEqual(len(self.store.refs()), len(self.refs) + 2)

    def test_unknown_reference_is_rejected_with_a_usable_message(self):
        decision = {"kind": "composite", "name": "x", "summary": "s", "parents": [],
                    "ir": [{"use": "place_single_cup", "params": {}}]}
        with self.assertRaisesRegex(ValueError, "not in the library"):
            self.run.artifact_data(decision, self.task, self.store)

    def test_inline_leaf_with_bad_source_is_rejected(self):
        decision = {"kind": "composite", "name": "x", "summary": "s", "parents": [],
                    "ir": [{"use": "new:y", "params": {}}],
                    "new_leaves": [{"name": "y", "task_node": "B2.4", "source": "generated"}]}
        with self.assertRaisesRegex(ValueError, "top-level act"):
            self.run.artifact_data(decision, self.task, self.store)
        self.assertEqual(self.store.refs(), self.refs)


if __name__ == "__main__":
    unittest.main()
