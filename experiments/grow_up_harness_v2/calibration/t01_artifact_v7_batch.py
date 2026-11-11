"""Registered v7 T01 check: control, the target failure case, and a passing case.

Each physical episode runs in its own process; no retries, no model requests.
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
V7 = PACKAGE / "artifacts/t01_cup_to_tray.yaml"
sys.path.insert(0, str(PACKAGE))

from harness import artifact as artifact_mod  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


ARMS = [("control", "saved", "control_2500"),
        ("position_310102", "generated", "position_310102"),
        ("position_310103", "generated", "position_310103")]


def main() -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, default=V7)
    args = parser.parse_args()
    artifact_path = args.artifact.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    suite = read(SUITE / "registration.json")
    cases = {row["id"]: row for row in suite["cases"]}
    source_paths = [CAL / "t01_artifact_case.py", CAL / "t01_artifact_v7.py",
                    CAL / "t01_fast.py", CAL / "t01_agent_pilot.py", CAL / "t01_motion.py",
                    PACKAGE / "harness/artifact.py", artifact_path,
                    ROOT / "experiments/t0_agent_v1/runtime.py",
                    ROOT / "experiments/t0_agent_v1/tray_verify.py",
                    ROOT / "experiments/cordis_t01/worker.py"]
    registration = {
        "date": "2026-11-06", "status": "registered_before_episodes",
        "boundary": "MuJoCo simulation; T01 single cup to tray",
        "artifact": {"path": str(artifact_path.relative_to(ROOT)),
                     "version": artifact_mod.load(artifact_path).version,
                     "digest": artifact_mod.digest(artifact_mod.load(artifact_path))},
        "parent_batch": "experiments/grow_up_harness_v2/runs/t01_artifact_v6_20261106_002/results.json",
        "repair": "raise_clear, move above tray and descend_to_lower use move_linear from the actual palm",
        "arms": [{"id": name, "kind": kind, "case": case,
                  "instance_sha256": hashlib.sha256(json.dumps(
                      cases[case]["instance"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
                 for name, kind, case in ARMS],
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in source_paths},
        "budget": {"physical_episodes": len(ARMS), "simulation_s_per_episode": 180,
                   "retries": 0, "model_requests": 0},
        "prediction": ("v7_control and v7_position_310103 still pass; v7_position_310102 no "
                      "longer raises MAX_MOVE_M in lift and reaches placement"),
        "falsification": ("any control regression, or another MAX_MOVE_M rejection, refutes "
                         "the command-cursor repair"),
    }
    (output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    rows, interrupted = [], None
    for name, kind, case in ARMS:
        target = output / name
        started = time.monotonic()
        script = CAL / ("t01_fast.py" if kind == "saved" else "t01_artifact_case.py")
        argv = [sys.executable, "-B", str(script), "--output", str(target),
                "--case", case, "--artifact", str(artifact_path), "--suite", str(SUITE)]
        with (output / f"{name}.log").open("x") as handle:
            process = subprocess.run(argv, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                                     env={**os.environ, "PYTHONPATH": str(PACKAGE),
                                          "PYTHONDONTWRITEBYTECODE": "1",
                                          "OPENBLAS_NUM_THREADS": "1", "MUJOCO_GL": "egl",
                                          "LIBGL_ALWAYS_SOFTWARE": "1"}, check=False)
        if process.returncode not in (0, 2) or not (target / "result.json").is_file():
            interrupted = {"arm": name, "returncode": process.returncode,
                           "wall_seconds": time.monotonic() - started, "retried": False}
            break
        row = read(target / "result.json")
        row.update(arm=name, wall_seconds=time.monotonic() - started)
        rows.append(row)
        if row.get("route") == "refuse":
            interrupted = {"arm": name, "reason": "artifact binding refused", "retried": False}
            break
        if name == "v7_control" and not row.get("verified_success"):
            interrupted = {"arm": name, "reason": "control failed; stop before treatment",
                           "retried": False}
            break
        print(json.dumps({"arm": name, "success": row.get("verified_success"),
                          "rejected": bool(row.get("rejected_command"))}), flush=True)
    summary = {"rows": rows, "completed": len(rows), "registered": len(ARMS),
               "interrupted": interrupted, "model_requests": 0,
               "simulation_s": sum(r.get("simulation_seconds") or 0 for r in rows),
               "wall_s": sum(r.get("wall_seconds") or 0 for r in rows),
               "successes": sum(bool(r.get("verified_success")) for r in rows)}
    (output / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in
                      ("completed", "registered", "interrupted", "successes",
                       "simulation_s", "wall_s")}, indent=2))
    return summary


if __name__ == "__main__":
    main()
