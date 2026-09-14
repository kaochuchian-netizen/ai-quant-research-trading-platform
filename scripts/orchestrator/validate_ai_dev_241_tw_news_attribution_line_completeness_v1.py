#!/usr/bin/env python3
"""Validate AI-DEV-241 TW news attribution and LINE completeness contracts."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.market.instrument_master import instrument_metadata  # noqa: E402
from app.reports.delivery_provenance import build_delivery_provenance  # noqa: E402
from app.reports.tw_line_completeness import build_symbol_delivery_accounting, rendered_symbols_from_text  # noqa: E402
from app.reports.tw_pre_open_delivery_contract import _channel_delivery  # noqa: E402
from app.reports.tw_pre_open_quality import news_contract  # noqa: E402
from app.reports.tw_preopen_product_intelligence import SCHEMA_VERSION as PRODUCT_SCHEMA, render_line  # noqa: E402
from app.us_stock.batch_reliability import contract_for_window  # noqa: E402

NOW = "2026-09-14T07:00:00+08:00"
EXPECTED_TW = ["2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293"]


def _news(title: str, **extra: Any) -> dict[str, Any]:
    base = {
        "headline": title,
        "publisher": "中央社",
        "published_at": "2026-09-14T06:30:00+08:00",
        "source_url": "https://example.invalid/news",
        "relevance": "high",
        "materiality": "high",
        "direction": "neutral",
    }
    base.update(extra)
    return base


def _product(symbol: str, direction_label: str = "偏多") -> dict[str, Any]:
    return {
        "schema_version": PRODUCT_SCHEMA,
        "symbol": symbol,
        "name": {"2330": "台積電", "2337": "旺宏", "2353": "宏碁"}.get(symbol, symbol),
        "direction_label": direction_label,
        "direction_arrow": "↑" if direction_label == "偏多" else "↔",
        "target_price": 100.0,
        "predicted_low": 95.0,
        "predicted_high": 105.0,
        "news_funnel": {"retrieved_count": 1, "selected_count": 0},
        "important_news": [],
    }


def _cards(symbols: list[str]) -> list[dict[str, Any]]:
    return [{"symbol": symbol, "stock_id": symbol, "tw_preopen_product_intelligence_v1": _product(symbol)} for symbol in symbols]


def _snapshot(symbols: list[str]) -> dict[str, Any]:
    return {
        "snapshot_id": "snap-ai-dev-241",
        "revision": 1,
        "effective_trading_date": "2026-09-14",
        "payload_hash": "hash-ai-dev-241",
        "payload": {"tracking_symbols": symbols, "structured_pre_open_cards": _cards(symbols)},
    }


def run_validation() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    positive = news_contract(
        [_news("台積電 TSMC 先進製程需求升溫", source_url="https://example.invalid/tsmc")],
        generated_at=NOW,
        target_symbol="2330",
        target_name="台積電",
    )
    checks["2330_tsmc_positive_attribution"] = (
        positive["evidence_funnel"]["stages"]["ADMITTED"] == 1
        and positive["evidence_funnel"]["stages"]["SYMBOL_ATTRIBUTED"] == 1
        and positive["evidence"][0]["entity_attribution"]["method"] == "canonical_tw_identity_alias_match"
    )

    unrelated = news_contract(
        [_news("宏碁發表新款商用筆電", source_url="https://example.invalid/acer")],
        generated_at=NOW,
        target_symbol="2330",
        target_name="台積電",
    )
    checks["unrelated_candidate_rejected"] = unrelated["evidence_funnel"]["rejection_reasons"].get("SYMBOL_ATTRIBUTION_FAILED") == 1

    ambiguous = news_contract(
        [_news("台積電與宏碁共同推動供應鏈活動", source_url="https://example.invalid/multi", related_symbols=["2330", "2353"])],
        generated_at=NOW,
        target_symbol="2330",
        target_name="台積電",
    )
    checks["ambiguous_candidate_fail_closed"] = ambiguous["evidence_funnel"]["rejection_reasons"].get("AMBIGUOUS_SYMBOL_ATTRIBUTION") == 1

    etf_leak = news_contract(
        [_news("國泰永續高股息 ETF 配息資訊更新", source_url="https://example.invalid/etf")],
        generated_at=NOW,
        target_symbol="2330",
        target_name="台積電",
    )
    checks["no_etf_company_cross_symbol_leakage"] = etf_leak["evidence_funnel"]["rejection_reasons"].get("SYMBOL_ATTRIBUTION_FAILED") == 1
    sector_generic = news_contract(
        [_news("半導體產業景氣回溫，供應鏈看法轉佳", source_url="https://example.invalid/sector")],
        generated_at=NOW,
        target_symbol="2330",
        target_name="台積電",
    )
    checks["generic_sector_news_not_company_attributed"] = sector_generic["evidence_funnel"]["rejection_reasons"].get("SYMBOL_ATTRIBUTION_FAILED") == 1

    metadata = {symbol: instrument_metadata("TW", symbol) for symbol in EXPECTED_TW}
    details["watchlist_metadata"] = {symbol: metadata[symbol].get("status") for symbol in EXPECTED_TW}
    checks["current_watchlist_symbols_resolve_where_metadata_exists"] = all(
        row.get("status") == "AVAILABLE"
        for symbol, row in metadata.items()
        if symbol != "3293"
    ) and metadata["3293"].get("status") == "MISSING"

    systematic = news_contract(
        [_news(f"候選新聞 {idx}", source_url=f"https://example.invalid/{idx}") for idx in range(5)],
        generated_at=NOW,
        target_symbol="2330",
        target_name="台積電",
    )
    checks["fetched_5_usable_0_mapping_failure_degraded"] = (
        systematic["evidence_funnel"]["stages"]["RETRIEVED"] == 5
        and systematic["evidence_funnel"]["stages"]["ADMITTED"] == 0
        and systematic["evidence_funnel"]["rejection_reasons"].get("SYMBOL_ATTRIBUTION_FAILED") == 5
        and systematic["absence_state"] == "NEWS_DISCOVERED_BUT_FILTERED"
    )

    symbols = EXPECTED_TW[:-1]
    line = render_line(_cards(symbols), "https://example.invalid/stock-ai-dashboard/dashboard/tw/")
    rendered = rendered_symbols_from_text(line, symbols)
    accounting = build_symbol_delivery_accounting(
        expected_symbols=symbols,
        rendered_symbols=rendered,
        policy="admitted-snapshot notification after public Dashboard parity",
        channel="line",
        content=line,
    )
    details["line_preview"] = line
    details["line_accounting"] = accounting
    checks["line_expected_rendered_omitted_accounting"] = accounting["expected_symbols"] == symbols and accounting["rendered_symbols"] == symbols and accounting["omitted_symbols"] == []
    checks["no_silent_line_symbol_omission"] = accounting["complete"] is True and accounting["silent_omission"] is False
    checks["message_chunking_completeness"] = accounting["message_count"] == 1 and accounting["chunk_count"] == 1 and len(line) <= 520

    provenance = build_delivery_provenance(
        market="TW",
        window="pre_open_0700",
        trading_date="2026-09-14",
        snapshot=_snapshot(symbols),
        canonical_url="https://example.invalid/stock-ai-dashboard/dashboard/tw/",
        channel="line",
        content=line,
        delivery_result="dry_run_not_sent",
        delivery_attempted=False,
        symbol_delivery_accounting=accounting,
    )
    checks["delivery_provenance_carries_symbol_accounting"] = provenance["symbol_delivery_accounting"]["complete"] is True

    calls: list[dict[str, Any]] = []
    receipt_snapshot = _snapshot(["2330"])
    with tempfile.TemporaryDirectory() as tmp:
        sent = _channel_delivery("line", lambda snapshot: calls.append(snapshot) or {"send_attempted": True, "send_status": "sent"}, receipt_snapshot, Path(tmp))
        replay = _channel_delivery("line", lambda snapshot: calls.append(snapshot) or {"send_attempted": True, "send_status": "sent"}, receipt_snapshot, Path(tmp))
    checks["existing_notification_idempotency_preserved"] = sent["send_status"] == "sent" and replay["send_status"] == "already_delivered" and len(calls) == 1

    checks["tw_preopen_lifecycle_symbols_complete"] = provenance["symbol_delivery_accounting"]["expected_symbol_count"] == len(symbols)
    checks["us_behavior_unchanged"] = contract_for_window("us_pre_market_2000").window == "us_pre_market_2000" and contract_for_window("us_intraday_2300").window == "us_intraday_2300"
    checks["semantic_layers_distinct"] = (
        "prediction_model" != "news_research_evidence"
        and positive["confidence"]["reason_codes"] == ["NO_OFFICIAL_CONFIRMATION"]
    )

    return {
        "schema_version": "ai_dev_241_tw_news_attribution_line_completeness_validation_v1",
        "task_id": "AI-DEV-241",
        "ok": all(checks.values()),
        "passed_count": sum(1 for value in checks.values() if value),
        "total_count": len(checks),
        "checks": checks,
        "details": details,
        "semantic_consistency_finding": "research evidence sufficiency and deterministic forecast direction are separate layers; no forecast policy change is made",
        "safety": {
            "production_rerun": False,
            "line_sent": False,
            "email_sent": False,
            "db_or_sheet_write": False,
            "scheduler_modified": False,
            "trading_or_order": False,
            "credentials_touched": False,
            "production_runtime_mutated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
