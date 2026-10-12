"""AI-DEV-256B legacy frozen-evidence replay compatibility, fixture-only."""
from __future__ import annotations

from copy import deepcopy
import unittest

from app.evaluation.prediction_regression_contract import stamp
from app.evaluation.production_evidence import (
    LEGACY_LEARNING_USED_CUTOFF,
    freeze,
    outcome,
    validate_frozen,
    assess,
)
from app.evaluation.session_calendar import load_calendar


def current(*, market="TW", day="2026-09-24", symbol="TEST"):
    calendar = load_calendar(market)
    frozen_at = "2026-09-24T07:00:00+08:00" if market == "TW" else "2026-09-24T08:00:00-04:00"
    available = "2026-09-24T06:00:00+08:00" if market == "TW" else "2026-09-24T07:00:00-04:00"
    source = "fixture-tw" if market == "TW" else "fixture-us"
    reference = {"identity":"reference","value":100.0,"source":source,"source_revision":"v1","source_digest":"a"*64,"as_of":available,"available_at":available,"producer":"fixture"}
    atr = {"identity":"atr14","value":2.0,"source":source,"source_revision":"v1","source_digest":"b"*64,"as_of":available,"available_at":available,"producer":"WILDER_14_COMPLETED_POINT_IN_TIME"}
    reference, atr = stamp(reference), stamp(atr)
    return freeze(prediction_id=f"{market}-{day}-{symbol}", symbol=symbol, direction="UP", frozen_at=frozen_at,
                  reference=reference, atr=atr, calendar=calendar, review_session=day,
                  producer="fixture", market=market, stream="pre_open_0700" if market == "TW" else "us_pre_market_2000")


def legacy(*, market="TW", day="2026-09-24", symbol="TEST"):
    value = current(market=market, day=day, symbol=symbol)
    value.pop("learning_used")
    return stamp(value)


class LegacyFrozenReplayTests(unittest.TestCase):
    def test_tw_legacy_missing_learning_used_replays_without_mutation(self):
        value = legacy(market="TW")
        before = deepcopy(value)
        self.assertEqual(validate_frozen(value), value)
        self.assertEqual(value, before)

    def test_us_legacy_missing_learning_used_replays_without_mutation(self):
        value = legacy(market="US")
        before = deepcopy(value)
        self.assertEqual(validate_frozen(value), value)
        self.assertEqual(value, before)

    def test_explicit_historical_null_representation_replays(self):
        value = current(market="TW")
        self.assertIsNone(value["learning_used"])
        self.assertEqual(validate_frozen(value), value)

    def test_current_missing_learning_used_fails_closed(self):
        value = current(market="TW")
        value["prediction_frozen_at"] = LEGACY_LEARNING_USED_CUTOFF
        value.pop("learning_used")
        value = stamp(value)
        with self.assertRaisesRegex(ValueError, "FROZEN_LEARNING_USED_MISSING"):
            validate_frozen(value)

    def test_modified_prediction_fails(self):
        value = legacy(market="TW")
        changed = deepcopy(value); changed["direction"] = "DOWN"
        with self.assertRaisesRegex(ValueError, "EVIDENCE_DIGEST"):
            validate_frozen(changed)

    def test_wrong_hash_fails(self):
        value = legacy(market="TW")
        bad_hash = deepcopy(value); bad_hash["content_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "EVIDENCE_DIGEST"):
            validate_frozen(bad_hash)

    def test_wrong_market_fails(self):
        value = legacy(market="TW")
        market = deepcopy(value); market["market"] = "US"; market = stamp(market)
        with self.assertRaises(ValueError):
            validate_frozen(market)

    def test_wrong_date_fails(self):
        value = legacy(market="TW")
        date = deepcopy(value); date["event"]["horizon"]["session_date"] = "2026-09-25"; date = stamp(date)
        with self.assertRaises(ValueError):
            validate_frozen(date)

    def test_modified_outcome_is_not_admitted(self):
        value = legacy(market="TW")
        realized = outcome(value, close=102.0, source="fixture", revision="v1", source_digest="c"*64,
                           available_at=value["event"]["horizon"]["close_at"], session_date="2026-09-24")
        changed = deepcopy(realized); changed["close"] = 103.0
        result = assess(value, changed, observed_at="2026-09-25T17:00:00+08:00")
        self.assertEqual(result["state"], "BLOCKED_INPUT")

    def test_modified_legacy_evidence_fails(self):
        value = legacy(market="US")
        value["features"]["reference"]["value"] = 101.0
        with self.assertRaisesRegex(ValueError, "EVIDENCE_DIGEST"):
            validate_frozen(value)


if __name__ == "__main__":
    unittest.main()
