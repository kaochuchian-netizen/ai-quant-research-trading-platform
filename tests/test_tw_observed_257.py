import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.reports.line_chunks import split_line_text, text_units, deliver_line_chunks, LineChunkFailure
from app.reports.tw_line_completeness import notification_universe_evidence, complete_line_universe, build_symbol_delivery_accounting
from app.reports.observed_timestamp import observed_time
from app.market.snapshot_normalizer import normalize_snapshot
from app.market.historical_price_loader import get_historical_prices
from app.market.tw_symbol_historical_admission import admit_tw_symbols_with_history
from app.reports.tw_four_window_decision import build_observed_card
from app.history.tw_observed_contract import canonical_bars, classify_observed_path

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = "2026-10-01T13:35:00+08:00"


class LineTests(unittest.TestCase):
    def test_incident_length_retained(self):
        text = "2330 台積電\n" + "測試" * 280 + "\n3293"
        self.assertGreater(len(text), 520)
        self.assertEqual(split_line_text(text), [text])

    def test_exact_limit(self):
        self.assertEqual(len(split_line_text("字" * 5000)), 1)

    def test_multi_chunk_lossless(self):
        text = "中文\n😀" * 4500
        chunks = split_line_text(text)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(text_units(c) <= 5000 for c in chunks))

    def test_surrogate_boundary(self):
        chunks = split_line_text("a" * 4999 + "😀終")
        self.assertEqual(chunks, ["a" * 4999, "😀終"])

    def test_reject_empty(self):
        with self.assertRaises(ValueError): split_line_text("")

    def test_sender_all_chunks(self):
        received = []
        receipt = deliver_line_chunks("字" * 11000, received.append)
        self.assertEqual("".join(received), "字" * 11000)
        self.assertEqual(receipt["completed_chunk_count"], 3)

    def test_partial_delivery_not_success(self):
        sent = []
        def sender(chunk):
            if sent: raise RuntimeError("transport failure")
            sent.append(chunk)
        with self.assertRaises(LineChunkFailure) as ctx:
            deliver_line_chunks("字" * 6000, sender)
        self.assertEqual(ctx.exception.chunk_delivery["completed_chunk_count"], 1)
        self.assertTrue(ctx.exception.chunk_delivery["partial_delivery_possible"])

    def test_all_watchlist_exclusions_explicit(self):
        payload = notification_universe_evidence({"historical_symbol_admission": [
            {"symbol": "2330", "status": "ADMITTED"},
            {"symbol": "009816", "status": "HISTORICAL_INSUFFICIENT", "exclusion_reason": "STALE"},
            {"symbol": "00878", "status": "HISTORICAL_INSUFFICIENT", "exclusion_reason": "STALE"}]})
        text = complete_line_universe("2330 正式卡片", payload, ["2330"])
        self.assertTrue(all(s in text for s in payload["notification_universe"]))
        self.assertIn("歷史資料未更新", text)
        self.assertNotIn("STALE", text)

    def test_unexplained_omission_rejected(self):
        with self.assertRaises(ValueError):
            complete_line_universe("2330", {"tracking_symbols": ["2330", "00878"]}, ["2330"])

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError): complete_line_universe("", {}, ["2330", "2330"])

    def test_accounting_real_chunk_count(self):
        r = build_symbol_delivery_accounting(expected_symbols=["2330"], rendered_symbols=["2330"], policy="test", channel="line", content="2330" + "字"*10000)
        self.assertEqual(r["chunk_count"], 3)
        self.assertTrue(r["complete"])

    def test_wrapper_full_content_and_mock_transport(self):
        from scripts.orchestrator import approved_pre_open_delivery as wrapper
        payload = {"tracking_symbols": ["2330"], "structured_pre_close_cards": [{"symbol": "2330", "name": "測試"*600}]}
        snapshot = {"payload": payload}
        before = copy.deepcopy(snapshot)
        full = wrapper.build_line_message("pre_close_1335", CAPTURE, "completed", "https://example.invalid", "", snapshot)
        self.assertGreater(len(full), 520)
        sent = []
        with patch.object(wrapper.importlib, "import_module", return_value=SimpleNamespace(send_line_report=sent.append)):
            result = wrapper.send_concise_line("pre_close_1335", CAPTURE, "completed", "https://example.invalid", "", snapshot)
        self.assertEqual("".join(sent), full)
        self.assertEqual(snapshot, before)
        self.assertEqual(result["send_status"], "sent")


