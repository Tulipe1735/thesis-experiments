"""Compare the perceived cup and tray poses with the simulator truth at t=0.

No model, no episode. The skill's placement band is +/-13 mm and its passes are
2.7-9.6 mm inside it, so a perception error of a centimetre would explain the
position-group failures without any control error.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PACKAGE = ROOT / "experiments/grow_up_harness_v2"
if str(PACKAGE / "calibration") not in sys.path:
    sys.path.insert(0, str(PACKAGE / "calibration"))

import t01_agent_pilot as pilot  # noqa: E402
from experiments.cordis_t01.worker import SavedInitialRobot  # noqa: E402
from experiments.t0_agent_v1.common import read, relative, sha, write_new  # noqa: E402
from experiments.t0_agent_v1.runtime import CountedPort, PilotRobot  # noqa: E402

SUITE = ROOT / "experiments/cordis_t01/runs/t01_variation_20261028_001"


def pelvis_frame(robot, world):
    pelvis = robot.data.xpos[robot.pelvis_id]
    rotation = robot.data.xmat[robot.pelvis_id].reshape(3, 3)
    return rotation.T @ (np.asarray(world) - pelvis)


def measure(case, registration):
    instance = case["instance"]
    model = registration["models"][case["model_key"]]
    folder = Path("/tmp/opencode/perception") / case["id"]
    folder.mkdir(parents=True, exist_ok=True)
    kwargs = dict(scene_path=ROOT / model["path"], budget=registration["simulation_budget_s"])
    if case.get("initial_source"):
        robot = SavedInitialRobot(folder, instance, initial_state=ROOT / case["initial_source"], **kwargs)
    else:
        robot = PilotRobot(folder, instance, **kwargs)
    robot.advance(.75, "initial_settling")
    port = CountedPort(robot)
    state = pilot.observe(port, robot)

    cup_body = instance["cups"][0]["body"]
    cup_truth = pelvis_frame(robot, robot.data.xpos[robot.model.body(cup_body).id])
    floor_geom = robot.model.geom("tray_floor").id
    tray_truth = pelvis_frame(robot, robot.data.geom_xpos[floor_geom])

    perceived_cup = (state["cup_bottoms_m"] or [None])[0]
    perceived_tray = state["tray_floor_center_m"]
    row = {
        "case": case["id"], "group": case.get("group"), "cup_asset": case.get("cup_asset"),
        "tray_asset": case.get("tray_asset"),
        "cup_truth_xy": [round(float(v), 4) for v in cup_truth[:2]],
        "cup_perceived_xy": [round(float(v), 4) for v in perceived_cup[:2]] if perceived_cup else None,
        "cup_error_xy": ([round(float(perceived_cup[i] - cup_truth[i]), 4) for i in range(2)]
                         if perceived_cup else None),
        "tray_truth_xy": [round(float(v), 4) for v in tray_truth[:2]],
        "tray_perceived_xy": [round(float(v), 4) for v in perceived_tray[:2]] if perceived_tray else None,
        "tray_error_xy": ([round(float(perceived_tray[i] - tray_truth[i]), 4) for i in range(2)]
                          if perceived_tray else None),
        "cup_radius_prior_m": state.get("cup_radius_prior_m"),
    }
    if row["cup_error_xy"]:
        row["cup_error_norm_m"] = round(float(np.hypot(*row["cup_error_xy"])), 4)
    if row["tray_error_xy"]:
        row["tray_error_norm_m"] = round(float(np.hypot(*row["tray_error_xy"])), 4)
    robot.renderer.close()
    return row


def run(output: Path, case_ids=None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    registration = read(SUITE / "registration.json")
    cases = [c for c in registration["cases"] if not case_ids or c["id"] in case_ids]
    write_new(output / "registration.json", {
        "date": "2026-11-05", "boundary": "simulation", "kind": "t01_perception_vs_truth",
        "suite": relative(SUITE), "suite_sha256": sha(SUITE / "registration.json"),
        "cases": [c["id"] for c in cases], "model_requests": 0,
        "note": "Perceived poses are read through the same observe() the agent uses; truth is the simulator body and geom position.",
    })
    rows = [measure(case, registration) for case in cases]
    cup = [r["cup_error_norm_m"] for r in rows if r.get("cup_error_norm_m") is not None]
    tray = [r["tray_error_norm_m"] for r in rows if r.get("tray_error_norm_m") is not None]
    summary = {
        "cases": len(rows),
        "cup_error_max_m": round(max(cup), 4) if cup else None,
        "cup_error_mean_m": round(sum(cup) / len(cup), 4) if cup else None,
        "tray_error_max_m": round(max(tray), 4) if tray else None,
        "tray_error_mean_m": round(sum(tray) / len(tray), 4) if tray else None,
        "rows": rows,
    }
    write_new(output / "results.json", summary)
    for row in rows:
        print(f"{row['case']:20s} cup_err={row.get('cup_error_norm_m')} "
              f"tray_err={row.get('tray_error_norm_m')} "
              f"cup_err_xy={row['cup_error_xy']}", flush=True)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", default=None)
    args = parser.parse_args(argv)
    summary = run(args.output.resolve(), args.case)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
