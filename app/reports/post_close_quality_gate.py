"""Cross-market post-close decision-quality projection.

This is a presentation admission gate.  It does not score, infer, mutate, or
replace canonical review evidence; it only prevents a channel from describing
an unproven component as a prediction success or failure.
"""
from __future__ import annotations

from typing import Any

from app.reports.tw_tactical_direction_evaluation import project_tactical_direction_evaluation

VERSION = "post_close_decision_quality_gate_v2"
POST_CLOSE_WINDOWS = {"post_close_1500", "us_post_close_review_0630"}
RANGE_RESULTS = {"hit", "partial_hit", "miss", "not_applicable"}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _result(value: Any) -> str | None:
    value = str(value or "").lower()
    return {"hit": "hit", "correct": "hit", "miss": "miss", "incorrect": "miss",
            "partial_hit": "partial_hit", "not_applicable": "not_applicable"}.get(value)


def _insufficient(reason: str) -> dict[str, Any]:
    return {"status": "INSUFFICIENT_EVIDENCE", "result": None, "reason_code": reason}


def _evaluated(result: str, scope: str) -> dict[str, Any]:
    return {"status": "EVALUATED", "result": result, "reason_code": None, "scope": scope}


def _not_applicable(reason: str, scope: str) -> dict[str, Any]:
    return {"status": "NOT_APPLICABLE", "result": "not_applicable", "reason_code": reason, "scope": scope}


def _tw_canonical_range_result(card: dict[str, Any]) -> str | None:
    """Use only the established tactical range result; never research-v2."""
    candidates = [card.get("prediction_range_result")]
    evaluation = card.get("prediction_evaluation")
    if isinstance(evaluation, dict):
        candidates.append(evaluation.get("range_result"))
    for candidate in candidates:
        result = _result(candidate)
        if result in RANGE_RESULTS:
            return result
    return None


def evaluate_card(card: dict[str, Any], *, market: str, window: str) -> dict[str, Any]:
    """Return the only public-safe outcome labels for one post-close card."""
    if (market, window) not in {("TW", "post_close_1500"), ("US", "us_post_close_review_0630")}:
        raise ValueError("QUALITY_GATE_WINDOW")
    review = card.get("review") if isinstance(card.get("review"), dict) else {}
    actual = review.get("actual_range") if isinstance(review.get("actual_range"), dict) else {}
    low = _number(review.get("actual_low", card.get("actual_low", actual.get("low", card.get("session_low")))))
    high = _number(review.get("actual_high", card.get("actual_high", actual.get("high", card.get("session_high")))))
    close = _number(review.get("actual_close", card.get("actual_close", card.get("current_price"))))
    actual_ok = None not in (low, high, close) and low <= close <= high
    evaluation = review.get("prediction_evaluation_v2") if isinstance(review.get("prediction_evaluation_v2"), dict) else {}
    if not evaluation and isinstance(card.get("prediction_evaluation_v2"), dict):
        evaluation = card["prediction_evaluation_v2"]
    direction_eval = evaluation.get("direction") if isinstance(evaluation.get("direction"), dict) else {}
    range_eval = evaluation.get("range") if isinstance(evaluation.get("range"), dict) else {}

    if not actual_ok:
        direction = _insufficient("ACTUAL_OUTCOME_MISSING_OR_INVALID")
        interval = _insufficient("ACTUAL_OUTCOME_MISSING_OR_INVALID")
    elif market == "TW" and ("frozen_delivery_prediction_v1" in card or "delivery_prediction_evaluation_v1" in card):
        from app.reports.tw_delivery_evaluation import quality
        direction, interval = quality(card)
    elif market == "US":
        if direction_eval.get("status") == "evaluated" and isinstance(direction_eval.get("hit"), bool) and direction_eval.get("forecast") and direction_eval.get("actual"):
            direction = _evaluated("hit" if direction_eval["hit"] else "miss", "US_CURRENT_SESSION_DIRECTION")
        elif _result(direction_eval.get("result")) and direction_eval.get("predicted_direction"):
            direction = _evaluated(_result(direction_eval.get("result")), "US_CURRENT_SESSION_DIRECTION")
        else:
            direction = _insufficient("DIRECTION_EVALUATION_NOT_ADMITTED")
        range_result = _result(card.get("prediction_range_result"))
        if range_eval.get("status") == "evaluated" and isinstance(range_eval.get("hit"), bool) and range_result:
            interval = _evaluated(range_result, "US_CURRENT_SESSION_RANGE")
        else:
            interval = _insufficient("RANGE_EVALUATION_NOT_ADMITTED")
    else:
        direction = project_tactical_direction_evaluation(card)
        integrity = card.get("prediction_interval_integrity") if isinstance(card.get("prediction_interval_integrity"), dict) else {}
        failure = card.get("prediction_failure") if isinstance(card.get("prediction_failure"), dict) else {}
        if integrity.get("status") == "INVALID" or failure.get("reason_code") == "prediction_interval_reversed":
            interval = _insufficient("PREDICTION_INTERVAL_INVALID")
        else:
            range_result = _tw_canonical_range_result(card)
            if range_result == "not_applicable":
                interval = _not_applicable("NO_CANONICAL_TACTICAL_RANGE_FORECAST", "TW_POST_CLOSE_RANGE")
            elif range_result:
                interval = _evaluated(range_result, "TW_POST_CLOSE_RANGE")
            else:
                interval = _insufficient("RANGE_EVALUATION_NOT_ADMITTED")
    components = (direction["status"], interval["status"])
    status = "EVALUATED" if components == ("EVALUATED", "EVALUATED") else "PARTIAL_EVIDENCE" if actual_ok else "INSUFFICIENT_EVIDENCE"
    if all(value in {"EVALUATED", "NOT_APPLICABLE"} for value in components):
        status = "EVALUATED"
    return {"schema_version": VERSION, "market": market, "window": window, "symbol": str(card.get("symbol") or card.get("stock_id") or ""),
            "prediction_identity": (card.get("source_trade_plan") or {}).get("source_snapshot_id") or card.get("source_snapshot_id"),
            "actual": {"status": "AVAILABLE" if actual_ok else "INSUFFICIENT_EVIDENCE", "low": low, "high": high, "close": close},
            "direction": direction, "range": interval, "status": status}