class TimestampTests(unittest.TestCase):
    def check(self, raw, state, reason=None, **kwargs):
        result = observed_time(raw, captured_at=CAPTURE, session_date="2026-10-01", **kwargs)
        self.assertEqual(result["freshness_status"], state)
        if reason: self.assertEqual(result["reason"], reason)
        return result

    def test_incident_future_no_offset_guess(self):
        r = self.check(1790861400000000000, "invalid", "FUTURE_TIMESTAMP")
        self.assertEqual(r["normalized_timestamp"], "2026-10-01T21:30:00+08:00")

    def test_naive_exchange_time(self): self.check("2026-10-01T13:30:00", "fresh")
    def test_aware_utc(self): self.check("2026-10-01T05:30:00+00:00", "fresh")
    def test_prior_session_stale(self): self.check("2026-09-30T13:30:00+08:00", "stale")
    def test_missing(self): self.check(None, "unavailable")
    def test_malformed(self): self.check("bad", "invalid")
    def test_unknown_precision(self): self.check(123, "invalid")
    def test_boolean(self): self.check(True, "invalid")
    def test_naive_undeclared_zone(self): self.check("2026-10-01T13:30:00", "invalid", source_timezone="UNKNOWN")
    def test_naive_capture(self):
        self.assertEqual(observed_time("2026-10-01",captured_at="2026-10-01T13:35:00",session_date="2026-10-01")["freshness_status"], "invalid")
    def test_all_epoch_units(self):
        seconds = int(datetime(2026,10,1,5,30,tzinfo=timezone.utc).timestamp())
        for multiplier in (1,1000,1000000,1000000000): self.check(seconds*multiplier,"fresh")
    def test_replay(self):
        self.assertEqual(self.check("2026-10-01T13:30:00", "fresh"), self.check("2026-10-01T13:30:00", "fresh"))
    def test_card_invalid_not_fresh(self):
        c = build_observed_card(window="pre_close_1335", setup_card={"symbol":"2330"}, quote={"close":100,"open":99,"high":101,"low":98,"snapshot_time":1790861400000000000}, trading_date="2026-10-01",generated_at=CAPTURE,source_snapshot_id=None,source_revision=1,source_payload_hash=None)
        self.assertEqual(c["freshness_status"], "invalid")
        self.assertIsNone(c["market_data_as_of"])
        self.assertIn("market_data_as_of",c["missing_fields"])
    def test_normalizer_raw_preserved(self):
        values = dict(ts=1790861400000000000,code="2330",open=99,high=101,low=98,close=100,volume=1,total_volume=10,change_price=1,change_rate=1,buy_price=99,buy_volume=1,sell_price=100,sell_volume=1)
        r=normalize_snapshot(SimpleNamespace(**values),captured_at=CAPTURE)
        self.assertEqual(r["snapshot_time"],str(values["ts"]))
        self.assertEqual(r["observed_timestamp_evidence"]["reason"],"FUTURE_TIMESTAMP")


