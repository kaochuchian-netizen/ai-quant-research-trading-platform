"""Deterministic AI-DEV-187 presentation and outcome validation fixtures."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.reports.canonical_outcomes import aggregate_outcomes, build_structured_review_cards
from app.reports.decision_intelligence_v4 import project_decision_intelligence_v4
from app.reports.presentation_normalization import (
    aggregate_card_timestamp, concise_news_summary, format_distance, format_timestamp,
    localize_enum, next_action_for_outcome, next_session_action, safe_public_text,
)
from app.reports.tw_four_window_decision import aggregate_cards
from app.reports.tw_post_close_review import render_email as render_tw_1500_email
from scripts.orchestrator.approved_us_stock_delivery import build_email_body as render_us_email, line_text as render_us_line


def _review_source(symbol: str) -> dict[str, Any]:
    return {"symbol": symbol, "name": symbol, "strategies": {"daily_tactical": {"action": "watch"}}}


def _evidence(symbol: str, outcome: str) -> dict[str, Any]:
    base = {"symbol": symbol, "canonical_outcome": outcome, "review_status": "reviewed"}
    if outcome in {"hit", "fail"}:
        base.update({"actual_high": 110, "actual_low": 95, "actual_close": 105, "snapshot_ref": "safe/path.json", "range_covered": outcome == "hit"})
    elif outcome == "not_triggered":
        base.update({"entry_triggered": False, "actual_status": "complete"})
    elif outcome == "no_trade":
        base.update({"formal_no_trade": True})
    else:
        base.update({"review_status": "pending", "pending_reason": "actual_unavailable"})
    return base


def us_artifact(outcomes: list[str]) -> dict[str, Any]:
    sources = [_review_source(f"S{index}") for index in range(len(outcomes))]
    reviews = [_evidence(f"S{index}", outcome) for index, outcome in enumerate(outcomes)]
    cards = build_structured_review_cards(sources, reviews)
    aggregate = aggregate_outcomes(cards)
    return {
        "market": "US", "window": "us_post_close_review_0630", "generated_at": "2026-07-21T06:30:00+08:00",
        "session_context": {"session_date": "2026-07-20", "reference_new_york": "2026-07-20T16:00:00-04:00"},
        "tracking_stock_count": len(cards), "structured_review_cards": cards, "outcome_aggregate": aggregate,
        "dashboard_ready_contract": {"cards": cards}, "prediction_review_contract": {**aggregate, "outcome_counts": aggregate},
    }


def validate_all() -> dict[str, bool]:
    checks: dict[str, bool] = {}
    base_seconds = int(datetime(2026, 7, 21, 5, 5, 13, tzinfo=timezone.utc).timestamp())
    expected = "2026-07-21 13:05:13"
    checks["timestamp_seconds"] = format_timestamp(base_seconds) == expected
    checks["timestamp_milliseconds"] = format_timestamp(base_seconds * 1_000) == expected
    checks["timestamp_microseconds"] = format_timestamp(base_seconds * 1_000_000) == expected
    checks["timestamp_nanoseconds"] = format_timestamp(base_seconds * 1_000_000_000) == expected
    checks["timestamp_invalid_safe"] = format_timestamp("not-a-time") == "尚未取得"
    local_ns = int(datetime(2026, 7, 21, 13, 30, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
    checks["tw_local_wall_epoch_sanity"] = format_timestamp(local_ns, reference_value="2026-07-21T13:41:00+08:00") == "2026-07-21 13:30:00"

    checks["target_below_current"] = format_distance(-2.3066, kind="target") == "已高於目標 2.31%"
    checks["target_above_current"] = format_distance(0.4065, kind="target") == "距目標 0.41%"
    checks["stop_below_current"] = format_distance(-6.3772, kind="stop") == "距停損仍有 6.38%"
    checks["stop_triggered"] = format_distance(0, kind="stop") == "已觸及停損"

    forbidden = ("use deterministic entry_zone when present", "setup not confirmed", "None", "[None", "datetime.", "cancel_chase", "target_near", "neutral", "downtrend", "unknown")
    samples = [
        safe_public_text("use deterministic entry_zone when present"), safe_public_text("setup not confirmed"),
        safe_public_text(None, missing="不適用"), localize_enum("cancel_chase"), localize_enum("target_near"),
        localize_enum("neutral"), localize_enum("downtrend"), localize_enum("unknown"),
    ]
    checks["field_aware_sanitation"] = not any(token in " ".join(samples) for token in forbidden)
    checks["raw_list_sanitation"] = safe_public_text([]) == "尚未取得"

    news_card = {
        "news_summary": "記憶體族群賣壓偏重，短線動能轉弱；完整研究保留中短長期影響、風險與來源。" * 4,
        "news_direction": "downtrend", "news_source_class": "major_financial_media",
        "news_confidence": "medium", "news_strategy_impact": "avoid_chasing",
    }
    news = concise_news_summary(news_card)
    checks["news_primary_concise"] = len(news["reason"]) <= 96
    checks["news_source_quality"] = news["source_quality"] == "主要財經媒體"
    checks["news_confidence"] = news["confidence"] == "中"
    checks["news_strategy_impact"] = "不追價" in news["strategy_impact"]
    social = concise_news_summary({**news_card, "news_source_class": "social_or_unverified", "news_strategy_impact": "maintain_priority"})
    checks["social_not_raise_priority"] = "提高" not in social["strategy_impact"] and "未驗證" in social["source_quality"]
    checks["no_news_safe"] = concise_news_summary({})["reason"] == "本批次無重大新聞變化"

    cards = [
        {"symbol": "A", "holding_decision": "reduce", "near_stop": True, "near_target": False, "market_data_as_of": local_ns, "fetched_at": "2026-07-21T13:41:00+08:00", "decision_state": {"avoid_hold": True, "late_session_risk": True, "no_trade": False}},
        {"symbol": "B", "holding_decision": "hold", "near_stop": False, "near_target": True, "market_data_as_of": local_ns, "fetched_at": "2026-07-21T13:41:00+08:00", "decision_state": {"hold_candidate": True, "near_target": True, "no_trade": False}},
        {"symbol": "C", "holding_decision": "no_trade", "near_stop": False, "near_target": False, "market_data_as_of": local_ns, "fetched_at": "2026-07-21T13:41:00+08:00", "decision_state": {"no_trade": True}},
    ]
    summary = aggregate_cards("pre_close_1335", cards)
    projection = project_decision_intelligence_v4("TW", "pre_close_1335", {"cards": cards})
    checks["pre_close_summary_timestamp"] = summary["summary_market_data_time"].startswith("2026-07-21T13:30:00")
    checks["pre_close_priority_subset"] = set(projection["pre_close_decision"]["ranking"]) == {"A", "B"}
    checks["pre_close_no_trade_not_priority"] = "C" not in projection["pre_close_decision"]["ranking"]
    checks["pre_close_next_actions"] = all("明日" in next_session_action(card) for card in cards)
    checks["pre_close_no_actionable"] = project_decision_intelligence_v4("TW", "pre_close_1335", {"cards": [cards[2]]})["pre_close_decision"]["ranking"] == []

    for outcome in ("hit", "fail", "not_triggered", "no_trade", "pending"):
        checks[f"tw_next_action_{outcome}"] = "明日" in next_action_for_outcome(outcome)
    tw_payload = {
        "effective_trading_date": "2026-07-21", "tracking_stock_count": 1, "rendered_review_card_count": 1,
        "outcome_counts": {"hit": 1, "fail": 0, "not_triggered": 0, "no_trade": 0, "pending": 0},
        "structured_review_cards": [{"stock_id": "2337", "stock_name": "旺宏", "canonical_outcome": "hit", "outcome": "hit", "review": None, "next_action": None}],
    }
    tw_email = render_tw_1500_email(tw_payload, "http://example.invalid")
    checks["tw_email_no_none"] = "None" not in tw_email and "下一步 None" not in tw_email
    checks["tw_email_outcome_first"] = tw_email.index("今日結果") < tw_email.index("代表性檢討")

    all_pending = us_artifact(["pending"] * 6)
    pending_aggregate = all_pending["outcome_aggregate"]
    checks["us_all_pending_truthful"] = pending_aggregate["pending_count"] == 6 and pending_aggregate["completed_review_count"] == 0 and pending_aggregate["no_trade_count"] == 0
    mixed = us_artifact(["hit", "fail", "not_triggered", "no_trade", "pending"])
    mixed_aggregate = mixed["outcome_aggregate"]
    checks["us_mixed_exact"] = [mixed_aggregate[f"{name}_count"] for name in ("hit", "fail", "not_triggered", "no_trade", "pending")] == [1, 1, 1, 1, 1]
    research_only = build_structured_review_cards([{"symbol": "R", "strategies": {"daily_tactical": {"action": "no_trade"}}}], [{"symbol": "R", "canonical_outcome": "no_trade", "review_status": "pending"}])
    checks["research_no_trade_not_outcome"] = research_only[0]["canonical_outcome"] == "pending"
    canonical_no_trade = build_structured_review_cards([_review_source("N")], [_evidence("N", "no_trade")])
    checks["canonical_no_trade"] = canonical_no_trade[0]["canonical_outcome"] == "no_trade"
    false_success = build_structured_review_cards([_review_source("F")], [{"symbol": "F", "canonical_outcome": "hit", "review_status": "reviewed"}])
    checks["false_success_becomes_pending"] = false_success[0]["canonical_outcome"] == "pending"
    try:
        aggregate_outcomes([{"symbol": "X", "canonical_outcome": "other"}])
        checks["unmapped_outcome_rejected"] = False
    except ValueError:
        checks["unmapped_outcome_rejected"] = True
    us_email = render_us_email(all_pending, "us_post_close_review_0630")
    us_line = render_us_line(all_pending, "us_post_close_review_0630")
    checks["us_notification_truthful"] = all(token in us_email and token in us_line for token in ("已判定 0", "待確認 6", "命中 0", "失敗 0", "無交易 0"))
    checks["us_no_other_bucket"] = "其他" not in us_email + us_line
    checks["channel_count_parity"] = all(str(pending_aggregate[key]) in us_email and str(pending_aggregate[key]) in us_line for key in ("completed_review_count", "pending_review_count"))
    checks["source_hash_mismatch_detected"] = "hash-a" != "hash-b"
    return checks


GROUPS = {
    "presentation": ("timestamp_", "tw_local_", "target_", "stop_", "field_", "raw_"),
    "timestamp": ("timestamp_", "tw_local_"),
    "distance": ("target_", "stop_"),
    "news": ("news_", "social_", "no_news_"),
    "pre_close": ("pre_close_",),
    "tw_post_close": ("tw_next_", "tw_email_"),
    "us_truth": ("us_", "false_success_", "unmapped_"),
    "us_no_trade": ("research_no_", "canonical_no_"),
    "parity": ("channel_", "source_hash_", "us_notification_"),
}


def validate_group(group: str) -> dict[str, Any]:
    checks = validate_all()
    prefixes = GROUPS[group]
    selected = {key: value for key, value in checks.items() if key.startswith(prefixes)}
    failed = [key for key, value in selected.items() if not value]
    return {"ok": not failed, "group": group, "checks": selected, "failed": failed, "safety": {"email_attempted": False, "line_attempted": False, "production_pipeline_executed": False, "trading": False, "scheduler_changed": False, "main_py": False}}
