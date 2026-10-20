from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.dashboard import multi_market_dashboard as dashboard
from app.dashboard.window_snapshot_archive import SnapshotSelection
from app.reports.post_close_quality_gate import tw_post_close_archive_quality_projection

SNAPSHOT_ID = "c5bbe2f3d57a701bbe95a1be118a8f27374e0e0eb14d2a8239579d943927dc88"
SYMBOLS = ["2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293"]
NAMES = {"2330": "台積電", "009816": "凱基台灣TOP50", "2337": "旺宏", "2353": "宏碁", "6873": "泓德能源", "4743": "合一", "2305": "全友", "00878": "國泰永續高股息", "1409": "新纖", "3293": "鈊象"}


def card(symbol: str, *, direction_hit: bool | None, range_result: str) -> dict:
    no_forecast = symbol == "2305"
    opening = 100.0
    closing = 101.0 if direction_hit is not False else 99.0
    return {
        "symbol": symbol, "name": NAMES[symbol], "trading_date": "2026-10-20",
        "prediction_source_window": "pre_open_0700", "source_snapshot_id": "a" * 64,
        "prediction_snapshot_id": "a" * 64, "prediction_payload_hash": "b" * 64,
        "prediction_status": "no_trade" if no_forecast else "active",
        "plan_status": "no_trade" if no_forecast else "active",
        "predicted_direction": None if no_forecast else "bullish",
        "predicted_low": None if no_forecast else 99.5,
        "predicted_high": None if no_forecast else 101.5,
        "direction_hit": direction_hit,
        "prediction_range_result": range_result,
        "prediction_interval_integrity": {"status": "NOT_APPLICABLE" if no_forecast else "VALID"},
        "actual_status": "complete", "actual_open": opening, "actual_low": 98.0,
        "actual_high": 102.0, "actual_close": closing, "source_name": "official_ohlc_fixture",
        "intraday_observed_path_evidence_v1": {"evidence_status": "OBSERVED_ONLY", "completeness": "SPARSE_UNVERIFIED", "observed_low": 98.5, "observed_high": 101.5},
    }


def snapshot(*, snapshot_id: str = SNAPSHOT_ID, revision: int = 1) -> dict:
    direction_hits = {"2330", "009816", "2337", "2353", "4743", "3293"}
    cards = [card(symbol, direction_hit=None if symbol == "2305" else symbol in direction_hits,
                  range_result="not_applicable" if symbol == "2305" else "hit" if symbol == "2353" else "partial_hit") for symbol in SYMBOLS]
    return {
        "schema_version": "window_snapshot_archive_v1", "market": "TW", "window": "post_close_1500",
        "effective_trading_date": "2026-10-20", "generated_at": "2026-10-20T15:00:00+08:00",
        "revision_created_at": "2026-10-20T15:00:00+08:00", "revision": revision,
        "snapshot_id": snapshot_id, "runtime_provenance": "scheduled", "admission_reason": "scheduled_admitted", "admitted": True,
        "payload": {"market": "TW", "window": "post_close_1500", "effective_trading_date": "2026-10-20",
                    "notification_universe": SYMBOLS, "structured_review_cards": cards},
    }


class TwPostCloseArchiveRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = snapshot()
        self.selection = SnapshotSelection("TW", "post_close_1500", self.snapshot, None)

    def _resolver(self, *, latest=None):
        return patch.object(dashboard, "resolve_snapshots", return_value=SnapshotSelection("TW", "post_close_1500", latest or self.snapshot, None))

    def _expected_identity(self) -> dict:
        contract = dashboard.snapshot_parity_contract(self.snapshot)
        assert contract is not None
        return {
            "market": "TW", "window": "post_close_1500", "effective_trading_date": "2026-10-20",
            "snapshot_id": SNAPSHOT_ID, "revision": 1, "payload_hash": contract["payload_hash"],
        }

    def test_fixed_20261020_snapshot_renders_full_archive_from_canonical_quality_projection(self):
        with self._resolver(), patch.object(dashboard, "revisions_for_snapshot", return_value=[self.snapshot]):
            html = dashboard.render_snapshot_archive_page("TW", "post_close_1500", "latest", self.snapshot, {"available": False, "empty_state": "fixture"})
        self.assertIn("<!doctype html>", html)
        self.assertIn("回到總覽", html)
        self.assertIn(SNAPSHOT_ID, html)
        self.assertEqual(html.count('class="mobile-decision-card"'), 10)
        self.assertIn("方向符合：6/9", html)
        self.assertIn("區間完全符合：1/9｜部分符合：8", html)
        self.assertIn("2305 全友", html)
        self.assertIn("不適用（未提供正式方向預測）", html)
        self.assertIn("偏多（正式資料）", html)
        self.assertNotIn("分時觀測", html)
        self.assertIn("data-ai-dev-255-evidence", html)
        self.assertIn("@media(max-width:640px)", html)

    def test_quality_projection_is_snapshot_bound_and_fail_closed(self):
        projection = tw_post_close_archive_quality_projection(self.snapshot)
        self.assertEqual(projection["snapshot_id"], SNAPSHOT_ID)
        self.assertEqual(len(projection["cards"]), 10)
        bad = deepcopy(self.snapshot)
        bad["payload"]["notification_universe"] = SYMBOLS[:-1]
        with self.assertRaisesRegex(ValueError, "FROZEN_UNIVERSE"):
            tw_post_close_archive_quality_projection(bad)

    def test_publisher_rejects_newer_latest_before_writing_target(self):
        newer = snapshot(snapshot_id="d" * 64, revision=2)
        expected = self._expected_identity()
        with TemporaryDirectory() as raw, patch.object(dashboard, "resolve_snapshots", return_value=SnapshotSelection("TW", "post_close_1500", newer, self.snapshot)):
            target = Path(raw) / "public/dashboard/archive/tw/post_close_1500/latest/index.html"
            target.parent.mkdir(parents=True); target.write_text("newer-report", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ARCHIVE_LATEST_IDENTITY_MISMATCH"):
                dashboard.publish_archive_latest_route("TW", "post_close_1500", static_root=Path(raw) / "public", output_dir=Path(raw) / "output", expected_identity=expected)
            self.assertEqual(target.read_text(encoding="utf-8"), "newer-report")

    def test_publish_is_idempotent_and_atomic_failure_keeps_prior_public_html(self):
        expected = self._expected_identity()
        with TemporaryDirectory() as raw, self._resolver(), patch.object(dashboard, "revisions_for_snapshot", return_value=[self.snapshot]):
            root = Path(raw); public = root / "public"; output = root / "output"
            first = dashboard.publish_archive_latest_route("TW", "post_close_1500", static_root=public, output_dir=output, expected_identity=expected)
            target = Path(first["target"]); stable = target.read_bytes()
            second = dashboard.publish_archive_latest_route("TW", "post_close_1500", static_root=public, output_dir=output, expected_identity=expected)
            self.assertEqual(stable, Path(second["target"]).read_bytes())
            with patch.object(dashboard.os, "replace", side_effect=OSError("fixture atomic failure")):
                with self.assertRaises(OSError):
                    dashboard.publish_archive_latest_route("TW", "post_close_1500", static_root=public, output_dir=output, expected_identity=expected)
            self.assertEqual(stable, target.read_bytes())

    def test_missing_formal_evidence_fails_closed_before_publish(self):
        broken = deepcopy(self.snapshot)
        broken["payload"]["structured_review_cards"][0].pop("actual_close")
        with TemporaryDirectory() as raw, patch.object(dashboard, "resolve_snapshots", return_value=SnapshotSelection("TW", "post_close_1500", broken, None)):
            with self.assertRaisesRegex(ValueError, "QUALITY_GATE_BLOCKED"):
                dashboard.publish_archive_latest_route("TW", "post_close_1500", static_root=Path(raw) / "public", output_dir=Path(raw) / "output")


if __name__ == "__main__":
    unittest.main()
