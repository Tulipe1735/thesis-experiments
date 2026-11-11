"""Step predicates: frozen thresholds, formulas, and the trace adapter."""

from __future__ import annotations

import copy
import unittest

from harness import predicates


def base_state() -> dict:
    return {
        "time": 1.0,
        "target": "cup",
        "objects": {
            "cup": {
                "position_m": [0.5, 0.0, 0.17],
                "frame": "current_pelvis",
                "pelvis_position_m": [0.5, 0.0, 0.17],
                "initial_bottom_z_m": 0.16,
                "mass_kg": 0.2,
                "hand_contact_N": 0.0,
                "upward_support_N": {"table": 1.962},
                "linear_speed_m_s": 0.0,
                "angular_speed_rad_s": 0.0,
            },
            "jar": {
                "position_m": [0.6, 0.1, 0.18],
                "frame": "current_pelvis",
                "pelvis_position_m": [0.6, 0.1, 0.18],
                "initial_bottom_z_m": 0.17,
                "mass_kg": 0.3,
                "hand_contact_N": 0.0,
                "upward_support_N": {"table": 2.943},
                "linear_speed_m_s": 0.0,
                "angular_speed_rad_s": 0.0,
            },
        },
        "robot": {"tilt_deg": 0.0, "drift_m": 0.0},
        "protection": None,
        "external_forces": False,
        "equality_constraints": 0,
        "palm": {"position_m": [0.5, 0.0, 0.17], "frame": "current_pelvis"},
        "hand": {"open_fraction": 1.0},
        "perception": {
            "target_depth_valid": True,
            "target_points": 100,
            "target_estimate": [0.5, 0.0, 0.2],
            "confidence": 0.9,
        },
    }


def held(state: dict) -> dict:
    state["objects"]["cup"]["upward_support_N"] = {"left_hand_thumb": 0.5}
    state["objects"]["cup"]["hand_contact_N"] = 0.4
    return state


def lifted(state: dict) -> dict:
    held(state)
    state["objects"]["cup"]["position_m"] = [0.5, 0.0, 0.30]
    return state


class ContractTests(unittest.TestCase):
    def test_spec_covers_every_step_predicate(self):
        self.assertEqual(set(predicates.SPECS), set(predicates.STEP_PREDICATES))
        self.assertEqual(len(predicates.STEP_PREDICATES), 10)
        for name in predicates.STEP_PREDICATES:
            self.assertTrue(predicates.SPECS[name].definition)
            self.assertTrue(predicates.SPECS[name].needs)

    def test_digest_is_stable_and_frozen(self):
        self.assertEqual(predicates.digest(), predicates.digest())
        self.assertEqual(len(predicates.digest()), 64)
        self.assertEqual(predicates.THRESHOLDS["minimum_lift_m"], 0.10)
        self.assertEqual(predicates.THRESHOLDS["stable_s"], 1.0)
        self.assertEqual(predicates.THRESHOLDS["linear_speed_m_s"], 0.02)

    def test_unknown_predicate_is_unavailable_not_false(self):
        ok, results, missing = predicates.check_all(["HeldLifted"], base_state())
        self.assertFalse(ok)
        self.assertEqual(missing, ("HeldLifted",))
        self.assertEqual(results, {})


