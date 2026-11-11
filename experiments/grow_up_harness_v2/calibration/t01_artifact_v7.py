"""Create T01 artifact v7: lift, transport-above and descent follow the actual palm.

v6 fixed the post-lean approach but the guard still rejected a planned walk
point during lift on case position_310102: the arm carried the cup one step
behind the open-loop cursor (6.8 cm at the final point), although the cup was
held rigidly and lifted 12.2 cm. v7 sets `execution: linear` on raise_clear,
the move to place-above and descend_to_lower so each is one move_linear from
the actual palm. Targets, phases, closure, thresholds and evaluator unchanged.
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
HISTORY = PACKAGE / "artifacts/_superseded/t01_cup_to_tray_v6.yaml"
RUN = "experiments/grow_up_harness_v2/runs/t01_artifact_v7_20261106_001"


def build() -> dict:
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    if data["version"] != 6:
        raise ValueError(f"expected v6 source, found v{data['version']}")
    if HISTORY.exists():
        raise FileExistsError(f"superseded v6 copy already exists: {HISTORY}")
    HISTORY.write_bytes(SOURCE.read_bytes())

    lift = data["ir"]["phases"]["lift"]
    release = data["ir"]["phases"]["release"]
    if [step["op"] for step in lift] != ["raise_clear", "walk_to"]:
        raise ValueError(f"unexpected lift shape: {[s['op'] for s in lift]}")
    if [step["op"] for step in release] != ["descend_to_lower", "wait", "open_hand",
                                            "wait", "retreat_up", "wait", "finish"]:
        raise ValueError(f"unexpected release shape: {[s['op'] for s in release]}")
    lift[0]["execution"] = "linear"
    lift[1]["execution"] = "linear"
    release[0]["execution"] = "linear"

    data["version"] = 7
    data["provenance"]["first_run"] = RUN
    data["provenance"]["note"] = (
        "v7 continues the v6 bounded repair. Diagnosis on development case "
        "position_310102: after a successful grasp and a 12.2 cm lift, the open-loop "
        "carry points ran one step ahead of the arm (6.8 cm at the final point) and the "
        "5 cm guard rejected the move. The arm tracked its joint targets within about "
        "1 cm, so this is command-cursor accumulation, not unreachable geometry. v7 "
        "executes raise_clear, the move above the tray and descend_to_lower as one "
        "move_linear each, which interpolates from the actual palm. Targets, yaw, "
        "phases, closure, thresholds and the independent evaluator are unchanged."
    )
    data["projections"] = {
        "code": {"path": "experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v7/program.py",
                 "entry": "plan"},
        "skill": {"path": "experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v7/SKILL.md"},
    }
    data["evidence"] = {}
    data["limits"] = [
        "candidate; v7 has no paired or repair-lineage validation",
        "v5 and v6 evidence is historical and does not transfer to v7",
        "tested only on consumed development instances and the saved control state",
        "one upright white cup and one fixed tray; simulation only",
        "placement near-misses and cases outside the tried instances are unresolved",
    ]

    artifact = artifact_mod.Artifact.model_validate(data)
    SOURCE.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    manifest = artifact_mod.compile_artifact(artifact)
    old = (PACKAGE / "artifacts/generated/t01_cup_to_tray/v6/program.py").read_text().splitlines()
    new = (PACKAGE / "artifacts/generated/t01_cup_to_tray/v7/program.py").read_text().splitlines()
    diff = [line for line in difflib.unified_diff(old, new, "v6", "v7", n=1)]
    return {"artifact": str(SOURCE.relative_to(ROOT)), "version": 7,
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
