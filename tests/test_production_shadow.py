"""Synthetic session integration; no production readers, transports or runtime."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from app.evaluation.session_calendar import load_calendar, session, CalendarError, validate_calendar
from app.evaluation.offline_report_projection import digest
from app.evaluation.production_shadow import build_shadow, bind_predecessor, validate_shadow, source_packet
from app.dashboard.shadow_evaluation_archive import persist, hook
from app.dashboard.window_snapshot_archive import snapshot_id, write_snapshot, load_admitted_snapshots

def calendar(market="TW"):
    return deepcopy(load_calendar(market))

def snapshot(market="TW", day="2026-09-24", window=None, revision=1, kind="scheduled"):
    v={"schema_version":"window_snapshot_archive_v1", "market":market,
       "window":window or ("post_close_1500" if market=="TW" else "us_post_close_review_0630"),
       "effective_trading_date":day, "generated_at":day+("T15:00:00+08:00" if market=="TW" else "T17:00:00-04:00"),
       "revision":revision, "run_kind":kind, "status":"complete", "admitted":True,
       "runtime_provenance":"scheduled_production" if kind=="scheduled" else "manual_rerun",
       "payload":{"structured_review_cards":[{"symbol":"SYNTHETIC"}]} if market=="TW" else {"items":[{"symbol":"SYNTHETIC"}]}}
    v["snapshot_id"]=snapshot_id(v)
    return v

def packet(market="TW", **kw):
    return source_packet(snapshot(market, **kw))

def artifact(market="TW", **kw):
    return build_shadow(packet(market, **kw), calendar(market))

class CalendarTests(unittest.TestCase):
    def test_tw_normal(self): self.assertEqual(session(calendar(),"TW","2026-09-24")["state"],"NORMAL")
    def test_tw_holiday(self):
        with self.assertRaisesRegex(CalendarError,"NON_TRADING"): session(calendar(),"TW","2026-09-28")
    def test_tw_boundary(self):
        self.assertEqual(session(calendar(),"TW","2026-12-31")["session_date"],"2026-12-31")
    def test_us_normal(self): self.assertEqual(session(calendar("US"),"US","2026-09-24")["state"],"NORMAL")
    def test_us_holiday(self):
        with self.assertRaisesRegex(CalendarError,"NON_TRADING"): session(calendar("US"),"US","2026-11-26")
    def test_early_close(self):
        self.assertEqual(session(calendar("US"),"US","2026-11-27")["close_at"],"2026-11-27T13:00:00-05:00")
    def test_special_closure(self):
        c=calendar("US"); r=next(r for r in c["days"] if r["session_date"]=="2026-09-24")
        r.update(state="SPECIAL_CLOSURE",open_at=None,close_at=None)
        c["content_hash"]=digest({k:v for k,v in c.items() if k!="content_hash"})
        with self.assertRaisesRegex(CalendarError,"NON_TRADING"): session(c,"US","2026-09-24")
    def test_digest(self):
        c=calendar();c["revision"]=2
        with self.assertRaisesRegex(CalendarError,"DIGEST"): validate_calendar(c,"TW")
    def test_missing(self):
        self.assertEqual(build_shadow(packet(),None)["reason_codes"],["CALENDAR_MISSING"])
    def test_outside(self):
        with self.assertRaisesRegex(CalendarError,"OUTSIDE"): session(calendar(),"TW","2027-01-01")
    def test_replay(self): self.assertEqual(calendar(),calendar())
    def test_malformed(self):
        self.assertEqual(build_shadow(packet(),{})["reason_codes"],["CALENDAR_MALFORMED"])
    def test_timezone(self):
        self.assertEqual(session(calendar("US"),"US","2026-03-06")["close_at"][-6:],"-05:00")
        self.assertEqual(session(calendar("US"),"US","2026-03-09")["close_at"][-6:],"-04:00")
    def test_pin(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);c=calendar();(p/"x.json").write_text(json.dumps(c))
            (p/"manifest_v1.json").write_text(json.dumps({"TW":{"file":"x.json","content_hash":"wrong"}}))
            with self.assertRaisesRegex(CalendarError,"PIN"): load_calendar("TW",p)

class IntegrationTests(unittest.TestCase):
    def test_tw_preopen(self): self.assertEqual(packet(window="pre_open_0700")["review_session"],"2026-09-24")
    def test_tw_intraday(self): self.assertEqual(packet(window="intraday_1305")["review_session"],"2026-09-24")
    def test_tw_preclose(self): self.assertEqual(packet(window="pre_close_1335")["review_session"],"2026-09-24")
    def test_tw_postclose(self): self.assertEqual(packet(window="post_close_1500")["review_session"],"2026-09-24")
    def test_us_windows(self):
        for w in ("us_pre_market_2000","us_intraday_2300","us_post_close_review_0630"):
            self.assertEqual(packet("US",window=w)["review_session"],"2026-09-24")
    def test_timezone_boundary(self):
        s=snapshot("US");s["generated_at"]="2026-09-25T06:30:00+08:00"
        self.assertEqual(source_packet(s)["review_session"],"2026-09-24")
    def test_holiday_blocked(self): self.assertEqual(artifact(day="2026-09-28")["status"],"BLOCKED_INPUT")
    def test_incomplete(self):
        p=packet();p["evaluated_at"]="2026-09-24T07:00:00+08:00"
        r=build_shadow(p,calendar())
        self.assertEqual(r["status"],"PENDING");self.assertEqual(r["component_evidence"],{})
    def test_missing_outcome(self):
        r=artifact();self.assertEqual(r["status"],"INSUFFICIENT_SAMPLE")
        for e in r["component_evidence"].values():
            self.assertIsNone(e["user_facing"]["prediction_accuracy_score"]["score"])
    def test_completed_allows_evaluator(self):
        self.assertTrue(artifact()["component_evidence"])
    def test_us_integration(self): self.assertTrue(artifact("US")["component_evidence"])
    def test_no_predecessor(self): self.assertEqual(artifact()["comparison"]["status"],"NO_PREDECESSOR")
    def test_blocked_predecessor(self):
        self.assertEqual(bind_predecessor(artifact(),build_shadow(packet(day="2026-09-23"),None))["comparison"]["status"],"REJECTED")
    def test_digest_reject(self):
        r=artifact();r["status"]="EVALUATED"
        with self.assertRaisesRegex(ValueError,"DIGEST"):validate_shadow(r)
    def test_corrupt_predecessor(self): self.assertEqual(bind_predecessor(artifact(),{})["comparison"]["status"],"REJECTED")
    def test_manual_isolation(self): self.assertFalse(artifact(kind="manual_rerun")["scored_predecessor_eligible"])
    def test_determinism(self): self.assertEqual(artifact(),artifact())
    def test_revision(self): self.assertNotEqual(artifact()["content_hash"],artifact(revision=2)["content_hash"])
    def test_lifecycle(self): self.assertFalse(artifact()["lifecycle_mutation"])
    def test_strategy(self): self.assertFalse(artifact()["strategy_mutation"])
    def test_output_unchanged(self):
        s=snapshot();old=deepcopy(s);build_shadow(source_packet(s),calendar());self.assertEqual(s,old)
    def test_inputs_unchanged(self):
        p=packet();old=deepcopy(p);build_shadow(p,calendar());self.assertEqual(p,old)
    def test_replay(self): self.assertTrue(validate_shadow(artifact()))
    def test_worker_failure_isolated(self):
        with patch("app.dashboard.shadow_evaluation_archive.subprocess.run", side_effect=OSError):
            self.assertIsNone(hook(Path("/synthetic")))
    def test_archive_delivery_failure_isolated(self):
        with tempfile.TemporaryDirectory() as d, patch("app.dashboard.shadow_evaluation_archive.hook",side_effect=RuntimeError) as failing, patch("app.dashboard.window_snapshot_archive.__file__", str(Path(d)/"app/dashboard/window_snapshot_archive.py")):
            s=snapshot()
            r=write_snapshot(Path(d)/"artifacts/archive/window_snapshots",market="TW",window="post_close_1500",effective_trading_date="2026-09-24",
                 generated_at=s["generated_at"],source_payload={"runtime_provenance":"scheduled_production","items":[]},status="completed")
            self.assertTrue(r["written"])
            failing.assert_called_once()
    def test_persistence_reload_idempotency(self):
        with tempfile.TemporaryDirectory() as d:
            s=snapshot();p=Path(d)/"tw"/s["window"]/s["effective_trading_date"]/"revision-0001.json"
            p.parent.mkdir(parents=True);p.write_text(json.dumps(s))
            a=persist(p);b=persist(p)
            self.assertEqual(a["content_hash"],b["content_hash"]);self.assertEqual(b["status"],"IDEMPOTENT")
            self.assertTrue(validate_shadow(json.loads(Path(a["path"]).read_text())))
            self.assertEqual(len(load_admitted_snapshots(Path(d))),1)

class ScoredPredecessorTests(unittest.TestCase):
    def scored(self, day="2026-09-24", kind="scheduled", window=None):
        from test_offline_review_evaluators import improvement_fixtures
        rows, _ = improvement_fixtures()
        p=packet(day=day,kind=kind,window=window)
        p["symbols"]=["SYNTHETIC_TW"]
        p["rows"]=json.loads(json.dumps(rows).replace("synthetic_daily","daily_tactical").replace("2026-09-08","2026-09-07").replace("2026-09-09","2026-09-08"))
        p["evaluated_at"]=day+"T16:59:00+08:00"
        return build_shadow(p,calendar())
    def test_valid_scored_evidence(self):
        r=self.scored();self.assertEqual(r["status"],"EVALUATED")
    def test_valid_predecessor(self):
        prior=self.scored();current=self.scored(day="2026-09-29")
        r=bind_predecessor(current,prior)
        self.assertEqual(r["comparison"]["predecessor_ref"]["content_hash"],prior["content_hash"])
        self.assertTrue(validate_shadow(r))
    def test_other_stream_rejected(self):
        r=bind_predecessor(self.scored(day="2026-09-29",window="intraday_1305"),self.scored())
        self.assertEqual(r["comparison"]["status"],"REJECTED")
    def test_manual_scored_excluded(self):
        self.assertFalse(self.scored(kind="manual_rerun")["scored_predecessor_eligible"])
    def test_component_preserved(self):
        r=self.scored()
        bound=bind_predecessor(r)
        self.assertEqual(r["component_evidence"],bound["component_evidence"])
    def test_aggregate_tamper(self):
        r=self.scored()
        r["component_evidence"]["SYNTHETIC_TW"]["user_facing"]["prediction_accuracy_score"]["score"]=1
        r["content_hash"]=digest({k:v for k,v in r.items() if k!="content_hash"})
        with self.assertRaisesRegex(ValueError,"REPLAY"):validate_shadow(r)
    def test_weights_unchanged(self):
        from app.evaluation.offline_review_evaluators import load_contract
        before=deepcopy(load_contract()["weights_percent"]);self.scored()
        self.assertEqual(before,load_contract()["weights_percent"])

class ResourceTests(unittest.TestCase):
    def test_low_memory_skip(self):
        from app.dashboard.shadow_evaluation_archive import worker_budget
        with patch("resource.setrlimit") as limit:
            self.assertFalse(worker_budget(1024))
            limit.assert_not_called()
    def test_limits_owned_worker_only(self):
        from app.dashboard.shadow_evaluation_archive import worker_budget
        with patch("resource.setrlimit") as limit:
            self.assertTrue(worker_budget(1024*1024))
            self.assertEqual(limit.call_count,2)
