from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.reports.mobile_decision_presentation import (
    post_close_canonical_cards,
    post_close_canonical_lines,
    project_card,
    render_line,
    render_post_close_email,
    render_primary,
)
from scripts.orchestrator.codex_frozen_post_close_replay import load_frozen_input, prepare


def card(symbol: str, *, no_trade: bool = False) -> dict:
    return {
        "symbol": symbol,
        "name": "測試標的" + symbol,
        "trading_date": "2026-10-20",
        "prediction_source_window": "pre_open_0700",
        "source_snapshot_id": "a" * 64,
        "prediction_snapshot_id": "a" * 64,
        "prediction_payload_hash": "b" * 64,
        "prediction_status": "no_trade" if no_trade else "active",
        "plan_status": "no_trade" if no_trade else "active",
        "predicted_direction": None if no_trade else "bullish",
        "predicted_low": None if no_trade else 100.0,
        "predicted_high": None if no_trade else 110.0,
        "direction_hit": None if no_trade else True,
        "prediction_range_result": "not_applicable" if no_trade else "partial_hit",
        "actual_status": "complete",
        "actual_open": 100.0,
        "actual_low": 99.0,
        "actual_high": 112.0,
        "actual_close": 105.0,
        "source_name": "official_fixture",
        "intraday_observed_path_evidence_v1": {
            "evidence_status": "OBSERVED_ONLY", "completeness": "SPARSE_UNVERIFIED",
            "observed_close_vs_open_direction": "DOWN", "observed_low": 98.0, "observed_high": 113.0,
        },
    }


def payload(symbols: list[str]) -> dict:
    return {
        "market": "TW", "window": "post_close_1500", "effective_trading_date": "2026-10-20",
        "notification_universe": list(symbols), "structured_review_cards": [card(symbol, no_trade=symbol == "2305") for symbol in symbols],
    }


def snapshot(symbols: list[str]) -> dict:
    return {
        "effective_trading_date": "2026-10-20",
        "metadata": {"market": "TW", "active_window": "post_close_1500", "snapshot_id": "c" * 64, "revision": 1, "payload_hash": "d" * 64},
        "payload": payload(symbols),
    }


class PostClosePresentationTests(unittest.TestCase):
    def test_formal_ohlc_wins_over_sparse_observed_path(self):
        fields = {item["label"]: item["value"] for item in project_card(card("2330"), "TW", "post_close_1500")["fields"]}
        self.assertIn("正式資料", fields["今天實際走勢"])
        self.assertIn("99.00", fields["今天實際區間"])
        self.assertNotIn("分時觀測", fields["今天實際走勢"])
        self.assertIn("預測：偏多／實際：偏多", fields["方向預測結果"])
        self.assertIn("預測：100.00–110.00／實際：99.00–112.00", fields["區間預測結果"])

    def test_no_trade_is_not_a_missing_actual_outcome(self):
        fields = {item["label"]: item["value"] for item in project_card(card("2305", no_trade=True), "TW", "post_close_1500")["fields"]}
        self.assertIn("不適用", fields["方向預測結果"])
        self.assertIn("正式資料", fields["今天實際區間"])
        self.assertIn("未提供預測", fields["今日預測結果"])

    def test_line_email_dashboard_share_dynamic_frozen_universe(self):
        symbols = ["2330", "009816", "2305"]
        value = payload(symbols)
        line = render_line(value, "TW", "post_close_1500", "https://example.invalid/dashboard")
        email = render_post_close_email(value, "TW", "post_close_1500", "https://example.invalid/dashboard")
        dashboard = render_primary(value, "TW", "post_close_1500")
        rows = post_close_canonical_lines(value, "TW", "post_close_1500")
        self.assertEqual(len(rows), len(symbols))
        for row in rows:
            self.assertEqual(line.count(row), 1)
            self.assertEqual(email.count(row), 1)
        self.assertIn("評估總覽", dashboard)
        self.assertIn("方向符合：2/2", dashboard)
        self.assertIn("區間完全符合：0/2", dashboard)

    def test_legacy_presentation_without_frozen_universe_does_not_become_delivery_universe(self):
        symbols = ["2330", "009816", "2305"]
        value = payload(symbols)
        value.pop("notification_universe")
        self.assertEqual([card["symbol"] for card in post_close_canonical_cards(value, "TW", "post_close_1500")], symbols)
        with self.assertRaisesRegex(ValueError, "FROZEN_UNIVERSE_MISSING"):
            post_close_canonical_cards(value, "TW", "post_close_1500", require_frozen_universe=True)

    def test_frozen_universe_mismatch_fails_closed(self):
        value = payload(["2330", "009816"])
        value["structured_review_cards"] = value["structured_review_cards"][:-1]
        with self.assertRaisesRegex(ValueError, "FROZEN_UNIVERSE"):
            render_line(value, "TW", "post_close_1500", "https://example.invalid", require_frozen_universe=True)


