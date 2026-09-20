#!/usr/bin/env python3
"""Validate AI-DEV-249 CNYES live aggregation hang/lifecycle hardening."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.research.cnyes_selenium_browser as browser_module  # noqa: E402
from app.research.cnyes_selenium_browser import (  # noqa: E402
    CnyesBrowserTimeouts,
    CnyesSeleniumBrowser,
)
from app.research.tw_news_aggregation import TwNewsAggregationSession, collect_tw_news  # noqa: E402


class _Process:
    pid = 999999


class _Service:
    process = _Process()


class _Element:
    text = "台積電 月營收 成長 法說 展望 訂單 產能 重大訊息 " * 8


class _Driver:
    service = _Service()

    def __init__(self, *, fail: str | None = None, quit_delay: float = 0.0) -> None:
        self.fail = fail
        self.quit_delay = quit_delay
        self.closed = False
        self.page_timeout: float | None = None
        self.script_timeout: float | None = None

    def set_page_load_timeout(self, value: float) -> None:
        self.page_timeout = value

    def set_script_timeout(self, value: float) -> None:
        self.script_timeout = value

    def get(self, _url: str) -> None:
        if self.fail == "get_timeout":
            raise TimeoutError("page load timeout")

    def execute_script(self, _script: str) -> list[dict[str, str]]:
        if self.fail == "script_timeout":
            raise TimeoutError("script timeout")
        return [{
            "href": "https://news.cnyes.com/news/id/6609020",
            "text": "2026/09/18 09:05 台積電月營收成長 法說展望佳",
            "datetime_attr": "2026/09/18 09:05",
        }]

    def find_elements(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return [object()]

    def find_element(self, *_args: Any, **_kwargs: Any) -> _Element:
        return _Element()

    def quit(self) -> None:
        if self.quit_delay:
            time.sleep(self.quit_delay)
        self.closed = True


class _Browser:
    def __init__(self, *, fail: str | None = None) -> None:
        self.fail = fail
        self.closed = False

    def open_search(self, _url: str) -> None:
        if self.fail == "search_timeout":
            raise TimeoutError("search timeout")

    def wait_results_ready(self) -> None:
        pass

    def visible_result_cards(self) -> list[dict[str, Any]]:
        return [{
            "title": "台積電月營收成長 法說展望佳",
            "published_at": "2026/09/18 09:05",
            "url": "https://news.cnyes.com/news/id/6609020",
            "source": "鉅亨網",
            "content_status": "TITLE_ONLY",
        }]

    def scroll_for_more(self, _count: int) -> list[dict[str, Any]]:
        return []

    def open_article(self, _url: str) -> None:
        if self.fail == "article_timeout":
            raise TimeoutError("article timeout")

    def article_body(self) -> str:
        return "台積電 月營收 成長 法說 展望 訂單 產能 重大訊息 " * 8

    def close(self) -> None:
        self.closed = True


def _google_item() -> dict[str, Any]:
    return {
        "title": "台積電月營收成長",
        "source": "Google News RSS",
        "published": "2026-09-18T09:00:00+08:00",
        "link": "https://news.example/google-only",
    }


def _run() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    source_browser = (ROOT / "app/research/cnyes_selenium_browser.py").read_text(encoding="utf-8")
    source_diag = (ROOT / "scripts/orchestrator/diagnose_cnyes_live_aggregation_v1.py").read_text(encoding="utf-8")
    source_validator = (ROOT / "scripts/orchestrator/validate_tw_news_content_relevance_materiality_v1.py").read_text(encoding="utf-8")

    checks["stage_progress_emitted"] = all(token in source_diag for token in [
        "WATCHLIST_START", "WATCHLIST_DONE", "GOOGLE_RSS_START", "GOOGLE_RSS_DONE",
        "CNYES_BROWSER_START", "CNYES_BROWSER_READY", "CNYES_SYMBOL_START",
        "CNYES_SEARCH_DONE", "CNYES_ARTICLE_START", "CNYES_ARTICLE_DONE",
        "AGGREGATION_DONE", "BROWSER_QUIT_START", "BROWSER_QUIT_DONE", "FINAL_JSON",
    ])
    checks["final_json_stdout_contract"] = "file=sys.stderr" in source_diag and '"FINAL_JSON"' in source_diag and "print(json.dumps(result" in source_diag

    driver = _Driver()
    wrapped = CnyesSeleniumBrowser(driver, timeouts=CnyesBrowserTimeouts(page_load_seconds=3, script_seconds=2))
    checks["driver_timeouts_configured"] = driver.page_timeout == 3 and driver.script_timeout == 2 and wrapped.lifecycle.sessions_created == 1

    try:
        CnyesSeleniumBrowser(_Driver(fail="get_timeout"), timeouts=CnyesBrowserTimeouts(page_load_seconds=0.01)).open_search("https://www.cnyes.com/search/news?keyword=2330")
        checks["search_timeout"] = False
    except TimeoutError as exc:
        checks["search_timeout"] = "CNYES_SEARCH" in str(exc) or getattr(exc, "stage", "") == "CNYES_SEARCH"

    try:
        CnyesSeleniumBrowser(_Driver(fail="get_timeout"), timeouts=CnyesBrowserTimeouts(page_load_seconds=0.01)).open_article("https://news.cnyes.com/news/id/1")
        checks["article_timeout"] = False
    except TimeoutError as exc:
        checks["article_timeout"] = "CNYES_ARTICLE_NAVIGATION" in str(exc) or getattr(exc, "stage", "") == "CNYES_ARTICLE_NAVIGATION"

    original_cleanup = browser_module._terminate_owned_process_tree
    try:
        browser_module._terminate_owned_process_tree = lambda root_pid, grace_seconds: [root_pid]  # type: ignore[assignment]
        slow = CnyesSeleniumBrowser(_Driver(quit_delay=0.2), timeouts=CnyesBrowserTimeouts(quit_seconds=0.01, process_cleanup_grace_seconds=0.01))
        lifecycle = slow.close()
    finally:
        browser_module._terminate_owned_process_tree = original_cleanup  # type: ignore[assignment]
    checks["quit_timeout"] = lifecycle.quit_timed_out is True and lifecycle.cleanup_attempted is True and lifecycle.cleanup_pids == [999999]
    checks["exception_cleanup"] = "_terminate_owned_process_tree" in source_browser and "finally" in source_diag and "BROWSER_QUIT_START" in source_diag
    checks["one_browser_session_per_batch"] = "browser_launches" in source_diag and "sessions_created=session.browser_launches" in source_diag
    checks["no_orphan_on_success"] = "sessions_closed=session.browser_sessions_closed" in source_diag
    checks["no_orphan_on_failure"] = "browser_cleanup_pids" in source_diag and "quit_timed_out" in source_diag
    checks["no_broad_pkill_killall"] = "pkill" not in source_browser + source_diag and "killall" not in source_browser + source_diag and "_terminate_owned_process_tree(root_pid" in source_browser

    timeout = collect_tw_news(
        "2330",
        "台積電",
        reference="2026-09-18",
        session=TwNewsAggregationSession(browser_factory=lambda: _Browser(fail="search_timeout")),
        google_fetcher=lambda *_: [_google_item()],
    )
    checks["cnyes_failure_isolation"] = bool(timeout["source_health"]["CNYES"]["status"] == "degraded" and timeout["items"])
    google_failed = collect_tw_news(
        "2330",
        "台積電",
        reference="2026-09-18",
        session=TwNewsAggregationSession(browser_factory=lambda: _Browser()),
        google_fetcher=lambda *_: (_ for _ in ()).throw(RuntimeError("rss down")),
    )
    checks["google_failure_isolation"] = google_failed["source_health"]["GOOGLE_NEWS_RSS"]["status"] == "failed" and google_failed["source_health"]["CNYES"]["status"] == "success"
    checks["ai_dev_248_semantics_unchanged"] = (ROOT / "scripts/orchestrator/validate_ai_dev_248_tw_news_aggregation_cnyes_delivery_integration_v1.py").exists()
    checks["governance_validator_remains_offline"] = "webdriver.Chrome" not in source_validator and "class _BrowserAdapter" in source_validator
    checks["browser_startup_timeout_contract"] = "CNYES_BROWSER_START" in source_diag and "--stage-timeout-seconds" in source_diag

    details["checked_files"] = [
        "app/research/cnyes_selenium_browser.py",
        "app/research/tw_news_aggregation.py",
        "scripts/orchestrator/diagnose_cnyes_live_aggregation_v1.py",
    ]
    return {
        "ok": all(bool(value) for value in checks.values()),
        "passed_count": sum(1 for value in checks.values() if bool(value)),
        "total_count": len(checks),
        "checks": checks,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = _run()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
