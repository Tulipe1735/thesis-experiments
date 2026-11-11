"""Dense scores add partial credit without changing the official verdict."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness import dense_eval


def cup(margin=0.0005, support=1.86, hand=0.0, other=0.0):
    return {
        "footprint_margin_m": margin, "tray_floor_support_N": support,
        "hand_contact_N": hand, "other_object_contact_N": other,
        "support_height_error_m": 0.0, "cup_tilt_deg": 0.0,
        "linear_speed_m_s": 0.0, "angular_speed_rad_s": 0.0,
        "pelvis_tilt_deg": 0.0, "pelvis_drift_m": 0.0,
        "cup_position_tray_m": [0.0, 0.0, 0.0], "lift_m": 0.12,
    }


def write_case(root: Path, name: str, *, official: bool, item: dict) -> Path:
    episode = root / name / "episode"
    episode.mkdir(parents=True)
    rows = [{"time": i * 0.05, "cups": {"task_cup": dict(item)}} for i in range(31)]
    (episode / "verified_samples.json").write_text(json.dumps(rows))
    verification = {
        "verified_success": official, "terminal_simultaneous_stable_s": 1.5 if official else 0.0,
        "final": {"cups": {"task_cup": item}}, "execution_error": None, "protection": None,
        "initial_valid": True, "max_lift_m": {"task_cup": 0.12},
    }
    path = episode / "independent_verification.json"
    path.write_text(json.dumps(verification))
    return path


class DenseEvalTests(unittest.TestCase):
    def test_sub_mm_margin_is_near_miss_but_not_official(self):
        with tempfile.TemporaryDirectory() as directory, \
             unittest.mock.patch.object(dense_eval, "ROOT", Path(directory)):
            path = write_case(Path(directory), "submm", official=False, item=cup(margin=0.0005))
            result = dense_eval.score_case(path)
        self.assertFalse(result["official_success"])
        self.assertTrue(result["relaxed_margin_success"])
        self.assertTrue(result["near_miss"])
        self.assertAlmostEqual(result["relaxed_terminal_hold_s"], 1.5)
        self.assertGreater(result["dense_score"], 0.7)
        self.assertFalse(result["official_verdict_changed"])

    def test_rim_contact_caps_dense_score(self):
        with tempfile.TemporaryDirectory() as directory, \
             unittest.mock.patch.object(dense_eval, "ROOT", Path(directory)):
            path = write_case(Path(directory), "rim", official=False,
                              item=cup(margin=0.0003, other=1.0))
            result = dense_eval.score_case(path)
        self.assertFalse(result["near_miss"])
        self.assertLessEqual(result["dense_score"], 0.45)
        self.assertIn("rim_or_other_contact", result["failure_classes"])


if __name__ == "__main__":
    unittest.main()
