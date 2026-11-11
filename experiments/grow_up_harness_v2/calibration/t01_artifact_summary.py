"""Summarize the registered v5-v8 T01 artifact series without changing any result."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "experiments/grow_up_harness_v2/runs"

BATCHES = [
    ("v5/v6", RUNS / "t01_artifact_v6_20261106_002" / "results.json"),
    ("v7", RUNS / "t01_artifact_v7_20261106_001" / "results.json"),
    ("v8", RUNS / "t01_artifact_v8_20261106_001" / "results.json"),
    ("v9", RUNS / "t01_artifact_v9_20261106_001" / "results.json"),
]


def main() -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for label, path in BATCHES:
        data = json.loads(path.read_text())
        for row in data["rows"]:
            artifact = row.get("artifact") or {}
            rows.append({
                "batch": label,
                "arm": row.get("arm") or row.get("case"),
                "case": row.get("case"),
                "kind": row.get("route"),
                "version": artifact.get("version"),
                "digest": artifact.get("digest"),
                "verified_success": bool(row.get("verified_success")),
                "terminal_stable_s": row.get("terminal_stable_s"),
                "footprint_margin_m": row.get("footprint_margin_m"),
                "cup_tilt_deg": row.get("cup_tilt_deg"),
                "rejected": bool(row.get("rejected_command")),
                "rejection_phase": (row.get("rejected_command") or {}).get("phase"),
                "corrections": row.get("corrections"),
                "simulation_seconds": row.get("simulation_seconds"),
                "wall_seconds": row.get("wall_seconds"),
            })
    summary = {
        "date": "2026-11-06",
        "boundary": "MuJoCo simulation; consumed development instances; no validated scope",
        "rows": rows,
        "episodes": len(rows),
        "successes": sum(row["verified_success"] for row in rows),
        "simulation_seconds": sum(row["simulation_seconds"] or 0 for row in rows),
        "wall_seconds": sum(row["wall_seconds"] or 0 for row in rows),
        "model_requests": 0,
        "by_case": {},
    }
    for row in rows:
        bucket = summary["by_case"].setdefault(row["case"], {})
        bucket[row["batch"]] = row["verified_success"]
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for row in rows:
        print(f"{row['batch']:6s} v{row['version']} {row['case']:18s} "
              f"ok={row['verified_success']!s:5s} margin={row['footprint_margin_m']} "
              f"reject={row['rejection_phase']}")
    print(json.dumps({key: summary[key] for key in
                      ("episodes", "successes", "simulation_seconds", "wall_seconds")}, indent=2))
    return summary


if __name__ == "__main__":
    main()
