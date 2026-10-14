from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.evaluation.session_calendar import load_calendar
from app.history.tw_intraday_1m import (
    FULL_SESSION_PROOF_KIND, PARTIAL_PROOF_KIND, archive_artifact, build_artifact,
    decode_shioaji_kbars_timestamp, derive_path_metrics, expected_minutes,
    fetch_shioaji_1m_rows, replay_artifact, validate_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = load_calendar("TW")
DAY = "2026-10-13"
AVAILABLE = "2026-10-13T13:31:00+08:00"
SOURCE = {"name": "shioaji_kbars", "revision": "fixture-v2", "source_digest": "a" * 64}
WATCHLIST = ("2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293")
PRODUCTION_OBSERVED_COUNTS = {"2330": 266, "009816": 264, "2337": 266, "2353": 259, "6873": 77, "4743": 180, "2305": 265, "00878": 266, "1409": 263, "3293": 211}


def full_proof():
    return {"kind": FULL_SESSION_PROOF_KIND, "source": "fixture-authority", "source_digest": "b" * 64, "verified_label_count": 270}


def partial_proof(count: int):
    return {"kind": PARTIAL_PROOF_KIND, "source": "fixture-authority", "source_digest": "c" * 64, "verified_label_count": count}


def rows(count: int = 270, symbol: str = "2330"):
    timestamps = expected_minutes(CALENDAR, DAY)[:count]
    return [{"symbol": symbol, "timestamp": timestamp, "open": 100, "high": 102, "low": 99, "close": 101, "volume": 10} for timestamp in timestamps]


def artifact(values=None, **kwargs):
    available_at = kwargs.pop("available_at", AVAILABLE)
    proof = kwargs.pop("completeness_proof", full_proof() if values is None else None)
    return build_artifact(rows() if values is None else values, symbol="2330", trading_session=DAY, calendar=CALENDAR, source=SOURCE, available_at=available_at, completeness_proof=proof, **kwargs)


class TimestampAndGridTests(unittest.TestCase):
    def test_raw_ns_provider_decoder_is_explicit_local_wall_clock(self):
        self.assertEqual(decode_shioaji_kbars_timestamp(1791882060000000000), "2026-10-13T09:01:00+08:00")

    def test_decoder_is_not_ambient_timezone_dependent(self):
        raw = 1791882060000000000
        self.assertEqual(decode_shioaji_kbars_timestamp(raw), decode_shioaji_kbars_timestamp(str(raw)))

    def test_bar_end_grid_has_authoritative_labels(self):
        grid = expected_minutes(CALENDAR, DAY)
        self.assertEqual(len(grid), 270)
        self.assertEqual(grid[0], "2026-10-13T09:01:00+08:00")
        self.assertEqual(grid[-1], "2026-10-13T13:30:00+08:00")
        with self.assertRaises(ValueError):
            expected_minutes(CALENDAR, "2026-01-01")


class CanonicalizationTests(unittest.TestCase):
    def test_complete_requires_positive_full_session_proof(self):
        value = artifact()
        self.assertEqual(value["completeness"], "COMPLETE")
        self.assertEqual(value["expected_bar_count"], 270)
        self.assertEqual(value["coverage_ratio"], 1.0)

    def test_sparse_kbars_without_proof_is_not_partial(self):
        value = artifact(rows(77), completeness_proof=None)
        self.assertEqual(value["completeness"], "SPARSE_UNVERIFIED")
        self.assertEqual(value["absent_bar_count"], 193)
        self.assertEqual(value["coverage_ratio"], 77 / 270)

    def test_partial_requires_independent_acquisition_proof(self):
        value = artifact(rows(2), completeness_proof=partial_proof(2))
        self.assertEqual(value["completeness"], "PARTIAL")
        with self.assertRaisesRegex(ValueError, "COMPLETE_PROOF_MISMATCH"):
            artifact(rows(2), completeness_proof=full_proof())

    def test_empty_is_unavailable(self):
        self.assertEqual(artifact([], completeness_proof=None)["completeness"], "UNAVAILABLE")

    def test_unordered_identical_duplicate_is_deduped_deterministically(self):
        value = artifact()
        reordered = list(reversed(rows())) + [rows()[0]]
        self.assertEqual(value, artifact(reordered, completeness_proof=full_proof()))

    def test_conflicting_duplicate_rejected(self):
        bad = rows() + [{**rows()[0], "close": 100}]
        with self.assertRaisesRegex(ValueError, "CONFLICTING_DUPLICATE_BAR"):
            artifact(bad, completeness_proof=full_proof())

    def test_invalid_geometry_timestamp_and_session_rejected(self):
        with self.assertRaisesRegex(ValueError, "BAR_GEOMETRY"):
            artifact([{**rows()[0], "high": 1}], completeness_proof=None)
        with self.assertRaisesRegex(ValueError, "BAR_TIMESTAMP_PRECISION"):
            artifact([{**rows()[0], "timestamp": "2026-10-13T09:01:30+08:00"}], completeness_proof=None)
        with self.assertRaisesRegex(ValueError, "BAR_OUTSIDE_SESSION"):
            artifact([{**rows()[0], "timestamp": "2026-10-13T09:00:00+08:00"}], completeness_proof=None)

    def test_future_incomplete_and_wrong_symbol_rejected(self):
        with self.assertRaisesRegex(ValueError, "BAR_INCOMPLETE_OR_FUTURE"):
            artifact([rows()[0]], available_at="2026-10-13T09:00:00+08:00", completeness_proof=None)
        with self.assertRaisesRegex(ValueError, "BAR_SYMBOL"):
            artifact([{**rows()[0], "symbol": "2337"}], completeness_proof=None)

    def test_all_current_watchlist_production_coverage_fixtures_remain_sparse_unverified(self):
        for symbol in WATCHLIST:
            observed_count = PRODUCTION_OBSERVED_COUNTS[symbol]
            value = build_artifact(rows(observed_count, symbol), symbol=symbol, trading_session=DAY, calendar=CALENDAR, source=SOURCE, available_at=AVAILABLE)
            self.assertEqual(value["symbol"], symbol)
            self.assertEqual(value["observed_bar_count"], observed_count)
            self.assertEqual(value["completeness"], "SPARSE_UNVERIFIED")


class ArchiveReplayTests(unittest.TestCase):
    def test_archive_is_immutable_idempotent_and_offline_replayable(self):
        value = artifact()
        with TemporaryDirectory() as tmp:
            target = archive_artifact(value, root=tmp, calendar=CALENDAR)
            self.assertIn("tw_intraday/1m/v2/2026-10-13/2330", str(target))
            self.assertEqual(target, archive_artifact(value, root=tmp, calendar=CALENDAR))
            restored = replay_artifact(root=tmp, trading_session=DAY, symbol="2330", content_hash=value["content_hash"], calendar=CALENDAR)
            self.assertEqual(restored, value)

    def test_tamper_rejected(self):
        value = artifact(); value["bars"][0]["close"] = 1
        with self.assertRaisesRegex(ValueError, "ARTIFACT_DIGEST"):
            validate_artifact(value, calendar=CALENDAR)

    def test_v1_bar_open_artifact_cannot_silently_validate_as_v2(self):
        v1 = artifact()
        v1["schema_version"] = "tw_intraday_1m_artifact_v1"
        v1["bar_timestamp_convention"] = "BAR_OPEN_TIMESTAMP_HALF_OPEN_1M"
        with self.assertRaisesRegex(ValueError, "ARTIFACT_IDENTITY|ARTIFACT_SCHEMA"):
            validate_artifact(v1, calendar=CALENDAR)


class MetricsTests(unittest.TestCase):
    def test_mfe_mae_range_touch_and_close_direction_with_proven_complete_path(self):
        data = rows()
        data[0] = {**data[0], "open": 100, "high": 101, "low": 99, "close": 100}
        data[1] = {**data[1], "open": 100, "high": 106, "low": 98, "close": 104}
        data[-1] = {**data[-1], "open": 104, "high": 105, "low": 103, "close": 104}
        result = derive_path_metrics(artifact(data, completeness_proof=full_proof()), calendar=CALENDAR, reference_price=100, predicted_range=(105, 107), flat_band=0.5)
        self.assertEqual(result["close_vs_open_direction"], "UP")
        self.assertEqual(result["mfe"], 6.0); self.assertEqual(result["mae"], -2.0)
        self.assertTrue(result["range_touch"]["touched"])
        self.assertEqual(result["range_touch"]["first_touch_at"], data[1]["timestamp"])

    def test_unproven_sparse_path_cannot_create_metrics(self):
        result = derive_path_metrics(artifact(rows(77), completeness_proof=None), calendar=CALENDAR)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result["trend"])
        self.assertIsNone(result["mfe"])


