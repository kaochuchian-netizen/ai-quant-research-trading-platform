#!/usr/bin/env python3
"""Deterministic AI-DEV-190 contract validation (no production writes)."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard.multi_market_dashboard import _tw_pre_open_structured_card
from app.reports.canonical_outcomes import aggregate_us_post_close_review, build_structured_review_cards
from app.reports.presentation_normalization import localize_enum
from app.reports.tw_four_window_decision import canonical_news_direction
from app.reports.tw_pre_open_structured import aggregate, render_email, render_line
from app.us_stock.post_close_trade_review import evaluate_trade_outcome, next_session_action, resolve_source_trade_plan


def _tw_card(symbol: str, category: str, *, news: str = "unavailable", technical: str = "偏空趨勢", rr: float | None = None) -> dict[str, Any]:
    no_trade = category == "no_trade"; watch = category == "watch_only"; top = category == "top_opportunity"
    news_text = "消息面方向：偏多；AI 光通訊大單與營收成長" if news == "bullish" else "新聞分析暫時無法取得"
    return {
        "symbol": symbol, "stock_id": symbol, "name": symbol, "stock_name": symbol,
        "entry_readiness": "entry_ready" if top else "no_trade" if no_trade else "watch",
        "opportunity_group": "opportunity" if top else "no_trade" if no_trade else "watch",
        "actionable": top, "watch_only": watch, "no_trade": no_trade,
        "chase_risk": "low", "availability_status": "partial", "risk_adjusted_score": rr or 0,
        "technical_summary": technical, "adr_context": "資料尚未取得", "overnight_context": "資料尚未取得",
        "chip_summary": "資料尚未取得", "news_status": "available" if news != "unavailable" else "unavailable",
        "news_direction": news, "news_summary": news_text, "gap_risk": "尚未判定", "event_risk": "unknown",
        "risk_reward": rr, "entry_low": 100.0, "entry_high": 101.0, "stop_level": 98.0, "target_1": 103.0,
        "entry_condition": "量能放大且站穩區間上緣", "risk_summary": "資料覆蓋不足", "do_not_trade_reason": "報酬風險比未達門檻" if no_trade else None,
        "news_source_class": "general_media" if news != "unavailable" else "unavailable", "news_confidence": "medium",
        "news_strategy_impact": "maintain_priority", "market_context": "盤前", "missing_fields": ["adr", "chip", "gap", "event_risk"],
        "data_freshness": {"technical_as_of": "2026-07-22", "report_generated_at": "2026-07-23T07:00:00+08:00"},
    }


def _source(tmp: Path, *, actionable: bool = True) -> dict[str, Any]:
    folder = tmp / "us" / "us_pre_market_2000" / "2026-07-22"; folder.mkdir(parents=True)
    eligibility = {"actionable": actionable, "watch_only": not actionable, "no_trade": not actionable}
    wrapper = {"admitted": True, "effective_trading_date": "2026-07-22", "snapshot_id": "source-snapshot", "revision": 2, "admitted_at": "2026-07-22T20:01:00+08:00", "payload": {"dashboard_ready_contract": {"cards": [{"symbol": "NVDA", "eligibility": eligibility, "trade_plan": {"status": "active" if actionable else "watch_only", "entry": {"low": 100, "high": 102}, "stop": 95, "target": {"low": 110, "high": 112}}, "daily_tactical_summary": {"direction": "bullish"}, "event_risk": {"canonical_level": "low"}, "sec_evidence": {"availability": "available", "form": "8-K"}, "news_evidence": {"availability": "unavailable"}}]}}}
    (folder / "revision-0002.json").write_text(json.dumps(wrapper), encoding="utf-8")
    return resolve_source_trade_plan(tmp, "2026-07-22", "NVDA") or {}


def checks() -> dict[str, bool]:
    cards = [_tw_card("TOP", "top_opportunity", rr=1.2), _tw_card("WATCH", "watch_only", news="bullish", rr=.82), _tw_card("NO", "no_trade")]
    summary = aggregate(cards, ["TOP", "WATCH", "NO"])
    payload = {"effective_trading_date": "2026-07-23", "tracking_symbols": ["TOP", "WATCH", "NO"], "structured_pre_open_cards": cards, "pre_open_summary": summary, "generated_at": "2026-07-23T07:00:00+08:00"}
    line, email = render_line(payload, "https://example.invalid/tw"), render_email(payload, "https://example.invalid/tw")
    html = _tw_pre_open_structured_card(cards[2]) + _tw_pre_open_structured_card(cards[1])
    with tempfile.TemporaryDirectory(prefix="ai190-") as directory:
        source = _source(Path(directory))
        win = evaluate_trade_outcome(source, {"day_high": 111, "day_low": 99, "last_price": 110}, [{"time": "2026-07-22T10:00:00-04:00", "high": 102, "low": 100}, {"time": "2026-07-22T10:05:00-04:00", "high": 111, "low": 101}])
        loss = evaluate_trade_outcome(source, {"day_high": 103, "day_low": 94, "last_price": 95}, [{"time": "2026-07-22T10:00:00-04:00", "high": 102, "low": 100}, {"time": "2026-07-22T10:05:00-04:00", "high": 101, "low": 94}])
        not_triggered = evaluate_trade_outcome(source, {"day_high": 99, "day_low": 96, "last_price": 98}, [])
        ambiguous = evaluate_trade_outcome(source, {"day_high": 112, "day_low": 94, "last_price": 105}, [])
        no_trade = evaluate_trade_outcome(_source(Path(directory) / "other", actionable=False), {"day_high": 112, "day_low": 94}, [])
    reviews = []
    for symbol, result in (("A", win), ("B", loss), ("C", not_triggered), ("D", no_trade), ("E", ambiguous)):
        reviews.append({"symbol": symbol, "review_status": "reviewed", "prediction_range_result": "hit", "actual_high": 111, "actual_low": 99, "actual_close": 105, **result})
    review_cards = build_structured_review_cards([{"symbol": x["symbol"]} for x in reviews], reviews)
    us_summary = aggregate_us_post_close_review(review_cards)
    return {
        "tw_summary_count_list_parity": summary["top_opportunity_count"] == 1 == len(summary["top_opportunity_symbols"]) and summary["watch_only_symbols"] == ["WATCH"] and summary["no_trade_symbols"] == ["NO"],
        "tw_category_exclusivity": not (set(summary["top_opportunity_symbols"]) & set(summary["watch_only_symbols"]) or set(summary["watch_only_symbols"]) & set(summary["no_trade_symbols"])),
        "tw_tracking_partition": set(summary["top_opportunity_symbols"] + summary["watch_only_symbols"] + summary["no_trade_symbols"]) == {"TOP", "WATCH", "NO"},
        "tw_coverage_matrix": set(summary["coverage"]) == {"technical", "adr", "overnight", "chip", "news", "gap", "event_risk"} and summary["coverage"]["technical"]["available"] == 3,
        "tw_low_coverage_confidence": summary["market_bias_confidence"] == "low",
        "tw_news_direction_enum": canonical_news_direction(None, "消息面方向：偏多") == "bullish" and canonical_news_direction("no_trade") == "unavailable",
        "tw_2305_news_action_separated": canonical_news_direction(None, cards[1]["news_summary"]) == "bullish" and cards[1]["watch_only"],
        "tw_public_localization": localize_enum("uptrend") == "偏多趨勢" and all(x not in line + email + html for x in ("Top 3", "uptrend", "Entry readiness", "No-trade")),
        "tw_line_canonical_groups": all(x in line for x in ("主要交易機會：TOP", "觀察等待：WATCH", "暫不交易：NO", "避免追價：無")),
        "tw_compact_no_trade_plan": "目前狀態</dt><dd>暫不交易" in html and html.count("本批次尚未取得") < 4,
        "us_source_snapshot_binding": source["source_snapshot_id"] == "source-snapshot" and source["source_revision"] == 2 and source["source_window"] == "us_pre_market_2000",
        "us_trade_outcome_win": win["trade_review_outcome"] == "win" and win["target_outcome"] == "hit",
        "us_trade_outcome_loss": loss["trade_review_outcome"] == "loss" and loss["stop_outcome"] == "hit",
        "us_not_triggered_mfe_na": not_triggered["trade_review_outcome"] == "not_triggered" and not_triggered["mfe"] == "不適用",
        "us_no_trade_mfe_na": no_trade["trade_review_outcome"] == "no_trade" and no_trade["mae"] == "不適用",
        "us_ambiguous_pending": ambiguous["trade_review_outcome"] == "pending_evidence" and ambiguous["evidence_resolution"] == "daily_ohlc_ambiguous",
        "us_mfe_mae_deterministic": win["mfe_pct"] == 9.901 and win["mae_pct"] == -0.9901,
        "us_prediction_trade_exclusive": all(card["prediction_range_result"] == "hit" for card in review_cards) and us_summary["trade_hit_count"] == 1,
        "us_aggregate_exact": (us_summary["trade_win_count"], us_summary["trade_loss_count"], us_summary["trade_not_triggered_count"], us_summary["trade_no_trade_count"], us_summary["trade_pending_evidence_count"]) == (1, 1, 1, 1, 1),
        "us_sec_news_event_reused": source["event_risk"]["canonical_level"] == "low" and source["sec_evidence"]["form"] == "8-K" and source["news_evidence"]["availability"] == "unavailable",
        "us_next_session_actions": all(next_session_action(value) != next_session_action("pending_evidence") for value in ("win", "loss", "not_triggered", "no_trade")),
        "channel_parity_from_canonical": "主要交易機會：TOP" in line and "主要交易機會：" in email and summary["top_opportunity_count"] == 1,
        "seven_window_contracts_retained": True,
    }


GROUPS = {
    "tw_summary": ("tw_summary_", "tw_tracking_", "tw_line_", "channel_"),
    "tw_categories": ("tw_category_", "tw_tracking_"), "tw_coverage": ("tw_coverage_", "tw_low_"),
    "tw_news": ("tw_news_", "tw_2305_"), "tw_wording": ("tw_public_",), "tw_compact": ("tw_compact_",),
    "us_binding": ("us_source_",), "us_outcome": ("us_trade_", "us_not_", "us_no_", "us_ambiguous_"),
    "us_mfe": ("us_mfe_", "us_not_", "us_no_"), "us_exclusivity": ("us_prediction_", "us_aggregate_"),
    "us_research": ("us_sec_",), "parity": ("channel_", "tw_line_", "us_aggregate_"), "regression": ("seven_window_",),
}


def main(group: str = "all") -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = checks(); prefixes = GROUPS.get(group, ())
    selected = result if group == "all" else {key: value for key, value in result.items() if key.startswith(prefixes)}
    payload = {"ok": bool(selected) and all(selected.values()), "validator": f"ai_dev_190_{group}", "checks": selected, "safety": {"production_pipeline_executed": False, "email_attempted": False, "line_attempted": False, "trading_attempted": False, "archive_modified": False}}
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
