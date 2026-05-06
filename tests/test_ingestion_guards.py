"""Tests for mcp_server.ingestion_guards."""

import json
import os
import tempfile
import unittest

from mcp_server.ingestion_guards import validate_write, IngestionRejected


class TestIngestionGuards(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.rejection_log = os.path.join(self.tmpdir.name, "rejected_writes.jsonl")
        os.environ["FAULKNER_REJECTION_LOG"] = self.rejection_log
        # Save and clear env vars so each test starts clean
        self._saved_env = {}
        for key in ("FAULKNER_ALLOW_AUTOMATED", "FAULKNER_INGESTION_BLOCKLIST_FILE"):
            if key in os.environ:
                self._saved_env[key] = os.environ[key]
                del os.environ[key]

    def tearDown(self):
        # Restore saved env vars
        for key, val in self._saved_env.items():
            os.environ[key] = val
        # Delete keys that were originally absent
        for key in self._saved_env:
            if key not in os.environ:
                del os.environ[key]
        self.tmpdir.cleanup()

    # --- A ---
    def test_blocklist_rejects_playbook_signature(self):
        with self.assertRaises(IngestionRejected) as ctx:
            validate_write("Pattern",
                           name_fields={"name": "playbook-routing-1234567890123"},
                           source_files=[], source="manual")
        self.assertEqual(ctx.exception.reason, "blocklist_match")

    # --- B ---
    def test_blocklist_rejects_ts13_suffix_in_any_field(self):
        with self.assertRaises(IngestionRejected) as ctx:
            validate_write("Pattern",
                           name_fields={"context": "some context-1234567890123"},
                           source_files=[], source="manual")
        self.assertEqual(ctx.exception.reason, "blocklist_match")

    # --- C ---
    def test_source_files_with_agent_genesis_substring_rejected(self):
        with self.assertRaises(IngestionRejected) as ctx:
            validate_write("Decision",
                           name_fields={"description": "a clean decision"},
                           source_files=["agent-genesis:somewhere"],
                           source="manual")
        self.assertEqual(ctx.exception.reason, "agent_genesis_source_files")

    # --- D ---
    def test_missing_source_when_allow_automated_false_rejected(self):
        with self.assertRaises(IngestionRejected) as ctx:
            validate_write("Decision",
                           name_fields={"description": "clean"},
                           source_files=[], source=None)
        self.assertEqual(ctx.exception.reason, "missing_or_invalid_source")

    # --- E ---
    def test_invalid_source_value_rejected(self):
        with self.assertRaises(IngestionRejected) as ctx:
            validate_write("Decision",
                           name_fields={"description": "clean"},
                           source_files=[], source="claude_code")
        self.assertEqual(ctx.exception.reason, "missing_or_invalid_source")

    # --- F ---
    def test_source_manual_passes(self):
        validate_write("Decision",
                       name_fields={"description": "clean description"},
                       source_files=[], source="manual")
        # no exception → pass

    # --- G ---
    def test_source_reviewed_automated_passes(self):
        validate_write("Decision",
                       name_fields={"description": "clean description"},
                       source_files=[], source="reviewed_automated")
        # no exception → pass

    # --- H ---
    def test_allow_automated_env_true_skips_source_check(self):
        os.environ["FAULKNER_ALLOW_AUTOMATED"] = "true"
        # Clean name, no agent-genesis, source=None should pass when allow_automated is true
        validate_write("Pattern",
                       name_fields={"name": "clean-pattern"},
                       source_files=[], source=None)
        # no exception → pass

    # --- I ---
    def test_rejection_writes_jsonl_line(self):
        # Trigger a rejection
        with self.assertRaises(IngestionRejected):
            validate_write("Pattern",
                           name_fields={"name": "playbook-x-1234567890123"},
                           source_files=[], source="manual")
        # Read the log
        log_path = os.environ["FAULKNER_REJECTION_LOG"]
        with open(log_path, "r") as f:
            lines = f.read().strip().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertIn("timestamp", entry)
        self.assertIn("label", entry)
        self.assertIn("reason", entry)

    # --- J ---
    def test_clean_decision_passes(self):
        validate_write("Decision",
                       name_fields={"description": "Use FalkorDB for graph storage"},
                       source_files=[], source="manual")
        # no exception → pass


if __name__ == "__main__":
    unittest.main()
