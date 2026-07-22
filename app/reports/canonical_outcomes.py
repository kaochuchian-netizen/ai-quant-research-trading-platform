"""Canonical structured-review outcomes and deterministic aggregation."""
from __future__ import annotations

from collections import Counter
from typing import Any

CANONICAL_OUTCOMES = ("hit", "fail", "not_triggered", "no_trade", "pending")


def actual_outcome_evidence(review: dict[str, Any], outcome: str) -> bool:
    """Require explicit outcome evidence; tactical/research labels are never completion evidence."""
    if outcome == "pending":
        return True
    if outcome in {"hit", "fail"}:
        return (
            review.get("actual_high") is not None
            and review.get("actual_low") is not None
            and review.get("actual_close") is not None
            and bool(review.get("snapshot_ref") or review.get("prediction_snapshot_id"))
            and isinstance(review.get("range_covered"), bool)
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
        proposed = normalize_outcome(
            review.get("canonical_outcome"),
            review_status=review.get("review_status"),
            range_covered=review.get("range_covered"),
        )
        item["canonical_outcome"] = proposed if actual_outcome_evidence(review, proposed) else "pending"
        item["outcome_evidence"] = {
            "actual_available": actual_outcome_evidence(review, proposed),
            "prediction_snapshot": review.get("snapshot_ref") or review.get("prediction_snapshot_id"),
            "actual_high": review.get("actual_high"), "actual_low": review.get("actual_low"),
            "actual_close": review.get("actual_close"), "range_covered": review.get("range_covered"),
            "pending_reason": review.get("pending_reason") if item["canonical_outcome"] == "pending" else None,
        }
        result.append(item)
    return result


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
