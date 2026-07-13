"""Human-readable presentation helpers for decision dashboards.

This module intentionally formats existing runtime fields only. It must not
calculate strategy scores, price levels, predictions, or review outcomes.
"""
from __future__ import annotations

from typing import Any

MISSING_TEXT = "暫無"


def clean_text(value: Any, *, missing: str = MISSING_TEXT) -> str:
    if value is None:
        return missing
    if isinstance(value, bool):
        return "是" if value else "否"
    text = str(value).strip()
    if not text or text in {"None", "null", "N/A", "nan", "資料待接"}:
        return missing
    return text


def format_availability(value: Any) -> str:
    return {
        "available": "可用",
        "available_reference": "參考資料可用",
        "unavailable": "尚未接入",
        "insufficient": "資料不足",
        "insufficient_data": "資料不足",
        "missing": "缺資料",
        "partial": "部分可用",
        "complete": "完整",
        "stale": "資料過期",
        "unknown": "資料不足",
    }.get(clean_text(value, missing="unknown"), clean_text(value, missing="資料不足"))


def format_direction(value: Any) -> str:
    return {
        "bullish": "偏多",
        "mildly_bullish": "溫和偏多",
        "neutral": "觀望",
        "mildly_bearish": "溫和偏空",
        "bearish": "偏空",
        "no_trade": "暫不操作",
        "unknown": "觀望",
    }.get(clean_text(value, missing="unknown"), clean_text(value, missing="觀望"))


def format_setup(value: Any) -> str:
    return {
        "breakout": "突破",
        "pullback": "拉回",
        "trend_continuation": "趨勢延續",
        "mean_reversion": "超跌反彈",
        "range_trade": "區間操作",
        "reversal_watch": "反轉觀察",
        "no_trade": "無適合策略",
        "insufficient_data": "資料不足",
        "unknown": "尚未形成策略",
    }.get(clean_text(value, missing="unknown"), clean_text(value, missing="尚未形成策略"))


def format_data_quality(value: Any) -> str:
    return {
        "complete": "完整",
        "partial": "部分完整",
        "limited": "有限",
        "insufficient": "不足",
        "insufficient_data": "資料不足",
        "available": "可用",
        "available_reference": "參考資料可用",
        "unavailable": "尚未接入",
        "not_applicable": "不適用",
        "limited_for_etf": "ETF 部分適用",
        "stale": "資料過期",
        "unknown": "資料不足",
    }.get(clean_text(value, missing="unknown"), clean_text(value, missing="資料不足"))


def format_position_size(value: Any) -> str:
    return {
        "normal": "一般部位",
        "half": "半部位",
        "small": "小部位",
        "avoid": "不建立部位",
    }.get(clean_text(value, missing="avoid"), clean_text(value, missing="不建立部位"))


def format_risk_level(value: Any) -> str:
    return {
        "low": "低",
        "medium": "中",
        "high": "高",
        "unknown": "資料不足",
    }.get(clean_text(value, missing="unknown"), clean_text(value, missing="資料不足"))


def format_review_status(value: Any) -> str:
    return {
        "pending": "待檢討",
        "no_trade": "無交易",
        "not_triggered": "尚未觸發",
        "win": "成功",
        "loss": "失敗",
        "breakeven": "損益兩平",
        "expired": "已失效",
        "insufficient_data": "資料不足",
        "invalid_data": "資料無效",
    }.get(clean_text(value, missing="pending"), clean_text(value, missing="待檢討"))


def format_trend(value: Any) -> str:
    return {
        "bullish": "偏多",
        "bearish": "偏空",
        "neutral": "中性",
        "uncertain": "不明朗",
        "insufficient_data": "資料不足",
        "unknown": "不明朗",
    }.get(clean_text(value, missing="unknown"), clean_text(value, missing="不明朗"))


def format_optional_price(value: Any) -> str:
    if value is None:
        return MISSING_TEXT
    try:
        number = float(value)
    except (TypeError, ValueError):
        return clean_text(value)
    return f"{number:.2f}".rstrip("0").rstrip(".")


def format_price_zone(zone: Any) -> str:
    if not isinstance(zone, dict):
        return MISSING_TEXT
    low = zone.get("low")
    high = zone.get("high")
    if low is None or high is None:
        return MISSING_TEXT
    return f"{format_optional_price(low)}–{format_optional_price(high)}"


def format_stop(value: Any) -> str:
    if isinstance(value, dict):
        price = format_optional_price(value.get("price"))
        reason = clean_text(value.get("reason"), missing="")
        return price if not reason else f"{price}｜{reason}"
    return format_optional_price(value)


