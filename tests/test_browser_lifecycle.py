"""Offline fault injection: never launch Chrome, pipeline or delivery code."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.research import browser_lifecycle as life
from app.research.cnyes_selenium_browser import (
    CnyesBrowserLifecycle, CnyesBrowserTimeouts, CnyesSeleniumBrowser, _create_local_browser,
)
from app.research.tw_news_aggregation import TwNewsAggregationSession, collect_tw_news


class Driver:
    def __init__(self, failure=None):
        self.failure = failure
        self.quits = 0
        self.service = SimpleNamespace(process=None)

    def set_page_load_timeout(self, seconds):
        self.page_timeout = seconds
        if self.failure == 'configure':
            raise ValueError('configure')

    def set_script_timeout(self, seconds): self.script_timeout = seconds
    def get(self, url):
        if self.failure:
            raise self.failure
    def quit(self):
        self.quits += 1
        if self.failure == 'quit':
            raise RuntimeError('quit')
        if self.failure == 'slow_quit':
            time.sleep(.1)


def selenium_fixture(chrome):
    modules = {name: ModuleType(name) for name in ('selenium', 'selenium.webdriver', 'selenium.webdriver.chrome', 'selenium.webdriver.chrome.options')}
    modules['selenium'].webdriver = modules['selenium.webdriver']
    modules['selenium.webdriver'].Chrome = chrome
    modules['selenium.webdriver.chrome.options'].Options = lambda: SimpleNamespace(add_argument=lambda _: None)
    return patch.dict(sys.modules, modules)


class LifecycleTests(unittest.TestCase):
    def test_success_cleanup_once(self):
        driver = Driver()
        browser = CnyesSeleniumBrowser(driver)
        browser.close(); browser.close()
        self.assertEqual(driver.quits, 1)
        self.assertEqual(browser.lifecycle.sessions_closed, 1)
        self.assertEqual((driver.page_timeout, driver.script_timeout), (12, 5))

    def test_partial_creation_failure_attempts_quit(self):
        calls = []
        class Partial(Driver):
            def __init__(self, **_):
                calls.append('created_child')
                raise ValueError('original')
            def quit(self): calls.append('quit')
        with selenium_fixture(Partial), self.assertRaisesRegex(ValueError, 'original'):
            _create_local_browser(headless=True, timeouts=CnyesBrowserTimeouts(), profile='/unused', lifecycle=CnyesBrowserLifecycle())
        self.assertEqual(calls, ['created_child', 'quit'])

    def test_selenium_internal_quit_not_duplicated(self):
        calls = []
        class Partial(Driver):
            def __init__(self, **_):
                self.quit()
                raise ValueError('original')
            def quit(self): calls.append('quit')
        with selenium_fixture(Partial), self.assertRaises(ValueError):
            _create_local_browser(headless=True, timeouts=CnyesBrowserTimeouts(), profile='/unused', lifecycle=CnyesBrowserLifecycle())
        self.assertEqual(calls, ['quit'])

    def test_setup_exception_cleanup(self):
        driver = Driver('configure')
        with self.assertRaises(ValueError): CnyesSeleniumBrowser(driver)
        self.assertEqual(driver.quits, 1)

    def test_navigation_exception_cleanup(self):
        driver = Driver(ValueError('navigation'))
        with self.assertRaisesRegex(ValueError, 'navigation'):
            with TwNewsAggregationSession(browser_factory=lambda: CnyesSeleniumBrowser(driver)) as session:
                session.get_browser().open_search('fixture')
        self.assertEqual(driver.quits, 1)

    def test_timeout_cleanup(self):
        driver = Driver(TimeoutError('navigation timeout'))
        with self.assertRaises(TimeoutError):
            with TwNewsAggregationSession(browser_factory=lambda: CnyesSeleniumBrowser(driver)) as session:
                session.get_browser().open_article('fixture')
        self.assertEqual(driver.quits, 1)

    def test_parser_exception_cleanup(self):
        driver = Driver()
        with self.assertRaisesRegex(ValueError, 'parser'):
            with TwNewsAggregationSession(browser_factory=lambda: CnyesSeleniumBrowser(driver)) as session:
                session.get_browser()
                raise ValueError('parser')
        self.assertEqual(driver.quits, 1)

    def test_cancellation_cleanup(self):
        for error in (KeyboardInterrupt(), SystemExit()):
            driver = Driver()
            with self.assertRaises(type(error)):
                with TwNewsAggregationSession(browser_factory=lambda: CnyesSeleniumBrowser(driver)) as session:
                    session.get_browser()
                    raise error
            self.assertEqual(driver.quits, 1)

    def test_quit_failure_audited_without_masking_original(self):
        driver = Driver('quit')
        with self.assertLogs('app.research.browser_lifecycle', level='WARNING') as logs:
            with self.assertRaisesRegex(ValueError, 'original'):
                with TwNewsAggregationSession(browser_factory=lambda: CnyesSeleniumBrowser(driver)) as session:
                    session.get_browser()
                    raise ValueError('original')
        self.assertIn('quit_failed', '\n'.join(logs.output))
        self.assertEqual(driver.quits, 1)

    def test_quit_timeout_bounded(self):
        driver = Driver('slow_quit')
        browser = CnyesSeleniumBrowser(driver, timeouts=CnyesBrowserTimeouts(quit_seconds=.01))
        started = time.monotonic()
        self.assertTrue(browser.close().quit_timed_out)
        self.assertLess(time.monotonic()-started, .09)

    def test_external_cleanup_error_preserves_original(self):
        browser = SimpleNamespace(close=Mock(side_effect=RuntimeError('close')))
        with self.assertRaisesRegex(ValueError, 'original'):
            with TwNewsAggregationSession(browser_factory=lambda: browser) as session:
                session.get_browser()
                raise ValueError('original')

    def test_no_duplicate_creation_or_retry(self):
        factory = Mock(side_effect=life.BrowserUnavailable('LOW_MEMORY'))
        session = TwNewsAggregationSession(browser_factory=factory)
        for _ in range(2):
            with self.assertRaisesRegex(life.BrowserUnavailable, 'LOW_MEMORY'): session.get_browser()
        self.assertEqual(factory.call_count, 1)
        session.close()
        with self.assertRaisesRegex(life.BrowserUnavailable, 'SESSION_CLOSED'): session.get_browser()

    def test_thread_creation_serialized(self):
        factory = Mock(return_value=Driver())
        session = TwNewsAggregationSession(browser_factory=factory)
        threads = [threading.Thread(target=session.get_browser) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        session.close()
        self.assertEqual(factory.call_count, 1)

    def test_cross_process_concurrency_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = str(Path(tmp)/'lease')
            admission = life.Admission(lock, memory=lambda: 2**31).acquire()
            code = 'from app.research.browser_lifecycle import Admission; Admission(%r, memory=lambda:2**31).acquire()' % lock
            result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('BROWSER_BUSY', result.stderr)
            admission.release()
            life.Admission(lock, memory=lambda: 2**31).acquire().release()

    def test_low_memory_and_unknown_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            for memory, reason in ((100, 'LOW_MEMORY'), (None, 'MEMORY_UNKNOWN')):
                admission = life.Admission(str(Path(tmp)/'lease'), memory=lambda: memory)
                with self.assertRaisesRegex(life.BrowserUnavailable, reason): admission.acquire()
                self.assertIsNone(admission.fd)

    def test_owned_tree_excludes_other_jobs(self):
        table = {10:(1,'a','S'), 11:(10,'b','S'), 12:(11,'c','S'), 99:(1,'x','S'), 100:(99,'y','S')}
        self.assertEqual(life.owned_processes(10, table), {11:'b', 12:'c'})

    def test_stale_service_pid_cannot_claim_unrelated_tree(self):
        from app.research.cnyes_selenium_browser import _terminate_owned_process_tree
        table = {99:(1,'new','S'), 100:(99,'child','S')}
        with patch.object(life, 'process_table', return_value=table), patch.object(life, 'signal_owned') as kill:
            self.assertEqual(_terminate_owned_process_tree(99, grace_seconds=0), [])
            kill.assert_not_called()

    def test_pid_reuse_is_not_signalled(self):
        with patch.object(os, 'pidfd_open', return_value=123, create=True), patch.object(os, 'close'), patch.object(signal, 'pidfd_send_signal', create=True) as kill, patch.object(life, 'process_table', return_value={10:(1,'new','S')}):
            self.assertFalse(life.signal_owned(10, 'old', signal.SIGKILL))
            kill.assert_not_called()

    def test_signal_bound_to_owned_pidfd(self):
        with patch.object(os, 'pidfd_open', return_value=123, create=True), patch.object(os, 'close'), patch.object(signal, 'pidfd_send_signal', create=True) as kill, patch.object(life, 'process_table', return_value={10:(1,'old','S')}):
            self.assertTrue(life.signal_owned(10, 'old', signal.SIGTERM))
            kill.assert_called_once_with(123, signal.SIGTERM)

    def test_title_only_fallback_does_not_promote_content(self):
        session = TwNewsAggregationSession(browser_factory=Mock(side_effect=life.BrowserUnavailable('LOW_MEMORY')), downstream_fetch_content=False)
        with patch.dict(os.environ, {'STOCK_AI_DISABLE_LIVE_NEWS_NETWORK':'0'}):
            result = collect_tw_news('2330','台積電',reference='2026-09-22',session=session,
                google_fetcher=lambda *_:[{'title':'台積電 2330 營收', 'link':'https://example.com/news','published':'2026-09-22'}])
        self.assertEqual(result['source_health']['CNYES']['reason'], 'LOW_MEMORY')
        self.assertTrue(result['items'])
        self.assertTrue(all(x.get('content_status') != 'FULL_CONTENT' for x in result['items']))

    def test_requests_enrichment_remains_available(self):
        session = TwNewsAggregationSession(browser_factory=Mock(side_effect=life.BrowserUnavailable('BROWSER_BUSY')))
        from app.research.tw_news_content_relevance import ArticleContent
        body = '台積電 2330 營收成長與新產品訂單。' * 12
        with patch.dict(os.environ, {'STOCK_AI_DISABLE_LIVE_NEWS_NETWORK':'0'}), patch('app.research.tw_news_content_relevance.fetch_article_content', return_value=ArticleContent('success', body)) as fetch:
            result = collect_tw_news('2330','台積電',session=session,google_fetcher=lambda *_:[{'title':'台積電營收','link':'https://example.com/news'}])
        fetch.assert_called_once()
        self.assertEqual(result['items'][0]['content'], body)
        self.assertEqual(result['content_relevance_enrichment']['content_success'], 1)

    def test_internally_created_session_closed_on_parser_error(self):
        browser = SimpleNamespace(close=Mock())
        with patch('app.research.tw_news_aggregation._default_cnyes_browser_factory', return_value=browser), patch('app.research.tw_news_aggregation.collect_cnyes_browser_news', side_effect=KeyboardInterrupt()), patch.dict(os.environ, {'STOCK_AI_DISABLE_LIVE_NEWS_NETWORK':'0'}):
            with self.assertRaises(KeyboardInterrupt): collect_tw_news('2330','台積電',google_fetcher=lambda *_:[])
        browser.close.assert_called_once()

    def test_each_resource_cleanup_attempted_without_masking(self):
        browser = life.ManagedBrowser.__new__(life.ManagedBrowser)
        browser._lock = threading.RLock()
        browser._closed = False
        browser._timer = browser._process = None
        browser._end = time.monotonic()+30
        browser.lifecycle = CnyesBrowserLifecycle()
        browser._temp = SimpleNamespace(cleanup=Mock(side_effect=OSError('profile')))
        browser._sock = SimpleNamespace(close=Mock(side_effect=OSError('socket')))
        browser._admission = SimpleNamespace(release=Mock(side_effect=OSError('lock')))
        with self.assertLogs('app.research.browser_lifecycle',level='WARNING') as logs:
            with self.assertRaisesRegex(ValueError, 'original'):
                try: raise ValueError('original')
                finally: browser.close()
        browser._temp.cleanup.assert_called_once()
        browser._sock.close.assert_called_once()
        browser._admission.release.assert_called_once()
        self.assertEqual(len(browser.lifecycle.cleanup_errors), 3)
        self.assertIn('resource_cleanup_failed', '\n'.join(logs.output))

    def test_rpc_page_budget_independent_of_overall(self):
        browser = life.ManagedBrowser.__new__(life.ManagedBrowser)
        browser._lock = threading.RLock()
        browser._closed = False
        browser._sock = object()
        browser.reference = None
        browser._end = time.monotonic()+100
        browser.timeouts = CnyesBrowserTimeouts(page_load_seconds=.01)
        with patch.object(life,'send'), patch.object(life,'receive',return_value={'result':None}) as receive:
            browser.open_article('fixture')
        self.assertAlmostEqual(receive.call_args.args[1], .26)

    def test_ipc_timeout_is_bounded(self):
        a,b = socket.socketpair()
        try:
            with self.assertRaisesRegex(life.BrowserUnavailable,'TIMEOUT'): life.receive(a,.01)
        finally:
            a.close(); b.close()

    def test_ipc_preserves_coalesced_messages(self):
        a,b = socket.socketpair()
        try:
            b.sendall(b'{"result":1}\n{"result":2}\n')
            self.assertEqual(life.receive(a,.1)['result'],1)
            self.assertEqual(life.receive(a,.1)['result'],2)
        finally:
            a.close(); b.close()


@unittest.skipUnless(sys.platform == 'linux', 'Linux subreaper/pidfd integration runs in CI')
class WorkerIntegrationTests(unittest.TestCase):
    def exercise(self, mode):
        real_popen = subprocess.Popen
        fixture = str(Path(__file__).with_name('browser_worker_fixture.py'))
        captured = []
        def launch(args, **kwargs):
            captured.append(args[4])  # owned profile directory
            return real_popen([args[0], fixture, mode, pid_record, *args[3:]], **kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            pid_record = str(Path(tmp)/'pids')
            unrelated = real_popen([sys.executable,'-c','import time; time.sleep(30)'])
            try:
                admission = life.Admission(str(Path(tmp)/'lease'), memory=lambda:2**31)
                timeouts = CnyesBrowserTimeouts(creation_seconds=2, overall_seconds=3, quit_seconds=.1, process_cleanup_grace_seconds=.05)
                with patch.object(life.subprocess,'Popen', side_effect=launch):
                    if mode in ('partial','creation_hang'):
                        with self.assertRaises(life.BrowserUnavailable): life.ManagedBrowser(timeouts=timeouts,admission=admission)
                    else:
                        browser = life.ManagedBrowser(timeouts=timeouts,admission=admission)
                        if mode == 'navigation':
                            with self.assertRaises(life.BrowserUnavailable): browser.open_search('fixture')
                        elif mode == 'overall':
                            with self.assertRaises(life.BrowserUnavailable): browser.open_search('fixture')
                        elif mode == 'parent_eof':
                            browser._sock.close()
                            browser._process.wait(timeout=5)
                        elif mode == 'idle':
                            browser._process.wait(timeout=6)
                        elif mode == 'cancel':
                            with self.assertRaises(KeyboardInterrupt):
                                try: raise KeyboardInterrupt()
                                finally: browser.close()
                        browser.close()
                        if mode != 'parent_eof':
                            self.assertTrue(browser.lifecycle.quit_attempted)
                        self.assertIsNotNone(browser._process.returncode)
                self.assertIsNone(unrelated.poll(), 'another job must survive')
                self.assertTrue(all(not Path(path).exists() for path in captured))
                # Fixture records every detached grandchild PID outside the profile.
                record = Path(pid_record)
                self.assertTrue(record.exists())
                self.assertEqual(Path(pid_record + '.quit').read_text().splitlines(), ['quit'])
                for pid in map(int, record.read_text().splitlines()):
                    with self.assertRaises(ProcessLookupError): os.kill(pid, 0)
                # Releasing/reacquiring the inherited lease proves worker termination.
                life.Admission(str(Path(tmp)/'lease'),memory=lambda:2**31).acquire().release()
            finally:
                unrelated.terminate(); unrelated.wait(timeout=2)

    def test_worker_success_profile_and_no_orphans(self): self.exercise('success')
    def test_worker_partial_failure_profile_and_no_orphans(self): self.exercise('partial')
    def test_worker_constructor_timeout(self): self.exercise('creation_hang')
    def test_worker_navigation_exception(self): self.exercise('navigation')
    def test_worker_overall_timeout(self): self.exercise('overall')
    def test_worker_quit_failure(self): self.exercise('quit')
    def test_worker_keyboard_interrupt(self): self.exercise('cancel')
    def test_worker_parent_eof(self): self.exercise('parent_eof')
    def test_worker_idle_lifetime_expiry(self): self.exercise('idle')
    def test_worker_quit_hang(self): self.exercise('quit_hang')


if __name__ == '__main__': unittest.main()