class ProviderAdapterTests(unittest.TestCase):
    def test_shioaji_numeric_timestamp_adapter_uses_provider_local_wall_clock_decoder(self):
        raw = SimpleNamespace(ts=[1791882060000000000], Open=[100], High=[101], Low=[99], Close=[100], Volume=[5])
        api = SimpleNamespace(Contracts=SimpleNamespace(Stocks={"2330": "contract"}), kbars=lambda *args, **kwargs: raw)
        values = fetch_shioaji_1m_rows(api, symbol="2330", trading_session=DAY)
        self.assertEqual(values[0]["bar_timestamp"], "2026-10-13T09:01:00+08:00")
        self.assertEqual(values[0]["source_timestamp"], "1791882060000000000")

    def test_adapter_rejects_non_minute_numeric_timestamp(self):
        raw = SimpleNamespace(ts=[1791882060000000001], Open=[100], High=[101], Low=[99], Close=[100], Volume=[5])
        api = SimpleNamespace(Contracts=SimpleNamespace(Stocks={"2330": "contract"}), kbars=lambda *args, **kwargs: raw)
        with self.assertRaisesRegex(ValueError, "SHIOAJI_KBARS_TIMESTAMP_PRECISION"):
            fetch_shioaji_1m_rows(api, symbol="2330", trading_session=DAY)


class ContractTests(unittest.TestCase):
    def test_v2_contract_is_offline_not_activated(self):
        value = json.loads((ROOT / "config/governance/tw_intraday_1m_contract_v2.json").read_text())
        self.assertFalse(value["production_ingestion_enabled"])
        self.assertFalse(value["production_evaluation_enabled"])
        self.assertEqual(value["bar_timestamp_convention"], "BAR_END_TIMESTAMP_HALF_OPEN_1M")
        self.assertIn("SPARSE_UNVERIFIED", value["completeness"])


if __name__ == "__main__":
    unittest.main()
