"""TW news aggregation for production analysis.

This layer is the single production-facing news source coordinator. It keeps
Google News RSS and CNYES independent, deduplicates across sources, enriches
content before prompt construction, and exposes source health without making
Selenium a governance-validator dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import os
import re
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from analysis.news_fetcher import fetch_stock_news
from app.research.tw_news_content_relevance import (
    CNYES_BROWSER_CONCURRENCY,
    CnyesBrowserContentCache,
    collect_cnyes_browser_news,
    enrich_news_items,
)

GOOGLE_SOURCE = "GOOGLE_NEWS_RSS"
CNYES_SOURCE = "CNYES"
MAX_ADMITTED_ARTICLES = 6
MAX_CHARS_PER_ARTICLE = 900
MAX_TOTAL_NEWS_CONTEXT_CHARS = 3600


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _canonical_url(value: Any) -> str:
    url = _text(value)
    if not url:
        return ""
    parsed = urlparse(url)
    if "news.google." in parsed.netloc.lower():
        for key in ("url", "u"):
            raw = parse_qs(parsed.query).get(key, [None])[0]
            if raw:
                return _canonical_url(unquote(raw))
    match = re.search(r"/news/id/(\d+)", url)
    if match:
        return f"https://news.cnyes.com/news/id/{match.group(1)}"
    return url.split("#", 1)[0]


def _dedupe_identity(item: dict[str, Any]) -> str:
    url = _canonical_url(item.get("source_url") or item.get("url") or item.get("link"))
    match = re.search(r"/news/id/(\d+)", url)
    if match:
        return f"cnyes:{match.group(1)}"
    article_id = _text(item.get("article_id") or item.get("article_identity"))
    if article_id:
        return article_id.lower()
    if url:
        return url.lower()
    title = _text(item.get("title") or item.get("headline")).lower()
    published = _text(item.get("published_at") or item.get("published") or item.get("date"))[:16]
    return "title-date:" + hashlib.sha256(f"{title}|{published}".encode("utf-8")).hexdigest()[:24]


def _content_rank(item: dict[str, Any]) -> int:
    status = str(item.get("content_status") or "").upper()
    if status == "FULL_CONTENT" or _text(item.get("content")):
        return 3
    if status in {"PARTIAL", "PARTIAL_CONTENT"}:
        return 2
    return 1


def _published_key(item: dict[str, Any]) -> str:
    return _text(item.get("published_at") or item.get("published") or item.get("date"))


def _normalize_google_item(item: dict[str, Any], *, stock_id: str, stock_name: str) -> dict[str, Any]:
    url = _canonical_url(item.get("source_url") or item.get("url") or item.get("link"))
    result = dict(item)
    result.update({
        "market": "TW",
        "symbol": str(stock_id),
        "stock_id": str(stock_id),
        "stock_name": stock_name,
        "title": _text(item.get("title") or item.get("headline")),
        "headline": _text(item.get("headline") or item.get("title")),
        "source": item.get("source") or GOOGLE_SOURCE,
        "publisher": item.get("publisher") or item.get("source") or GOOGLE_SOURCE,
        "source_url": url,
        "url": url,
        "published_at": item.get("published_at") or item.get("published"),
        "content_status": "TITLE_ONLY",
        "fetch_status": item.get("fetch_status") or "title_only",
        "source_provenance": [{"source": GOOGLE_SOURCE, "url": url, "content_status": "TITLE_ONLY"}],
        "primary_source": GOOGLE_SOURCE,
    })
    return result


def _normalize_cnyes_item(item: dict[str, Any], *, stock_id: str, stock_name: str) -> dict[str, Any]:
    url = _canonical_url(item.get("source_url") or item.get("url"))
    result = dict(item)
    result.update({
        "market": "TW",
        "symbol": str(stock_id),
        "stock_id": str(stock_id),
        "stock_name": stock_name,
        "title": _text(item.get("title") or item.get("headline")),
        "headline": _text(item.get("headline") or item.get("title")),
        "source": "鉅亨網",
        "publisher": "鉅亨網",
        "source_url": url,
        "url": url,
        "published_at": item.get("published_at") or item.get("published"),
        "source_provenance": [{"source": CNYES_SOURCE, "url": url, "content_status": item.get("content_status")}],
        "primary_source": CNYES_SOURCE,
    })
    return result


def _merge_duplicate(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    incumbent = dict(existing)
    challenger = dict(incoming)
    winner, loser = (challenger, incumbent) if _content_rank(challenger) > _content_rank(incumbent) else (incumbent, challenger)
    provenance = list(incumbent.get("source_provenance") or []) + list(challenger.get("source_provenance") or [])
    seen = set()
    merged_provenance = []
    for entry in provenance:
        key = (entry.get("source"), entry.get("url"))
        if key in seen:
            continue
        seen.add(key)
        merged_provenance.append(entry)
    result = {**loser, **winner}
    result["source_provenance"] = merged_provenance
    result["source"] = winner.get("source") or loser.get("source")
    result["publisher"] = winner.get("publisher") or loser.get("publisher")
    result["primary_source"] = winner.get("primary_source") or winner.get("source")
    return result


def dedupe_news_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_identity: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _dedupe_identity(item)
        if key in by_identity:
            by_identity[key] = _merge_duplicate(by_identity[key], item)
        else:
            by_identity[key] = dict(item)
    return sorted(by_identity.values(), key=lambda item: (_published_key(item), _content_rank(item)), reverse=True)


@dataclass
class TwNewsAggregationSession:
    """Batch-scoped state for CNYES browser reuse and transient content cache."""

    browser_factory: Callable[[], Any] | None = None
    enable_cnyes: bool = True
    browser: Any | None = None
    cnyes_cache: CnyesBrowserContentCache = field(default_factory=CnyesBrowserContentCache)
    browser_launches: int = 0
    symbols_processed: list[str] = field(default_factory=list)
    searches_attempted: int = 0
    articles_navigated: int = 0
    cache_hits: int = 0

    def get_browser(self) -> Any:
        if self.browser is None:
            factory = self.browser_factory or _default_cnyes_browser_factory
            self.browser = factory()
            self.browser_launches += 1
        return self.browser

    def close(self) -> None:
        browser, self.browser = self.browser, None
        if browser is not None:
            close = getattr(browser, "close", None) or getattr(browser, "quit", None)
            if callable(close):
                close()

    def __enter__(self) -> "TwNewsAggregationSession":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.close()


def _default_cnyes_browser_factory() -> Any:
    from app.research.cnyes_selenium_browser import create_cnyes_selenium_browser
    return create_cnyes_selenium_browser()


def collect_tw_news(
    stock_id: str,
    stock_name: str,
    *,
    reference: Any | None = None,
    session: TwNewsAggregationSession | None = None,
    google_fetcher: Callable[..., list[dict[str, Any]]] = fetch_stock_news,
    include_cnyes: bool | None = None,
) -> dict[str, Any]:
    started_at = _utc_now()
    reference = reference or started_at
    session = session or TwNewsAggregationSession()
    include_cnyes = session.enable_cnyes if include_cnyes is None else include_cnyes
    source_health: dict[str, dict[str, Any]] = {}
    raw_items: list[dict[str, Any]] = []
    cnyes_result: dict[str, Any] | None = None

    try:
        google_items = google_fetcher(stock_id, stock_name)
        source_health[GOOGLE_SOURCE] = {"attempted": True, "status": "success" if google_items else "degraded", "result_count": len(google_items)}
        raw_items.extend(_normalize_google_item(item, stock_id=str(stock_id), stock_name=stock_name) for item in google_items)
    except Exception as exc:
        source_health[GOOGLE_SOURCE] = {"attempted": True, "status": "failed", "reason": exc.__class__.__name__, "result_count": 0}

    if include_cnyes and os.environ.get("STOCK_AI_DISABLE_LIVE_NEWS_NETWORK") != "1":
        try:
            session.symbols_processed.append(str(stock_id))
            session.searches_attempted += 1
            before_cache = len(session.cnyes_cache.content_by_identity)
            cnyes_result = collect_cnyes_browser_news(
                session.get_browser(),
                symbol=str(stock_id),
                stock_name=stock_name,
                reference=reference,
                content_cache=session.cnyes_cache,
            )
            after_cache = len(session.cnyes_cache.content_by_identity)
            attempted = int(cnyes_result.get("article_navigation_attempted") or 0)
            session.articles_navigated += attempted
            session.cache_hits += max(0, attempted - max(0, after_cache - before_cache))
            cnyes_articles = [_normalize_cnyes_item(item, stock_id=str(stock_id), stock_name=stock_name) for item in cnyes_result.get("articles", [])]
            raw_items.extend(cnyes_articles)
            degraded_reason = cnyes_result.get("scroll_stop_reason") if cnyes_result.get("scroll_stop_reason") in {"PROTECTION_BLOCKED", "BROWSER_TIMEOUT", "BROWSER_CRASH"} else None
            source_health[CNYES_SOURCE] = {
                "attempted": True,
                "status": "degraded" if degraded_reason else "success",
                "reason": degraded_reason,
                "result_count": len(cnyes_articles),
                "within_window_results": cnyes_result.get("within_window_results"),
                "scroll_stop_reason": cnyes_result.get("scroll_stop_reason"),
                "target_trading_dates": cnyes_result.get("target_trading_dates"),
                "browser_concurrency": CNYES_BROWSER_CONCURRENCY,
            }
        except Exception as exc:
            source_health[CNYES_SOURCE] = {"attempted": True, "status": "degraded", "reason": exc.__class__.__name__, "result_count": 0}
    else:
        source_health[CNYES_SOURCE] = {"attempted": False, "status": "skipped", "reason": "DISABLED" if not include_cnyes else "LIVE_NETWORK_DISABLED", "result_count": 0}

    deduped = dedupe_news_items(raw_items)
    deduped, enrichment = enrich_news_items(deduped, stock_id=str(stock_id), stock_name=stock_name, fetch_content=True)
    completed_at = _utc_now()
    retrieved_sources = [source for source, health in source_health.items() if health.get("status") in {"success", "degraded"} and health.get("result_count", 0) > 0]
    attempted_sources = [source for source, health in source_health.items() if health.get("attempted") is True]
    return {
        "schema_version": "tw_news_aggregation_v1",
        "market": "TW",
        "symbol": str(stock_id),
        "stock_name": stock_name,
        "items": deduped,
        "content_relevance_enrichment": enrichment,
        "source_health": source_health,
        "cnyes_collection": cnyes_result,
        "retrieval": {
            "lookback_hours": 72,
            "sources_attempted": attempted_sources,
            "sources_succeeded": [source for source, health in source_health.items() if health.get("status") == "success"],
            "sources_failed": [{"source": source, "reason": health.get("reason") or health.get("status")} for source, health in source_health.items() if health.get("status") in {"failed", "degraded"}],
            "sources_degraded": [source for source, health in source_health.items() if health.get("status") == "degraded"],
            "query_started_at": started_at,
            "query_completed_at": completed_at,
            "result_count_raw": len(raw_items),
            "result_count_deduped": len(deduped),
            "result_count_admitted": int(enrichment.get("admission_ready") or 0),
            "result_count_evaluation_ready": int(enrichment.get("admission_ready") or 0),
            "retrieved_sources": retrieved_sources,
            "dedup_savings": max(0, len(raw_items) - len(deduped)),
            "browser_launches": session.browser_launches,
            "browser_concurrency": CNYES_BROWSER_CONCURRENCY,
            "transient_cache_entries": len(session.cnyes_cache.content_by_identity),
            "failure_reason": None if deduped else "NO_RESULT",
        },
        "prompt_policy": news_prompt_policy(),
    }


def news_prompt_policy() -> dict[str, int]:
    return {
        "max_admitted_articles": MAX_ADMITTED_ARTICLES,
        "max_chars_per_article": MAX_CHARS_PER_ARTICLE,
        "max_total_news_context_chars": MAX_TOTAL_NEWS_CONTEXT_CHARS,
    }


def select_prompt_news_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def rank(item: dict[str, Any]) -> tuple[int, int, str, str]:
        mat = {"critical": 3, "high": 2, "medium": 1}.get(str(item.get("materiality") or "").lower(), 0)
        rel = {"critical": 3, "high": 2, "medium": 1}.get(str(item.get("relevance") or "").lower(), 0)
        return (mat, rel, _published_key(item), _text(item.get("source")))
    selected = sorted(items, key=rank, reverse=True)[:MAX_ADMITTED_ARTICLES]
    total = 0
    bounded: list[dict[str, Any]] = []
    for item in selected:
        copy = dict(item)
        content = _text(copy.get("content"))[:MAX_CHARS_PER_ARTICLE]
        remaining = MAX_TOTAL_NEWS_CONTEXT_CHARS - total
        if remaining <= 0:
            break
        copy["content"] = content[:remaining]
        total += len(copy["content"])
        bounded.append(copy)
    return bounded


def build_aggregation_news_prompt(stock_id: str, stock_name: str, news_items: list[dict[str, Any]]) -> str:
    if not news_items:
        from analysis.news_prompt_builder import build_news_prompt
        return build_news_prompt(stock_id, stock_name, news_items)

    news_text = ""
    for index, item in enumerate(news_items, start=1):
        content = _text(item.get("content"))[:MAX_CHARS_PER_ARTICLE]
        if not content:
            content = _text(item.get("summary") or item.get("description") or item.get("title"))[:360]
        provenance = item.get("source_provenance") if isinstance(item.get("source_provenance"), list) else []
        source_names = ", ".join(dict.fromkeys(_text(entry.get("source")) for entry in provenance if entry.get("source")))
        news_text += f"""
新聞 {index}
股票：{stock_name}（{stock_id}）
日期：{item.get("published_at") or item.get("published") or ""}
來源：{source_names or item.get("source", "")}
標題：{item.get("title") or item.get("headline") or ""}
相關性：{item.get("relevance", "UNKNOWN")}
重大性：{item.get("materiality", "UNKNOWN")}
內文摘要：{content}
"""

    return f"""
你是台股新聞分析引擎，請根據以下已完成來源彙整、去重、內文補強與 relevance/materiality 評估的新聞，分析新聞消息面對股票的影響。

股票：{stock_name}（{stock_id}）

近期新聞：
{news_text}

請用繁體中文，輸出精簡分析。不可把來源不足的新聞當成確定事實。

輸出格式固定如下：

【新聞面分析】
新聞熱度：高 / 中 / 低
消息面方向：偏多 / 中性 / 偏空
主要原因：
-
-

短線影響：
中線影響：
長線影響：

風險：
-

結論：
"""
