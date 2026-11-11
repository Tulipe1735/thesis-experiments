"""Create T01 artifact v8: keep v7's lift repair, restore the stepped descent.

v7 passed position_310102 but regressed position_310103 (-24.1 mm, 12 deg,
six recenter corrections). The regression is in the release/placement phase,
which v7 changed to one move_linear descent. v8 reverts only that step to the
v6 stepped descent; lift and transport keep the from-actual-palm repair.
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
HISTORY = PACKAGE / "artifacts/_superseded/t01_cup_to_tray_v7.yaml"
RUN = "experiments/grow_up_harness_v2/runs/t01_artifact_v8_20261106_001"


def build() -> dict:
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    if data["version"] != 7:
        raise ValueError(f"expected v7 source, found v{data['version']}")
    if HISTORY.exists():
        raise FileExistsError(f"superseded v7 copy already exists: {HISTORY}")
    HISTORY.write_bytes(SOURCE.read_bytes())

    release = data["ir"]["phases"]["release"]
    if release[0]["op"] != "descend_to_lower" or release[0].get("execution") != "linear":
        raise ValueError("expected v7 linear descent")
    release[0]["execution"] = "walk"

    data["version"] = 8
    data["provenance"]["first_run"] = RUN
    data["provenance"]["note"] = (
        "v8 keeps v7's lift/transport repair (move_linear from the actual palm) and "
        "reverts only descend_to_lower to the stepped execution. v7 added "
        "position_310102 but regressed position_310103 to -24.1 mm with six recenter "
        "corrections; the regression is in the placement phase that v7 changed last. "
        "Targets, yaw, phases, closure, thresholds and evaluator are unchanged."
    )
    data["projections"] = {
        "code": {"path": "experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v8/program.py",
                 "entry": "plan"},
        "skill": {"path": "experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v8/SKILL.md"},
    }
    data["evidence"] = {}
    data["limits"] = [
        "candidate; v8 has no paired or repair-lineage validation",
        "v5, v6 and v7 evidence is historical and does not transfer to v8",
        "tested only on consumed development instances and the saved control state",
        "one upright white cup and one fixed tray; simulation only",
        "no net coverage gain has been demonstrated beyond these consumed instances",
    ]

    artifact = artifact_mod.Artifact.model_validate(data)
    SOURCE.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    manifest = artifact_mod.compile_artifact(artifact)
    old = (PACKAGE / "artifacts/generated/t01_cup_to_tray/v7/program.py").read_text().splitlines()
    new = (PACKAGE / "artifacts/generated/t01_cup_to_tray/v8/program.py").read_text().splitlines()
    diff = [line for line in difflib.unified_diff(old, new, "v7", "v8", n=1)]
    return {"artifact": str(SOURCE.relative_to(ROOT)), "version": 8,
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
