"""Registered v5/v6 T01 comparison: one subprocess per physical episode.

Arms:
  v5_control     known-good saved control state, artifact v5 (baseline)
  v6_control     same state, artifact v6 (no-regression check)
  v6_position    generated case position_310102 that v5 rejected at the 5 cm guard
  v6_position_pass generated case position_310103 that v5 solved (regression)

No retries, no model requests, no threshold or evaluator changes.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "experiments/grow_up_harness_v2"
CAL = PACKAGE / "calibration"
SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_repl3_20261105_001"
V5 = PACKAGE / "artifacts/_superseded/t01_cup_to_tray_v5.yaml"
V6 = PACKAGE / "artifacts/t01_cup_to_tray.yaml"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    sys.path.insert(0, str(PACKAGE))
    from harness import artifact as artifact_mod
    return artifact_mod.digest(artifact_mod.load(path))


ARMS = [
    ("v5_control", "saved", "control_2500", V5),
    ("v6_control", "saved", "control_2500", V6),
    ("v6_position_310102", "generated", "position_310102", V6),
    ("v6_position_310103", "generated", "position_310103", V6),
]


def main() -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    registration = read(SUITE / "registration.json")
    cases = {row["id"]: row for row in registration["cases"]}
    source_paths = [
        CAL / "t01_artifact_case.py", CAL / "t01_artifact_v6.py", CAL / "t01_fast.py",
        CAL / "t01_agent_pilot.py", CAL / "t01_motion.py",
        PACKAGE / "harness/artifact.py", PACKAGE / "harness/contracts.py",
        ROOT / "experiments/t0_agent_v1/runtime.py",
        ROOT / "experiments/t0_agent_v1/tray_verify.py",
        ROOT / "experiments/t0_agent_v1/tray_tools.py",
        ROOT / "experiments/cordis_t01/worker.py",
        V5, V6,
    ]
    payload = {
        "date": "2026-11-06", "status": "registered_before_episodes",
        "boundary": "MuJoCo simulation; T01 single cup to tray",
        "task": "T01", "suite": str(SUITE.relative_to(ROOT)),
        "artifact_v5": {"path": str(V5.relative_to(ROOT)), "digest": digest(V5), "status": "superseded"},
        "artifact_v6": {"path": str(V6.relative_to(ROOT)), "digest": digest(V6), "status": "candidate"},
        "repair": "three absolute post-lean moves use move_linear instead of open-loop walk points",
        "arms": [{"id": name, "kind": kind, "case": case,
                  "instance_sha256": hashlib.sha256(json.dumps(
                      cases[case]["instance"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                  "artifact": str(artifact.relative_to(ROOT))}
                 for name, kind, case, artifact in ARMS],
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in source_paths},
        "model": registration["models"]["DH_2F_mug_06__rectangular_low_rim_v1"],
        "budget": {"physical_episodes": len(ARMS), "simulation_s_per_episode": 180,
                   "retries": 0, "model_requests": 0, "corrections_per_episode": 6},
        "prediction": ("v5_control reproduces success; v6_control also succeeds and v6_position_310103 "
                      "stays successful; v6_position_310102 no longer raises the 5 cm guard rejection "
                      "and may complete placement"),
        "falsification": ("any control regression (v5_control or v6_position_310103 fails), or "
                         "v6_position_310102 still rejected by MAX_MOVE_M, refutes the repair"),
        "controls": {"negative": "not rerun here; recorded in t01_controls_20261104_001",
                     "positive": "v5_control on the same saved state"},
        "scope_note": "position_310102/310103 are generated development instances, not validated scope",
    }
    (output / "registration.json").write_text(json.dumps(payload, indent=2) + "\n")
    rows, interrupted = [], None
    for name, kind, case, artifact in ARMS:
        target = output / name
        log = output / f"{name}.log"
        started = time.monotonic()
        if kind == "saved":
            argv = [sys.executable, "-B", str(CAL / "t01_fast.py"), "--output", str(target),
                    "--case", case, "--artifact", str(artifact), "--suite", str(SUITE)]
        else:
            argv = [sys.executable, "-B", str(CAL / "t01_artifact_case.py"), "--output", str(target),
                    "--case", case, "--artifact", str(artifact), "--suite", str(SUITE)]
        with log.open("x") as handle:
            process = subprocess.run(argv, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                                     env={**os.environ, "PYTHONPATH": str(PACKAGE),
                                          "PYTHONDONTWRITEBYTECODE": "1",
                                          "OPENBLAS_NUM_THREADS": "1", "MUJOCO_GL": "egl",
                                          "LIBGL_ALWAYS_SOFTWARE": "1"},
                                     check=False)
        if process.returncode not in (0, 2) or not (target / "result.json").is_file():
            interrupted = {"arm": name, "returncode": process.returncode,
                           "wall_seconds": time.monotonic() - started, "retried": False}
            break
        row = read(target / "result.json")
        row.update(arm=name, wall_seconds=time.monotonic() - started)
        rows.append(row)
        if row.get("route") == "refuse":
            interrupted = {"arm": name, "reason": "artifact binding refused; not executed",
                           "returncode": process.returncode, "retried": False}
            break
        if name == "v5_control" and not row.get("verified_success"):
            interrupted = {"arm": "v5_control", "reason": "baseline failed; stop before treatment",
                           "returncode": process.returncode, "retried": False}
            break
        print(json.dumps({"arm": name, "success": row.get("verified_success"),
                          "rejected": bool(row.get("rejected_command"))}), flush=True)
    summary = {
        "rows": rows, "completed": len(rows), "registered": len(ARMS),
        "interrupted": interrupted, "model_requests": 0,
        "v6_successes_on_generated": sum(r.get("verified_success") for r in rows
                                         if r.get("route") == "development_generated_case"),
        "generated_completed": sum(r.get("route") == "development_generated_case" for r in rows),
        "simulation_s": sum(r.get("simulation_seconds") or 0 for r in rows),
        "wall_s": sum(r.get("wall_seconds") or 0 for r in rows),
        "validated_scope_episodes": sum(r.get("route") == "fast" for r in rows),
    }
    (output / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in
                      ("completed", "registered", "interrupted", "v6_successes_on_generated",
                       "generated_completed", "simulation_s", "wall_s")}, indent=2))
    return summary


if __name__ == "__main__":
    main()
