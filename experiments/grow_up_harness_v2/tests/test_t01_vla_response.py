"""Input-response analysis must not mistake right-arm changes for left-arm response."""

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "calibration"))
from t01_vla_response import NOISE_SEEDS, summarize


class ResponseAnalysisTests(unittest.TestCase):
    def test_primary_metric_excludes_right_arm_and_late_frames(self):
        names = [f"left_arm_{i}_joint" for i in range(7)]
        names += [f"right_arm_{i}_joint" for i in range(7)]
        names += [f"left_hand_{i}_joint" for i in range(7)]
        names += [f"right_hand_{i}_joint" for i in range(7)]
        with tempfile.TemporaryDirectory() as directory:
            rows = []
            for block, seed in enumerate(NOISE_SEEDS):
                baseline = np.full((1, 50, 28), block * 0.1)
                for kind, position in (("factorial", "asset_310300"), ("repeat", "asset_310300"),
                                       ("factorial", "right_change"), ("factorial", "late_left_change")):
                    values = baseline.copy()
                    if position == "right_change":
                        values[:, :, 7:14] += 0.02
                    if position == "late_left_change":
                        values[:, 15:, :7] += 0.02
                    index = len(rows) + 1
                    path = Path(directory) / f"{index}.npy"
                    np.save(path, values)
                    rows.append({"index": index, "seed": seed, "kind": kind, "position": position,
                                 "instruction": "transfer", "action_file": str(path)})
            metrics = summarize(rows, names)
        primary = metrics["left_arm_first15"]
        self.assertTrue(all(row["rmse_rad"] == 0 for row in primary["repeat_rmse"]))
        self.assertTrue(all(row["rmse_rad"] == 0 for row in primary["one_factor_effects"]))
        self.assertTrue(all(row["rmse_rad"] > 0 for row in metrics["all28_full50"]["one_factor_effects"]))
        late_effects = [row for row in metrics["left_arm_full50"]["one_factor_effects"]
                        if row["position"] == "late_left_change"]
        self.assertTrue(all(row["rmse_rad"] > 0 for row in late_effects))


if __name__ == "__main__":
    unittest.main()
