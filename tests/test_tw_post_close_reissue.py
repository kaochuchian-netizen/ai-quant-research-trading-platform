from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.reports.channel_delivery_receipt import deliver_once, receipt_path
from app.reports.line_chunks import split_line_text
from app.reports.tw_post_close_reissue import (
    SNAPSHOT_ID, canonical_rows, delivery_identities, load_bound_snapshot, prepare_reissue,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ai_dev_275_tw_20261016_golden.json").read_text())


def snapshot(*, count: int = 10) -> dict:
    cards = deepcopy(FIXTURE["structured_review_cards"])
    symbols = list(FIXTURE["tracking_symbols"])
    if count < len(cards):
        cards, symbols = cards[:count], symbols[:count]
    while len(cards) < count:
        template = deepcopy(cards[len(cards) % len(cards)])
        symbol = f"9{len(cards):04d}"
        template["symbol"] = symbol
        template["name"] = f"動態標的{len(cards)}"
        cards.append(template)
        symbols.append(symbol)
    payload = {**deepcopy(FIXTURE), "structured_review_cards": cards, "notification_universe": symbols}
    return {
        "market": "TW", "window": "post_close_1500", "effective_trading_date": "2026-10-19",
        "snapshot_id": SNAPSHOT_ID, "revision": 1, "payload": payload,
    }


class TwPostCloseReissueTests(unittest.TestCase):
    def prepared(self):
        return prepare_reissue(snapshot(), "https://example.test/dashboard")

    def test_snapshot_binding_rejects_mismatch_before_any_delivery(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "snapshot.json"
            invalid = snapshot(); invalid["snapshot_id"] = "f" * 64
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "BINDING_MISMATCH"):
                load_bound_snapshot(path)
            self.assertEqual(list(Path(raw).glob("*.json")), [path])

    def test_line_and_email_share_all_frozen_canonical_rows(self):
        content = self.prepared()
        self.assertIn("補發／修正版", content.line)
        self.assertIn("補發／修正版", content.email)
        self.assertEqual(len(content.rows), len(FIXTURE["tracking_symbols"]))
        for row in content.rows:
            rendered = f"{row['symbol']} {row['name']}｜方向：{row['direction']}｜區間：{row['range']}"
            self.assertEqual(content.line.count(rendered), 1)
            self.assertEqual(content.email.count(rendered), 1)
        self.assertLessEqual(len(content.line), 520)

    def test_frozen_universe_is_dynamic_for_eight_and_fifteen_symbols(self):
        for count in (8, 15):
            content = prepare_reissue(snapshot(count=count), "https://example.test/dashboard")
            self.assertEqual(len(content.rows), count)
            self.assertEqual(content.line.count("｜方向："), count)
            self.assertEqual(content.email.count("｜方向："), count)
            chunks = split_line_text(content.line)
            self.assertEqual("".join(chunks), content.line)

    def test_notification_universe_is_frozen_source_and_beats_current_tracking_alias(self):
        bound = snapshot()
        bound["payload"]["tracking_symbols"] = ["9999"] * 10
        self.assertEqual([row["symbol"] for row in canonical_rows(bound)], FIXTURE["tracking_symbols"])

    def test_content_addressed_identity_differs_by_channel_and_reissue_content(self):
        content = self.prepared()
        identities = delivery_identities(content)
        self.assertEqual(identities["line"]["snapshot_id"], SNAPSHOT_ID)
        self.assertNotEqual(identities["line"], identities["email"])
        changed = prepare_reissue(snapshot(), "https://example.test/other")
        self.assertNotEqual(identities["line"], delivery_identities(changed)["line"])

    def test_duplicate_delivery_is_suppressed_after_accepted_transport(self):
        content = self.prepared()
        identity = delivery_identities(content)["line"]
        calls: list[int] = []
        with tempfile.TemporaryDirectory() as raw:
            first = deliver_once(receipt_root=Path(raw), identity=identity, channel="line", sender=lambda: calls.append(1) or {"recipients": [{"recipient": "private", "status": "accepted"}]})
            second = deliver_once(receipt_root=Path(raw), identity=identity, channel="line", sender=lambda: calls.append(2) or {"recipients": [{"recipient": "private", "status": "accepted"}]})
            receipt = json.loads(receipt_path(Path(raw), identity).read_text())
        self.assertEqual(first["send_status"], "sent")
        self.assertEqual(second["send_status"], "already_delivered")
        self.assertEqual(calls, [1])
        self.assertNotIn("private", json.dumps(receipt))
        self.assertFalse(receipt["final_recipient_delivery_confirmed"])

    def test_timeout_and_partial_failure_are_terminal_and_fail_closed(self):
        content = self.prepared()
        identity = delivery_identities(content)["email"]
        with tempfile.TemporaryDirectory() as raw:
            first = deliver_once(receipt_root=Path(raw), identity=identity, channel="email", sender=lambda: {"recipients": [{"recipient": "a", "status": "accepted"}, {"recipient": "b", "status": "timeout"}]})
            second = deliver_once(receipt_root=Path(raw), identity=identity, channel="email", sender=lambda: {"recipients": [{"recipient": "a", "status": "accepted"}]})
        self.assertEqual(first["transport_result"], "partial_failure")
        self.assertEqual(second["send_status"], "suppressed_prior_delivery_attempt")

    def test_line_override_is_receipted_with_mock_transport(self):
        from scripts.orchestrator import approved_pre_open_delivery as delivery
        sender = type("Sender", (), {"send_line_report": staticmethod(lambda message: [("private-line", 200)])})
        with tempfile.TemporaryDirectory() as raw, patch.object(delivery.importlib, "import_module", return_value=sender):
            result = delivery.send_concise_line("post_close_1500", "2026-10-19T15:00:00+08:00", "completed", "https://example.test", "", snapshot(), Path(raw), rendered_message="【2026-10-19 15:00 補發／修正版】")
        self.assertEqual(result["send_status"], "sent")
        self.assertEqual(result["transport_result"], "transport_accepted")
        self.assertNotIn("private-line", json.dumps(result["receipt"]))

    def test_existing_sender_supports_content_override_without_changing_default_contract(self):
        from scripts.orchestrator import approved_pre_open_delivery as delivery
        config = {"host": "smtp.example.test", "port": "587", "user": "u", "password": "p", "from_addr": "from@example.test", "to_addr": "to@example.test"}
        with tempfile.TemporaryDirectory() as raw, \
             patch.object(delivery, "load_env_file"), \
             patch.object(delivery, "load_mail_config", return_value=config), \
             patch.object(delivery, "send_message", return_value={}):
            result = delivery.send_delivery_email(Path("/unused"), "post_close_1500", "r", "2026-10-19T15:00:00+08:00", "completed", "https://example.test", "", snapshot(), Path(raw), rendered_body="【2026-10-19 15:00 補發／修正版】\n完整十檔", subject_prefix="【2026-10-19 15:00 補發／修正版】")
        self.assertEqual(result["send_status"], "sent")
        self.assertEqual(result["recipient_count"], 1)

    def test_canonical_rows_reject_missing_or_duplicate_symbol(self):
        broken = snapshot()
        broken["payload"]["structured_review_cards"] = broken["payload"]["structured_review_cards"][:-1]
        with self.assertRaisesRegex(ValueError, "SYMBOL_IDENTITY_MISMATCH"):
            canonical_rows(broken)
        duplicate = snapshot()
        duplicate["payload"]["structured_review_cards"][-1] = deepcopy(duplicate["payload"]["structured_review_cards"][0])
        with self.assertRaisesRegex(ValueError, "SYMBOL_IDENTITY_MISMATCH"):
            canonical_rows(duplicate)


if __name__ == "__main__":
    unittest.main()
