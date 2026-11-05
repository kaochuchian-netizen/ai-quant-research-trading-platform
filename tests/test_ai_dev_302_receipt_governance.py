"""Read-only, fail-closed receipt classification; no senders or Production IO."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.orchestrator.validate_post_merge_status import (
    classify_dirty_paths, summarize_post_merge_status, transport_receipt_error,
)
from tests.test_validate_post_merge_status import platform


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class TransportReceiptGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = {
            "schema_version": "window_snapshot_archive_v1", "market": "TW",
            "window": "pre_open_0700", "effective_trading_date": "2026-11-05",
            "revision": 1, "generated_at": "2026-11-05T07:00:00+08:00",
            "status": "complete", "run_kind": "scheduled",
            "runtime_provenance": "scheduled_production", "admitted": True,
            "payload": {"runtime_provenance": "scheduled_production", "tracking_symbols": ["009816"]},
        }
        self.snapshot["snapshot_id"] = digest(self.snapshot)
        self.source = "artifacts/archive/window_snapshots/tw/pre_open_0700/2026-11-05/revision-0001.json"
        self.write(self.source, self.snapshot)
        self.receipt = {
            "schema_version": "channel_delivery_receipt_v1", "channel": "email",
            "identity": {"market": "TW", "window": "pre_open_0700", "trading_date": "2026-11-05",
                         "revision": 1, "snapshot_id": self.snapshot["snapshot_id"],
                         "payload_hash": digest(self.snapshot["payload"]), "channel": "email",
                         "content_sha256": hashlib.sha256(b"rendered content").hexdigest()},
            "transport_result": "transport_accepted", "recipient_count": 1,
            "accepted_recipient_count": 1, "final_recipient_delivery_confirmed": False,
            "recipients": [{"recipient_mask": "sha256:" + "a" * 20, "status": "accepted"}],
            "attempted_at": "2026-11-05T07:43:05+08:00",
        }
        self.path = self.save_receipt(self.receipt)

    def write(self, path, value):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(value), encoding="utf-8")

    def save_receipt(self, value):
        path = "artifacts/runtime/delivery_receipts/tw/pre_open_0700/transport/" + digest(value["identity"]) + ".json"
        self.write(path, value)
        return path

    def classify(self, path=None):
        return classify_dirty_paths(["?? " + (path or self.path)], repo_root=self.root)

    def assert_unknown(self, path=None):
        result = self.classify(path)
        self.assertEqual(result["unknown_dirty_paths"], [path or self.path])
        self.assertEqual(result["preserved_runtime_artifacts"], [])

    def test_valid_email_line_and_terminal_failures_are_preserved_without_delivery_claim(self):
        for channel in ("email", "line"):
            for status, result in (("accepted", "transport_accepted"), ("failed", "failed"),
                                   ("timeout", "timeout"), ("unknown", "unknown")):
                with self.subTest(channel=channel, status=status):
                    value = deepcopy(self.receipt)
                    value["channel"] = value["identity"]["channel"] = channel
                    value["recipients"][0]["status"] = status
                    value["accepted_recipient_count"] = int(status == "accepted")
                    value["transport_result"] = result
                    path = self.save_receipt(value)
                    self.assertEqual(self.classify(path)["preserved_runtime_artifacts"], [path])

    def test_no_root_or_missing_source_is_unknown(self):
        self.assertEqual(classify_dirty_paths(["?? " + self.path])["unknown_dirty_paths"], [self.path])
        (self.root / self.source).unlink()
        self.assert_unknown()

    def test_schema_and_identity_fail_closed(self):
        changes = [("schema_version", "other"), ("channel", "line"),
                   ("recipient_count", True), ("accepted_recipient_count", 0),
                   ("final_recipient_delivery_confirmed", True), ("transport_result", "sent"),
                   ("recipients", {}), ("attempted_at", "2026-11-05")]
        for key, value in changes:
            with self.subTest(key=key):
                receipt = deepcopy(self.receipt)
                receipt[key] = value
                self.write(self.path, receipt)
                self.assert_unknown()
        for key, value in [("revision", True), ("revision", 0), ("revision", 2),
                           ("market", "US"), ("window", "post_close_1500"),
                           ("trading_date", "../../etc"), ("trading_date", "2026-11-06"),
                           ("snapshot_id", "a" * 64), ("payload_hash", "b" * 64),
                           ("content_sha256", "not-a-hash"), ("channel", "sms")]:
            with self.subTest(identity=key, value=value):
                receipt = deepcopy(self.receipt)
                receipt["identity"][key] = value
                self.assert_unknown(self.save_receipt(receipt))

    def test_filename_hash_mismatch_is_unknown(self):
        path = str(Path(self.path).with_name("0" * 64 + ".json"))
        self.write(path, self.receipt)
        self.assert_unknown(path)

    def test_invalid_json_duplicate_keys_and_non_finite_are_unknown(self):
        for raw in ("[]", "{", '{"schema_version":1,"schema_version":2}', '{"value":NaN}'):
            (self.root / self.path).write_text(raw)
            self.assert_unknown()

    def test_snapshot_provenance_and_hash_must_be_verified(self):
        for change in ({"schema_version": "bad"}, {"status": "failed"},
                       {"runtime_provenance": "preview"}, {"admitted": False},
                       {"revision": True}, {"market": "US"},
                       {"payload": {"runtime_provenance": "scheduled_production", "changed": True}}):
            with self.subTest(change=change):
                self.write(self.source, {**self.snapshot, **change})
                self.assert_unknown()
        # Even with recomputed hashes a non-production source cannot be admitted.
        source = {**self.snapshot, "run_kind": "fixture", "is_fixture": True}
        source.pop("snapshot_id")
        source["snapshot_id"] = digest(source)
        self.write(self.source, source)
        receipt = deepcopy(self.receipt)
        receipt["identity"]["snapshot_id"] = source["snapshot_id"]
        self.assert_unknown(self.save_receipt(receipt))

    def test_path_spoofing_does_not_expand_allowlist(self):
        paths = [self.path.replace("transport/", "transport/../"),
                 self.path.replace("transport/", "transport/nested/"),
                 self.path + ".bak", self.path.replace("/tw/", "/us/"),
                 self.path.replace("pre_open_0700", "intraday_1305"),
                 "/" + self.path, "./" + self.path,
                 self.path.replace(".json", ".py"),
                 str(Path(self.path).with_name("A" * 64 + ".json"))]
        for path in paths:
            with self.subTest(path=path):
                self.assert_unknown(path)

    def test_rename_delete_type_change_and_quoted_status_cannot_hide_residue(self):
        for entry in ("R  app/source.py -> " + self.path, " D " + self.path,
                      " T " + self.path, '?? "' + self.path + '"', "?? " + self.path + " "):
            with self.subTest(entry=entry):
                result = classify_dirty_paths([entry], repo_root=self.root)
                self.assertEqual(result["preserved_runtime_artifacts"], [])
                self.assertTrue(result["unknown_dirty_paths"])

    def test_receipt_and_snapshot_symlinks_and_fifo_are_rejected(self):
        for relative in (self.path, self.source):
            path = self.root / relative
            data = path.read_bytes()
            outside = self.root / "outside.json"
            outside.write_bytes(data)
            path.unlink()
            path.symlink_to(outside)
            self.assert_unknown()
            path.unlink()
            path.write_bytes(data)
        path = self.root / self.path
        path.unlink()
        os.mkfifo(path)
        self.assert_unknown()

    def test_parent_symlink_is_rejected(self):
        parent = (self.root / self.path).parent
        moved = parent.with_name("real-transport")
        parent.rename(moved)
        parent.symlink_to(moved, target_is_directory=True)
        self.assert_unknown()

    def test_oversized_unreadable_or_changed_file_is_unknown(self):
        with patch("scripts.orchestrator.validate_post_merge_status.os.open", side_effect=PermissionError):
            self.assert_unknown()
        (self.root / self.path).write_bytes(b" " * (1024 * 1024 + 1))
        self.assert_unknown()

    def test_summary_uses_explicit_root_and_keeps_original_rules(self):
        entries = ["?? " + self.path, " M artifacts/runtime/formal_prediction_runtime_latest.json"]
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.root / self.path, self.root / self.source)}
        report = summarize_post_merge_status(platform(status=entries), repo_root=self.root)
        self.assertTrue(report["worktree_governance_safe"])
        self.assertEqual(report["unknown_dirty_paths"], [])
        self.assertEqual(report["blocking_task_residue"], [])
        self.assertEqual(len(report["preserved_runtime_artifacts"]), 2)
        for path, retained in before.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), retained)
        report = classify_dirty_paths(entries + [" M app/source.py", "?? mystery.json"], repo_root=self.root)
        self.assertEqual(report["blocking_task_residue"], ["app/source.py"])
        self.assertEqual(report["unknown_dirty_paths"], ["mystery.json"])


if __name__ == "__main__":
    unittest.main()
