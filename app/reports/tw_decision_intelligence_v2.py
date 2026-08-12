"""Institutional TW decision-intelligence projection.

This layer explains and prioritizes existing canonical decisions.  It never
changes strategy geometry, model scores, prediction output, or production
ranking.  Dashboard, Archive, Email/LINE previews and Operations can rebuild
the same projection from one admitted window payload.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Iterable

from .tw_pre_open_quality import public_reason
from .tw_four_window_decision import PREDICTION_RESULTS, canonical_prediction_range_result
from app.research.tw_daily_generator import (
    build_tw_daily_research,
    compact_research_lines,
    validate_tw_daily_research,
)
from app.research.tw_production_intelligence_v2 import source_health, verification_health

SCHEMA_VERSION = "tw_decision_intelligence_v2"
WINDOWS = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
STATUSES = {"AVAILABLE", "MISSING", "STALE", "NOT_APPLICABLE"}
DIMENSIONS = (
    "technical", "trend", "market_breadth", "gap", "volume", "event",
    "news", "sector", "etf", "adr", "macro", "chip", "fundamental",
)
MODEL_BOUNDARY = {
    "strategy_changed": False,
    "scoring_changed": False,
    "strategy_ranking_changed": False,
    "prediction_model_changed": False,
    "factor_weights_changed": False,
    "automatic_learning": False,
    "rank_purpose": "presentation_only_existing_evidence_projection",
}
CATEGORY_LABELS = {
    "BUY_CANDIDATE": "優先機會候選",
    "WATCH_CANDIDATE": "觀察候選",
    "HOLD_CANDIDATE": "續抱候選",
    "REDUCE_CANDIDATE": "降低風險候選",
    "AVOID_CANDIDATE": "避開候選",
}


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip() or fallback
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return fallback


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _unique(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in output:
            output.append(text)
    return output


def _cards(payload: dict[str, Any], window: str) -> list[dict[str, Any]]:
    keys = {
        "pre_open_0700": ("structured_pre_open_cards", "cards"),
        "intraday_1305": ("structured_intraday_cards", "cards"),
        "pre_close_1335": ("structured_pre_close_cards", "structured_intraday_cards", "cards"),
        "post_close_1500": ("structured_review_cards", "cards"),
    }[window]
    dashboard = payload.get("dashboard_ready_contract") if isinstance(payload.get("dashboard_ready_contract"), dict) else {}
    for candidate in [*(payload.get(key) for key in keys), dashboard.get("cards")]:
        if isinstance(candidate, list) and candidate:
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _symbol(card: dict[str, Any]) -> str:
    return _text(card.get("symbol") or card.get("stock_id"), "UNKNOWN")


def _name(card: dict[str, Any]) -> str:
    return _text(card.get("name") or card.get("stock_name"), _symbol(card))


def _tactical(card: dict[str, Any]) -> dict[str, Any]:
    strategies = card.get("strategies") if isinstance(card.get("strategies"), dict) else {}
    tactical = strategies.get("daily_tactical") if isinstance(strategies.get("daily_tactical"), dict) else {}
    return tactical or (card.get("daily_tactical_summary") if isinstance(card.get("daily_tactical_summary"), dict) else {})


def _direction(card: dict[str, Any]) -> str:
    technical = card.get("technical_data") if isinstance(card.get("technical_data"), dict) else {}
    raw = _text(technical.get("direction") or card.get("direction") or _tactical(card).get("direction")).lower()
    if raw in {"bullish", "uptrend", "strong_uptrend", "long", "偏多", "偏多趨勢"}:
        return "bullish"
    if raw in {"bearish", "downtrend", "short", "偏空", "偏空趨勢"}:
        return "bearish"
    if raw in {"neutral", "sideways", "盤整", "中性"}:
        return "neutral"
    return "unavailable"


def _is_available(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value) and any(_is_available(item) for item in value.values())
    if isinstance(value, list):
        return any(_is_available(item) for item in value)
    text = _text(value).lower()
    return bool(text) and not any(token in text for token in (
        "尚未取得", "尚未判定", "無法判定", "不適用", "資料不足", "unavailable", "unknown", "none",
    ))


def _coverage_item(status: str, source: str, evidence: Any, impact: str) -> dict[str, Any]:
    return {"status": status, "source": source, "evidence": evidence, "decision_impact": impact}


def coverage_registry(card: dict[str, Any], payload: dict[str, Any], window: str) -> dict[str, dict[str, Any]]:
    technical = card.get("technical_data") if isinstance(card.get("technical_data"), dict) else {}
    market = payload.get("market_context") if isinstance(payload.get("market_context"), dict) else {}
    news = card.get("news_evidence") if isinstance(card.get("news_evidence"), dict) else {}
    tactical = _tactical(card)
    gaps = " ".join(str(item).upper() for item in [*(card.get("data_gaps") or []), *(card.get("missing_fields") or [])])
    stale = "STALE" in gaps or _text(card.get("freshness_status") or card.get("source_freshness")).lower() == "stale"
    technical_available = bool(technical.get("analysis_eligible")) if technical else _is_available(card.get("technical_summary") or tactical.get("technical_factors"))
    direction = _direction(card)
    etf_symbol = _symbol(card).startswith("00")
    values = {
        "technical": (technical_available, technical.get("source") or "canonical_technical", technical.get("history_bars") or card.get("technical_summary")),
        "trend": (direction != "unavailable", "canonical_technical", direction),
        "market_breadth": (_is_available(payload.get("market_breadth") or market.get("breadth")), "tw_market_context", payload.get("market_breadth") or market.get("breadth")),
        "gap": (_is_available(card.get("gap_risk") or card.get("gap_state") or card.get("gap_pct")), "canonical_quote", card.get("gap_risk") or card.get("gap_state") or card.get("gap_pct")),
        "volume": (card.get("volume_ratio") is not None or _is_available(tactical.get("technical_factors", {}).get("volume_ma20") if isinstance(tactical.get("technical_factors"), dict) else None), "canonical_volume", card.get("volume_ratio") or (tactical.get("technical_factors") or {}).get("volume_ma20")),
        "event": (_text(card.get("event_risk")).lower() in {"low", "medium", "high"}, "canonical_event", card.get("event_risk")),
        "news": (bool(news.get("primary_evidence") or news.get("admitted_evidence")), "canonical_news", news.get("primary_evidence") or news.get("admitted_evidence")),
        "sector": (_is_available(card.get("sector_context") or card.get("sector") or market.get("sector_rotation")), "tw_sector_context", card.get("sector_context") or card.get("sector") or market.get("sector_rotation")),
        "etf": (_is_available(card.get("etf_context") or market.get("etf")) or etf_symbol, "tw_etf_context", card.get("etf_context") or market.get("etf") or ("self_etf" if etf_symbol else None)),
        "adr": (_is_available(card.get("adr_context")), "canonical_adr", card.get("adr_context")),
        "macro": (_is_available(card.get("macro_context") or market.get("macro")), "tw_macro_context", card.get("macro_context") or market.get("macro")),
        "chip": (_is_available(card.get("chip_summary") or card.get("chip_context")), "canonical_chip", card.get("chip_summary") or card.get("chip_context")),
        "fundamental": (_is_available(card.get("fundamental_evidence") or card.get("fundamental_context")), "canonical_fundamental", card.get("fundamental_evidence") or card.get("fundamental_context")),
    }
    result: dict[str, dict[str, Any]] = {}
    for dimension in DIMENSIONS:
        available, source, evidence = values[dimension]
        not_applicable = dimension == "adr" and etf_symbol
        dimension_stale = stale and dimension in {"technical", "trend", "gap", "volume"}
        status = "NOT_APPLICABLE" if not_applicable else "STALE" if available and dimension_stale else "AVAILABLE" if available else "MISSING"
        impact = "可納入本次判斷。" if status == "AVAILABLE" else "資料過期，限制決策升級。" if status == "STALE" else "本標的不適用。" if status == "NOT_APPLICABLE" else "缺少此證據，降低研究信心但不偽裝為中性。"
        result[dimension] = _coverage_item(status, source, evidence, impact)
    return result


def _score(card: dict[str, Any]) -> float:
    tactical = _tactical(card)
    for value in (card.get("total_score"), card.get("score"), tactical.get("final_score"), tactical.get("score"), tactical.get("confidence")):
        number = _number(value)
        if number is not None:
            return number
    return 0.0


def _risk_flags(card: dict[str, Any]) -> list[str]:
    tactical = _tactical(card)
    return _unique(public_reason(item) for item in [
        *(card.get("risk_reasons") or []), *(tactical.get("risk_reasons") or []),
        card.get("risk_summary"), card.get("do_not_trade_reason"), card.get("action_change_reason"),
        "追價風險偏高" if _text(card.get("chase_risk") or tactical.get("chase_risk")).lower() in {"high", "高"} else None,
        "事件風險偏高" if _text(card.get("event_risk") or tactical.get("event_risk")).lower() == "high" else None,
    ])


def _decision_category(card: dict[str, Any], window: str) -> str:
    action = _text(card.get("canonical_intraday_action") or card.get("overnight_action") or card.get("action") or _tactical(card).get("action")).lower()
    plan = _text(card.get("plan_status") or card.get("opportunity_group") or _tactical(card).get("setup_type")).lower()
    outcome = _text(card.get("trade_outcome") or card.get("canonical_outcome")).lower()
    if window == "post_close_1500" and outcome in {"loss", "fail"}:
        return "AVOID_CANDIDATE"
    if any(token in action for token in ("exit", "停止", "不建議留倉", "取消")):
        return "AVOID_CANDIDATE"
    if any(token in action for token in ("reduce", "降低", "減碼")):
        return "REDUCE_CANDIDATE"
    if any(token in action for token in ("hold", "留倉", "續抱", "維持")) and plan not in {"no_trade", "watch"}:
        return "HOLD_CANDIDATE"
    if plan in {"no_trade", "無交易"} or any(token in action for token in ("暫不", "no_trade", "避免")):
        return "AVOID_CANDIDATE"
    eligibility = card.get("eligibility") if isinstance(card.get("eligibility"), dict) else {}
    if eligibility.get("actionable") is True or card.get("entry_readiness") in {"entry_ready", "ready_for_open_confirmation"}:
        return "BUY_CANDIDATE"
    return "WATCH_CANDIDATE"


def _rank(rows: list[dict[str, Any]], score_key: str, rank_key: str, *, descending: bool = True) -> None:
    ordered = sorted(rows, key=lambda row: ((-row[score_key]) if descending else row[score_key], row["symbol"]))
    last: float | None = None
    rank = 0
    for index, row in enumerate(ordered, 1):
        value = row[score_key]
        if value != last:
            rank = index
            last = value
        row[rank_key] = rank


def _stock_intelligence(card: dict[str, Any], payload: dict[str, Any], window: str) -> dict[str, Any]:
    coverage = coverage_registry(card, payload, window)
    applicable = [item for item in coverage.values() if item["status"] != "NOT_APPLICABLE"]
    available = [item for item in applicable if item["status"] == "AVAILABLE"]
    coverage_score = round(len(available) / len(applicable) * 100, 1) if applicable else 0.0
    direction, base, risks = _direction(card), _score(card), _risk_flags(card)
    rr = _number(card.get("risk_reward") or _tactical(card).get("reward_risk"))
    category = _decision_category(card, window)
    opportunity_score = round(base + (8 if direction == "bullish" else -8 if direction == "bearish" else 0) + min(8, (rr or 0) * 3) + (8 if category == "BUY_CANDIDATE" else 3 if category in {"HOLD_CANDIDATE", "WATCH_CANDIDATE"} else -8) - len(risks) * 3, 2)
    research_score = round(coverage_score * .7 + min(30, len(_unique([card.get("technical_summary"), card.get("news_summary"), card.get("chip_summary"), card.get("fundamental_context")])) * 7.5), 2)
    missing_count = sum(item["status"] in {"MISSING", "STALE"} for item in coverage.values())
    risk_score = round(min(100, len(risks) * 14 + missing_count * 4 + (15 if direction == "bearish" else 0)), 2)
    reasons = _unique([
        *(card.get("reasons") or []), *(_tactical(card).get("reasons") or []),
        card.get("reasoning"), card.get("action_change_reason"), card.get("next_session_action"),
    ])
    strongest = next((f"{key} 已取得" for key, item in coverage.items() if item["status"] == "AVAILABLE"), "目前沒有可納入的完整研究證據")
    missing = [key for key, item in coverage.items() if item["status"] in {"MISSING", "STALE"}]
    confidence = _number(card.get("confidence") or _tactical(card).get("confidence") or base)
    components = {
        "technical": 100 if coverage["technical"]["status"] == "AVAILABLE" else 0,
        "news": 100 if coverage["news"]["status"] == "AVAILABLE" else 0,
        "macro": 100 if coverage["macro"]["status"] == "AVAILABLE" else 0,
        "coverage": coverage_score,
        "risk": max(0.0, 100 - risk_score),
    }
    tomorrow_state = "REASSESS" if category == "AVOID_CANDIDATE" else "CONTINUE_OBSERVE" if category == "WATCH_CANDIDATE" else "PRIORITY_OBSERVE" if category in {"BUY_CANDIDATE", "HOLD_CANDIDATE"} else "REASSESS"
    tomorrow_text = {"REASSESS": "明日重新評估", "CONTINUE_OBSERVE": "明日延續觀察", "PRIORITY_OBSERVE": "明日優先觀察"}[tomorrow_state]
    return {
        "symbol": _symbol(card), "name": _name(card), "decision_category": category,
        "decision_category_label": CATEGORY_LABELS[category],
        "direction": direction, "market_positioning": _text(card.get("market_positioning") or card.get("sector_context"), "依本批次個股證據定位"),
        "technical_state": _text(card.get("technical_summary"), "技術狀態尚未取得"),
        "fundamental_summary": _text(card.get("fundamental_context") or card.get("fundamental_summary"), "本批次未取得可納入的基本面證據"),
        "event_summary": _text(card.get("news_summary") or card.get("event_summary"), "本批次未取得重大事件證據"),
        "risk_factors": risks or ["未發現已由本批次證據確認的額外風險"],
        "decision_reason": reasons[:4] or [f"沿用既有正式決策「{CATEGORY_LABELS[category]}」，不由呈現層改變策略。"],
        "confidence": confidence,
        "confidence_explanation": {"components": components, "supporting": [strongest], "limiting": missing, "conflict": bool(direction == "neutral" and coverage["news"]["status"] == "AVAILABLE"), "model_score_recomputed": False},
        "invalid_conditions": _unique([card.get("invalidation_condition"), (_tactical(card).get("playbook") or {}).get("invalidation_condition"), card.get("stop_level")]) or ["依原 canonical plan 的失效條件"],
        "tomorrow_watch": tomorrow_text,
        "tomorrow_state": tomorrow_state,
        "tomorrow_state_presentation_only": True,
        "coverage": coverage, "coverage_score": coverage_score,
        "opportunity_projection_score": opportunity_score, "research_projection_score": research_score, "risk_projection_score": risk_score,
        "projection_disclaimer": "排序僅供 PM 閱讀優先級，不修改既有策略排序。",
    }


def _prediction_review(rows: list[dict[str, Any]], window: str) -> dict[str, Any] | None:
    if window != "post_close_1500":
        return None
    predictions, outcomes = Counter(), Counter()
    failures: list[dict[str, Any]] = []
    for row in rows:
        source = row["_source"]
        evaluation_v2 = source.get("prediction_evaluation_v2") if isinstance(source.get("prediction_evaluation_v2"), dict) else {}
        prediction = canonical_prediction_range_result(source)
        outcome = _text(source.get("trade_outcome") or source.get("canonical_outcome"), "pending_evidence")
        predictions[prediction] += 1
        outcomes[outcome] += 1
        if prediction in {"miss", "partial_hit"} or outcome in {"loss", "fail", "pending_evidence"}:
            failures.append({"symbol": row["symbol"], "prediction": prediction, "trade_outcome": outcome, "direction_result": evaluation_v2.get("direction_result"), "interval_width": evaluation_v2.get("interval_width"), "high_error": evaluation_v2.get("high_error"), "low_error": evaluation_v2.get("low_error"), "midpoint_error": evaluation_v2.get("midpoint_error"), "no_trade_classification": evaluation_v2.get("no_trade_classification"), "error_attribution": row["risk_factors"][:2], "unused_evidence": [key for key, item in row["coverage"].items() if item["status"] == "AVAILABLE" and key not in {"technical", "trend"}], "missing_evidence": [key for key, item in row["coverage"].items() if item["status"] in {"MISSING", "STALE"}], "learning_candidate": True})
    best = sorted(rows, key=lambda row: (-row["opportunity_projection_score"], row["symbol"]))
    worst = sorted(rows, key=lambda row: (-row["risk_projection_score"], row["symbol"]))
    return {
        "prediction_distribution": {name: int(predictions.get(name, 0)) for name in PREDICTION_RESULTS}, "trade_outcome_distribution": dict(sorted(outcomes.items())),
        "direction_accuracy": {"status": "available" if predictions else "missing", "hit": predictions.get("hit", 0), "partial_hit": predictions.get("partial_hit", 0), "miss": predictions.get("miss", 0)},
        "entry_accuracy": {"not_triggered": outcomes.get("not_triggered", 0), "review_source": "canonical_trade_outcome"},
        "exit_accuracy": {"win": outcomes.get("win", 0), "loss": outcomes.get("loss", 0), "open_at_close": outcomes.get("open_at_close", 0)},
        "confidence_calibration": {"method": "prediction_v2_confidence_bucket_vs_forward_outcome", "weights_modified": False, "sample_claim": "early_sample_no_statistical_claim"},
        "error_attribution": failures, "factor_attribution": "existing evidence coverage and canonical outcome only",
        "strategy_attribution": "read_only; no strategy mutation", "top_performer": best[0]["symbol"] if best else None,
        "worst_performer": worst[0]["symbol"] if worst else None,
        "tomorrow_improvement": "優先補足失敗案例的缺失證據，保留為 learning candidate；不自動調整模型。" if failures else "延續已驗證證據鏈，下一交易日重新建立 admitted plan。",
        "automatic_learning": False,
    }


def build_tw_decision_intelligence_v2(window: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if window not in WINDOWS:
        raise ValueError(f"unsupported TW window: {window}")
    payload = payload if isinstance(payload, dict) else {}
    source_cards = _cards(payload, window)
    rows = []
    for card in source_cards:
        row = _stock_intelligence(card, payload, window)
        row["_source"] = card
        rows.append(row)
    _rank(rows, "opportunity_projection_score", "opportunity_rank")
    _rank(rows, "research_projection_score", "research_rank")
    _rank(rows, "risk_projection_score", "risk_rank")
    research_projection = build_tw_daily_research(window, payload, source_cards, rows)
    research_by_symbol = {
        row["symbol"]: row for row in research_projection["research_notes"]
    }
    for row in rows:
        research_note = research_by_symbol.get(row["symbol"])
        if research_note:
            row["research_note"] = research_note
    public_rows = [{key: value for key, value in row.items() if key != "_source"} for row in rows]
    coverage_summary = {
        dimension: dict(Counter(row["coverage"][dimension]["status"] for row in rows))
        for dimension in DIMENSIONS
    }
    categories = {name: [row["symbol"] for row in rows if row["decision_category"] == name] for name in ("BUY_CANDIDATE", "WATCH_CANDIDATE", "HOLD_CANDIDATE", "REDUCE_CANDIDATE", "AVOID_CANDIDATE")}
    opportunity = sorted(rows, key=lambda row: (-row["opportunity_projection_score"], row["symbol"]))
    risks = sorted(rows, key=lambda row: (-row["risk_projection_score"], row["symbol"]))
    research = sorted(rows, key=lambda row: (-row["research_projection_score"], row["symbol"]))
    directions = Counter(row["direction"] for row in rows)
    sectors: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        sector = _text(row["coverage"]["sector"]["evidence"], "未分類")
        sectors.setdefault(sector, []).append(row)
    sector_rotation = []
    for sector, members in sorted(sectors.items()):
        score = sum(1 if item["direction"] == "bullish" else -1 if item["direction"] == "bearish" else 0 for item in members)
        state = "Leading" if score > 0 else "Lagging" if score < 0 else "Improving" if any(item["opportunity_projection_score"] > 50 for item in members) else "Weakening"
        sector_rotation.append({"sector": sector, "state": state, "symbol_count": len(members), "source": "canonical_symbol_cards"})
    market_narrative = research_projection["morning_or_window_brief"]["market_narrative"]
    evidence_conflicts = [row["symbol"] for row in rows if (row.get("confidence_explanation") or {}).get("conflict")]
    supporting_evidence = _unique(
        item
        for row in rows
        for item in (row.get("decision_reason") or [])[:1]
    )[:5]
    template_fallbacks = [
        row["symbol"] for row in rows
        if (row.get("decision_reason") or [""])[0].startswith("沿用既有正式決策")
    ]
    top = opportunity[0] if opportunity else None
    actionable_top = next((row for row in opportunity if row["decision_category"] in {"BUY_CANDIDATE", "HOLD_CANDIDATE", "WATCH_CANDIDATE"}), None)
    tracking_top = research[0] if research else top
    top_risk = risks[0] if risks else None
    if top_risk and tracking_top and top_risk["symbol"] == tracking_top["symbol"]:
        top_risk = next((row for row in risks if row["symbol"] != tracking_top["symbol"]), top_risk)
    best_etf = next((row for row in opportunity if row["symbol"].startswith("00")), None)
    avoid_sectors = [item["sector"] for item in sector_rotation if item["state"] in {"Lagging", "Weakening"} and item["sector"] != "未分類"]
    top_note = research_by_symbol.get(actionable_top["symbol"]) if actionable_top else None
    tracking_note = research_by_symbol.get(tracking_top["symbol"]) if tracking_top else None
    risk_note = research_by_symbol.get(top_risk["symbol"]) if top_risk else None
    pm_summary = {
        "one_line": market_narrative,
        "largest_opportunity": top_note["research_summary"] if top_note else (f"本批次沒有通過既有 action gate 的交易機會；最佳研究觀察為 {tracking_note['research_summary']}" if tracking_note else "本批次沒有可排序標的"),
        "largest_risk": (f"{top_risk['symbol']} {_name(top_risk['_source'])}：{risk_note['counter_argument']}" if risk_note else f"{top_risk['symbol']} {_name(top_risk['_source'])}：{top_risk['risk_factors'][0]}") if top_risk else "本批次沒有可排序風險",
        "most_worth_tracking": tracking_top["symbol"] if tracking_top else None,
        "most_worth_dropping": top_risk["symbol"] if top_risk and top_risk["decision_category"] == "AVOID_CANDIDATE" else None,
        "next_observation": tracking_top["tomorrow_watch"] if tracking_top else "等待下一正式 window",
        "if_only_one_symbol": tracking_top["symbol"] if tracking_top else None,
        "if_no_trade_reason": ("沒有標的通過既有 action gate；最佳研究候選仍維持觀察，因為 " + (tracking_note["research_summary"] if tracking_note else "正反證據與未知項尚未共同支持進場")) if tracking_top and not categories["BUY_CANDIDATE"] else None,
    }
    window_intelligence = {
        "pre_open_0700": {"top_opportunities": [row["symbol"] for row in opportunity[:3]], "top_risks": [row["symbol"] for row in risks[:3]], "best_watch": research[0]["symbol"] if research else None, "best_etf": best_etf["symbol"] if best_etf else None, "avoid_sectors": avoid_sectors, "pm_one_line": market_narrative},
        "intraday_1305": {"breakout": [row["symbol"] for row in rows if _text(row["_source"].get("trigger_status") or row["_source"].get("entry_trigger_state")) in {"triggered", "target_hit"} and row["direction"] == "bullish"], "breakdown": [row["symbol"] for row in rows if _text(row["_source"].get("trigger_status") or row["_source"].get("entry_trigger_state")) in {"invalidated", "stop_hit"}], "momentum": [row["symbol"] for row in rows if row["direction"] == "bullish" and row["coverage"]["volume"]["status"] == "AVAILABLE"], "intraday_strength": [row["symbol"] for row in opportunity[:3]], "intraday_weakness": [row["symbol"] for row in risks[:3]], "risk_update": [row["symbol"] for row in rows if row["risk_projection_score"] >= 30]},
        "pre_close_1335": {"hold": categories["HOLD_CANDIDATE"], "overnight_risk": [row["symbol"] for row in risks[:3]], "tomorrow_gap_assessment": "沿用已取得 Gap／事件／量價證據；缺失項目不推導為低風險。", "late_flow": [row["symbol"] for row in rows if row["coverage"]["volume"]["status"] == "AVAILABLE"], "next_day_priority": [row["symbol"] for row in opportunity[:3]]},
        "post_close_1500": {"review": _prediction_review(rows, window)},
    }[window]
    identity = {
        "market": "TW", "window": window,
        "effective_trading_date": payload.get("effective_trading_date") or payload.get("trading_date"),
        "snapshot_id": payload.get("snapshot_id"), "revision": payload.get("revision"),
        "source_payload_hash": payload.get("source_payload_hash"),
    }
    prediction_ids = sorted(str(card.get("prediction_snapshot_v2", {}).get("prediction_identity")) for card in source_cards if isinstance(card.get("prediction_snapshot_v2"), dict) and card.get("prediction_snapshot_v2", {}).get("prediction_identity"))
    review_ids = sorted(str(card.get("prediction_evaluation_v2", {}).get("review_identity")) for card in source_cards if isinstance(card.get("prediction_evaluation_v2"), dict) and card.get("prediction_evaluation_v2", {}).get("review_identity"))
    prediction_bundle_identity = "twpredbundle_" + _hash({"identity": identity, "predictions": prediction_ids, "reviews": review_ids})[:24]
    result = {
        "schema_version": SCHEMA_VERSION, "identity": identity, "stock_intelligence": public_rows,
        "coverage_registry": coverage_summary, "decision_categories": categories,
        "rankings": {"opportunity": [row["symbol"] for row in opportunity], "research": [row["symbol"] for row in research], "risk": [row["symbol"] for row in risks]},
        "market_intelligence": {"direction_distribution": dict(sorted(directions.items())), "sector_rotation": sector_rotation, "market_narrative": market_narrative, "breadth_source": "有明確市場廣度時使用該證據；否則僅標示為個股卡分布", "supporting_evidence": supporting_evidence, "evidence_conflicts": evidence_conflicts, "conflict_policy": "衝突證據不平均抵銷；保留雙方並限制信心。", "template_fallback_symbols": template_fallbacks},
        "window_intelligence": window_intelligence, "prediction_review": _prediction_review(rows, window),
        "pm_daily_summary": pm_summary,
        "research_reasoning_projection": research_projection,
        "research_reasoning_identity": research_projection["production_research_identity"],
        "source_health_v1": source_health(source_cards),
        "model_verifiability_health_v1": verification_health([card.get("verification_record_v1") for card in source_cards if isinstance(card.get("verification_record_v1"), dict)]),
        "prediction_identity": prediction_bundle_identity,
        "prediction_identities": prediction_ids, "review_identities": review_ids,
        "model_boundary": MODEL_BOUNDARY,
    }
    result["decision_identity"] = "twdi2_" + _hash(result)[:24]
    return result


def compact_tw_v2_lines(bundle: dict[str, Any]) -> list[str]:
    pm = bundle.get("pm_daily_summary") or {}
    ranks = bundle.get("rankings") or {}
    research = bundle.get("research_reasoning_projection") if isinstance(bundle.get("research_reasoning_projection"), dict) else {}
    research_lines = compact_research_lines(research) if research else []
    return [
        research_lines[0] if research_lines else f"PM 摘要：{pm.get('one_line') or '尚未取得'}",
        research_lines[1] if len(research_lines) > 1 else f"最大機會：{pm.get('largest_opportunity') or '尚未取得'}",
        research_lines[2] if len(research_lines) > 2 else f"最大風險：{pm.get('largest_risk') or '尚未取得'}",
        f"優先追蹤：{'、'.join((ranks.get('opportunity') or [])[:3]) or '無'}｜決策 {bundle.get('decision_identity') or '尚未取得'}｜預測 {bundle.get('prediction_identity') or '尚未取得'}",
    ]


def validate_tw_decision_intelligence_v2(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if bundle.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    research = bundle.get("research_reasoning_projection")
    if not isinstance(research, dict):
        errors.append("research_reasoning_projection")
    boundary = bundle.get("model_boundary") or {}
    if any(boundary.get(key) is not False for key in (
        "strategy_changed", "scoring_changed", "strategy_ranking_changed",
        "prediction_model_changed", "factor_weights_changed", "automatic_learning",
    )):
        errors.append("model_boundary_violation")
    rows = bundle.get("stock_intelligence") or []
    symbols = [row.get("symbol") for row in rows]
    if len(symbols) != len(set(symbols)):
        errors.append("duplicate_symbol")
    for row in rows:
        if set(row.get("coverage") or {}) != set(DIMENSIONS):
            errors.append(f"coverage_dimensions:{row.get('symbol')}")
        if any(item.get("status") not in STATUSES for item in (row.get("coverage") or {}).values()):
            errors.append(f"coverage_status:{row.get('symbol')}")
        if row.get("decision_category") not in {"BUY_CANDIDATE", "WATCH_CANDIDATE", "HOLD_CANDIDATE", "REDUCE_CANDIDATE", "AVOID_CANDIDATE"}:
            errors.append(f"decision_category:{row.get('symbol')}")
        if (row.get("confidence_explanation") or {}).get("model_score_recomputed") is not False:
            errors.append(f"confidence_recomputed:{row.get('symbol')}")
    categories = bundle.get("decision_categories") or {}
    flattened = [symbol for values in categories.values() for symbol in values]
    if sorted(flattened) != sorted(symbols) or len(flattened) != len(set(flattened)):
        errors.append("category_partition")
    rankings = bundle.get("rankings") or {}
    if any(sorted(values) != sorted(symbols) for values in rankings.values()):
        errors.append("ranking_partition")
    if isinstance(research, dict):
        errors.extend(
            f"research:{item}"
            for item in validate_tw_daily_research(research, set(symbols))
        )
    copy = {key: value for key, value in bundle.items() if key != "decision_identity"}
    if bundle.get("decision_identity") != "twdi2_" + _hash(copy)[:24]:
        errors.append("decision_identity")
    return sorted(set(errors))
