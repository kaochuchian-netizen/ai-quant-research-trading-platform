from __future__ import annotations

import http.client
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import unittest

from app.dashboard.daily_learning_presentation import publish_dashboard
from app.evaluation.session_calendar import load_calendar
from app.history.tw_intraday_1m import (
    build_artifact, derive_path_metrics, expected_minutes, observed_path_evidence,
)
from app.reports.mobile_decision_presentation import project_card
from app.reports.tw_four_window_decision import build_observed_card, upgrade_pre_open_card
from app.reports.structured_card_diagnostics import CardValidationError
from app.reports.tw_pre_open_structured import unavailable_card

DAY = "2026-10-13"
CALENDAR = load_calendar("TW")
SOURCE = {"name": "fixture", "revision": "v1", "source_digest": "a" * 64}


def sparse_artifact():
    labels = expected_minutes(CALENDAR, DAY)[:2]
    rows = [
        {"symbol": "2330", "timestamp": labels[0], "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1},
        {"symbol": "2330", "timestamp": labels[1], "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1},
    ]
    return build_artifact(rows, symbol="2330", trading_session=DAY, calendar=CALENDAR,
                          source=SOURCE, available_at=DAY + "T13:31:00+08:00")


class DashboardPermissionTests(unittest.TestCase):
    def test_generated_latest_and_immutable_files_are_group_readable_and_http_served(self):
        value = {"identity": "a" * 64, "report_date": DAY, "markets": {}, "learning_artifact": {"markets": {}}}
        with TemporaryDirectory() as root:
            base = Path(root)
            result = publish_dashboard(value, static_root=base / "public", output_root=base / "staging")
            latest = base / "public/dashboard/daily-evaluation/latest/index.html"
            immutable = base / "public/dashboard/daily-evaluation" / DAY / ("a" * 64) / "index.html"
            self.assertEqual(os.stat(latest).st_mode & 0o777, 0o664)
            self.assertEqual(os.stat(immutable).st_mode & 0o777, 0o664)
            handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(*args, directory=str(base / "public"), **kwargs)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            worker = Thread(target=server.serve_forever, daemon=True); worker.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                conn.request("GET", result["route"])
                self.assertEqual(conn.getresponse().status, 200)
            finally:
                server.shutdown(); server.server_close(); worker.join(timeout=3)


class IntradayObservedConsumerTests(unittest.TestCase):
    def test_sparse_artifact_is_observed_only_not_full_path(self):
        evidence = observed_path_evidence(sparse_artifact(), calendar=CALENDAR)
        self.assertEqual(evidence["evidence_status"], "OBSERVED_ONLY")
        self.assertEqual(evidence["path_metrics_status"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(evidence["observed_close_vs_open_direction"], "UP")
        self.assertNotIn("verified_path_metrics", evidence)
        self.assertEqual(evidence["absent_bar_count"], 268)

    def test_sparse_evidence_is_presented_as_unverified_observation(self):
        evidence = observed_path_evidence(sparse_artifact(), calendar=CALENDAR)
        card = {"symbol": "2330", "name": "測試", "review_snapshot": {"actual_range": {"low": 90, "high": 110}},
                "intraday_observed_path_evidence_v1": evidence}
        fields = {item["label"]: item["value"] for item in project_card(card, "TW", "post_close_1500")["fields"]}
        self.assertIn("未驗證完整", fields["今天實際走勢"])
        self.assertIn("未驗證完整", fields["今天實際區間"])

    def test_reversed_predicted_range_is_never_sorted_for_path_metrics(self):
        labels = expected_minutes(CALENDAR, DAY)
        rows = [{"symbol": "2330", "timestamp": label, "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1} for label in labels]
        artifact = build_artifact(
            rows, symbol="2330", trading_session=DAY, calendar=CALENDAR, source=SOURCE,
            available_at=DAY + "T13:31:00+08:00",
            completeness_proof={"kind": "AUTHORITATIVE_FULL_SESSION_GRID_V1", "source": "fixture", "source_digest": "b" * 64, "verified_label_count": 270},
        )
        with self.assertRaisesRegex(ValueError, "PREDICTED_RANGE_REVERSED"):
            derive_path_metrics(artifact, calendar=CALENDAR, predicted_range=(102, 100))


class IntervalIntegrityTests(unittest.TestCase):
    def test_frozen_producer_rejects_reversed_entry_to_target_interval(self):
        with self.assertRaisesRegex(CardValidationError, "prediction_interval_reversed"):
            upgrade_pre_open_card(
                {"symbol": "2337", "trading_date": DAY},
                {"setup_type": "watch", "entry_zone": {"low": 100, "high": 100}, "target_1": {"low": 90, "high": 90}},
            )

    def test_legacy_invalid_frozen_interval_becomes_one_structured_card_failure(self):
        setup = {
            "symbol": "2337", "name": "測試", "trading_date": DAY, "entry_readiness": "watch",
            "strategy_type": "watch", "predicted_low": 100, "predicted_high": 90,
            "predicted_direction": "bearish", "strategies": {"daily_tactical": {"direction": "bearish"}},
            "prediction_snapshot_v2": {"prediction_status": "evaluable", "range_forecast": {"low": 100, "high": 90}},
        }
        quote = {"close": 95, "open": 100, "high": 101, "low": 94,
                 "snapshot_time": DAY + "T15:00:00+08:00", "captured_at": DAY + "T15:00:00+08:00",
                 "source_timezone": "Asia/Taipei"}
        card = build_observed_card(window="post_close_1500", setup_card=setup, quote=quote, trading_date=DAY,
                                   generated_at=DAY + "T15:00:00+08:00", source_snapshot_id="fixture",
                                   source_revision=1, source_payload_hash="fixture")
        self.assertEqual(card["prediction_failure"]["reason_code"], "prediction_interval_reversed")
        self.assertEqual(card["prediction_range_result"], "not_applicable")
        self.assertEqual(card["actual_status"], "complete")

    def test_new_preopen_invalid_interval_keeps_a_structured_failure_reason(self):
        card = unavailable_card("2337", "測試", DAY, "prediction_interval_reversed")
        self.assertEqual(card["failure_category"], "structured_card_validation_failed")
        self.assertEqual(card["failure_reason_code"], "prediction_interval_reversed")

    def test_post_close_card_binds_observed_only_evidence_without_changing_daily_ohlc(self):
        setup = {
            "symbol": "2330", "name": "測試", "trading_date": DAY, "entry_readiness": "watch",
            "strategy_type": "watch", "predicted_low": 90, "predicted_high": 110,
            "predicted_direction": "bullish", "strategies": {"daily_tactical": {"direction": "bullish"}},
        }
        quote = {"close": 102, "open": 100, "high": 103, "low": 99,
                 "snapshot_time": DAY + "T15:00:00+08:00", "captured_at": DAY + "T15:00:00+08:00",
                 "source_timezone": "Asia/Taipei"}
        evidence = observed_path_evidence(sparse_artifact(), calendar=CALENDAR)
        card = build_observed_card(window="post_close_1500", setup_card=setup, quote=quote, trading_date=DAY,
                                   generated_at=DAY + "T15:00:00+08:00", source_snapshot_id="fixture",
                                   source_revision=1, source_payload_hash="fixture", intraday_path_evidence=evidence)
        self.assertEqual(card["intraday_observed_path_evidence_v1"]["artifact_digest"], evidence["artifact_digest"])
        self.assertEqual(card["actual_trend"]["status"], "OBSERVED_ONLY")
        self.assertEqual(card["actual_range"]["completeness"], "SPARSE_UNVERIFIED")
        self.assertEqual(card["review_snapshot"]["actual_range"], {"low": 99.0, "high": 103.0})


if __name__ == "__main__":
    unittest.main()
