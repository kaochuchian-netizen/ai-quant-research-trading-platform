"""Synthetic-only 252 semantic regressions; never production inputs."""
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import tempfile
from app.evaluation.production_evidence import *
from app.evaluation.session_calendar import load_calendar
from app.evaluation.offline_review_evaluators import realized_prediction_direction
from app.dashboard.production_evidence_archive import publish

def frozen(day="2026-09-24", symbol="TEST"):
    c=load_calendar("TW")
    ref=feature("reference_price",100,source="fixture",revision="v1",source_digest="a"*64,
                as_of=day+"T06:00:00+08:00",available_at=day+"T06:00:00+08:00",producer="fixture")
    atr=feature("atr14",10,source="fixture",revision="v1",source_digest="b"*64,
                as_of=day+"T06:00:00+08:00",available_at=day+"T06:00:00+08:00",producer="WILDER_14_COMPLETED_POINT_IN_TIME")
    return freeze(prediction_id="fixture-"+day,symbol=symbol,direction="UP",frozen_at=day+"T07:00:00+08:00",
                  reference=ref,atr=atr,calendar=c,review_session=day,producer="fixture-v1")

def realized(p,close=105):
    h=p["event"]["horizon"]
    return outcome(p,close=close,source="fixture",revision="v1",source_digest="c"*64,
                   available_at=h["close_at"],session_date=h["session_date"])

