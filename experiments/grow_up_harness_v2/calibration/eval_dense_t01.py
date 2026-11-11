"""Recompute dense T01 scores from saved samples; official verdicts unchanged."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import dense_eval
from experiments.t0_agent_v1.common import read, relative, sha, write_new

AUDIT = ROOT / "experiments/grow_up_harness_v2/runs/t01_evaluator_audit_20261106_001"


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    judge = read(AUDIT / "vlm_judge.json")
    cases = judge["ground_truth"]
    write_new(output / "registration.json", {
        "date": "2026-11-06", "kind": "dense_t01_eval_recompute", "status": "registered_before_recompute",
        "boundary": "saved simulation samples; no physics, no model requests",
        "source_audit": relative(AUDIT / "vlm_judge.json"),
        "source_sha256": sha(AUDIT / "vlm_judge.json"),
        "official_evaluator": "experiments/t0_agent_v1/tray_verify.py",
        "official_evaluator_sha256": sha(ROOT / "experiments/t0_agent_v1/tray_verify.py"),
        "dense_evaluator": relative(Path(dense_eval.__file__)),
        "dense_evaluator_sha256": sha(Path(dense_eval.__file__)),
        "cases": list(cases), "official_thresholds_unchanged": True,
        "prediction": "official stays 2/7; sub-mm margin cases become relaxed_margin_success and near_miss with high dense score; rim/negative cases stay low",
        "falsification": "if any case's official verdict or near-miss label disagrees with its saved samples, the dense decomposition is invalid",
    })
    rows = []
    for label, item in cases.items():
        result = dense_eval.score_case(ROOT / item["verification"])
        result["label"] = label
        result["official_from_audit"] = bool(item["official"])
        rows.append(result)
    summary = {
        "cases": len(rows),
        "official_successes": sum(row["official_success"] for row in rows),
        "relaxed_successes": sum(row["relaxed_margin_success"] for row in rows),
        "near_misses": sum(row["near_miss"] for row in rows),
        "rows": rows,
        "official_unchanged": all(row["official_success"] == row["official_from_audit"] for row in rows),
        "qualification": ("Dense score is a diagnostic/learning signal, not a task verdict. "
                          "Official 1 mm success remains the authority."),
    }
    write_new(output / "dense_eval.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, indent=2))
    for row in rows:
        print(f"{row['label']:18s} official={str(row['official_success']):5s} "
              f"relaxed={str(row['relaxed_margin_success']):5s} near={str(row['near_miss']):5s} "
              f"dense={row['dense_score']:.3f} margin={row['final']['footprint_margin_m']:+.6f} "
              f"classes={','.join(row['failure_classes'])}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output.resolve())
