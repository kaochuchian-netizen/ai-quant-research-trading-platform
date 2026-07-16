"""TW 15:00 structured review payload shared by archive and delivery channels."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
SCHEMA_VERSION = "tw_post_close_structured_review_v1"


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _outcome(review: dict[str, Any], tactical: dict[str, Any]) -> str:
    raw = " ".join(str(review.get(key) or "").strip().lower() for key in (
        "outcome", "status", "hit_miss_status", "direction_result",
    ))
    if any(token in raw for token in ("partial_hit", "hit", "win", "success", "命中", "成功")):
        return "hit"
    if any(token in raw for token in ("not_triggered", "not triggered", "未觸發")):
        return "not_triggered"
    if any(token in raw for token in ("miss", "loss", "fail", "失敗", "未命中")):
        return "fail"
    action = str(tactical.get("action") or "").strip().lower()
    if any(token in action for token in ("no_trade", "no trade", "觀望", "避免", "暫不操作")):
        return "no_trade"
    return "pending"


def build_structured_review_payload(
    review_runtime: dict[str, Any] | None,
    window_runtime: dict[str, Any] | None,
    *,
    effective_batch_time: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Join formal review rows to the matching 15:00 tactical rows without fallback."""
    review_runtime = review_runtime if isinstance(review_runtime, dict) else {}
    window_runtime = window_runtime if isinstance(window_runtime, dict) else {}
    tactical_by_id = {
        str(item.get("stock_id")): item
        for item in _dicts(window_runtime.get("cards"))
        if item.get("stock_id")
    }
    cards: list[dict[str, Any]] = []
    for review in _dicts(review_runtime.get("stocks")):
        stock_id = str(review.get("stock_id") or "")
        if not stock_id:
            continue
        tactical_card = tactical_by_id.get(stock_id, {})
        strategies = tactical_card.get("strategies") if isinstance(tactical_card.get("strategies"), dict) else {}
        tactical = strategies.get("daily_tactical") if isinstance(strategies.get("daily_tactical"), dict) else {}
        if not tactical:
            tactical = tactical_card
        outcome = _outcome(review, tactical)
        direction = {
            "predicted": review.get("predicted_direction"),
            "actual": review.get("actual_direction"),
            "result": review.get("direction_result"),
        }
        trigger = {
            "status": review.get("entry_result") or ("not_triggered" if outcome == "not_triggered" else "pending"),
            "entry_zone": tactical.get("entry_zone"),
        }
        stop = {
            "plan": tactical.get("stop_invalidation") or tactical.get("stop"),
            "result": review.get("stop_result") or "pending",
        }
        target = {
            "target_1": tactical.get("target_1"),
            "target_2": tactical.get("target_2"),
            "target_1_result": review.get("target_1_result") or "pending",
            "target_2_result": review.get("target_2_result") or "pending",
        }
        review_snapshot = {
            "status": outcome,
            "hit_miss_status": review.get("hit_miss_status"),
            "direction_result": review.get("direction_result"),
            "entry_result": trigger["status"],
            "stop_result": stop["result"],
            "target_1_result": target["target_1_result"],
            "target_2_result": target["target_2_result"],
            "actual_range": [review.get("actual_low"), review.get("actual_high")],
            "mfe": review.get("mfe"),
            "mae": review.get("mae"),
            "false_breakout": review.get("false_breakout"),
        }
        cards.append({
            "schema_version": SCHEMA_VERSION,
            "stock_id": stock_id,
            "stock_name": str(review.get("stock_name") or tactical_card.get("stock_name") or ""),
            "outcome": outcome,
            "direction": direction,
            "trigger": trigger,
            "stop": stop,
            "target": target,
            "result": review.get("hit_miss_status") or outcome,
            "review": review.get("recommendation_for_improvement") or "正式檢討資料待補齊。",
            "next_action": tactical.get("action") or tactical_card.get("action") or "維持觀察",
            "review_snapshot": review_snapshot,
            "strategies": {"daily_tactical": dict(tactical)},
            "source_evidence": review.get("source_evidence") or [],
            "advisory_only": True,
        })
    counts = Counter(card["outcome"] for card in cards)
    distribution = {key: int(counts.get(key, 0)) for key in ("hit", "not_triggered", "fail", "no_trade", "pending")}
    body = {"cards": cards, "outcome_counts": distribution}
    content_hash = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    generated = generated_at or review_runtime.get("generated_at")
    rates = [
        float(item["seven_day_hit_rate"])
        for item in _dicts(review_runtime.get("stocks"))
        if isinstance(item.get("seven_day_hit_rate"), (int, float)) and not isinstance(item.get("seven_day_hit_rate"), bool)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "market": "TW",
        "window": "post_close_1500",
        "effective_trading_date": review_runtime.get("review_date"),
        "effective_batch_time": effective_batch_time,
        "source_data_time": window_runtime.get("source_data_time"),
        "generated_at": generated,
        "tracking_stock_count": len(cards),
        "rendered_review_card_count": len(cards),
        "structured_review_cards": cards,
        "outcome_counts": distribution,
        "review_content_hash": content_hash,
        "seven_day_sample_count": len(rates),
        "seven_day_hit_rate": (sum(rates) / len(rates)) if rates else None,
        "source_contract": "formal_prediction_review_runtime + matching post_close_1500 window runtime",
        "cross_window_fallback": False,
        "fixture": False,
        "validation_only": False,
    }