class EvidenceTests(unittest.TestCase):
    def test_native(self): self.assertEqual(capability("TW","pre_open_0700"),"NATIVE_DIRECTION")
    def test_freeze(self): self.assertEqual(validate_frozen(frozen()),frozen())
    def test_replay(self): self.assertEqual(frozen(),frozen())
    def test_optional_confidence(self): self.assertIsNone(frozen()["event_confidence"])
    def test_unique(self): self.assertEqual(len(unique_predictions([frozen()]*4)),1)
    def test_lineage(self): self.assertEqual(lineage(frozen())["origin_event_contract"],EVENT)
    def test_missing_frozen(self): self.assertEqual(assess({},None,observed_at="2026-09-24T16:00:00+08:00")["state"],"BLOCKED_INPUT")
    def test_waiting(self): self.assertEqual(assess(frozen(),None,observed_at="2026-09-24T08:00:00+08:00")["state"],"WAITING_OUTCOME")
    def test_outcome_missing(self): self.assertEqual(assess(frozen(),None,observed_at="2026-09-24T16:00:00+08:00")["state"],"WAITING_OUTCOME")
    def test_mature_single_is_insufficient(self): self.assertEqual(assess(frozen(),realized(frozen()),observed_at="2026-09-24T16:00:00+08:00")["state"],"INSUFFICIENT_SAMPLE")
    def test_direction_without_confidence(self): self.assertTrue(assess(frozen(),realized(frozen()),observed_at="2026-09-24T16:00:00+08:00")["direction_correct"])
    def test_insufficient(self):
        p=frozen(); r=evaluate_direction([p],{p["sample_id"]:realized(p)},calendar=p["calendar"],review_session="2026-09-24",observed_at="2026-09-24T16:00:00+08:00")
        self.assertEqual(r["state"],"INSUFFICIENT_SAMPLE");self.assertIsNone(r["score"])
    def test_ten_sessions(self):
        c=load_calendar("TW")
        days=[r["session_date"] for r in c["days"] if r["state"] in {"NORMAL","EARLY_CLOSE"} and r["session_date"]<="2026-09-24"][-10:]
        ps=[frozen(d) for d in days];outs={p["sample_id"]:realized(p) for p in ps}
        r=evaluate_direction(ps,outs,calendar=c,review_session=days[-1],observed_at=days[-1]+"T16:00:00+08:00")
        self.assertEqual(r["state"],"EVALUATED");self.assertEqual(r["admission_state"],"READY_FOR_EVALUATION");self.assertEqual(r["score"],100);self.assertIsNone(r["prediction_accuracy_score"])
    def test_no_reweight(self):
        p=frozen();r=evaluate_direction([p],{},calendar=p["calendar"],review_session="2026-09-24",observed_at="2026-09-24T16:00:00+08:00")
        self.assertFalse(r["aggregate_reweighted"]);self.assertEqual(r["improvement"],"NOT_APPLICABLE")
    def test_immutable(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.json";publish(p,frozen());publish(p,frozen())
            with self.assertRaisesRegex(ValueError,"IMMUTABLE"): publish(p,{"different":True})
    def test_legacy_confidence(self):
        p=frozen()
        with self.assertRaises(ValueError):
            freeze(prediction_id=p["prediction_id"],symbol=p["symbol"],direction="UP",frozen_at=p["prediction_frozen_at"],
                   reference=p["features"]["reference"],atr=p["features"]["atr14"],calendar=p["calendar"],
                   review_session="2026-09-24",producer="fixture",event_confidence={"value":70})
    def test_horizon_dormant(self):
        with self.assertRaisesRegex(ValueError,"NO_NATIVE"): horizon(load_calendar("US"),"US","us_intraday_2300","2026-09-24")
    def test_late_freeze(self):
        p=frozen()
        with self.assertRaisesRegex(ValueError,"BEFORE_SESSION"):
            freeze(prediction_id=p["prediction_id"],symbol=p["symbol"],direction="UP",frozen_at="2026-09-24T09:00:00+08:00",
                   reference=p["features"]["reference"],atr=p["features"]["atr14"],calendar=p["calendar"],
                   review_session="2026-09-24",producer="fixture")
    def test_future_feature(self):
        p=frozen();r=deepcopy(p["features"]["reference"]);r["available_at"]="2026-09-24T08:00:00+08:00";r=stamp(r)
        with self.assertRaisesRegex(ValueError,"FUTURE"):
            freeze(prediction_id=p["prediction_id"],symbol=p["symbol"],direction="UP",frozen_at=p["prediction_frozen_at"],
                   reference=r,atr=p["features"]["atr14"],calendar=p["calendar"],review_session="2026-09-24",producer="fixture")
    def test_immature_outcome(self):
        with self.assertRaisesRegex(ValueError,"MATURE"):
            outcome(frozen(),close=100,source="fixture",revision="v1",source_digest="c"*64,
                    available_at="2026-09-24T12:00:00+08:00",session_date="2026-09-24")

def add_cases():
    for stream in ("intraday_1305","pre_close_1335","post_close_1500"):
        def test(self,stream=stream):
            self.assertEqual(capability("TW",stream),"INHERITED_REFERENCE_ONLY")
            self.assertEqual(lineage(frozen()),lineage(frozen()))
            self.assertEqual(len(unique_predictions([frozen()]*4)),1)
        setattr(EvidenceTests,"test_inherited_"+stream,test)
    for stream in MAPPING["US"]:
        def test(self,stream=stream):
            self.assertEqual(capability("US",stream),"CAPABILITY_UNAVAILABLE")
        setattr(EvidenceTests,"test_unavailable_"+stream,test)
    for field in ("prediction_frozen_at","event","features","prediction_id","sample_id","calendar"):
        def test(self,field=field):
            p=frozen();del p[field]
            self.assertEqual(assess(p,None,observed_at="2026-09-24T16:00:00+08:00")["state"],"BLOCKED_INPUT")
        setattr(EvidenceTests,"test_missing_"+field,test)
    for close in (98,99,99.00001,100,100.99999,101,102):
        def test(self,close=close):
            p=frozen();a=assess(p,realized(p,close),observed_at="2026-09-24T16:00:00+08:00")
            self.assertEqual(a["direction"],realized_prediction_direction(close,100,10))
        setattr(EvidenceTests,"test_canonical_equivalence_"+str(close).replace(".","_"),test)
    for market,stream,day,want in (("TW","pre_open_0700","2026-09-24","2026-09-24"),
       ("TW","intraday_1305","2026-09-24","2026-09-29"),
       ("US","us_pre_market_2000","2026-11-27","2026-11-27"),
       ("US","us_intraday_2300","2026-11-27","2026-11-30")):
        def test(self,market=market,stream=stream,day=day,want=want):
            self.assertEqual(horizon(load_calendar(market),market,stream,day,native=True)["session_date"],want)
        setattr(EvidenceTests,"test_mapping_"+market+stream,test)
add_cases()


from unittest.mock import patch
import json
from app.dashboard.production_evidence_archive import project, persist, reevaluate
from app.dashboard.window_snapshot_archive import snapshot_id
from test_production_shadow import snapshot
from app.evaluation.prediction_capture import capture

def source_snapshot(window="pre_open_0700", market="TW", kind="scheduled"):
    s=snapshot(market,window=window,kind=kind)
    p=frozen()
    row={"symbol":p["symbol"],"prediction_snapshot_v2":{"prediction_identity":p["prediction_id"]}}
    s["payload"]={"structured_review_cards":[row]} if market=="TW" else {"items":[{"symbol":"TEST","prediction":{"one_month_trend":"bullish","predicted_session_low":1,"predicted_session_high":2}}]}
    s["snapshot_id"]=snapshot_id({k:v for k,v in s.items() if k!="snapshot_id"})
    saved=stamp({"native_prediction_id":p["prediction_id"],"native_prediction_digest":digest(row["prediction_snapshot_v2"]),"capture":{"status":"FROZEN","frozen":p}})
    return s,{p["prediction_id"]:saved}

class ArchiveTests(unittest.TestCase):
    def test_four_windows_one_sample(self):
        records=[]
        for w in MAPPING["TW"]:
            s,src=source_snapshot(w); records+=project(s,src)["records"]
        self.assertEqual(sum(r["direction_sample_count"] for r in records),1)
        self.assertEqual(len({r["lineage"]["sample_id"] for r in records}),1)
    def test_report_unchanged(self):
        s,src=source_snapshot();before=deepcopy(s);project(s,src);self.assertEqual(s,before)
    def test_us_range_monthly_not_direction(self):
        s,_=source_snapshot("us_pre_market_2000","US");r=project(s)["records"][0]
        self.assertEqual(r["capability"],"CAPABILITY_UNAVAILABLE");self.assertIsNone(r["state"]);self.assertEqual(r["direction_sample_count"],0)
    def test_historical(self):
        s,_=source_snapshot();r=project(s)["records"][0]
        self.assertEqual(r["state"],"HISTORICAL_INELIGIBLE");self.assertEqual(r["direction_sample_count"],0)
    def test_historical_inherited(self):
        s,_=source_snapshot("intraday_1305");r=project(s)["records"][0]
        self.assertEqual(r["capability"],"INHERITED_REFERENCE_ONLY");self.assertIsNone(r["state"]);self.assertEqual(r["direction_sample_count"],0)
    def test_corrupt_source(self):
        s,src=source_snapshot();next(iter(src.values()))["capture"]["frozen"]["direction"]="DOWN"
        self.assertEqual(project(s,src)["records"][0]["state"],"BLOCKED_INPUT")
    def test_report_revision(self):
        s,src=source_snapshot();a=project(s,src)
        s["revision"]+=1;s["snapshot_id"]=snapshot_id({k:v for k,v in s.items() if k!="snapshot_id"})
        b=project(s,src)
        self.assertNotEqual(a["content_hash"],b["content_hash"]);self.assertEqual(a["records"][0]["lineage"],b["records"][0]["lineage"])
    def test_manual_isolation(self):
        s,src=source_snapshot(kind="manual_rerun");r=project(s,src)
        self.assertEqual(reevaluate(Path("/tmp/not-opened.json"),r),[])
    def test_persist_reload(self):
        s,_=source_snapshot("us_pre_market_2000","US")
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"us/us_pre_market_2000/2026-09-24/revision-0001.json";p.parent.mkdir(parents=True);p.write_text(json.dumps(s))
            a=persist(p);b=persist(p);self.assertEqual(a,b)
            self.assertEqual(json.loads(Path(a["path"]).read_text()),project(s))
    def test_project_replay(self):
        s,src=source_snapshot();self.assertEqual(project(s,src),project(s,src))
    def test_no_fix_fabrication(self):
        s,src=source_snapshot();self.assertFalse(project(s,src)["lifecycle_mutation"])
    def test_future_capture(self):
        c=load_calendar("TW");days=[r["session_date"] for r in c["days"] if r["state"]=="NORMAL" and r["session_date"]<"2026-09-24"][-20:]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data/historical/1234_daily.csv";p.parent.mkdir(parents=True)
            p.write_text("date,open,high,low,close,volume\n"+"".join(day+",100,102,98,100,1000\n" for day in days))
            card={"symbol":"1234","trading_date":"2026-09-24","prediction_snapshot_v2":{"prediction_identity":"native","reference_price":100,"method_version":"fixture","direction_forecast":"bullish"}}
            before=deepcopy(card)
            r=capture(card,root=d,clock=lambda:"2026-09-24T07:00:00+08:00")
            self.assertEqual(r["status"],"FROZEN");validate_frozen(r["frozen"]);self.assertEqual(before,card)
    def test_late_capture_not_historical(self):
        with tempfile.TemporaryDirectory() as d:
            r=capture({"symbol":"1234","trading_date":"2026-09-24"},root=d,clock=lambda:"2026-09-24T16:00:00+08:00")
            self.assertEqual(r["status"],"BLOCKED_INPUT")
    def test_mixed_symbols_rejected(self):
        with self.assertRaisesRegex(ValueError,"MIXED_SYMBOL"):
            evaluate_direction([frozen(symbol="A"),frozen(symbol="B")],{},calendar=load_calendar("TW"),review_session="2026-09-24",observed_at="2026-09-24T16:00:00+08:00")


class RuntimeTests(unittest.TestCase):
    def test_outcome_persistence_replay(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); archive=root/"artifacts/archive/window_snapshots"
            f=frozen(symbol="1234"); s,src=source_snapshot()
            row=s["payload"]["structured_review_cards"][0];row["symbol"]="1234"
            s["snapshot_id"]=snapshot_id({k:v for k,v in s.items() if k!="snapshot_id"})
            src={f["prediction_id"]:stamp({"native_prediction_id":f["prediction_id"],"native_prediction_digest":digest(row["prediction_snapshot_v2"]),"capture":{"status":"FROZEN","frozen":f}})}
            record=project(s,src)
            p=archive/"tw/pre_open_0700/2026-09-24/revision-0001.json";p.parent.mkdir(parents=True)
            publish(p.parent/".evidence"/(record["content_hash"]+".json"),record)
            csv=root/"data/historical/1234_daily.csv";csv.parent.mkdir(parents=True)
            csv.write_text("date,open,high,low,close,volume\n2026-09-24,100,106,98,105,1000\n2026-09-25,105,106,104,105,1000\n")
            os.utime(csv,(1790330400,1790330400))
            a=reevaluate(p,record,data_root=root,observed_at="2026-09-25T16:00:00+08:00")
            b=reevaluate(p,record,data_root=root,observed_at="2026-09-25T16:00:00+08:00")
            self.assertEqual(a,b);self.assertEqual(len(a),1)
            self.assertEqual(len(list(p.parent.glob(".outcome/*.json"))),1)
            self.assertEqual(len(list(p.parent.glob(".assessment/*.json"))),1)
    def test_contract_consistency(self):
        c=json.loads((Path(__file__).resolve().parents[1]/"config/governance/production_evidence_accumulation_v1.json").read_text())
        self.assertEqual(c["schema_version"],VERSION);self.assertEqual(set(c["states"]),STATES)
        for market,streams in c["capabilities"].items():
            for stream,value in streams.items(): self.assertEqual(capability(market,stream),value)
        self.assertEqual(c["minimum_samples"],{"3d":3,"10d":10})
    def test_predecessor_reject(self):
        from app.dashboard.production_evidence_archive import bind_assessment
        v={"result":{"state":"INSUFFICIENT_SAMPLE"}}
        self.assertEqual(bind_assessment(v,{"invalid":True})["comparison"]["status"],"REJECTED")
    def test_no_predecessor(self):
        from app.dashboard.production_evidence_archive import bind_assessment
        v=bind_assessment({"result":{"state":"INSUFFICIENT_SAMPLE"}})
        self.assertEqual(v["comparison"]["status"],"NO_PREDECESSOR")
        self.assertEqual(v["realized_fix_effect"],"INSUFFICIENT_EVIDENCE")

