#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from repair_config_metadata import repair


ID = "7c3f7918-d444-45f0-8a55-172cb6d8dcaa"
OTHER = "11111111-1111-1111-1111-111111111111"


class RepairConfigMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = Path(temporary.name) / "configLibrary"
        self.config.mkdir()
        self.meta = self.config / "_meta.json"
        self.profile = self.config / f"{ID}.json"
        self.profile.write_bytes(b'{"provider":"gateway"}\n')
        self.original = b'{"extra": {"keep": 42}, "appliedId": "' + ID.encode() + b'"}\n'
        self.meta.write_bytes(self.original)
        self.backup = self.config.parent / "configLibrary-meta.backup.json"

    def test_repairs_missing_entries_without_changing_profile_or_extra_keys(self):
        profile = self.profile.read_bytes()
        self.assertTrue(repair(self.config))
        self.assertEqual(self.backup.read_bytes(), self.original)
        self.assertEqual(self.profile.read_bytes(), profile)
        self.assertEqual(json.loads(self.meta.read_bytes()), {
            "extra": {"keep": 42}, "appliedId": ID,
            "entries": [{"id": ID, "name": "Gateway"}],
        })
        updated = self.meta.read_bytes()
        self.assertFalse(repair(self.config))
        self.assertEqual(self.meta.read_bytes(), updated)

    def test_existing_valid_entries_are_byte_unchanged(self):
        existing = {"appliedId": ID, "entries": [{"id": ID, "name": "existing"}, {"id": OTHER, "name": "other"}]}
        raw = json.dumps(existing).encode()
        self.meta.write_bytes(raw)
        self.assertFalse(repair(self.config))
        self.assertEqual(self.meta.read_bytes(), raw)
        self.assertFalse(self.backup.exists())

    def test_refuses_invalid_metadata_and_profiles(self):
        cases = [b"not json", b"[]", b'{}',
                 b'{"appliedId":"../unsafe"}',
                 json.dumps({"appliedId": ID, "entries": []}).encode(),
                 json.dumps({"appliedId": ID, "entries": [{"id": OTHER, "name": "other"}]}).encode(),
                 json.dumps({"appliedId": ID, "entries": [{"id": ID, "name": "one"}, {"id": ID, "name": "two"}]}).encode(),
                 json.dumps({"appliedId": ID, "entries": [{"id": ID, "name": "\n"}]}).encode()]
        for raw in cases:
            with self.subTest(raw=raw):
                self.meta.write_bytes(raw)
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    repair(self.config)
                self.assertEqual(self.meta.read_bytes(), raw)
                self.assertFalse(self.backup.exists())
        self.meta.write_bytes(self.original)
        self.profile.write_bytes(b"[]")
        with self.assertRaises(ValueError):
            repair(self.config)
        self.profile.write_bytes(b"not json")
        with self.assertRaises(json.JSONDecodeError):
            repair(self.config)

    def test_refuses_ambiguous_profiles_backup_and_invalid_name(self):
        (self.config / f"{OTHER}.json").write_bytes(b"{}")
        with self.assertRaises(ValueError):
            repair(self.config)
        (self.config / f"{OTHER}.json").unlink()
        for name in (" ", "bad\nname", "bad\x7fname"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                repair(self.config, name)
        self.backup.write_bytes(b"existing backup")
        with self.assertRaises(FileExistsError):
            repair(self.config)
        self.assertEqual(self.backup.read_bytes(), b"existing backup")
        self.assertEqual(self.meta.read_bytes(), self.original)
        with self.assertRaises(FileNotFoundError):
            repair(self.config / "missing")

    def test_replace_failure_preserves_original_and_cleans_temp(self):
        with patch("repair_config_metadata.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                repair(self.config)
        self.assertEqual(self.meta.read_bytes(), self.original)
        self.assertEqual(self.backup.read_bytes(), self.original)
        self.assertEqual(list(self.config.glob(".meta-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