def _taipei_display(value: Any, fallback: str = "尚未取得") -> str:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(TAIPEI).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def render_email(payload: dict[str, Any], dashboard_url: str, *, snapshot_id: str = "", revision: int | None = None, payload_hash: str = "") -> str:
    counts = payload.get("outcome_counts", {})
    cards = _dicts(payload.get("structured_review_cards"))
    ranked = sorted(cards, key=lambda card: ({"hit": 0, "pending": 1, "fail": 2, "not_triggered": 3, "no_trade": 4}.get(str(card.get("outcome")), 9), str(card.get("stock_id"))))
    lines = [
        "【Stock AI】15:00 台股盤後檢討",
        f"交易日：{payload.get('effective_trading_date') or '尚未取得'}",
        f"盤後批次：{_taipei_display(payload.get('effective_batch_time'))}",
        f"行情時間：{_taipei_display(payload.get('source_data_time'))}",
        f"報告產生：{_taipei_display(payload.get('generated_at'))}",
        f"Tracking：{payload.get('tracking_stock_count', 0)}｜Rendered：{payload.get('rendered_review_card_count', 0)}",
        f"今日結果：命中 {counts.get('hit', 0)}｜未觸發 {counts.get('not_triggered', 0)}｜失敗 {counts.get('fail', 0)}｜無交易 {counts.get('no_trade', 0)}｜待確認 {counts.get('pending', 0)}",
        (f"7 日檢討：有效樣本 {payload.get('seven_day_sample_count', 0)}｜平均命中率 {float(payload.get('seven_day_hit_rate')):.1%}"
         if payload.get("seven_day_hit_rate") is not None else "7 日檢討：待累積"),
    ]
    if snapshot_id:
        lines.append(f"Snapshot：{snapshot_id}｜Revision {revision or 1}｜Payload {payload_hash}")
    if ranked:
        lines += ["", "代表性檢討："]
        for card in ranked[:5]:
            lines.append(f"- {card.get('stock_id')} {card.get('stock_name')}：{card.get('outcome')}｜{card.get('review')}｜下一步 {card.get('next_action')}")
    else:
        lines += ["", "本批次尚未建立正式 Review Payload。不跨 window 補值，不使用 Sample 或 Fixture。"]
    lines += ["", "完整報告：", dashboard_url, "僅供研究參考，非交易指令。"]
    return "\n".join(lines)


def render_line(payload: dict[str, Any], dashboard_url: str) -> str:
    counts = payload.get("outcome_counts", {})
    review_line = (f"7 日檢討：有效樣本 {payload.get('seven_day_sample_count', 0)}｜平均命中率 {float(payload.get('seven_day_hit_rate')):.1%}"
                   if payload.get("seven_day_hit_rate") is not None else "7 日檢討：待累積")
    return "\n".join([
        "【Stock AI】15:00 台股盤後檢討",
        f"命中 {counts.get('hit', 0)}｜未觸發 {counts.get('not_triggered', 0)}｜失敗 {counts.get('fail', 0)}",
        f"無交易 {counts.get('no_trade', 0)}｜待確認 {counts.get('pending', 0)}",
        f"Tracking {payload.get('tracking_stock_count', 0)}｜Rendered {payload.get('rendered_review_card_count', 0)}",
        review_line,
        "完整報告：",
        dashboard_url,
    ])
