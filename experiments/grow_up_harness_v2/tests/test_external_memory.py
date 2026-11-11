"""External Skill2Real text enters as candidate memory, never as executable code."""

import tempfile
import unittest
from pathlib import Path

from harness import external_memory
from harness.contracts import Scope, Status
from harness.registry import Registry

PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE / "runs/skill2real_memory_import_20261106_001/source/skill-library-data.js"
SCOPE = Scope("T01", frozenset({"DH_2F_mug_06", "rectangular_low_rim_v1"}),
              "external_prior:skill2real")


class ExternalMemoryTests(unittest.TestCase):
    def test_selected_entries_match_the_hash_pinned_source(self):
        self.assertTrue(SOURCE.is_file(), "downloaded Skill2Real source snapshot is missing")
        external_memory.verify_source(SOURCE)
        entries = external_memory.source_entries(SOURCE)
        self.assertEqual(len(external_memory.SELECTED), 16)
        for item in external_memory.SELECTED:
            with self.subTest(source_id=item.source_id):
                self.assertEqual(external_memory.entry_digest(entries[item.source_id]),
                                 item.source_digest)

    def test_notes_are_candidate_text_with_provenance_and_no_code_claim(self):
        notes = external_memory.notes(SCOPE, SOURCE)
        self.assertEqual(len(notes), 16)
        for note in notes:
            with self.subTest(note=note.id):
                self.assertIs(note.status, Status.CANDIDATE)
                self.assertEqual(note.scope, SCOPE)
                self.assertIn("NOT LOCALLY VALIDATED", note.text)
                self.assertIn("not executable code", note.text)
                self.assertIn(external_memory.SOURCE_URL, note.evidence)
                self.assertTrue(any(item.startswith("entry_sha256:") for item in note.evidence))
                self.assertNotIn("def act(", note.text)

    def test_registry_import_adds_memory_only_and_no_formal_op(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Registry(Path(directory) / "registry")
            notes = external_memory.notes(SCOPE, SOURCE)
            refs = []
            for note in notes:
                refs.append((note.id, registry.put(note)))
            snapshot = registry.commit(refs, label="external_memory")
            frozen = registry.freeze(snapshot.id)
            view = registry.load(frozen.id)
            self.assertEqual(sum(artifact.kind == "memory" for artifact in view.artifacts.values()), 16)
            self.assertEqual(registry.op_table(frozen.id, "formal"), {})
            self.assertEqual(registry.skill_graph(frozen.id), {"nodes": [], "edges": []})
            self.assertTrue(registry.verify(frozen.id)["ok"])
            loaded_id, loaded = external_memory.load_registry_notes(Path(directory) / "registry")
            self.assertEqual(loaded_id, frozen.id)
            self.assertEqual([note.digest() for note in loaded], [note.digest() for note in notes])

    def test_source_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "changed.js"
            changed.write_text(SOURCE.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "source changed"):
                external_memory.verify_source(changed)


if __name__ == "__main__":
    unittest.main()
