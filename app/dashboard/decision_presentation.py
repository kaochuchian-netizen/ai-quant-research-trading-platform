"""Human-readable presentation helpers for decision dashboards.

This module intentionally formats existing runtime fields only. It must not
calculate strategy scores, price levels, predictions, or review outcomes.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.reports.presentation_normalization import normalize_date_presentation

MISSING_TEXT = "暫無"


def clean_text(value: Any, *, missing: str = MISSING_TEXT) -> str:
    if value is None:
        return missing
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (date, datetime)):
        timezone_name = "Asia/Taipei" if isinstance(value, datetime) and value.tzinfo is None else None
        return normalize_date_presentation(value, timezone_name=timezone_name)
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


def format_large_number(value: Any, *, currency: str = "USD") -> str:
    if value is None:
        return MISSING_TEXT
    try:
        number = float(value)
    except (TypeError, ValueError):
        return clean_text(value)
    abs_number = abs(number)
    if abs_number >= 1_000_000_000:
        return f"{currency} {number / 1_000_000_000:.1f}B"
    if abs_number >= 1_000_000:
        return f"{currency} {number / 1_000_000:.1f}M"
    return f"{currency} {number:.0f}"


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


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _human_status(value: Any) -> str:
    text = clean_text(value, missing="")
    return {
        "live market data fetched": "已取得最新市場資料",
        "metadata checked": "已檢查資料來源狀態",
        "無近期重大 8-K metadata": "近期沒有重大 8-K 公告",
        "有近期 8-K": "有近期 8-K 重大事件公告",
        "available_reference": "參考資料可用",
        "news metadata": "新聞中繼資料已檢查",
        "metadata_available": "來源 metadata 可用",
        "unavailable": "尚未接入可驗證資料",
        "available": "可用",
        "us_daily_tactical_factor_v1": "美股短線因子 v1",
    }.get(text, text or "資料不足")


def _filing_label(form: Any) -> str:
    text = clean_text(form, missing="")
    return {
        "10-Q": "10-Q 季報",
        "10-K": "10-K 年報",
        "8-K": "8-K 重大事件公告",
        "6-K": "6-K 外國發行人公告",
        "20-F": "20-F 外國發行人年報",
    }.get(text, text or "近期沒有重大公告")


def _latest_sec_summary(card: dict[str, Any]) -> str:
    sec = _nested(card, "research_sections", "sec")
    if isinstance(sec, dict):
        latest = _first_dict(sec.get("latest_quarterly_report"), sec.get("latest_annual_report"))
        recent = sec.get("recent_8k_items")
        if isinstance(recent, list) and recent and isinstance(recent[0], dict):
            latest = recent[0]
        if latest:
            form = _filing_label(latest.get("form") or card.get("latest_sec_filing"))
            date = clean_text(latest.get("filing_date"), missing="")
            return f"最近 SEC：{form}" + (f"（{date}）" if date else "")
    latest_form = clean_text(card.get("latest_sec_filing"), missing="")
    if latest_form:
        return f"最近 SEC：{_filing_label(latest_form)}"
    return "最近 SEC：近期沒有重大公告"


def _earnings_summary(card: dict[str, Any]) -> str:
    earnings = _nested(card, "research_sections", "earnings")
    if isinstance(earnings, dict):
        latest = earnings.get("latest_earnings") if isinstance(earnings.get("latest_earnings"), dict) else {}
        eps = format_optional_price(latest.get("actual_eps")) if latest else MISSING_TEXT
        revenue_meta = latest.get("actual_revenue_normalized") if latest and isinstance(latest.get("actual_revenue_normalized"), dict) else None
        revenue = (
            clean_text(revenue_meta.get("presentation")) if revenue_meta else
            "正式資料尚無法安全標準化" if latest and latest.get("actual_revenue") is not None else MISSING_TEXT
        )
        next_earnings = _nested(earnings, "next_earnings", "expected_date")
        status = format_availability(earnings.get("earnings_status") or card.get("latest_earnings_status"))
        parts = [f"財報：{status}"]
        if eps != MISSING_TEXT:
            parts.append(f"EPS {eps}")
        if revenue != MISSING_TEXT:
            parts.append(f"營收 {revenue}")
        if clean_text(next_earnings, missing=""):
            parts.append(f"下次財報 {clean_text(next_earnings, missing='')}")
        return "；".join(parts)
    return f"財報：{format_availability(card.get('latest_earnings_status'))}"


def _fundamental_summary(card: dict[str, Any]) -> str:
    comparison = _nested(card, "research_sections", "fundamentals", "comparison")
    metrics = _nested(card, "research_sections", "fundamentals", "metrics")
    trend = clean_text(card.get("financial_quality"), missing="")
    if isinstance(comparison, dict):
        trend = clean_text(comparison.get("trend_direction"), missing=trend or "資料不足")
    revenue_growth = _nested(metrics, "revenue_growth_yoy", "value") if isinstance(metrics, dict) else None
    margin = _nested(metrics, "operating_margin", "value") if isinstance(metrics, dict) else None
    extras: list[str] = []
    if revenue_growth is not None:
        extras.append(f"營收成長 {format_percent(revenue_growth)}")
    if margin is not None:
        extras.append(f"營業利益率 {format_percent(margin)}")
    return "；".join([f"基本面：{trend or '資料不足'}", *extras])


def _material_news_summary(card: dict[str, Any]) -> str:
    symbol = clean_text(card.get("symbol") or card.get("stock_id"), missing="此股票")
    news = card.get("bilingual_news_snippet") if isinstance(card.get("bilingual_news_snippet"), dict) else {}
    headline = clean_text(news.get("chinese_translation") or news.get("english_headline"), missing="")
    reading = clean_text(news.get("investment_reading"), missing="")
    if headline and "無可驗證重大新聞" not in headline:
        return f"{symbol} 近期發布：{headline}"
    if reading and "未取得可安全引用新聞" not in reading:
        return f"{symbol}：{reading}"
    event = _human_status(card.get("official_event_warning"))
    if event and event not in {"資料不足", "暫無"}:
        return f"{symbol} 近期事件：{event}"
    return f"{symbol}：近三日未發現可驗證重大新聞"


def _news_event_layers(card: dict[str, Any]) -> dict[str, str]:
    symbol = clean_text(card.get("symbol") or card.get("stock_id"), missing="此股票")
    sec = _latest_sec_summary(card)
    earnings = _earnings_summary(card)
    official = f"{sec}；{earnings}"
    news = card.get("bilingual_news_snippet") if isinstance(card.get("bilingual_news_snippet"), dict) else {}
    headline = clean_text(news.get("chinese_translation") or news.get("english_headline"), missing="")
    reading = clean_text(news.get("investment_reading"), missing="")
    if headline and "無可驗證重大新聞" not in headline:
        market = f"{symbol} 市場參考新聞：{headline}（市場參考，非公司官方公告）"
        count = "1 則"
    elif reading and "未取得可安全引用新聞" not in reading:
        market = f"{symbol} 市場參考：{reading}（非公司官方公告）"
        count = "1 則"
    else:
        market = f"{symbol} 近期未發現可安全引用的市場新聞標題；本卡以官方文件、財報與價格資料為主要依據。"
        count = "0 則可安全引用"
    status = f"官方重大事件：已檢查；市場參考新聞：{count}；來源品質：中等"
    return {"official": official, "market": market, "status": status}


def _rating_reason(research: dict[str, Any], tactical: dict[str, Any], card: dict[str, Any]) -> str:
    rating = clean_text(research.get("rating") or card.get("research_rating") or card.get("rating"), missing="資料不足")
    action = clean_text(research.get("action") or card.get("action"), missing="中性觀察")
    reasons = [
        f"技術：{format_setup(tactical.get('setup_type'))} / {format_direction(tactical.get('tactical_direction') or tactical.get('direction'))}",
        _fundamental_summary(card).replace("基本面：", "基本面："),
        _material_news_summary(card),
    ]
    return f"{rating}｜{action}｜主要原因：" + "；".join(reasons)


def _research_reason_items(research: dict[str, Any], tactical: dict[str, Any], card: dict[str, Any]) -> list[str]:
    items: list[str] = []
    symbol = clean_text(card.get("symbol") or card.get("stock_id"), missing="此股票")
    rationale = clean_text(research.get("rationale"), missing="")
    tactical_rationale = clean_text(tactical.get("tactical_rationale"), missing="")
    technical = clean_text(card.get("technical_summary"), missing="")
    tactical_reasons = tactical.get("reasons") if isinstance(tactical.get("reasons"), list) else []
    if rationale:
        items.append(f"研究依據：{rationale}")
    if tactical_rationale and tactical_rationale not in items:
        tactical_rationale = tactical_rationale.replace(
            "Daily Tactical uses price momentum, trend, volatility, market context, and event risk. It is independent from Research / Position score.",
            "每日短線策略使用價格動能、趨勢、波動、市場脈絡與事件風險，並獨立於研究／持有評分。",
        )
        items.append(f"短線依據：{tactical_rationale}")
    for item in tactical_reasons[:3]:
        reason = clean_text(item, missing="")
        if reason:
            items.append(f"{symbol} 短線依據：{reason}")
    if technical:
        items.append(f"技術摘要：{technical}")
    items.append(_fundamental_summary(card))
    items.append(_latest_sec_summary(card))
    return limit_items(items, limit=5, fallback="目前沒有足夠依據")


def _risk_items(research: dict[str, Any], tactical: dict[str, Any], card: dict[str, Any]) -> list[str]:
    raw: list[Any] = []
    for value in (research.get("risk_notes"), tactical.get("risk_notes"), tactical.get("risk_reasons")):
        if isinstance(value, list):
            raw.extend(value)
    event = _human_status(card.get("official_event_warning"))
    if event:
        raw.append(f"事件風險：{event}")
    raw.append(f"追價風險：{format_risk_level(tactical.get('chase_risk'))}；事件風險：{format_risk_level(tactical.get('event_risk'))}")
    translated = [
        clean_text(item, missing="")
        .replace("Research / Position", "研究／持有策略")
        .replace("setup", "策略型態")
        for item in raw
    ]
    return limit_items(translated, limit=5, fallback="目前未偵測到額外風險")


def _review_summary(card: dict[str, Any], tactical: dict[str, Any]) -> str:
    symbol = clean_text(card.get("symbol") or card.get("stock_id"), missing="此股票")
    review = tactical.get("review_contract") if isinstance(tactical.get("review_contract"), dict) else {}
    status = review.get("status") or card.get("review_result")
    return f"{symbol} 策略檢討：{format_review_status(status)}；{clean_text(card.get('review_result'), missing='等待下一輪 runtime review')}"


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
    tactical = _first_dict(
        _nested(fallback, "strategies", "daily_tactical"),
        fallback.get("daily_tactical_summary"),
    )
    rating = clean_text(research.get("rating") or fallback.get("research_rating") or fallback.get("rating"), missing="資料不足")
    action = clean_text(research.get("action") or fallback.get("action"), missing="中性觀察")
    return {
        "rating": rating,
        "action": action,
        "confidence": format_confidence(research.get("confidence") or fallback.get("confidence")),
        "one_month": format_trend(prediction.get("one_month_trend") or fallback.get("one_month_trend")),
        "three_month": format_trend(prediction.get("three_month_trend") or fallback.get("three_month_trend")),
        "financial_quality": _fundamental_summary(fallback),
        "official_events": _human_status(fallback.get("official_event_warning")),
        "material_news": _material_news_summary(fallback),
        "sec": _latest_sec_summary(fallback),
        "earnings": _earnings_summary(fallback),
        "rating_detail": _rating_reason(research, tactical, fallback),
        "one_line_conclusion": f"{rating}：{action}；{format_direction(tactical.get('tactical_direction') or tactical.get('direction'))}",
        "conclusion": clean_text(research.get("action") or fallback.get("action"), missing="部分研究資料尚未完成"),
        "review": _review_summary(fallback, tactical),
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
    reasons = _research_reason_items(research, tactical, card)
    risks = _risk_items(research, tactical, card)
    return {
        "schema_version": "decision_presentation_v3",
        "market": market,
        "symbol": clean_text(symbol, missing=""),
        "name": clean_text(name, missing=""),
        "summary_cards": {
            "research": {"title": "中長期研究", "value": research_summary["rating"], "subvalue": research_summary["action"]},
            "daily_tactical": {"title": "每日短線策略", "value": tactical_plan["direction"], "subvalue": tactical_plan["action"]},
            "prediction": {"title": "預測", "value": prediction["today_range"], "subvalue": f"明日 {prediction['tomorrow_range']}"},
            "confidence": {"title": "信心", "value": tactical_plan["confidence"], "subvalue": f"研究 {research_summary['confidence']}"},
        },
        "daily_tactical": tactical_plan,
        "prediction": prediction,
        "research": research_summary,
        "reasons": reasons,
        "risks": risks,
        "research_v3": {
            "today_summary": research_summary["one_line_conclusion"],
            "one_line_conclusion": research_summary["one_line_conclusion"],
            "primary_evidence": reasons,
            "primary_risks": risks,
            "material_news": research_summary["material_news"],
            "earnings": research_summary["earnings"],
            "sec": research_summary["sec"],
            "research_rating": research_summary["rating_detail"],
            "research_conclusion": research_summary["conclusion"],
            "review": research_summary["review"],
            "news_events": _news_event_layers(card),
        },
        "technical_detail": {
            "factor_coverage": format_factor_coverage(tactical.get("factor_coverage") or tactical.get("source_status")),
            "score_components": format_score_components(tactical.get("score_components")),
            "strategy_id": clean_text(tactical.get("strategy_id"), missing="資料不足"),
            "factor_version": _human_status(tactical.get("factor_version")),
        },
    }


def decision_email_block_v2(presentation: dict[str, Any]) -> str:
    t = presentation["daily_tactical"]
    p = presentation["prediction"]
    r = presentation["research"]
    rv3 = presentation.get("research_v3", {})
    return "\n".join([
        f"{presentation['symbol']} {presentation['name']}",
        f"Research：{r['rating']} / {r['action']} / 信心 {r['confidence']}",
        f"今日研究摘要：{rv3.get('today_summary', r['conclusion'])}",
        f"Daily Tactical：{t['direction']} / {t['setup']} / {t['action']}",
        f"Prediction：今日 {p['today_range']}；明日 {p['tomorrow_range']}；信心 {p['confidence']}",
        f"Entry：{t['entry_zone']}｜Stop：{t['stop']}｜Target：{t['target_1']}｜RR：{t['reward_risk']}",
        f"主要依據：{'；'.join(presentation.get('reasons', []))}",
        f"主要風險：{'；'.join(presentation.get('risks', []))}",
        f"重大事件：{rv3.get('material_news', r['material_news'])}",
        f"財報：{rv3.get('earnings', r.get('earnings', '資料不足'))}",
        f"SEC：{rv3.get('sec', r['sec'])}",
        f"Review：{rv3.get('review', r.get('review', '資料不足'))}",
        f"研究結論：{rv3.get('research_conclusion', r['conclusion'])}",
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
    highlights = []
    for item in presentations[:6]:
        t = item.get("daily_tactical", {})
        p = item.get("prediction", {})
        r = item.get("research", {})
        highlights.append(
            f"{item.get('symbol')}：研究 {r.get('rating')}｜短線 {t.get('direction')} / {t.get('action')}｜今日預測 {p.get('today_range')}"
        )
    return "\n".join([
        f"{market_label}決策摘要已更新",
        f"研究摘要：{len(presentations)} 檔",
        f"短線可觀察：{tactical_watch}",
        f"今日不建議進場：{no_trade}",
        "重點：",
        *highlights,
        "今日預測：請看 Dashboard / Email",
        "Dashboard：",
        dashboard_url,
        "僅供研究參考，非交易指令。",
    ])
