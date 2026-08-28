#!/usr/bin/env python3
"""AI-DEV-226 Phase B TW four-window summary, continuity and ledger gate."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import render_tw_window_report
from app.reports.tw_evidence_regression import append_records, build_regression_records, canonical_event_identity, validate_record
from app.reports.tw_four_window_decision import build_observed_card
from app.reports.tw_human_summary import build_tw_human_summary, validate_tw_human_summary
from app.reports.tw_pre_open_quality import canonical_tw_event_identity, news_contract, technical_contract
from app.reports.tw_prediction_explainability import project_tw_prediction_card


def require(value: bool, message: str) -> None:
    if not value: raise AssertionError(message)


def setup(symbol: str = "2330", direction: str = "bullish", *, no_trade: bool = False) -> dict:
    low, high, current = (580.0, 620.0, 600.0)
    return {
        "market": "TW", "window": "pre_open_0700", "symbol": symbol, "stock_id": symbol,
        "name": "台積電", "stock_name": "台積電", "trading_date": "2026-08-27",
        "setup_id": f"setup-{symbol}", "entry_readiness": "no_trade" if no_trade else "watch",
        "actionable": False, "no_trade": no_trade, "plan_status": "no_trade" if no_trade else "watch",
        "strategy_type": "no_trade" if no_trade else "range", "predicted_direction": direction,
        "predicted_low": low, "predicted_high": high, "target_price": 610.0, "current_price": current,
        "reference_price": current, "entry_low": 595, "entry_high": 605, "stop_level": 575,
        "target_1": 625, "target_2": 640, "entry_condition": "量價確認後觀察", "invalidation_condition": "跌破 580",
        "technical_summary": "震盪偏多", "market_context": "電子權值盤前中性偏多", "chip_summary": "外資資料待確認",
        "technical_data": {"analysis_eligible": True, "history_bars": 30, "required_bars": 20, "direction": direction, "source": "fixture", "latest_date": "2026-08-27", "freshness_status": "fresh"},
        "strategies": {"research_position": {"stance": "neutral"}, "daily_tactical": {"setup_type": "range", "direction": direction, "formal_trade_plan": not no_trade, "technical_factors": {"volume_ma20": 1000}}},
        "prediction_snapshot_v2": {"schema_version": "tw_prediction_snapshot_v2", "prediction_identity": f"pred-{symbol}", "prediction_status": "evaluable", "direction_forecast": direction, "range_forecast": {"low": low, "high": high}, "confidence": 68.0, "point_forecast": {"price": 610.0, "owner": "tw_prediction_engine", "is_execution_target": False, "is_support": False, "is_resistance": False}},
        "key_reasons": ["價格結構維持", "量能等待確認"], "main_risk": "跌破預測下界",
        "news_candidate_records": [
            {"candidate_id": "n1", "headline": "公司公告先進製程展望", "publisher": "MOPS", "published_at": "2026-08-27T06:00:00+08:00", "source_reference": "https://mops.example/a", "symbol_attributed": True, "primary_subject": symbol, "relationship_type": "primary", "relevance": "high", "materiality": "high", "freshness": "fresh", "source_tier": 1, "source_quality": "high", "admission_status": "ADMITTED", "research_role": "SUPPORTING", "counted_in_synthesis": True, "evidence_id": "ev1"},
            {"candidate_id": "n2", "headline": "舊市場雜訊", "publisher": "secondary", "published_at": "2026-08-20T06:00:00+08:00", "source_reference": "https://secondary.example/b", "symbol_attributed": False, "relevance": "low", "materiality": "low", "admission_status": "REJECTED", "rejection_reason": "SYMBOL_ATTRIBUTION_FAILED"},
        ],
        "news_evidence": {"status": "available", "evidence": [{"news_id": "n1", "headline": "公司公告先進製程展望", "publisher": "MOPS", "published_at": "2026-08-27T06:00:00+08:00", "source_url": "https://mops.example/a", "source_tier": 1, "official_source": True, "freshness": "fresh", "relevance": "high", "materiality": "high", "direction": "bullish", "direction_status": "EVALUATED", "summary": "官方展望提供需求能見度。"}], "evidence_funnel": {"count_semantics": "EXACT", "stages": {"DISCOVERED": 2, "RETRIEVED": 2, "NORMALIZED": 2, "SYMBOL_ATTRIBUTED": 1, "RELEVANT": 1, "MATERIAL": 1, "QUALITY_QUALIFIED": 1, "FRESH": 1, "DEDUPLICATED": 1, "ADMITTED": 1}}},
        "data_gaps": [], "missing_fields": [], "data_status": "complete",
        "chip_result": {"status": "available", "source": "TWSE_T86", "as_of": "2026-08-27", "foreign_net": 1000, "investment_trust_net": 100, "dealer_net": -10},
    }


def lifecycle(seed: dict) -> list[dict]:
    first = project_tw_prediction_card(seed, "pre_open_0700", strict=False)
    first["tw_human_decision_summary_v1"] = build_tw_human_summary(first, "pre_open_0700")
    q13 = {"open": 600, "high": 612, "low": 594, "close": 608, "total_volume": 900, "snapshot_time": "2026-08-27T13:05:00+08:00", "source": "fixture"}
    mid = build_observed_card(window="intraday_1305", setup_card=first, quote=q13, trading_date="2026-08-27", generated_at="2026-08-27T13:05:10+08:00", source_snapshot_id="snap-0700", source_revision=1, source_payload_hash="hash-0700")
    mid["current_snapshot_id"] = "snap-1305"; mid["prior_card"] = first
    mid["tw_human_decision_summary_v1"] = build_tw_human_summary(mid, "intraday_1305")
    q1335 = {**q13, "high": 615, "close": 611, "snapshot_time": "2026-08-27T13:35:00+08:00"}
    close = build_observed_card(window="pre_close_1335", setup_card=first, quote=q1335, trading_date="2026-08-27", generated_at="2026-08-27T13:35:10+08:00", source_snapshot_id="snap-0700", source_revision=1, source_payload_hash="hash-0700", prior_card=mid, lifecycle_timeline=mid.get("lifecycle_timeline"))
    close.update({"current_snapshot_id": "snap-1335", "parent_source_snapshot_id": "snap-1305", "prior_card": mid, "closing_risk": "尾盤量能不足"})
    close["tw_human_decision_summary_v1"] = build_tw_human_summary(close, "pre_close_1335")
    q15 = {**q1335, "high": 618, "low": 590, "close": 613, "snapshot_time": "2026-08-27T15:00:00+08:00"}
    review = build_observed_card(window="post_close_1500", setup_card=first, quote=q15, trading_date="2026-08-27", generated_at="2026-08-27T15:00:10+08:00", source_snapshot_id="snap-0700", source_revision=1, source_payload_hash="hash-0700", prior_card=close, lifecycle_timeline=close.get("lifecycle_timeline"))
    review["current_snapshot_id"] = "snap-1500"; review["prior_card"] = close
    review["tw_human_decision_summary_v1"] = build_tw_human_summary(review, "post_close_1500")
    return [first, mid, close, review]


def main() -> int:
    checks: dict[str, str] = {}
    rows = lifecycle(setup())
    windows = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
    for row, window in zip(rows, windows):
        summary = row["tw_human_decision_summary_v1"]
        require(not validate_tw_human_summary(summary), f"invalid summary {window}: {validate_tw_human_summary(summary)}")
        require(summary["decision_authority"] is False, "presentation gained decision authority")
    s07, s13, s1335, s15 = [row["tw_human_decision_summary_v1"] for row in rows]
    require(s07["direction"] == "BULLISH" and s07["forecast_low"] <= s07["forecast_target"] <= s07["forecast_high"], "07 forecast hierarchy invalid")
    require(len(s07["key_reasons"]) <= 4 and 1 <= len(s07["important_news"]) <= 4, "07 bounds invalid")
    checks["human_summary_0700"] = "PASS"
    require(s13["origin_prediction_identity"] == s07["origin_prediction_identity"] and s13["range_position"] == "WITHIN_RANGE", "13:05 lineage/delta invalid")
    missing = copy.deepcopy(s13); missing["origin_prediction_identity"] = None; require("source_lineage" in validate_tw_human_summary(missing), "missing lineage accepted")
    checks["delta_1305"] = "PASS"
    require(s1335["parent_snapshot_identity"] == "snap-1305" and s1335["current_snapshot_identity"] == "snap-1335", "13:35 identities collapsed")
    stale = copy.deepcopy(s1335); stale["current_snapshot_identity"] = stale["parent_snapshot_identity"]; require("stale_snapshot" in validate_tw_human_summary(stale), "stale 13:35 accepted")
    checks["delta_1335"] = "PASS"
    require(s15["actual_close"] == 613 and s15["forecast_errors"]["midpoint"] is not None and s15["tactical_outcome"] is not None, "15:00 learning incomplete")
    no_trade_rows = lifecycle(setup("2337", "bearish", no_trade=True))
    no_trade = no_trade_rows[-1]["tw_human_decision_summary_v1"]
    require(no_trade["tactical_outcome"] == "no_trade" and no_trade["range_result"] not in {None, "not_applicable"}, "no-trade suppressed prediction evaluation")
    checks["learning_1500"] = "PASS"

    base_news = {"items": [
        {"headline": "台積電調整資本支出展望 - Reuters", "publisher": "Reuters", "published_at": "2026-08-27T05:00:00+08:00", "source_url": "https://r.example/1", "symbol_attributed": True, "primary_subject": "2330", "relationship_type": "primary", "relevance": "high", "materiality": "high"},
        {"headline": "台積電調整資本支出展望 - Bloomberg", "publisher": "Bloomberg", "published_at": "2026-08-27T05:05:00+08:00", "source_url": "https://b.example/2", "symbol_attributed": True, "primary_subject": "2330", "relationship_type": "primary", "relevance": "high", "materiality": "high"},
    ]}
    contracted = news_contract(base_news, generated_at="2026-08-27T07:00:00+08:00")
    require(contracted["evidence_funnel"]["stages"]["ADMITTED"] == 1, "syndicated event not collapsed")
    missing_materiality = copy.deepcopy(base_news); missing_materiality["items"] = [dict(base_news["items"][0])]; missing_materiality["items"][0].pop("materiality")
    require(news_contract(missing_materiality, generated_at="2026-08-27T07:00:00+08:00")["evidence_funnel"]["rejection_reasons"].get("MATERIALITY_NOT_EVALUATED") == 1, "missing materiality admitted")
    missing_attr = copy.deepcopy(base_news); missing_attr["items"] = [dict(base_news["items"][0])]; missing_attr["items"][0].pop("symbol_attributed"); missing_attr["items"][0].pop("relationship_type")
    require(news_contract(missing_attr, generated_at="2026-08-27T07:00:00+08:00")["evidence_funnel"]["rejection_reasons"].get("SYMBOL_ATTRIBUTION_FAILED") == 1, "missing attribution admitted")
    contextual = dict(base_news["items"][0], relationship_type="macro", contextual_role="CONTEXT", direction="bullish")
    contextual_contract = news_contract({"items": [contextual]}, generated_at="2026-08-27T07:00:00+08:00")
    require(contextual_contract["evidence"][0]["direction"] == "unavailable" and contextual_contract["evidence"][0]["contextual_role"] == "CONTEXT", "context established company direction")
    event_a = canonical_tw_event_identity(base_news["items"][0]); event_b = canonical_tw_event_identity(base_news["items"][1]); require(event_a == event_b, "publisher-independent identity unstable")
    distinct = dict(base_news["items"][1]); distinct["headline"] = "台積電新增美國廠量產時程"; require(canonical_tw_event_identity(distinct) != event_a, "distinct update collapsed")
    checks["news_integrity"] = "PASS"

    ledger_card = copy.deepcopy(rows[0]); ledger_card["news_candidate_records"] = setup()["news_candidate_records"]
    records = build_regression_records(card=ledger_card, window="pre_open_0700", trading_date="2026-08-27", generated_at="2026-08-27T07:00:00+08:00")
    require(any(row["record_kind"] == "news" and row["admission_status"] == "ADMITTED" for row in records), "admitted news missing")
    require(any(row["record_kind"] == "news" and row["admission_status"] == "REJECTED" for row in records), "rejected news missing")
    require(any(row["record_kind"] == "chip_flow" for row in records) and any(row["record_kind"] == "technical" for row in records), "chip/technical linkage missing")
    require(all(not validate_record(row) for row in records), "invalid ledger record")
    missing_chip = copy.deepcopy(ledger_card); missing_chip["chip_result"] = {"status": "missing", "source": "TWSE", "foreign_net": 0}
    missing_records = build_regression_records(card=missing_chip, window="pre_open_0700", trading_date="2026-08-27", generated_at="2026-08-27T07:00:00+08:00")
    require(any(row["record_kind"] == "chip_flow" and row.get("value") is None and row["admission_status"] == "REJECTED" for row in missing_records), "missing zero became neutral")
    with tempfile.TemporaryDirectory(prefix="ai226-ledger-") as tmp:
        first = append_records(records, Path(tmp)); second = append_records(records, Path(tmp))
        require(first["written"] == len(records) and second["existing"] == len(records), "append-only replay failed")
    require(all(not ({"article_body", "full_text", "raw_html"} & set(row)) for row in records), "copyright body persisted")
    checks["ledger_and_chip_safety"] = "PASS"
    stale_technical = technical_contract({"trading_date": "2026-08-27", "direction": "bullish", "technical_factors": {"history_days": 30, "ma20": 100, "latest_date": "2026-08-01"}})
    require(stale_technical["freshness"] == "stale" and stale_technical["analysis_eligible"] is False, "stale technical evidence admitted")
    checks["technical_freshness_and_linkage"] = "PASS"

    payloads = {}
    keys = {"pre_open_0700": "structured_pre_open_cards", "intraday_1305": "structured_intraday_cards", "pre_close_1335": "structured_pre_close_cards", "post_close_1500": "structured_review_cards"}
    for row, window in zip(rows, windows): payloads[window] = {"market": "TW", "window": window, "effective_trading_date": "2026-08-27", keys[window]: [row], "cards": [row]}
    html = "".join(render_tw_window_report(window, payloads[window]) for window in windows)
    for token in ("今日決策摘要", "方向", "信心", "預測目標", "預估區間", "相較前一時段", "13:05 基準", "13:35 現況", "預測與學習摘要", "證據學習"):
        require(token in html, f"renderer token missing: {token}")
    require("data-decision-authority=\"false\"" in html, "renderer authority unsafe")
    checks["renderer_four_window_hierarchy"] = "PASS"

    changed = subprocess.run(["git", "diff", "--name-only", "origin/main...HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    protected_prefixes = ("app/us_stock/", "app/strategy/", "app/database/", "scripts/orchestrator/activate_google_drive", "scripts/orchestrator/upload_google_drive")
    require(not any(path.startswith(protected_prefixes) for path in changed), f"protected path changed: {changed}")
    checks["protected_contracts"] = "PASS"
    print(json.dumps({"schema_version": "ai_dev_226_phase_b_validator_v1", "status": "PASS", "checks": checks, "check_count": len(checks), "production_rerun": False, "notifications_sent": False, "trading": False, "production_db_write": False, "oauth_drive_changed": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
