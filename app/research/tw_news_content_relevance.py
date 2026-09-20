"""Read-only TW news article extraction and deterministic relevance scoring.

This module is intentionally dependency-light and policy-first.  It can enrich
Google News RSS candidates with readable article content when the article page
is openly accessible.  If content cannot be fetched or parsed, the candidate is
left without relevance/materiality so downstream admission remains fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from html import unescape
from html.parser import HTMLParser
import ipaddress
import os
import re
import socket
import time as monotonic_time
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
import urllib3

from app.market.tw_history_admission import expected_completed_session
from app.market.instrument_master import instrument_metadata

USER_AGENT = "stock-ai-news-evidence/1.0"
MAX_CONTENT_CHARS = 6000
MIN_CONTENT_CHARS = 80
REQUEST_TIMEOUT_SECONDS = 6
MAX_RESPONSE_BYTES = 1_000_000
MAX_REDIRECTS = 3
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}
TAIPEI = ZoneInfo("Asia/Taipei")
CNYES_SOURCE = "CNYES"
CNYES_SEARCH_METHOD = "SELENIUM_BROWSER"
CNYES_LAZY_LOAD_METHOD = "DOM_INCREMENTAL_SCROLL"
CNYES_ARTICLE_METHOD = "SELENIUM_BROWSER"
CNYES_INTERNAL_JSON_ENDPOINT = "NOT_PRODUCTION_DEPENDENCY"
CNYES_BROWSER_CONCURRENCY = 1
CNYES_TIME_WINDOW_SCHEMA = "cnyes_tw_trading_day_freshness_v1"
CNYES_MAX_SCROLL_ROUNDS = 8
CNYES_MAX_SEARCH_RESULTS = 80
CNYES_MAX_SEARCH_DURATION_SECONDS = 18.0

MATERIALITY_KEYWORDS = {
    "critical": (
        "重大訊息", "重訊", "併購", "收購", "下市", "停牌", "財測下修", "財測上修",
        "重大裁罰", "違約", "倒閉", "破產",
    ),
    "high": (
        "月營收", "營收", "財報", "獲利", "eps", "毛利率", "法說", "展望", "訂單",
        "出貨", "產能", "資本支出", "股利", "除息", "庫藏股", "新產品", "接單",
        "客戶", "供應鏈", "投資", "擴產", "減產",
    ),
    "medium": (
        "股價", "成交", "外資", "投信", "法人", "產業", "需求", "價格", "新品",
        "市場", "技術", "合作", "題材", "轉型",
    ),
}

LOW_VALUE_PATTERNS = (
    "股市爆料同學會", "個股概覽", "今日股價與討論", "含.*etf與基金成分股",
    "投資風險", "討論區", "存股", "能買", "該買嗎",
)

POSITIVE_TERMS = ("成長", "增加", "升溫", "上修", "創高", "擴產", "接單", "動能", "看好", "轉強")
NEGATIVE_TERMS = ("下滑", "衰退", "下修", "減產", "裁罰", "虧損", "風險", "賣壓", "跌", "違約")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._capture = False
        self._chunks: list[str] = []
        self.meta_description: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside"}:
            self._skip_depth += 1
            return
        if tag == "meta":
            name = (attr.get("name") or attr.get("property") or "").lower()
            if name in {"description", "og:description"} and attr.get("content"):
                self.meta_description = attr["content"]
        if tag in {"article", "main", "p", "h1", "h2", "li"}:
            self._capture = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._skip_depth and tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside"}:
            self._skip_depth -= 1
        if tag in {"article", "main", "p", "h1", "h2", "li"}:
            self._capture = False
            self._chunks.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if self._capture and text:
            self._chunks.append(text)

    def text(self) -> str:
        parts = []
        if self.meta_description:
            parts.append(self.meta_description)
        parts.extend(self._chunks)
        return normalize_text(" ".join(parts))


@dataclass(frozen=True)
class ArticleContent:
    fetch_status: str
    content: str
    final_url: str | None = None
    failure_reason: str | None = None
    http_status: int | None = None


@dataclass(frozen=True)
class CnyesSearchConfig:
    max_scroll_rounds: int = CNYES_MAX_SCROLL_ROUNDS
    max_search_results: int = CNYES_MAX_SEARCH_RESULTS
    max_search_duration_seconds: float = CNYES_MAX_SEARCH_DURATION_SECONDS
    min_boundary_older_results: int = 1
    max_article_navigation: int = 3


@dataclass
class CnyesBrowserContentCache:
    """Per bounded collection-session article cache.

    It prevents opening the same CNYES article page more than once when multiple
    symbols or aliases discover the same canonical article.  The cache stores
    transient content for the current pipeline execution only; persisted
    artifacts should keep analysis results and source metadata, not an
    unbounded full-text mirror.
    """

    content_by_identity: dict[str, ArticleContent]

    def __init__(self) -> None:
        self.content_by_identity = {}


class _PinnedResponse:
    def __init__(self, *, status: int, headers: Any, raw_response: Any, url: str) -> None:
        self.status_code = status
        self.headers = headers
        self._raw_response = raw_response
        self.url = url
        self.encoding = "utf-8"

    def iter_content(self, chunk_size: int = 65536):
        yield from self._raw_response.stream(chunk_size)

    def close(self) -> None:
        close = getattr(self._raw_response, "release_conn", None)
        if callable(close):
            close()


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _day(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        if isinstance(value, datetime):
            return value.astimezone(TAIPEI).date() if value.tzinfo else value.date()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(TAIPEI).date()
    except (TypeError, ValueError):
        return None


def _parse_published_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(TAIPEI) if value.tzinfo else value.replace(tzinfo=TAIPEI)
    text = normalize_text(value)
    if not text:
        return None
    slash_match = re.search(
        r"\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\b",
        text,
    )
    if slash_match:
        year, month, day, hour, minute, second = slash_match.groups()
        try:
            return datetime(
                int(year),
                int(month),
                int(day),
                int(hour or 0),
                int(minute or 0),
                int(second or 0),
                tzinfo=TAIPEI,
            )
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(TAIPEI) if parsed.tzinfo else parsed.replace(tzinfo=TAIPEI)


def parse_cnyes_dom_timestamp(value: Any, *, reference: Any | None = None) -> str | None:
    """Normalize CNYES DOM/display timestamps to an Asia/Taipei ISO string.

    CNYES search cards can expose machine timestamps in a ``datetime`` attribute
    or display-only strings such as ``2026/09/17``, ``09/17 15:11`` or ``08:10``
    for same-day latest cards.  The parser is intentionally deterministic and
    does not infer stale dates beyond the supplied reference day.
    """
    parsed = _parse_published_at(value)
    if parsed:
        return parsed.isoformat()
    text = normalize_text(value)
    if not text:
        return None
    ref_dt = _parse_published_at(reference) if reference is not None else None
    ref_day = ref_dt.date() if ref_dt else None
    month_day = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?\b", text)
    if month_day and ref_day:
        month, day, hour, minute = month_day.groups()
        try:
            return datetime(
                ref_day.year,
                int(month),
                int(day),
                int(hour or 0),
                int(minute or 0),
                tzinfo=TAIPEI,
            ).isoformat()
        except ValueError:
            return None
    clock = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if clock and ref_day:
        hour, minute = clock.groups()
        try:
            return datetime(ref_day.year, ref_day.month, ref_day.day, int(hour), int(minute), tzinfo=TAIPEI).isoformat()
        except ValueError:
            return None
    return None


def cnyes_search_result_from_dom(
    *,
    href: str,
    text: str = "",
    datetime_attr: str | None = None,
    symbol: str = "",
    stock_name: str = "",
    reference: Any | None = None,
    content_status: str = "TITLE_ONLY",
) -> dict[str, Any]:
    """Build a normalized CNYES search record from Selenium DOM fields."""
    raw_text = normalize_text(text)
    published_at = parse_cnyes_dom_timestamp(datetime_attr or raw_text, reference=reference)
    title = raw_text
    if published_at:
        title = re.sub(r"\b20\d{2}[/-]\d{1,2}[/-]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b", " ", title)
        title = re.sub(r"^\d{1,2}:\d{2}\s+", " ", title)
    title = re.sub(r"^(台股新聞|台股盤後|台股營收|台股公告|雜誌|盤後|新聞)\s+", " ", title)
    return {
        "market": "TW",
        "symbol": str(symbol),
        "stock_name": stock_name,
        "title": normalize_text(title),
        "published_at": published_at,
        "url": _canonical_news_url({"url": href}),
        "source": "鉅亨網",
        "content_status": content_status,
        "article_id": (re.search(r"/news/id/(\d+)", href or "").group(1) if re.search(r"/news/id/(\d+)", href or "") else None),
        "raw_text_preview": raw_text[:240],
    }


def resolve_tw_recent_two_trading_days(
    reference: Any,
    *,
    holiday_dates: set[str] | set[date] | None = None,
) -> list[date]:
    """Return current-or-most-recent TW trading day plus the previous TW trading day."""
    current = expected_completed_session(reference, window="completed_session", holiday_dates=holiday_dates)
    if current is None:
        return []
    previous_seed = current - timedelta(days=1)
    previous = expected_completed_session(previous_seed, window="completed_session", holiday_dates=holiday_dates)
    return [current, previous] if previous else [current]


def build_cnyes_target_window(
    reference: Any,
    *,
    holiday_dates: set[str] | set[date] | None = None,
) -> dict[str, Any]:
    days = resolve_tw_recent_two_trading_days(reference, holiday_dates=holiday_dates)
    if not days:
        return {
            "schema_version": CNYES_TIME_WINDOW_SCHEMA,
            "target_trading_dates": [],
            "target_window_start": None,
            "target_window_end": None,
            "status": "INVALID_REFERENCE_DATE",
        }
    start_day = min(days)
    end_day = max(days)
    return {
        "schema_version": CNYES_TIME_WINDOW_SCHEMA,
        "target_trading_dates": [day.isoformat() for day in days],
        "target_window_start": datetime.combine(start_day, time.min, tzinfo=TAIPEI).isoformat(),
        "target_window_end": datetime.combine(end_day, time.max, tzinfo=TAIPEI).isoformat(),
        "status": "READY",
        "calendar_policy": "current_or_most_recent_tw_trading_day_plus_previous_tw_trading_day",
    }


def _canonical_news_url(raw: dict[str, Any]) -> str:
    url = normalize_text(raw.get("source_url") or raw.get("url") or raw.get("link"))
    match = re.search(r"/news/id/(\d+)", url)
    if match:
        return f"https://news.cnyes.com/news/id/{match.group(1)}"
    return url.split("#", 1)[0]


def cnyes_article_identity(raw: dict[str, Any]) -> str:
    url = _canonical_news_url(raw)
    match = re.search(r"/news/id/(\d+)", url)
    if match:
        return f"cnyes:{match.group(1)}"
    return url or normalize_text(raw.get("title") or raw.get("headline"))


def _normalize_cnyes_search_result(raw: dict[str, Any]) -> dict[str, Any]:
    raw_published = raw.get("published_at") or raw.get("published") or raw.get("date")
    published = _parse_published_at(raw_published)
    if published is None:
        normalized = parse_cnyes_dom_timestamp(raw_published, reference=raw.get("reference"))
        published = _parse_published_at(normalized)
    url = _canonical_news_url(raw)
    return {
        "market": raw.get("market") or "TW",
        "symbol": str(raw.get("symbol") or raw.get("stock_id") or ""),
        "matched_keyword": raw.get("matched_keyword"),
        "title": normalize_text(raw.get("title") or raw.get("headline")),
        "published_at": published.isoformat() if published else None,
        "url": url,
        "source_url": url,
        "source": raw.get("source") or "鉅亨網",
        "content": normalize_text(raw.get("content")),
        "fetch_status": raw.get("fetch_status") or ("success" if raw.get("content") else "title_only"),
        "relevance_status": raw.get("relevance_status") or "NOT_EVALUATED",
        "content_status": raw.get("content_status") or ("FULL_CONTENT" if raw.get("content") else "TITLE_ONLY"),
        "article_id": raw.get("article_id") or (re.search(r"/news/id/(\d+)", url).group(1) if re.search(r"/news/id/(\d+)", url) else None),
        "article_identity": cnyes_article_identity({**raw, "url": url}),
        "raw_fields": {key: value for key, value in raw.items() if key not in {"content"}},
    }


def collect_cnyes_time_window_results(
    result_batches: list[list[dict[str, Any]]] | tuple[list[dict[str, Any]], ...],
    *,
    symbol: str,
    stock_name: str,
    reference: Any,
    holiday_dates: set[str] | set[date] | None = None,
    config: CnyesSearchConfig | None = None,
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    """Collect CNYES search results with a TW-trading-window bounded lazy-load contract.

    The caller supplies incrementally loaded search-result batches.  A live source
    can obtain those batches through a public cursor/API endpoint or, only when
    necessary, a browser-scroll fallback; this pure collector owns the shared
    freshness, dedupe, priority and stop-reason semantics.
    """
    cfg = config or CnyesSearchConfig()
    target = build_cnyes_target_window(reference, holiday_dates=holiday_dates)
    target_dates = set(target["target_trading_dates"])
    lower_day = min((_day(value) for value in target_dates if value), default=None)
    start = monotonic_time.monotonic()
    seen_urls: set[str] = set()
    within_window: list[dict[str, Any]] = []
    all_dates: list[datetime] = []
    older_than_window_seen = 0
    search_results_seen = 0
    scroll_rounds = 0
    stop_reason = "NO_RESULTS"
    saw_window_result = False

    for batch in result_batches:
        if scroll_rounds >= cfg.max_scroll_rounds:
            stop_reason = "MAX_SCROLL_ROUNDS_REACHED"
            break
        elapsed = elapsed_seconds if elapsed_seconds is not None else monotonic_time.monotonic() - start
        if elapsed >= cfg.max_search_duration_seconds:
            stop_reason = "MAX_SEARCH_DURATION_REACHED"
            break
        if search_results_seen >= cfg.max_search_results:
            stop_reason = "MAX_SEARCH_RESULTS_REACHED"
            break
        scroll_rounds += 1
        new_items = 0
        batch_parseable: list[tuple[dict[str, Any], datetime]] = []
        for raw in batch:
            if search_results_seen >= cfg.max_search_results:
                stop_reason = "MAX_SEARCH_RESULTS_REACHED"
                break
            item = _normalize_cnyes_search_result({**raw, "symbol": symbol, "stock_name": stock_name, "reference": reference})
            url = item.get("url") or ""
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            search_results_seen += 1
            new_items += 1
            published = _parse_published_at(item.get("published_at"))
            if published:
                all_dates.append(published)
                batch_parseable.append((item, published))
                published_day = published.date().isoformat()
                if published_day in target_dates:
                    within_window.append(item)
                    saw_window_result = True
                elif lower_day and published.date() < lower_day:
                    older_than_window_seen += 1
        if new_items == 0:
            stop_reason = "NO_NEW_RESULTS"
            break
        old_items = [
            (item, published)
            for item, published in batch_parseable
            if lower_day and published.date() < lower_day
        ]
        if old_items and saw_window_result:
            last_parseable_is_old = bool(batch_parseable and batch_parseable[-1] in old_items)
            if last_parseable_is_old and len(old_items) >= cfg.min_boundary_older_results:
                stop_reason = "TRADING_WINDOW_BOUNDARY_REACHED"
                break
        if stop_reason == "MAX_SEARCH_RESULTS_REACHED":
            break
        stop_reason = "MORE_RESULTS_AVAILABLE_OR_BOUND_NOT_REACHED"
    else:
        if result_batches:
            stop_reason = "INPUT_EXHAUSTED_BEFORE_BOUNDARY"

    within_window.sort(key=lambda item: (_parse_published_at(item.get("published_at")) or datetime.min.replace(tzinfo=TAIPEI)), reverse=True)
    fetch_queue = build_cnyes_article_fetch_queue(within_window)
    return {
        "schema_version": "cnyes_time_window_bounded_collection_v1",
        "source": CNYES_SOURCE,
        "search_method": CNYES_SEARCH_METHOD,
        "lazy_load_method": CNYES_LAZY_LOAD_METHOD,
        "article_method": CNYES_ARTICLE_METHOD,
        "internal_json_endpoint": CNYES_INTERNAL_JSON_ENDPOINT,
        "market": "TW",
        "symbol": symbol,
        "stock_name": stock_name,
        **target,
        "search_scroll_rounds": scroll_rounds,
        "search_results_seen": search_results_seen,
        "within_window_results": len(within_window),
        "older_than_window_seen": older_than_window_seen,
        "scroll_stop_reason": stop_reason,
        "oldest_result_seen": min(all_dates).isoformat() if all_dates else None,
        "newest_result_seen": max(all_dates).isoformat() if all_dates else None,
        "deduplicated_articles": len(within_window),
        "full_content_available": sum(1 for item in within_window if str(item.get("content_status") or "").upper() == "FULL_CONTENT"),
        "article_navigation_required": len(fetch_queue),
        "article_navigation_attempted": 0,
        "article_navigation_success": 0,
        "article_navigation_failed": 0,
        "article_fetch_required": len(fetch_queue),
        "article_fetch_attempted": 0,
        "article_fetch_success": 0,
        "article_fetch_failed": 0,
        "browser_timeout_count": 0,
        "protection_blocked_count": 0,
        "browser_crash_count": 0,
        "usable_for_analysis_count": 0,
        "articles": within_window,
        "article_fetch_queue": fetch_queue,
        "safety_bounds": {
            "max_scroll_rounds": cfg.max_scroll_rounds,
            "max_search_results": cfg.max_search_results,
            "max_search_duration_seconds": cfg.max_search_duration_seconds,
        },
    }


def build_cnyes_article_fetch_queue(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required_statuses = {"TITLE_ONLY", "PARTIAL", "PARTIAL_CONTENT", "EMPTY"}
    queue = [
        item for item in articles
        if str(item.get("content_status") or "").upper() in required_statuses
    ]
    queue.sort(
        key=lambda item: (
            _parse_published_at(item.get("published_at")) or datetime.min.replace(tzinfo=TAIPEI),
            normalize_text(item.get("title")),
            normalize_text(item.get("url")),
        ),
        reverse=True,
    )
    return queue


def _browser_failure_reason(exc: BaseException) -> str:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    if any(token in text for token in ("captcha", "cloudflare", "security challenge", "access denied", "blocked")):
        return "PROTECTION_BLOCKED"
    if "timeout" in text:
        return "BROWSER_TIMEOUT"
    if any(token in text for token in ("crash", "disconnected", "session deleted", "chrome not reachable")):
        return "BROWSER_CRASH"
    return exc.__class__.__name__.upper()


def _article_content_from_browser(browser: Any, article: dict[str, Any]) -> ArticleContent:
    url = normalize_text(article.get("url") or article.get("source_url"))
    if not url:
        return ArticleContent("failed", "", failure_reason="ARTICLE_URL_MISSING")
    try:
        browser.open_article(url)
        body = normalize_text(browser.article_body())
    except Exception as exc:  # Browser adapters normalize concrete Selenium errors differently.
        return ArticleContent("failed", "", final_url=url, failure_reason=_browser_failure_reason(exc))
    if len(body) < MIN_CONTENT_CHARS:
        return ArticleContent("failed", "", final_url=url, failure_reason="EMPTY_OR_UNREADABLE_CONTENT")
    return ArticleContent("success", body[:MAX_CONTENT_CHARS], final_url=url)


def collect_cnyes_browser_news(
    browser: Any,
    *,
    symbol: str,
    stock_name: str,
    reference: Any,
    holiday_dates: set[str] | set[date] | None = None,
    config: CnyesSearchConfig | None = None,
    content_cache: CnyesBrowserContentCache | None = None,
) -> dict[str, Any]:
    """Collect and enrich CNYES news through one bounded Selenium browser session.

    The browser object is intentionally adapter-shaped so CI can use deterministic
    DOM fixtures and production can bind it to Selenium/Chrome without making
    live cnyes.com a test dependency.
    """
    cfg = config or CnyesSearchConfig()
    cache = content_cache or CnyesBrowserContentCache()
    batches: list[list[dict[str, Any]]] = []
    search_url = f"https://www.cnyes.com/search/news?keyword={symbol}"
    browser_timeout_count = protection_blocked_count = browser_crash_count = 0
    try:
        browser.open_search(search_url)
        browser.wait_results_ready()
        batches.append(list(browser.visible_result_cards()))
        while True:
            current = collect_cnyes_time_window_results(
                batches,
                symbol=symbol,
                stock_name=stock_name,
                reference=reference,
                holiday_dates=holiday_dates,
                config=cfg,
            )
            if current["scroll_stop_reason"] in {
                "TRADING_WINDOW_BOUNDARY_REACHED",
                "NO_NEW_RESULTS",
                "MAX_SCROLL_ROUNDS_REACHED",
                "MAX_SEARCH_RESULTS_REACHED",
                "MAX_SEARCH_DURATION_REACHED",
            }:
                break
            try:
                next_batch = list(browser.scroll_for_more(current["search_results_seen"]))
            except Exception as exc:
                reason = _browser_failure_reason(exc)
                if reason == "PROTECTION_BLOCKED":
                    protection_blocked_count += 1
                elif reason == "BROWSER_TIMEOUT":
                    browser_timeout_count += 1
                elif reason == "BROWSER_CRASH":
                    browser_crash_count += 1
                current["scroll_stop_reason"] = reason
                break
            if not next_batch:
                batches.append([])
                break
            batches.append(next_batch)
    except Exception as exc:
        reason = _browser_failure_reason(exc)
        if reason == "PROTECTION_BLOCKED":
            protection_blocked_count += 1
        elif reason == "BROWSER_TIMEOUT":
            browser_timeout_count += 1
        elif reason == "BROWSER_CRASH":
            browser_crash_count += 1
        current = collect_cnyes_time_window_results(
            batches,
            symbol=symbol,
            stock_name=stock_name,
            reference=reference,
            holiday_dates=holiday_dates,
            config=cfg,
        )
        current["scroll_stop_reason"] = reason

    result = collect_cnyes_time_window_results(
        batches,
        symbol=symbol,
        stock_name=stock_name,
        reference=reference,
        holiday_dates=holiday_dates,
        config=cfg,
    )
    if "current" in locals() and current.get("scroll_stop_reason") in {"PROTECTION_BLOCKED", "BROWSER_TIMEOUT", "BROWSER_CRASH"}:
        result["scroll_stop_reason"] = current["scroll_stop_reason"]
    attempted = success = failed = 0
    enriched_articles: list[dict[str, Any]] = []
    fetch_identities = {
        str(item.get("article_identity") or cnyes_article_identity(item))
        for item in result["article_fetch_queue"][: max(0, cfg.max_article_navigation)]
    }
    for article in result["articles"]:
        item = dict(article)
        identity = str(item.get("article_identity") or cnyes_article_identity(item))
        if identity in fetch_identities:
            if identity not in cache.content_by_identity:
                attempted += 1
                cache.content_by_identity[identity] = _article_content_from_browser(browser, item)
            content_result = cache.content_by_identity[identity]
            item["article_fetch"] = {
                "status": content_result.fetch_status,
                "failure_reason": content_result.failure_reason,
                "final_url": content_result.final_url,
                "method": CNYES_ARTICLE_METHOD,
            }
            if content_result.fetch_status == "success":
                success += 1
                item["content"] = content_result.content
                item["content_status"] = "FULL_CONTENT"
                item["fetch_status"] = "success"
            else:
                failed += 1
                reason = content_result.failure_reason or "ARTICLE_FETCH_FAILED"
                if reason == "PROTECTION_BLOCKED":
                    protection_blocked_count += 1
                elif reason == "BROWSER_TIMEOUT":
                    browser_timeout_count += 1
                elif reason == "BROWSER_CRASH":
                    browser_crash_count += 1
        enriched_articles.append(item)
    result["articles"] = enriched_articles
    result["article_navigation_attempted"] = attempted
    result["article_navigation_success"] = success
    result["article_navigation_failed"] = failed
    result["article_fetch_attempted"] = attempted
    result["article_fetch_success"] = success
    result["article_fetch_failed"] = failed
    result["browser_timeout_count"] = browser_timeout_count
    result["protection_blocked_count"] = protection_blocked_count
    result["browser_crash_count"] = browser_crash_count
    result["usable_for_analysis_count"] = sum(1 for item in enriched_articles if item.get("content_status") == "FULL_CONTENT")
    result["browser_concurrency"] = CNYES_BROWSER_CONCURRENCY
    result["retention_policy"] = {
        "persist_full_article_corpus": False,
        "persisted_fields": [
            "source", "article_id", "title", "published_at", "canonical_url",
            "content_state", "analysis_result", "relevance", "materiality", "fetch_metadata",
        ],
        "full_text_lifecycle": "transient_in_process_for_relevance_materiality_only",
    }
    return result


def extract_article_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html or "")
    return parser.text()[:MAX_CONTENT_CHARS]


def _read_limited_response(response: Any, max_bytes: int = MAX_RESPONSE_BYTES) -> tuple[str, str | None]:
    chunks: list[bytes] = []
    total = 0
    if hasattr(response, "iter_content"):
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                return "", "RESPONSE_TOO_LARGE"
            chunks.append(chunk)
        raw = b"".join(chunks)
        encoding = getattr(response, "encoding", None) or "utf-8"
        return raw.decode(encoding, errors="replace"), None
    text = str(getattr(response, "text", ""))
    if len(text.encode("utf-8")) > max_bytes:
        return "", "RESPONSE_TOO_LARGE"
    return text, None


def _public_ip_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(address.is_global)


def _resolve_host_ips(hostname: str, port: int | None = None) -> list[str]:
    infos = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


def _validate_public_url(url: str, *, resolver: Any = None) -> tuple[bool, str | None, list[str]]:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        return False, "UNTRUSTED_OR_INVALID_URL", []
    hostname = parsed.hostname.strip().lower()
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return False, "PRIVATE_OR_INTERNAL_URL", []
    if _public_ip_address(hostname):
        return True, None, [hostname]
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return False, "PRIVATE_OR_INTERNAL_URL", []

    resolve = resolver or _resolve_host_ips
    try:
        addresses = list(resolve(hostname, parsed.port))
    except Exception:
        return False, "HOST_RESOLUTION_FAILED", []
    if not addresses:
        return False, "HOST_RESOLUTION_FAILED", []
    if any(not _public_ip_address(address) for address in addresses):
        return False, "PRIVATE_OR_INTERNAL_URL", []
    return True, None, sorted(dict.fromkeys(str(address) for address in addresses))


def _request_with_verified_ip(
    client: Any,
    url: str,
    *,
    resolved_ip: str,
    timeout: int,
    headers: dict[str, str],
) -> Any:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    request_headers = dict(headers)
    request_headers["Host"] = hostname if parsed.port is None else f"{hostname}:{parsed.port}"
    if client is not requests:
        return client.get(
            url,
            timeout=timeout,
            headers=request_headers,
            stream=True,
            allow_redirects=False,
            resolved_ip=resolved_ip,
        )
    timeout_config = urllib3.Timeout(connect=timeout, read=timeout)
    if parsed.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            resolved_ip,
            port=port,
            assert_hostname=hostname,
            server_hostname=hostname,
            timeout=timeout_config,
            retries=False,
        )
    else:
        pool = urllib3.HTTPConnectionPool(resolved_ip, port=port, timeout=timeout_config, retries=False)
    response = pool.request("GET", path, headers=request_headers, preload_content=False, redirect=False)
    return _PinnedResponse(status=response.status, headers=response.headers, raw_response=response, url=url)


def _connection_ip_still_verified(
    url: str,
    *,
    verified_addresses: list[str],
    connection_resolver: Any,
) -> tuple[bool, str | None]:
    ok, reason, connection_addresses = _validate_public_url(url, resolver=connection_resolver)
    if not ok:
        return False, reason
    if not set(connection_addresses).issubset(set(verified_addresses)):
        return False, "DNS_REBINDING_DETECTED"
    return True, None


def fetch_article_content(
    url: str,
    *,
    session: Any = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    resolver: Any = None,
    connection_resolver: Any = None,
    max_redirects: int = MAX_REDIRECTS,
) -> ArticleContent:
    ok, reason, addresses = _validate_public_url(str(url or ""), resolver=resolver)
    if not ok:
        return ArticleContent("failed", "", failure_reason=reason)
    if session is None and os.environ.get("STOCK_AI_DISABLE_LIVE_NEWS_NETWORK") == "1":
        return ArticleContent("failed", "", failure_reason="LIVE_NEWS_NETWORK_DISABLED")
    client = session or requests
    current_url = str(url)
    response = None
    try:
        for redirect_count in range(max_redirects + 1):
            ok, reason, addresses = _validate_public_url(current_url, resolver=resolver)
            if not ok:
                return ArticleContent("failed", "", final_url=current_url, failure_reason=reason)
            if connection_resolver is not None:
                ok, reason = _connection_ip_still_verified(
                    current_url,
                    verified_addresses=addresses,
                    connection_resolver=connection_resolver,
                )
                if not ok:
                    return ArticleContent("failed", "", final_url=current_url, failure_reason=reason)
            response = _request_with_verified_ip(
                client,
                current_url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
                resolved_ip=addresses[0],
            )
            status = int(getattr(response, "status_code", 0) or 0)
            if status not in REDIRECT_STATUSES:
                break
            location = str(getattr(response, "headers", {}).get("location") or "")
            close = getattr(response, "close", None)
            if callable(close):
                close()
            if not location:
                return ArticleContent("failed", "", final_url=current_url, failure_reason="REDIRECT_LOCATION_MISSING", http_status=status)
            if redirect_count >= max_redirects:
                return ArticleContent("failed", "", final_url=current_url, failure_reason="TOO_MANY_REDIRECTS", http_status=status)
            next_url = urljoin(current_url, location)
            ok, reason, _addresses = _validate_public_url(next_url, resolver=resolver)
            if not ok:
                return ArticleContent("failed", "", final_url=next_url, failure_reason=reason, http_status=status)
            current_url = next_url
        else:
            return ArticleContent("failed", "", final_url=current_url, failure_reason="TOO_MANY_REDIRECTS")
    except requests.Timeout:
        return ArticleContent("failed", "", failure_reason="REQUEST_TIMEOUT")
    except requests.RequestException as exc:
        return ArticleContent("failed", "", failure_reason=exc.__class__.__name__)
    except urllib3.exceptions.HTTPError as exc:
        return ArticleContent("failed", "", failure_reason=exc.__class__.__name__)
    if response is None:
        return ArticleContent("failed", "", failure_reason="REQUEST_FAILED")
    status = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", current_url) or current_url)
    ok, reason, _addresses = _validate_public_url(final_url, resolver=resolver)
    if not ok:
        return ArticleContent("failed", "", final_url=final_url, failure_reason=reason, http_status=status)
    if status >= 400:
        return ArticleContent("failed", "", final_url=final_url, failure_reason="HTTP_ERROR", http_status=status)
    ctype = str(getattr(response, "headers", {}).get("content-type", "")).lower()
    if ctype and "html" not in ctype and "text" not in ctype:
        return ArticleContent("failed", "", final_url=final_url, failure_reason="UNSUPPORTED_CONTENT_TYPE", http_status=status)
    html, read_error = _read_limited_response(response)
    close = getattr(response, "close", None)
    if callable(close):
        close()
    if read_error:
        return ArticleContent("failed", "", final_url=final_url, failure_reason=read_error, http_status=status)
    text = extract_article_text(html)
    if len(text) < MIN_CONTENT_CHARS:
        return ArticleContent("failed", "", final_url=final_url, failure_reason="EMPTY_OR_UNREADABLE_CONTENT", http_status=status)
    return ArticleContent("success", text, final_url=final_url, http_status=status)


def _aliases(symbol: str, stock_name: str | None) -> list[str]:
    meta = instrument_metadata("TW", symbol)
    values = [symbol, stock_name, meta.get("display_name"), meta.get("adr_symbol")]
    if symbol == "2330":
        values.extend(["台積", "台灣積體電路", "tsmc", "taiwan semiconductor"])
    return [normalize_text(v).lower() for v in dict.fromkeys(v for v in values if normalize_text(v))]


def _contains_alias(text: str, alias: str) -> bool:
    if not alias:
        return False
    if re.search(r"[a-z0-9]", alias):
        return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text) is not None
    return alias in text


def _keyword_level(text: str) -> tuple[str | None, list[str]]:
    matched: list[str] = []
    for level in ("critical", "high", "medium"):
        for keyword in MATERIALITY_KEYWORDS[level]:
            if keyword.lower() in text:
                matched.append(keyword)
        if matched:
            return level, matched[:8]
    return None, []


def _direction(text: str) -> str:
    positive = sum(1 for term in POSITIVE_TERMS if term in text)
    negative = sum(1 for term in NEGATIVE_TERMS if term in text)
    if positive > negative:
        return "bullish"
    if negative > positive:
        return "bearish"
    return "neutral"


def evaluate_news_item(item: dict[str, Any], *, stock_id: str, stock_name: str, content: str) -> dict[str, Any]:
    """Return deterministic relevance/materiality fields or fail-closed reasons."""
    meta = instrument_metadata("TW", str(stock_id))
    title = normalize_text(item.get("headline") or item.get("title"))
    body = normalize_text(content)
    text = f"{title} {body}".lower()
    evidence: dict[str, Any] = {
        "method": "deterministic_tw_news_relevance_materiality_v1",
        "content_available": bool(body),
        "matched_aliases": [],
        "matched_keywords": [],
        "rejection_reason": None,
    }
    if meta.get("instrument_type") == "etf":
        evidence["rejection_reason"] = "ETF_COMPANY_NEWS_NOT_APPLICABLE"
        return evidence
    if not body:
        evidence["rejection_reason"] = "ARTICLE_CONTENT_UNAVAILABLE"
        return evidence
    aliases = [alias for alias in _aliases(str(stock_id), stock_name) if _contains_alias(text, alias)]
    evidence["matched_aliases"] = aliases
    if not aliases:
        evidence["rejection_reason"] = "CONTENT_SYMBOL_EVIDENCE_MISSING"
        return evidence
    if any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in LOW_VALUE_PATTERNS):
        evidence["relevance"] = "low"
        evidence["materiality"] = "low"
        evidence["rejection_reason"] = "LOW_VALUE_METADATA_OR_FORUM_CONTENT"
        return evidence
    level, keywords = _keyword_level(text)
    evidence["matched_keywords"] = keywords
    if not level:
        evidence["relevance"] = "low"
        evidence["materiality"] = "low"
        evidence["rejection_reason"] = "NO_MATERIAL_EVENT_KEYWORD"
        return evidence
    evidence.update({
        "relevance": "high" if len(aliases) >= 2 or str(stock_id) in aliases else "medium",
        "materiality": level,
        "direction": _direction(text),
        "relationship_type": "primary",
        "research_role": "SUPPORTING",
        "summary": normalize_text(body)[:240],
    })
    return evidence


def enrich_news_items(
    items: list[dict[str, Any]],
    *,
    stock_id: str,
    stock_name: str,
    session: Any = None,
    fetch_content: bool = True,
    resolver: Any = None,
    connection_resolver: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    content_cache: dict[str, ArticleContent] = {}
    stats = {
        "schema_version": "tw_news_content_relevance_enrichment_v1",
        "fetch_content": fetch_content,
        "items_total": len(items),
        "content_success": 0,
        "content_failed": 0,
        "evaluated": 0,
        "admission_ready": 0,
        "rejection_reasons": {},
    }
    for raw in items:
        item = dict(raw)
        url = item.get("source_url") or item.get("url") or item.get("link")
        content_result = ArticleContent("skipped", "", failure_reason="CONTENT_FETCH_DISABLED")
        existing_content = normalize_text(item.get("content"))
        if existing_content and item.get("fetch_status") == "success":
            content_result = ArticleContent("success", existing_content[:MAX_CONTENT_CHARS], final_url=str(url) if url else None)
        elif fetch_content and url:
            cache_key = str(url)
            if cache_key not in content_cache:
                content_cache[cache_key] = fetch_article_content(
                    cache_key,
                    session=session,
                    resolver=resolver,
                    connection_resolver=connection_resolver,
                )
            content_result = content_cache[cache_key]
        item["article_fetch"] = {
            "status": content_result.fetch_status,
            "failure_reason": content_result.failure_reason,
            "http_status": content_result.http_status,
            "final_url": content_result.final_url,
        }
        if content_result.fetch_status == "success":
            stats["content_success"] += 1
            item["content"] = content_result.content
        else:
            stats["content_failed"] += 1
        evaluation = evaluate_news_item(item, stock_id=stock_id, stock_name=stock_name, content=content_result.content)
        item["relevance_materiality_evaluation"] = evaluation
        stats["evaluated"] += 1
        if not evaluation.get("rejection_reason"):
            for key in ("relevance", "materiality", "direction", "relationship_type", "research_role", "summary"):
                if evaluation.get(key) is not None:
                    item[key] = evaluation[key]
            item["source_url"] = item.get("source_url") or item.get("link")
            stats["admission_ready"] += 1
        else:
            for key in ("relevance", "materiality"):
                if evaluation.get(key) is not None:
                    item[key] = evaluation[key]
            reason = str(evaluation["rejection_reason"])
            stats["rejection_reasons"][reason] = stats["rejection_reasons"].get(reason, 0) + 1
        enriched.append(item)
    return enriched, stats
