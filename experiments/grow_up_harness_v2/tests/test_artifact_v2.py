"""artifact.v2: identity, two projections, composite compilation, task tree."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from harness import artifact_v2 as A  # noqa: E402
from harness.agent import check_source  # noqa: E402
from harness.grow_loop import dry_run  # noqa: E402

TREE = json.loads((ROOT / "experiments/grow_up_harness_v2/artifacts_v2/task_tree_v1.json").read_text())
OBS = {"joints": {"left_elbow_joint": {"q": .1, "dq": 0., "target": .1}}}

# A leaf that shadows module names with parameters/locals and calls np with a
# keyword equal to a module name; it counts calls and finishes after task.n waits.
LEAF = '''import math
import numpy as np
axis = 7
COUNT = 0
def helper(axis):
    return np.sum(np.ones((2, 2)), axis=0).tolist() + [axis]
def init(profile):
    global COUNT
    COUNT = 0
    return {"i": 0}
def act(observation, task, state):
    global COUNT
    COUNT += 1
    helper(axis)
    total = [COUNT for COUNT in range(2)]
    if state["i"] >= task["n"]:
        return {"action": {"op": "done"}, "state": state}
    return {"action": {"op": "wait", "duration": task["d"]}, "state": {"i": state["i"] + 1}}
'''


def leaf_data(store, name="waiter", source=LEAF, node="B2.1"):
    return {"schema": A.SCHEMA, "kind": "leaf", "name": name, "task_node": node, "summary": "wait n times",
            "contract": {"pre": ["guard_clear"], "post": ["waited"], "failure_codes": [],
                         "params": {"n": {"type": "float", "description": "count"},
                                    "d": {"type": "float", "description": "duration"}}},
            "scope": {"task_family": "unit", "initial_sha256": [], "plant_sha256": "x"},
            "provenance": {"author": "test", "created_on": "unit"},
            "implementation": {"source_sha256": store.put_source(source)}}


def composite_data(steps, name="twice", params=("n", "d")):
    return {"schema": A.SCHEMA, "kind": "composite", "name": name, "task_node": "DEV.waypoints",
            "summary": "run steps", "contract": {"pre": ["guard_clear"], "post": ["waited"], "failure_codes": [],
            "params": {p: {"type": "float", "description": p} for p in params}},
            "scope": {"task_family": "unit", "initial_sha256": [], "plant_sha256": "x"},
            "provenance": {"author": "test", "created_on": "unit"}, "ir": steps}


def run(source, task, limit=50):
    """Execute act in-process (the Worker path is covered by dry_run tests)."""
    check_source(source)
    space = {}
    exec(compile(source, "<projection>", "exec"), space)  # noqa: S102 - test-only, trusted text
    state = space["init"]({}) if "init" in space else None
    ops = []
    for _ in range(limit):
        result = space["act"](OBS, task, state)
        state = result["state"]
        ops.append(result["action"])
        if result["action"]["op"] in ("done", "fail"):
            return ops
    raise AssertionError("did not finish")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = A.Store(Path(self.tmp.name), TREE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_leaf_identity_projection_and_evidence_do_not_change_ref(self):
        leaf = self.store.add(leaf_data(self.store))
        self.assertEqual(self.store.code(leaf), LEAF)
        before = (Path(self.tmp.name) / "artifacts" / f"{leaf}.yaml").read_bytes()
        self.store.record(leaf, "t0", True, "ep", "0" * 64)
        self.assertEqual(self.store.add(leaf_data(self.store)), leaf)
        self.assertEqual((Path(self.tmp.name) / "artifacts" / f"{leaf}.yaml").read_bytes(), before)
        self.assertIn("1/1", self.store.skill(leaf))
        self.assertEqual(self.store.verify(), {leaf: True})

    def test_unknown_node_missing_source_and_bad_fields_rejected(self):
        with self.assertRaisesRegex(ValueError, "task_node"):
            self.store.add(leaf_data(self.store, node="Z9"))
        data = leaf_data(self.store)
        data["implementation"]["source_sha256"] = "1" * 64
        with self.assertRaises(FileNotFoundError):
            self.store.add(data)
        data = leaf_data(self.store)
        data["extra"] = 1
        with self.assertRaises(ValueError):
            self.store.add(data)

    def test_single_step_composite_behaves_like_its_leaf(self):
        leaf = self.store.add(leaf_data(self.store))
        comp = self.store.add(composite_data([{"use": leaf, "params": {"n": {"task": "n"}, "d": {"task": "d"}}}]))
        task = {"n": 3, "d": .2}
        self.assertEqual(run(self.store.code(comp), task), run(LEAF, task))

    def test_composite_sequences_binds_literals_and_nests(self):
        leaf = self.store.add(leaf_data(self.store))
        inner = self.store.add(composite_data([
            {"use": leaf, "params": {"n": {"literal": 1}, "d": {"task": "d"}}},
            {"use": leaf, "params": {"n": {"task": "n"}, "d": {"literal": .1}}}], name="inner"))
        outer = self.store.add(composite_data([{"use": inner, "params": {"n": {"literal": 2}, "d": {"task": "d"}}}],
                                              name="outer", params=("d",)))
        data = composite_data([{"use": inner, "params": {"n": {"literal": 2}, "d": {"task": "d"}}}],
                              name="outer", params=("d",))
        self.assertEqual(self.store.preview_code(data), self.store.code(outer))
        ops = run(self.store.code(outer), {"d": .2})
        self.assertEqual(ops, [{"op": "wait", "duration": .2}, {"op": "wait", "duration": .1},
                               {"op": "wait", "duration": .1}, {"op": "done"}])
        self.assertTrue(dry_run(self.store.code(outer), {}, {"d": .2}, OBS, 4)["passed"])
        tree = self.store.task_tree()
        self.assertIn({"from": outer, "to": inner, "order": 0}, tree["composes"])
        self.assertIn('-->|2|', self.store.mermaid())

    def test_two_different_leaves_do_not_share_globals(self):
        a = self.store.add(leaf_data(self.store))
        other = LEAF.replace('"duration": task["d"]', '"duration": 0.04')
        b = self.store.add(leaf_data(self.store, name="fixed", source=other))
        comp = self.store.add(composite_data([
            {"use": a, "params": {"n": {"literal": 1}, "d": {"literal": .2}}},
            {"use": b, "params": {"n": {"literal": 1}, "d": {"literal": .2}}}]))
        code = self.store.code(comp)
        self.assertEqual([o.get("duration") for o in run(code, {"n": 0, "d": 0})], [.2, .04, None])

    def test_missing_binding_unknown_param_and_undeclared_task_ref_rejected(self):
        leaf = self.store.add(leaf_data(self.store))
        with self.assertRaisesRegex(ValueError, "lacks parameters"):
            self.store.add(composite_data([{"use": leaf, "params": {"n": {"task": "n"}}}]))
        with self.assertRaisesRegex(ValueError, "no parameters"):
            self.store.add(composite_data([{"use": leaf, "params": {"n": {"task": "n"}, "d": {"task": "d"},
                                                                    "z": {"literal": 1}}}]))
        with self.assertRaisesRegex(ValueError, "undeclared task param"):
            self.store.add(composite_data([{"use": leaf, "params": {"n": {"task": "q"}, "d": {"task": "d"}}}]))

    def test_import_aliases_are_isolated_between_leaves(self):
        template = '''from math import FUNC as f
def act(observation, task, state):
    if state:
        return {"action": {"op": "done"}, "state": state}
    return {"action": {"op": "wait", "duration": f(0) + 0.1}, "state": True}
'''
        leaves = [self.store.add(leaf_data(self.store, name=name, source=template.replace('FUNC', func)))
                  for name, func in [('sine_leaf', 'sin'), ('cosine_leaf', 'cos')]]
        comp = self.store.add(composite_data([
            {"use": r, "params": {"n": {"literal": 1}, "d": {"literal": .2}}} for r in leaves]))
        self.assertEqual([a.get('duration') for a in run(self.store.code(comp), {})], [.1, 1.1, None])

    def test_nested_global_bypasses_outer_local_and_class_attributes_keep_names(self):
        source = '''X = 0.2
class Box:
    X = 0.4
    def read(self):
        return X
def act(observation, task, state):
    if state:
        return {"action": {"op": "done"}, "state": state}
    X = 0.8
    def read():
        global X
        return X
    return {"action": {"op": "wait", "duration": read() + Box.X + Box().read()}, "state": True}
'''
        leaf = self.store.add(leaf_data(self.store, source=source))
        comp = self.store.add(composite_data([
            {"use": leaf, "params": {"n": {"literal": 1}, "d": {"literal": .2}}}]))
        self.assertEqual(run(self.store.code(comp), {}), run(source, {}))

    def test_missing_intermediate_parameter_and_wrong_types_are_rejected(self):
        leaf = self.store.add(leaf_data(self.store))
        inner = self.store.add(composite_data([
            {"use": leaf, "params": {"n": {"literal": 1}, "d": {"literal": .2}}}]))
        with self.assertRaisesRegex(ValueError, 'lacks parameters'):
            self.store.add(composite_data([{"use": inner, "params": {}}]))
        for value in ['bad', [1., 2., 3.], float('nan')]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'incompatible literal'):
                self.store.add(composite_data([
                    {"use": leaf, "params": {"n": {"literal": value}, "d": {"literal": .2}}}]))
        data = composite_data([{"use": leaf, "params": {"n": {"task": "n"}, "d": {"task": "d"}}}])
        data['contract']['params']['n']['type'] = 'vec3'
        with self.assertRaisesRegex(ValueError, 'incompatible task type'):
            self.store.add(data)

    def test_follows_edges_from_post_and_pre(self):
        a = self.store.add(leaf_data(self.store))
        data = leaf_data(self.store, name="after")
        data["contract"]["pre"] = ["waited"]
        b = self.store.add(data)
        self.assertIn({"from": a, "to": b, "via": ["waited"]}, self.store.task_tree()["follows"])


if __name__ == "__main__":
    unittest.main()
