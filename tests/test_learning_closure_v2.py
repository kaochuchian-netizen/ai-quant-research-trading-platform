import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from capture_context_support import scheduled
from app.runtime.capture_context import decision, CONTEXT_ENV, RUN_ENV, reject_inherited_context
from app.evaluation.daily_evaluation import build_daily, replay, predecessor_proof
from app.evaluation.daily_evaluation_v2 import build, coverage
from app.evaluation.daily_learning import latest, validate, validate_reference
from app.evaluation.us_session_direction import predict_v2, replay_prediction, capture_safely, capture_existing, STREAM
from app.dashboard.production_evidence_archive import publish, project
from app.dashboard.daily_learning_presentation import render_dashboard
from app.evaluation.prediction_regression_contract import stamp
from test_daily_evaluation import packet, mature_inputs
from test_us_session_direction import obs, report, receipt, load_calendar, History


class ContextTests(unittest.TestCase):
    def decision(self, **kwargs):
        return decision(market='US', window=STREAM, session_date='2026-09-24', **kwargs)

    def test_scheduled_progress_allowed(self):
        with scheduled(), patch.dict(os.environ, {'STOCK_AI_MANUAL_RERUN_PROGRESS_LOG':'fixture'}):
            self.assertEqual(self.decision(), 'CAPTURE_ALLOWED')

    def test_unknown_context(self):
        self.assertNotEqual(self.decision(environment={}), 'CAPTURE_ALLOWED')

    def test_manual_and_dry_run_cannot_inherit(self):
        for mode in ('manual', 'dry_run'):
            with scheduled():
                reject_inherited_context(**{mode:True})
                self.assertNotEqual(self.decision(), 'CAPTURE_ALLOWED')

    def test_dry_run_flag_denied(self):
        with scheduled():
            self.assertEqual(self.decision(dry_run=True), 'CAPTURE_DRY_RUN')

    def test_conflicts_expiry_unknown_schema(self):
        for key,value in [('run_id','other'),('market','TW'),('window','wrong'),
                          ('session_date','2026-09-23'),('mode','unknown'),
                          ('schema_version','unknown'),('issued_at','2026-09-23T08:00:00-04:00')]:
            with self.subTest(key=key), scheduled() as context:
                context[key]=value
                with patch.dict(os.environ,{CONTEXT_ENV:json.dumps(context)}):
                    self.assertNotEqual(self.decision(),'CAPTURE_ALLOWED')

    def test_direct_frozen_write_denied(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=True):
            p=Path(d)/'us/us_pre_market_2000/2026-09-24/.frozen/test.json'
            with self.assertRaises(ValueError):publish(p,{})
            self.assertFalse(p.exists())

    def test_immutable_conflict(self):
        with tempfile.TemporaryDirectory() as d, scheduled():
            p=Path(d)/'us/us_pre_market_2000/2026-09-24/.frozen/test.json'
            publish(p,{'a':1});before=p.read_bytes()
            with self.assertRaises(ValueError):publish(p,{'a':2})
            self.assertEqual(before,p.read_bytes())

    def test_safe_failure_reasons(self):
        for target,value,reason in [
                ('threading.current_thread',SimpleNamespace(name='fixture-worker'),'CAPTURE_NOT_MAIN_THREAD'),
                ('signal.getitimer',(1,0),'CAPTURE_OUTER_ALARM_ACTIVE')]:
            with scheduled(), patch('app.evaluation.us_session_direction.'+target,return_value=value), patch('app.evaluation.us_session_direction.capture_existing') as capture:
                r=capture_safely('TEST',{},None,'2026-09-24',STREAM,enabled=True)
                self.assertEqual(r['reason'],reason);capture.assert_not_called()
        with scheduled(), patch('app.evaluation.us_session_direction.capture_existing',side_effect=TimeoutError):
            self.assertEqual(capture_safely('TEST',{},None,'2026-09-24',STREAM,enabled=True)['reason'],'CAPTURE_TIMEOUT')


