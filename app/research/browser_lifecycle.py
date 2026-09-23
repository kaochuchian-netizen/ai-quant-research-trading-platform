"""Bounded, single-owner Selenium worker. No browser dependencies at import time.

Linux production uses a subreaper so even detached Chrome crash handlers remain
owned children. IPC, admission and cleanup contain no article URLs or secrets.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import json
import logging
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import weakref
from typing import Any

LOG = logging.getLogger(__name__)
MIN_AVAILABLE_BYTES = 1024 * 1024 * 1024  # reserve 1 GiB on the 3.8 GiB VM


class BrowserUnavailable(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def audit(event: str, **fields: Any) -> None:
    LOG.warning("browser_lifecycle %s", json.dumps({"event": event, "pid": os.getpid(), "parent_pid": os.getppid(), "time_unix": time.time(), **fields}, sort_keys=True))


def available_memory() -> int | None:
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


class Admission:
    """A stable, per-OS-user lock across batches/worktrees; never unlink it."""
    def __init__(self, path: str | None = None, memory=available_memory):
        self.path = path or f'/tmp/stock-ai-browser-{os.getuid()}.lock'
        self.memory = memory
        self.fd: int | None = None

    def acquire(self) -> 'Admission':
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.release()
            raise BrowserUnavailable('BROWSER_BUSY') from None
        except OSError:
            self.release()
            raise BrowserUnavailable('ADMISSION_UNAVAILABLE') from None
        memory = self.memory()
        if memory is None or memory < MIN_AVAILABLE_BYTES:
            self.release()
            raise BrowserUnavailable('MEMORY_UNKNOWN' if memory is None else 'LOW_MEMORY')
        return self

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)  # inherited worker FD keeps the lease on parent death
            self.fd = None


def process_table() -> dict[int, tuple[int, str, str]]:
    """pid -> (ppid, start ticks, state), never command lines/environment."""
    rows = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            rows[int(path.parent.name)] = (int(fields[1]), fields[19], fields[0])
        except (OSError, ValueError, IndexError):
            continue
    return rows


def owned_processes(root: int, table: dict | None = None) -> dict[int, str]:
    table = process_table() if table is None else table
    owned: dict[int, str] = {}
    parents = {root}
    while True:
        found = {pid for pid, (ppid, _, _) in table.items() if ppid in parents and pid not in parents}
        if not found:
            return owned
        for pid in found:
            owned[pid] = table[pid][1]
        parents.update(found)


def signal_owned(pid: int, birth: str, sig: int) -> bool:
    """Bind signal to a pidfd, then check identity (safe against PID reuse)."""
    fd = None
    try:
        fd = os.pidfd_open(pid)
        row = process_table().get(pid)
        if row is None or row[1] != birth or row[2] == 'Z':
            return False
        signal.pidfd_send_signal(fd, sig)
        return True
    except ProcessLookupError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


def cleanup_children(root: int, grace: float = 0.5) -> list[int]:
    """Subreaper keeps orphan/reparented descendants attributable to this worker."""
    seen = owned_processes(root)
    for pid, birth in seen.items():
        try:
            signal_owned(pid, birth, signal.SIGTERM)
        except OSError as exc:
            audit('child_signal_failed', error=type(exc).__name__, child_pid=pid)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        seen.update(owned_processes(root))
        if not seen:
            break
        time.sleep(0.02)
    # Repeat kill/reap while new descendants can still be adopted or forked.
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        remaining = owned_processes(root)
        seen.update(remaining)
        for pid, birth in remaining.items():
            try:
                signal_owned(pid, birth, signal.SIGKILL)
            except OSError as exc:
                audit('child_signal_failed', error=type(exc).__name__, child_pid=pid)
        try:
            while os.waitpid(-1, os.WNOHANG)[0]:
                pass
        except ChildProcessError:
            break
        if not owned_processes(root):
            break
        time.sleep(0.01)
    remaining = owned_processes(root)
    if remaining:
        audit('cleanup_residue', count=len(remaining))
        raise BrowserUnavailable('CLEANUP_RESIDUE')
    return list(seen)


@contextmanager
def deadline(seconds: float):
    """Worker-only alarm; never touches the production caller's signal handlers."""
    def expire(_signum, _frame):
        raise TimeoutError('BROWSER_STAGE_TIMEOUT')
    old = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, max(0.001, seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def send(sock: socket.socket, value: dict) -> None:
    sock.sendall(json.dumps(value).encode() + b'\n')


_buffers = weakref.WeakKeyDictionary()


def receive(sock: socket.socket, seconds: float) -> dict:
    end = time.monotonic() + seconds
    data = _buffers.pop(sock, b'')
    while True:
        if b'\n' in data:
            line, rest = data.split(b'\n', 1)
            _buffers[sock] = rest
            return json.loads(line)
        if len(data) > 4 * 1024 * 1024:
            raise BrowserUnavailable('BROWSER_RESPONSE_TOO_LARGE')
        remaining = end - time.monotonic()
        if remaining <= 0 or not select.select([sock], [], [], remaining)[0]:
            raise BrowserUnavailable('BROWSER_STAGE_TIMEOUT')
        chunk = sock.recv(65536)
        if not chunk:
            raise BrowserUnavailable('BROWSER_WORKER_EXITED')
        data += chunk


class ManagedBrowser:
    """Only JSON crosses the worker boundary. Lifetime is bounded even when idle."""
    def __init__(self, *, headless=True, timeouts=None, admission=None):
        from app.research.cnyes_selenium_browser import CnyesBrowserTimeouts, CnyesBrowserLifecycle
        self.timeouts = timeouts or CnyesBrowserTimeouts()
        self.lifecycle = CnyesBrowserLifecycle()
        self.reference = None
        self.fallback_reason = None
        self._lock = threading.RLock()
        self._closed = False
        self._process = None
        self._sock = None
        self._temp = None
        self._timer = None
        self._admission = admission or Admission()
        self._end = time.monotonic() + self.timeouts.overall_seconds
        try:
            self._admission.acquire()
            self._temp = tempfile.TemporaryDirectory(prefix='stock-ai-browser-')
            self._sock, child = socket.socketpair()
            self._sock.settimeout(2)
            try:
                self._process = subprocess.Popen(
                    [sys.executable, '-m', 'app.research.browser_lifecycle', str(child.fileno()),
                     self._temp.name, json.dumps(asdict(self.timeouts)), str(int(headless))],
                    pass_fds=(child.fileno(), self._admission.fd), start_new_session=True,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                )
            finally:
                child.close()
            response = receive(self._sock, min(self.timeouts.creation_seconds, self.timeouts.overall_seconds))
            self._check(response)
            self.lifecycle.sessions_created = 1
            self.lifecycle.service_pid = response.get('service_pid')
            self._timer = threading.Timer(max(0.001, self._end-time.monotonic()), self.close)
            self._timer.daemon = True
            self._timer.start()
            audit('ready', worker_pid=self._process.pid, service_pid=self.lifecycle.service_pid)
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _check(response):
        if response.get('error'):
            raise BrowserUnavailable(response['error'])
        return response.get('result')

    def _call(self, method, *args):
        with self._lock:
            if self._closed:
                raise BrowserUnavailable(self.fallback_reason or 'BROWSER_CLOSED')
            try:
                send(self._sock, {'method': method, 'args': args, 'reference': str(self.reference) if self.reference else None})
                budget = {
                    'open_search': self.timeouts.page_load_seconds,
                    'open_article': self.timeouts.page_load_seconds,
                    'wait_results_ready': self.timeouts.results_ready_seconds,
                    'visible_result_cards': self.timeouts.script_seconds,
                    'scroll_for_more': self.timeouts.script_seconds + self.timeouts.scroll_growth_seconds,
                    'article_body': self.timeouts.article_body_seconds + self.timeouts.script_seconds,
                }[method]
                remaining = min(budget + 0.25, self._end-time.monotonic())
                return self._check(receive(self._sock, max(0.001, remaining)))
            except BaseException as exc:
                self.fallback_reason = getattr(exc, "reason", type(exc).__name__)
                self.close()
                raise

    def open_search(self, url): return self._call('open_search', url)
    def wait_results_ready(self): return self._call('wait_results_ready')
    def visible_result_cards(self): return self._call('visible_result_cards')
    def scroll_for_more(self, count): return self._call('scroll_for_more', count)
    def open_article(self, url): return self._call('open_article', url)
    def article_body(self): return self._call('article_body')

    def close(self):
        with self._lock:
            if self._closed:
                return self.lifecycle
            self._closed = True
            if time.monotonic() >= self._end:
                self.fallback_reason = "BROWSER_STAGE_TIMEOUT"
            if self._timer:
                self._timer.cancel()
            try:
                if self._process:
                    # SIGTERM interrupts both constructor and navigation; worker finally
                    # attempts quit exactly once before bounded descendant cleanup.
                    if self._process.poll() is None:
                        self._process.terminate()
                    try:
                        close_end = time.monotonic() + self.timeouts.quit_seconds + self.timeouts.process_cleanup_grace_seconds + 3
                        response = receive(self._sock, close_end-time.monotonic())
                        while 'closed' not in response:
                            response = receive(self._sock, max(0.001, close_end-time.monotonic()))
                        for key, value in response['closed'].items():
                            if hasattr(self.lifecycle, key):
                                setattr(self.lifecycle, key, value)
                        self._process.wait(timeout=2)
                    except Exception as exc:
                        self.lifecycle.quit_timed_out = True
                        audit('worker_cleanup_failed', error=type(exc).__name__, worker_pid=self._process.pid)
                        # This dedicated session was created by this Popen; leader is
                        # still our unreaped child. No global process-name matching.
                        if self._process.poll() is None:
                            # Descendants may have created a separate session. Bind
                            # their identities before killing the worker/group.
                            for pid, birth in owned_processes(self._process.pid).items():
                                try:
                                    signal_owned(pid, birth, signal.SIGKILL)
                                except OSError as kill_error:
                                    audit('forced_cleanup_failed', error=type(kill_error).__name__)
                            os.killpg(self._process.pid, signal.SIGKILL)
                            self._process.wait(timeout=2)
            except BaseException as exc:
                audit('cleanup_failed', error=type(exc).__name__)
            finally:
                for resource, cleanup in (
                    ('profile', self._temp.cleanup if self._temp else None),
                    ('ipc', self._sock.close if self._sock else None),
                    ('admission', self._admission.release),
                ):
                    if cleanup:
                        try:
                            cleanup()
                        except BaseException as exc:
                            self.lifecycle.cleanup_errors.append(type(exc).__name__)
                            audit('resource_cleanup_failed', resource=resource, error=type(exc).__name__)
                audit('closed', **asdict(self.lifecycle))
            return self.lifecycle


def worker(sock: socket.socket, profile: str, timeouts, headless: bool) -> None:
    import ctypes
    from app.research.cnyes_selenium_browser import _create_local_browser, CnyesBrowserLifecycle
    lifecycle = CnyesBrowserLifecycle()
    # Fail closed on platforms without safe ownership/signalling primitives.
    if not hasattr(os, 'pidfd_open') or ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        send(sock, {'error': 'OWNERSHIP_UNAVAILABLE'})
        return
    def cancel(_signum, _frame):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, cancel)
    os.environ['TMPDIR'] = profile
    tempfile.tempdir = profile
    sock.settimeout(2)
    browser = None
    try:
        with deadline(timeouts.overall_seconds):
            browser = _create_local_browser(headless=headless, timeouts=timeouts, profile=profile, lifecycle=lifecycle)
            send(sock, {'result': 'ready', 'service_pid': lifecycle.service_pid})
            methods = {'open_search', 'wait_results_ready', 'visible_result_cards', 'scroll_for_more', 'open_article', 'article_body'}
            while True:
                request = receive(sock, timeouts.overall_seconds)
                method = request.get('method')
                if method not in methods:
                    raise BrowserUnavailable('INVALID_BROWSER_OPERATION')
                browser.reference = request.get('reference')
                audit('operation_started', operation=method, service_pid=lifecycle.service_pid)
                result = getattr(browser, method)(*request.get('args', []))
                audit('operation_completed', operation=method, service_pid=lifecycle.service_pid)
                send(sock, {'result': result})
    except BaseException as exc:
        try:
            send(sock, {'error': getattr(exc, 'reason', 'BROWSER_STAGE_TIMEOUT' if isinstance(exc, TimeoutError) else type(exc).__name__)})
        except OSError:
            pass
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if browser:
            try:
                browser.close()
            except BaseException as exc:
                lifecycle.cleanup_errors.append(type(exc).__name__)
                audit('adapter_cleanup_failed', error=type(exc).__name__)
        try:
            lifecycle.cleanup_attempted = True
            lifecycle.cleanup_pids = cleanup_children(os.getpid(), timeouts.process_cleanup_grace_seconds)
        except BaseException as exc:
            lifecycle.cleanup_errors.append(type(exc).__name__)
            audit('owned_cleanup_failed', error=type(exc).__name__)
        try:
            shutil.rmtree(profile)
        except OSError as exc:
            audit('profile_cleanup_failed', error=type(exc).__name__)
        try:
            send(sock, {'closed': asdict(lifecycle)})
        except OSError:
            pass
        sock.close()


if __name__ == '__main__':
    from app.research.cnyes_selenium_browser import CnyesBrowserTimeouts
    worker(socket.socket(fileno=int(sys.argv[1])), sys.argv[2], CnyesBrowserTimeouts(**json.loads(sys.argv[3])), bool(int(sys.argv[4])))
