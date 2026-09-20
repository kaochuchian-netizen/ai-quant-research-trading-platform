#!/usr/bin/env python3
"""Bounded live CNYES aggregation diagnostic runner.

This tool is intentionally separate from governance validators.  It emits
machine-readable progress to stderr so a live hang can be localized before the
final stdout JSON is available.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.news_fetcher import fetch_stock_news  # noqa: E402
from app.loaders.google_sheet_loader import load_stock_ids_with_provenance  # noqa: E402
from app.market.instrument_master import instrument_metadata  # noqa: E402
from app.research.cnyes_selenium_browser import CnyesBrowserTimeouts, create_cnyes_selenium_browser  # noqa: E402
from app.research.tw_news_aggregation import TwNewsAggregationSession, collect_tw_news  # noqa: E402
from app.research.tw_news_content_relevance import collect_cnyes_browser_news  # noqa: E402


EVENTS = (
    "WATCHLIST_START",
    "WATCHLIST_DONE",
    "GOOGLE_RSS_START",
    "GOOGLE_RSS_DONE",
    "CNYES_BROWSER_START",
    "CNYES_BROWSER_READY",
    "CNYES_SYMBOL_START",
    "CNYES_SEARCH_DONE",
    "CNYES_ARTICLE_START",
    "CNYES_ARTICLE_DONE",
    "AGGREGATION_DONE",
    "BROWSER_QUIT_START",
    "BROWSER_QUIT_DONE",
    "FINAL_JSON",
)


class DiagnosticStageTimeout(TimeoutError):
    def __init__(self, stage: str, timeout_seconds: float) -> None:
        self.stage = stage
        self.timeout_seconds = timeout_seconds
        super().__init__(f"{stage} exceeded {timeout_seconds:.1f}s")


@dataclass
class Progress:
    started: float = field(default_factory=time.monotonic)
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, stage: str, *, symbol: str | None = None, status: str = "ok", **extra: Any) -> None:
        event = {
            "event": stage,
            "stage": stage,
            "elapsed_seconds": round(time.monotonic() - self.started, 4),
            "status": status,
        }
        if symbol:
            event["symbol"] = symbol
        event.update(extra)
        self.events.append(event)
        print(json.dumps(event, ensure_ascii=False, sort_keys=True), file=sys.stderr, flush=True)


def _timed(progress: Progress, stage: str, timeout_seconds: float, fn: Callable[[], Any], *, symbol: str | None = None) -> Any:
    before = time.monotonic()
    result = fn()
    elapsed = time.monotonic() - before
    if elapsed > timeout_seconds:
        progress.emit(stage, symbol=symbol, status="timeout", duration_seconds=round(elapsed, 4), timeout_seconds=timeout_seconds)
        raise DiagnosticStageTimeout(stage, timeout_seconds)
    return result


def _stock_name(symbol: str) -> str:
    meta = instrument_metadata(symbol)
    return str(meta.get("name") or meta.get("company_name") or symbol)


def _load_watchlist(progress: Progress, limit: int, timeout_seconds: float) -> list[str]:
    progress.emit("WATCHLIST_START")
    symbols, evidence = _timed(progress, "WATCHLIST_DONE", timeout_seconds, lambda: load_stock_ids_with_provenance())
    selected = [str(symbol) for symbol in symbols[:limit]]
    progress.emit("WATCHLIST_DONE", status="ok", symbol_count=len(selected), source=evidence.get("source"))
    return selected


def _count_orphans() -> dict[str, int]:
    try:
        import subprocess
        output = subprocess.check_output(["ps", "-eo", "comm="], text=True, timeout=2)
    except Exception:
        return {"chrome_like": -1, "chromedriver_like": -1}
    names = [line.strip().lower() for line in output.splitlines()]
    return {
        "chrome_like": sum(1 for name in names if "chrome" in name or "chromium" in name),
        "chromedriver_like": sum(1 for name in names if "chromedriver" in name),
    }


def _browser_factory(timeout_seconds: float) -> Any:
    return create_cnyes_selenium_browser(
        timeouts=CnyesBrowserTimeouts(
            page_load_seconds=min(12.0, timeout_seconds),
            script_seconds=5.0,
            results_ready_seconds=10.0,
            scroll_growth_seconds=6.0,
            article_body_seconds=10.0,
            quit_seconds=5.0,
        )
    )


def _run_google_only(progress: Progress, symbol: str, stock_name: str, timeout_seconds: float) -> dict[str, Any]:
    progress.emit("GOOGLE_RSS_START", symbol=symbol)
    items = _timed(progress, "GOOGLE_RSS_DONE", timeout_seconds, lambda: fetch_stock_news(symbol, stock_name), symbol=symbol)
    progress.emit("GOOGLE_RSS_DONE", symbol=symbol, result_count=len(items))
    return {"result_count": len(items)}


def _run_browser_smoke(progress: Progress, timeout_seconds: float) -> dict[str, Any]:
    browser = None
    progress.emit("CNYES_BROWSER_START")
    try:
        browser = _timed(progress, "CNYES_BROWSER_READY", timeout_seconds, lambda: _browser_factory(timeout_seconds))
        progress.emit("CNYES_BROWSER_READY", status="ok")
        return {"ok": True, "lifecycle": getattr(browser, "lifecycle", None).__dict__}
    finally:
        if browser is not None:
            progress.emit("BROWSER_QUIT_START")
            lifecycle = browser.close()
            progress.emit("BROWSER_QUIT_DONE", sessions_closed=lifecycle.sessions_closed, quit_timed_out=lifecycle.quit_timed_out, cleanup_pids=lifecycle.cleanup_pids)


def _run_cnyes_symbol(progress: Progress, symbol: str, stock_name: str, reference: str, timeout_seconds: float) -> dict[str, Any]:
    browser = None
    progress.emit("CNYES_BROWSER_START")
    try:
        browser = _timed(progress, "CNYES_BROWSER_READY", timeout_seconds, lambda: _browser_factory(timeout_seconds))
        progress.emit("CNYES_BROWSER_READY", status="ok")
        progress.emit("CNYES_SYMBOL_START", symbol=symbol)
        result = collect_cnyes_browser_news(browser, symbol=symbol, stock_name=stock_name, reference=reference)
        progress.emit(
            "CNYES_SEARCH_DONE",
            symbol=symbol,
            within_window_results=result.get("within_window_results"),
            search_results_seen=result.get("search_results_seen"),
            scroll_stop_reason=result.get("scroll_stop_reason"),
        )
        if result.get("article_navigation_attempted"):
            progress.emit("CNYES_ARTICLE_START", symbol=symbol, attempted=result.get("article_navigation_attempted"))
            progress.emit("CNYES_ARTICLE_DONE", symbol=symbol, success=result.get("article_navigation_success"), failed=result.get("article_navigation_failed"))
        return result
    finally:
        if browser is not None:
            progress.emit("BROWSER_QUIT_START")
            lifecycle = browser.close()
            progress.emit("BROWSER_QUIT_DONE", sessions_closed=lifecycle.sessions_closed, quit_timed_out=lifecycle.quit_timed_out, cleanup_pids=lifecycle.cleanup_pids)


def _run_aggregation(progress: Progress, symbols: list[str], reference: str, timeout_seconds: float) -> dict[str, Any]:
    session = TwNewsAggregationSession(browser_factory=lambda: _browser_factory(timeout_seconds))
    results: list[dict[str, Any]] = []
    try:
        for symbol in symbols:
            stock_name = _stock_name(symbol)
            progress.emit("GOOGLE_RSS_START", symbol=symbol)
            progress.emit("CNYES_SYMBOL_START", symbol=symbol)
            result = collect_tw_news(symbol, stock_name, reference=reference, session=session)
            cnyes = result.get("cnyes_collection") or {}
            health = result.get("source_health") or {}
            progress.emit("GOOGLE_RSS_DONE", symbol=symbol, status=str(health.get("GOOGLE_NEWS_RSS", {}).get("status")), result_count=health.get("GOOGLE_NEWS_RSS", {}).get("result_count"))
            progress.emit("CNYES_SEARCH_DONE", symbol=symbol, status=str(health.get("CNYES", {}).get("status")), within_window_results=cnyes.get("within_window_results"), scroll_stop_reason=cnyes.get("scroll_stop_reason"))
            if cnyes.get("article_navigation_attempted"):
                progress.emit("CNYES_ARTICLE_START", symbol=symbol, attempted=cnyes.get("article_navigation_attempted"))
                progress.emit("CNYES_ARTICLE_DONE", symbol=symbol, success=cnyes.get("article_navigation_success"), failed=cnyes.get("article_navigation_failed"))
            results.append(result)
        progress.emit("AGGREGATION_DONE", symbol_count=len(results))
    finally:
        progress.emit("BROWSER_QUIT_START")
        session.close()
        progress.emit("BROWSER_QUIT_DONE", sessions_created=session.browser_launches, sessions_closed=session.browser_sessions_closed, quit_timed_out=session.browser_quit_timed_out, cleanup_pids=session.browser_cleanup_pids)
    return {
        "symbols": symbols,
        "results": [
            {
                "symbol": item.get("symbol"),
                "source_health": item.get("source_health"),
                "cnyes": item.get("cnyes_collection"),
                "prompt_ready_count": len(item.get("prompt_news_items") or []),
            }
            for item in results
        ],
        "browser_sessions_created": session.browser_launches,
        "browser_sessions_closed": session.browser_sessions_closed,
        "browser_quit_timed_out": session.browser_quit_timed_out,
        "browser_cleanup_pids": session.browser_cleanup_pids,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["watchlist", "google-rss", "browser-smoke", "cnyes-search", "aggregate-one", "aggregate-multi"], required=True)
    parser.add_argument("--symbol")
    parser.add_argument("--reference", default="now")
    parser.add_argument("--max-symbols", type=int, default=1)
    parser.add_argument("--stage-timeout-seconds", type=float, default=35.0)
    args = parser.parse_args()

    progress = Progress()
    status = "PASS"
    error: dict[str, Any] | None = None
    before = _count_orphans()
    payload: dict[str, Any] = {}
    try:
        symbols = [args.symbol] if args.symbol else _load_watchlist(progress, max(1, args.max_symbols), args.stage_timeout_seconds)
        symbol = symbols[0]
        stock_name = _stock_name(symbol)
        if args.mode == "watchlist":
            payload = {"symbols": symbols}
        elif args.mode == "google-rss":
            payload = _run_google_only(progress, symbol, stock_name, args.stage_timeout_seconds)
        elif args.mode == "browser-smoke":
            payload = _run_browser_smoke(progress, args.stage_timeout_seconds)
        elif args.mode == "cnyes-search":
            payload = _run_cnyes_symbol(progress, symbol, stock_name, args.reference, args.stage_timeout_seconds)
        elif args.mode == "aggregate-one":
            payload = _run_aggregation(progress, [symbol], args.reference, args.stage_timeout_seconds)
        elif args.mode == "aggregate-multi":
            payload = _run_aggregation(progress, symbols[: max(1, args.max_symbols)], args.reference, args.stage_timeout_seconds)
    except Exception as exc:
        status = "FAIL"
        error = {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "stage": getattr(exc, "stage", None),
            "timeout_seconds": getattr(exc, "timeout_seconds", None),
        }
        progress.emit(str(error.get("stage") or "DIAGNOSTIC_ERROR"), status="failed", error_type=error["type"])
    after = _count_orphans()
    result = {
        "schema_version": "ai_dev_249_cnyes_live_diagnostic_v1",
        "status": status,
        "ok": status == "PASS",
        "mode": args.mode,
        "elapsed_seconds": round(time.monotonic() - progress.started, 4),
        "payload": payload,
        "error": error,
        "events": progress.events,
        "process_counts_before": before,
        "process_counts_after": after,
    }
    progress.emit("FINAL_JSON", status=status.lower())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
