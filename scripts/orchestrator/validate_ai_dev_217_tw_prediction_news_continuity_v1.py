#!/usr/bin/env python3
"""AI-DEV-217 TW prediction/news/four-window product gate."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import render_tw_window_report
from app.reports.tw_four_window_decision import (
    aggregate_cards,
    build_observed_card,
    evaluate_post_close,
)
from app.reports.tw_prediction_explainability import (
    classify_tw_news,
    finalized_tw_news_projection,
    post_close_quality_review,
    project_tw_prediction_card,
    validate_interval,
    validate_news_surface_parity,
)
from app.research.tw_daily_generator import build_tw_daily_research
from app.research.tw_production_intelligence_v2 import evaluate_prediction


def _raises(fn, code: str) -> bool:
    try:
        fn()
    except ValueError as exc:
        return code in str(exc)
    return False


def _news(headline: str, *, publisher: str, tier: int, direction: str = "bullish", official: bool = False) -> dict:
    return {
        "headline": headline, "publisher": publisher, "source_tier": tier,
        "direction": direction, "direction_status": "EVALUATED",
        "freshness": "fresh", "materiality": "high", "official_source": official,
        "published_at": "2026-08-14T06:30:00+08:00", "source_url": "https://example.test/news",
    }


def setup(symbol: str, *, direction: str = "bullish") -> dict:
    low, high = ((125.0, 135.0) if symbol == "2337" else (69.0, 72.6))
    current = 130.0 if symbol == "2337" else 70.5
    return {
        "market": "TW", "window": "pre_open_0700", "symbol": symbol,
        "stock_id": symbol, "name": "旺宏" if symbol == "2337" else "泓德能源",
        "stock_name": "旺宏" if symbol == "2337" else "泓德能源",
        "trading_date": "2026-08-14", "setup_id": f"setup-{symbol}",
        "entry_readiness": "watch", "actionable": False, "plan_status": "watch",
        "strategy_type": "range", "predicted_direction": direction,
        "predicted_low": low, "predicted_high": high, "current_price": current,
        "entry_low": low, "entry_high": high, "stop_level": low - 2,
        "target_1": high, "target_2": high + 3, "entry_condition": f"站上 {high}",
        "invalidation_condition": f"跌破 {low}", "chase_risk": "low", "event_risk": "low",
        "technical_summary": "偏多趨勢" if direction == "bullish" else "偏空趨勢",
        "technical_data": {"analysis_eligible": True, "history_bars": 30, "required_bars": 20, "direction": direction, "source": "fixture"},
        "market_context": "市場區間整理", "chip_summary": "籌碼待確認",
        "strategies": {"daily_tactical": {"setup_type": "range", "direction": direction,
            "technical_factors": {"volume_ma20": 1000}, "playbook": {
                "entry_condition": f"站上 {high}", "invalidation_condition": f"跌破 {low}"}}},
        "prediction_snapshot_v2": {"schema_version": "tw_prediction_snapshot_v2",
            "prediction_identity": f"twpred-{symbol}-20260814", "prediction_status": "evaluable",
            "direction_forecast": direction, "range_forecast": {"low": low, "high": high},
            "confidence": 68.0},
        "news_evidence": {"status": "available", "evidence": [_news(
            "公司公告重大股東持股異動" if symbol == "2337" else "同學風向與貼文摘要 - 股市爆料同學會 - CMoney",
            publisher="TWSE" if symbol == "2337" else "CMoney", tier=1 if symbol == "2337" else 3,
            official=symbol == "2337")], "evidence_funnel": {"count_semantics": "EXACT", "stages": {
                "DISCOVERED": 1, "RETRIEVED": 1, "NORMALIZED": 1, "SYMBOL_ATTRIBUTED": 1,
                "RELEVANT": 1, "MATERIAL": 1, "QUALITY_QUALIFIED": 1, "FRESH": 1,
                "DEDUPLICATED": 1, "ADMITTED": 1}}},
        "data_gaps": [], "missing_fields": [], "data_status": "complete",
    }


def lifecycle(seed: dict) -> list[dict]:
    first = project_tw_prediction_card(seed, "pre_open_0700")
    quote_1305 = {"open": seed["current_price"], "high": seed["predicted_high"] - .5,
        "low": seed["predicted_low"] + .5, "close": seed["current_price"] + .5,
        "total_volume": 900, "snapshot_time": "2026-08-14T13:05:00+08:00", "source": "fixture"}
    mid = build_observed_card(window="intraday_1305", setup_card=first, quote=quote_1305,
        trading_date="2026-08-14", generated_at="2026-08-14T13:05:10+08:00",
        source_snapshot_id="snap-0700", source_revision=1, source_payload_hash="hash-0700")
    quote_1335 = {**quote_1305, "close": seed["current_price"] + .8,
        "snapshot_time": "2026-08-14T13:35:00+08:00"}
    close = build_observed_card(window="pre_close_1335", setup_card=first, quote=quote_1335,
        trading_date="2026-08-14", generated_at="2026-08-14T13:35:10+08:00",
        source_snapshot_id="snap-0700", source_revision=1, source_payload_hash="hash-0700",
        prior_card=mid, lifecycle_timeline=mid["lifecycle_timeline"])
    quote_1500 = {**quote_1335, "close": seed["current_price"] + 1,
        "snapshot_time": "2026-08-14T15:00:00+08:00"}
    review = build_observed_card(window="post_close_1500", setup_card=first, quote=quote_1500,
        trading_date="2026-08-14", generated_at="2026-08-14T15:00:10+08:00",
        source_snapshot_id="snap-0700", source_revision=1, source_payload_hash="hash-0700",
        prior_card=close, lifecycle_timeline=close["lifecycle_timeline"])
    return [first, mid, close, review]


def chromium_check(html: str) -> dict:
    from app.dashboard.visual_evidence_archive import _browser_render
    with tempfile.TemporaryDirectory(prefix="ai217-") as raw:
        root = Path(raw)
        page_path = root / "fixture.html"
        page_path.write_text("<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><style>body{font-family:'Noto Sans CJK TC',sans-serif}</style></head><body data-market='TW' data-window='pre_open_0700' data-effective-trading-date='2026-08-14' data-snapshot-id='fixture' data-revision='1' data-payload-hash='fixture-hash'>" + html + "</body></html>", encoding="utf-8")
        png, pdf = root / "fixture.png", root / "fixture.pdf"
        rendered = _browser_render(page_path, png, pdf, timeout_ms=45_000)
        text = rendered["text"]
        font_loaded = rendered["font_diagnostics"]["font_loaded"]
        return {"ok": png.stat().st_size > 1000 and pdf.stat().st_size > 1000 and pdf.read_bytes().startswith(b"%PDF") and "今日短線預期" in text and "預測區間" in text and rendered["pdf_error"] is None,
            "font_loaded": font_loaded, "glyph_diagnostics": rendered["font_diagnostics"], "png_size": png.stat().st_size, "pdf_size": pdf.stat().st_size,
            "output_root_removed_after_context": True}


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    checks["reversed_2337_interval_fail_closed"] = _raises(lambda: validate_interval(135.0, 126.25), "interval_reversed")
    invalid_snapshot = {"prediction_status": "evaluable", "direction_forecast": "bullish", "range_forecast": {"low": 135.0, "high": 126.25}}
    checks["reversed_interval_not_evaluated"] = _raises(lambda: evaluate_prediction(invalid_snapshot, {"open": 140, "high": 144.5, "low": 134.5, "close": 137}), "interval_reversed")

    conflict = setup("2337")
    conflict["reasoning"] = "trend bearish"
    checks["same_horizon_trend_conflict_rejected"] = _raises(lambda: project_tw_prediction_card(conflict, "pre_open_0700"), "same_horizon")
    conflict["signal_conflict"] = True
    allowed = project_tw_prediction_card(conflict, "pre_open_0700")
    checks["explicit_cross_horizon_conflict_allowed"] = allowed["prediction_presentation_v1"]["signal_conflict"] is True

    chains = {symbol: lifecycle(setup(symbol)) for symbol in ("2337", "6873")}
    for symbol, rows in chains.items():
        ids = [row["prediction_presentation_v1"]["prediction_id"] for row in rows]
        checks[f"{symbol}_four_window_lineage"] = len(set(ids)) == 1
        checks[f"{symbol}_intraday_progress"] = rows[1]["prediction_presentation_v1"]["intraday_prediction_status"]["status"] == "on_track"
        checks[f"{symbol}_pre_close_expectation"] = bool(rows[2]["prediction_presentation_v1"]["close_expectation"])
        checks[f"{symbol}_post_close_continuity"] = rows[3]["prediction_evaluation_v2"]["evaluation_status"] == "evaluated"
    p6873 = chains["6873"][0]["prediction_presentation_v1"]
    checks["6873_coherent_hierarchy"] = p6873["direction"] == "bullish" and p6873["expected_path"] == "震盪偏多" and p6873["daily_tactical"]["formal_trade_plan"] is False

    cmoney_a = classify_tw_news(_news("CPI 符合預期 準備噴…..！ - 股市爆料同學會 - CMoney", publisher="CMoney", tier=3), symbol="009816", instrument_type="etf")
    cmoney_b = classify_tw_news(_news("泓德能源同學風向與貼文摘要 - 股市爆料同學會 - CMoney", publisher="CMoney", tier=3), symbol="6873")
    checks["cmoney_009816_sentiment_only"] = cmoney_a["tw_news_tier"] == 4 and not cmoney_a["can_establish_research_direction"] and cmoney_a["direction"] == "unavailable"
    checks["cmoney_6873_sentiment_only"] = cmoney_b["tw_news_tier"] == 4 and not cmoney_b["can_establish_research_direction"]
    etf = classify_tw_news(_news("00878 公告成分股調整", publisher="TWSE", tier=1, official=True), symbol="00878", instrument_type="etf")
    checks["etf_specific_constituent_event"] = etf["instrument_news_contract"] == "etf_specific" and etf["etf_event_type"] == "constituent_change"
    official = finalized_tw_news_projection(setup("2337"))
    checks["official_positive_recall"] = official["selected_count"] == 1 and official["state"] == "AVAILABLE"
    low_tier = finalized_tw_news_projection(setup("6873"))
    checks["tier4_not_institutional_research"] = low_tier["selected_count"] == 0 and low_tier["directional_count"] == 0
    mutation = setup("2337")
    mutation["news_selected_count"] = 0
    checks["dual_news_truth_mutation_rejected"] = "news_summary_count_mismatch" in validate_news_surface_parity(mutation)

    payloads = {}
    for index, window in enumerate(("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")):
        cards = [chains[symbol][index] for symbol in ("2337", "6873")]
        key = {"pre_open_0700": "structured_pre_open_cards", "intraday_1305": "structured_intraday_cards", "pre_close_1335": "structured_pre_close_cards", "post_close_1500": "structured_review_cards"}[window]
        payloads[window] = {"market": "TW", "window": window, "effective_trading_date": "2026-08-14", "tracking_stock_count": 2, key: cards, "cards": cards}
    research = build_tw_daily_research("pre_open_0700", payloads["pre_open_0700"], payloads["pre_open_0700"]["cards"], [])
    note_by_symbol = {row["symbol"]: row for row in research["research_notes"]}
    checks["rre_uses_finalized_news_truth"] = note_by_symbol["2337"]["research_evidence_observability"]["news"]["stages"]["RRE_USED"] == 1 and note_by_symbol["6873"]["research_evidence_observability"]["news"]["stages"]["RRE_USED"] == 0
    checks["directionless_low_tier_no_direction"] = research["morning_or_window_brief"]["market_narrative"].startswith("今日研究主線：")

    review = post_close_quality_review(payloads["post_close_1500"]["cards"])
    checks["post_close_quality_review"] = all(review.get(key) for key in ("best_prediction", "worst_prediction", "biggest_range_error", "tomorrow_carry_forward_question"))
    summary = aggregate_cards("post_close_1500", payloads["post_close_1500"]["cards"])
    checks["aggregate_quality_review_exposed"] = summary.get("prediction_quality_review_v1", {}).get("schema_version") == "tw_post_close_prediction_quality_v1"
    html = "".join(render_tw_window_report(window, payloads[window]) for window in payloads)
    required = ("今日短線預期", "方向 / 路徑", "預測區間", "支撐 / 壓力", "轉強條件", "轉弱 / 失效", "目前進度", "Research view", "Daily Tactical")
    checks["renderer_first_screen_contract"] = all(value in html for value in required)
    visual = chromium_check(html)
    checks["real_chromium_png_pdf"] = bool(visual["ok"])
    checks["cjk_font_loaded"] = bool(visual.get("font_loaded"))
    checks["decision_ownership_preserved"] = all(row["prediction_presentation_v1"]["decision_ownership_preserved"] for rows in chains.values() for row in rows)
    details.update({"lineage": {symbol: [row["prediction_presentation_v1"] for row in rows] for symbol, rows in chains.items()}, "news": {"official": official, "tier4": low_tier}, "post_close_quality": review, "visual": visual})
    return {"task_id": "AI-DEV-217", "contract_version": "ai_dev_217_tw_prediction_news_continuity_v1", "ok": all(checks.values()), "checks": checks, "errors": [key for key, value in checks.items() if not value], "details": details,
        "safety": {"production_pipeline": False, "notifications": False, "trading": False, "scheduler": False, "production_db": False, "secrets": False, "immutable_history": False, "strategy_changed": False, "prediction_weights_changed": False, "decision_rules_changed": False}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
