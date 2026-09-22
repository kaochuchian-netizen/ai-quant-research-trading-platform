"""Lazy Selenium adapter for CNYES collection."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import signal
import threading
import time
from typing import Any

from app.research.tw_news_content_relevance import cnyes_search_result_from_dom, normalize_text


@dataclass(frozen=True)
class CnyesBrowserTimeouts:
    creation_seconds: float = 25.0
    overall_seconds: float = 180.0
    page_load_seconds: float = 12.0
    script_seconds: float = 5.0
    results_ready_seconds: float = 10.0
    scroll_growth_seconds: float = 6.0
    article_body_seconds: float = 15.0
    quit_seconds: float = 5.0
    process_cleanup_grace_seconds: float = 2.0


@dataclass
class CnyesBrowserLifecycle:
    sessions_created: int = 0
    sessions_closed: int = 0
    quit_timed_out: bool = False
    cleanup_attempted: bool = False
    cleanup_pids: list[int] = field(default_factory=list)
    service_pid: int | None = None
    quit_attempted: bool = False
    cleanup_errors: list[str] = field(default_factory=list)


class CnyesBrowserTimeoutError(TimeoutError):
    def __init__(self, stage: str, timeout_seconds: float, message: str | None = None) -> None:
        self.stage = stage
        self.timeout_seconds = timeout_seconds
        super().__init__(message or f"{stage} timed out after {timeout_seconds:.1f}s")


def _driver_service_pid(driver: Any) -> int | None:
    service = getattr(driver, "service", None)
    process = getattr(service, "process", None)
    pid = getattr(process, "pid", None)
    try:
        return int(pid) if pid else None
    except (TypeError, ValueError):
        return None


def _terminate_owned_process_tree(root_pid: int, *, grace_seconds: float) -> list[int]:
    """Identity-bound cleanup; managed workers additionally reap detached children."""
    from app.research.browser_lifecycle import owned_processes, process_table, signal_owned
    table = process_table()
    # A stale service PID must never acquire ownership of an unrelated process.
    if root_pid not in owned_processes(os.getpid(), table):
        return []
    owned = owned_processes(root_pid, table)
    if root_pid in table:
        owned[root_pid] = table[root_pid][1]
    for pid, birth in owned.items():
        signal_owned(pid, birth, signal.SIGTERM)
    if owned:
        time.sleep(max(0, grace_seconds))
    for pid, birth in owned.items():
        signal_owned(pid, birth, signal.SIGKILL)
    return list(owned)


class CnyesSeleniumBrowser:
    def __init__(
        self,
        driver: Any,
        *,
        reference: Any | None = None,
        timeouts: CnyesBrowserTimeouts | None = None,
        lifecycle: CnyesBrowserLifecycle | None = None,
    ) -> None:
        self._closed = False
        self.driver = driver
        self.reference = reference
        self.timeouts = timeouts or CnyesBrowserTimeouts()
        self.lifecycle = lifecycle or CnyesBrowserLifecycle()
        self.lifecycle.sessions_created += 1
        self.lifecycle.service_pid = _driver_service_pid(driver)
        self._last_count = 0
        try:
            self._configure_driver_timeouts()
        except BaseException:
            self.close()
            raise

    def _configure_driver_timeouts(self) -> None:
        page = getattr(self.driver, "set_page_load_timeout", None)
        script = getattr(self.driver, "set_script_timeout", None)
        if callable(page):
            page(self.timeouts.page_load_seconds)
        if callable(script):
            script(self.timeouts.script_seconds)

    def open_search(self, url: str) -> None:
        try:
            self.driver.get(url)
        except Exception as exc:
            if "timeout" in f"{exc.__class__.__name__}: {exc}".lower():
                raise CnyesBrowserTimeoutError("CNYES_SEARCH", self.timeouts.page_load_seconds) from exc
            raise

    def wait_results_ready(self) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        try:
            WebDriverWait(self.driver, self.timeouts.results_ready_seconds).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, 'a[href*="news.cnyes.com/news/id/"]')) > 0)
        except Exception as exc:
            if "timeout" in f"{exc.__class__.__name__}: {exc}".lower():
                raise CnyesBrowserTimeoutError("CNYES_RESULTS_READY", self.timeouts.results_ready_seconds) from exc
            raise

    def _cards(self) -> list[dict[str, Any]]:
        script = r'''
        const anchors = Array.from(document.querySelectorAll('a[href*="news.cnyes.com/news/id/"]'));
        return anchors.map((a) => {
          const container = a.closest('article, section, div') || a;
          const timeNode = container.querySelector('time,[datetime]');
          return {
            href: a.href || a.getAttribute('href') || '',
            text: (container.innerText || a.innerText || '').trim(),
            datetime_attr: timeNode ? (timeNode.getAttribute('datetime') || timeNode.textContent || '') : ''
          };
        });
        '''
        try:
            rows = self.driver.execute_script(script) or []
        except Exception as exc:
            if "timeout" in f"{exc.__class__.__name__}: {exc}".lower():
                raise CnyesBrowserTimeoutError("CNYES_DOM_SCRIPT", self.timeouts.script_seconds) from exc
            raise
        cards: list[dict[str, Any]] = []
        for row in rows:
            href = row.get('href') if isinstance(row, dict) else ''
            if not href:
                continue
            cards.append(cnyes_search_result_from_dom(href=href, text=row.get('text', ''), datetime_attr=row.get('datetime_attr'), reference=self.reference))
        self._last_count = len(cards)
        return cards

    def visible_result_cards(self) -> list[dict[str, Any]]:
        return self._cards()

    def scroll_for_more(self, current_count: int) -> list[dict[str, Any]]:
        from selenium.webdriver.support.ui import WebDriverWait
        before = max(current_count, self._last_count)
        try:
            self.driver.execute_script('window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));')
        except Exception as exc:
            if "timeout" in f"{exc.__class__.__name__}: {exc}".lower():
                raise CnyesBrowserTimeoutError("CNYES_SCROLL_SCRIPT", self.timeouts.script_seconds) from exc
            raise
        try:
            WebDriverWait(self.driver, self.timeouts.scroll_growth_seconds).until(lambda _d: len(self._cards()) > before)
        except Exception as exc:
            if "timeout" in f"{exc.__class__.__name__}: {exc}".lower():
                raise CnyesBrowserTimeoutError("CNYES_SCROLL_GROWTH", self.timeouts.scroll_growth_seconds) from exc
            return []
        cards = self._cards()
        return cards[before:]

    def open_article(self, url: str) -> None:
        try:
            self.driver.get(url)
        except Exception as exc:
            if "timeout" in f"{exc.__class__.__name__}: {exc}".lower():
                raise CnyesBrowserTimeoutError("CNYES_ARTICLE_NAVIGATION", self.timeouts.page_load_seconds) from exc
            raise

    def article_body(self) -> str:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        try:
            WebDriverWait(self.driver, self.timeouts.article_body_seconds).until(lambda d: len(normalize_text(d.find_element(By.TAG_NAME, 'body').text)) > 80)
        except Exception as exc:
            if "timeout" in f"{exc.__class__.__name__}: {exc}".lower():
                raise CnyesBrowserTimeoutError("CNYES_ARTICLE_BODY", self.timeouts.article_body_seconds) from exc
            raise
        return normalize_text(self.driver.find_element(By.TAG_NAME, 'body').text)

    def close(self) -> CnyesBrowserLifecycle:
        if self._closed:
            return self.lifecycle
        self._closed = True
        error: list[BaseException] = []

        def _quit() -> None:
            try:
                self.lifecycle.quit_attempted = True
                self.driver.quit()
            except BaseException as exc:
                error.append(exc)

        thread = threading.Thread(target=_quit, name="cnyes-selenium-quit", daemon=True)
        thread.start()
        thread.join(self.timeouts.quit_seconds)
        self.lifecycle.quit_timed_out = thread.is_alive()
        if error or thread.is_alive():
            from app.research.browser_lifecycle import audit
            self.lifecycle.cleanup_errors.extend(type(exc).__name__ for exc in error)
            audit("quit_failed", timed_out=thread.is_alive(), errors=self.lifecycle.cleanup_errors)
            root_pid = self.lifecycle.service_pid or _driver_service_pid(self.driver)
            if root_pid:
                self.lifecycle.cleanup_attempted = True
                try:
                    self.lifecycle.cleanup_pids = _terminate_owned_process_tree(
                        root_pid, grace_seconds=self.timeouts.process_cleanup_grace_seconds,
                    )
                except BaseException as exc:
                    self.lifecycle.cleanup_errors.append(type(exc).__name__)
                    audit("tree_cleanup_failed", error=type(exc).__name__)
        else:
            self.lifecycle.sessions_closed += 1
        return self.lifecycle


def create_cnyes_selenium_browser(
    *, headless: bool = True, timeouts: CnyesBrowserTimeouts | None = None,
):
    from app.research.browser_lifecycle import ManagedBrowser
    return ManagedBrowser(headless=headless, timeouts=timeouts)


def _create_local_browser(*, headless, timeouts, profile, lifecycle):
    """Worker only: retain an object even if Selenium __init__ fails halfway."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    class OnceChrome(webdriver.Chrome):
        _quit_once = False

        def quit(self):
            if self._quit_once:
                return
            self._quit_once = True
            lifecycle.quit_attempted = True
            return super().quit()

    options = Options()
    if headless:
        options.add_argument('--headless=new')
    options.page_load_strategy = 'eager'
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1280,1800')
    options.add_argument('--user-data-dir=' + profile + '/profile')
    options.add_argument('--disable-breakpad')
    driver = OnceChrome.__new__(OnceChrome)
    try:
        driver.__init__(options=options)
        return CnyesSeleniumBrowser(driver, timeouts=timeouts, lifecycle=lifecycle)
    except BaseException:
        # Constructor/setup exceptions must retain their original identity.
        wrapper = CnyesSeleniumBrowser.__new__(CnyesSeleniumBrowser)
        wrapper.driver, wrapper.timeouts, wrapper.lifecycle = driver, timeouts, lifecycle
        wrapper._closed = False
        try:
            wrapper.close()
        except BaseException as cleanup_error:
            from app.research.browser_lifecycle import audit
            audit("partial_cleanup_failed", error=type(cleanup_error).__name__)
        raise
