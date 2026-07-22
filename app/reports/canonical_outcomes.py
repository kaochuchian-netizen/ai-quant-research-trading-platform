"""Canonical structured-review outcomes and deterministic aggregation."""
from __future__ import annotations

from collections import Counter
from typing import Any

CANONICAL_OUTCOMES = ("hit", "fail", "not_triggered", "no_trade", "pending")
PREDICTION_RESULTS = ("hit", "miss", "pending")


def prediction_range_result(review: dict[str, Any]) -> str:
    """Return the prediction evaluation without implying a trade outcome."""
    raw = str(review.get("prediction_range_result") or "").strip().lower()
    if raw in PREDICTION_RESULTS:
        return raw
    covered = review.get("range_covered")
    if covered is True:
        return "hit"
    if covered is False:
        return "miss"
    return "pending"


def actual_outcome_evidence(review: dict[str, Any], outcome: str) -> bool:
    """Require explicit outcome evidence; tactical/research labels are never completion evidence."""
    if outcome == "pending":
        return True
    if outcome == "hit":
        return (
            review.get("entry_triggered") is True
            and (review.get("target_outcome") == "hit" or review.get("target_1_hit") is True)
            and review.get("actual_high") is not None
            and review.get("actual_low") is not None
        )
    if outcome == "fail":
        return (
            review.get("entry_triggered") is True
            and (review.get("stop_outcome") == "hit" or review.get("stop_hit") is True or review.get("formal_failure") is True)
            and review.get("actual_high") is not None
            and review.get("actual_low") is not None
        )
    if outcome == "not_triggered":
        return review.get("entry_triggered") is False and review.get("actual_status") == "complete"
    if outcome == "no_trade":
        return review.get("formal_no_trade") is True or review.get("canonical_no_trade_evidence") is True
    return False


def normalize_outcome(value: Any, *, review_status: Any = None, range_covered: Any = None) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"win": "hit", "loss": "fail", "nottriggered": "not_triggered", "waiting": "pending", "unknown": "pending"}
    raw = aliases.get(raw, raw)
    if raw in CANONICAL_OUTCOMES:
        return raw
    status = str(review_status or "").strip().lower()
    if status != "reviewed":
        return "pending"
    if range_covered is True:
        return "hit"
    if range_covered is False:
        return "fail"
    return "pending"


def build_structured_review_cards(cards: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol = {str(item.get("symbol") or item.get("stock_id") or "").upper(): item for item in reviews}
    result = []
    seen: set[str] = set()
    for source in cards:
        symbol = str(source.get("symbol") or source.get("stock_id") or "").upper()
        if not symbol or symbol in seen:
            raise ValueError("duplicate_or_missing_review_symbol")
        seen.add(symbol)
        review = by_symbol.get(symbol, {})
        item = dict(source)
        item["review"] = review
        prediction_result = prediction_range_result(review)
        proposed = normalize_outcome(
            review.get("canonical_outcome"),
            review_status=review.get("review_status"),
            range_covered=review.get("range_covered"),
        )
        item["prediction_range_result"] = prediction_result
        item["trade_outcome"] = proposed if actual_outcome_evidence(review, proposed) else "pending"
        item["canonical_outcome"] = item["trade_outcome"]
        item["outcome_evidence"] = {
            "actual_available": actual_outcome_evidence(review, proposed),
            "prediction_range_result": prediction_result,
            "prediction_snapshot": review.get("snapshot_ref") or review.get("prediction_snapshot_id"),
            "actual_high": review.get("actual_high"), "actual_low": review.get("actual_low"),
            "actual_close": review.get("actual_close"), "range_covered": review.get("range_covered"),
            "pending_reason": review.get("pending_reason") if item["canonical_outcome"] == "pending" else None,
        }
        result.append(item)
    return result


def normalize_review_card(card: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy range-result cards prospectively for presentation."""
    item = dict(card)
    review = item.get("review") if isinstance(item.get("review"), dict) else item
    item["prediction_range_result"] = prediction_range_result(review)
    proposed = normalize_outcome(item.get("trade_outcome") or item.get("canonical_outcome"))
    item["trade_outcome"] = proposed if actual_outcome_evidence(review, proposed) else "pending"
    item["canonical_outcome"] = item["trade_outcome"]
    return item


def aggregate_us_post_close_review(cards: list[dict[str, Any]]) -> dict[str, int]:
    normalized = [normalize_review_card(card) for card in cards]
    trade = aggregate_outcomes(normalized)
    prediction = Counter(card["prediction_range_result"] for card in normalized)
    return {
        "prediction_range_hit_count": prediction["hit"],
        "prediction_range_miss_count": prediction["miss"],
        "prediction_pending_count": prediction["pending"],
        "trade_hit_count": trade["hit_count"],
        "trade_fail_count": trade["fail_count"],
        "trade_not_triggered_count": trade["not_triggered_count"],
        "trade_no_trade_count": trade["no_trade_count"],
        "trade_pending_count": trade["pending_count"],
        "review_card_count": trade["review_card_count"],
        "completed_trade_review_count": trade["completed_review_count"],
        "pending_trade_review_count": trade["pending_review_count"],
        "review_universe_count": trade["review_universe_count"],
    }


def aggregate_outcomes(cards: list[dict[str, Any]]) -> dict[str, int]:
    symbols: set[str] = set()
    outcomes: list[str] = []
    for card in cards:
        symbol = str(card.get("symbol") or card.get("stock_id") or "").upper()
        if not symbol or symbol in symbols:
            raise ValueError("duplicate_or_missing_review_symbol")
        symbols.add(symbol)
        outcome = str(card.get("canonical_outcome") or "")
        if outcome not in CANONICAL_OUTCOMES:
            raise ValueError("missing_or_invalid_canonical_outcome")
        outcomes.append(outcome)
    counts = Counter(outcomes)
    payload = {f"{name}_count": counts[name] for name in CANONICAL_OUTCOMES}
    payload.update({
        "review_card_count": len(cards),
        "completed_review_count": sum(counts[name] for name in CANONICAL_OUTCOMES if name != "pending"),
        "pending_review_count": counts["pending"],
        "review_universe_count": len(cards),
    })
    if sum(payload[f"{name}_count"] for name in CANONICAL_OUTCOMES) != len(cards):
        raise ValueError("review_outcome_count_invariant_failed")
    return payload