class PredicateTests(unittest.TestCase):
    def test_guard_clear(self):
        state = base_state()
        self.assertTrue(predicates.evaluate("guard_clear", state))
        state["robot"]["tilt_deg"] = 6.0
        self.assertFalse(predicates.evaluate("guard_clear", state))
        state = base_state()
        state["protection"] = "torque"
        self.assertFalse(predicates.evaluate("guard_clear", state))

    def test_target_visible(self):
        state = base_state()
        self.assertTrue(predicates.evaluate("target_visible", state))
        state["perception"]["target_points"] = 10
        self.assertFalse(predicates.evaluate("target_visible", state))
        state = base_state()
        state["perception"]["target_depth_valid"] = False
        self.assertFalse(predicates.evaluate("target_visible", state))

    def test_hand_empty_and_open(self):
        state = base_state()
        self.assertTrue(predicates.evaluate("hand_empty", state))
        self.assertTrue(predicates.evaluate("hand_open", state))
        state["objects"]["cup"]["hand_contact_N"] = 0.2
        self.assertFalse(predicates.evaluate("hand_empty", state))
        state = base_state()
        state["hand"]["open_fraction"] = 0.3
        self.assertFalse(predicates.evaluate("hand_open", state))

    def test_target_localized_checks_shape_only(self):
        state = base_state()
        self.assertTrue(predicates.evaluate("target_localized", state))
        state["perception"]["confidence"] = 0.4
        self.assertFalse(predicates.evaluate("target_localized", state))
        state = base_state()
        del state["perception"]["target_estimate"]
        ok, _results, missing = predicates.check_all(["target_localized"], state)
        self.assertFalse(ok)
        self.assertEqual(missing, ("target_localized",))

    def test_palm_near_target(self):
        state = base_state()
        self.assertTrue(predicates.evaluate("palm_near_target", state))
        state = base_state()
        state["palm"]["position_m"] = [0.7, 0.0, 0.17]
        self.assertFalse(predicates.evaluate("palm_near_target", state))
        state = base_state()
        state["palm"]["position_m"] = [0.5, 0.0, 0.25]
        self.assertTrue(predicates.evaluate("palm_near_target", state))
        state["palm"]["position_m"] = [0.5, 0.0, 0.26]
        self.assertFalse(predicates.evaluate("palm_near_target", state))

    def test_palm_near_target_rejects_mixed_frames(self):
        state = base_state()
        state["palm"]["frame"] = "world"
        with self.assertRaises(predicates.PredicateUnavailable):
            predicates.evaluate("palm_near_target", state)
        state = base_state()
        del state["palm"]["frame"]
        with self.assertRaises(predicates.PredicateUnavailable):
            predicates.evaluate("palm_near_target", state)
        state = base_state()
        state["objects"]["cup"]["frame"] = "world"
        with self.assertRaises(predicates.PredicateUnavailable):
            predicates.evaluate("palm_near_target", state)

    def test_grasp_contact_and_holding(self):
        state = base_state()
        self.assertFalse(predicates.evaluate("grasp_contact", state))
        self.assertFalse(predicates.evaluate("holding_target", state))
        state = held(state)
        self.assertTrue(predicates.evaluate("grasp_contact", state))
        self.assertTrue(predicates.evaluate("holding_target", state))
        weak = held(base_state())
        weak["objects"]["cup"]["upward_support_N"] = {"left_hand_thumb": 0.1}
        self.assertFalse(predicates.evaluate("holding_target", weak))
        table = held(base_state())
        table["objects"]["cup"]["upward_support_N"]["table"] = 0.5
        self.assertFalse(predicates.evaluate("holding_target", table))

    def test_lifted_and_stable(self):
        state = lifted(base_state())
        self.assertTrue(predicates.evaluate("target_lifted", state))
        self.assertTrue(predicates.evaluate("target_stable", state))
        state["objects"]["cup"]["position_m"] = [0.5, 0.0, 0.20]
        self.assertFalse(predicates.evaluate("target_lifted", state))
        state = lifted(base_state())
        state["objects"]["cup"]["linear_speed_m_s"] = 0.03
        self.assertFalse(predicates.evaluate("target_stable", state))

    def test_missing_initial_bottom_is_unavailable(self):
        state = lifted(base_state())
        del state["objects"]["cup"]["initial_bottom_z_m"]
        ok, _results, missing = predicates.check_all(["target_lifted"], state)
        self.assertFalse(ok)
        self.assertEqual(missing, ("target_lifted",))


class TraceAdapterTests(unittest.TestCase):
    def instance(self) -> dict:
        return {
            "objects": [
                {"name": "cup", "asset": {"mass_kg": 0.2}},
                {"name": "jar", "asset": {"mass_kg": 0.3}},
            ]
        }

    def frame(self) -> dict:
        return {
            "time": 0.5,
            "objects": {
                "cup": {
                    "position_m": [0.5, 0.0, 0.30],
                    "hand_contact_N": 0.4,
                    "upward_support_N": {"left_hand_thumb": 0.5},
                    "linear_speed_m_s": 0.0,
                    "angular_speed_rad_s": 0.0,
                },
                "jar": {
                    "position_m": [0.6, 0.1, 0.18],
                    "hand_contact_N": 0.0,
                    "upward_support_N": {"table": 2.943},
                    "linear_speed_m_s": 0.0,
                    "angular_speed_rad_s": 0.0,
                },
            },
            "robot": {"tilt_deg": 1.0, "drift_m": 0.01},
            "external_forces": False,
            "equality_constraints": 0,
        }

    def test_trace_state_verifies_plant_predicates(self):
        state = predicates.from_trace_frame(self.frame(), self.instance(), "cup", {"cup": 0.16})
        self.assertTrue(predicates.evaluate("target_lifted", state))
        self.assertTrue(predicates.evaluate("target_stable", state))
        self.assertTrue(predicates.evaluate("guard_clear", state))
        self.assertTrue(predicates.evaluate("hand_empty", state) is False)  # cup has hand contact

    def test_trace_state_cannot_answer_perception_or_palm(self):
        state = predicates.from_trace_frame(self.frame(), self.instance(), "cup", {"cup": 0.16})
        ok, results, missing = predicates.check_all(
            ["palm_near_target", "target_visible", "hand_open", "target_lifted"], state
        )
        self.assertFalse(ok)
        self.assertEqual(
            set(missing), {"palm_near_target", "target_visible", "hand_open"}
        )
        self.assertTrue(results["target_lifted"])

    def test_without_initial_bottom_lift_is_unavailable(self):
        state = predicates.from_trace_frame(self.frame(), self.instance(), "cup")
        ok, _results, missing = predicates.check_all(["target_lifted"], state)
        self.assertFalse(ok)
        self.assertEqual(missing, ("target_lifted",))


if __name__ == "__main__":
    unittest.main()
