#!/usr/bin/env python3
"""Deterministic AI-DEV-193 contract validation (no network or writes)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.market.historical_price_loader import MAX_KBARS_LOOKBACK_DAYS, bounded_kbars_date_window
import analysis.news_analysis_engine as news_engine
from app.reports.presentation_normalization import concise_news_summary
from app.reports.tw_pre_open_quality import market_confidence, news_contract, public_reason, technical_contract
from app.reports.tw_pre_open_structured import aggregate, build_card, render_email, render_line

NATURAL = ROOT / "artifacts/archive/window_snapshots/tw/pre_open_0700/2026-07-27/revision-0001.json"
RAW_MARKERS = ("limited history below", "trend confirmation unavailable", "reward/risk below", "confidence downgraded")


def _tactical(history: int, *, direction: str = "neutral") -> dict:
    return {
        "setup_type": "no_trade", "direction": direction, "action": "暫不操作", "data_quality": "limited" if history < 20 else "partial",
        "technical_factors": {"history_days": history, "history_start": "2026-06-01", "history_end": "2026-07-24", "latest_date": "2026-07-24", "ma20": None if history < 20 else 100, "source": "canonical_historical_csv"},
        "entry_zone": None, "stop_invalidation": None, "target_1": None, "target_2": None,
        "reward_risk": None, "chase_risk": "low", "event_risk": "unknown",
        "risk_reasons": ["INSUFFICIENT_HISTORY", "RR_BELOW_THRESHOLD"] if history < 20 else ["SETUP_NOT_CONFIRMED"],
        "reasons": ["歷史資料不足最低需求"] if history < 20 else ["交易條件尚未確認"],
        "playbook": {"entry_condition": "use deterministic entry_zone when present"},
    }


def _card(symbol: str, history: int, news=None) -> dict:
    return build_card(
        symbol=symbol, name=f"測試{symbol}", trading_date="2026-07-27",
        indicator={"date": "2026-07-24", "close": 100, "summary": "盤整"}, news=news,
        score={"action": "暫不操作", "score": 20}, tactical=_tactical(history), generated_at="2026-07-27T07:00:00+08:00",
    )


def validate() -> dict:
    checks: dict[str, bool] = {}
    insufficient = _card("2330", 12)
    checks["history_insufficient_is_ineligible"] = insufficient["technical_data"]["analysis_eligible"] is False
    checks["history_insufficient_direction_unavailable"] = insufficient["technical_data"]["direction"] == "unavailable" and insufficient["technical_summary"] == "無法判定"
    checks["gap_missing_chase_unavailable"] = insufficient["chase_risk"] == "unavailable"
    sufficient = _card("2337", 60, [{"headline": "公司公告營運更新", "publisher": "MOPS", "published_at": "2026-07-27T06:10:00+08:00", "url": "mops:2337:1", "direction": "bullish", "official_source": True}])
    checks["history_sufficient_is_eligible"] = sufficient["technical_data"]["analysis_eligible"] is True
    checks["news_evidence_traceable"] = sufficient["news_status"] == "available" and len(sufficient["news_items"]) == 1 and sufficient["news_items"][0]["source_tier"] == 1
    checks["news_direction_has_confidence"] = sufficient["news_direction"] == "bullish" and isinstance(sufficient["news_confidence"].get("score"), int)
    unavailable = news_contract({"analysis": "目前沒有可用新聞", "items": [], "retrieval": {"lookback_hours": 72, "sources_attempted": ["GOOGLE_NEWS_RSS"], "sources_succeeded": [], "sources_failed": [{"source": "GOOGLE_NEWS_RSS", "reason": "NO_RESULT"}, {"source": "MOPS", "reason": "SOURCE_NOT_CONFIGURED"}, {"source": "TWSE", "reason": "SOURCE_NOT_CONFIGURED"}, {"source": "COMPANY_IR", "reason": "SOURCE_NOT_CONFIGURED"}], "failure_reason": "NO_RESULT"}}, generated_at="2026-07-27T07:00:00+08:00")
    checks["no_news_has_diagnostics"] = unavailable["source_quality"] == "not_applicable" and unavailable["retrieval"]["failure_reason"] == "NO_RESULT" and unavailable["retrieval"]["sources_attempted"] == ["GOOGLE_NEWS_RSS"]
    checks["unconfigured_official_sources_not_claimed_attempted"] = all(item["reason"] == "SOURCE_NOT_CONFIGURED" for item in unavailable["retrieval"]["sources_failed"] if item["source"] in {"MOPS", "TWSE", "COMPANY_IR"})
    original_fetch, original_generate = news_engine.fetch_stock_news, news_engine.generate_analysis
    try:
        news_engine.fetch_stock_news = lambda *_args, **_kwargs: [{"title": "測試公告", "source": "測試媒體", "published": "2026-07-27T06:00:00+08:00", "link": "https://example.invalid/news"}]
        news_engine.generate_analysis = lambda _prompt: "消息面方向：偏多"
        bundle = news_engine.analyze_news("2337", "旺宏", include_evidence=True)
    finally:
        news_engine.fetch_stock_news, news_engine.generate_analysis = original_fetch, original_generate
    checks["producer_preserves_news_evidence"] = bundle["items"][0]["title"] == "測試公告" and bundle["retrieval"]["sources_attempted"] == ["GOOGLE_NEWS_RSS"]
    checks["news_unavailable_public_semantics"] = concise_news_summary(insufficient)["source_quality"].startswith("不適用")
    cards = [insufficient, sufficient]
    summary = aggregate(cards, ["2330", "2337"])
    checks["coverage_separates_quote_history_trend"] = summary["coverage"]["quote_available"]["available"] == 2 and summary["coverage"]["history_sufficient"]["available"] == 1 and summary["coverage"]["trend_confirmed"]["available"] == 1
    checks["market_confidence_has_components"] = set(summary["market_confidence"]["components"]) == {"technical", "overnight_adr", "chip", "news", "gap", "event_risk"}
    payload = {"effective_trading_date": "2026-07-27", "tracking_symbols": ["2330", "2337"], "structured_pre_open_cards": cards, "pre_open_summary": summary}
    public = render_line(payload, "https://example.invalid") + render_email(payload, "https://example.invalid")
    checks["channel_canonical_coverage"] = "技術可執行 1/2" in public and "整體信心" in public
    checks["public_internal_wording_removed"] = not any(marker in public.lower() for marker in RAW_MARKERS)
    checks["reason_localization"] = public_reason("reward/risk below 0.8 threshold") == "報酬風險比低於最低門檻"
    checks["history_window_not_truncated_to_30_days"] = MAX_KBARS_LOOKBACK_DAYS >= 180 and bounded_kbars_date_window("2026-01-01", "2026-07-27")[0] == "2026-01-29"
    audit = []
    if NATURAL.exists():
        snap = json.loads(NATURAL.read_text(encoding="utf-8"))
        for card in snap.get("payload", {}).get("structured_pre_open_cards", []):
            tactical = ((card.get("strategies") or {}).get("daily_tactical") or {})
            audit.append({"symbol": card.get("symbol"), "history_bars": (tactical.get("technical_factors") or {}).get("history_days"), "analysis_eligible_under_v1": technical_contract(tactical)["analysis_eligible"]})
    checks["natural_history_audit_complete"] = not audit or len(audit) == 9
    return {"ok": all(checks.values()), "checks": checks, "natural_2026_07_27_history_audit": audit, "safety": {"network": False, "writes": False, "notifications": False, "trading": False}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
