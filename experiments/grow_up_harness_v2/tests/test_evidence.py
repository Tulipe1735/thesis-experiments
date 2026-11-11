"""Episode hashes: exact coverage, tamper detection, exclusive store."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness import evidence


class HashTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="evidence-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_write_and_verify(self) -> None:
        (self.root / "a.json").write_text("{}\n", encoding="utf-8")
        (self.root / "b.txt").write_text("x\n", encoding="utf-8")
        hashes = evidence.write_hashes(self.root)
        self.assertEqual(set(hashes), {"a.json", "b.txt"})
        self.assertTrue(evidence.verify_hashes(self.root)["ok"])

    def test_tamper_is_detected(self) -> None:
        (self.root / "a.json").write_text("{}\n", encoding="utf-8")
        evidence.write_hashes(self.root)
        (self.root / "a.json").write_text('{"changed": 1}\n', encoding="utf-8")
        result = evidence.verify_hashes(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["mismatched"], ["a.json"])

    def test_unlisted_file_is_detected(self) -> None:
        (self.root / "a.json").write_text("{}\n", encoding="utf-8")
        evidence.write_hashes(self.root)
        (self.root / "late.txt").write_text("late\n", encoding="utf-8")
        result = evidence.verify_hashes(self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["unlisted"], ["late.txt"])

    def test_missing_manifest(self) -> None:
        self.assertFalse(evidence.verify_hashes(self.root)["ok"])

    def test_episode_store_is_exclusive(self) -> None:
        store = evidence.EpisodeStore(self.root / "episode")
        store.write_json("manifest.json", {"id": "x"})
        store.write_jsonl("events.jsonl", [{"event": "start"}])
        hashes = store.finalize()
        self.assertEqual(set(hashes), {"manifest.json", "events.jsonl"})
        with self.assertRaises(FileExistsError):
            evidence.EpisodeStore(self.root / "episode")


if __name__ == "__main__":
    unittest.main()
