"""Versioned long-lived company knowledge; never daily market observations."""
from __future__ import annotations

from typing import Any

_KNOWLEDGE: dict[tuple[str, str], dict[str, list[str]]] = {
    ("TW", "2330"): {"business": ["晶圓代工"], "products": ["先進製程", "先進封裝"], "customers": ["全球半導體設計公司"], "supply_chain": ["半導體設備", "材料"], "industry": ["半導體"], "long_term_drivers": ["AI與高效能運算"], "macro_sensitivity": ["全球科技資本支出", "匯率"]},
    ("TW", "2337"): {"business": ["記憶體製造"], "products": ["NOR Flash", "ROM"], "customers": ["消費電子與工業客戶"], "supply_chain": ["晶圓材料", "電子終端"], "industry": ["記憶體"], "long_term_drivers": ["庫存循環", "車用電子"], "macro_sensitivity": ["半導體循環", "終端需求"]},
    ("TW", "2305"): {"business": ["影像設備與光通訊"], "products": ["影像掃描設備", "光通訊產品"], "customers": ["企業與設備客戶"], "supply_chain": ["光學零組件", "電子製造"], "industry": ["電子周邊", "光通訊"], "long_term_drivers": ["AI資料中心光通訊需求"], "macro_sensitivity": ["企業資本支出", "電子需求循環"]},
    ("TW", "2353"): {"business": ["資訊硬體與服務"], "products": ["個人電腦", "顯示器", "企業解決方案"], "customers": ["消費者", "企業與教育市場"], "supply_chain": ["電子零組件", "品牌通路"], "industry": ["資訊硬體"], "long_term_drivers": ["商用換機", "AI PC"], "macro_sensitivity": ["消費需求", "企業IT支出"]},
    ("TW", "4743"): {"business": ["新藥研發"], "products": ["生物製劑", "新藥授權"], "customers": ["醫療體系", "授權合作夥伴"], "supply_chain": ["臨床試驗", "生物製造"], "industry": ["生技製藥"], "long_term_drivers": ["臨床里程碑", "國際授權"], "macro_sensitivity": ["監管審查", "研發資金環境"]},
    ("TW", "6873"): {"business": ["再生能源服務"], "products": ["太陽能電站", "能源管理"], "customers": ["企業用電戶", "能源市場"], "supply_chain": ["太陽能模組", "電力工程"], "industry": ["綠能"], "long_term_drivers": ["能源轉型", "企業綠電需求"], "macro_sensitivity": ["利率", "能源政策"]},
    ("TW", "1409"): {"business": ["紡織與材料"], "products": ["聚酯纖維", "工業材料"], "customers": ["紡織與工業客戶"], "supply_chain": ["石化原料", "紡織加工"], "industry": ["紡織"], "long_term_drivers": ["機能材料", "循環材料"], "macro_sensitivity": ["原料價格", "全球消費需求"]},
    ("TW", "00878"): {"business": ["台股高股息ETF"], "products": ["高股息投資組合"], "customers": ["ETF投資人"], "supply_chain": ["成分股與指數規則"], "industry": ["ETF"], "long_term_drivers": ["股息品質", "成分股獲利"], "macro_sensitivity": ["利率", "台股風險偏好"]},
    ("TW", "009816"): {"business": ["台股大型權值ETF"], "products": ["台灣大型股投資組合"], "customers": ["ETF投資人"], "supply_chain": ["成分股與指數規則"], "industry": ["ETF"], "long_term_drivers": ["大型權值股獲利"], "macro_sensitivity": ["台股風險偏好", "外資流向"]},
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