class HistoryTests(unittest.TestCase):
    def api(self, conflict=False):
        calls=[]
        def kbars(contract,start,end):
            first,last=datetime.fromisoformat(start),datetime.fromisoformat(end)
            self.assertLessEqual((last-first).days+1,30)
            dates=[first+timedelta(days=i) for i in range((last-first).days+1)]
            calls.append((start,end))
            value=101 if conflict and len(calls)>1 else 100
            return SimpleNamespace(ts=dates,Open=[value]*len(dates),High=[value]*len(dates),Low=[value]*len(dates),Close=[value]*len(dates),Volume=[1]*len(dates))
        return SimpleNamespace(Contracts=SimpleNamespace(Stocks={"00878":"contract"}),kbars=kbars),calls
    def test_180_days_preserved_bounded_requests(self):
        api,calls=self.api(); d=get_historical_prices(api,"00878","2026-04-01","2026-10-01")
        self.assertEqual(len(d),180)
        self.assertEqual(len(calls),7)
        self.assertTrue(d.ts.is_monotonic_increasing)
        self.assertFalse(d.ts.duplicated().any())
    def test_one_day(self):
        api,calls=self.api();self.assertEqual(len(get_historical_prices(api,"00878","2026-09-30","2026-09-30")),1)
        self.assertEqual(len(calls),1)
    def test_conflicting_duplicate_fail_closed(self):
        api,_=self.api(True)
        with self.assertRaises(ValueError):get_historical_prices(api,"00878","2026-04-01","2026-10-01")
    def test_provider_failure_propagates(self):
        api,_=self.api();api.kbars=lambda *a,**k: (_ for _ in ()).throw(RuntimeError("provider"))
        with self.assertRaises(RuntimeError):get_historical_prices(api,"00878","2026-09-01","2026-10-01")
    def test_stale_never_admitted(self):
        admitted,rows=admit_tw_symbols_with_history(["00878","009816"],target_date="2026-10-01",inspector=lambda *a,**k:{"exists":True,"usable":False,"warning":"STALE","latest_date":"2026-09-29","row_count":122},bootstrapper=lambda *a,**k:self.fail("must not overwrite"))
        self.assertEqual(admitted,[])
        self.assertTrue(all(r["exclusion_reason"]=="STALE" for r in rows))


class MinuteContractTests(unittest.TestCase):
    def setUp(self):
        self.times=[f"2026-10-01T09:0{i}:00+08:00" for i in range(3)]
        self.rows=[dict(timestamp=t,open=100,high=102,low=98,close=101,volume=1) for t in self.times]
    def evidence(self, rows=None):
        return canonical_bars(self.rows if rows is None else rows,expected_timestamps=self.times,as_of=CAPTURE)
    def test_sort_dedup_replay(self):
        self.assertEqual(self.evidence(),self.evidence(list(reversed(self.rows))+[self.rows[0]]))
    def test_conflict(self):
        with self.assertRaises(ValueError):self.evidence(self.rows+[{**self.rows[0],"close":100}])
    def test_missing_no_fill(self):
        e=self.evidence(self.rows[:2]);self.assertEqual(e["status"],"DATA_MISSING");self.assertEqual(len(e["bars"]),2)
    def test_missing_not_sideways(self):
        e=self.evidence([]);self.assertIsNone(classify_observed_path(e,previous_close=100,flat_band=0,parameter_version="fixture")["trend"])
    def test_future_rejected(self):
        with self.assertRaises(ValueError): canonical_bars(self.rows,expected_timestamps=self.times,as_of="2026-10-01T09:01:00+08:00")
    def test_geometry(self):
        with self.assertRaises(ValueError):self.evidence([{**self.rows[0],"high":1}])
    def test_prediction_not_input(self):
        with self.assertRaises(ValueError):self.evidence([{**self.rows[0],"predicted_direction":"UP"}])
    def test_digest_tamper(self):
        e=self.evidence();e["bars"][0]["close"]=100
        with self.assertRaises(ValueError): classify_observed_path(e,previous_close=100,flat_band=0,parameter_version="fixture")
    def test_five_trend_rules(self):
        cases=[(100,102,103,0,"OPEN_LOW_RISE"),(100,98,97,0,"OPEN_HIGH_FALL"),(100,102,100,0,"BULLISH"),(100,98,100,0,"BEARISH"),(100,101,100,1,"SIDEWAYS")]
        for opening,close,previous,band,label in cases:
            rows=[{**r,"open":opening,"close":close,"high":max(opening,close),"low":min(opening,close)} for r in self.rows]
            result=classify_observed_path(self.evidence(rows),previous_close=previous,flat_band=band,parameter_version="fixture-only-v1")
            self.assertEqual(result["trend"],label);self.assertFalse(result["production_eligible"])
    def test_contract_no_activation(self):
        d=json.loads((ROOT/"config/governance/tw_observed_minute_contract_v1.json").read_text())
        self.assertFalse(d["production_ingestion_enabled"])
        self.assertFalse(d["production_actual_trend_enabled"])
        self.assertIsNone(d["actual_trend"]["production_parameter_default"])
        self.assertEqual(set(d["actual_trend"]["priority"]),set(d["actual_trend"]["rules"]))


if __name__ == "__main__": unittest.main()
