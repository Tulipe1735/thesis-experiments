"""Create T01 artifact v6: bounded repair of the post-lean approach commands.

Observed defect (v5, case position_310102): after the waist lean, `plan()`
emits open-loop walk points from a cursor that no longer matches the actual
palm. The next 3.5 cm step then exceeds the 5 cm single-move guard. At the
rejected command the actual palm was 6.77 cm from the target.

Repair boundary: the three absolute moves after the lean use `line_to`
(move_linear), which interpolates from the actual palm at execution time.
Targets, yaw, thresholds, phases, closure and evaluator are unchanged.
"""

import argparse
import difflib
import json
from pathlib import Path
import sys

import yaml

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PACKAGE))

from harness import artifact as artifact_mod  # noqa: E402

SOURCE = PACKAGE / "artifacts/t01_cup_to_tray.yaml"
HISTORY = PACKAGE / "artifacts/_superseded/t01_cup_to_tray_v5.yaml"
RUN = "experiments/grow_up_harness_v2/runs/t01_artifact_v6_20261106_001"


def build() -> dict:
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    if data["version"] != 5:
        raise ValueError(f"expected v5 source, found v{data['version']}")
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    if HISTORY.exists():
        raise FileExistsError(f"superseded v5 copy already exists: {HISTORY}")
    HISTORY.write_bytes(SOURCE.read_bytes())

    plan = data["ir"]["phases"]["plan"]
    expected = ["walk_to", "walk_to", "joints", "wait", "move_to", "walk_to",
                "walk_to", "close_hand", "wait"]
    actual = [step["op"] for step in plan]
    if actual != expected:
        raise ValueError(f"unexpected v5 plan shape: {actual}")

    for index in (4, 5, 6):
        step = plan[index]
        plan[index] = {
            "op": "line_to",
            "to": step["to"],
            "yaw": step["yaw"],
            "orientation": "yaw",
            "seconds": 2.0,
        }

    data["version"] = 6
    data["provenance"]["first_run"] = RUN
    data["provenance"]["note"] = (
        "v6 is a bounded repair of v5. Diagnosis: on development case "
        "position_310102 the post-lean approach used a stale open-loop cursor and one "
        "command exceeded the 5 cm single-move guard; the actual palm was 6.77 cm from "
        "the rejected target. Only the three absolute moves after the waist lean now use "
        "move_linear, which interpolates from the actual palm. Targets, yaw, closure, "
        "thresholds, phases and the independent evaluator are unchanged. v5 evidence is "
        "retained in the repository but is not evidence for v6."
    )
    data["projections"] = {
        "code": {"path": "experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v6/program.py",
                 "entry": "plan"},
        "skill": {"path": "experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v6/SKILL.md"},
    }
    data["evidence"] = {}
    data["limits"] = [
        "candidate; v6 has no paired or repair-lineage validation yet",
        "v5 paired/transfer evidence is historical and does not transfer to v6",
        "v6 is tested only on consumed development instances and the saved control state",
        "one upright white cup and one fixed tray; simulation only",
        "the post-lean move_linear repair is not yet shown to improve placement near-misses",
    ]

    artifact = artifact_mod.Artifact.model_validate(data)
    SOURCE.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    manifest = artifact_mod.compile_artifact(artifact)
    old = (PACKAGE / "artifacts/generated/t01_cup_to_tray/v5/program.py").read_text().splitlines()
    new = (PACKAGE / "artifacts/generated/t01_cup_to_tray/v6/program.py").read_text().splitlines()
    diff = [line for line in difflib.unified_diff(old, new, "v5", "v6", n=1)]
    return {"artifact": str(SOURCE.relative_to(ROOT)), "version": 6,
            "digest": artifact_mod.digest(artifact), "manifest": manifest,
            "program_diff": diff, "superseded_copy": str(HISTORY.relative_to(ROOT))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "build.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("artifact", "version", "digest", "superseded_copy")}, indent=2))
    print("\n".join(result["program_diff"]))
