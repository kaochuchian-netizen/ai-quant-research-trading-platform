from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.evaluation.session_calendar import load_calendar
from app.history.tw_intraday_1m import (
    archive_artifact, build_artifact, derive_path_metrics, expected_minutes,
    fetch_shioaji_1m_rows, replay_artifact, validate_artifact,
)


ROOT = Path(__file__).resolve().parents[1]
CALENDAR = load_calendar("TW")
DAY = "2026-10-13"
AVAILABLE = "2026-10-13T13:31:00+08:00"
SOURCE = {"name": "shioaji_kbars", "revision": "fixture-v1", "source_digest": "a" * 64}


def rows(count: int = 270):
    timestamps = expected_minutes(CALENDAR, DAY)[:count]
    return [{"symbol": "2330", "timestamp": timestamp, "open": 100, "high": 102,
             "low": 99, "close": 101, "volume": 10} for timestamp in timestamps]


def artifact(values=None, **kwargs):
    available_at = kwargs.pop("available_at", AVAILABLE)
    return build_artifact(rows() if values is None else values, symbol="2330", trading_session=DAY,
                          calendar=CALENDAR, source=SOURCE, available_at=available_at, **kwargs)


class CanonicalizationTests(unittest.TestCase):
    def test_valid_complete_session(self):
        value = artifact()
        self.assertEqual(value["completeness"], "COMPLETE")
        self.assertEqual(value["expected_bar_count"], 270)

    def test_unordered_identical_duplicate_is_deduped_deterministically(self):
        value = artifact()
        reordered = list(reversed(rows())) + [rows()[0]]
        self.assertEqual(value, artifact(reordered))

    def test_conflicting_duplicate_rejected(self):
        bad = rows() + [{**rows()[0], "close": 100}]
        with self.assertRaisesRegex(ValueError, "CONFLICTING_DUPLICATE_BAR"):
            artifact(bad)

    def test_missing_minutes_are_partial_not_fabricated(self):
        value = artifact(rows(2))
        self.assertEqual(value["completeness"], "PARTIAL")
        self.assertEqual(value["observed_bar_count"], 2)
        self.assertEqual(len(value["missing_bar_timestamps"]), 268)

    def test_empty_is_unavailable(self):
        self.assertEqual(artifact([])["completeness"], "UNAVAILABLE")

    def test_invalid_geometry_timestamp_and_session_rejected(self):
        with self.assertRaisesRegex(ValueError, "BAR_GEOMETRY"):
            artifact([{**rows()[0], "high": 1}])
        with self.assertRaisesRegex(ValueError, "BAR_TIMESTAMP_PRECISION"):
            artifact([{**rows()[0], "timestamp": "2026-10-13T09:00:30+08:00"}])
        with self.assertRaisesRegex(ValueError, "BAR_OUTSIDE_SESSION"):
            artifact([{**rows()[0], "timestamp": "2026-10-13T08:59:00+08:00"}])

    def test_future_incomplete_and_wrong_symbol_rejected(self):
        with self.assertRaisesRegex(ValueError, "BAR_INCOMPLETE_OR_FUTURE"):
            artifact([rows()[0]], available_at="2026-10-13T09:00:00+08:00")
        with self.assertRaisesRegex(ValueError, "BAR_SYMBOL"):
            artifact([{**rows()[0], "symbol": "2337"}])

    def test_calendar_boundary_and_non_session(self):
        self.assertEqual(expected_minutes(CALENDAR, DAY)[0], "2026-10-13T09:00:00+08:00")
        self.assertEqual(expected_minutes(CALENDAR, DAY)[-1], "2026-10-13T13:29:00+08:00")
        with self.assertRaises(ValueError):
            expected_minutes(CALENDAR, "2026-01-01")

    def test_current_tw_watchlist_symbols_are_isolated(self):
        symbols = ("2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293")
        for symbol in symbols:
            source_rows = [{**row, "symbol": symbol} for row in rows(1)]
            value = build_artifact(source_rows, symbol=symbol, trading_session=DAY, calendar=CALENDAR,
                                   source=SOURCE, available_at=AVAILABLE)
            self.assertEqual(value["symbol"], symbol)
            self.assertEqual(value["completeness"], "PARTIAL")


class ArchiveReplayTests(unittest.TestCase):
    def test_archive_is_immutable_idempotent_and_offline_replayable(self):
        value = artifact()
        with TemporaryDirectory() as tmp:
            target = archive_artifact(value, root=tmp, calendar=CALENDAR)
            self.assertIn("tw_intraday/1m/2026-10-13/2330", str(target))
            self.assertEqual(target, archive_artifact(value, root=tmp, calendar=CALENDAR))
            restored = replay_artifact(root=tmp, trading_session=DAY, symbol="2330", content_hash=value["content_hash"], calendar=CALENDAR)
            self.assertEqual(restored, value)

    def test_tamper_rejected(self):
        value = artifact(); value["bars"][0]["close"] = 1
        with self.assertRaisesRegex(ValueError, "ARTIFACT_DIGEST"):
            validate_artifact(value, calendar=CALENDAR)


class MetricsTests(unittest.TestCase):
    def test_mfe_mae_range_touch_and_close_direction(self):
        data = rows()
        data[0] = {**data[0], "open": 100, "high": 101, "low": 99, "close": 100}
        data[1] = {**data[1], "open": 100, "high": 106, "low": 98, "close": 104}
        data[-1] = {**data[-1], "open": 104, "high": 105, "low": 103, "close": 104}
        result = derive_path_metrics(artifact(data), calendar=CALENDAR, reference_price=100, predicted_range=(105, 107), flat_band=0.5)
        self.assertEqual(result["close_vs_open_direction"], "UP")
        self.assertEqual(result["mfe"], 6.0); self.assertEqual(result["mae"], -2.0)
        self.assertTrue(result["range_touch"]["touched"])
        self.assertEqual(result["range_touch"]["first_touch_at"], data[1]["timestamp"])

    def test_partial_cannot_create_metrics(self):
        result = derive_path_metrics(artifact(rows(2)), calendar=CALENDAR)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result["trend"])


class ProviderAdapterTests(unittest.TestCase):
    def test_shioaji_adapter_is_separate_from_persistence(self):
        raw = SimpleNamespace(ts=[datetime(2026, 10, 13, 9, 0)], Open=[100], High=[101], Low=[99], Close=[100], Volume=[5])
        api = SimpleNamespace(Contracts=SimpleNamespace(Stocks={"2330": "contract"}), kbars=lambda *args, **kwargs: raw)
        values = fetch_shioaji_1m_rows(api, symbol="2330", trading_session=DAY)
        self.assertEqual(values[0]["timestamp"], "2026-10-13T09:00:00")
        self.assertNotIn("content_hash", values[0])


class ContractTests(unittest.TestCase):
    def test_contract_is_offline_not_activated(self):
        value = json.loads((ROOT / "config/governance/tw_intraday_1m_contract_v1.json").read_text())
        self.assertFalse(value["production_ingestion_enabled"])
        self.assertFalse(value["production_evaluation_enabled"])
        self.assertEqual(value["interval"], "1m")


if __name__ == "__main__":
    unittest.main()
