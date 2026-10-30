"""Bounded, public Google News RSS fallback for US company headlines.

Only metadata is retrieved. All candidates pass the existing US news funnel;
RSS does not authorize attribution or trading direction.
"""
from __future__ import annotations

from datetime import timezone
from app.loaders.batch_universe import query
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

RSS_URL = "https://news.google.com/rss/search"
MAX_RSS_ITEMS = 30


def fetch_us_google_news_rss(symbol: str, company: dict | None = None, *, source_domain: str | None = None) -> tuple[list[dict], str | None]:
    """Return source-labeled candidates and an error type, never invented items."""
    try:
        search = query(company or {"symbol":str(symbol).upper()})
    except ValueError:
        return [], "COMPANY_IDENTITY_UNRESOLVED_OR_AMBIGUOUS"
    if source_domain:
        if source_domain != "news.cnyes.com": return [], "SOURCE_NOT_ALLOWLISTED"
        search += " site:" + source_domain
    try:
        response = requests.get(
            RSS_URL,
            params={"q": f"({search}) when:4d", "hl": "en-US", "gl": "US", "ceid": "US:en"},
            timeout=8,
            headers={"User-Agent": "StockAIResearch/1.0"},
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        rows = []
        for node in root.findall("./channel/item")[:MAX_RSS_ITEMS]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            published = (node.findtext("pubDate") or "").strip()
            source = node.find("source")
            publisher = (source.text or "").strip() if source is not None else ""
            try:
                timestamp = parsedate_to_datetime(published)
                if timestamp.tzinfo is None:
                    continue
                published = timestamp.astimezone(timezone.utc).isoformat()
            except (ValueError, TypeError, OverflowError):
                continue
            if not (title and link and publisher):
                continue
            rows.append({
                "title": title,
                "link": link,
                "pubDate": published,
                "publisher": publisher,
                "contentType": "STORY",
                "discovery_channel": "CNYES" if source_domain else "GOOGLE_NEWS_RSS",
                "company_identity": company,
            })
        return rows, None
    except (requests.RequestException, ElementTree.ParseError, ValueError) as exc:
        return [], type(exc).__name__
