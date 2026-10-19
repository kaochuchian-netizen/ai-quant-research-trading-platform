from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.reports.channel_delivery_receipt import delivery_identity, deliver_once, receipt_path


SNAPSHOT = {
    "effective_trading_date": "2026-10-19",
    "metadata": {
        "market": "TW", "active_window": "post_close_1500",
        "snapshot_id": "a" * 64, "revision": 1, "payload_hash": "b" * 64,
    },
}


class Tw1500DeliveryReceiptTests(unittest.TestCase):
    def identity(self, channel: str = "line") -> dict:
        return delivery_identity(snapshot=SNAPSHOT, channel=channel, market="TW", window="post_close_1500", content="內容")

    def delivery(self, root: Path, channel: str, rows: list[dict]):
        return deliver_once(
            receipt_root=root, identity=self.identity(channel), channel=channel,
            sender=lambda: {"recipients": rows, "attempted_at": "2026-10-19T15:00:00+08:00"},
        )

    def test_line_success_is_receipted_and_masked(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self.delivery(Path(raw), "line", [{"recipient": "U-secret-line-id", "status": "accepted", "status_code": 200}])
            self.assertEqual(result["send_status"], "sent")
            receipt = json.loads(Path(result["receipt_path"]).read_text())
        self.assertEqual(receipt["transport_result"], "transport_accepted")
        self.assertNotIn("U-secret-line-id", json.dumps(receipt))
        self.assertFalse(receipt["final_recipient_delivery_confirmed"])

    def test_smtp_success_is_transport_not_inbox_confirmation(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self.delivery(Path(raw), "email", [{"recipient": "person@example.test", "status": "accepted"}])
        self.assertEqual(result["transport_result"], "transport_accepted")
        self.assertFalse(result["receipt"]["final_recipient_delivery_confirmed"])

    def test_timeout_persists_terminal_receipt_and_does_not_retry(self):
        calls = []
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            identity = self.identity()
            first = deliver_once(receipt_root=root, identity=identity, channel="line", sender=lambda: calls.append(1) or {"recipients": [{"recipient": "U", "status": "timeout", "error_type": "Timeout"}]})
            second = deliver_once(receipt_root=root, identity=identity, channel="line", sender=lambda: calls.append(2) or {"recipients": [{"recipient": "U", "status": "accepted"}]})
        self.assertEqual(first["transport_result"], "timeout")
        self.assertEqual(second["send_status"], "suppressed_prior_delivery_attempt")
        self.assertEqual(calls, [1])

    def test_partial_success_is_never_claimed_as_sent(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self.delivery(Path(raw), "line", [
                {"recipient": "U1", "status": "accepted", "status_code": 200},
                {"recipient": "U2", "status": "rejected", "status_code": 429},
            ])
        self.assertEqual(result["send_status"], "failed")
        self.assertEqual(result["transport_result"], "partial_failure")

    def test_duplicate_identity_is_exactly_once(self):
        calls = []
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            identity = self.identity()
            first = deliver_once(receipt_root=root, identity=identity, channel="line", sender=lambda: calls.append(1) or {"recipients": [{"recipient": "U", "status": "accepted"}]})
            second = deliver_once(receipt_root=root, identity=identity, channel="line", sender=lambda: calls.append(2) or {"recipients": [{"recipient": "U", "status": "accepted"}]})
            self.assertEqual(receipt_path(root, identity), Path(first["receipt_path"]))
        self.assertEqual(second["send_status"], "already_delivered")
        self.assertEqual(calls, [1])

    def test_identity_binds_channel_and_rendered_content(self):
        self.assertNotEqual(self.identity("line"), self.identity("email"))
        other = delivery_identity(snapshot=SNAPSHOT, channel="line", market="TW", window="post_close_1500", content="改版內容")
        self.assertNotEqual(self.identity(), other)

    def test_line_wrapper_records_masked_per_recipient_api_acceptance(self):
        from scripts.orchestrator import approved_pre_open_delivery as wrapper
        snapshot = {**SNAPSHOT, "payload": {"structured_review_cards": []}}
        sender = SimpleNamespace(send_line_report=lambda _: [("U-private", 200)])
        with tempfile.TemporaryDirectory() as raw, patch.object(wrapper.importlib, "import_module", return_value=sender):
            result = wrapper.send_concise_line("post_close_1500", "2026-10-19T15:00:00+08:00", "completed", "https://example.invalid", "", snapshot, Path(raw))
        self.assertEqual(result["send_status"], "sent")
        self.assertEqual(result["recipient_count"], 1)
        self.assertNotIn("U-private", json.dumps(result["receipt"]))

    def test_smtp_wrapper_rejected_recipient_is_not_claimed_sent(self):
        from scripts.orchestrator import approved_pre_open_delivery as wrapper
        config = {"host": "smtp.example.test", "port": "587", "user": "u", "password": "p", "from_addr": "from@example.test", "to_addr": "to@example.test"}
        with tempfile.TemporaryDirectory() as raw, \
             patch.object(wrapper, "load_env_file"), \
             patch.object(wrapper, "load_mail_config", return_value=config), \
             patch.object(wrapper, "send_message", return_value={"to@example.test": (550, b"denied")}):
            result = wrapper.send_delivery_email(Path("/does/not/matter"), "post_close_1500", "run", "2026-10-19T15:00:00+08:00", "completed", "https://example.invalid", "", SNAPSHOT, Path(raw))
        self.assertEqual(result["send_status"], "failed")
        self.assertEqual(result["transport_result"], "failed")


if __name__ == "__main__":
    unittest.main()