class CompatibilityTests(unittest.TestCase):
    def test_v1_v2_and_cross_version_predecessor(self):
        old=build_daily('2026-09-25',packet());before=deepcopy(old)
        new=build('2026-09-26',packet(),predecessor_proof(old))
        self.assertEqual(replay(old),before);self.assertEqual(replay(new),new)
        self.assertEqual(new['comparison']['status'],'BOUND')
        next_value=build('2026-09-27',packet(),predecessor_proof(new))
        self.assertEqual(replay(next_value),next_value)
        self.assertEqual(validate(new['learning_artifact']),new['learning_artifact'])

    def test_zero_waiting_partial(self):
        empty={m:{'calendar':load_calendar(m),'records':[],'outcomes':[]} for m in ('TW','US')}
        for inputs,state in [(empty,'NO_ELIGIBLE_PREDICTION'),(packet(),'WAITING_OUTCOME'),(mature_inputs(),'INSUFFICIENT_SAMPLE')]:
            value=build('2026-09-25',inputs)
            for m in ('TW','US'):
                self.assertEqual(value['markets'][m]['coverage_summary']['state'],state)
                self.assertNotEqual(value['learning_artifact']['markets'][m]['finding'],'EVIDENCE_CHAIN_OBSERVED')
            self.assertIn('合格預測',render_dashboard(value))

    def test_blocked_and_mature(self):
        inputs=packet();inputs['US']['prerequisite_error']='fixture'
        self.assertEqual(build('2026-09-25',inputs)['markets']['US']['coverage_summary']['state'],'BLOCKED_INPUT')
        market={'status':'VALID','stocks':{'TEST':{'sample_reviews':{'s':{'assessment':{'eligible':True}}},
            'direction_component':{'windows':{'3':{'sample_size':3},'10':{'sample_size':10}}}}}}
        self.assertEqual(coverage(market,{'records':[]})['state'],'EVALUATED')

    def test_unknown_versions_fail_closed(self):
        value=build_daily('2026-09-25',packet());value['schema_version']='unknown';value=stamp(value)
        with self.assertRaises(ValueError):replay(value)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'artifacts/archive/window_snapshots/.daily_evaluation/2026-09-25/x.json'
            p.parent.mkdir(parents=True);p.write_text(json.dumps(value))
            with self.assertRaises(ValueError):latest(d,'US','2026-09-28','2026-09-28T08:00:00-04:00')

    def test_us_pinned_learning_replay(self):
        with tempfile.TemporaryDirectory() as d:
            value=build_daily('2026-09-23',{m:{'calendar':load_calendar(m),'records':[],'outcomes':[]} for m in ('TW','US')})
            p=Path(d)/'artifacts/archive/window_snapshots/.daily_evaluation/2026-09-23/x.json'
            p.parent.mkdir(parents=True);p.write_text(json.dumps(value))
            reference=latest(d,'US','2026-09-24','2026-09-24T08:01:00-04:00')
        result=predict_v2(obs(),load_calendar('US'),frozen_at='2026-09-24T08:01:00-04:00',learning_reference=reference)
        self.assertEqual(replay_prediction(result),result)
        self.assertEqual(project(report(),{'TEST':receipt(result)})['records'][0]['direction_sample_count'],1)
        result['learning_reference']['actionable_learning']['active']=True
        with self.assertRaises(ValueError):replay_prediction(stamp(result))

    def test_v2_latest_and_v1_rollback_reader(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)/'artifacts/archive/window_snapshots'
            for namespace,value in [('.daily_evaluation',build_daily('2026-09-25',packet())),
                                    ('.daily_evaluation_v2',build('2026-09-25',packet()))]:
                p=base/namespace/'2026-09-25/x.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(value))
            ref=latest(d,'US','2026-09-28','2026-09-28T08:00:00-04:00')
            self.assertEqual(ref['learning_payload']['schema_version'],'daily_learning_application_v2')
            validate_reference(ref,market='US',frozen_at='2026-09-28T08:00:00-04:00')


class WriterSafetyTests(unittest.TestCase):
    def test_v1_rollback_cannot_fork_v2_chain(self):
        from app.dashboard.daily_evaluation_archive import persist_daily
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'.daily_evaluation_v2/2026-09-25/x.json'
            p.parent.mkdir(parents=True);p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'V1_WRITER_AFTER_V2_DENIED'):
                persist_daily(d,'2026-09-26')

    def test_governance_checks_v2_replay_and_path(self):
        from scripts.orchestrator.validate_post_merge_status import is_preserved_runtime_artifact
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);v=build('2026-09-25',packet())
            p=root/'artifacts/archive/window_snapshots/.daily_evaluation_v2/2026-09-25'/(v['identity']+'.json')
            p.parent.mkdir(parents=True);p.write_text(json.dumps(v))
            self.assertTrue(is_preserved_runtime_artifact(str(p.relative_to(root)),repo_root=root))
            p.write_text('{}')
            self.assertFalse(is_preserved_runtime_artifact(str(p.relative_to(root)),repo_root=root))

    def test_shadow_never_publishes_or_sends(self):
        from scripts.orchestrator import approved_daily_evaluation as entry
        v=build_daily('2026-09-25',packet())
        with tempfile.TemporaryDirectory() as d, patch.object(entry,'persist_daily',return_value=(Path(d)/'v.json',v)) as persist, \
                patch.object(entry,'publish_dashboard') as dashboard, patch.object(entry,'publish_daily_evaluation_landing') as landing, \
                patch.object(entry,'deliver_line_notice') as send:
            self.assertEqual(entry.main(['--report-date','2026-09-25','--shadow-output',d]),0)
            dashboard.assert_not_called();landing.assert_not_called();send.assert_not_called()
            self.assertEqual(persist.call_args.kwargs['version'],'daily_evaluation_integration_v2')
