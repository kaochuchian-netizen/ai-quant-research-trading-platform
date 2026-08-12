"""Production research projection for the four canonical TW windows.

This module converts already-admitted TW evidence into RRE V1 notes.  It is a
read-only projection: canonical decisions remain inputs and are never changed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from app.research.tw_production_intelligence_v2 import effective_coverage, instrument_context, technical_evidence

from .projection import MODEL_BOUNDARY, build_research_reasoning_projection

WINDOWS = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
MISSING_LABELS = {
    "INSUFFICIENT_HISTORY": "技術歷史",
    "TREND_UNAVAILABLE": "趨勢確認",
    "CHIP_UNAVAILABLE": "籌碼",
    "NEWS_UNAVAILABLE": "新聞",
    "GAP_UNAVAILABLE": "Gap",
    "EVENT_RISK_UNAVAILABLE": "事件風險",
    "VOLUME_UNAVAILABLE": "量能",
}
CLASS_LABELS = {
    "market": "市場", "macro": "總經", "technical": "技術", "fundamental": "基本面",
    "news": "新聞", "etf": "ETF", "adr": "ADR", "chip": "籌碼", "sector": "產業",
    "corporate": "公司", "event": "事件",
}
WINDOW_LABELS = {
    "pre_open_0700": "研究晨報",
    "intraday_1305": "盤中研究更新",
    "pre_close_1335": "收盤前研究敘事",
    "post_close_1500": "盤後研究檢討",
}
DIRECTION_LABELS = {
    "bullish": "偏多", "bearish": "偏空", "neutral": "中性",
    "unavailable": "無法判定",
}


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip() or fallback
    return fallback


def _symbol(card: dict[str, Any]) -> str:
    return _text(card.get("symbol") or card.get("stock_id"), "UNKNOWN").upper()


def _name(card: dict[str, Any]) -> str:
    return _text(card.get("name") or card.get("stock_name"), _symbol(card))


def _iso(value: Any, fallback: str) -> str:
    text = _text(value)
    if not text:
        return fallback
    try:
        if "," in text or text.endswith((" GMT", " UTC")):
            parsed = parsedate_to_datetime(text)
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except (TypeError, ValueError):
        return fallback


def _direction(value: Any) -> str:
    raw = _text(value).lower()
    if raw in {"bullish", "uptrend", "strong_uptrend", "long", "偏多", "偏多趨勢"}:
        return "bullish"
    if raw in {"bearish", "downtrend", "short", "偏空", "偏空趨勢"}:
        return "bearish"
    if raw in {"neutral", "sideways", "中性", "盤整"}:
        return "neutral"
    return "unavailable"


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = re.search(r"[-+]?\d+(?:\.\d+)?", _text(value))
    return float(match.group()) if match else None


def _available(value: Any) -> bool:
    text = str(value or "").lower()
    return bool(value) and not any(token in text for token in (
        "尚未取得", "無法判定", "不適用", "unavailable", "unknown", "none",
        "不使用未驗證", "暫時無法取得",
    ))


def _record(
    *,
    market_time: str,
    symbol: str,
    evidence_class: str,
    source: str,
    summary: str,
    direction: str,
    coverage: str = "AVAILABLE",
    confidence: float = .7,
    reliability: float = .75,
    published_at: Any = None,
    reference: Any = None,
    materiality: str = "medium",
    research_role: str = "substantive",
) -> dict[str, Any]:
    return {
        "market": "TW", "symbol": symbol, "evidence_class": evidence_class,
        "source_name": source, "source_type": "canonical_admitted_payload",
        "source_reference": reference, "published_at": _iso(published_at, market_time) if published_at else None,
        "observed_at": market_time, "freshness": "fresh" if coverage == "AVAILABLE" else "unknown",
        "reliability": reliability, "confidence": confidence, "coverage_status": coverage,
        "summary": summary, "direction": direction, "materiality": materiality,
        "research_role": research_role,
    }


def _freshness_status(published_at: Any, observed_at: str) -> str:
    if not published_at:
        return "AVAILABLE"
    try:
        published = datetime.fromisoformat(_iso(published_at, observed_at))
        observed = datetime.fromisoformat(observed_at)
        return "STALE" if (observed - published).total_seconds() > 72 * 3600 else "AVAILABLE"
    except (TypeError, ValueError):
        return "PARTIAL"


def _card_evidence(card: dict[str, Any], market_time: str) -> list[dict[str, Any]]:
    symbol = _symbol(card)
    rows: list[dict[str, Any]] = []
    technical = card.get("technical_data") if isinstance(card.get("technical_data"), dict) else {}
    technical_ok = technical.get("analysis_eligible") is True
    technical_direction = _direction(technical.get("direction") or card.get("technical_direction"))
    bars = technical.get("history_bars")
    rows.append(_record(
        market_time=market_time, symbol=symbol, evidence_class="technical",
        source=_text(technical.get("source"), "canonical_technical"),
        summary=(f"技術歷史 {bars} 根，方向{DIRECTION_LABELS[technical_direction]}" if technical_ok else f"技術歷史 {bars or '不足'} 根，尚不足以確認趨勢"),
        direction=technical_direction if technical_ok else "unavailable",
        coverage="AVAILABLE" if technical_ok else "PARTIAL" if int(bars or 0) > 0 else "MISSING",
        confidence=.8 if technical_ok else .2, reliability=.85,
        published_at=technical.get("source_timestamp"),
        research_role="contextual",
    ))

    adr = card.get("adr_context")
    if _available(adr):
        change = _number(adr)
        adr_name = "TSM ADR" if symbol == "2330" else "ADR"
        adr_direction = "上漲" if change is not None and change > 0 else "下跌" if change is not None and change < 0 else "持平"
        rows.append(_record(
            market_time=market_time, symbol=symbol, evidence_class="adr",
            source="canonical_adr", summary=f"{adr_name} 隔夜{adr_direction} {abs(change):.2f}%，提供隔夜方向參考" if change is not None else f"{adr_name} 隔夜方向資料已取得",
            direction="bullish" if change is not None and change > 0 else "bearish" if change is not None and change < 0 else "neutral",
            confidence=.82, reliability=.85,
            research_role="contextual",
        ))

    news = card.get("news_evidence") if isinstance(card.get("news_evidence"), dict) else {}
    news_conf = news.get("confidence") if isinstance(news.get("confidence"), dict) else {}
    admitted_news = [item for item in (news.get("evidence") or []) if isinstance(item, dict)]
    for item in admitted_news[:3]:
        headline = _text(item.get("headline"))
        if not headline:
            continue
        direction = _direction(item.get("direction"))
        coverage = _freshness_status(item.get("published_at"), market_time)
        rows.append(_record(
            market_time=market_time, symbol=symbol, evidence_class="news",
            source=_text(item.get("publisher"), "canonical_news"),
            summary=headline, direction=direction, coverage=coverage,
            confidence=max(0.0, min(1.0, float(news_conf.get("score") or 50) / 100)),
            reliability=max(.3, min(1.0, float(item.get("source_tier") or 4) and (1.05 - float(item.get("source_tier") or 4) * .15))),
            published_at=item.get("published_at"), reference=item.get("source_url"),
            materiality=_text(item.get("materiality"), "medium"),
        ))

    dimensions = (
        ("chip", card.get("chip_summary"), "canonical_chip", card.get("chip_direction")),
        ("fundamental", card.get("fundamental_context") or card.get("fundamental_summary"), "canonical_fundamental", card.get("fundamental_direction")),
        ("sector", card.get("sector_context") or card.get("sector"), "canonical_sector", card.get("sector_direction")),
        ("macro", card.get("macro_context"), "canonical_macro", card.get("macro_direction")),
        ("market", card.get("market_context"), "canonical_market_context", card.get("market_direction")),
        ("event", card.get("event_summary") or card.get("event_risk"), "canonical_event", card.get("event_direction")),
    )
    for evidence_class, value, source, direction_value in dimensions:
        if _available(value):
            rows.append(_record(
                market_time=market_time, symbol=symbol, evidence_class=evidence_class,
                source=source, summary=_text(value) or json.dumps(value, ensure_ascii=False, sort_keys=True),
                direction=_direction(direction_value), confidence=.65, reliability=.72,
                research_role="substantive" if evidence_class in {"fundamental", "event"} else "contextual",
            ))

    volume = card.get("volume_ratio")
    if volume is not None:
        ratio = _number(volume)
        rows.append(_record(
            market_time=market_time, symbol=symbol, evidence_class="market",
            source="canonical_intraday_volume", summary=f"盤中量能倍率 {ratio:.2f} 倍" if ratio is not None else "盤中量能已取得",
            direction="bullish" if ratio is not None and ratio >= 1 else "neutral",
            confidence=.8, reliability=.88,
            research_role="contextual",
        ))
    price = card.get("current_price") or card.get("observed_price")
    if price is not None:
        session_open = _number(card.get("session_open"))
        current = _number(price)
        change_pct = None if current is None or session_open in (None, 0) else (current / session_open - 1) * 100
        price_direction = "bullish" if change_pct is not None and change_pct > .2 else "bearish" if change_pct is not None and change_pct < -.2 else "neutral"
        rows.append(_record(
            market_time=market_time, symbol=symbol, evidence_class="market",
            source="canonical_observed_quote",
            summary=(f"盤中價格 {price}，較開盤{change_pct:+.2f}%（高 {card.get('session_high')}／低 {card.get('session_low')}）" if change_pct is not None else f"盤中價格證據 {price} 已取得；缺少開盤價，暫不推導方向"),
            direction=price_direction if change_pct is not None else "unavailable", confidence=.9, reliability=.95,
            research_role="contextual",
        ))
    context = instrument_context(symbol)
    rows.append(_record(
        market_time=market_time, symbol=symbol, evidence_class="sector", source="canonical_tw_instrument_map_v2",
        summary=f"{context['sector']}｜{context['industry']}｜同儕 {context['peer']}", direction="neutral",
        coverage="AVAILABLE" if context["sector"] != "未分類" else "MISSING", confidence=.75, reliability=.9,
        research_role="contextual",
    ))
    return rows


def _missing(card: dict[str, Any], reasoning: dict[str, Any]) -> list[str]:
    result = [MISSING_LABELS.get(str(code).upper(), str(code)) for code in (card.get("data_gaps") or [])]
    result.extend(CLASS_LABELS.get(value, value) for value in reasoning.get("missing_evidence") or [])
    output: list[str] = []
    for value in result:
        if value and value not in output:
            output.append(value)
    return output


def _labels(ids: list[str], evidence: list[dict[str, Any]]) -> list[str]:
    by_id = {item["evidence_id"]: item for item in evidence}
    labels = []
    for evidence_id in ids:
        if evidence_id not in by_id:
            continue
        item = by_id[evidence_id]
        prefix = CLASS_LABELS.get(item["evidence_class"], item["evidence_class"])
        provenance = ""
        if item["evidence_class"] in {"news", "event", "fundamental", "corporate"}:
            published = str(item.get("published_at") or item.get("observed_at") or "")[:16]
            provenance = f"（{item.get('source_name') or '來源未標示'}{f'｜{published}' if published else ''}）"
        labels.append(f"{prefix}｜{item['summary']}{provenance}")
    return labels


def _news_diagnostics(card: dict[str, Any], bundle: dict[str, Any], *, rendered_count: int) -> dict[str, Any]:
    news = card.get("news_evidence") if isinstance(card.get("news_evidence"), dict) else {}
    source = news.get("evidence_funnel") if isinstance(news.get("evidence_funnel"), dict) else {}
    stages = dict(source.get("stages") or {})
    admitted_count = len([item for item in news.get("evidence") or [] if isinstance(item, dict)])
    upstream_stages = ("DISCOVERED", "RETRIEVED", "NORMALIZED", "SYMBOL_ATTRIBUTED", "RELEVANT", "MATERIAL", "QUALITY_QUALIFIED", "FRESH", "DEDUPLICATED", "ADMITTED")
    inferred_stages = []
    for name in upstream_stages:
        if name not in stages:
            stages[name] = admitted_count
            inferred_stages.append(name)
    source_semantics = source.get("count_semantics")
    if source_semantics:
        count_semantics = str(source_semantics)
    elif source.get("stages"):
        count_semantics = "EXACT_LEGACY_V1"
    else:
        count_semantics = "COMPATIBILITY_LOWER_BOUND"
    if inferred_stages and source.get("stages"):
        count_semantics = "PARTIAL_COMPATIBILITY_LOWER_BOUND"
    used = sum(item.get("evidence_class") == "news" and item.get("evidence_id") in set(bundle["reasoning"].get("substantive_evidence_ids") or []) for item in bundle["evidence"])
    stages["RRE_USED"] = used
    stages["RENDERED"] = min(rendered_count, used)
    rejection_reasons = dict(source.get("rejection_reasons") or {})
    if stages.get("ADMITTED", 0) > used:
        rejection_reasons["RRE_NOT_SELECTED"] = stages["ADMITTED"] - used
    if used > stages["RENDERED"]:
        rejection_reasons["RENDERER_NOT_SELECTED"] = used - stages["RENDERED"]
    absence = "NEWS_SELECTED_AND_RENDERED" if stages["RENDERED"] else "NEWS_ADMITTED_NOT_SELECTED" if stages.get("ADMITTED", 0) else "NEWS_DISCOVERED_BUT_FILTERED" if stages.get("DISCOVERED", 0) else "NO_RELEVANT_NEWS_DISCOVERED"
    return {
        "schema_version": "tw_research_evidence_funnel_v1",
        "count_semantics": count_semantics,
        "inferred_stages": inferred_stages,
        "stages": stages,
        "rejection_reasons": rejection_reasons,
        "absence_state": absence,
    }


def _hypothesis_state(window: str, card: dict[str, Any]) -> dict[str, Any]:
    if window == "pre_open_0700":
        return {"state": "created", "reason": "盤前 admitted evidence 建立初始研究假設"}
    prediction = card.get("prediction_snapshot_v2") if isinstance(card.get("prediction_snapshot_v2"), dict) else {}
    predicted = str(prediction.get("direction_forecast") or "insufficient_data")
    current, opened = _number(card.get("current_price")), _number(card.get("session_open"))
    if current is None or opened in (None, 0) or predicted == "insufficient_data":
        return {"state": "insufficient_new_evidence", "reason": "缺少可比較的盤前預測或盤中開收價格"}
    actual = "bullish" if current > opened * 1.002 else "bearish" if current < opened * .998 else "neutral"
    if actual == predicted:
        state = "confirmed" if window == "post_close_1500" else "strengthened"
        reason = f"本批次價格方向 {actual} 與盤前假設一致"
    elif actual == "neutral" or predicted == "neutral":
        state = "weakened"
        reason = f"本批次價格方向 {actual} 未充分確認盤前假設 {predicted}"
    else:
        state = "contradicted" if window != "post_close_1500" else "invalidated"
        reason = f"本批次價格方向 {actual} 與盤前假設 {predicted} 相反"
    return {"state": state, "reason": reason, "predicted_direction": predicted, "observed_direction": actual}


def _window_update(window: str, card: dict[str, Any], conclusion: str) -> dict[str, Any]:
    if window == "pre_open_0700":
        state = "建立今日研究假設"
    elif window == "intraday_1305":
        trigger = _text(card.get("trigger_status") or card.get("entry_trigger_state"), "not_applicable")
        state = f"盤中檢查：{trigger}"
    elif window == "pre_close_1335":
        action = _text(card.get("overnight_action") or card.get("action"), "觀察")
        state = f"收盤前判斷：{action}"
    else:
        outcome = _text(card.get("trade_outcome") or card.get("canonical_outcome"), "pending_evidence")
        state = f"盤後檢討：{outcome}"
    source = card.get("source_plan") if isinstance(card.get("source_plan"), dict) else {}
    return {
        "window": window, "state": state, "research_conclusion": conclusion,
        "source_window": source.get("source_window") or card.get("source_window") or "pre_open_0700",
        "source_snapshot_id": source.get("source_snapshot_id") or card.get("source_snapshot_id"),
        "source_revision": source.get("source_revision") or card.get("source_revision"),
        "source_hash": source.get("source_hash") or card.get("source_payload_hash"),
    }


def build_tw_daily_research(
    window: str,
    payload: dict[str, Any],
    cards: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if window not in WINDOWS:
        raise ValueError(f"unsupported TW research window: {window}")
    generated = _iso(payload.get("generated_at") or payload.get("effective_batch_time"), "2026-01-01T00:00:00+08:00")
    evidence = {_symbol(card): _card_evidence(card, generated) for card in cards}
    triggers: dict[str, dict[str, str]] = {}
    for card in cards:
        tactical = ((card.get("strategies") or {}).get("daily_tactical") or {}) if isinstance(card.get("strategies"), dict) else {}
        playbook = tactical.get("playbook") if isinstance(tactical.get("playbook"), dict) else {}
        triggers[_symbol(card)] = {
            "expected_trigger": _text(card.get("entry_condition") or playbook.get("trigger_condition"), "新增價格、量能與研究證據共同確認"),
            "invalidation": _text(card.get("invalidation_condition") or playbook.get("invalidation_condition") or card.get("stop_level"), "核心反向證據成立或原研究條件失效"),
        }
    rre = build_research_reasoning_projection("TW", str(payload.get("effective_trading_date") or ""), evidence, triggers)
    cards_by_symbol = {_symbol(card): card for card in cards}
    decisions = {str(row.get("symbol")): row for row in decision_rows}
    notes = []
    for bundle in rre["bundles"]:
        symbol = bundle["symbol"]
        card = cards_by_symbol[symbol]
        decision = decisions.get(symbol, {})
        reasoning = bundle["reasoning"]
        supporting = _labels(reasoning["supporting_evidence_ids"], bundle["evidence"])
        opposing = _labels(reasoning["opposing_evidence_ids"], bundle["evidence"])
        contextual = _labels(reasoning.get("contextual_evidence_ids") or [], bundle["evidence"])
        missing = _missing(card, reasoning)
        company = bundle["knowledge"].get("dimensions") or {}
        context = [
            *company.get("business", [])[:1], *company.get("products", [])[:2],
            *company.get("long_term_drivers", [])[:2],
        ]
        action = _text(decision.get("decision_category_label") or card.get("action"), "觀察候選")
        if supporting and opposing:
            summary = f"{symbol} {_name(card)}同時有正反證據；{supporting[0]}，但{opposing[0]}，因此維持「{action}」。"
        elif supporting:
            limit = f"；但仍缺少{'、'.join(missing[:2])}" if missing else ""
            summary = f"{symbol} {_name(card)}的主要支持為{supporting[0]}{limit}，目前維持「{action}」。"
        elif opposing:
            summary = f"{symbol} {_name(card)}受{opposing[0]}限制，且需確認{'、'.join(missing[:2]) or '後續證據'}，目前維持「{action}」。"
        else:
            summary = f"{symbol} {_name(card)}目前沒有足以形成方向結論的證據；長期脈絡為{'、'.join(context[:2]) or '尚未建檔'}，先維持「{action}」。"
        substantive_count = len(reasoning.get("substantive_evidence_ids") or [])
        qualified = reasoning["conclusion"] in {"bullish", "bearish", "mixed"} and substantive_count > 0 and float(reasoning["confidence"]["score"]) >= 50
        news_rendered = sum(item.startswith("新聞｜") for item in supporting + opposing)
        notes.append({
            "symbol": symbol, "name": _name(card), "generated_by": "research_reasoning_engine_v1",
            "research_summary": summary, "conclusion": reasoning["conclusion"],
            "supporting": supporting, "opposing": opposing, "missing": missing,
            "contextual_evidence": contextual,
            "why": reasoning.get("why") or [], "why_not": reasoning.get("why_not") or [],
            "unknown": missing, "counter_argument": reasoning["counter_argument"],
            "company_context": context, "knowledge_status": bundle["knowledge"]["status"],
            "hypothesis": bundle["hypothesis"], "confidence_reasoning": reasoning["confidence"],
            "reasoning_chain": reasoning["reasoning_chain"],
            "window_update": _window_update(window, card, reasoning["conclusion"]),
            "hypothesis_lifecycle": _hypothesis_state(window, card),
            "technical_evidence_v2": technical_evidence(card),
            "effective_coverage_v2": effective_coverage(card),
            "instrument_context_v2": instrument_context(symbol),
            "prediction_snapshot_v2": card.get("prediction_snapshot_v2"),
            "decision_category": decision.get("decision_category"),
            "decision_category_label": action, "decision_modified": False,
            "research_quality": {"qualified": qualified, "substantive_evidence_count": substantive_count, "minimum_confidence": 50, "reason_codes": [] if qualified else ["INSUFFICIENT_SUBSTANTIVE_RESEARCH"]},
            "research_evidence_observability": {"news": _news_diagnostics(card, bundle, rendered_count=news_rendered)},
        })
    notes.sort(key=lambda row: (-float(row["confidence_reasoning"]["score"]), row["symbol"]))
    qualified_notes = [row for row in notes if row["research_quality"]["qualified"]]
    strongest = qualified_notes[0] if qualified_notes else None
    relative = notes[0] if notes else None
    risk = max(notes, key=lambda row: (len(row["opposing"]), len(row["missing"]), row["symbol"])) if notes else None
    positive = sum(row["conclusion"] == "bullish" for row in notes)
    negative = sum(row["conclusion"] == "bearish" for row in notes)
    mixed = sum(row["conclusion"] == "mixed" for row in notes)
    insufficient = sum(row["conclusion"] == "insufficient_evidence" for row in notes)
    known_context = []
    for row in notes:
        for value in row["company_context"]:
            if value not in known_context:
                known_context.append(value)
    narrative = (
        f"今日研究主線：{positive} 檔具偏多研究證據、{negative} 檔具偏空證據、{mixed} 檔正反訊號衝突、{insufficient} 檔證據不足；"
        f"目前可辨識脈絡以{'、'.join(known_context[:3]) or '個股既有產業定位'}為主。"
    )
    brief = {
        "label": WINDOW_LABELS[window], "market_narrative": narrative,
        "best_research": f"{strongest['symbol']} {strongest['name']}｜{strongest['research_summary']}" if strongest else "本批次無符合研究品質門檻的標的",
        "best_research_status": "QUALIFIED" if strongest else "NO_QUALIFIED_RESEARCH",
        "relative_evidence_candidate": f"{relative['symbol']} {relative['name']}" if relative else None,
        "largest_research_risk": f"{risk['symbol']} {risk['name']}｜缺口：{'、'.join(risk['missing'][:3]) or '無'}" if risk else "尚無研究風險",
        "next_question": (
            strongest["hypothesis"]["expected_trigger"] if strongest else "等待下一批次研究證據"
        ),
    }
    result = {
        "schema_version": "tw_daily_research_reasoning_v1", "market": "TW", "window": window,
        "effective_trading_date": payload.get("effective_trading_date"),
        "source_identity": {
            "snapshot_id": payload.get("snapshot_id"), "revision": payload.get("revision"),
            "source_payload_hash": payload.get("source_payload_hash"),
        },
        "research_notes": notes, "morning_or_window_brief": brief,
        "research_evidence_observability": {
            "schema_version": "tw_research_evidence_observability_v1",
            "market": "TW", "window": window,
            "symbols": {row["symbol"]: row["research_evidence_observability"] for row in notes},
        },
        "rre_projection": rre, "research_reasoning_identity": rre["research_reasoning_identity"],
        "research_first_pipeline": True, "decision_is_read_only_consumer": True,
        "model_boundary": MODEL_BOUNDARY,
    }
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    result["production_research_identity"] = "twresearch_" + hashlib.sha256(raw.encode()).hexdigest()[:24]
    return result


def compact_research_lines(research: dict[str, Any]) -> list[str]:
    brief = research.get("morning_or_window_brief") or {}
    return [
        f"{brief.get('label') or '研究摘要'}：{brief.get('market_narrative') or '尚未取得'}",
        f"最佳研究：{brief.get('best_research') or '尚未取得'}",
        f"主要研究風險：{brief.get('largest_research_risk') or '尚未取得'}",
    ]


def validate_tw_daily_research(value: dict[str, Any], expected_symbols: set[str]) -> list[str]:
    errors: list[str] = []
    notes = value.get("research_notes") or []
    if {row.get("symbol") for row in notes} != expected_symbols:
        errors.append("research_symbol_partition")
    if any(row.get("generated_by") != "research_reasoning_engine_v1" for row in notes):
        errors.append("legacy_research_note")
    for row in notes:
        symbol = row.get("symbol")
        for key in ("supporting", "opposing", "missing", "unknown", "reasoning_chain"):
            if not isinstance(row.get(key), list):
                errors.append(f"{symbol}:{key}")
        hypothesis = row.get("hypothesis") or {}
        if not hypothesis.get("expected_trigger") or not hypothesis.get("invalidation"):
            errors.append(f"{symbol}:hypothesis")
        if not row.get("counter_argument"):
            errors.append(f"{symbol}:counter_argument")
        if row.get("decision_modified") is not False:
            errors.append(f"{symbol}:decision_boundary")
        quality = row.get("research_quality") or {}
        if row.get("conclusion") in {"bullish", "bearish", "mixed"} and not quality.get("substantive_evidence_count"):
            errors.append(f"{symbol}:direction_without_substantive_evidence")
        diagnostic = ((row.get("research_evidence_observability") or {}).get("news") or {})
        stages = diagnostic.get("stages") or {}
        ordered = ("DISCOVERED", "RETRIEVED", "NORMALIZED", "SYMBOL_ATTRIBUTED", "RELEVANT", "MATERIAL", "QUALITY_QUALIFIED", "FRESH", "DEDUPLICATED", "ADMITTED", "RRE_USED", "RENDERED")
        if any(not isinstance(stages.get(stage), int) or stages.get(stage, -1) < 0 for stage in ordered):
            errors.append(f"{symbol}:news_funnel_counts")
        elif any(stages[left] < stages[right] for left, right in zip(ordered, ordered[1:])):
            errors.append(f"{symbol}:news_funnel_non_monotonic")
        semantics = diagnostic.get("count_semantics")
        if semantics not in {"EXACT", "EXACT_LEGACY_V1", "COMPATIBILITY_LOWER_BOUND", "PARTIAL_COMPATIBILITY_LOWER_BOUND"}:
            errors.append(f"{symbol}:news_funnel_count_semantics")
        if semantics in {"COMPATIBILITY_LOWER_BOUND", "PARTIAL_COMPATIBILITY_LOWER_BOUND"} and not diagnostic.get("inferred_stages"):
            errors.append(f"{symbol}:news_funnel_inference_provenance")
    if value.get("research_first_pipeline") is not True or value.get("decision_is_read_only_consumer") is not True:
        errors.append("production_pipeline_order")
    if value.get("model_boundary") != MODEL_BOUNDARY:
        errors.append("model_boundary")
    brief = value.get("morning_or_window_brief") or {}
    if not all(brief.get(key) for key in ("market_narrative", "best_research", "largest_research_risk", "next_question")):
        errors.append("brief_incomplete")
    qualified_notes = [row for row in notes if (row.get("research_quality") or {}).get("qualified")]
    if brief.get("best_research_status") == "QUALIFIED" and not qualified_notes:
        errors.append("best_research_without_qualified_candidate")
    if qualified_notes and brief.get("best_research_status") != "QUALIFIED":
        errors.append("qualified_candidate_not_presented")
    observability = value.get("research_evidence_observability") or {}
    if set((observability.get("symbols") or {}).keys()) != expected_symbols:
        errors.append("research_observability_symbol_partition")
    return sorted(set(errors))