def format_percent(value: Any) -> str:
    if value is None:
        return MISSING_TEXT
    try:
        number = float(value)
    except (TypeError, ValueError):
        return clean_text(value)
    if abs(number) <= 1:
        number *= 100
    return f"{number:.1f}%"


def format_ratio(value: Any) -> str:
    if value is None:
        return "資料不足"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return clean_text(value, missing="資料不足")


def format_confidence_level(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "資料不足"
    if score < 30:
        return "偏低"
    if score < 50:
        return "中低"
    if score < 70:
        return "中等"
    if score < 85:
        return "中高"
    return "高"


def format_confidence(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "資料不足"
    return f"{score:.0f}%｜{format_confidence_level(score)}"


def limit_items(items: Any, *, limit: int = 5, fallback: str = "目前沒有足夠資料") -> list[str]:
    if not isinstance(items, list):
        return [fallback]
    cleaned = [clean_text(item) for item in items if clean_text(item) != MISSING_TEXT]
    return cleaned[:limit] if cleaned else [fallback]


def format_factor_coverage(value: Any) -> list[tuple[str, str]]:
    labels = {
        "technical_engine": "技術分析",
        "technical": "技術分析",
        "historical_ohlcv": "歷史價量",
        "volume": "成交量",
        "support_resistance": "支撐壓力",
        "chip_engine": "法人籌碼",
        "twse_institutional_flow": "法人買賣超",
        "margin_short": "融資融券",
        "news_event": "新聞事件",
        "event_news": "新聞事件",
        "tw_market_context": "市場環境",
        "market_context": "市場環境",
        "price_trend": "價格趨勢",
        "research": "研究資料",
        "fundamentals": "財務資料",
        "sec": "SEC / 官方文件",
        "earnings": "財報與指引",
        "bilingual_news": "雙語新聞",
    }
    if isinstance(value, dict) and isinstance(value.get("statuses"), dict):
        value = value["statuses"]
    if not isinstance(value, dict):
        return [("資料來源", "資料不足")]
    return [(labels.get(str(key), str(key).replace("_", " ")), format_data_quality(status)) for key, status in value.items()]


def format_score_components(value: Any) -> list[tuple[str, str]]:
    labels = {
        "technical_setup": "技術型態",
        "volume_confirmation": "量能確認",
        "chip_flow": "籌碼",
        "market_context": "市場環境",
        "risk_quality": "風險品質",
        "data_quality": "資料品質",
        "risk_penalty": "風險扣分",
        "data_quality_penalty": "資料扣分",
        "technical": "技術",
        "news": "新聞",
        "research": "研究",
    }
    if not isinstance(value, dict):
        return [("分數構成", "資料不足")]
    rows: list[tuple[str, str]] = []
    for key, score in value.items():
        try:
            text = f"{float(score):.2f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            text = clean_text(score, missing="資料不足")
        rows.append((labels.get(str(key), str(key).replace("_", " ")), text))
    return rows or [("分數構成", "資料不足")]


def is_no_trade(tactical: dict[str, Any]) -> bool:
    return (
        clean_text(tactical.get("setup_type"), missing="no_trade") == "no_trade"
        or clean_text(tactical.get("direction"), missing="no_trade") == "no_trade"
        or clean_text(tactical.get("position_size"), missing="avoid") == "avoid"
    )



def _zone_from_flat(payload: dict[str, Any], low_key: str, high_key: str) -> str:
    low = payload.get(low_key)
    high = payload.get(high_key)
    if low is None or high is None:
        return MISSING_TEXT
    return f"{format_optional_price(low)}–{format_optional_price(high)}"


def prediction_summary_from_tw_card(card: dict[str, Any]) -> dict[str, str]:
    snapshot = card.get("prediction_snapshot", {}) if isinstance(card.get("prediction_snapshot"), dict) else {}
    research = (card.get("strategies", {}) or {}).get("research_position", {}) if isinstance(card.get("strategies"), dict) else {}
    research_prediction = research.get("prediction", {}) if isinstance(research.get("prediction"), dict) else {}
    today = _zone_from_flat(snapshot, "target_1_low", "target_1_high")
    tomorrow = _zone_from_flat(snapshot, "target_2_low", "target_2_high")
    if today == MISSING_TEXT:
        today = format_price_zone(research_prediction.get("same_day_high_low"))
    if tomorrow == MISSING_TEXT:
        tomorrow = format_price_zone(research_prediction.get("next_day_high_low"))
    reason = "資料不足：目前 prediction snapshot 沒有完整價位。" if today == MISSING_TEXT and tomorrow == MISSING_TEXT else "依現有 runtime prediction snapshot 呈現。"
    return {
        "today_range": today,
        "tomorrow_range": tomorrow,
        "expected_range": today if today != MISSING_TEXT else tomorrow,
        "expected_move": format_percent(snapshot.get("expected_move_pct")),
        "confidence": format_confidence(snapshot.get("confidence") or research.get("confidence")),
        "status": "資料不足" if today == MISSING_TEXT and tomorrow == MISSING_TEXT else "可參考",
        "reason": reason,
    }


def prediction_summary_from_us_card(card: dict[str, Any]) -> dict[str, str]:
    today = clean_text(card.get("session_predicted_high_low"), missing=MISSING_TEXT)
    tomorrow = clean_text(card.get("next_session_predicted_high_low"), missing=MISSING_TEXT)
    return {
        "today_range": today,
        "tomorrow_range": tomorrow,
        "expected_range": today if today != MISSING_TEXT else tomorrow,
        "expected_move": MISSING_TEXT,
        "confidence": format_confidence(card.get("confidence")),
        "status": "資料不足" if today == MISSING_TEXT and tomorrow == MISSING_TEXT else "可參考",
        "reason": "Production runtime prediction range." if today != MISSING_TEXT or tomorrow != MISSING_TEXT else "Prediction unavailable：runtime artifact 未提供完整區間。",
    }


def format_tactical_action(value: Any) -> str:
    text = clean_text(value, missing="等待確認")
    return {
        "wait_trigger": "等待觸發",
        "wait_for_trigger": "等待觸發",
        "breakout_pending": "等待突破",
        "breakout_confirmation": "等待突破確認",
        "pullback_pending": "等待拉回",
        "range_trade": "等待進入區間",
        "wait_stabilization": "等待止穩",
        "no_trade": "暫不操作",
        "avoid": "暫不操作",
    }.get(text, text)


def is_explicit_no_trade(tactical: dict[str, Any]) -> bool:
    setup = clean_text(tactical.get("setup_type"), missing="")
    direction = clean_text(tactical.get("direction") or tactical.get("tactical_direction"), missing="")
    position = clean_text(tactical.get("position_size"), missing="")
    action = clean_text(tactical.get("action"), missing="").lower().replace(" ", "_")
    return (
        setup == "no_trade"
        or direction == "no_trade"
        or position == "avoid"
        or action in {"no_trade", "avoid", "avoid_trade", "暫不操作", "今日不建議進場"}
    )


def tactical_plan_from_payload(tactical: dict[str, Any]) -> dict[str, str]:
    tactical = tactical if isinstance(tactical, dict) else {}
    no_trade = is_explicit_no_trade(tactical)
    entry = tactical.get("entry_zone")
    stop = tactical.get("stop_invalidation") or tactical.get("stop_reference") or tactical.get("invalidation_level")
    target1 = tactical.get("target_1") or tactical.get("target_zone_1")
    target2 = tactical.get("target_2") or tactical.get("target_zone_2")
    expected = tactical.get("expected_move_pct") if tactical.get("expected_move_pct") is not None else tactical.get("expected_move")
    rr = tactical.get("reward_risk") if tactical.get("reward_risk") is not None else tactical.get("reward_risk_ratio")
    action = "今日不建議進場" if no_trade else format_tactical_action(tactical.get("action"))
    return {
        "direction": format_direction(tactical.get("direction") or tactical.get("tactical_direction")),
        "setup": format_setup(tactical.get("setup_type")),
        "action": action,
        "entry_zone": format_price_zone(entry),
        "stop": format_stop(stop),
        "target_1": format_price_zone(target1),
        "target_2": format_price_zone(target2),
        "expected_move": format_percent(expected),
        "reward_risk": format_ratio(rr),
        "confidence": format_confidence(tactical.get("confidence") or tactical.get("tactical_confidence")),
        "risk": format_risk_level(tactical.get("chase_risk") or tactical.get("event_risk")),
        "position_size": format_position_size(tactical.get("position_size")),
        "data_quality": format_data_quality(tactical.get("data_quality")),
        "conclusion": action if no_trade else format_tactical_action(tactical.get("action")),
    }


def research_summary_from_payload(research: dict[str, Any], fallback: dict[str, Any] | None = None) -> dict[str, str]:
    fallback = fallback or {}
    prediction = research.get("prediction", {}) if isinstance(research.get("prediction"), dict) else {}
    return {
        "rating": clean_text(research.get("rating") or fallback.get("rating"), missing="資料不足"),
        "action": clean_text(research.get("action") or fallback.get("action"), missing="資料不足"),
        "confidence": format_confidence(research.get("confidence") or fallback.get("confidence")),
        "one_month": format_trend(prediction.get("one_month_trend") or fallback.get("one_month_trend")),
        "three_month": format_trend(prediction.get("three_month_trend") or fallback.get("three_month_trend")),
        "financial_quality": clean_text(fallback.get("financial_quality"), missing="資料不足"),
        "official_events": clean_text(fallback.get("official_event_warning"), missing="資料不足"),
        "material_news": clean_text(fallback.get("material_news") or fallback.get("latest_status"), missing="資料不足"),
        "sec": clean_text(fallback.get("latest_sec_filing"), missing="資料不足"),
        "conclusion": clean_text(research.get("action") or fallback.get("action"), missing="部分研究資料尚未完成"),
    }


def decision_presentation_v2(market: str, card: dict[str, Any]) -> dict[str, Any]:
    strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
    if market == "US":
        research = strategies.get("research_position") or card.get("research_position_summary") or {}
        tactical = strategies.get("daily_tactical") or card.get("daily_tactical_summary") or {}
        research = research if isinstance(research, dict) else {}
        tactical = tactical if isinstance(tactical, dict) else {}
        prediction = prediction_summary_from_us_card(card)
        symbol = card.get("symbol") or card.get("stock_id")
        name = card.get("name") or card.get("stock_name")
    else:
        research = strategies.get("research_position", {}) if isinstance(strategies.get("research_position"), dict) else {}
        tactical = strategies.get("daily_tactical", {}) if isinstance(strategies.get("daily_tactical"), dict) else {}
        prediction = prediction_summary_from_tw_card(card)
        symbol = card.get("stock_id") or card.get("symbol")
        name = card.get("stock_name") or card.get("name")
    tactical_plan = tactical_plan_from_payload(tactical)
    research_summary = research_summary_from_payload(research, card)
    return {
        "schema_version": "decision_presentation_v2",
        "market": market,
        "symbol": clean_text(symbol, missing=""),
        "name": clean_text(name, missing=""),
        "summary_cards": {
            "research": {"title": "Research", "value": research_summary["rating"], "subvalue": research_summary["action"]},
            "daily_tactical": {"title": "Daily Tactical", "value": tactical_plan["direction"], "subvalue": tactical_plan["action"]},
            "prediction": {"title": "Prediction", "value": prediction["today_range"], "subvalue": f"明日 {prediction['tomorrow_range']}"},
            "confidence": {"title": "Confidence", "value": tactical_plan["confidence"], "subvalue": f"Research {research_summary['confidence']}"},
        },
        "daily_tactical": tactical_plan,
        "prediction": prediction,
        "research": research_summary,
        "reasons": limit_items(tactical.get("reasons"), fallback="目前沒有足夠依據"),
        "risks": limit_items(tactical.get("risk_reasons") or tactical.get("risk_notes"), fallback="目前未偵測到額外風險"),
        "technical_detail": {
            "factor_coverage": format_factor_coverage(tactical.get("factor_coverage") or tactical.get("source_status")),
            "score_components": format_score_components(tactical.get("score_components")),
            "strategy_id": clean_text(tactical.get("strategy_id"), missing="資料不足"),
            "factor_version": clean_text(tactical.get("factor_version"), missing="資料不足"),
        },
    }


def decision_email_block_v2(presentation: dict[str, Any]) -> str:
    t = presentation["daily_tactical"]
    p = presentation["prediction"]
    r = presentation["research"]
    return "\n".join([
        f"{presentation['symbol']} {presentation['name']}",
        f"Research：{r['rating']} / {r['action']} / 信心 {r['confidence']}",
        f"Daily Tactical：{t['direction']} / {t['setup']} / {t['action']}",
        f"Prediction：今日 {p['today_range']}；明日 {p['tomorrow_range']}；信心 {p['confidence']}",
        f"Entry：{t['entry_zone']}｜Stop：{t['stop']}｜Target：{t['target_1']}｜RR：{t['reward_risk']}",
        f"Risk：追價/事件 {t['risk']}｜資料 {t['data_quality']}",
    ])


def decision_line_summary_v2(market_label: str, presentations: list[dict[str, Any]], dashboard_url: str) -> str:
    tactical_watch = 0
    no_trade = 0
    for item in presentations:
        action = item.get("daily_tactical", {}).get("action")
        if action == "今日不建議進場":
            no_trade += 1
        else:
            tactical_watch += 1
    return "\n".join([
        f"{market_label}決策摘要已更新",
        f"Research：{len(presentations)} 檔",
        f"Daily Tactical 可觀察：{tactical_watch}",
        f"今日不建議進場：{no_trade}",
        "今日預測：請看 Dashboard / Email",
        "Dashboard：",
        dashboard_url,
        "僅供研究參考，非交易指令。",
    ])
