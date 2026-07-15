"""Deterministic seven-window decision-content projection.

This module is the presentation boundary shared by Dashboard, Email, LINE and
immutable archive pages.  It classifies only values present in the supplied
artifact; missing inputs stay explicit and are never inferred from another
market or window.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .window_report_contract import get_window_report_contract, normalize_window

SCHEMA_VERSION = "seven_window_decision_intelligence_v4"

WINDOW_PRESENTATION: dict[tuple[str, str], dict[str, Any]] = {
    ("TW", "pre_open_0700"): {
        "question": "今天開盤前該看什麼、哪些能做、哪些不能追？",
        "card_type": "pre-open-decision-v4",
        "sections": ("今日盤前總結", "市場環境", "Top opportunities", "No-trade list", "Chase-risk list", "Entry readiness", "Confidence distribution", "今日預測區間", "主要依據與風險", "新聞與事件", "資料完整度", "同時段變化"),
        "new_fields": ("top_opportunities", "no_trade", "chase_risk", "entry_readiness", "confidence_distribution", "same_window_change"),
        "suppressed": ("盤中 trigger", "尚未發生的 outcome review", "完整 runtime metadata"),
    },
    ("TW", "intraday_1305"): {
        "question": "哪些 setup 已觸發、哪些失效、現在還能不能做？",
        "card_type": "intraday-change-v4",
        "sections": ("盤中變化摘要", "與 07:00 相比", "Setup 已觸發", "Setup 尚未觸發", "Setup 已失效", "Still actionable", "Target proximity ranking", "Stop risk ranking", "量價確認", "New risk since 07:00"),
        "new_fields": ("triggered_count", "invalidated_count", "still_actionable_count", "target_proximity", "stop_risk", "price_volume_confirmation", "new_risk"),
        "suppressed": ("完整中長期 Research", "完整財報 / SEC", "盤後 outcome card"),
    },
    ("TW", "pre_close_1335"): {
        "question": "收盤前是否留倉、避追、減碼或等待明天？",
        "card_type": "pre-close-snapshot-v4",
        "sections": ("收盤前摘要", "留倉候選", "不留倉候選", "尾盤風險升高", "接近目標", "接近停損", "當日 setup 最終狀態", "明日 watchlist 新增 / 移除", "同時段變化"),
        "new_fields": ("hold_candidates", "avoid_overnight", "late_risk", "watchlist_delta", "same_window_change"),
        "suppressed": ("完整 07:00 操作卡", "完整 Research / Financial / SEC", "長篇進場計畫", "完整 technical detail"),
    },
    ("TW", "post_close_1500"): {
        "question": "今日預測與實際結果如何，哪些成功、失敗或未觸發？",
        "card_type": "post-close-review-v4",
        "sections": ("今日預測 vs 實際", "Outcome distribution", "Direction hit rate", "Trigger quality", "Target effectiveness", "Stop effectiveness", "MFE / MAE", "False Breakout", "Confidence calibration", "7-day trend", "明日觀察", "同時段變化"),
        "new_fields": ("outcome_distribution", "direction_hit_rate", "trigger_quality", "target_effectiveness", "stop_effectiveness", "confidence_calibration", "seven_day_trend", "same_window_change"),
        "suppressed": ("新的今日進場區", "新的當日 target plan", "完整 Tactical Plan", "完整 Research / News / SEC"),
    },
    ("US", "us_pre_market_2000"): {
        "question": "盤前機會、Premarket、Gap 與事件風險如何？",
        "card_type": "us-pre-market-v4",
        "sections": ("美股盤前總結", "Premarket movers", "Gap continuation risk", "SPY / QQQ / Sector context", "VIX / market risk", "Event-risk ranking", "Sector-relative strength", "Entry readiness", "Entry / Stop / Target", "Earnings / SEC / Official Events", "近期市場新聞", "同時段變化"),
        "new_fields": ("premarket_movers", "gap_continuation_risk", "event_risk", "sector_relative_strength", "entry_readiness", "same_window_change"),
        "suppressed": ("盤後 outcome", "06:30 review"),
    },
    ("US", "us_intraday_2300"): {
        "question": "開盤後量價與 Gap 是否確認，setup 是否仍可做？",
        "card_type": "us-intraday-change-v4",
        "sections": ("開盤後變化", "Confirmed setups", "Failed gaps", "Volume-confirmed moves", "Still actionable", "Chase risk", "Entry trigger", "Target / Stop proximity", "Tactical adjustment", "盤中事件更新", "與 20:00 預期偏差"),
        "new_fields": ("confirmed_setups", "failed_gaps", "volume_confirmed", "still_actionable", "chase_risk", "premarket_deviation"),
        "suppressed": ("完整 20:00 Research / Financial / SEC", "06:30 outcome review"),
    },
    ("US", "us_post_close_review_0630"): {
        "question": "全日 outcome 與 prediction review 如何，隔日看什麼？",
        "card_type": "us-post-close-review-v4",
        "sections": ("美股全日 outcome", "Review distribution", "Direction hit", "Setup quality", "Gap effectiveness", "Entry / Stop / Target outcome", "MFE / MAE", "Confidence calibration", "Earnings / SEC / overnight event update", "Next-session watchlist", "同時段變化"),
        "new_fields": ("review_distribution", "direction_hit", "setup_quality", "gap_effectiveness", "confidence_calibration", "same_window_change"),
        "suppressed": ("新的盤前交易計畫", "完整 20:00 卡"),
    },
}


def _cards(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    direct = payload.get("cards")
    if isinstance(direct, list):
        return [card for card in direct if isinstance(card, dict)]
    dashboard = payload.get("dashboard_ready_contract")
    if isinstance(dashboard, dict) and isinstance(dashboard.get("cards"), list):
        return [card for card in dashboard["cards"] if isinstance(card, dict)]
    nested = payload.get("payload")
    return _cards(nested) if isinstance(nested, dict) else []


def _identifier(card: dict[str, Any]) -> str:
    return str(card.get("stock_id") or card.get("symbol") or card.get("card_id") or "未識別標的")


def _tactical(card: dict[str, Any]) -> dict[str, Any]:
    strategies = card.get("strategies") if isinstance(card.get("strategies"), dict) else {}
    value = strategies.get("daily_tactical") if isinstance(strategies.get("daily_tactical"), dict) else None
    if value is None and isinstance(card.get("daily_tactical_summary"), dict):
        value = card["daily_tactical_summary"]
    return value or {}


def _review(card: dict[str, Any]) -> dict[str, Any]:
    for key in ("review_snapshot", "review_result", "outcome"):
        if isinstance(card.get(key), dict):
            return card[key]
    return {}


def _text(*values: Any) -> str:
    return " ".join(str(value).lower() for value in values if value is not None)


def _explicit_bool(card: dict[str, Any], tactical: dict[str, Any], review: dict[str, Any], keys: Iterable[str]) -> bool | None:
    for source in (review, tactical, card):
        for key in keys:
            value = source.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "yes", "hit", "triggered", "confirmed", "有效", "已觸發", "命中"}:
                    return True
                if normalized in {"false", "no", "miss", "failed", "invalidated", "未觸發", "失效", "未命中"}:
                    return False
    return None


def _classify(card: dict[str, Any]) -> dict[str, Any]:
    tactical, review = _tactical(card), _review(card)
    action_text = _text(tactical.get("action"), tactical.get("direction"), tactical.get("setup_type"), review.get("status"), review.get("result"), card.get("action"), card.get("latest_status"))
    no_trade = any(token in action_text for token in ("no_trade", "no trade", "暫不操作", "避免", "觀望"))
    invalidated = any(token in action_text for token in ("invalid", "failed", "失效", "failure", "loss", "停損"))
    triggered = _explicit_bool(card, tactical, review, ("triggered", "entry_triggered", "entry_result", "setup_triggered"))
    if triggered is None:
        triggered = True if any(token in action_text for token in ("triggered", "已觸發", "confirmed", "確認突破")) else False
    confidence = tactical.get("confidence", card.get("confidence"))
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = None
    chase = str(tactical.get("chase_risk") or card.get("chase_risk") or "unknown").lower()
    event = str(tactical.get("event_risk") or card.get("official_event_warning") or "unknown")
    direction_hit = _explicit_bool(card, tactical, review, ("direction_hit", "direction_result"))
    volume_confirmed = _explicit_bool(card, tactical, review, ("volume_confirmed", "volume_confirmation", "flow_confirmation"))
    gap_follow = _explicit_bool(card, tactical, review, ("gap_follow_through", "gap_continuation", "gap_effective"))
    outcome_text = _text(review.get("status"), review.get("result"), review.get("hit_miss_status"), review.get("outcome"))
    if no_trade:
        outcome = "no_trade"
    elif any(token in outcome_text for token in ("not_triggered", "not triggered", "未觸發")):
        outcome = "not_triggered"
    elif any(token in outcome_text for token in ("win", "hit", "success", "命中", "成功")):
        outcome = "win"
    elif any(token in outcome_text for token in ("loss", "miss", "failed", "失敗", "停損")):
        outcome = "loss"
    else:
        outcome = "pending"
    has_entry = tactical.get("entry_zone") is not None or tactical.get("entry_zone_low") is not None
    return {
        "id": _identifier(card), "no_trade": no_trade, "invalidated": invalidated,
        "triggered": bool(triggered), "still_actionable": bool(has_entry and not no_trade and not invalidated),
        "confidence": confidence_value, "chase_risk": chase, "event_risk": event,
        "direction_hit": direction_hit, "volume_confirmed": volume_confirmed,
        "gap_follow_through": gap_follow, "outcome": outcome,
        "entry_ready": bool(has_entry and not no_trade),
        "target": tactical.get("target_zone_1") or tactical.get("target_1") or tactical.get("target1"),
        "stop": tactical.get("stop_reference") or tactical.get("stop") or tactical.get("stop_invalidation"),
        "source": "cards[].strategies.daily_tactical / review_snapshot / review_result",
    }


def _ids(rows: list[dict[str, Any]], key: str, expected: Any = True) -> list[str]:
    return [row["id"] for row in rows if row.get(key) == expected]


def _distribution(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _confidence_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    values = Counter()
    for row in rows:
        score = row["confidence"]
        values["unknown" if score is None else "high" if score >= 70 else "medium" if score >= 45 else "low"] += 1
    return dict(values)


def project_decision_intelligence_v4(
    market: str,
    window: str,
    payload: dict[str, Any] | None,
    *,
    previous_projection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project one market/window payload without reading mutable global runtime."""
    market, window = normalize_window(market, window)
    spec = WINDOW_PRESENTATION[(market, window)]
    contract = get_window_report_contract(market, window)
    rows = [_classify(card) for card in _cards(payload)]
    outcomes = _distribution(row["outcome"] for row in rows)
    counts = {
        "total": len(rows),
        "top_opportunities": len([row for row in rows if row["entry_ready"] and (row["confidence"] or 0) >= 45]),
        "no_trade": len(_ids(rows, "no_trade")),
        "chase_risk": len([row for row in rows if row["chase_risk"] in {"high", "高"}]),
        "entry_ready": len(_ids(rows, "entry_ready")),
        "triggered": len(_ids(rows, "triggered")),
        "invalidated": len(_ids(rows, "invalidated")),
        "still_actionable": len(_ids(rows, "still_actionable")),
        "volume_confirmed": len(_ids(rows, "volume_confirmed")),
        "failed_gaps": len(_ids(rows, "gap_follow_through", False)),
        "direction_hit": len(_ids(rows, "direction_hit")),
        "reviewed": sum(value for key, value in outcomes.items() if key != "pending"),
    }
    prior_counts = previous_projection.get("counts", {}) if isinstance(previous_projection, dict) else {}
    deltas = {key: counts[key] - int(prior_counts[key]) for key in counts if key in prior_counts and isinstance(prior_counts[key], int)}
    return {
        "schema_version": SCHEMA_VERSION,
        "market": market,
        "window": window,
        "title": contract.title,
        "question": spec["question"],
        "expected_card_type": spec["card_type"],
        "section_inventory": list(spec["sections"]),
        "new_decision_fields": list(spec["new_fields"]),
        "suppressed_sections": list(spec["suppressed"]),
        "counts": counts,
        "lists": {
            "opportunities": [item["id"] for item in sorted(rows, key=lambda value: value["confidence"] or -1, reverse=True) if item["entry_ready"]][:5],
            "no_trade": _ids(rows, "no_trade"),
            "invalidated": _ids(rows, "invalidated"),
            "triggered": _ids(rows, "triggered"),
            "still_actionable": _ids(rows, "still_actionable"),
            "chase_risk": [row["id"] for row in rows if row["chase_risk"] in {"high", "高"}],
            "volume_confirmed": _ids(rows, "volume_confirmed"),
            "failed_gaps": _ids(rows, "gap_follow_through", False),
            "event_risk": [row["id"] for row in rows if str(row["event_risk"]).lower() not in {"", "low", "unknown", "none"}],
        },
        "outcome_distribution": outcomes,
        "confidence_distribution": _confidence_distribution(rows),
        "same_window_change": {"available": bool(previous_projection), "count_deltas": deltas, "policy": "same_market_same_window_previous_effective_trading_date"},
        "provenance": {
            "payload": "function argument: immutable snapshot payload or current window artifact",
            "classification": "explicit card tactical/review fields only",
            "cross_window_fallback": False,
            "invented_values": False,
        },
    }


