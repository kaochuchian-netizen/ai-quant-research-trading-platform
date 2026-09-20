"""Lazy Selenium adapter for CNYES collection."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import signal
import subprocess
import threading
import time
from typing import Any

from app.research.tw_news_content_relevance import cnyes_search_result_from_dom, normalize_text


@dataclass(frozen=True)
class CnyesBrowserTimeouts:
    page_load_seconds: float = 12.0
    script_seconds: float = 5.0
    results_ready_seconds: float = 10.0
    scroll_growth_seconds: float = 6.0
    article_body_seconds: float = 10.0
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


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _descendant_pids(root_pid: int) -> list[int]:
    try:
        output = subprocess.check_output(["ps", "-eo", "pid=,ppid="], text=True, timeout=2)
    except Exception:
        return []
    children: dict[int, list[int]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        children.setdefault(ppid, []).append(pid)
    result: list[int] = []
    stack = list(children.get(root_pid, []))
    while stack:
        pid = stack.pop()
        if pid in result:
            continue
        result.append(pid)
        stack.extend(children.get(pid, []))
    return result


def _terminate_owned_process_tree(root_pid: int, *, grace_seconds: float) -> list[int]:
    """Terminate only the WebDriver-owned process tree rooted at ``root_pid``."""
    pids = [pid for pid in _descendant_pids(root_pid) + [root_pid] if pid > 1 and _process_exists(pid)]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.monotonic() + max(0.1, grace_seconds)
    while time.monotonic() < deadline and any(_process_exists(pid) for pid in pids):
        time.sleep(0.05)
    for pid in pids:
        if _process_exists(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    return pids


class CnyesSeleniumBrowser:
    def __init__(
        self,
        driver: Any,
        *,
        reference: Any | None = None,
        timeouts: CnyesBrowserTimeouts | None = None,
        lifecycle: CnyesBrowserLifecycle | None = None,
    ) -> None:
        self.driver = driver
        self.reference = reference
        self.timeouts = timeouts or CnyesBrowserTimeouts()
        self.lifecycle = lifecycle or CnyesBrowserLifecycle()
        self.lifecycle.sessions_created += 1
        self.lifecycle.service_pid = _driver_service_pid(driver)
        self._last_count = 0
        self._configure_driver_timeouts()

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
        error: list[BaseException] = []

        def _quit() -> None:
            try:
                self.driver.quit()
            except BaseException as exc:  # pragma: no cover - preserved for lifecycle evidence
                error.append(exc)

        thread = threading.Thread(target=_quit, name="cnyes-selenium-quit", daemon=True)
        thread.start()
        thread.join(self.timeouts.quit_seconds)
        if thread.is_alive():
            self.lifecycle.quit_timed_out = True
            root_pid = self.lifecycle.service_pid or _driver_service_pid(self.driver)
            if root_pid:
                self.lifecycle.cleanup_attempted = True
                self.lifecycle.cleanup_pids = _terminate_owned_process_tree(
                    root_pid,
                    grace_seconds=self.timeouts.process_cleanup_grace_seconds,
                )
        else:
            self.lifecycle.sessions_closed += 1
        if error:
            raise error[0]
        return self.lifecycle


def create_cnyes_selenium_browser(
    *,
    headless: bool = True,
    timeouts: CnyesBrowserTimeouts | None = None,
) -> CnyesSeleniumBrowser:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    options = Options()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1280,1800')
    driver = webdriver.Chrome(options=options)
    return CnyesSeleniumBrowser(driver, timeouts=timeouts)