def batch_gate(cards: list[dict[str, Any]], *, market: str, window: str) -> dict[str, Any]:
    items = [evaluate_card(card, market=market, window=window) for card in cards]
    safe = all(item["direction"].get("result") is not None or item["direction"].get("reason_code") for item in items) and all(item["range"].get("result") is not None or item["range"].get("reason_code") for item in items)
    return {"schema_version": VERSION, "market": market, "window": window, "cards": items,
            "status": "QUALIFIED" if all(item["status"] == "EVALUATED" for item in items) else "PARTIAL_QUALIFIED" if safe else "BLOCKED_MISLEADING_SUMMARY",
            "line_send_allowed": safe}


def tw_post_close_archive_quality_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build the exact TW 15:00 presentation projection from one snapshot.

    Archive publication must not reintroduce the older lifecycle renderer after
    a quality-gated post-close replay has selected formal OHLC and frozen
    tactical identities. The projection is derived only from the immutable
    snapshot payload; it neither persists data nor performs any market-data
    lookup.
    """
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else None
    if (
        str(snapshot.get("market") or "") != "TW"
        or str(snapshot.get("window") or snapshot.get("scheduler_window") or "") != "post_close_1500"
        or not isinstance(payload, dict)
        or payload.get("market") not in {None, "TW"}
        or payload.get("window") not in {None, "post_close_1500"}
        or str(payload.get("effective_trading_date") or snapshot.get("effective_trading_date") or "")
           != str(snapshot.get("effective_trading_date") or "")
    ):
        raise ValueError("TW_POST_CLOSE_ARCHIVE_SNAPSHOT_IDENTITY_INVALID")

    # Import here to keep generic US and pre-open dashboard routes independent
    # from this route-specific presentation contract.
    from app.reports.mobile_decision_presentation import post_close_canonical_cards

    cards = post_close_canonical_cards(payload, "TW", "post_close_1500", require_frozen_universe=True)
    gate = batch_gate(cards, market="TW", window="post_close_1500")
    complete_rows = all(
        item.get("actual", {}).get("status") == "AVAILABLE"
        and item.get("direction", {}).get("status") in {"EVALUATED", "NOT_APPLICABLE"}
        and item.get("range", {}).get("status") in {"EVALUATED", "NOT_APPLICABLE"}
        for item in gate["cards"]
    )
    if not gate["line_send_allowed"] or not complete_rows or len(gate["cards"]) != len(cards):
        raise ValueError("TW_POST_CLOSE_ARCHIVE_QUALITY_GATE_BLOCKED")
    by_symbol = {str(item.get("symbol") or ""): item for item in gate["cards"]}
    expected = [str(card.get("symbol") or card.get("stock_id") or "") for card in cards]
    if len(by_symbol) != len(expected) or set(by_symbol) != set(expected):
        raise ValueError("TW_POST_CLOSE_ARCHIVE_QUALITY_CARD_MISMATCH")
    return {
        "schema_version": "tw_post_close_archive_quality_projection_v1",
        "market": "TW",
        "window": "post_close_1500",
        "effective_trading_date": str(snapshot.get("effective_trading_date") or ""),
        "snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "revision": int(snapshot.get("revision") or 1),
        "cards": gate["cards"],
        "quality_by_symbol": by_symbol,
        "status": gate["status"],
    }
