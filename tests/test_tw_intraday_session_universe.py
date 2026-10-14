from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from app.dashboard.window_snapshot_archive import snapshot_id
from app.history.tw_intraday_1m import SCHEMA_VERSION as INTRADAY_SCHEMA_VERSION
from app.history.tw_intraday_session_universe import (
    bind_0700_universe, build_1500_collection_plan, normalize_tw_symbol,
    validate_bound_universe, verify_universe_source,
)

DAY = "2026-10-13"
CURRENT = ["2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293"]


def source_snapshot(symbols: list[str], *, session: str = DAY):
    value = {
        "schema_version": "window_snapshot_archive_v1", "market": "TW", "window": "pre_open_0700",
        "effective_trading_date": session, "generated_at": session + "T07:00:00+08:00", "revision": 1,
        "run_kind": "scheduled", "status": "complete", "admitted": True,
        "runtime_provenance": "scheduled_production", "payload": {"tracking_symbols": list(symbols)},
    }
    value["snapshot_id"] = snapshot_id(value)
    return value


def artifact(symbol: str, day: str):
    seed = f"{symbol}:{day}".encode()
    return {"schema_version": INTRADAY_SCHEMA_VERSION, "symbol": symbol, "trading_session": day,
            "content_hash": sha256(seed).hexdigest(), "completeness": "SPARSE_UNVERIFIED"}


class UniverseBindingTests(unittest.TestCase):
    def test_dynamic_eight_current_ten_and_fifteen_symbol_universes(self):
        for count in (8, 10, 15):
            symbols = [f"{index:04d}" for index in range(1, count + 1)]
            value = bind_0700_universe(source_snapshot(symbols), trading_session=DAY)
            self.assertEqual(value["symbol_count"], count)
            self.assertEqual(value["symbols"], symbols)

    def test_current_ten_symbol_universe_preserves_leading_zero_etfs(self):
        value = bind_0700_universe(source_snapshot(CURRENT), trading_session=DAY)
        self.assertEqual(value["symbols"], CURRENT)
        self.assertIn("009816", value["symbols"])
        self.assertIn("00878", value["symbols"])
        self.assertEqual(normalize_tw_symbol("009816"), "009816")

    def test_digest_is_deterministic_and_source_bound(self):
        snapshot = source_snapshot(CURRENT)
        one = bind_0700_universe(snapshot, trading_session=DAY)
        two = bind_0700_universe(deepcopy(snapshot), trading_session=DAY)
        self.assertEqual(one, two)
        altered = source_snapshot(list(reversed(CURRENT)))
        self.assertNotEqual(one["universe_digest"], bind_0700_universe(altered, trading_session=DAY)["universe_digest"])

    def test_wrong_session_missing_artifact_duplicates_and_mismatch_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "MISSING_OR_UNADMITTED"):
            bind_0700_universe({}, trading_session=DAY)
        with self.assertRaisesRegex(ValueError, "SESSION_MISMATCH"):
            bind_0700_universe(source_snapshot(CURRENT, session="2026-10-09"), trading_session=DAY)
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            bind_0700_universe(source_snapshot(["2330", "2330"]), trading_session=DAY)
        bound = bind_0700_universe(source_snapshot(CURRENT), trading_session=DAY)
        changed = deepcopy(bound); changed["symbols"] = list(reversed(changed["symbols"]))
        with self.assertRaisesRegex(ValueError, "DIGEST_MISMATCH"):
            validate_bound_universe(changed, trading_session=DAY)
        with self.assertRaisesRegex(ValueError, "SOURCE_MISMATCH"):
            verify_universe_source(bound, source_snapshot(list(reversed(CURRENT))))


class CollectionPlanTests(unittest.TestCase):
    def test_no_fixed_count_assumption_and_every_symbol_has_terminal_result(self):
        symbols = [f"{index:04d}" for index in range(1, 16)]
        universe = bind_0700_universe(source_snapshot(symbols), trading_session=DAY)
        plan = build_1500_collection_plan(universe, trading_session=DAY,
            fetch_rows=lambda symbol, day: [{"symbol": symbol}],
            build_canonical_artifact=lambda rows, symbol, day: artifact(symbol, day))
        self.assertEqual(plan["expected_symbol_count"], 15)
        self.assertEqual(plan["kbars_success_count"], 15)
        self.assertEqual(plan["artifact_success_count"], 15)
        self.assertEqual(plan["terminal_result_coverage"], 1.0)
        self.assertEqual([row["symbol"] for row in plan["records"]], symbols)

    def test_one_provider_failure_is_explicit_not_omitted(self):
        universe = bind_0700_universe(source_snapshot(["2330", "009816", "00878"]), trading_session=DAY)
        def fetch(symbol, day):
            if symbol == "009816":
                raise RuntimeError("provider unavailable")
            return [{"symbol": symbol}]
        plan = build_1500_collection_plan(universe, trading_session=DAY, fetch_rows=fetch,
            build_canonical_artifact=lambda rows, symbol, day: artifact(symbol, day))
        self.assertEqual(plan["failed_symbols"], ["009816"])
        self.assertEqual(plan["artifact_success_count"], 2)
        self.assertEqual(plan["symbol_coverage"], 2 / 3)
        self.assertEqual(plan["terminal_result_coverage"], 1.0)
        failure = next(row for row in plan["records"] if row["symbol"] == "009816")
        self.assertEqual((failure["stage"], failure["reason_code"]), ("KBARS_FETCH", "KBARS_FAILURE"))

    def test_canonical_failure_is_explicit_and_wrong_session_rejected(self):
        universe = bind_0700_universe(source_snapshot(["2330"]), trading_session=DAY)
        plan = build_1500_collection_plan(universe, trading_session=DAY, fetch_rows=lambda *_: [{}],
            build_canonical_artifact=lambda *_: (_ for _ in ()).throw(ValueError("bad artifact")))
        self.assertEqual(plan["failed_symbols"], ["2330"])
        self.assertEqual(plan["records"][0]["reason_code"], "CANONICAL_ARTIFACT_FAILURE")
        with self.assertRaisesRegex(ValueError, "SESSION_MISMATCH"):
            build_1500_collection_plan(universe, trading_session="2026-10-14", fetch_rows=lambda *_: [], build_canonical_artifact=lambda *_: {})


if __name__ == "__main__":
    unittest.main()