class ReceiptTimestampTests(unittest.TestCase):
    def test_line_receipt_uses_transport_time_not_report_time(self):
        from scripts.orchestrator import approved_pre_open_delivery as delivery

        frozen = snapshot(["2330"])
        sender = type("Sender", (), {"send_line_report": staticmethod(lambda _: [("private", 200)])})
        transport_time = datetime.fromisoformat("2026-10-21T10:11:12+08:00")
        with TemporaryDirectory() as raw, \
             patch.object(delivery.importlib, "import_module", return_value=sender), \
             patch.object(delivery, "now_taipei", return_value=transport_time):
            result = delivery.send_concise_line("post_close_1500", "2026-10-20T15:00:00+08:00", "completed", "https://example.invalid", "", frozen, Path(raw), rendered_message="測試")
        self.assertEqual(result["receipt"]["attempted_at"], "2026-10-21T10:11:12+08:00")

    def test_timeout_receipt_also_uses_transport_time(self):
        from scripts.orchestrator import approved_pre_open_delivery as delivery

        frozen = snapshot(["2330"])
        transport_time = datetime.fromisoformat("2026-10-21T10:11:12+08:00")
        with TemporaryDirectory() as raw, \
             patch.object(delivery.importlib, "import_module", return_value=type("Sender", (), {"send_line_report": staticmethod(lambda _: (_ for _ in ()).throw(TimeoutError("fixture")))})), \
             patch.object(delivery, "now_taipei", return_value=transport_time):
            result = delivery.send_concise_line("post_close_1500", "2026-10-20T15:00:00+08:00", "completed", "https://example.invalid", "", frozen, Path(raw), rendered_message="測試")
        self.assertEqual(result["receipt"]["attempted_at"], "2026-10-21T10:11:12+08:00")
        self.assertEqual(result["receipt"]["transport_result"], "timeout")


class CodexReplayTests(unittest.TestCase):
    def test_frozen_replay_renders_isolated_full_universe_without_sending(self):
        value = snapshot(["2330", "009816", "2305"])
        result = prepare(value, trading_date="2026-10-20", window="post_close_1500", dashboard_url="https://example.invalid/dashboard")
        self.assertEqual(result["mode"], "FROZEN_INPUT_REPLAY")
        self.assertEqual(result["expected_symbols"], ["2330", "009816", "2305"])
        self.assertFalse(result["notification_attempted"])
        self.assertFalse(result["dashboard_latest_modified"])
        self.assertEqual(len(result["canonical_rows"]), 3)

    def test_replay_rejects_wrong_date_before_rendering(self):
        with TemporaryDirectory() as raw:
            path = Path(raw) / "input.json"
            path.write_text(json.dumps(snapshot(["2330"])), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "IDENTITY_MISMATCH"):
                load_frozen_input(path, trading_date="2026-10-19", window="post_close_1500")


if __name__ == "__main__":
    unittest.main()
