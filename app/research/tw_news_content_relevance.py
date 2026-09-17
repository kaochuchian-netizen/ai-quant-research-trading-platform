"""Read-only TW news article extraction and deterministic relevance scoring.

This module is intentionally dependency-light and policy-first.  It can enrich
Google News RSS candidates with readable article content when the article page
is openly accessible.  If content cannot be fetched or parsed, the candidate is
left without relevance/materiality so downstream admission remains fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urlparse

import requests

from app.market.instrument_master import instrument_metadata

USER_AGENT = "stock-ai-news-evidence/1.0"
MAX_CONTENT_CHARS = 6000
MIN_CONTENT_CHARS = 80
REQUEST_TIMEOUT_SECONDS = 6
MAX_RESPONSE_BYTES = 1_000_000

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


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


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


def fetch_article_content(url: str, *, session: Any = None, timeout: int = REQUEST_TIMEOUT_SECONDS) -> ArticleContent:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ArticleContent("failed", "", failure_reason="UNTRUSTED_OR_INVALID_URL")
    client = session or requests
    try:
        response = client.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, stream=True, allow_redirects=True)
    except requests.Timeout:
        return ArticleContent("failed", "", failure_reason="REQUEST_TIMEOUT")
    except requests.RequestException as exc:
        return ArticleContent("failed", "", failure_reason=exc.__class__.__name__)
    status = int(getattr(response, "status_code", 0) or 0)
    final_url = str(getattr(response, "url", url))
    final = urlparse(final_url)
    if final.scheme not in {"http", "https"} or not final.netloc:
        return ArticleContent("failed", "", final_url=final_url, failure_reason="UNTRUSTED_REDIRECT_URL", http_status=status)
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
        if fetch_content and url:
            cache_key = str(url)
            if cache_key not in content_cache:
                content_cache[cache_key] = fetch_article_content(cache_key, session=session)
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
