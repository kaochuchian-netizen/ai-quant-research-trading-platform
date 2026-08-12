"""Safe shared presentation normalization for financial values and dates."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

UNSAFE_FINANCIAL_TEXT = "正式資料尚無法安全標準化"
MISSING_TEXT = "尚未取得"

ENUM_LABELS = {
    "wait": "等待", "watch": "觀察", "downtrend": "偏空趨勢", "sideways": "盤整",
    "unknown": "尚未判定", "neutral": "中性", "cancel_chase": "取消追價",
    "target_near": "接近目標", "entry_triggered_hold": "已觸發，續抱觀察",
    "wait_for_volume": "等待量能確認", "reduce_risk": "降低風險",
    "data_unavailable": "行情不足", "not_applicable": "不適用", "unavailable": MISSING_TEXT,
    "pending": "待確認", "hit": "命中", "fail": "失敗", "not_triggered": "未觸發",
    "no_trade": "無交易", "triggered": "已觸發", "inside_zone": "進入進場區",
    "not_reached": "尚未到達", "passed_without_safe_entry": "已偏離安全進場區",
    "invalidated": "已失效", "strong": "量能強勁", "confirmed": "量能確認",
    "normal": "一般", "weak": "量能偏弱", "high": "高", "medium": "中", "low": "低",
    "complete": "完整", "partial": "部分可用", "stale": "資料過舊",
    "bullish": "偏多", "bearish": "偏空", "maintain_watch": "維持觀察",
    "official_disclosure": "官方公告", "exchange_or_regulator": "交易所／主管機關",
    "company_ir": "公司 IR", "major_financial_media": "主要財經媒體",
    "general_media": "一般財經媒體", "social_or_unverified": "社群／未驗證來源",
    "uptrend": "偏多趨勢", "strong_uptrend": "強勢多頭", "mildly_bullish": "溫和偏多",
    "win": "交易命中", "loss": "交易失敗", "pending_evidence": "證據待補",
    "open_at_close": "收盤時交易尚未結束", "partial_hit": "預測區間部分命中",
    "hold_with_protection": "可留倉但需保護", "both_near": "雙向臨界",
    "wait_volume": "等待量能確認", "exit": "退出／停止原策略",
    "active": "正式交易計畫", "not_started": "尚未開始", "closed": "已結束",
    "not_hit": "未觸發",
    "available": "可用", "unclassified": "尚未分類", "miss": "預測區間未命中",
    "long": "偏多交易", "short": "偏空交易", "not_applicable": "不適用",
    "target_hit": "目標已觸及", "stop_hit": "停損已觸及",
    "mixed": "多空混合", "insufficient_evidence": "證據不足",
    "insufficient_new_evidence": "新增證據不足", "created": "研究假設已建立",
    "strengthened": "研究假設增強", "weakened": "研究假設減弱",
    "contradicted": "研究假設受到反證", "supportive": "支持", "adverse": "不利",
}

INSTRUCTION_LABELS = {
    "use deterministic entry_zone when present": "價格進入建議區間，且量價與風險條件符合",
    "setup not confirmed": "進場條件尚未確認",
    "reward/risk below 0.8 threshold": "風險報酬比低於 0.8，不符合交易門檻",
}


def localize_enum(value: Any, *, missing: str = MISSING_TEXT) -> str:
    if value is None or value == "":
        return missing
    text = str(value).strip()
    return ENUM_LABELS.get(text, INSTRUCTION_LABELS.get(text, text))


def safe_public_text(value: Any, *, missing: str = MISSING_TEXT) -> str:
    """Format one field without exposing provider errors, Python repr, or raw containers."""
    if value in (None, "", [], {}):
        return missing
    if isinstance(value, list):
        items = [safe_public_text(item, missing="") for item in value]
        return "、".join(item for item in items if item) or missing
    if isinstance(value, dict):
        if value.get("error") or value.get("error_type"):
            return "資料來源暫時無法取得"
        for key in ("summary", "conclusion", "reason", "direction", "status"):
            if value.get(key) not in (None, "", [], {}):
                return safe_public_text(value[key], missing=missing)
        return missing
    text = str(value).strip()
    lowered = text.lower()
    if "gemini error" in lowered or "deadline_exceeded" in lowered or text.startswith(("datetime.date(", "datetime.datetime(")):
        return "資料來源暫時無法取得"
    if text in {"None", "None / None", "[None, None]", "[]", "{}"}:
        return "不適用"
    return localize_enum(text, missing=missing)


def format_price_range(value: Any, *, missing: str = MISSING_TEXT) -> str:
    """Render a low/high mapping without exposing a Python/JSON representation."""
    if not isinstance(value, dict):
        return missing if value in (None, "", "not_applicable") else safe_public_text(value, missing=missing)
    try:
        low, high = float(value.get("low")), float(value.get("high"))
    except (TypeError, ValueError):
        return missing
    low, high = min(low, high), max(low, high)
    return f"{low:.2f}–{high:.2f}"


def _timestamp_datetime(value: Any, default_timezone: str) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        magnitude = abs(float(value))
        divisor = 1_000_000_000 if magnitude >= 1e18 else 1_000_000 if magnitude >= 1e15 else 1_000 if magnitude >= 1e12 else 1
        try:
            parsed = datetime.fromtimestamp(float(value) / divisor, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if text.isdigit() and 10 <= len(text) <= 19:
            return _timestamp_datetime(int(text), default_timezone)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
    return parsed


def _numeric_local_wall_time(value: Any, timezone_name: str) -> datetime | None:
    text = str(value or "").strip()
    if not text.isdigit() or not 10 <= len(text) <= 19:
        return None
    magnitude = abs(float(text))
    divisor = 1_000_000_000 if magnitude >= 1e18 else 1_000_000 if magnitude >= 1e15 else 1_000 if magnitude >= 1e12 else 1
    try:
        wall = datetime.fromtimestamp(float(text) / divisor, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None
    return wall.replace(tzinfo=ZoneInfo(timezone_name))


def format_timestamp(
    value: Any, *, timezone_name: str = "Asia/Taipei", missing: str = MISSING_TEXT,
    reference_value: Any = None,
) -> str:
    parsed = _timestamp_datetime(value, timezone_name)
    reference = _timestamp_datetime(reference_value, timezone_name)
    if parsed is not None and reference is not None and parsed > reference + timedelta(minutes=30):
        parsed = _numeric_local_wall_time(value, timezone_name) or parsed
    return missing if parsed is None else parsed.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S")


def format_market_time(
    value: Any, *, source_timezone: str | None = None, time_kind: str | None = None,
    reference_value: Any = None, trading_date: Any = None, market: str = "TW",
) -> tuple[str, str]:
    """Return an honest label/value pair using explicit source-time semantics."""
    if time_kind in {"trading_date_only", "daily_bar_close_marker"}:
        return ("行情日期", str(trading_date or value or MISSING_TEXT)[:10])
    zone = source_timezone or ("Asia/Taipei" if market.upper() == "TW" else "America/New_York")
    return ("行情時間", format_timestamp(value, timezone_name=zone, reference_value=reference_value))


def aggregate_card_timestamp(cards: list[dict[str, Any]], *, timezone_name: str = "Asia/Taipei") -> str | None:
    parsed = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        value = card.get("source_record_time") or card.get("market_data_as_of")
        item = _timestamp_datetime(value, timezone_name)
        reference = _timestamp_datetime(card.get("normalized_at") or card.get("fetched_at"), timezone_name)
        if item is not None and reference is not None and item > reference + timedelta(minutes=30):
            item = _numeric_local_wall_time(value, timezone_name) or item
        parsed.append(item)
    valid = [item for item in parsed if item is not None]
    return max(valid).astimezone(ZoneInfo(timezone_name)).isoformat() if valid else None


def format_distance(value: Any, *, kind: str) -> str:
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return "不適用" if value in (None, "", "not_applicable") else MISSING_TEXT
    amount = abs(distance)
    if kind == "target":
        if distance < -0.005:
            return f"已高於目標 {amount:.2f}%"
        if abs(distance) <= 0.005:
            return "已到達目標"
        return f"距目標 {amount:.2f}%"
    if kind == "stop":
        if distance > 0.005:
            return f"已低於停損 {amount:.2f}%"
        if abs(distance) <= 0.005:
            return "已觸及停損"
        return f"距停損仍有 {amount:.2f}%"
    raise ValueError("unsupported_distance_kind")


def next_action_for_outcome(outcome: Any) -> str:
    return {
        "hit": "已命中目標；明日觀察量能是否延續，並保護既有成果。",
        "fail": "已觸發失敗條件；明日不延續原 setup，等待重新評估。",
        "not_triggered": "今日未觸發；明日等待重新進入安全區間。",
        "no_trade": "今日無交易；明日重新評估。",
        "pending": "實際結果尚未完整；明日先確認資料完整性。",
        "win": "已命中目標；明日觀察量能是否延續，並保護既有成果。",
        "loss": "已觸發失敗條件；明日不延續原交易條件，等待重新評估。",
        "open_at_close": "交易於收盤仍持續；尚未觸及目標或停損，明日延續追蹤。",
        "pending_evidence": "行情或時序證據不足；補足證據後再判定。",
    }.get(str(outcome), "結果尚未判定；明日先確認資料完整性。").replace("setup", "交易條件")


def next_session_action(card: dict[str, Any]) -> str:
    holding = str(card.get("holding_decision") or "")
    if card.get("near_stop") or holding == "reduce":
        return "明日優先檢查停損風險，不新增部位。"
    if card.get("near_target") and holding == "hold":
        return "明日觀察量能是否延續；若量能轉弱，優先保護既有成果。"
    if holding == "avoid_overnight" or card.get("entry_trigger_state") == "passed_without_safe_entry":
        return "明日等待價格回到安全區間；未回落前不追價。"
    if holding == "no_trade":
        return "明日維持觀察，除非重新形成完整交易條件。"
    if holding == "hold":
        return "明日續看量價與風險條件，保留既有成果。"
    return "明日等待重新形成完整量價條件。"


def concise_news_summary(card: dict[str, Any]) -> dict[str, str]:
    detail = card.get("news_summary") or card.get("news_detail")
    retrieval = card.get("news_retrieval") if isinstance(card.get("news_retrieval"), dict) else {}
    evidence = card.get("news_items") if isinstance(card.get("news_items"), list) else []
    unavailable = not evidence or not detail or any(token in str(detail).lower() for token in ("gemini error", "deadline_exceeded", "暫時無法取得", "尚未取得可用分析"))
    if unavailable:
        attempted = retrieval.get("sources_attempted") or ["MOPS", "TWSE", "COMPANY_IR", "GENERAL_FINANCIAL_MEDIA"]
        reason = {
            "NO_RESULT": "最近 72 小時未找到可納入分析的新聞",
            "NO_MATERIAL_NEWS": "最近 72 小時沒有符合重大性門檻的新聞",
            "LOW_QUALITY_ONLY": "查詢結果缺少可追溯來源，未納入決策",
        }.get(str(retrieval.get("failure_reason")), "最近 72 小時未取得符合品質與重大性門檻的新聞")
        return {
            "direction": "無法判定", "status": "未取得可納入分析的內容",
            "reason": f"{reason}；已檢查：{'、'.join(attempted)}",
            "strategy_impact": "不調整原技術／策略排序",
            "source_quality": "不適用｜無可納入證據", "confidence": "不適用",
        }
    direction = localize_enum(card.get("news_direction") or card.get("predicted_direction") or "unknown")
    reason = safe_public_text(detail, missing="本批次無重大新聞變化")
    if len(reason) > 96:
        reason = reason[:93].rstrip("，；。 ") + "…"
    impact = str(card.get("news_strategy_impact") or "maintain_priority")
    impact_text = {
        "raise_priority": "提高觀察優先級，但仍需量價確認",
        "maintain_priority": "維持目前優先級",
        "lower_priority": "降低進場優先級，等待量能改善",
        "avoid_chasing": "降低進場優先級，量能未改善前不追價",
        "wait_for_confirmation": "等待正式資訊與量價確認",
        "no_material_effect": "目前對策略無重大影響",
    }.get(impact, "維持目前優先級")
    quality = str(card.get("news_source_class") or "not_applicable")
    source = {"high": "高｜官方一手來源", "medium_high": "中高｜專業或產業來源", "medium": "中｜一般財經媒體", "low": "低｜未充分確認", "not_applicable": "不適用｜無可納入證據"}.get(quality, "不適用｜無可納入證據")
    confidence_data = card.get("news_confidence") if isinstance(card.get("news_confidence"), dict) else {}
    score = confidence_data.get("score")
    level = {"high": "高", "medium": "中等", "low": "偏低", "not_applicable": "不適用"}.get(str(confidence_data.get("level")), "不適用")
    confidence = f"{score}%｜{level}" if isinstance(score, (int, float)) else level
    return {"direction": direction, "status": "分析可用", "reason": reason, "strategy_impact": impact_text, "source_quality": source, "confidence": confidence}


def format_adr_context(value: Any, *, strategy_action: Any = None) -> str:
    """Present ADR context without leaking provider field labels or raw objects."""
    if value in (None, "", [], {}):
        return MISSING_TEXT
    text = safe_public_text(value)
    import re
    match = re.search(r"(?:change rate|change_rate|漲跌幅)\s*[：:]?\s*([+-]?\d+(?:\.\d+)?)", text, re.I)
    if not match:
        return text.replace("change rate", "漲跌幅")
    change = float(match.group(1))
    direction = "上漲" if change > 0 else "下跌" if change < 0 else "持平"
    impact = "偏多" if change > 0 else "偏空" if change < 0 else "中性"
    suffix = "，但不改變目前無交易判斷" if str(strategy_action) == "no_trade" else "，作為盤前輔助參考"
    return f"TSM ADR：{direction} {abs(change):.2f}%｜資料時段：最近一個美股交易日｜策略影響：{impact}{suffix}"


def normalize_date_presentation(value: Any, *, timezone_name: str | None = None) -> str:
    if value is None or value == "":
        return "資料尚未取得"
    if isinstance(value, datetime):
        current = value
        if current.tzinfo is None:
            if not timezone_name:
                return UNSAFE_FINANCIAL_TEXT
            current = current.replace(tzinfo=ZoneInfo(timezone_name))
        elif timezone_name:
            current = current.astimezone(ZoneInfo(timezone_name))
        return current.isoformat(timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if text.startswith("datetime.date(") or text.startswith("datetime.datetime("):
        return UNSAFE_FINANCIAL_TEXT
    return text


def normalize_financial_value(
    value: Any, *, unit: str | None, currency: str | None, scale: Any = 1,
    source: str, period_end: Any = None, filing_date: Any = None,
) -> dict[str, Any]:
    raw = {"raw_value": value, "raw_unit": unit, "raw_currency": currency, "raw_scale": scale}
    try:
        number = Decimal(str(value))
        multiplier = Decimal(str(scale))
    except (InvalidOperation, ValueError, TypeError):
        number = None
        multiplier = None
    safe_currency = str(currency or "").upper()
    safe_unit = str(unit or "").lower()
    monetary = safe_unit in {"currency", "per_share"}
    currency_valid = safe_currency in {"USD", "TWD"} if monetary else safe_currency in {"", "USD", "TWD"}
    valid = number is not None and multiplier is not None and currency_valid and safe_unit in {"currency", "shares", "per_share", "ratio", "percent"}
    normalized = number * multiplier if valid else None
    return {
        **raw,
        "normalized_value": float(normalized) if normalized is not None else None,
        "normalized_unit": unit if valid else None,
        "normalized_currency": safe_currency if valid and monetary else None,
        "source": source,
        "period_end": normalize_date_presentation(period_end) if period_end else None,
        "filing_date": normalize_date_presentation(filing_date) if filing_date else None,
        "safe_to_present": valid,
        "presentation": str(float(normalized)) if valid else UNSAFE_FINANCIAL_TEXT,
    }
