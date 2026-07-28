"""Canonical seven-window daily decision experience projection.

This module explains existing decisions.  It does not score, rank, promote a
setup, or alter trading geometry.  Every public channel consumes the same
deterministic projection built from one admitted market/window payload.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Iterable

SCHEMA_VERSION = "daily_decision_experience_v1"
TRANSITIONS = {
    "UNCHANGED", "STRENGTHENED", "WEAKENED", "UPGRADED", "DOWNGRADED",
    "INVALIDATED", "CLOSED", "NO_PRIOR_STATE",
}
MISSING_STATES = {
    "AVAILABLE", "STALE", "MISSING", "NOT_APPLICABLE", "SOURCE_FAILED",
    "PARTIAL", "DEFERRED",
}
WINDOW_ORDER = {
    "TW": ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"),
    "US": ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"),
}
SOURCE_PRIORITY = {
    "official_disclosure": 1, "exchange_or_regulator": 1, "company_ir": 3,
    "financial_results": 2, "government_macro": 5, "sector": 6,
    "technical": 7, "market_flow": 8, "major_financial_media": 9,
    "general_media": 9, "sentiment": 10,
}
PUBLIC_LABELS = {
    "UNCHANGED": "判斷不變", "STRENGTHENED": "判斷增強", "WEAKENED": "判斷轉弱",
    "UPGRADED": "決策升級", "DOWNGRADED": "決策降級", "INVALIDATED": "策略失效",
    "CLOSED": "結果已收束", "NO_PRIOR_STATE": "當日尚無上一正式時段",
    "hold": "可留倉", "hold_with_protection": "可留倉但需保護", "watch": "觀察",
    "reduce": "降低部位", "exit": "退出／不建議留倉", "no_trade": "無交易",
    "win": "交易命中", "loss": "交易失敗", "not_triggered": "未觸發",
    "open_at_close": "收盤尚未結束", "pending_evidence": "證據不足",
    "hit": "命中", "fail": "失敗", "pending": "待確認", "partial_hit": "部分命中",
}


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
    preferred = {
        "pre_open_0700": ("structured_pre_open_cards", "cards"),
        "intraday_1305": ("structured_intraday_cards", "cards"),
        "pre_close_1335": ("structured_pre_close_cards", "structured_intraday_cards", "cards"),
        "post_close_1500": ("structured_review_cards", "cards"),
        "us_pre_market_2000": ("structured_premarket_cards", "cards", "items"),
        "us_intraday_2300": ("structured_intraday_cards", "cards", "items"),
        "us_post_close_review_0630": ("structured_review_cards", "cards", "items"),
    }.get(window, ("cards",))
    dashboard = payload.get("dashboard_ready_contract")
    candidates: list[Any] = [payload.get(key) for key in preferred]
    if isinstance(dashboard, dict):
        candidates.append(dashboard.get("cards"))
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return [card for card in candidate if isinstance(card, dict)]
    return []


def _symbol(card: dict[str, Any]) -> str:
    return _text(card.get("symbol") or card.get("stock_id") or card.get("card_id"), "UNKNOWN")


def _identity(payload: dict[str, Any], market: str, window: str) -> dict[str, Any]:
    runtime = payload.get("runtime_provenance") if isinstance(payload.get("runtime_provenance"), dict) else {}
    return {
        "market": market,
        "window": window,
        "effective_trading_date": payload.get("effective_trading_date") or payload.get("trading_date") or runtime.get("effective_trading_date"),
        "revision": payload.get("revision") or runtime.get("revision"),
        "snapshot_id": payload.get("snapshot_id") or runtime.get("snapshot_id"),
        "source_payload_hash": payload.get("source_payload_hash") or runtime.get("source_payload_hash") or runtime.get("payload_hash"),
        "as_of": payload.get("source_data_time") or payload.get("generated_at") or runtime.get("generated_at"),
    }


def _evidence_id(market: str, window: str, symbol: str, evidence_class: str, reference: str) -> str:
    raw = "|".join((market, window, symbol, evidence_class, reference))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _evidence_record(
    *, market: str, window: str, symbol: str, source_name: Any, source_type: str,
    reference: Any, published_at: Any, observed_at: Any, freshness: Any,
    evidence_class: str, summary: Any, direction: Any, materiality: Any,
    reliability: Any, decision_impact: Any,
) -> dict[str, Any]:
    ref = _text(reference, f"{source_type}:{symbol}")
    return {
        "evidence_id": _evidence_id(market, window, symbol, evidence_class, ref),
        "market": market,
        "symbol_or_scope": symbol,
        "source_name": _text(source_name, "尚未提供來源名稱"),
        "source_type": source_type,
        "source_priority": SOURCE_PRIORITY.get(source_type, 99),
        "source_url_or_reference": ref,
        "published_at": published_at,
        "observed_at": observed_at,
        "freshness": _text(freshness, "unavailable").lower(),
        "evidence_class": evidence_class,
        "summary": _text(summary, "本批次未提供摘要"),
        "direction": _text(direction, "unavailable").lower(),
        "materiality": _text(materiality, "unavailable").lower(),
        "reliability": _text(reliability, "unavailable").lower(),
        "decision_impact": _text(decision_impact, "本證據未改變既有決策"),
    }


def build_evidence_chain(market: str, window: str, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for card in cards:
        symbol = _symbol(card)
        technical = card.get("technical_data") if isinstance(card.get("technical_data"), dict) else {}
        if technical:
            records.append(_evidence_record(
                market=market, window=window, symbol=symbol,
                source_name=technical.get("source"), source_type="technical",
                reference=f"{technical.get('history_start')}..{technical.get('history_end')}",
                published_at=technical.get("source_timestamp"), observed_at=technical.get("source_timestamp"),
                freshness=technical.get("freshness"), evidence_class="technical_history",
                summary=card.get("technical_summary") or f"歷史資料 {technical.get('history_bars', 0)}/{technical.get('required_bars', 0)} 根",
                direction=technical.get("direction"), materiality="medium",
                reliability="available" if technical.get("analysis_eligible") else "limited",
                decision_impact=card.get("reasoning") or card.get("action_change_reason"),
            ))
        news = card.get("news_evidence") if isinstance(card.get("news_evidence"), dict) else {}
        primary = news.get("primary_evidence") if isinstance(news.get("primary_evidence"), dict) else {}
        if primary:
            source_type = "official_disclosure" if primary.get("official_source") else "general_media"
            records.append(_evidence_record(
                market=market, window=window, symbol=symbol,
                source_name=primary.get("publisher"), source_type=source_type,
                reference=primary.get("source_url") or primary.get("dedupe_key"),
                published_at=primary.get("published_at"), observed_at=(news.get("retrieval") or {}).get("query_completed_at"),
                freshness=card.get("news_status") or "available", evidence_class="news",
                summary=primary.get("headline"), direction=primary.get("direction"),
                materiality=primary.get("materiality"), reliability=primary.get("source_quality"),
                decision_impact=card.get("news_strategy_impact"),
            ))
        current = card.get("current_price") if card.get("current_price") is not None else card.get("premarket_price")
        if current is not None:
            records.append(_evidence_record(
                market=market, window=window, symbol=symbol,
                source_name=card.get("source_name") or card.get("source"), source_type="technical",
                reference=card.get("source_payload_hash") or f"price:{symbol}:{card.get('source_record_time')}",
                published_at=card.get("source_record_time"), observed_at=card.get("market_data_as_of") or card.get("source_timestamp"),
                freshness=card.get("freshness_status") or card.get("source_freshness"), evidence_class="observed_market",
                summary=f"觀察價格 {current}", direction=card.get("direction"), materiality="high",
                reliability=card.get("data_status"), decision_impact=card.get("action_change_reason") or card.get("adjustment_reason"),
            ))
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        if record["market"] == market:
            deduped[record["evidence_id"]] = record
    return sorted(deduped.values(), key=lambda item: (item["source_priority"], item["symbol_or_scope"], item["evidence_id"]))


def build_missing_data(cards: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for card in cards:
        symbol = _symbol(card)
        missing = _unique([*(card.get("missing_fields") or []), *(card.get("data_gaps") or [])])
        for field in missing:
            normalized = field.upper()
            status = "STALE" if "STALE" in normalized else "SOURCE_FAILED" if "FAILED" in normalized or "TIMEOUT" in normalized else "MISSING"
            records.append({
                "symbol_or_scope": symbol, "data_class": field, "status": status,
                "reason": normalized, "expected_source": _expected_source(normalized),
                "last_success_at": None, "freshness": "unavailable",
                "decision_impact": "此缺口限制決策升級，不視為中性證據。",
                "confidence_impact": "降低可解釋信心上限。",
                "fallback_used": False, "fallback_source": None,
                "user_message": f"{field} 尚未取得；目前決策僅依已取得證據。",
            })
        freshness = _text(card.get("freshness_status") or card.get("source_freshness")).lower()
        if freshness == "stale":
            records.append({
                "symbol_or_scope": symbol, "data_class": "observed_market", "status": "STALE",
                "reason": "SOURCE_STALE", "expected_source": _text(card.get("source_name"), "market_data_provider"),
                "last_success_at": card.get("source_record_time"), "freshness": "stale",
                "decision_impact": "過期行情不得作為最新觸發證據。", "confidence_impact": "降低信心。",
                "fallback_used": False, "fallback_source": None,
                "user_message": "行情證據已過期，本批次不將其視為最新證據。",
            })
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        unique[(record["symbol_or_scope"], record["data_class"], record["status"])] = record
    return sorted(unique.values(), key=lambda item: (item["symbol_or_scope"], item["data_class"]))


def _expected_source(reason: str) -> str:
    for token, source in (
        ("NEWS", "official/company/news provider"), ("CHIP", "institutional flow provider"),
        ("GAP", "premarket/open quote provider"), ("EVENT", "official disclosure/event provider"),
        ("HISTORY", "canonical daily OHLCV provider"), ("VOLUME", "intraday volume provider"),
    ):
        if token in reason:
            return source
    return "canonical market-specific provider"


def _confidence(cards: list[dict[str, Any]], evidence: list[dict[str, Any]], missing: list[dict[str, Any]]) -> dict[str, Any]:
    scores: list[float] = []
    cap_reasons: list[str] = []
    for card in cards:
        strategies = card.get("strategies") if isinstance(card.get("strategies"), dict) else {}
        tactical = strategies.get("daily_tactical") if isinstance(strategies.get("daily_tactical"), dict) else {}
        if not tactical and isinstance(card.get("daily_tactical_summary"), dict):
            tactical = card["daily_tactical_summary"]
        for value in (card.get("confidence"), tactical.get("confidence"), card.get("score"), card.get("research_confidence")):
            number = _number(value)
            if number is not None:
                scores.append(number * 100 if 0 <= number <= 1 else number)
                break
        cap_reasons += _unique([card.get("confidence_cap_reason"), *(card.get("data_gaps") or [])])
    positive = [item["summary"] for item in evidence if item["direction"] in {"bullish", "positive", "long"}]
    negative = [item["summary"] for item in evidence if item["direction"] in {"bearish", "negative", "short"}]
    freshness = Counter(item["freshness"] for item in evidence)
    score = round(sum(scores) / len(scores), 1) if scores else None
    level = "unavailable" if score is None else "high" if score >= 70 else "medium" if score >= 45 else "low"
    consistency = "insufficient" if not evidence else "mixed" if positive and negative else "aligned"
    return {
        "score": score, "level": level, "score_source": "existing_canonical_card_confidence",
        "model_weights_changed": False,
        "supporting_evidence": positive[:4], "contradicting_evidence": negative[:4],
        "missing_inputs": _unique(item["data_class"] for item in missing)[:12],
        "freshness_quality": dict(sorted(freshness.items())),
        "evidence_consistency": consistency,
        "market_uncertainty": "偏高" if missing or consistency != "aligned" else "一般",
        "confidence_cap_reason": _unique(cap_reasons)[:8] or (["EVIDENCE_COVERAGE_LIMITED"] if missing else []),
        "explanation": _confidence_text(score, positive, negative, missing),
    }


def _confidence_text(score: float | None, positive: list[str], negative: list[str], missing: list[dict[str, Any]]) -> str:
    if score is None:
        return "本批次沒有可追溯的既有信心分數；不補造分數。"
    reasons = []
    if positive:
        reasons.append(f"正向證據 {len(positive)} 項")
    if negative:
        reasons.append(f"反向證據 {len(negative)} 項")
    if missing:
        reasons.append(f"資料缺口 {len(missing)} 項限制信心上限")
    return f"沿用既有決策信心 {score:.1f}；" + ("、".join(reasons) if reasons else "本批次未提供可展開的證據因子") + "。"


def _dedup_timeline(cards: list[dict[str, Any]], market: str) -> list[dict[str, Any]]:
    allowed = set(WINDOW_ORDER[market])
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for card in cards:
        symbol = _symbol(card)
        candidates = [item for item in card.get("lifecycle_timeline") or [] if isinstance(item, dict)]
        for source_key in ("source_plan", "source_trade_plan"):
            source = card.get(source_key) if isinstance(card.get(source_key), dict) else {}
            source_window = source.get("source_window")
            if source_window in allowed:
                candidates.append({
                    "source_window": source_window,
                    "state": source.get("plan_status") or source.get("trade_plan_status") or "watch",
                    "effective_date": source.get("source_effective_date") or card.get("trading_date") or card.get("session_date"),
                    "source_snapshot_id": source.get("source_snapshot_id"),
                    "revision": source.get("source_revision"), "source_hash": source.get("source_hash"),
                    "identity_status": "explicit_source_plan_binding",
                })
        intraday = card.get("intraday_evidence") if isinstance(card.get("intraday_evidence"), dict) else {}
        if intraday.get("source_window") in allowed:
            candidates.append({
                "source_window": intraday.get("source_window"),
                "state": intraday.get("trigger_status") or "observed",
                "effective_date": intraday.get("source_effective_date") or card.get("trading_date") or card.get("session_date"),
                "source_snapshot_id": intraday.get("source_snapshot_id"),
                "revision": intraday.get("source_revision"), "source_hash": intraday.get("source_hash"),
                "identity_status": "explicit_intraday_evidence_binding",
            })
        card_window = _text(card.get("window"))
        if card_window in allowed:
            candidates.append({
                "source_window": card_window, "state": _state_for_card(card),
                "effective_date": card.get("trading_date") or card.get("session_date"),
                "source_snapshot_id": card.get("snapshot_id"), "revision": card.get("revision"),
                "source_hash": card.get("source_payload_hash"), "identity_status": "current_payload_projection",
            })
        for item in candidates:
            if not isinstance(item, dict) or item.get("source_window") not in allowed:
                continue
            candidate = {**item, "symbol": symbol}
            key = (symbol, str(item["source_window"]))
            current = selected.get(key)
            quality = (1 if candidate.get("source_snapshot_id") else 0, int(candidate.get("revision") or 0))
            current_quality = (1 if current and current.get("source_snapshot_id") else 0, int((current or {}).get("revision") or 0))
            if current is None or quality >= current_quality:
                selected[key] = candidate
    order = {window: index for index, window in enumerate(WINDOW_ORDER[market])}
    return sorted(selected.values(), key=lambda item: (item["symbol"], order[str(item["source_window"])]))


def _state_for_card(card: dict[str, Any]) -> str:
    for key in ("trade_outcome", "canonical_outcome", "overnight_action", "canonical_intraday_action", "intraday_action", "trigger_status", "entry_trigger_state", "plan_status", "decision_category", "action"):
        value = _text(card.get(key)).lower()
        if value:
            return value
    return "unknown"


def _transition(window: str, market: str, cards: list[dict[str, Any]], timeline: list[dict[str, Any]]) -> dict[str, Any]:
    current_index = WINDOW_ORDER[market].index(window)
    current_states: list[str] = []
    previous_states: list[str] = []
    for card in cards:
        symbol = _symbol(card)
        rows = [item for item in timeline if item["symbol"] == symbol]
        current = next((item for item in rows if item["source_window"] == window), None)
        prior = [item for item in rows if WINDOW_ORDER[market].index(item["source_window"]) < current_index]
        if current:
            current_states.append(_text(current.get("state"), "unknown"))
        if prior:
            previous_states.append(_text(prior[-1].get("state"), "unknown"))
    if current_index == 0 or not previous_states:
        state = "NO_PRIOR_STATE"
        reason = "這是當日第一個正式 window，沒有可安全引用的上一時段決策。"
    elif any(value in {"invalidated", "exit", "loss", "stop_hit"} for value in current_states):
        state, reason = "INVALIDATED", "既有生命週期證據顯示策略已失效或退出。"
    elif window in {"post_close_1500", "us_post_close_review_0630"} and any(value in {"win", "loss", "no_trade", "not_triggered", "closed"} for value in current_states):
        state, reason = "CLOSED", "盤後結果已由 canonical outcome 收束。"
    elif current_states and Counter(current_states) == Counter(previous_states):
        state, reason = "UNCHANGED", "目前狀態與上一正式 window 一致。"
    elif any(value in {"active", "hold", "triggered", "win"} for value in current_states) and any(value in {"watch", "wait", "not_triggered"} for value in previous_states):
        state, reason = "UPGRADED", "新增證據使既有觀察狀態升級。"
    elif any(value in {"watch", "reduce", "no_trade", "pending_evidence"} for value in current_states):
        state, reason = "DOWNGRADED", "新增風險、資料限制或市場行為使決策降級。"
    else:
        state, reason = "WEAKENED", "狀態已改變，但目前證據不足以宣稱升級。"
    return {
        "state": state, "public_label": PUBLIC_LABELS[state], "reason": reason,
        "previous_state_counts": dict(sorted(Counter(previous_states).items())),
        "current_state_counts": dict(sorted(Counter(current_states).items())),
        "evidence_source": "deduplicated lifecycle_timeline",
    }


def _summary_fields(market: str, window: str, payload: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, str]:
    if market == "TW" and window == "pre_open_0700":
        summary = payload.get("pre_open_summary") if isinstance(payload.get("pre_open_summary"), dict) else {}
        derived = _decision_group_counts(cards)
        action = f"主要交易機會 {derived['top'] if derived['classified'] else summary.get('top_opportunity_count', 0)}、觀察 {derived['watch'] if derived['classified'] else summary.get('watch_only_count', 0)}、暫不交易 {derived['no_trade'] if derived['classified'] else summary.get('no_trade_count', 0)}"
        view = "盤前決策已建立；僅依本批次可用證據判定。"
    elif market == "US" and window == "us_pre_market_2000":
        summary = payload.get("premarket_summary") if isinstance(payload.get("premarket_summary"), dict) else {}
        derived = _decision_group_counts(cards)
        action = f"主要交易機會 {derived['top'] if derived['classified'] else summary.get('top_opportunity_count', 0)}、觀察 {derived['watch'] if derived['classified'] else summary.get('watch_only_count', 0)}、暫不交易 {derived['no_trade'] if derived['classified'] else summary.get('no_trade_count', 0)}"
        view = "美股盤前決策已建立，盤中只監控此 admitted source plan。"
    else:
        summary = payload.get("tw_window_summary") if market == "TW" else payload.get("intraday_summary") or payload.get("review_summary")
        summary = summary if isinstance(summary, dict) else {}
        derived = _lifecycle_counts(cards)
        if window in {"intraday_1305", "us_intraday_2300"}:
            action = f"已觸發 {derived['triggered'] if derived['classified'] else summary.get('triggered_count', 0)}、已失效 {derived['invalidated'] if derived['classified'] else summary.get('invalidated_count', 0)}、仍可行動 {derived['actionable'] if derived['classified'] else summary.get('still_actionable_count', 0)}"
            view = "盤中依觀察價格、成交量與來源計畫證據更新。"
        elif window == "pre_close_1335":
            counts = derived["overnight"] if derived["overnight"] else summary.get("overnight_action_counts") or {}
            action = "、".join(f"{PUBLIC_LABELS.get(str(key), key)} {value}" for key, value in counts.items()) or "本批次沒有可安全彙整的留倉決策"
            view = "收盤前依同日盤中狀態決定留倉、觀察、降低部位或退出。"
        else:
            outcomes = derived["outcomes"] if derived["outcomes"] else summary.get("trade_outcome_counts") or summary.get("outcome_counts") or payload.get("outcome_aggregate") or {}
            action = "、".join(f"{PUBLIC_LABELS.get(str(key), key)} {value}" for key, value in outcomes.items()) or "本批次結果尚未提供"
            view = "盤後分開呈現預測評估與交易結果。"
    return {"current_view": view, "current_action": action}


def _decision_group_counts(cards: list[dict[str, Any]]) -> dict[str, int | bool]:
    counts = {"top": 0, "watch": 0, "no_trade": 0, "classified": False}
    for card in cards:
        eligibility = card.get("eligibility") if isinstance(card.get("eligibility"), dict) else {}
        category = _text(card.get("decision_category") or card.get("opportunity_group") or card.get("plan_status")).lower()
        top = card.get("top_opportunity") is True or eligibility.get("top_opportunity") is True or category in {"top_opportunity", "entry_ready"}
        no_trade = card.get("no_trade") is True or eligibility.get("no_trade") is True or category == "no_trade"
        watch = card.get("watch_only") is True or eligibility.get("watch_only") is True or category in {"watch", "watch_only", "watch_wait"}
        if top or no_trade or watch:
            counts["classified"] = True
        counts["top"] += int(top)
        counts["no_trade"] += int(no_trade)
        counts["watch"] += int(watch and not top and not no_trade)
    return counts


def _lifecycle_counts(cards: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"triggered": 0, "invalidated": 0, "actionable": 0, "classified": False, "overnight": {}, "outcomes": {}}
    overnight: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    for card in cards:
        strategies = card.get("strategies") if isinstance(card.get("strategies"), dict) else {}
        tactical = strategies.get("daily_tactical") if isinstance(strategies.get("daily_tactical"), dict) else {}
        if not tactical and isinstance(card.get("daily_tactical_summary"), dict):
            tactical = card["daily_tactical_summary"]
        trigger = _text(card.get("trigger_status") or card.get("entry_trigger_state")).lower()
        action = _text(card.get("canonical_intraday_action") or card.get("intraday_action") or tactical.get("action")).lower()
        if not trigger and isinstance(tactical.get("entry_triggered"), bool):
            trigger = "triggered" if tactical["entry_triggered"] else "not_triggered"
        if trigger:
            result["classified"] = True
        result["triggered"] += int(trigger in {"triggered", "target_hit"})
        result["invalidated"] += int(trigger in {"invalidated", "stop_hit"} or action in {"invalidated", "exit"})
        eligibility = card.get("eligibility") if isinstance(card.get("eligibility"), dict) else {}
        explicit_actionable = eligibility.get("actionable") if "actionable" in eligibility else card.get("actionable")
        if isinstance(explicit_actionable, bool):
            result["classified"] = True
            result["actionable"] += int(explicit_actionable and trigger not in {"invalidated", "stop_hit"})
        elif trigger == "triggered" and action not in {"invalidated", "exit", "no_trade", "cancel_chase"}:
            result["actionable"] += 1
        overnight_action = _text(card.get("overnight_action")).lower()
        if overnight_action:
            overnight[overnight_action] += 1
        outcome = _text(card.get("trade_outcome") or card.get("canonical_outcome")).lower()
        review = card.get("review_result") if isinstance(card.get("review_result"), dict) else card.get("review_snapshot") if isinstance(card.get("review_snapshot"), dict) else {}
        outcome = outcome or _text(review.get("trade_outcome") or review.get("canonical_outcome") or review.get("status")).lower()
        if outcome:
            outcomes[outcome] += 1
    result["overnight"] = dict(sorted(overnight.items()))
    result["outcomes"] = dict(sorted(outcomes.items()))
    return result


def build_daily_decision_experience(market: str, window: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    market = str(market).upper()
    if market not in WINDOW_ORDER or window not in WINDOW_ORDER[market]:
        raise ValueError(f"unsupported market/window: {market}/{window}")
    payload = payload if isinstance(payload, dict) else {}
    raw_cards = _cards(payload, window)
    foreign_cards = [card for card in raw_cards if _text(card.get("market")).upper() not in {"", market}]
    cards = [card for card in raw_cards if card not in foreign_cards]
    identity = _identity(payload, market, window)
    evidence = build_evidence_chain(market, window, cards)
    missing = build_missing_data(cards, evidence)
    confidence = _confidence(cards, evidence, missing)
    timeline = _dedup_timeline(cards, market)
    transition = _transition(window, market, cards, timeline)
    summary = _summary_fields(market, window, payload, cards)
    positive = [item for item in evidence if item["direction"] in {"bullish", "positive", "long"}]
    negative = [item for item in evidence if item["direction"] in {"bearish", "negative", "short"}]
    freshness = Counter(item["freshness"] for item in evidence)
    result = {
        "schema_version": SCHEMA_VERSION, "market": market, "window": window,
        **identity, **summary,
        "why": [item["summary"] for item in evidence[:4]] or ["本批次未提供可追溯 evidence；不補造原因。"],
        "opportunity": [item["summary"] for item in positive[:3]] or ["未發現可由本批次證據支持的主要機會。"],
        "risk": [item["summary"] for item in negative[:3]] or (["資料缺口限制決策升級。"] if missing else ["本批次未提供額外負面證據。"]),
        "confidence": confidence.get("score"), "confidence_explanation": confidence,
        "evidence_summary": {"count": len(evidence), "records": evidence, "source_priority_policy": "official_first_v1"},
        "missing_data_impact": {"count": len(missing), "records": missing, "missing_is_neutral": False},
        "change_from_previous_window": transition,
        "next_trigger": _next_trigger(window, cards, missing),
        "next_window_watch": _next_window(window, market),
        "source_freshness": {"distribution": dict(sorted(freshness.items())), "has_stale": bool(freshness.get("stale")), "has_missing": bool(missing)},
        "lifecycle_timeline": timeline,
        "market_isolation": {"market": market, "cross_market_evidence_count": 0, "rejected_cross_market_card_count": len(foreign_cards)},
        "card_count": len(cards), "artifact_revision": identity.get("revision"),
        "model_contract": {"strategy_changed": False, "scoring_changed": False, "ranking_changed": False},
    }
    stable = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result["canonical_summary_hash"] = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    return result


def _next_trigger(window: str, cards: list[dict[str, Any]], missing: list[dict[str, Any]]) -> str:
    candidates = _unique(
        card.get("entry_condition") or card.get("next_session_action") or card.get("tomorrow_watch_status")
        for card in cards
    )
    if candidates:
        return "；".join(candidates[:2])
    if missing:
        return "先補足關鍵缺失資料；資料未恢復前不升級 action。"
    defaults = {
        "pre_open_0700": "觀察開盤價格、量能與事件風險是否支持原決策。",
        "intraday_1305": "觀察價格、量能、目標與停損距離是否改變。",
        "pre_close_1335": "觀察收盤狀態與隔夜風險，決定是否延續原策略。",
        "post_close_1500": "下一交易日依新 admitted setup 重新評估。",
        "us_pre_market_2000": "23:00 僅依本盤前 source plan 檢查價格、Gap與量能。",
        "us_intraday_2300": "06:30 以實際行情證據判定 outcome，不重建 trade plan。",
        "us_post_close_review_0630": "下一個 20:00 window 重新建立 admitted source plan。",
    }
    return defaults[window]


def _next_window(window: str, market: str) -> str:
    order = WINDOW_ORDER[market]
    index = order.index(window)
    return order[index + 1] if index + 1 < len(order) else "next_trading_session"


def compact_decision_story(summary: dict[str, Any]) -> list[str]:
    confidence = summary.get("confidence_explanation") or {}
    score = summary.get("confidence")
    confidence_text = "尚未取得" if score is None else f"{float(score):.1f}"
    transition = summary.get("change_from_previous_window") or {}
    return [
        f"目前判斷：{summary.get('current_view')}",
        f"目前行動：{summary.get('current_action')}",
        f"信心：{confidence_text}｜{confidence.get('explanation')}",
        f"相較上一時段：{transition.get('public_label') or PUBLIC_LABELS.get(str(transition.get('state')), '尚未判定')}｜{transition.get('reason')}",
        f"下一觸發：{summary.get('next_trigger')}",
    ]


def validate_daily_decision_experience(summary: dict[str, Any]) -> list[str]:
    """Semantic validation; field presence alone is not sufficient."""
    errors: list[str] = []
    required = (
        "current_view", "current_action", "why", "opportunity", "risk",
        "confidence_explanation", "evidence_summary", "missing_data_impact",
        "change_from_previous_window", "next_trigger", "next_window_watch",
        "effective_trading_date", "as_of", "source_freshness",
        "canonical_summary_hash",
    )
    for field in required:
        if field not in summary:
            errors.append(f"missing:{field}")
    transition = summary.get("change_from_previous_window") or {}
    if transition.get("state") not in TRANSITIONS:
        errors.append("invalid_transition")
    evidence = (summary.get("evidence_summary") or {}).get("records") or []
    evidence_fields = {
        "evidence_id", "market", "symbol_or_scope", "source_name", "source_type",
        "source_url_or_reference", "published_at", "observed_at", "freshness",
        "evidence_class", "summary", "direction", "materiality", "reliability",
        "decision_impact",
    }
    for index, record in enumerate(evidence):
        if not isinstance(record, dict) or not evidence_fields.issubset(record):
            errors.append(f"invalid_evidence:{index}")
        elif record.get("market") != summary.get("market"):
            errors.append(f"cross_market_evidence:{index}")
    missing = (summary.get("missing_data_impact") or {}).get("records") or []
    if (summary.get("missing_data_impact") or {}).get("missing_is_neutral") is not False:
        errors.append("missing_data_must_not_be_neutral")
    for index, record in enumerate(missing):
        if not isinstance(record, dict) or record.get("status") not in MISSING_STATES:
            errors.append(f"invalid_missing_status:{index}")
        elif not record.get("decision_impact") or not record.get("confidence_impact"):
            errors.append(f"missing_impact_absent:{index}")
    confidence = summary.get("confidence_explanation") or {}
    for field in (
        "supporting_evidence", "contradicting_evidence", "missing_inputs",
        "freshness_quality", "evidence_consistency", "market_uncertainty",
        "confidence_cap_reason", "explanation",
    ):
        if field not in confidence:
            errors.append(f"confidence_missing:{field}")
    if confidence.get("model_weights_changed") is not False:
        errors.append("confidence_changed_model_weights")
    if (summary.get("source_freshness") or {}).get("has_stale") and not any(item.get("status") == "STALE" for item in missing):
        errors.append("stale_not_disclosed")
    if (summary.get("market_isolation") or {}).get("cross_market_evidence_count") != 0:
        errors.append("market_isolation_failed")
    timeline = summary.get("lifecycle_timeline") or []
    seen: set[tuple[str, str]] = set()
    effective_date = _text(summary.get("effective_trading_date"))
    for index, item in enumerate(timeline):
        key = (_text(item.get("symbol")), _text(item.get("source_window")))
        if key in seen:
            errors.append(f"duplicate_timeline_window:{index}")
        seen.add(key)
        item_date = _text(item.get("effective_date"))
        if effective_date and item_date and item_date > effective_date:
            errors.append(f"future_timeline_evidence:{index}")
    copy = {key: value for key, value in summary.items() if key != "canonical_summary_hash"}
    expected_hash = hashlib.sha256(json.dumps(copy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if summary.get("canonical_summary_hash") != expected_hash:
        errors.append("canonical_summary_hash_mismatch")
    return sorted(set(errors))
