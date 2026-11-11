"""Create T01 artifact v9: give the linear lift/transport enough time to converge.

v8's position_310103 trajectory is bit-identical to v7's, so the descent change
was inert there; the regression comes from v7's linear lift/transport, which
covers 17 cm in 2 s and leaves the arm short, after which the vision recenter
loop makes six corrections and ends -24.1 mm outside. v9 keeps everything and
only raises the two linear lift/transport durations to 8 s.
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
HISTORY = PACKAGE / "artifacts/_superseded/t01_cup_to_tray_v8.yaml"
RUN = "experiments/grow_up_harness_v2/runs/t01_artifact_v9_20261106_001"


def build() -> dict:
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    if data["version"] != 8:
        raise ValueError(f"expected v8 source, found v{data['version']}")
    if HISTORY.exists():
        raise FileExistsError(f"superseded v8 copy already exists: {HISTORY}")
    HISTORY.write_bytes(SOURCE.read_bytes())

    lift = data["ir"]["phases"]["lift"]
    if [step["op"] for step in lift] != ["raise_clear", "walk_to"]:
        raise ValueError(f"unexpected lift shape: {[s['op'] for s in lift]}")
    if lift[0].get("execution") != "linear" or lift[1].get("execution") != "linear":
        raise ValueError("expected v8 linear lift")
    lift[0]["seconds"] = 8.0
    lift[1]["seconds"] = 8.0

    data["version"] = 9
    data["provenance"]["first_run"] = RUN
    data["provenance"]["note"] = (
        "v9 keeps v8's structure. v8's position_310103 trajectory is bit-identical to "
        "v7's, so the descent revert was inert; the regression is caused by the linear "
        "lift/transport finishing 17 cm in 2 s and leaving the arm short, after which "
        "the vision recenter loop corrected six times and ended -24.1 mm outside. v9 "
        "gives those two linear moves 8 s, close to the time the stepped version used. "
        "Targets, phases, closure, thresholds and evaluator are unchanged."
    )
    data["projections"] = {
        "code": {"path": "experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v9/program.py",
                 "entry": "plan"},
        "skill": {"path": "experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v9/SKILL.md"},
    }
    data["evidence"] = {}
    data["limits"] = [
        "candidate; v9 has no paired or repair-lineage validation",
        "v5-v8 evidence is historical and does not transfer to v9",
        "tested only on consumed development instances and the saved control state",
        "one upright white cup and one fixed tray; simulation only",
        "the duration change is calibrated on two consumed failure cases",
    ]

    artifact = artifact_mod.Artifact.model_validate(data)
    SOURCE.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    manifest = artifact_mod.compile_artifact(artifact)
    old = (PACKAGE / "artifacts/generated/t01_cup_to_tray/v8/program.py").read_text().splitlines()
    new = (PACKAGE / "artifacts/generated/t01_cup_to_tray/v9/program.py").read_text().splitlines()
    diff = [line for line in difflib.unified_diff(old, new, "v8", "v9", n=1)]
    return {"artifact": str(SOURCE.relative_to(ROOT)), "version": 9,
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
