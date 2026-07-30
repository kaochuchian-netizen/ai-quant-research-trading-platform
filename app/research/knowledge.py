"""Versioned long-lived company knowledge; never daily market observations."""
from __future__ import annotations

from typing import Any

_KNOWLEDGE: dict[tuple[str, str], dict[str, list[str]]] = {
    ("TW", "2330"): {"business": ["晶圓代工"], "products": ["先進製程", "先進封裝"], "customers": ["全球半導體設計公司"], "supply_chain": ["半導體設備", "材料"], "industry": ["半導體"], "long_term_drivers": ["AI與高效能運算"], "macro_sensitivity": ["全球科技資本支出", "匯率"]},
    ("TW", "2337"): {"business": ["記憶體製造"], "products": ["NOR Flash", "ROM"], "customers": ["消費電子與工業客戶"], "supply_chain": ["晶圓材料", "電子終端"], "industry": ["記憶體"], "long_term_drivers": ["庫存循環", "車用電子"], "macro_sensitivity": ["半導體循環", "終端需求"]},
    ("US", "AAPL"): {"business": ["消費科技與服務"], "products": ["iPhone", "Mac", "Services"], "customers": ["消費者", "企業"], "supply_chain": ["亞洲製造", "半導體"], "industry": ["科技硬體"], "long_term_drivers": ["裝置生態系", "服務營收"], "macro_sensitivity": ["消費需求", "美元", "利率"]},
    ("US", "NVDA"): {"business": ["加速運算"], "products": ["GPU", "Networking"], "customers": ["雲端服務商", "企業"], "supply_chain": ["晶圓代工", "先進封裝", "記憶體"], "industry": ["半導體"], "long_term_drivers": ["AI資本支出"], "macro_sensitivity": ["科技資本支出", "出口管制"]},
}


def get_knowledge(market: str, symbol: str) -> dict[str, Any]:
    key = (market.upper(), symbol.upper())
    dimensions = _KNOWLEDGE.get(key)
    empty = {name: [] for name in ("business", "products", "customers", "supply_chain", "industry", "long_term_drivers", "macro_sensitivity")}
    return {
        "schema_version": "research_knowledge_context_v1", "knowledge_version": "2026-07-30.v1",
        "market": key[0], "symbol": key[1], "status": "AVAILABLE" if dimensions else "PARTIAL",
        "dimensions": dimensions or empty, "dynamic_daily_data": False,
        "provenance": "versioned_repository_knowledge",
    }


def validate_knowledge(value: dict[str, Any]) -> list[str]:
    errors = []
    if value.get("dynamic_daily_data") is not False: errors.append("knowledge_must_be_long_lived")
    if value.get("status") == "AVAILABLE" and not any(value.get("dimensions", {}).values()): errors.append("available_knowledge_empty")
    if any(key in value for key in ("current_price", "observed_at", "daily_return")): errors.append("daily_data_in_knowledge")
    return errors
