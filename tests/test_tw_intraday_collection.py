from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.dashboard.window_snapshot_archive import snapshot_id
from app.evaluation.session_calendar import load_calendar
from app.history.tw_intraday_1m import build_artifact, expected_minutes
from app.history.tw_intraday_collection import (
    archive_collection_manifest, build_collection_manifest, collect_session,
    replay_collection_manifest, select_natural_0700_snapshot, validate_collection_manifest,
)
from app.history.tw_intraday_session_universe import bind_0700_universe

DAY = "2026-10-13"
CALENDAR = load_calendar("TW")
SOURCE = {"name": "fixture", "revision": "v1", "source_digest": "a" * 64}


def snapshot(symbols: list[str]) -> dict:
    value = {
        "schema_version": "window_snapshot_archive_v1", "market": "TW", "window": "pre_open_0700",
        "effective_trading_date": DAY, "generated_at": DAY + "T07:00:00+08:00", "revision": 1,
        "run_kind": "scheduled", "status": "complete", "admitted": True,
        "runtime_provenance": "scheduled_production", "payload": {"tracking_symbols": symbols},
    }
    value["snapshot_id"] = snapshot_id(value)
    return value


def artifact(symbol: str) -> dict:
    timestamp = expected_minutes(CALENDAR, DAY)[0]
    return build_artifact(
        [{"symbol": symbol, "bar_timestamp": timestamp, "source_timestamp": timestamp,
          "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}],
        symbol=symbol, trading_session=DAY, calendar=CALENDAR, source=SOURCE,
        available_at=DAY + "T13:31:00+08:00",
    )


class CollectionManifestTests(unittest.TestCase):
    def test_archives_every_success_and_replays_exact_frozen_universe(self):
        source = snapshot(["2330", "009816", "00878"])
        universe = bind_0700_universe(source, trading_session=DAY)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = build_collection_manifest(
                universe, trading_session=DAY, fetch_rows=lambda symbol, _: [{"symbol": symbol}],
                build_canonical_artifact=lambda _, symbol, __: artifact(symbol), archive_root=root, calendar=CALENDAR,
            )
            path = archive_collection_manifest(manifest, root=root)
            self.assertEqual(manifest["terminal_result_coverage"], 1.0)
            self.assertEqual(manifest["artifact_success_count"], 3)
            self.assertEqual([item["symbol"] for item in manifest["records"]], ["2330", "009816", "00878"])
            self.assertTrue(path.is_file())
            self.assertEqual(path, archive_collection_manifest(manifest, root=root))
            with patch("app.history.tw_intraday_collection.select_natural_0700_snapshot", return_value=source):
                replayed = replay_collection_manifest(root=root, snapshot_root=root / "snapshots", trading_session=DAY,
                                                      content_hash=manifest["content_hash"], calendar=CALENDAR)
            self.assertEqual(replayed, manifest)

    def test_one_provider_or_archive_failure_preserves_other_terminal_records(self):
        source = snapshot(["2330", "009816", "00878"])
        universe = bind_0700_universe(source, trading_session=DAY)
        def fetch(symbol, _):
            if symbol == "009816":
                raise RuntimeError("provider")
            return [{"symbol": symbol}]
        with TemporaryDirectory() as tmp:
            manifest = build_collection_manifest(
                universe, trading_session=DAY, fetch_rows=fetch,
                build_canonical_artifact=lambda _, symbol, __: artifact(symbol), archive_root=tmp, calendar=CALENDAR,
            )
            self.assertEqual(manifest["artifact_success_count"], 2)
            self.assertEqual(manifest["failed_symbols"], ["009816"])
            self.assertEqual(manifest["collection_status"], "PARTIAL")
            self.assertEqual(manifest["terminal_result_coverage"], 1.0)
            failure = manifest["records"][1]
            self.assertEqual((failure["stage"], failure["reason_code"]), ("KBARS_FETCH", "KBARS_FAILURE"))
            self.assertTrue((Path(tmp) / manifest["records"][0]["archive_path"]).is_file())

    def test_manifest_tamper_and_universe_digest_mismatch_fail_closed(self):
        source = snapshot(["2330"])
        universe = bind_0700_universe(source, trading_session=DAY)
        manifest = build_collection_manifest(
            universe, trading_session=DAY, fetch_rows=lambda *_: [{}],
            build_canonical_artifact=lambda _, symbol, __: artifact(symbol),
        )
        tampered = deepcopy(manifest); tampered["expected_symbols"] = ["2337"]
        with self.assertRaisesRegex(ValueError, "COVERAGE|DIGEST"):
            validate_collection_manifest(tampered)

    def test_missing_natural_snapshot_fails_without_substitution(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "NATURAL_SNAPSHOT_UNAVAILABLE"):
                select_natural_0700_snapshot(tmp, trading_session=DAY)

    def test_collect_session_provider_unavailable_records_every_frozen_symbol(self):
        source = snapshot(["2330", "009816"])
        with TemporaryDirectory() as tmp, patch("app.history.tw_intraday_collection.select_natural_0700_snapshot", return_value=source):
            manifest, _ = collect_session(trading_session=DAY, snapshot_root=tmp, archive_root=tmp, api=None,
                                           available_at=DAY + "T15:00:00+08:00", calendar=CALENDAR)
        self.assertEqual(manifest["artifact_success_count"], 0)
        self.assertEqual(manifest["failed_symbols"], ["2330", "009816"])
        self.assertEqual(manifest["terminal_result_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()
