"""254 synthetic fixtures only; no production execution or transports."""
import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from app.evaluation.daily_evaluation import *
from app.evaluation.session_calendar import load_calendar, latest_completed_session, CalendarError
from app.dashboard.daily_evaluation_archive import persist_daily, collect_market, post_close_review, publish
from app.dashboard.production_evidence_archive import project
from app.us_stock.trading_calendar import resolve_us_effective_trading_date
from test_production_evidence import source_snapshot, frozen, realized
from test_us_session_direction import prediction, receipt, report

def packet():
    s,src=source_snapshot()
    tw=project(s,src)
    us=project(report(),{"TEST":receipt(prediction())})
    return {m:{"calendar":load_calendar(m),"records":[r],"outcomes":[]} for m,r in (("TW",tw),("US",us))}

def mature_inputs():
    x=packet()
    for market in ("TW","US"):
        p=x[market]["records"][0]["records"][0]["frozen"]
        from app.evaluation.production_evidence import outcome
        x[market]["outcomes"]=[outcome(p,close=p["features"]["reference"]["value"]+5,source="fixture",revision="v1",
             source_digest="a"*64,available_at=p["event"]["horizon"]["close_at"],session_date="2026-09-24")]
    return x

class DailyTests(unittest.TestCase):
    def build(self,x=None,day="2026-09-25",prior=None):return build_daily(day,x or packet(),prior)
    def test_cross_dates(self):
        v=self.build(day="2026-09-28")
        self.assertEqual(v["markets"]["TW"]["review_session"],"2026-09-24")
        self.assertEqual(v["markets"]["US"]["review_session"],"2026-09-25")
    def test_schedule_zone(self):self.assertEqual(canonical_cutoff("2026-09-25"),"2026-09-25T17:00:00+08:00")
    def test_253_admission(self):
        x=packet();ps,_,_=admitted(x["US"]["records"],"US",canonical_cutoff("2026-09-25"),"2026-09-24")
        self.assertEqual(len(ps),1);self.assertEqual(ps[0]["producer"],"US_PREOPEN_SESSION_DIRECTION_V1")
    def test_252_waiting(self):
        r=self.build()["markets"]["US"]["stocks"]["TEST"]["sample_reviews"]
        self.assertEqual(next(iter(r.values()))["assessment"]["state"],"WAITING_OUTCOME")
    def test_mature(self):
        r=self.build(mature_inputs())["markets"]["US"]["stocks"]["TEST"]
        self.assertTrue(next(iter(r["sample_reviews"].values()))["assessment"]["eligible"])
    def test_provisional_rejected(self):
        x=mature_inputs();x["US"]["outcomes"][0]["available_at"]="2026-09-24T15:00:00-04:00"
        x["US"]["outcomes"][0]=stamp(x["US"]["outcomes"][0])
        self.assertEqual(self.build(x)["markets"]["US"]["status"],"BLOCKED_INPUT")
    def test_partial_251b_preserves_252(self):
        r=self.build(mature_inputs())["markets"]["US"]["stocks"]["TEST"]
        self.assertEqual(r["direction_component"]["windows"]["3"]["sample_size"],1)
        self.assertIsNone(r["evaluation"]["user_facing"]["prediction_accuracy_score"]["score"])
        self.assertEqual(r["evaluation"]["internal_evidence"]["composite"]["status"],"PENDING")
    def test_251c_chain(self):
        r=self.build()["markets"]["US"]["stocks"]["TEST"]
        self.assertEqual(r["evidence_chain"]["state"],"INCOMPLETE")
        self.assertEqual(r["realized_effect"]["state"],"INSUFFICIENT_EVIDENCE")
    def test_thresholds(self):
        r=self.build()["markets"]["US"]["stocks"]["TEST"]["direction_component"]
        self.assertEqual([r["windows"][n]["required"] for n in ("3","10")],[3,10])
    def test_replay(self):
        v=self.build();self.assertEqual(replay(v),v)
    def test_determinism(self):self.assertEqual(self.build(),self.build())
    def test_source_unchanged(self):
        x=packet();before=deepcopy(x);self.build(x);self.assertEqual(before,x)
    def test_no_predecessor(self):self.assertEqual(self.build()["comparison"]["status"],"NO_PREDECESSOR")
    def test_predecessor(self):
        p=predecessor_proof(self.build());v=self.build(day="2026-09-26",prior=p)
        self.assertEqual(v["comparison"]["status"],"BOUND");replay(v)
    def test_no_score_comparison(self):
        p=predecessor_proof(self.build());v=self.build(day="2026-09-26",prior=p)
        self.assertTrue(all(c["status"]=="INSUFFICIENT_COMPARISON" for c in v["comparison"]["components"].values()))
    def test_predecessor_corrupt(self):
        p=predecessor_proof(self.build());p["identity"]="bad"
        self.assertEqual(self.build(day="2026-09-26",prior=p)["comparison"]["status"],"REJECTED")
    def test_predecessor_not_feature(self):
        a=self.build(day="2026-09-26");b=self.build(day="2026-09-26",prior=predecessor_proof(self.build()))
        self.assertEqual(a["markets"],b["markets"])
    def test_no_notification(self):self.assertFalse(self.build()["notification"])
    def test_no_lifecycle_mutation(self):self.assertFalse(self.build()["lifecycle_mutation"])
    def test_malformed_replay(self):
        v=self.build();v["thresholds"]["3"]=1;v=stamp(v)
        with self.assertRaises(ValueError):replay(v)
    def test_version_reject(self):
        v=self.build();v["schema_version"]="bad";v=stamp(v)
        with self.assertRaises(ValueError):replay(v)
    def test_independent_market_failure(self):
        x=packet();x["US"]["calendar"]["revision"]+=1;v=self.build(x)
        self.assertEqual(v["markets"]["TW"]["status"],"VALID");self.assertEqual(v["status"],"BLOCKED_INPUT")
    def test_duplicate(self):
        x=mature_inputs();x["US"]["records"]*=4
        r=self.build(x)["markets"]["US"]["stocks"]["TEST"]
        self.assertEqual(len(r["sample_reviews"]),1)
    def test_conflicting_outcome(self):
        x=mature_inputs();o=deepcopy(x["US"]["outcomes"][0]);o["close"]+=1;x["US"]["outcomes"].append(stamp(o))
        self.assertEqual(self.build(x)["markets"]["US"]["status"],"BLOCKED_INPUT")
    def test_attempts_not_forecasts(self):
        x=packet();x["US"]["records"]=[project(report(),{"TEST":receipt(prediction(slope=0))})]
        self.assertEqual(len(self.build(x)["markets"]["US"]["stocks"]["TEST"]["sample_reviews"]),0)
    def test_freeze_reference_preserved(self):
        x=packet();r=self.build(x)["markets"]["US"]["stocks"]["TEST"]["sample_reviews"]
        p=x["US"]["records"][0]["records"][0]["frozen"]
        self.assertEqual(next(iter(r.values()))["frozen_reference"],p["features"]["reference"])
    def test_freeze_atr_preserved(self):
        x=packet();r=self.build(x)["markets"]["US"]["stocks"]["TEST"]["sample_reviews"]
        p=x["US"]["records"][0]["records"][0]["frozen"]
        self.assertEqual(next(iter(r.values()))["frozen_atr14"],p["features"]["atr14"])

