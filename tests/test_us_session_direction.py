"""Synthetic-only 253 integration and contract regressions."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from app.evaluation.us_session_direction import *
from app.evaluation.production_evidence import assess, outcome, evaluate_direction, unique_predictions, validate_frozen
from app.dashboard.production_evidence_archive import project, persist, publish, reevaluate
from test_production_evidence import source_snapshot
from app.dashboard.window_snapshot_archive import snapshot_id

def obs(day="2026-09-24",slope=1):
    cal=load_calendar("US")
    days=[r["session_date"] for r in cal["days"] if r["state"] in {"NORMAL","EARLY_CLOSE"} and r["session_date"]<day][-20:]
    rows=[{"date":d,"close":100+i*slope,"high":102+i*slope,"low":98+i*slope} for i,d in enumerate(days)]
    return stamp({"schema_version":VERSION,"kind":"US_MARKET_OBSERVATION","symbol":"TEST","review_session":day,
                  "source":"Yahoo Finance / yfinance","source_version":"fixture",
                  "reference_price":rows[-1]["close"],"reference_as_of":session(cal,"US",days[-1])["close_at"],
                  "available_at":day+"T08:00:00-04:00","rows":rows})

def prediction(day="2026-09-24",slope=1):
    o=obs(day,slope)
    return predict(o,load_calendar("US"),frozen_at=day+"T08:01:00-04:00")

def receipt(value):
    return stamp({"schema_version":VERSION,"kind":"US_NATIVE_RECEIPT","symbol":"TEST",
                  "review_session":value["source"]["review_session"],"capture":value})

def report(window=STREAM,kind="scheduled"):
    return source_snapshot(window,"US",kind)[0]

class NativeTests(unittest.TestCase):
    def test_up(self): self.assertEqual(prediction()["direction"],"UP")
    def test_down(self): self.assertEqual(prediction(slope=-1)["direction"],"DOWN")
    def test_neutral_abstains(self): self.assertEqual(prediction(slope=0)["status"],"NO_FORECAST")
    def test_no_fake_flat(self): self.assertIsNone(prediction(slope=0)["direction"])
    def test_determinism(self): self.assertEqual(prediction(),prediction())
    def test_replay(self):
        p=prediction();self.assertEqual(p,predict(p["source"],p["calendar"],frozen_at=p["frozen_at"]))
    def test_source_unchanged(self):
        o=obs();b=deepcopy(o);predict(o,load_calendar("US"),frozen_at="2026-09-24T08:01:00-04:00");self.assertEqual(o,b)
    def test_market(self): self.assertEqual(prediction()["frozen"]["market"],"US")
    def test_horizon(self): self.assertEqual(prediction()["frozen"]["event"]["horizon"]["session_date"],"2026-09-24")
    def test_event(self): self.assertEqual(prediction()["frozen"]["event"]["version"],"prediction_direction_event_v1")
    def test_no_confidence(self): self.assertIsNone(prediction()["frozen"]["event_confidence"])
    def test_wilder(self): self.assertEqual(prediction()["frozen"]["features"]["atr14"]["value"],4)
    def test_atr_producer(self): self.assertEqual(prediction()["frozen"]["features"]["atr14"]["producer"],"WILDER_14_COMPLETED_POINT_IN_TIME")
    def test_reference(self): self.assertEqual(prediction()["frozen"]["features"]["reference"]["value"],119)
    def test_ma_provenance(self): self.assertEqual(set(prediction()["frozen"]["prediction_features"]),{"ma5","ma10"})
    def test_frozen_replay(self): self.assertEqual(validate_frozen(prediction()["frozen"]),prediction()["frozen"])
    def test_digest(self):
        f=prediction()["frozen"];f["direction"]="DOWN"
        with self.assertRaises(ValueError):validate_frozen(f)
    def test_postopen(self):
        with self.assertRaises(ValueError):predict(obs(),load_calendar("US"),frozen_at="2026-09-24T09:30:00-04:00")
    def test_future_availability(self):
        o=obs();o["available_at"]="2026-09-24T09:00:00-04:00";o=stamp(o)
        with self.assertRaises(ValueError):predict(o,load_calendar("US"),frozen_at="2026-09-24T08:30:00-04:00")
    def test_future_reference(self):
        o=obs();o["reference_as_of"]="2026-09-24T09:00:00-04:00";o=stamp(o)
        with self.assertRaises(ValueError):predict(o,load_calendar("US"),frozen_at="2026-09-24T08:30:00-04:00")
    def test_future_bar(self):
        o=obs();o["rows"][-1]["date"]="2026-09-24";o=stamp(o)
        with self.assertRaises(ValueError):predict(o,load_calendar("US"),frozen_at="2026-09-24T08:30:00-04:00")
    def test_missing_reference(self):
        o=obs();del o["reference_price"];o=stamp(o)
        with self.assertRaises(KeyError):predict(o,load_calendar("US"),frozen_at="2026-09-24T08:30:00-04:00")
    def test_insufficient_abstention(self):
        o=obs();o["rows"]=o["rows"][-5:];o=stamp(o)
        self.assertEqual(predict(o,load_calendar("US"),frozen_at="2026-09-24T08:30:00-04:00")["status"],"NO_FORECAST")
    def test_calendar_digest(self):
        c=load_calendar("US");c["revision"]+=1
        with self.assertRaises(ValueError):predict(obs(),c,frozen_at="2026-09-24T08:30:00-04:00")
    def test_waiting(self):
        self.assertEqual(assess(prediction()["frozen"],None,observed_at="2026-09-24T09:00:00-04:00")["state"],"WAITING_OUTCOME")
    def test_mature(self):
        f=prediction()["frozen"];h=f["event"]["horizon"]
        o=outcome(f,close=125,source="fixture",revision="v1",source_digest="a"*64,available_at=h["close_at"],session_date=h["session_date"])
        self.assertTrue(assess(f,o,observed_at=h["close_at"])["direction_correct"])
    def test_realized_flat(self):
        f=prediction()["frozen"];h=f["event"]["horizon"]
        o=outcome(f,close=119,source="fixture",revision="v1",source_digest="a"*64,available_at=h["close_at"],session_date=h["session_date"])
        self.assertEqual(assess(f,o,observed_at=h["close_at"])["direction"],"FLAT")
    def test_10_sessions(self):
        c=load_calendar("US")
        days=[r["session_date"] for r in c["days"] if r["state"]=="NORMAL" and r["session_date"]<="2026-09-24"][-10:]
        ps=[prediction(d)["frozen"] for d in days]
        outs={p["sample_id"]:outcome(p,close=125,source="fixture",revision="v1",source_digest="b"*64,
              available_at=p["event"]["horizon"]["close_at"],session_date=p["event"]["horizon"]["session_date"]) for p in ps}
        r=evaluate_direction(ps,outs,calendar=c,review_session=days[-1],observed_at="2026-09-24T17:00:00-04:00")
        self.assertEqual(r["state"],"EVALUATED");self.assertEqual(r["admission_state"],"READY_FOR_EVALUATION");self.assertEqual(r["score"],100)
    def test_single_insufficient(self):
        f=prediction()["frozen"]
        r=evaluate_direction([f],{},calendar=f["calendar"],review_session="2026-09-24",observed_at="2026-09-24T17:00:00-04:00")
        self.assertEqual(r["state"],"INSUFFICIENT_SAMPLE")
    def test_dedup(self):self.assertEqual(len(unique_predictions([prediction()["frozen"]]*3)),1)
    def test_report_unchanged(self):
        s=report();b=deepcopy(s);project(s,{"TEST":receipt(prediction())});self.assertEqual(s,b)
    def test_native_admitted(self):
        r=project(report(),{"TEST":receipt(prediction())})["records"][0]
        self.assertEqual(r["capability"],"NATIVE_DIRECTION");self.assertEqual(r["direction_sample_count"],1)
    def test_no_forecast_not_sample(self):
        r=project(report(),{"TEST":receipt(prediction(slope=0))})["records"][0]
        self.assertEqual(r["direction_sample_count"],0);self.assertEqual(r["direction_status"],"NO_FORECAST")
    def test_historical_not_converted(self):
        r=project(report())["records"][0];self.assertEqual(r["capability"],"CAPABILITY_UNAVAILABLE")
    def test_three_windows_one_sample(self):
        rs=[project(report(w),{"TEST":receipt(prediction())})["records"][0] for w in (STREAM,"us_intraday_2300","us_post_close_review_0630")]
        self.assertEqual(sum(r["direction_sample_count"] for r in rs),1)
        self.assertEqual(len({r["lineage"]["sample_id"] for r in rs}),1)
    def test_corrupt_receipt(self):
        r=receipt(prediction());r["capture"]["direction"]="DOWN"
        self.assertEqual(project(report(),{"TEST":r})["records"][0]["state"],"BLOCKED_INPUT")
    def test_manual_no_sample(self):
        r=project(report(kind="manual_rerun"),{"TEST":receipt(prediction())})
        self.assertEqual(r["records"][0]["direction_sample_count"],0)
        self.assertEqual(reevaluate("/not/read",r),[])
    def test_persist_reload(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)/"us"/STREAM/"2026-09-24";base.mkdir(parents=True)
            p=base/"revision-0001.json";p.write_text(json.dumps(report()))
            publish(base/".frozen"/(receipt_key("TEST","2026-09-24")+".json"),receipt(prediction()))
            a=persist(p);b=persist(p);self.assertEqual(a,b)
            self.assertEqual(json.loads(Path(a["path"]).read_text()),project(report(),{"TEST":receipt(prediction())}))
    def test_capture_disabled(self):
        with patch("app.evaluation.us_session_direction.capture_existing") as f:
            capture_safely("TEST",{},None,"2026-09-24",STREAM,enabled=False);f.assert_not_called()
    def test_capture_failure_isolation(self):
        with patch("app.evaluation.us_session_direction.capture_existing",side_effect=ValueError):
            capture_safely("TEST",{},None,"2026-09-24",STREAM,enabled=True)
    def test_manual_capture_excluded(self):
        from app.runtime.manual_rerun_progress import PROGRESS_LOG_ENV
        with patch.dict("os.environ",{PROGRESS_LOG_ENV:"fixture"}),patch("app.evaluation.us_session_direction.capture_existing") as f:
            capture_safely("TEST",{},None,"2026-09-24",STREAM,enabled=True);f.assert_not_called()

def calendar_tests():
    for day in ("2026-03-06","2026-03-09","2026-11-02","2026-11-27"):
        def run(self,day=day):
            p=prediction(day);self.assertEqual(p["status"],"FROZEN")
            self.assertEqual(p["frozen"]["event"]["horizon"]["session_date"],day)
        setattr(NativeTests,"test_calendar_"+day.replace("-","_"),run)
    for day in ("2026-12-25","2026-09-26"):
        def run(self,day=day):
            with self.assertRaises(ValueError):prediction(day)
        setattr(NativeTests,"test_non_session_"+day.replace("-","_"),run)
calendar_tests()

class History:
    def __init__(self,rows): self.rows=rows
    def tail(self,n): return History(self.rows[-n:])
    def iterrows(self):
        for r in self.rows:
            yield datetime.fromisoformat(r["date"]),{"High":r["high"],"Low":r["low"],"Close":r["close"]}

class CaptureIntegrationTests(unittest.TestCase):
    def run_capture(self,d,day="2026-09-24",window=STREAM,missing=False):
        o=obs(day);quote={"last_price":o["reference_price"],"market_data_as_of":o["reference_as_of"]}
        capture_existing("TEST",quote,None if missing else History(o["rows"]),day,window,root=d,
                         clock=lambda:day+"T08:01:00-04:00")
        return quote
    def test_future_capture_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            quote=self.run_capture(d)
            p=Path(d)/"artifacts/archive/window_snapshots/us"/STREAM/"2026-09-24/.frozen"/(receipt_key("TEST","2026-09-24")+".json")
            r=json.loads(p.read_text());self.assertEqual(r["capture"]["status"],"FROZEN")
            self.assertEqual(r["capture"]["source"]["quote_digest"],digest(quote))
    def test_capture_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_capture(d);before={str(p):p.read_bytes() for p in Path(d).rglob("*.json")}
            self.run_capture(d);self.assertEqual(before,{str(p):p.read_bytes() for p in Path(d).rglob("*.json")})
    def test_capture_missing_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):self.run_capture(d,missing=True)
            rows=[json.loads(p.read_text()) for p in Path(d).rglob("*.json")]
            self.assertEqual(rows[0]["capture"]["status"],"BLOCKED_INPUT")
    def test_capture_input_unchanged(self):
        o=obs();h=History(o["rows"]);before=deepcopy(h.rows)
        with tempfile.TemporaryDirectory() as d:
            capture_existing("TEST",{"last_price":119,"market_data_as_of":o["reference_as_of"]},h,"2026-09-24",STREAM,
                             root=d,clock=lambda:"2026-09-24T08:01:00-04:00")
        self.assertEqual(h.rows,before)
    def test_native_quote_binding(self):
        p=prediction();p["source"]["quote_digest"]="a"*64;p["source"]=stamp(p["source"]);p=stamp(p)
        self.assertEqual(project(report(),{"TEST":receipt(p)})["records"][0]["state"],"BLOCKED_INPUT")
    def test_later_window_no_new_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_capture(d,window="us_intraday_2300")
            rows=[json.loads(p.read_text()) for p in Path(d).rglob("*.json")]
            self.assertTrue(all(r["kind"]=="US_MARKET_OBSERVATION" for r in rows))
    def test_outcome_existing_accumulator(self):
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/"artifacts/archive/window_snapshots"
            base=archive/"us"/STREAM/"2026-09-24";base.mkdir(parents=True)
            s=report();p=base/"revision-0001.json";p.write_text(json.dumps(s))
            publish(base/".frozen"/(receipt_key("TEST","2026-09-24")+".json"),receipt(prediction()))
            persist(p)
            later=obs("2026-09-28")
            other=archive/"us"/STREAM/"2026-09-28";other.mkdir(parents=True)
            publish(other/".frozen"/(later["content_hash"]+".json"),later)
            current=project(s,{"TEST":receipt(prediction())})
            current["report_identity"]["effective_trading_date"]="2026-09-28"
            current=stamp(current)
            results=reevaluate(other/"revision-0001.json",current,data_root=d,observed_at="2026-09-28T08:30:00-04:00")
            self.assertTrue(results)
            outs=list((base/".outcome").glob("*.json"));self.assertEqual(len(outs),1)
            realized=json.loads(outs[0].read_text());self.assertEqual(realized["market"],"US")
            self.assertEqual(realized["source_digest"],later["content_hash"])
            before={str(p):p.read_bytes() for p in archive.rglob("*.json")}
            reevaluate(other/"revision-0001.json",current,data_root=d,observed_at="2026-09-28T08:31:00-04:00")
            self.assertEqual(before,{str(p):p.read_bytes() for p in archive.rglob("*.json")})
    def test_special_closure(self):
        c=load_calendar("US");r=next(r for r in c["days"] if r["session_date"]=="2026-09-24")
        r.update(state="SPECIAL_CLOSURE",open_at=None,close_at=None);c=stamp(c)
        with self.assertRaises(ValueError):predict(obs(),c,frozen_at="2026-09-24T08:01:00-04:00")
    def test_early_close_hour(self):
        self.assertEqual(prediction("2026-11-27")["frozen"]["event"]["horizon"]["close_at"],"2026-11-27T13:00:00-05:00")
    def test_taipei_boundary(self):
        p=prediction();o=obs()
        with self.assertRaises(ValueError):predict(o,load_calendar("US"),frozen_at="2026-09-25T08:01:00+08:00")
    def test_shared_rule_boundaries(self):
        from app.evaluation.direction_signal import moving_average_direction
        for ma in (99,99.8,100,100.2,101):
            legacy="bullish" if ma>100*1.002 else "bearish" if ma<100*.998 else "neutral"
            self.assertEqual(moving_average_direction(ma,100),legacy)
    def test_producer_not_tactical(self):
        self.assertEqual(prediction()["producer"],"US_PREOPEN_SESSION_DIRECTION_V1")
        self.assertNotIn("tactical",prediction()["prediction_rule"])
    def test_reference_digest_binding(self):
        p=prediction()["frozen"];self.assertEqual(p["event"]["reference_digest"],p["features"]["reference"]["content_hash"])
    def test_calendar_bound(self):
        p=prediction()["frozen"];self.assertEqual(p["event"]["horizon"]["calendar_hash"],p["calendar"]["content_hash"])
    def test_no_trade_feature_ignored(self):
        o=obs();o["tactical"]={"setup":"no_trade","direction":"bearish"};o=stamp(o)
        p=predict(o,load_calendar("US"),frozen_at="2026-09-24T08:01:00-04:00")
        self.assertEqual(p["direction"],"UP")
    def test_existing_range_not_input(self):
        o=obs();o["range"]=[1,2];o["one_month_trend"]="bearish";o["three_month_trend"]="bearish";o=stamp(o)
        self.assertEqual(predict(o,load_calendar("US"),frozen_at="2026-09-24T08:01:00-04:00")["direction"],"UP")
    def test_no_notify_calls(self):
        import ast
        path=Path(__file__).resolve().parents[1]/"app/evaluation/us_session_direction.py"
        tree=ast.parse(path.read_text())
        names={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(names & {"send","send_email","place_order","fetch_symbol","history"})

class ContractAuditTests(unittest.TestCase):
    def test_machine_contract(self):
        c=json.loads((Path(__file__).resolve().parents[1]/"config/governance/us_preopen_session_direction_v1.json").read_text())
        self.assertEqual(c["producer"],PRODUCER)
        self.assertEqual(c["rules"]["UP"],"MA5 > MA10 * 1.002")
        self.assertEqual(c["rules"]["DOWN"],"MA5 < MA10 * 0.998")
        self.assertIsNone(c["event_confidence"])
    def test_delivery_object_isolation(self):
        import ast
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/"app/us_stock/live_pipeline.py").read_text())
        hooks=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="capture_safely"]
        self.assertEqual(len(hooks),1)
        self.assertEqual([n.id for n in hooks[0].args if isinstance(n,ast.Name)],["symbol","window"])
        self.assertFalse(any(isinstance(n,ast.keyword) and n.arg in {"card","prediction","strategies"} for n in hooks[0].keywords))
    def test_us_market_cannot_cross_tw(self):
        f=prediction()["frozen"]
        with self.assertRaises(ValueError):
            evaluate_direction([f],{},calendar=load_calendar("TW"),review_session="2026-09-24",observed_at="2026-09-24T22:00:00Z")


class FreezeOrderingTests(unittest.TestCase):
    def test_forecast_computed_before_freeze_clock(self):
        import app.evaluation.us_session_direction as module
        original=module.predict
        events=[]
        def predict_spy(*args,**kwargs):
            events.append("predict");return original(*args,**kwargs)
        def clock():
            events.append("clock");return "2026-09-24T08:01:00-04:00"
        o=obs()
        with tempfile.TemporaryDirectory() as d,patch.object(module,"predict",side_effect=predict_spy):
            module.capture_existing("TEST",{"last_price":119,"market_data_as_of":o["reference_as_of"]},
                                    History(o["rows"]),"2026-09-24",STREAM,root=d,clock=clock)
        self.assertEqual(events,["clock","predict","clock","predict"])
    def test_calculation_crossing_open_does_not_freeze(self):
        o=obs();times=iter(["2026-09-24T09:29:59-04:00","2026-09-24T09:30:00-04:00"])
        with tempfile.TemporaryDirectory() as d:
            capture_existing("TEST",{"last_price":119,"market_data_as_of":o["reference_as_of"]},
                             History(o["rows"]),"2026-09-24",STREAM,root=d,clock=lambda:next(times))
            p=Path(d)/"artifacts/archive/window_snapshots/us"/STREAM/"2026-09-24/.frozen"/(receipt_key("TEST","2026-09-24")+".json")
            v=json.loads(p.read_text())
            self.assertEqual(v["capture"]["status"],"BLOCKED_INPUT")
            self.assertNotIn("frozen",v["capture"])


class MissingCalendarReceiptTests(unittest.TestCase):
    def test_calendar_failure_is_blocked_receipt(self):
        with tempfile.TemporaryDirectory() as d,patch("app.evaluation.us_session_direction.load_calendar",side_effect=ValueError("CALENDAR_MISSING")):
            with self.assertRaises(ValueError):
                capture_existing("TEST",{},None,"2026-09-24",STREAM,root=d)
            rows=[json.loads(p.read_text()) for p in Path(d).rglob("*.json")]
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["capture"]["status"],"BLOCKED_INPUT")
