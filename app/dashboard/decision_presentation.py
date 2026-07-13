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