def add_exclusions():
    changes={
       "inherited":lambda r:r["records"][0].update(capability="INHERITED_REFERENCE_ONLY"),
       "no_forecast":lambda r:r["records"][0].update(direction_status="NO_FORECAST"),
       "synthetic":lambda r:r.update(input_kind="SYNTHETIC"),
       "synthetic_flag":lambda r:r.update(synthetic=True),
       "historical":lambda r:r["records"][0].update(state="HISTORICAL_INELIGIBLE"),
       "blocked":lambda r:r["records"][0].update(state="BLOCKED_INPUT"),
       "manual":lambda r:r["report_identity"].update(run_kind="manual_rerun"),
       "zero_sample":lambda r:r["records"][0].update(direction_sample_count=0),
       "intraday":lambda r:r["report_identity"].update(window="us_intraday_2300"),
       "postclose":lambda r:r["report_identity"].update(window="us_post_close_review_0630"),
    }
    for name,change in changes.items():
        def test(self,change=change):
            x=packet();r=x["US"]["records"][0];change(r);x["US"]["records"][0]=stamp(r)
            self.assertEqual(len(self.build(x)["markets"]["US"]["stocks"]["TEST"]["sample_reviews"]),0)
        setattr(DailyTests,"test_exclude_"+name,test)
add_exclusions()

class CalendarTests(unittest.TestCase):
    def test_timezone_required(self):
        with self.assertRaises(CalendarError):latest_completed_session(load_calendar("US"),"US",datetime(2026,9,25))
    def test_coverage(self):
        with self.assertRaises(CalendarError):latest_completed_session(load_calendar("US"),"US","2027-01-01T17:00:00+08:00")
    def test_digest(self):
        c=load_calendar("US");c["revision"]+=1
        with self.assertRaises(CalendarError):latest_completed_session(c,"US","2026-09-25T17:00:00+08:00")
    def test_special_closure(self):
        c=load_calendar("US");row=next(r for r in c["days"] if r["session_date"]=="2026-09-24")
        row.update(state="SPECIAL_CLOSURE",open_at=None,close_at=None);c=stamp(c)
        self.assertEqual(latest_completed_session(c,"US","2026-09-25T06:30:00+08:00")["session_date"],"2026-09-23")

