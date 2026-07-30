#!/usr/bin/env python3
"""Deterministic semantic gate for AI-DEV-198 TW Decision Intelligence V2."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.reports.decision_intelligence_v4 import project_decision_intelligence_v4
from app.dashboard.multi_market_dashboard import _decision_intelligence_v4_html
from app.runtime.operations_provenance import build_operations_provenance
from app.reports.tw_decision_intelligence_v2 import (
    DIMENSIONS,
    build_tw_decision_intelligence_v2,
    compact_tw_v2_lines,
    validate_tw_decision_intelligence_v2,
)
from scripts.orchestrator.tw_four_window_validation_fixture import payloads
from scripts.orchestrator.approved_pre_open_delivery import _append_tw_v2


def _enrich(source: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    fixtures = copy.deepcopy(source)
    sectors = ["半導體", "記憶體", "AI 伺服器", "生技", "傳產", "光通訊", "ETF", "紡織", "ETF"]
    for window, payload in fixtures.items():
        payload.update({
            "snapshot_id": f"ai198-{window}", "revision": 1,
            "source_payload_hash": f"hash-{window}",
            "market_breadth": {"weighted_index": "improving", "otc": "mixed"},
            "market_context": {"macro": {"state": "neutral"}, "etf": {"state": "available"}},
        })
        cards = payload.get("cards") or []
        for index, card in enumerate(cards):
            card["sector"] = sectors[index]
            card["technical_summary"] = ["量價轉強", "區間整理", "動能轉弱"][index % 3]
            card["fundamental_context"] = f"{sectors[index]} 個股既有基本面摘要 {index + 1}"
            card["event_summary"] = "本批次無重大事件" if index % 2 else "產業需求證據更新"
            card["confidence"] = 72 - index * 4
            card["risk_reasons"] = [f"風險證據 {index + 1}"] if index in {2, 5, 7} else []
            card["next_session_action"] = f"下一批次確認 {sectors[index]} 量價與風險"
            card["news_status"] = "available" if index in {0, 1, 5} else "unavailable"
            if card["news_status"] == "available":
                card["news_evidence"] = {"primary_evidence": {"headline": f"{sectors[index]} 事件 {index + 1}"}}
                card["news_summary"] = "新聞證據偏多" if index != 1 else "新聞與技術證據衝突"
            technical = card.get("technical_data") if isinstance(card.get("technical_data"), dict) else {}
            technical.update({"analysis_eligible": index != 8, "direction": ["bullish", "neutral", "bearish"][index % 3], "history_bars": 60, "source": "fixture_daily"})
            card["technical_data"] = technical
            if index == 1:
                card["direction"] = "neutral"
            if window == "intraday_1305":
                card["trigger_status"] = "triggered" if index in {0, 3} else "invalidated" if index == 2 else "not_triggered"
            if window == "pre_close_1335":
                card["overnight_action"] = ["hold", "watch", "exit", "reduce", "no_trade"][index % 5]
            if window == "post_close_1500":
                card["prediction_evaluation"] = {"range_result": ["hit", "partial_hit", "miss"][index % 3]}
                card["trade_outcome"] = ["win", "open_at_close", "loss", "not_triggered", "no_trade"][index % 5]
    return fixtures


def validate() -> dict[str, Any]:
    errors: list[str] = []
    details: dict[str, Any] = {"windows": {}, "negative_tests": {}}
    fixtures = _enrich(payloads())
    identities: dict[str, str] = {}
    for window, payload in fixtures.items():
        bundle = build_tw_decision_intelligence_v2(window, payload)
        semantic = validate_tw_decision_intelligence_v2(bundle)
        if semantic:
            errors.extend(f"{window}:{item}" for item in semantic)
        rows = bundle["stock_intelligence"]
        symbols = {row["symbol"] for row in rows}
        if len(rows) != 9 or len(symbols) != 9:
            errors.append(f"{window}:symbol_partition")
        if any(set(row["coverage"]) != set(DIMENSIONS) for row in rows):
            errors.append(f"{window}:coverage_contract")
        if not any(item["status"] == "MISSING" for row in rows for item in row["coverage"].values()):
            errors.append(f"{window}:missing_truthfulness_fixture")
        if any(item["status"] == "MISSING" and "降低研究信心" not in item["decision_impact"] for row in rows for item in row["coverage"].values()):
            errors.append(f"{window}:missing_not_neutral")
        if any(row["coverage"]["news"]["status"] == "AVAILABLE" and not row["coverage"]["news"].get("evidence") for row in rows):
            errors.append(f"{window}:news_coverage_without_evidence")
        if len({row["opportunity_projection_score"] for row in rows}) < 3:
            errors.append(f"{window}:stock_differentiation")
        if set(bundle["rankings"]) != {"opportunity", "research", "risk"}:
            errors.append(f"{window}:rank_inventory")
        if any(set(values) != symbols for values in bundle["rankings"].values()):
            errors.append(f"{window}:rank_partition")
        if any("不修改既有策略排序" not in row["projection_disclaimer"] for row in rows):
            errors.append(f"{window}:ranking_boundary")
        if any(not row.get("decision_category_label") for row in rows):
            errors.append(f"{window}:category_localization")
        if not bundle["market_intelligence"]["market_narrative"]:
            errors.append(f"{window}:market_narrative")
        pm = bundle["pm_daily_summary"]
        if not all(pm.get(key) for key in ("one_line", "largest_opportunity", "largest_risk", "most_worth_tracking", "next_observation")):
            errors.append(f"{window}:pm_summary")
        if len(compact_tw_v2_lines(bundle)) != 4:
            errors.append(f"{window}:compact_summary")
        projection = project_decision_intelligence_v4("TW", window, payload)
        if projection.get("tw_decision_identity") != bundle["decision_identity"]:
            errors.append(f"{window}:projection_identity")
        if projection.get("tw_decision_intelligence_v2") != bundle:
            errors.append(f"{window}:canonical_projection")
        html = _decision_intelligence_v4_html("TW", window, payload)
        if bundle["decision_identity"] not in html or "台股決策智慧 V2" not in html:
            errors.append(f"{window}:dashboard_projection")
        if any(token in html for token in ("BUY_CANDIDATE", "WATCH_CANDIDATE", "Opportunity Rank")):
            errors.append(f"{window}:dashboard_localization")
        operations = build_operations_provenance(
            market="TW", window=window, runtime_status="controlled_no_send",
            runtime_trading_date=payload["effective_trading_date"],
            snapshot={"payload": payload, "snapshot_id": payload["snapshot_id"], "revision": 1},
            public_sync={}, email_result="controlled_no_send", line_result="controlled_no_send",
        )
        if operations.get("tw_decision_identity") != bundle["decision_identity"]:
            errors.append(f"{window}:operations_identity")
        email_preview = _append_tw_v2("電子郵件預覽", projection)
        line_preview = _append_tw_v2("LINE 預覽", projection, line_mode=True)
        if bundle["pm_daily_summary"]["one_line"] not in email_preview or bundle["pm_daily_summary"]["one_line"] not in line_preview:
            errors.append(f"{window}:preview_semantic_parity")
        if any(token in email_preview + line_preview for token in ("BUY_CANDIDATE", "WATCH_CANDIDATE", "Opportunity Rank")):
            errors.append(f"{window}:preview_localization")
        identities[window] = bundle["decision_identity"]
        details["windows"][window] = {
            "identity": bundle["decision_identity"], "symbols": len(rows),
            "categories": bundle["decision_categories"], "coverage": bundle["coverage_registry"],
        }

    pre = build_tw_decision_intelligence_v2("pre_open_0700", fixtures["pre_open_0700"])
    required_0700 = {"top_opportunities", "top_risks", "best_watch", "best_etf", "avoid_sectors", "pm_one_line"}
    if not required_0700 <= set(pre["window_intelligence"]): errors.append("pre_open_0700:window_intelligence")
    intra = build_tw_decision_intelligence_v2("intraday_1305", fixtures["intraday_1305"])
    if not {"breakout", "breakdown", "momentum", "intraday_strength", "intraday_weakness", "risk_update"} <= set(intra["window_intelligence"]): errors.append("intraday_1305:window_intelligence")
    close = build_tw_decision_intelligence_v2("pre_close_1335", fixtures["pre_close_1335"])
    if not {"hold", "overnight_risk", "tomorrow_gap_assessment", "late_flow", "next_day_priority"} <= set(close["window_intelligence"]): errors.append("pre_close_1335:window_intelligence")
    post = build_tw_decision_intelligence_v2("post_close_1500", fixtures["post_close_1500"])
    review = post.get("prediction_review") or {}
    if not review.get("error_attribution") or review.get("automatic_learning") is not False or review.get("confidence_calibration", {}).get("weights_modified") is not False:
        errors.append("post_close_1500:review_contract")

    us_rejected = False
    try:
        build_tw_decision_intelligence_v2("us_pre_market_2000", fixtures["pre_open_0700"])
    except ValueError:
        us_rejected = True
    if not us_rejected: errors.append("tw_us_isolation")

    corrupt = copy.deepcopy(pre); corrupt["decision_identity"] = "corrupt"
    details["negative_tests"]["identity"] = validate_tw_decision_intelligence_v2(corrupt)
    if "decision_identity" not in details["negative_tests"]["identity"]: errors.append("negative:identity")
    corrupt = copy.deepcopy(pre); corrupt["stock_intelligence"][0]["coverage"]["technical"]["status"] = "NEUTRAL"
    details["negative_tests"]["coverage_status"] = validate_tw_decision_intelligence_v2(corrupt)
    if not any(item.startswith("coverage_status:") for item in details["negative_tests"]["coverage_status"]): errors.append("negative:coverage_status")
    corrupt = copy.deepcopy(pre); first = corrupt["stock_intelligence"][0]["symbol"]; corrupt["decision_categories"]["BUY_CANDIDATE"].append(first)
    details["negative_tests"]["category_overlap"] = validate_tw_decision_intelligence_v2(corrupt)
    if "category_partition" not in details["negative_tests"]["category_overlap"]: errors.append("negative:category_overlap")
    all_avoid = copy.deepcopy(fixtures["pre_open_0700"])
    for card in all_avoid["cards"]:
        tactical = card.setdefault("strategies", {}).setdefault("daily_tactical", {})
        tactical["setup_type"] = "no_trade"
        tactical["action"] = "暫不操作"
        card["plan_status"] = "no_trade"
        card["action"] = "暫不操作"
        card["eligibility"] = {"actionable": False}
    no_trade_bundle = build_tw_decision_intelligence_v2("pre_open_0700", all_avoid)
    no_trade_pm = no_trade_bundle["pm_daily_summary"]
    details["negative_tests"]["all_avoid_truthfulness"] = no_trade_pm
    if "沒有通過既有 action gate" not in no_trade_pm["largest_opportunity"]:
        errors.append("negative:all_avoid_opportunity")
    if no_trade_pm["most_worth_tracking"] == no_trade_pm["most_worth_dropping"] and len(no_trade_bundle["stock_intelligence"]) > 1:
        errors.append("negative:tracking_risk_same_symbol")
    details["decision_identities"] = identities
    details["model_boundary"] = pre["model_boundary"]
    return {"ok": not errors, "validator": "validate_ai_dev_198_tw_decision_intelligence_v2", "errors": sorted(set(errors)), "details": details}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
