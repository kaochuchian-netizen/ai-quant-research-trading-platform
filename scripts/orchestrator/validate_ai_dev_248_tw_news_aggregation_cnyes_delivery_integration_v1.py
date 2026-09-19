#!/usr/bin/env python3
"""Validate AI-DEV-248 TW news aggregation and CNYES delivery integration."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.research.tw_news_aggregation import (  # noqa: E402
    CNYES_SOURCE,
    GOOGLE_SOURCE,
    TwNewsAggregationSession,
    build_aggregation_news_prompt,
    collect_tw_news,
    dedupe_news_items,
    select_prompt_news_items,
)


class _Browser:
    def __init__(self, batches: list[list[dict[str, Any]]], bodies: dict[str, str] | None = None, *, fail: str | None = None) -> None:
        self.batches = batches
        self.bodies = bodies or {}
        self.fail = fail
        self.index = 0
        self.opened_search_urls: list[str] = []
        self.opened_articles: list[str] = []
        self.closed = False

    def _maybe_fail(self) -> None:
        if self.fail == "timeout":
            raise TimeoutError("selenium explicit wait timeout")
        if self.fail == "protection":
            raise RuntimeError("Cloudflare security challenge blocked")
        if self.fail == "crash":
            raise RuntimeError("chrome not reachable")

    def open_search(self, url: str) -> None:
        self.opened_search_urls.append(url)
        self._maybe_fail()

    def wait_results_ready(self) -> None:
        self._maybe_fail()

    def visible_result_cards(self) -> list[dict[str, Any]]:
        self._maybe_fail()
        return self.batches[0] if self.batches else []

    def scroll_for_more(self, _current_count: int) -> list[dict[str, Any]]:
        self._maybe_fail()
        self.index += 1
        return self.batches[self.index] if self.index < len(self.batches) else []

    def open_article(self, url: str) -> None:
        self.opened_articles.append(url)
        self._maybe_fail()

    def article_body(self) -> str:
        return self.bodies.get(self.opened_articles[-1], "") if self.opened_articles else ""

    def close(self) -> None:
        self.closed = True


def _body(symbol: str) -> str:
    return f"{symbol} 台積電 月營收 成長 展望 訂單 產能 法說 重大訊息 " * 8


def _google_item(symbol: str = "2330", url: str = "https://news.cnyes.com/news/id/6609020") -> dict[str, Any]:
    return {
        "title": f"{symbol} 台積電月營收成長",
        "source": "Google News RSS",
        "published": "2026-09-18T09:00:00+08:00",
        "link": url,
    }


def _cnyes_card(symbol: str = "2330", *, url: str = "https://news.cnyes.com/news/id/6609020", content_status: str = "TITLE_ONLY") -> dict[str, Any]:
    return {
        "title": f"{symbol} 台積電月營收成長 法說展望佳",
        "published_at": "2026/09/18 09:05",
        "url": url,
        "source": "鉅亨網",
        "content_status": content_status,
    }


def _run() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    dynamic_symbol = "7777"
    browser = _Browser([[_cnyes_card(dynamic_symbol, url="https://news.cnyes.com/news/id/7777001")]], {"https://news.cnyes.com/news/id/7777001": _body(dynamic_symbol)})
    session = TwNewsAggregationSession(browser_factory=lambda: browser)
    aggregate = collect_tw_news(dynamic_symbol, "動態測試", reference="2026-09-18", session=session, google_fetcher=lambda *_: [_google_item(dynamic_symbol, "https://news.example/dynamic")])
    checks["dynamic_watchlist_symbol_google_and_cnyes"] = aggregate["symbol"] == dynamic_symbol and aggregate["source_health"][GOOGLE_SOURCE]["attempted"] and aggregate["source_health"][CNYES_SOURCE]["attempted"]
    checks["no_fixed_symbol_dependency"] = dynamic_symbol in session.symbols_processed and "2330" not in session.symbols_processed

    dup = collect_tw_news("2330", "台積電", reference="2026-09-18", session=TwNewsAggregationSession(browser_factory=lambda: _Browser([[_cnyes_card()]], {"https://news.cnyes.com/news/id/6609020": _body("2330")})), google_fetcher=lambda *_: [_google_item()])
    checks["google_rss_and_cnyes_aggregation"] = set(dup["source_health"]) == {GOOGLE_SOURCE, CNYES_SOURCE}
    checks["cross_source_duplicate_collapse"] = dup["retrieval"]["result_count_raw"] >= 2 and dup["retrieval"]["result_count_deduped"] == 1
    item = dup["items"][0]
    checks["full_content_wins_over_title_only"] = bool(item.get("content_status") == "FULL_CONTENT" and item.get("content"))
    checks["source_provenance_preserved"] = {entry.get("source") for entry in item.get("source_provenance", [])} == {GOOGLE_SOURCE, CNYES_SOURCE}
    checks["two_trading_day_freshness"] = dup["cnyes_collection"]["target_trading_dates"] == ["2026-09-18", "2026-09-17"]
    checks["old_article_never_browser_fetched"] = all("09/15" not in str(article.get("published_at")) for article in dup["cnyes_collection"].get("article_fetch_queue", []))
    prompt_items = select_prompt_news_items(dup["items"])
    prompt = build_aggregation_news_prompt("2330", "台積電", prompt_items)
    checks["full_content_before_ai_prompt"] = "內文摘要" in prompt and "月營收" in prompt and "重大性" in prompt
    checks["bounded_prompt_context"] = len(prompt) < 6000 and len(prompt_items) <= 6

    timeout_session = TwNewsAggregationSession(browser_factory=lambda: _Browser([], fail="timeout"))
    timeout = collect_tw_news("2330", "台積電", reference="2026-09-18", session=timeout_session, google_fetcher=lambda *_: [_google_item("2330", "https://news.example/google-only")])
    checks["cnyes_failure_isolation"] = bool(timeout["source_health"][CNYES_SOURCE]["status"] == "degraded" and timeout["source_health"][GOOGLE_SOURCE]["result_count"] == 1 and timeout["items"])
    google_failed = collect_tw_news("2330", "台積電", reference="2026-09-18", session=TwNewsAggregationSession(browser_factory=lambda: _Browser([[_cnyes_card()]], {"https://news.cnyes.com/news/id/6609020": _body("2330")})), google_fetcher=lambda *_: (_ for _ in ()).throw(RuntimeError("rss down")))
    checks["google_failure_isolation"] = bool(google_failed["source_health"][GOOGLE_SOURCE]["status"] == "failed" and google_failed["source_health"][CNYES_SOURCE]["status"] == "success" and google_failed["items"])

    shared_browser = _Browser([[_cnyes_card("2330")]], {"https://news.cnyes.com/news/id/6609020": _body("2330")})
    shared = TwNewsAggregationSession(browser_factory=lambda: shared_browser)
    collect_tw_news("2330", "台積電", reference="2026-09-18", session=shared, google_fetcher=lambda *_: [])
    collect_tw_news("3293", "鈊象", reference="2026-09-18", session=shared, google_fetcher=lambda *_: [])
    shared.close()
    checks["browser_session_reuse"] = shared.browser_launches == 1
    checks["browser_concurrency_one"] = dup["retrieval"]["browser_concurrency"] == 1
    checks["browser_cleanup"] = shared_browser.closed is True
    checks["transient_article_cache"] = shared.cnyes_cache.content_by_identity and dup["retrieval"]["transient_cache_entries"] >= 1

    source_pre = (ROOT / "app/pipelines/pre_open_pipeline.py").read_text(encoding="utf-8")
    source_pm = (ROOT / "app/pipelines/afternoon_report_pipeline.py").read_text(encoding="utf-8")
    source_engine = (ROOT / "analysis/news_analysis_engine.py").read_text(encoding="utf-8")
    checks["pre_open_0700_connected"] = "TwNewsAggregationSession" in source_pre and "aggregation_session=news_aggregation_session" in source_pre
    checks["intraday_1305_connected"] = "WINDOW_BY_PIPELINE" in source_pm and "intraday_1305" in source_pm and "aggregation_session=news_aggregation_session" in source_pm
    checks["pre_close_1335_connected"] = "pre_close_1335" in source_pm and "current_news_evidence" in source_pm
    checks["post_close_1500_connected"] = "post_close_1500" in source_pm and "include_evidence=True" in source_pm
    checks["source_attribution_rendered"] = "news_bundle" in source_pre and "current_news_items" in source_pm
    checks["aggregation_used_before_prompt"] = source_engine.index("aggregation = collect_tw_news") < source_engine.index("prompt = build_aggregation_news_prompt")

    tw_news_validator = (ROOT / "scripts/orchestrator/validate_tw_news_content_relevance_materiality_v1.py").read_text(encoding="utf-8")
    checks["existing_cnyes_regression_retained"] = "cnyes_2330_dom_20260917_parsed" in tw_news_validator and "cnyes_protection_challenge_fail_closed" in tw_news_validator
    checks["governance_validator_offline_no_selenium"] = "webdriver.Chrome" not in tw_news_validator and "class _BrowserAdapter" in tw_news_validator

    details["mock_benchmark"] = {
        "symbols_processed": shared.symbols_processed,
        "browser_launches": shared.browser_launches,
        "searches_attempted": shared.searches_attempted,
        "articles_navigated": shared.articles_navigated,
        "cache_entries": len(shared.cnyes_cache.content_by_identity),
        "dedup_savings": dup["retrieval"].get("dedup_savings"),
    }
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