for name,reference,want in (
    ("edt","2026-09-25T06:30:00+08:00","2026-09-24"),
    ("est","2026-01-07T06:30:00+08:00","2026-01-06"),
    ("dst_spring","2026-03-10T06:30:00+08:00","2026-03-09"),
    ("dst_fall","2026-11-03T06:30:00+08:00","2026-11-02"),
    ("holiday","2026-07-04T06:30:00+08:00","2026-07-02"),
    ("early_close","2026-11-28T06:30:00+08:00","2026-11-27"),
    ("before_close","2026-09-25T03:30:00+08:00","2026-09-23"),
    ("taipei_rollover","2026-09-25T00:30:00+08:00","2026-09-23"),
):
    def test(self,reference=reference,want=want):
        self.assertEqual(resolve_us_effective_trading_date(datetime.fromisoformat(reference),"us_post_close_review_0630").isoformat(),want)
    setattr(CalendarTests,"test_"+name,test)

class PersistenceTests(unittest.TestCase):
    def test_idempotency(self):
        with tempfile.TemporaryDirectory() as d,patch("app.dashboard.daily_evaluation_archive.collect",return_value=packet()):
            a,v=persist_daily(d,"2026-09-25");b,w=persist_daily(d,"2026-09-25")
            self.assertEqual(a,b);self.assertEqual(v,w);self.assertEqual(json.loads(a.read_text()),v)
    def test_immutable_revision(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("app.dashboard.daily_evaluation_archive.collect",return_value=packet()):a,v=persist_daily(d,"2026-09-25")
            with patch("app.dashboard.daily_evaluation_archive.collect",return_value=mature_inputs()):b,w=persist_daily(d,"2026-09-25")
            self.assertNotEqual(a,b);self.assertTrue(a.exists());self.assertTrue(b.exists())
    def test_manual_same_identity(self):
        with tempfile.TemporaryDirectory() as d,patch("app.dashboard.daily_evaluation_archive.collect",return_value=packet()):
            a,v=persist_daily(d,"2026-09-25");b,w=persist_daily(d,"2026-09-25")
            self.assertEqual(v["identity"],w["identity"])
    def test_shadow_isolation(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as o,patch("app.dashboard.daily_evaluation_archive.collect",return_value=packet()):
            p,v=persist_daily(d,"2026-09-25",output_root=o)
            self.assertFalse((Path(d)/".daily_evaluation").exists());self.assertTrue(p.is_relative_to(o))
    def test_previous_pin_stable(self):
        with tempfile.TemporaryDirectory() as d,patch("app.dashboard.daily_evaluation_archive.collect",return_value=packet()):
            persist_daily(d,"2026-09-25");a,v=persist_daily(d,"2026-09-26");b,w=persist_daily(d,"2026-09-26")
            self.assertEqual(v,w);self.assertEqual(v["comparison"]["status"],"BOUND")
    def test_collect_bound_report(self):
        with tempfile.TemporaryDirectory() as d:
            s,src=source_snapshot();r=project(s,src);p=Path(d)/"tw/pre_open_0700/2026-09-24"
            publish(p/"revision-0001.json",s);publish(p/".evidence"/(r["content_hash"]+".json"),r)
            x=collect_market(d,"TW",load_calendar("TW"),canonical_cutoff("2026-09-25"))
            self.assertEqual(x["records"],[r])
    def test_corrupt_canonical_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            s,src=source_snapshot();r=project(s,src);p=Path(d)/"tw/pre_open_0700/2026-09-24"
            s["revision"]=2;publish(p/"revision-0001.json",s);publish(p/".evidence"/(r["content_hash"]+".json"),r)
            with self.assertRaises(ValueError):collect_market(d,"TW",load_calendar("TW"),canonical_cutoff("2026-09-25"))
    def test_postclose_is_sidecar(self):
        with tempfile.TemporaryDirectory() as d:
            s=report("us_post_close_review_0630");p=Path(d)/"us/us_post_close_review_0630/2026-09-24/revision-0001.json"
            publish(p,s);before=p.read_bytes()
            with patch("app.dashboard.daily_evaluation_archive.collect_market",return_value=packet()["US"]):
                out=post_close_review(p)
            self.assertEqual(p.read_bytes(),before);self.assertEqual(json.loads(out.read_text())["legacy_range_tactical_mfe_mae"],"UNCHANGED_CANONICAL_REPORT")
    def test_failure_isolated(self):
        from app.dashboard.production_evidence_archive import persist
        with tempfile.TemporaryDirectory() as d:
            s=report("us_post_close_review_0630");p=Path(d)/"us/us_post_close_review_0630/2026-09-24/revision-0001.json";publish(p,s)
            with patch("app.dashboard.production_evidence_archive.reevaluate",return_value=[]),patch("app.dashboard.daily_evaluation_archive.post_close_review",side_effect=ValueError("bad")):
                self.assertEqual(persist(p)["status"],"EVIDENCE_ACCUMULATED")

class AdditionalTests(unittest.TestCase):
    def test_contract_agreement(self):
        from app.evaluation.daily_evaluation import VERSION
        root=Path(__file__).resolve().parents[1]
        c=json.loads((root/"config/governance/daily_evaluation_integration_contract_v1.json").read_text())
        self.assertEqual(c["schema_version"],VERSION);self.assertEqual(c["thresholds"],{"3":3,"10":10})
        self.assertFalse(c["notification"]);self.assertFalse(c["lifecycle_mutation"])
    def test_ten_real_independent_fixture_sessions(self):
        from app.evaluation.production_evidence import outcome
        x=packet();c=x["US"]["calendar"]
        days=[r["session_date"] for r in c["days"] if r["state"]=="NORMAL" and r["session_date"]<="2026-09-24"][-10:]
        x["US"]["records"]=[];x["US"]["outcomes"]=[]
        for day in days:
            p=prediction(day)["frozen"];r=packet()["US"]["records"][0]
            r["report_identity"]["effective_trading_date"]=day
            r["records"][0]["frozen"]=p;r["records"][0]["lineage"]=None
            x["US"]["records"].append(stamp(r))
            x["US"]["outcomes"].append(outcome(p,close=125,source="fixture",revision="v1",source_digest="a"*64,
                available_at=p["event"]["horizon"]["close_at"],session_date=day))
        v=build_daily("2026-09-25",x)
        result=v["markets"]["US"]["stocks"]["TEST"]["direction_component"]
        self.assertEqual(result["state"],"EVALUATED");self.assertEqual(result["windows"]["10"]["sample_size"],10)
        self.assertEqual(result["windows"]["3"]["sample_size"],3)
        self.assertIsNone(result["prediction_accuracy_score"])
    def test_future_outcome_waits(self):
        x=mature_inputs();o=x["US"]["outcomes"][0];o["available_at"]="2026-09-26T12:00:00-04:00"
        x["US"]["outcomes"][0]=stamp(o)
        v=build_daily("2026-09-25",x)
        reviews=v["markets"]["US"]["stocks"]["TEST"]["sample_reviews"]
        self.assertEqual(next(iter(reviews.values()))["assessment"]["state"],"WAITING_OUTCOME")
    def test_canonical_contract_unchanged(self):
        from app.evaluation.offline_review_evaluators import load_contract
        self.assertEqual(load_contract()["weights_percent"]["time"],{"last_3_sessions":35,"last_10_sessions":65})
    def test_no_entrypoint_transports(self):
        import ast
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/"scripts/orchestrator/approved_daily_evaluation.py").read_text())
        names=[n.module or "" for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertFalse(any(any(x in n for x in ("delivery","notification","trading","pipeline")) for n in names))

class BlockedPersistenceTests(unittest.TestCase):
    def test_blocked_saved_not_success(self):
        x=packet();x["US"]["prerequisite_error"]="INVALID_CALENDAR_OR_ARCHIVE"
        with tempfile.TemporaryDirectory() as d,patch("app.dashboard.daily_evaluation_archive.collect",return_value=x):
            path,value=persist_daily(d,"2026-09-25")
            self.assertTrue(path.exists());self.assertEqual(value["status"],"BLOCKED_INPUT");replay(value)
    def test_missing_calendar_isolated(self):
        from app.dashboard.daily_evaluation_archive import collect
        with tempfile.TemporaryDirectory() as d:
            x=collect(d,"2026-09-25",calendars={"TW":load_calendar("TW"),"US":None})
            v=build_daily("2026-09-25",x)
            self.assertEqual(v["markets"]["TW"]["status"],"VALID")
            self.assertEqual(v["markets"]["US"]["status"],"BLOCKED_INPUT")
    def test_evaluator_versions_pinned(self):
        v=build_daily("2026-09-25",packet())
        self.assertEqual(set(v["evaluator_contracts"]),{"251A","251B","251C","252","254"})
