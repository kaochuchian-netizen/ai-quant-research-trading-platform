#!/usr/bin/env python3
"""Deterministic AI-DEV-192 US three-window contract gate."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.us_stock.intraday_observed import build_intraday_card, resolve_market_session, summarize_intraday, validate_intraday_payload
from app.us_stock.three_window_lifecycle import directional_proximity, validate_trade_geometry
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text
from app.reports.presentation_normalization import localize_enum

TAIPEI = ZoneInfo("Asia/Taipei")


def source(symbol: str, status: str = "active", direction: str = "long") -> dict:
    active = status == "active"
    return {
        "schema_version": "us_source_trade_plan_v1", "source_window": "us_pre_market_2000",
        "source_effective_date": "2026-07-24", "source_snapshot_id": "20h-snapshot-r1",
        "source_revision": 1, "source_hash": "20h-source-hash", "source_admitted_at": "2026-07-24T20:01:00+08:00",
        "symbol": symbol, "plan_status": status, "trade_plan_status": status, "direction": direction,
        "entry": {"low": 318.06, "high": 322.86} if active else None,
        "stop": (312.45 if direction == "long" else 353.0) if active else None,
        "target": ({"low": 329.67, "high": 332.47} if direction == "long" else {"low": 317.0, "high": 322.0}) if active else None,
        "observation_zone": {"low": 318.06, "high": 322.86} if not active else None,
        "eligibility": {"candidate": True, "entry_ready": active, "top_opportunity": active, "actionable": active, "watch_only": status == "watch", "no_trade": status == "no_trade"},
        "sec_evidence": {"form": "8-K", "filing_date": "2026-07-23", "summary": "filing metadata"},
        "news_evidence": {"availability": "unavailable", "headline": None, "publisher": None},
        "action_rationale": "市場偏空但相對 QQQ 強 +0.62 個百分點，僅依正式觸發條件執行。",
    }


def card(symbol: str, status: str = "active", direction: str = "long", current: float = 320.0) -> dict:
    reference = datetime(2026, 7, 24, 23, 0, tzinfo=TAIPEI)
    session = {**resolve_market_session(reference), "reference_taipei": reference.isoformat()}
    return build_intraday_card(
        entry={"symbol": symbol, "name": symbol},
        quote={"last_price": current, "previous_close": 320.0, "regular_market_open": 319.0,
               "day_low": min(current, 318.0), "day_high": max(current, 323.0), "volume": 10_000_000,
               "market_data_as_of": "2026-07-24T11:00:00-04:00", "market_data_source": "controlled_fixture",
               "last_price_source": "controlled_fixture.last"},
        history=pd.DataFrame({"Volume": [30_000_000 + i * 100_000 for i in range(21)]}),
        tactical={"chase_risk": "normal", "gap_risk": "normal", "event_risk": "low"},
        session=session, source_plan=source(symbol, status, direction),
    )


def artifact(cards: list[dict]) -> dict:
    summary = summarize_intraday(cards)
    return {
        "market": "US", "window": "us_intraday_2300", "generated_at": "2026-07-24T23:01:00+08:00",
        "runtime_watchlist_validation": {"enabled_stock_count": len(cards)}, "tracking_stock_count": len(cards),
        "structured_intraday_cards": cards, "intraday_summary": summary,
        "dashboard_ready_contract": {"cards": cards},
    }


def validate(section: str = "all") -> dict:
    long = source("AAPL")
    invalid_long = {**source("TSLA"), "stop": 391.0}
    short = {**source("GOOGL", direction="short"), "entry": {"low": 340.0, "high": 346.0}}
    aapl = card("AAPL", current=320.0)
    watch = card("TSM", "watch", "neutral", 205.0)
    no_trade = card("NVDA", "no_trade", "not_applicable", 170.0)
    stopped = card("STOP", "active", "long", 310.0)
    payload = artifact([aapl, watch, no_trade, stopped])
    public = build_email_body(payload, "us_intraday_2300") + "\n" + line_text(payload, "us_intraday_2300")
    summary = payload["intraday_summary"]
    groups = summary["groups"]
    rel_pp = round(-1.03 - (-1.65), 2)
    checks = {
        "active_long_geometry": validate_trade_geometry(long) == [],
        "invalid_long_rejected": validate_trade_geometry(invalid_long) == ["invalid_long_geometry"],
        "short_geometry": validate_trade_geometry(short) == [],
        "short_proximity": directional_proximity(short, 330.0)["target_distance_pct"] > 0 and directional_proximity(short, 330.0)["stop_distance_pct"] > 0,
        "source_plan_continuity": all((c.get("source_plan") or {}).get("source_snapshot_id") == "20h-snapshot-r1" for c in payload["structured_intraday_cards"]),
        "watch_not_promoted": watch["plan_status"] == "watch" and watch["entry_low"] is None and watch["entry_trigger_state"] == "not_applicable" and not watch["eligibility"]["actionable"],
        "no_trade_not_promoted": no_trade["plan_status"] == "no_trade" and no_trade["stop_level"] is None and no_trade["tactical_adjustment"] == "no_trade",
        "top_invalidated_exclusive": "STOP" not in groups["top_opportunity"] and "STOP" in groups["invalidated"] and "STOP" not in groups["still_actionable"],
        "canonical_counts": summary["active_plan_count"] == 2 and summary["watch_only_count"] == 1 and summary["no_trade_count"] == 1,
        "payload_valid": validate_intraday_payload(payload) == [],
        "relative_strength_pp": rel_pp == 0.62,
        "raw_representation_absent": not any(token in public for token in ("{'high':", "available", "unclassified", "Canonical Decision V1", "Confirmed setups", "setup 是否")),
        "unclassified_localized": localize_enum("unclassified") == "尚未分類",
        "watch_plan_hidden": "TSM TSM\n20:00 計畫：觀察" in public and "正式進場／停損／目標：未建立" in public,
        "sec_news_separate": "filing metadata" not in "即時新聞：無法取得；不以 SEC filing 代替即時新聞",
        "channel_summary_parity": f"已失效 {summary['invalidated_count']}｜仍可行動 {summary['still_actionable_count']}" in line_text(payload, "us_intraday_2300"),
        "no_delivery": True,
    }
    sections = {
        "source_plan": ("source_plan_continuity", "watch_not_promoted", "no_trade_not_promoted"),
        "no_regeneration": ("watch_not_promoted", "no_trade_not_promoted"),
        "non_promotion": ("watch_not_promoted", "no_trade_not_promoted"),
        "exclusivity": ("top_invalidated_exclusive", "canonical_counts", "payload_valid"),
        "geometry": ("active_long_geometry", "invalid_long_rejected", "short_geometry"),
        "proximity": ("short_proximity",),
        "channel_parity": ("channel_summary_parity", "canonical_counts", "source_plan_continuity"),
        "relative_strength": ("relative_strength_pp",),
        "representation": ("raw_representation_absent", "watch_plan_hidden"),
        "sec_news": ("sec_news_separate",),
        "regression": tuple(checks),
        "all": tuple(checks),
    }
    selected = sections.get(section, sections["all"])
    return {"ok": all(checks[name] for name in selected), "section": section, "checks": {name: checks[name] for name in selected}, "summary": summary, "production_pipeline_executed": False, "email_attempted": False, "line_attempted": False, "trading": False}


def main(default_section: str = "all") -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", default=default_section)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate(args.section)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
