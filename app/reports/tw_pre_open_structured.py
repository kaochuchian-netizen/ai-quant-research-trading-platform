"""TW 07:00 structured decision payload shared by every presentation channel."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.reports.presentation_normalization import (
    concise_news_summary,
    format_timestamp,
    normalize_date_presentation,
    safe_public_text,
)
from app.reports.tw_four_window_decision import canonical_news_direction, localize, sanitize_text, upgrade_pre_open_card

WINDOW = "pre_open_0700"
MARKET = "TW"
TAIPEI = ZoneInfo("Asia/Taipei")
REQUIRED_CARD_FIELDS = {
    "symbol", "name", "market", "window", "trading_date", "rating", "score", "action",
    "market_context", "overnight_context", "adr_context", "entry_readiness", "entry_condition",
    "entry_zone", "stop_level", "target_level", "risk_reward", "chase_risk", "gap_risk",
    "event_risk", "technical_summary", "chip_summary", "news_summary", "fundamental_summary",
    "reasoning", "risk_summary", "do_not_trade_reason", "data_freshness", "source_payload_hash",
}


def _first(mapping: Any, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if mapping.get(key) not in (None, ""):
            return mapping[key]
    return None


def _text(value: Any, fallback: str = "資料尚未取得") -> str:
    return sanitize_text(value, fallback)[:480]


def _action_group(action: str, available: bool) -> str:
    if not available:
        return "unavailable"
    text = action.lower()
    if any(token in text for token in ("避免", "暫不", "觀望", "no_trade", "no trade")):
        return "no_trade"
    if any(token in text for token in ("等待", "觀察", "watch")):
        return "watch"
    return "opportunity"


def _source_time(value: Any) -> Any:
    if isinstance(value, dict):
        return _first(value, "as_of", "published_at", "timestamp", "date", "fetched_at")
    if isinstance(value, list):
        candidates = [_source_time(item) for item in value]
        return next((item for item in candidates if item not in (None, "")), None)
    return None


def _available_text(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and not any(token in text for token in (
        "尚未取得", "尚未判定", "暫時無法取得", "無法判定", "unknown", "unavailable", "資料不足",
    ))


def _coverage(cards: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    total = len(cards)
    checks = {
        "technical": lambda c: _available_text(c.get("technical_summary")),
        "adr": lambda c: _available_text(c.get("adr_context")),
        "overnight": lambda c: _available_text(c.get("overnight_context")) or _available_text(c.get("adr_context")),
        "chip": lambda c: _available_text(c.get("chip_summary")),
        "news": lambda c: c.get("news_status") == "available" and canonical_news_direction(c.get("news_direction"), c.get("news_summary")) in {"bullish", "neutral", "bearish"},
        "gap": lambda c: _available_text(c.get("gap_risk")),
        "event_risk": lambda c: str(c.get("event_risk") or "") in {"low", "medium", "high"},
    }
    return {name: {"available": sum(bool(check(card)) for card in cards), "total": total} for name, check in checks.items()}


def _market_bias(coverage: dict[str, dict[str, int]], cards: list[dict[str, Any]]) -> dict[str, Any]:
    technical = coverage["technical"]["available"]
    supporting = sum(coverage[key]["available"] for key in ("adr", "chip", "news", "gap", "event_risk"))
    bearish = sum("偏空" in str(card.get("technical_summary")) for card in cards)
    bullish = sum("偏多" in str(card.get("technical_summary")) for card in cards)
    bias = "cautious" if bearish >= bullish or supporting < len(cards) else "neutral"
    confidence = "low" if technical and supporting < len(cards) * 2 else "medium"
    reasons = ["TECHNICAL_ONLY"] if technical else ["TECHNICAL_UNAVAILABLE"]
    if coverage["overnight"]["available"] < len(cards): reasons.append("OVERNIGHT_COVERAGE_LOW")
    if coverage["chip"]["available"] < len(cards): reasons.append("CHIP_UNAVAILABLE")
    if coverage["news"]["available"] < len(cards): reasons.append("NEWS_COVERAGE_LOW")
    return {"market_bias": bias, "market_bias_confidence": confidence, "market_bias_reason_codes": reasons}


def build_card(*, symbol: str, name: str, trading_date: str, indicator: dict[str, Any] | None = None, adr: dict[str, Any] | None = None, news: Any = None, chip: dict[str, Any] | None = None, score: dict[str, Any] | None = None, analysis: Any = None, tactical: dict[str, Any] | None = None, source_revision: int = 1, missing_fields: list[str] | None = None, generated_at: str | None = None) -> dict[str, Any]:
    indicator, adr, chip, score = indicator or {}, adr or {}, chip or {}, score or {}
    missing = sorted(set(missing_fields or []))
    basic_available = bool(indicator) and _first(indicator, "close", "date") is not None
    status = "complete" if basic_available and not missing else "partial" if basic_available else "unavailable"
    action = _text(_first(score, "action"), "unavailable" if not basic_available else "等待確認")
    rating = _first(score, "rating")
    decision_score = _first(score, "total_score", "score")
    try:
        numeric_score = float(decision_score)
    except (TypeError, ValueError):
        numeric_score = 0.0
    chase_risk = "high" if any(token in action for token in ("追價", "避免")) else "unknown" if not basic_available else "normal"
    group = _action_group(action, basic_available)
    entry_readiness = "ready_for_open_confirmation" if group == "opportunity" and numeric_score >= 65 else "wait" if group in {"opportunity", "watch"} else "no_trade" if group == "no_trade" else "unavailable"
    generated_at = generated_at or datetime.now(TAIPEI).replace(microsecond=0).isoformat()
    technical_as_of = _first(indicator, "date", "source_data_date")
    card: dict[str, Any] = {
        "symbol": str(symbol), "stock_id": str(symbol), "name": name, "stock_name": name,
        "market": MARKET, "window": WINDOW, "trading_date": trading_date,
        "rating": rating, "score": decision_score, "total_score": decision_score, "action": action,
        "market_context": "盤前依前一交易日收盤與可用市場資料判斷",
        "overnight_context": _text(_first(adr, "market_summary", "status")),
        "adr_context": _text(adr),
        "entry_readiness": entry_readiness, "entry_condition": _text(_first(analysis, "entry_condition")),
        "entry_zone": _first(analysis, "entry_zone"), "stop_level": _first(analysis, "stop", "stop_loss"),
        "target_level": _first(analysis, "target", "target_price"), "risk_reward": _first(analysis, "risk_reward"),
        "chase_risk": chase_risk,
        "gap_risk": _text(_first(analysis, "gap_risk"), "尚未判定"),
        "event_risk": _text(_first(analysis, "event_risk"), "尚未判定"),
        "technical_summary": _text(_first(indicator, "summary", "trend", "signal")),
        "chip_summary": _text(_first(chip, "summary", "chip_signal", "status")),
        "news_summary": _text(news), "fundamental_summary": "盤前關鍵判斷不使用未驗證的基本面即時補值",
        "reasoning": _text(analysis), "risk_summary": "資料不完整時等待確認，不追價",
        "do_not_trade_reason": "資料不足" if not basic_available else ("策略明確不交易" if group == "no_trade" else None),
        "unavailable_reason": "、".join(missing) if status != "complete" else None,
        "availability_status": status, "missing_fields": missing,
        "data_freshness": {
            "market_data_as_of": technical_as_of, "technical_as_of": technical_as_of,
            "news_as_of": _source_time(news),
            "chip_as_of": _source_time(chip) or (technical_as_of if chip else None),
            "adr_as_of": _source_time(adr),
            "fundamental_period": None, "report_generated_at": generated_at,
        },
        "opportunity_group": group,
        "risk_adjusted_score": numeric_score - (20 if chase_risk == "high" else 0) - (10 if status != "complete" else 0),
        "strategies": {"daily_tactical": {"action": action, "rating": rating, "score": decision_score, "confidence": decision_score, "entry_zone": _first(analysis, "entry_zone"), "target_1": _first(analysis, "target", "target_price"), "stop_invalidation": _first(analysis, "stop", "stop_loss"), "chase_risk": chase_risk}},
    }
    if tactical:
        card = upgrade_pre_open_card(card, tactical, source_revision=source_revision)
    else:
        raw = json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        card["source_payload_hash"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return card


def unavailable_card(symbol: str, name: str, trading_date: str, reason: str, generated_at: str | None = None) -> dict[str, Any]:
    return build_card(symbol=symbol, name=name, trading_date=trading_date, missing_fields=[reason, "market_data"], generated_at=generated_at)


def aggregate(cards: list[dict[str, Any]], tracking_symbols: list[str]) -> dict[str, Any]:
    symbols = [str(card.get("symbol") or card.get("stock_id") or "") for card in cards]
    symbol_of = lambda card: str(card.get("symbol") or card.get("stock_id") or "")
    if len(symbols) != len(set(symbols)):
        raise ValueError("duplicate_structured_pre_open_symbol")
    if symbols != [str(value) for value in tracking_symbols]:
        raise ValueError("structured_pre_open_symbol_order_mismatch")
    readiness_rank = {"entry_ready": 0, "ready_for_open_confirmation": 0, "watch": 1, "wait": 1, "no_trade": 2, "unavailable": 3}
    ranking = sorted(
        cards,
        key=lambda card: (
            readiness_rank.get(str(card.get("entry_readiness")), 4),
            -float(card.get("risk_adjusted_score") or 0),
            str(card.get("event_risk")),
            str(card.get("chase_risk")),
            str(card.get("symbol")),
        ),
    )
    top = [symbol_of(card) for card in ranking if card.get("entry_readiness") in {"entry_ready", "ready_for_open_confirmation"} and card.get("actionable") is not False]
    no_trade = [symbol_of(card) for card in ranking if card.get("opportunity_group") == "no_trade" or card.get("no_trade") is True or card.get("availability_status") == "unavailable"]
    watch = [symbol_of(card) for card in ranking if symbol_of(card) not in set(top + no_trade) and card.get("availability_status") != "unavailable"]
    unavailable = [symbol_of(card) for card in ranking if card.get("availability_status") == "unavailable"]
    avoid = [symbol_of(card) for card in ranking if card.get("chase_risk") == "high" and symbol_of(card) not in set(top + no_trade)]
    coverage = _coverage(cards)
    bias = _market_bias(coverage, cards)
    result = {
        "tracking_stock_count": len(tracking_symbols), "structured_card_count": len(cards),
        "rendered_card_count": len(cards), "tracking_symbols": list(tracking_symbols),
        "structured_card_symbols": symbols,
        "top_opportunity_count": len(top), "top_opportunity_symbols": top,
        "entry_ready_count": len(top), "entry_ready_symbols": top,
        "watch_only_count": len(watch), "watch_only_symbols": watch,
        "no_trade_count": len(no_trade), "no_trade_symbols": no_trade,
        "avoid_chase_count": len(avoid), "avoid_chase_symbols": avoid,
        "chase_risk_count": len(avoid),
        "partial_data_count": sum(card.get("availability_status") == "partial" for card in cards),
        "unavailable_count": sum(card.get("availability_status") == "unavailable" for card in cards),
        "ranking": [symbol_of(card) for card in ranking],
        "groups": {
            "top_opportunities": top, "watch_wait": watch, "watch_only": watch,
            "no_trade": no_trade, "high_chase_risk": avoid, "avoid_chase": avoid,
            "unavailable": unavailable,
        },
        "coverage": coverage,
        **bias,
    }
    primary = top + watch + no_trade
    if len(primary) != len(set(primary)) or set(primary) != set(symbols):
        raise ValueError("canonical_pre_open_category_partition_failed")
    return result


def validate_payload(payload: dict[str, Any]) -> list[str]:
    tracking = [str(value) for value in payload.get("tracking_symbols", [])]
    cards = payload.get("structured_pre_open_cards") if isinstance(payload.get("structured_pre_open_cards"), list) else []
    symbols = [str(card.get("symbol") or "") for card in cards if isinstance(card, dict)]
    errors = []
    if int(payload.get("tracking_stock_count") or 0) != len(tracking):
        errors.append("tracking_count")
    if tracking and not cards:
        errors.append("structured_cards_missing")
    if len(cards) != len(tracking):
        errors.append("structured_card_count")
    if "structured_card_count" in payload and int(payload.get("structured_card_count") or 0) != len(cards):
        errors.append("declared_structured_card_count")
    if "rendered_card_count" in payload and int(payload.get("rendered_card_count") or 0) != len(cards):
        errors.append("declared_rendered_card_count")
    if symbols != tracking:
        errors.append("symbol_parity")
    if len(symbols) != len(set(symbols)):
        errors.append("duplicate_symbol")
    if any(card.get("market") != MARKET for card in cards):
        errors.append("card_market")
    if any(card.get("window") != WINDOW for card in cards):
        errors.append("card_window")
    if any(REQUIRED_CARD_FIELDS - set(card) for card in cards):
        errors.append("required_card_fields")
    compatibility_cards = payload.get("cards")
    if isinstance(compatibility_cards, list) and compatibility_cards != cards:
        errors.append("compatibility_cards_mismatch")
    for card in cards:
        candidate = dict(card)
        retained_hash = candidate.pop("source_payload_hash", None)
        raw = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if retained_hash != hashlib.sha256(raw.encode("utf-8")).hexdigest():
            errors.append("card_source_payload_hash")
            break
    try:
        expected_summary = aggregate(cards, tracking)
    except ValueError:
        expected_summary = None
    observed_summary = payload.get("pre_open_summary")
    if expected_summary is not None and observed_summary != expected_summary:
        errors.append("pre_open_summary_mismatch")
    if isinstance(observed_summary, dict):
        group_sets = [set(observed_summary.get(key) or []) for key in ("top_opportunity_symbols", "watch_only_symbols", "no_trade_symbols")]
        if any(group_sets[i] & group_sets[j] for i in range(3) for j in range(i + 1, 3)):
            errors.append("category_exclusivity")
        if set().union(*group_sets) != set(tracking):
            errors.append("category_coverage")
    return errors


def _report_generated_at(payload: dict[str, Any]) -> Any:
    cards = payload.get("structured_pre_open_cards")
    if isinstance(cards, list) and cards and isinstance(cards[0], dict):
        freshness = cards[0].get("data_freshness")
        if isinstance(freshness, dict) and freshness.get("report_generated_at"):
            return freshness["report_generated_at"]
    return payload.get("generated_at")


def render_email(payload: dict[str, Any], url: str) -> str:
    summary=payload.get("pre_open_summary") or aggregate(payload.get("structured_pre_open_cards",[]),payload.get("tracking_symbols",[]))
    if not summary.get("coverage"):
        summary=aggregate(payload.get("structured_pre_open_cards",[]),payload.get("tracking_symbols",[]) or [str(card.get("symbol") or card.get("stock_id")) for card in payload.get("structured_pre_open_cards",[])])
    cards={str(card.get("symbol") or card.get("stock_id")):card for card in payload.get("structured_pre_open_cards",[])}
    top=summary["top_opportunity_symbols"]
    lines=["【Stock AI】07:00 台股盤前決策",f"交易日：{payload.get('effective_trading_date')}",f"市場基調：{'偏保守' if summary['market_bias']=='cautious' else '中性'}｜信心：{'偏低' if summary['market_bias_confidence']=='low' else '中'}","主要交易機會："]
    for symbol in top:
        card=cards[symbol]; lines.append(f"- {symbol} {safe_public_text(card.get('name'))}｜{safe_public_text(card.get('action'))}｜{localize(card.get('entry_readiness'))}｜依據：{safe_public_text(card.get('reasoning'))}｜風險：{safe_public_text(card.get('risk_summary'))}")
    if not top:
        lines.append("- 本批次沒有符合 entry、stop、target、風險報酬與資料完整度門檻的標的")
    news_cards = [card for card in payload.get("structured_pre_open_cards", []) if isinstance(card, dict)][:3]
    if news_cards:
        lines.append("新聞決策摘要：")
        for card in news_cards:
            news = concise_news_summary(card)
            lines.extend([
                f"- {card.get('symbol')} {safe_public_text(card.get('name'))}｜新聞方向：{news['direction']}",
                f"  主要原因：{news['reason']}",
                f"  策略影響：{news['strategy_impact']}｜來源品質：{news['source_quality']}｜信心：{news['confidence']}",
            ])
    coverage=summary["coverage"]
    lines += [f"觀察等待：{'、'.join(summary['watch_only_symbols']) or '無'}",f"暫不交易：{'、'.join(summary['no_trade_symbols']) or '無'}",f"避免追價：{'、'.join(summary['avoid_chase_symbols']) or '無'}",f"資料覆蓋：技術 {coverage['technical']['available']}/{coverage['technical']['total']}｜ADR／隔夜 {coverage['overnight']['available']}/{coverage['overnight']['total']}｜籌碼 {coverage['chip']['available']}/{coverage['chip']['total']}｜新聞 {coverage['news']['available']}/{coverage['news']['total']}",f"報告產生：{format_timestamp(_report_generated_at(payload))}","完整報告：",url,"僅供研究參考，非交易指令。"]
    return "\n".join(lines)


def render_line(payload: dict[str, Any], url: str) -> str:
    summary=payload.get("pre_open_summary") or aggregate(payload.get("structured_pre_open_cards",[]),payload.get("tracking_symbols",[]))
    if not summary.get("coverage"):
        summary=aggregate(payload.get("structured_pre_open_cards",[]),payload.get("tracking_symbols",[]) or [str(card.get("symbol") or card.get("stock_id")) for card in payload.get("structured_pre_open_cards",[])])
    top=summary["top_opportunity_symbols"]
    news_card = next((card for card in payload.get("structured_pre_open_cards", []) if isinstance(card, dict)), None)
    news_line = "新聞：本批次無重大新聞變化"
    if news_card:
        news = concise_news_summary(news_card)
        news_line = f"新聞：{news_card.get('symbol')} {news['direction']}｜{news['strategy_impact']}"
    coverage=summary["coverage"]
    return "\n".join(["【Stock AI】07:00 台股盤前決策",f"市場基調：{'偏保守' if summary['market_bias']=='cautious' else '中性'}｜信心：{'偏低' if summary['market_bias_confidence']=='low' else '中'}","依據：以前一交易日技術面為主；隔夜、籌碼與新聞覆蓋不足",f"主要交易機會：{'、'.join(top) or '無'}",f"觀察等待：{'、'.join(summary['watch_only_symbols']) or '無'}",f"暫不交易：{'、'.join(summary['no_trade_symbols']) or '無'}",f"避免追價：{'、'.join(summary['avoid_chase_symbols']) or '無'}",news_line,f"資料覆蓋：技術 {coverage['technical']['available']}/{coverage['technical']['total']}｜ADR／隔夜 {coverage['overnight']['available']}/{coverage['overnight']['total']}｜籌碼 {coverage['chip']['available']}/{coverage['chip']['total']}｜新聞 {coverage['news']['available']}/{coverage['news']['total']}","完整報告：",url])