def compact_summary(projection: dict[str, Any], channel: str) -> str:
    counts = projection["counts"]
    window = projection["window"]
    if window in {"pre_open_0700", "us_pre_market_2000"}:
        body = f"可行動 {counts['entry_ready']}、不交易 {counts['no_trade']}、追價風險 {counts['chase_risk']}"
    elif window in {"intraday_1305", "us_intraday_2300"}:
        body = f"已觸發 {counts['triggered']}、已失效 {counts['invalidated']}、仍可行動 {counts['still_actionable']}"
    elif window == "pre_close_1335":
        body = f"可留意 {counts['still_actionable']}、不留倉/不交易 {counts['no_trade']}、尾盤風險 {counts['chase_risk']}"
    else:
        dist = projection["outcome_distribution"]
        outcome_labels = {"win": "成功", "loss": "失敗", "not_triggered": "未觸發", "no_trade": "無交易", "pending": "待檢討"}
        body = "、".join(f"{outcome_labels.get(key, '其他')} {value}" for key, value in dist.items()) or "尚無可檢討資料"
    prefix = "摘要" if channel == "line" else "Decision Intelligence V4"
    return f"{prefix}：{body}"


def inventory_rows() -> list[dict[str, Any]]:
    return [
        {"market": market, "window": window, **spec}
        for (market, window), spec in WINDOW_PRESENTATION.items()
    ]
