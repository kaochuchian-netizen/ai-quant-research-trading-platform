from __future__ import annotations

import unittest

import pandas as pd

from app.evaluation.session_calendar import load_calendar
from app.market.tw_history_admission import expected_completed_session, validate_history_candidate
from app.reports.mobile_decision_presentation import project_payload, render_line
from app.reports.tw_pre_open_structured import unavailable_card


SYMBOLS = ("2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293")


def history(end: str, rows: int = 30) -> pd.DataFrame:
    dates = pd.bdate_range(end=end, periods=rows)
    return pd.DataFrame({
        "date": dates,
        "open": [100.0 + i for i in range(rows)],
        "high": [101.0 + i for i in range(rows)],
        "low": [99.0 + i for i in range(rows)],
        "close": [100.5 + i for i in range(rows)],
        "volume": [1000] * rows,
    })


class TwNonTradingDayAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = load_calendar("TW")

    def test_authoritative_session_resolution(self):
        self.assertEqual(expected_completed_session("2026-10-13", calendar=self.calendar).isoformat(), "2026-10-12")
        self.assertEqual(expected_completed_session("2026-10-12", calendar=self.calendar).isoformat(), "2026-10-08")
        self.assertEqual(expected_completed_session("2026-10-11", calendar=self.calendar).isoformat(), "2026-10-08")
        self.assertEqual(expected_completed_session("2026-01-05", calendar=self.calendar).isoformat(), "2026-01-02")

    def test_incident_replay_all_watchlist_admitted(self):
        results = [validate_history_candidate(history("2026-10-08"), source="fixture", target_date="2026-10-12", calendar=self.calendar) for _ in SYMBOLS]
        self.assertTrue(all(row["admission_success"] for row in results))
        self.assertTrue(all(row["expected_latest_session"] == "2026-10-08" for row in results))

    def test_fail_closed_for_stale_future_and_wrong_calendar(self):
        stale = validate_history_candidate(history("2026-10-07"), source="fixture", target_date="2026-10-12", calendar=self.calendar)
        future = validate_history_candidate(history("2026-10-13"), source="fixture", target_date="2026-10-12", calendar=self.calendar)
        wrong = dict(self.calendar); wrong["market"] = "US"
        invalid = validate_history_candidate(history("2026-10-08"), source="fixture", target_date="2026-10-12", calendar=wrong)
        self.assertEqual(stale["status"], "STALE")
        self.assertEqual(future["status"], "FUTURE_DATA")
        self.assertEqual(invalid["status"], "SOURCE_FAILED")


class UnavailablePresentationTests(unittest.TestCase):
    def test_unavailable_prediction_is_not_sideways_in_line_or_card(self):
        cards = [unavailable_card(symbol, "測試", "2026-10-12", "historical_data_admission:STALE") for symbol in SYMBOLS]
        payload = {"window": "pre_open_0700", "structured_pre_open_cards": cards, "tracking_symbols": list(SYMBOLS)}
        projection = project_payload(payload, "TW", "pre_open_0700")
        self.assertTrue(all({field["label"]: field["value"] for field in row["fields"]}["走勢預測"] == "資料不足，暫不判斷" for row in projection["cards"]))
        text = render_line(payload, "TW", "pre_open_0700", "https://example.invalid")
        self.assertNotIn("走勢預測：盤整", text)
        self.assertEqual(sum(symbol in text for symbol in SYMBOLS), len(SYMBOLS))


if __name__ == "__main__":
    unittest.main()
