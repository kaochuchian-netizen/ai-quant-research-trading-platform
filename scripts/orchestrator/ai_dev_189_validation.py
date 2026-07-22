"""Deterministic, no-network fixtures shared by AI-DEV-189 validators."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.us_stock.premarket_decision import (
    build_premarket_card,
    canonical_event_risk,
    normalize_market_context,
    normalize_premarket_quote,
    separate_sec_news,
    summarize_premarket,
    validate_premarket_contract,
)

NY = ZoneInfo("America/New_York")
REFERENCE = datetime(2026, 7, 22, 8, 0, tzinfo=NY)


def quote(price: float | None = 205.4) -> dict:
    return {"previous_close": 203.2, "pre_market_price": price, "pre_market_time": "2026-07-22T07:58:00-04:00" if price is not None else None, "pre_market_volume": 180000, "market_data_source": "deterministic-provider"}


def context() -> dict:
    rows = {"SPY": (600.0, 602.4), "QQQ": (500.0, 503.5), "SOXX": (250.0, 251.5)}
    items = {}
    for symbol, (previous, price) in rows.items():
        items[symbol] = {"premarket": {"previous_close": previous, "price": price, "change_pct": round((price / previous - 1) * 100, 4), "timestamp": "2026-07-22T07:58:00-04:00", "source": "deterministic-provider", "freshness": "fresh", "availability": "available"}}
    return {"items": items}


def research(*, news: bool = True, material_sec: bool = False) -> dict:
    return {
        "earnings": {"event_risk_level": "low"},
        "sec": {"ok": True, "recent_8k_items": ([{"form": "8-K", "filing_date": "2026-07-21", "item": "2.02", "materiality": "material", "summary": "Results", "source": "SEC EDGAR"}] if material_sec else [])},
        "material_news": {"items": ([{"english_headline": "Premarket demand improves", "source": "Major Wire", "published_at": "2026-07-22T07:30:00-04:00", "direction": "bullish", "relevance": "high", "confidence": "medium", "investment_reading": "維持優先級"}] if news else [])},
    }


def base_card(symbol: str = "NVDA", *, rr: float = 1.34, confidence: float = 39.0, direction: str = "mildly_bullish", action: str = "突破確認後偏多") -> dict:
    return {"symbol": symbol, "name": symbol, "daily_tactical_summary": {"reward_risk_ratio": rr, "confidence": confidence, "direction": direction, "action": action, "chase_risk": "low", "entry_zone": {"low": 204, "high": 208}, "stop_reference": 199.65, "target_zone_1": {"low": 213, "high": 216}}}


def build(symbol: str = "NVDA", **kwargs) -> dict:
    news = kwargs.pop("news", True)
    card = base_card(symbol, **kwargs)
    research_payload = research(news=news)
    news_items = research_payload["material_news"]["items"]
    return build_premarket_card(card, quote(), research_payload, news_items, context(), REFERENCE)


def result(name: str, checks: dict[str, bool]) -> dict:
    failed = sorted(key for key, value in checks.items() if not value)
    return {"validator": name, "ok": not failed, "checks": checks, "failed": failed, "safety": {"network": False, "production_write": False, "email_attempted": False, "line_attempted": False, "trading": False}}


def emit(payload: dict, pretty: bool) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True))
    return 0 if payload.get("ok") else 1
