"""Import selected Skill2Real text as candidate memory; no code execution.

This is a library-admission run for external prior knowledge, not a robot
experiment. It writes a new registry, verifies the public source file and each
selected entry, and records that no third-party program was executed, no
formal op exists, and no memory has been validated on G1.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import external_memory
from harness.contracts import Scope
from harness.registry import Registry
from experiments.t0_agent_v1.common import read, relative, sha, write_new

SCOPE = Scope("T01", frozenset({"DH_2F_mug_06", "rectangular_low_rim_v1"}),
              "external_prior:skill2real")


def run(output: Path, source_dir: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    raw_skill = source_dir / "skill-library-data.js"
    raw_task = source_dir / "task-data.js"
    external_memory.verify_source(raw_skill)
    registration = {
        "date": "2026-11-06", "status": "registered_before_import", "boundary": "text only; no physics, no model requests",
        "sources": {
            "skill_library": {"url": external_memory.SOURCE_URL, "sha256": sha(raw_skill)},
            "task_gallery": {"url": "https://skill2real.github.io/task-data.js",
                             "sha256": sha(raw_task)},
        },
        "selected_ids": [item.source_id for item in external_memory.SELECTED],
        "scope": SCOPE.to_dict(),
        "method": "paraphrase each selected rule with attribution; keep source and entry hashes; do not vendor or run code templates",
        "prediction": "16 candidate MemoryNotes with verified entry hashes; 0 executable skills, 0 formal admissions, 0 local executions",
        "falsification": "any source/entry hash mismatch, any note marked validated, or any third-party code executed invalidates this import",
        "third_party_code": {"vendored": False, "executed": False,
                             "reason": "site has no stated code license and its task programs are adapted_task_program, reexecuted:false"},
    }
    write_new(output / "registration.json", registration)
    copied = output / "source"
    copied.mkdir()
    skill_source = copied / "skill-library-data.js"
    task_source = copied / "task-data.js"
    skill_source.write_bytes(raw_skill.read_bytes())
    task_source.write_bytes(raw_task.read_bytes())
    notes = external_memory.notes(SCOPE, skill_source)
    registry = Registry(output / "registry")
    refs = []
    rows = []
    source_by_note = {f"mem_skill2real_{item.source_id.removeprefix('skill-')}": item.source_id
                      for item in external_memory.SELECTED}
    for note in notes:
        digest = registry.put(note)
        refs.append((note.id, digest))
        rows.append({"id": note.id, "digest": digest, "status": note.status.value,
                     "source_id": source_by_note[note.id],
                     "evidence": list(note.evidence)})
    snapshot = registry.commit(refs, label="skill2real_external_memory")
    frozen = registry.freeze(snapshot.id)
    view = registry.load(frozen.id)
    library = {"snapshot_id": frozen.id, "frozen": frozen.frozen,
               "registry_root": relative(registry.root),
               "refs": [list(ref) for ref in frozen.refs],
               "memory_count": len([a for a in view.artifacts.values() if a.kind == "memory"]),
               "formal_op_count": len(registry.op_table(frozen.id, "formal")),
               "skill_graph": {"nodes": [], "edges": []},
               "integrity": registry.verify(frozen.id),
               "source_sha256": registration["sources"]["skill_library"]["sha256"]}
    write_new(output / "library_snapshot.json", library)
    result = {
        "boundary": "external text import; no physics and no model requests",
        "selected": len(external_memory.SELECTED),
        "candidate_memories": len(rows),
        "validated_memories": 0,
        "executable_skills_imported": 0,
        "formal_admissions": 0,
        "local_executions": 0,
        "source_entry_hashes_verified": len(rows),
        "rows": rows,
        "library": library,
        "qualification": ("These notes are external prior knowledge. They can guide a future "
                          "candidate program but do not add a validated G1 effect, a callable "
                          "third-party skill, or a reuse witness."),
        "next_use": "pass notes to the author prompt as explicitly unvalidated memory; require a new local registration before any physical run",
        "load_api": "external_memory.load_registry_notes(registry_root, snapshot_id); do not regenerate notes for a reuse claim",
    }
    write_new(output / "results.json", result)
    lines = ["# Skill2Real imported memory", "",
             f"Source `{external_memory.SOURCE_URL}` SHA `{registration['sources']['skill_library']['sha256']}`.",
             "All entries are candidate-only external prior; no code was executed.", ""]
    for note in notes:
        lines += [f"## {note.id}", "", note.text, "",
                  "Evidence: " + ", ".join(f"`{item}`" for item in note.evidence), ""]
    with (output / "notes.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "library")}, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="directory holding the downloaded skill-library-data.js and task-data.js")
    args = parser.parse_args()
    run(args.output.resolve(), args.source_dir.resolve())
