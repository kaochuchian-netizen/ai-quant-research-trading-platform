"""Isolated boundary tests: no analysis, providers, production paths or senders."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from app.runtime.delivery_supervisor import supervise
from app.reports.channel_delivery_receipt import deliver_once, delivery_identity, receipt_path
from app.us_stock.batch_reliability import contract_for_window, build_failure_status

class DeliveryRecoveryTests(unittest.TestCase):
    def test_worker_result_identity_and_stale_rejection(self):
        for stale in (False, True):
            with self.subTest(stale=stale), tempfile.TemporaryDirectory() as tmp:
                script = ('import os,json,sys; from pathlib import Path; '
                    'Path(sys.argv[-1]).write_text(json.dumps({"ok":True,"run_id":'
                    + ('"old-run"' if stale else 'os.environ["STOCK_AI_DELIVERY_RUN_ID"]') + '}))')
                result = supervise([sys.executable,'-c',script],cwd=Path(tmp),market='TW',window='pre_open_0700',timeout_seconds=3,evidence_root=Path(tmp))
                self.assertEqual(result['ok'],not stale)
                self.assertEqual(result['worker']['result_identity_verified'],not stale)

    def test_whole_worker_timeout_preserves_stage_and_termination(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = ('import os,json,time; from pathlib import Path; '
                'Path(os.environ["STOCK_AI_MANUAL_RERUN_PROGRESS_LOG"]).write_text(json.dumps({"stage":"archive_publish","status":"started","at":"2026-11-06T07:00:00+08:00"})+"\\n"); time.sleep(30)')
            result = supervise([sys.executable,'-c',script],cwd=Path(tmp),market='US',window='us_post_close_review_0630',timeout_seconds=.3,evidence_root=Path(tmp))
            self.assertFalse(result['ok'])
            self.assertEqual(result['worker']['terminal_status'],'timed_out')
            self.assertEqual(result['worker']['stage_timings']['archive_publish']['status'],'timed_out')
            self.assertTrue(result['worker']['termination'])

    def identity(self, content='frozen'):
        return delivery_identity(snapshot={'market':'TW','window':'pre_open_0700','effective_trading_date':'2026-11-06','snapshot_id':'test','revision':1,'payload':{}},channel='email',market='TW',window='pre_open_0700',content=content)

    def test_claim_blocks_concurrent_and_changed_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); identity=self.identity(); nested=[]
            def sender():
                nested.append(deliver_once(receipt_root=root,identity=identity,channel='email',sender=lambda:self.fail('duplicate transport')))
                return {'recipients':[{'recipient':'test@example.invalid','status':'accepted'}]}
            first=deliver_once(receipt_root=root,identity=identity,channel='email',sender=sender)
            self.assertTrue(first['send_attempted'])
            self.assertFalse(nested[0]['send_attempted'])
            for identity in (identity,self.identity('changed')):
                self.assertFalse(deliver_once(receipt_root=root,identity=identity,channel='email',sender=lambda:self.fail('duplicate'))['send_attempted'])

    def test_invalid_recipient_count_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); identity=self.identity()
            result=deliver_once(receipt_root=root,identity=identity,channel='email',sender=lambda:{'recipients':[{'recipient':'a','status':'accepted'}]})
            receipt=result['receipt'];receipt['accepted_recipient_count']=0
            receipt_path(root,identity).write_text(json.dumps(receipt))
            retained=deliver_once(receipt_root=root,identity=identity,channel='email',sender=lambda:self.fail('duplicate'))
            self.assertEqual(retained['error_type'],'InvalidDeliveryReceipt')

    def test_failure_policy_and_run_identity(self):
        now=datetime.fromisoformat('2026-11-06T06:30:00+08:00')
        for window in ('us_pre_market_2000','us_intraday_2300','us_post_close_review_0630'):
            self.assertTrue(contract_for_window(window).channel_policy.line_allowed)
            failure=build_failure_status(window=window,started_at=now,finished_at=now,reason='worker_timeout',run_id='shared-run')
            self.assertEqual(failure['run_id'],'shared-run')
            self.assertEqual(failure['line']['reason'],'worker_timeout_line_not_attempted')

if __name__=='__main__': unittest.main()
