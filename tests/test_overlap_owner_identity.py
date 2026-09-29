"""246 synthetic owner/lifecycle regression: no production calls or browser."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock
from app.runtime import process_guard as pg
from app.runtime.production_run_guard import evaluate_pre_open_run_guard
from app.runtime.timeout_policy import TimeoutPolicy
from app.runtime.decision_card_diagnostics import decision_card_failure_evidence
from app.research.browser_lifecycle import Admission,BrowserUnavailable,MIN_AVAILABLE_BYTES,signal_owned

ROOT=Path("/tmp/fixture-production")
def match(argv,cwd=str(ROOT),ppid=2):
    return pg.production_entrypoint(argv,cwd,ppid,ROOT)

class OwnerTests(unittest.TestCase):
    def test_observer_incident(self):
        code='import time; patterns=("run_stock_analysis.sh","main.py"); time.sleep(1)'
        self.assertIsNone(match(["python3","-u","-B","-c",code]))
    def test_shell_source_not_owner(self):self.assertIsNone(match(["bash","-c","cat run_stock_analysis.sh"]))
    def test_nested_ssh_not_owner(self):self.assertIsNone(match(["ssh","host","python3 -c run_stock_analysis.sh"]))
    def test_grep_not_owner(self):self.assertIsNone(match(["grep","run_stock_analysis.sh","x"]))
    def test_editor_not_owner(self):self.assertIsNone(match(["vim","run_stock_analysis.sh"]))
    def test_browser_worker_not_owner(self):self.assertIsNone(match(["python3","-m","app.research.browser_lifecycle","main.py"]))
    def test_foreign_same_name(self):self.assertIsNone(match(["python3","/tmp/foreign/main.py"],ppid=1))
    def test_foreign_wrapper(self):self.assertIsNone(match(["bash","/tmp/foreign/run_stock_analysis.sh"]))
    def test_relative_foreign_cwd(self):self.assertIsNone(match(["bash","run_stock_analysis.sh"],cwd="/tmp/foreign"))
    def test_missing_cwd(self):self.assertIsNone(match(["bash","run_stock_analysis.sh"],cwd=None))
    def test_argument_mention(self):self.assertIsNone(match(["python3","observer.py","run_stock_analysis.sh"]))
    def test_orphan_main(self):self.assertEqual(match(["python3","main.py"],ppid=1),"main.py")
    def test_nonorphan_main(self):self.assertIsNone(match(["python3","main.py"],ppid=42))
    def test_unknown_parent_main(self):self.assertIsNone(match(["python3","main.py"],ppid=None))
    def test_wrapper_direct(self):self.assertEqual(match([str(ROOT/"run_stock_analysis.sh")]),"run_stock_analysis.sh")
    def test_wrapper_bash(self):self.assertEqual(match(["/bin/bash",str(ROOT/"run_stock_analysis.sh")]),"run_stock_analysis.sh")
    def test_shell_double_dash(self):self.assertEqual(match(["sh","--","run_stock_analysis.sh"]),"run_stock_analysis.sh")
    def test_approved_exact(self):self.assertTrue(match(["python3","scripts/orchestrator/approved_pre_open_delivery.py","--window","pre_open_0700"]))
    def test_approved_equals(self):self.assertTrue(match(["python3","scripts/orchestrator/approved_pre_open_delivery.py","--window=pre_open_0700"]))
    def test_manual_dry_run(self):self.assertIsNone(match(["python3","scripts/orchestrator/approved_pre_open_delivery.py","--window","pre_open_0700","--dry-run"]))
    def test_missing_window(self):self.assertIsNone(match(["python3","scripts/orchestrator/approved_pre_open_delivery.py"]))
    def test_ambiguous_windows(self):self.assertIsNone(match(["python3","scripts/orchestrator/approved_pre_open_delivery.py","--window","pre_open_0700","--window","intraday_1305"]))
    def test_pipeline_approved(self):self.assertTrue(match(["python3","scripts/run_pipeline.py","pre_open","--production-approved"]))
    def test_pipeline_not_approved(self):self.assertIsNone(match(["python3","scripts/run_pipeline.py","pre_open"]))
    def test_pipeline_dry_run(self):self.assertIsNone(match(["python3","scripts/run_pipeline.py","pre_open","--production-approved","--dry-run"]))
    def test_unrelated_window(self):self.assertIsNone(match(["python3","scripts/orchestrator/approved_pre_open_delivery.py","--window","intraday_1305"]))
    def test_python_flags(self):self.assertTrue(match(["python3.10","-B","-u","-W","ignore","scripts/run_pipeline.py","pre_open","--production-approved"]))
    def test_stdin(self):self.assertIsNone(match(["python3","-","run_stock_analysis.sh"]))
    def test_nonpython_script(self):self.assertIsNone(match(["bash","main.py"],ppid=1))
    def test_redacted_diagnostic(self):
        value=match(["python3","scripts/orchestrator/approved_pre_open_delivery.py","--window","pre_open_0700","--sensitive-placeholder","never-print"])
        self.assertNotIn("never-print",value)
    def inspect(self,identities):
        with patch.object(pg,"_identity",side_effect=identities),patch.object(pg,"_argv",return_value=["bash",str(pg.REPO_ROOT/"run_stock_analysis.sh")]),patch.object(pg,"_readlink",return_value=str(pg.REPO_ROOT)),patch.object(pg,"_elapsed_seconds",return_value=12),patch.object(pg,"_ps_field",return_value="1"),patch.object(pg,"_run",return_value=""):
            return pg.inspect_process(99999999,5400)
    def test_stable_identity(self):self.assertTrue(self.inspect([(1,"123","S"),(1,"123","S")]).owner_identity_valid)
    def test_pid_reuse(self):self.assertFalse(self.inspect([(1,"123","S"),(1,"124","S")]).looks_like_pre_open_production)
    def test_exited_owner(self):self.assertFalse(self.inspect([(1,"123","S"),None]).looks_like_pre_open_production)
    def test_zombie_owner(self):self.assertFalse(self.inspect([(1,"123","S"),(1,"123","Z")]).looks_like_pre_open_production)

def row(pid,stale=False):
    return SimpleNamespace(pid=pid,looks_like_pre_open_production=True,stale=stale,to_dict=lambda:{"pid":pid,"stale":stale,"start_ticks":"123"})
class GuardTests(unittest.TestCase):
    def decide(self,rows):
        with patch("app.runtime.production_run_guard.inspect_pre_open_processes",return_value=rows),patch("app.runtime.production_run_guard._ancestor_pids",return_value={50}):
            return evaluate_pre_open_run_guard(TimeoutPolicy(),current_pid=100)
    def test_active_overlap(self):self.assertEqual(self.decide([row(200)]).status,"overlapping_run_blocked")
    def test_completed_owner(self):self.assertTrue(self.decide([]).allowed)
    def test_self_excluded(self):self.assertTrue(self.decide([row(100),row(50)]).allowed)
    def test_long_running_review_not_kill(self):
        d=self.decide([row(200,True)]);self.assertFalse(d.allowed);self.assertFalse(d.auto_kill_performed)
    def test_scheduler_overlap(self):self.assertFalse(self.decide([row(200),row(201)]).allowed)
    def test_deterministic(self):self.assertEqual(self.decide([row(200)]).to_dict(),self.decide([row(200)]).to_dict())
    def test_guard_no_kill(self):
        with patch("os.kill") as kill:
            self.decide([row(200,True)]);kill.assert_not_called()

class LeaseTests(unittest.TestCase):
    def test_release(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/"lease");a=Admission(p,memory=lambda:MIN_AVAILABLE_BYTES).acquire()
            with self.assertRaises(BrowserUnavailable):Admission(p,memory=lambda:MIN_AVAILABLE_BYTES).acquire()
            a.release();b=Admission(p,memory=lambda:MIN_AVAILABLE_BYTES).acquire();b.release()
    def test_stale_metadata_does_not_own_flock(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"lease";p.write_text('{"pid":99999999}')
            a=Admission(str(p),memory=lambda:MIN_AVAILABLE_BYTES).acquire();a.release()
            self.assertTrue(p.exists())
    def test_low_memory(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(BrowserUnavailable,"LOW_MEMORY"):Admission(str(Path(d)/"lease"),memory=lambda:0).acquire()
    def test_unknown_memory(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(BrowserUnavailable,"MEMORY_UNKNOWN"):Admission(str(Path(d)/"lease"),memory=lambda:None).acquire()
    def test_crashed_owner_kernel_release(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/"lease")
            child=subprocess.run([sys.executable,"-c","import fcntl,os,sys; f=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR,0o600); fcntl.flock(f,fcntl.LOCK_EX); os._exit(0)",p],check=True)
            a=Admission(p,memory=lambda:MIN_AVAILABLE_BYTES).acquire();a.release()
    def test_concurrent_acquisition(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/"lease");start=threading.Barrier(3);end=threading.Event();results=[]
            def run():
                start.wait();a=Admission(p,memory=lambda:MIN_AVAILABLE_BYTES)
                try:a.acquire();results.append(True);end.wait(2)
                except BrowserUnavailable:results.append(False)
                finally:a.release()
            ts=[threading.Thread(target=run) for _ in range(2)]
            for t in ts:t.start()
            start.wait()
            deadline=time.monotonic()+2
            while len(results)<2 and time.monotonic()<deadline:time.sleep(.005)
            end.set()
            for t in ts:t.join()
            self.assertEqual(sorted(results),[False,True])
    def test_no_foreign_pid_signal(self):
        with patch("app.research.browser_lifecycle.os.pidfd_open",return_value=9),patch("app.research.browser_lifecycle.os.close"),patch("app.research.browser_lifecycle.process_table",return_value={77:(1,"other","S")}),patch("app.research.browser_lifecycle.signal.pidfd_send_signal") as send:
            self.assertFalse(signal_owned(77,"original",signal.SIGTERM));send.assert_not_called()

class CardDiagnosticsTests(unittest.TestCase):
    def test_exact_reasons(self):
        rows=[{"status":"HISTORICAL_INSUFFICIENT","exclusion_reason":"STALE"}]*10
        d=decision_card_failure_evidence(rows,[],0)
        self.assertEqual(d["historical_exclusion_reasons"],{"STALE":10});self.assertEqual(d["historical_admitted_count"],0)
    def test_analysis_exception(self):self.assertEqual(decision_card_failure_evidence([], [{"reason":"ValueError"}],0)["analysis_failure_reasons"],{"ValueError":1})
    def test_no_payload_logging(self):
        d=decision_card_failure_evidence([{"exclusion_reason":"sensitive text /path"}],[],0)
        self.assertEqual(d["historical_exclusion_reasons"],{"UNSTRUCTURED_REASON":1})
    def test_admission_unchanged(self):
        rows=[{"status":"ADMITTED"},{"status":"HISTORICAL_INSUFFICIENT","exclusion_reason":"STALE"}]
        before=json.dumps(rows);d=decision_card_failure_evidence(rows,[],0)
        self.assertEqual(json.dumps(rows),before);self.assertFalse(d["admission_modified"])
    def test_deterministic(self):self.assertEqual(decision_card_failure_evidence([],[],0),decision_card_failure_evidence([],[],0))
    def test_notification_isolation(self):
        self.assertNotIn("send",json.dumps(decision_card_failure_evidence([],[],0)))
