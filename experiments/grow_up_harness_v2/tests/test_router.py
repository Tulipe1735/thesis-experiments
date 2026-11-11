"""FAST/REFUSE routing over the op table, skills and the initial predicates."""

from __future__ import annotations

import unittest

from harness.contracts import (
    PlanMode,
    Predicate,
    Scope,
    Skill,
    Snapshot,
    SnapshotView,
    Status,
    Step,
    TaskSpec,
)
from harness.ops import TP01_CHAIN, make_op, spec
from harness.router import Route, decide, skill_graph

SHA = "cd" * 32


def task(template: str = "TP01") -> TaskSpec:
    return TaskSpec(
        id="TP01_reach_train_000",
        template=template,
        instruction="lift the cup",
        assets=frozenset({"cup"}),
        goal=Predicate("HeldLifted", (("object", "cup"), ("minimum_lift_m", 0.10), ("stable_s", 1.0))),
        budget_s=60.0,
    )


def state(open_fraction: float = 1.0, empty: bool = True) -> dict:
    contact = 0.0 if empty else 1.0
    return {
        "target": "cup",
        "objects": {
            "cup": {
                "position_m": [0.4, 0.3, 0.96],
                "initial_bottom_z_m": 0.96,
                "mass_kg": 0.2,
                "hand_contact_N": contact,
                "upward_support_N": {"world": 2.0},
                "linear_speed_m_s": 0.0,
                "angular_speed_rad_s": 0.0,
            }
        },
        "hand": {"open_fraction": open_fraction},
        "perception": {"target_depth_valid": True, "target_points": 100},
        "robot": {"tilt_deg": 0.0, "drift_m": 0.0},
        "protection": None,
        "external_forces": False,
        "equality_constraints": 0,
    }


def view(status: Status = Status.VALIDATED, extra: tuple = (), complete: bool = True) -> SnapshotView:
    scope = Scope("TP01", frozenset({"cup"}))
    artifacts = []
    for step in TP01_CHAIN:
        item = spec(step.op_id)
        if item.builtin:
            artifacts.append(make_op(item, scope, Status.VALIDATED))
        elif complete:
            artifacts.append(make_op(item, scope, status, f"code_{item.op_id}", SHA))
    artifacts.extend(extra)
    refs = tuple(
        (getattr(artifact, "op_id", getattr(artifact, "id", "")), artifact.digest())
        for artifact in artifacts
    )
    snapshot = Snapshot(id="snap_router", refs=refs, parent=None, label="test", frozen=False)
    return SnapshotView(snapshot, {ref: artifact for (ref, _digest), artifact in zip(refs, artifacts)})


class DecisionTests(unittest.TestCase):
    def test_validated_chain_is_fast(self) -> None:
        decision = decide(task(), view(), predicate_state=state())
        self.assertIs(decision.route, Route.FAST)
        self.assertIs(decision.mode, PlanMode.REUSE)
        self.assertEqual([step.op_id for step in decision.program.steps], [s.op_id for s in TP01_CHAIN])
        self.assertEqual(decision.program.budget_s, 31.1)

    def test_candidates_are_refused_in_formal_and_fast_in_practice(self) -> None:
        formal = decide(task(), view(Status.CANDIDATE), admission="formal", predicate_state=state())
        self.assertIs(formal.route, Route.REFUSE)
        practice = decide(task(), view(Status.CANDIDATE), admission="practice", predicate_state=state())
        self.assertIs(practice.route, Route.FAST)

    def test_missing_candidate_ops_refuse_or_slow(self) -> None:
        builtins_only = view(complete=False)
        formal = decide(task(), builtins_only, admission="formal", predicate_state=state())
        self.assertIs(formal.route, Route.REFUSE)
        practice = decide(task(), builtins_only, admission="practice", predicate_state=state())
        self.assertIs(practice.route, Route.SLOW)
        self.assertEqual(practice.mode, PlanMode.SYNTHESIZE)
        self.assertEqual(practice.authoring_request, "author:TP01_reach_train_000")

    def test_missing_predicate_state_refuses(self) -> None:
        decision = decide(task(), view())
        self.assertIs(decision.route, Route.REFUSE)
        self.assertIn("predicate_state_required", decision.reason)

    def test_unknown_template_refuses(self) -> None:
        decision = decide(task("TP99"), view())
        self.assertIs(decision.route, Route.REFUSE)
        self.assertIn("unknown task template", decision.reason)

    def test_false_initial_predicate_refuses(self) -> None:
        decision = decide(task(), view(), predicate_state=state(empty=False))
        self.assertIs(decision.route, Route.REFUSE)
        self.assertIn("hand_empty", decision.reason)

    def test_initial_predicates_clear_fast(self) -> None:
        decision = decide(task(), view(), predicate_state=state())
        self.assertIs(decision.route, Route.FAST)


class SkillGraphTests(unittest.TestCase):
    def test_edges_follow_post_to_pre(self) -> None:
        scope = Scope("TP01", frozenset({"cup"}))
        first = Skill(
            id="open",
            version=1,
            scope=scope,
            status=Status.CANDIDATE,
            validation=None,
            steps=(Step("open_hand"),),
            pre=(Predicate("guard_clear"),),
            post=(Predicate("hand_open"),),
        )
        second = Skill(
            id="close",
            version=1,
            scope=scope,
            status=Status.CANDIDATE,
            validation=None,
            steps=(Step("close_hand"),),
            pre=(Predicate("hand_open"),),
            post=(Predicate("grasp_contact"),),
        )
        graph = skill_graph(view(Status.CANDIDATE, extra=(first, second)), admission="practice")
        self.assertEqual(graph["open"], ("close",))
        self.assertEqual(graph["close"], ())


if __name__ == "__main__":
    unittest.main()
