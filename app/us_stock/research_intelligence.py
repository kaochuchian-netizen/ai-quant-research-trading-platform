"""US research intelligence layer for SEC, fundamentals, earnings, news, and factors.

This module treats SEC/company materials as official evidence and yfinance/Yahoo
as market/reference data. It stores structured metadata only; it never stores full
filings, full transcripts, or full copyrighted articles.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from app.reports.presentation_normalization import normalize_financial_value

TAIPEI = ZoneInfo("Asia/Taipei")
SEC_BASE = "https://data.sec.gov"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
SEC_USER_AGENT = "StockAIResearch/1.0 contact=research@example.invalid"
SOURCE_TAXONOMY = {
    "sec_edgar": {"source_name": "SEC EDGAR", "source_type": "regulatory_filing", "source_tier": 1, "official_source": True},
    "company_ir": {"source_name": "Company Investor Relations", "source_type": "company_official", "source_tier": 1, "official_source": True},
    "yfinance": {"source_name": "Yahoo Finance / yfinance", "source_type": "market_reference", "source_tier": 2, "official_source": False},
    "secondary_news": {"source_name": "Secondary News Metadata", "source_type": "secondary_news", "source_tier": 3, "official_source": False},
}
SUPPORTED_SEC_FORMS = ("10-K", "10-Q", "8-K", "20-F", "6-K")
RESEARCH_FACTOR_VERSION = "us_research_factor_v1"
RESEARCH_WEIGHT_VERSION = "us_research_weight_v1"
OFFICIAL_SOURCE_REGISTRY = {
    "AAPL": {"investor_relations_url": "https://investor.apple.com/", "official_newsroom_url": "https://www.apple.com/newsroom/"},
    "MSFT": {"investor_relations_url": "https://www.microsoft.com/en-us/Investor/", "official_newsroom_url": "https://news.microsoft.com/"},
    "NVDA": {"investor_relations_url": "https://investor.nvidia.com/", "official_newsroom_url": "https://nvidianews.nvidia.com/"},
    "TSLA": {"investor_relations_url": "https://ir.tesla.com/", "official_newsroom_url": "https://www.tesla.com/blog"},
    "AMD": {"investor_relations_url": "https://ir.amd.com/", "official_newsroom_url": "https://www.amd.com/en/newsroom.html"},
    "GOOGL": {"investor_relations_url": "https://abc.xyz/investor/", "official_newsroom_url": "https://blog.google/"},
    "AMZN": {"investor_relations_url": "https://ir.aboutamazon.com/", "official_newsroom_url": "https://www.aboutamazon.com/news"},
    "META": {"investor_relations_url": "https://investor.fb.com/", "official_newsroom_url": "https://about.fb.com/news/"},
}


def now_taipei() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        number = float(value)
    except Exception:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return round(number, 4)


def provenance(source_key: str, *, retrieved_at: str | None = None, published_at: str | None = None, reference: str | None = None, quality: str = "available") -> dict[str, Any]:
    base = dict(SOURCE_TAXONOMY[source_key])
    base.update({
        "retrieved_at": retrieved_at or now_taipei(),
        "published_at": published_at,
        "source_reference": reference,
        "source_quality": quality,
        "freshness_status": "current" if published_at else "metadata_available",
    })
    return base


@dataclass
class SECClient:
    user_agent: str = SEC_USER_AGENT
    timeout: int = 10
    min_interval_seconds: float = 0.12

    def __post_init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"})
        self._ticker_map: dict[str, dict[str, Any]] | None = None
        self._last_request = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request = time.monotonic()

    def _get_json(self, url: str) -> dict[str, Any] | None:
        self._wait()
        try:
            response = self._session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                return None
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def ticker_to_cik(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper().strip()
        if self._ticker_map is None:
            data = self._get_json("https://www.sec.gov/files/company_tickers.json") or {}
            self._ticker_map = {}
            for row in data.values():
                if isinstance(row, dict) and row.get("ticker"):
                    self._ticker_map[str(row["ticker"]).upper()] = row
        row = (self._ticker_map or {}).get(symbol)
        if not row:
            return {"ok": False, "symbol": symbol, "cik": None, "missing_reason": "ticker_not_found_in_sec_company_tickers", "provenance": provenance("sec_edgar", quality="missing")}
        cik = str(row.get("cik_str", "")).zfill(10)
        return {"ok": True, "symbol": symbol, "cik": cik, "company_title": row.get("title"), "provenance": provenance("sec_edgar", reference="company_tickers.json")}

    def recent_filings(self, symbol: str) -> dict[str, Any]:
        mapping = self.ticker_to_cik(symbol)
        if not mapping.get("ok"):
            return {"ok": False, "symbol": symbol, "cik": mapping.get("cik"), "supported_forms": list(SUPPORTED_SEC_FORMS), "filings": [], "latest_annual_report": None, "latest_quarterly_report": None, "recent_8k_items": [], "missing_reason": mapping.get("missing_reason"), "provenance": mapping.get("provenance")}
        cik = mapping["cik"]
        data = self._get_json(f"{SEC_BASE}/submissions/CIK{cik}.json")
        if not data:
            return {"ok": False, "symbol": symbol, "cik": cik, "supported_forms": list(SUPPORTED_SEC_FORMS), "filings": [], "latest_annual_report": None, "latest_quarterly_report": None, "recent_8k_items": [], "missing_reason": "sec_submissions_unavailable", "provenance": provenance("sec_edgar", reference=f"CIK{cik}.json", quality="unavailable")}
        recent = data.get("filings", {}).get("recent", {}) if isinstance(data.get("filings"), dict) else {}
        forms = recent.get("form", []) or []
        dates = recent.get("filingDate", []) or []
        periods = recent.get("reportDate", []) or []
        accessions = recent.get("accessionNumber", []) or []
        primary_docs = recent.get("primaryDocument", []) or []
        filings = []
        for idx, form in enumerate(forms[:80]):
            if form not in SUPPORTED_SEC_FORMS:
                continue
            accession = accessions[idx] if idx < len(accessions) else None
            accession_nodash = str(accession or "").replace("-", "")
            url = f"{SEC_ARCHIVES_BASE}/{int(cik)}/{accession_nodash}/{primary_docs[idx]}" if accession and idx < len(primary_docs) and primary_docs[idx] else None
            filings.append({
                "form": form,
                "filing_date": dates[idx] if idx < len(dates) else None,
                "reporting_period": periods[idx] if idx < len(periods) else None,
                "accession": accession,
                "filing_url": url,
                "title": f"{form} filing metadata",
                "provenance": provenance("sec_edgar", published_at=dates[idx] if idx < len(dates) else None, reference=accession),
            })
        latest_annual = next((f for f in filings if f["form"] in {"10-K", "20-F"}), None)
        latest_quarterly = next((f for f in filings if f["form"] in {"10-Q", "6-K"}), None)
        recent_8k = [f for f in filings if f["form"] == "8-K"][:3]
        return {"ok": True, "symbol": symbol, "cik": cik, "company_title": data.get("name") or mapping.get("company_title"), "supported_forms": list(SUPPORTED_SEC_FORMS), "filings": filings[:12], "latest_annual_report": latest_annual, "latest_quarterly_report": latest_quarterly, "recent_8k_items": recent_8k, "provenance": provenance("sec_edgar", reference=f"CIK{cik}.json")}


class USResearchIntelligenceBuilder:
    def __init__(self, sec_client: SECClient | None = None) -> None:
        self.sec_client = sec_client or SECClient()
        self._ticker_cache: dict[str, Any] = {}

    def _ticker(self, symbol: str) -> Any:
        if symbol not in self._ticker_cache:
            self._ticker_cache[symbol] = yf.Ticker(symbol)
        return self._ticker_cache[symbol]

    def official_sources(self, symbol: str, sec: dict[str, Any]) -> dict[str, Any]:
        registry = OFFICIAL_SOURCE_REGISTRY.get(symbol.upper(), {})
        sec_page = f"https://www.sec.gov/edgar/browse/?CIK={sec.get('cik')}" if sec.get("cik") else None
        return {
            "symbol": symbol,
            "investor_relations_url": registry.get("investor_relations_url"),
            "official_newsroom_url": registry.get("official_newsroom_url"),
            "sec_company_page": sec_page,
            "company_official_items": [],
            "official_press_releases": [],
            "investor_presentations": [],
            "earnings_materials": [],
            "provenance": provenance("company_ir", quality="configured" if registry else "registry_missing"),
            "missing_reason": None if registry else "official_source_registry_missing_for_symbol",
        }

    def fundamentals(self, symbol: str) -> dict[str, Any]:
        retrieved_at = now_taipei()
        metrics: dict[str, dict[str, Any]] = {}
        missing = []
        try:
            ticker = self._ticker(symbol)
            info = ticker.get_info() or {}
        except Exception:
            info = {}
        metric_map = {
            "revenue": (info.get("totalRevenue"), "yfinance_totalRevenue", "currency"),
            "gross_margin": (info.get("grossMargins"), "yfinance_grossMargins", "percent"),
            "operating_margin": (info.get("operatingMargins"), "yfinance_operatingMargins", "percent"),
            "net_income": (info.get("netIncomeToCommon"), "yfinance_netIncomeToCommon", "currency"),
            "eps_diluted": (info.get("trailingEps"), "yfinance_trailingEps", "per_share"),
            "operating_cash_flow": (info.get("operatingCashflow"), "yfinance_operatingCashflow", "currency"),
            "free_cash_flow": (info.get("freeCashflow"), "yfinance_freeCashflow", "currency"),
            "cash_and_equivalents": (info.get("totalCash"), "yfinance_totalCash", "currency"),
            "total_debt": (info.get("totalDebt"), "yfinance_totalDebt", "currency"),
            "debt_to_equity": (info.get("debtToEquity"), "yfinance_debtToEquity", "ratio"),
            "shares_outstanding": (info.get("sharesOutstanding"), "yfinance_sharesOutstanding", "shares"),
            "revenue_growth_yoy": (info.get("revenueGrowth"), "yfinance_revenueGrowth", "percent"),
        }
        for name, (value, ref, unit) in metric_map.items():
            number = safe_float(value)
            if number is None:
                missing.append(name)
            normalized = normalize_financial_value(
                number, unit=unit,
                currency=(info.get("financialCurrency") or "USD") if unit in {"currency", "per_share"} else None,
                scale=1, source="yfinance_reference",
            )
            metrics[name] = {
                "value": number,
                "currency": (info.get("financialCurrency") or "USD") if unit in {"currency", "per_share"} else None,
                "unit": unit,
                "normalization": normalized,
                "period": "latest_available",
                "period_type": "ttm_or_latest_reference",
                "source": "yfinance_reference",
                "official_source": False,
                "data_quality": "available" if number is not None else "missing",
                "missing_reason": None if number is not None else "not_available_from_reference_payload",
                "provenance": provenance("yfinance", retrieved_at=retrieved_at, reference=ref, quality="available" if number is not None else "missing"),
            }
        trend = "資料不足"
        growth = metrics["revenue_growth_yoy"]["value"]
        margin = metrics["operating_margin"]["value"]
        if growth is not None and margin is not None:
            trend = "成長與獲利同步改善" if growth > 0 and margin > 0 else "成長或獲利承壓" if growth < 0 or margin < 0 else "中性"
        return {
            "schema_version": "us_fundamentals_v1",
            "symbol": symbol,
            "metrics": metrics,
            "comparison": {
                "latest_quarter_vs_prior_year_quarter": "資料待接：需要 XBRL/official statement period parser",
                "latest_annual_vs_prior_annual": "資料待接：需要 XBRL/official statement period parser",
                "trend_direction": trend,
                "margin_expansion_or_contraction": "資料待接" if margin is None else ("margin_positive" if margin > 0 else "margin_pressure"),
                "cash_flow_quality": "available" if metrics["operating_cash_flow"]["value"] is not None else "資料待接",
                "balance_sheet_risk": "available" if metrics["total_debt"]["value"] is not None else "資料待接",
            },
            "source_policy": "SEC filings are official; yfinance metrics are reference fallback until official XBRL parser is connected.",
            "missing_fields": missing,
        }

    def earnings(self, symbol: str) -> dict[str, Any]:
        retrieved_at = now_taipei()
        try:
            ticker = self._ticker(symbol)
            info = ticker.get_info() or {}
            cal = ticker.calendar
        except Exception:
            info, cal = {}, None
        next_earnings = None
        try:
            if isinstance(cal, dict):
                next_earnings = cal.get("Earnings Date") or cal.get("Earnings High") or cal.get("Earnings Low")
            elif hasattr(cal, "empty") and not cal.empty:
                next_earnings = str(cal.iloc[0].to_dict())
        except Exception:
            next_earnings = None
        latest_earnings_date = info.get("mostRecentQuarter") or info.get("lastFiscalYearEnd")
        eps_actual = safe_float(info.get("trailingEps"))
        revenue_actual = safe_float(info.get("totalRevenue"))
        return {
            "schema_version": "us_earnings_guidance_v1",
            "symbol": symbol,
            "earnings_status": "available_reference" if latest_earnings_date or next_earnings else "unavailable",
            "latest_earnings": {
                "reported_date": str(latest_earnings_date) if latest_earnings_date else None,
                "actual_revenue": revenue_actual,
                "actual_eps": eps_actual,
                "source_class": "company_reported_or_reference_payload",
                "official_source": False,
                "provenance": provenance("yfinance", retrieved_at=retrieved_at, reference="mostRecentQuarter/trailingEps/totalRevenue", quality="available" if latest_earnings_date or eps_actual or revenue_actual else "missing"),
            },
            "next_earnings": {"expected_date": str(next_earnings) if next_earnings else None, "before_after_market": None, "source_class": "external_calendar_reference", "official_source": False, "missing_reason": None if next_earnings else "next_earnings_date_unavailable"},
            "guidance_direction": "unavailable",
            "company_guidance": {"available": False, "guidance_raised_maintained_lowered": None, "source": None, "missing_reason": "verified_company_guidance_not_connected"},
            "analyst_consensus": {"available": False, "source_class": "third_party_estimate", "missing_reason": "consensus_not_used_without_clear_source"},
            "earnings_surprise": None,
            "management_outlook": "資料待接：未取得可驗證公司展望原文",
            "event_risk_level": "medium" if next_earnings else "low",
            "provenance": provenance("yfinance", retrieved_at=retrieved_at, reference="calendar/info"),
        }

    def classify_news(self, item: dict[str, Any]) -> str:
        text = (item.get("english_headline") or "").lower()
        rules = [
            ("earnings", ["earnings", "quarter", "results"]),
            ("guidance", ["guidance", "outlook", "forecast"]),
            ("product_launch", ["launch", "unveils", "introduces"]),
            ("regulatory/legal", ["lawsuit", "sec", "regulator", "antitrust"]),
            ("M&A", ["acquire", "merger", "deal"]),
            ("management_change", ["ceo", "cfo", "appoints", "resigns"]),
            ("capital_expenditure", ["capex", "factory", "data center"]),
            ("supply_chain", ["supplier", "supply"]),
            ("competition", ["rival", "competition"]),
            ("analyst_commentary", ["analyst", "price target", "rating"]),
            ("macro/sector", ["fed", "inflation", "sector", "nasdaq"]),
        ]
        for label, keywords in rules:
            if any(k in text for k in keywords):
                return label
        return "other"

    def material_news(self, symbol: str, news_items: list[dict[str, Any]]) -> dict[str, Any]:
        seen = set()
        output = []
        for item in news_items[:6]:
            headline = item.get("english_headline")
            if not headline:
                continue
            key = re.sub(r"[^a-z0-9]+", " ", headline.lower()).strip()[:90]
            if key in seen:
                continue
            seen.add(key)
            event_type = self.classify_news(item)
            output.append({
                "event_type": event_type,
                "dedup_key": key,
                "recency_bucket": "recent_reference",
                "english_headline": headline,
                "chinese_translation": item.get("chinese_translation") or ("英文標題摘要：" + headline),
                "english_summary": "Headline-only metadata; no full copyrighted article stored.",
                "chinese_summary": "僅保存標題層級資訊，未複製完整文章。",
                "headline_only": True,
                "vocabulary": vocabulary_for_event(event_type),
                "investment_reading": item.get("investment_reading") or "新聞作為事件脈絡，不單獨決定評等。",
                "official_source": bool(item.get("official_source")),
                "source_tier": 1 if item.get("official_source") else 3,
                "provenance": provenance("secondary_news", published_at=item.get("published_at"), reference=item.get("source"), quality="headline_only"),
            })
        return {"schema_version": "us_material_news_v1", "symbol": symbol, "items": output, "deduplicated_count": len(output), "missing_reason": None if output else "no_verified_material_news", "no_full_article_stored": True}

    def research_factors(self, technical: dict[str, Any], market_context: dict[str, Any], fundamentals: dict[str, Any], earnings: dict[str, Any], sec: dict[str, Any], news: dict[str, Any]) -> dict[str, Any]:
        metrics = fundamentals.get("metrics", {})
        revenue_growth = (metrics.get("revenue_growth_yoy") or {}).get("value")
        op_margin = (metrics.get("operating_margin") or {}).get("value")
        fcf = (metrics.get("free_cash_flow") or {}).get("value")
        debt = (metrics.get("total_debt") or {}).get("value")
        cash = (metrics.get("cash_and_equivalents") or {}).get("value")
        def factor(name: str, score: float | None, evidence: str, refs: list[str], quality: str = "available") -> dict[str, Any]:
            return {"name": name, "score": score, "evidence": evidence, "source_references": refs, "data_quality": quality, "freshness": "current_or_latest_available", "missing_data_handling": "neutral_score_or_confidence_penalty_when_missing"}
        factors = [
            factor("earnings_quality", 55 if earnings.get("latest_earnings", {}).get("actual_eps") is not None else 50, "EPS/reference earnings availability checked.", ["earnings.latest_earnings"]),
            factor("growth_momentum", 65 if revenue_growth and revenue_growth > 0 else 45 if revenue_growth and revenue_growth < 0 else 50, "Revenue growth reference checked.", ["fundamentals.revenue_growth_yoy"], "missing" if revenue_growth is None else "available"),
            factor("margin_quality", 65 if op_margin and op_margin > 0.15 else 50 if op_margin is not None else None, "Operating margin reference checked.", ["fundamentals.operating_margin"], "missing" if op_margin is None else "available"),
            factor("cash_flow_quality", 62 if fcf and fcf > 0 else 45 if fcf and fcf < 0 else None, "Free cash flow reference checked.", ["fundamentals.free_cash_flow"], "missing" if fcf is None else "available"),
            factor("balance_sheet_strength", 60 if cash and (not debt or cash > debt * 0.3) else 45 if debt else None, "Cash/debt reference checked.", ["fundamentals.cash_and_equivalents", "fundamentals.total_debt"], "missing" if cash is None and debt is None else "available"),
            factor("guidance_direction", 50, "Verified company guidance unavailable; neutral with confidence penalty.", ["earnings.company_guidance"], "missing"),
            factor("official_event_signal", 58 if sec.get("latest_quarterly_report") or sec.get("latest_annual_report") else 45, "Recent SEC official filing metadata checked.", ["sec.latest_quarterly_report", "sec.latest_annual_report"], "available" if sec.get("ok") else "missing"),
            factor("news_event_signal", 55 if news.get("items") else 50, "Material news headline metadata checked and deduplicated.", ["material_news.items"], "missing" if not news.get("items") else "available"),
            factor("market_environment", market_context.get("market_environment_score"), "SPY/QQQ/VIX/SOXX reference environment checked.", ["market_context"]),
            factor("technical_state", technical.get("technical_score"), "MA/RSI/MACD/Bollinger state checked.", ["technical"]),
            factor("volatility_risk", 45 if technical.get("volatility_state") == "high" else 55 if technical.get("volatility_state") == "low" else 50, "Volatility state influences risk.", ["technical.volatility_state"]),
        ]
        valid_scores = [f["score"] for f in factors if isinstance(f.get("score"), (int, float))]
        missing_count = len([f for f in factors if f.get("data_quality") == "missing" or f.get("score") is None])
        research_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else None
        if research_score is None:
            rating, confidence = "資料不足", None
        elif research_score >= 65:
            rating, confidence = "research_positive", max(35, min(75, research_score - missing_count * 3))
        elif research_score <= 42:
            rating, confidence = "research_risk", max(25, min(65, research_score))
        else:
            rating, confidence = "research_neutral", max(30, min(70, research_score - missing_count * 2))
        return {"schema_version": "us_research_factors_v1", "research_factor_version": RESEARCH_FACTOR_VERSION, "research_weight_version": RESEARCH_WEIGHT_VERSION, "research_score": research_score, "research_rating": rating, "research_confidence": round(confidence, 1) if confidence is not None else None, "missing_factor_count": missing_count, "factors": factors, "research_rationale": "US-specific deterministic factors combine official SEC metadata, fundamentals references, earnings/guidance separation, news events, market context, technical state, volatility, and data completeness."}

    def build_for_symbol(self, symbol: str, technical: dict[str, Any], market_context: dict[str, Any], news_items: list[dict[str, Any]]) -> dict[str, Any]:
        sec = self.sec_client.recent_filings(symbol)
        fundamentals = self.fundamentals(symbol)
        earnings = self.earnings(symbol)
        official = self.official_sources(symbol, sec)
        news = self.material_news(symbol, news_items)
        factors = self.research_factors(technical, market_context, fundamentals, earnings, sec, news)
        return {"schema_version": "us_research_intelligence_v1", "symbol": symbol, "source_taxonomy": SOURCE_TAXONOMY, "sec": sec, "fundamentals": fundamentals, "earnings": earnings, "official_sources": official, "material_news": news, "research_factors": factors, "provenance_required": True, "copyright_policy": "metadata_and_short_summaries_only_no_full_articles_or_filings"}


def vocabulary_for_event(event_type: str) -> list[dict[str, str]]:
    base = {
        "earnings": ("earnings release", "財報公告"),
        "guidance": ("revenue guidance", "營收展望"),
        "product_launch": ("product launch", "產品發表"),
        "regulatory/legal": ("regulatory scrutiny", "監管審查"),
        "analyst_commentary": ("price target", "目標價"),
    }
    term, zh = base.get(event_type, ("material event", "重大事件"))
    return [{"term": term, "meaning_zh": zh, "usage_note": "Use as event context, not as a standalone trading instruction.", "example_en": f"The {term} may affect near-term volatility.", "example_zh": f"{zh}可能影響短期波動。"}]
