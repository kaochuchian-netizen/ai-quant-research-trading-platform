"""Canonical structured-review outcomes and deterministic aggregation."""
from __future__ import annotations

from collections import Counter
from typing import Any

CANONICAL_OUTCOMES = ("hit", "fail", "not_triggered", "no_trade", "pending")


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
        item["canonical_outcome"] = normalize_outcome(
            review.get("canonical_outcome"),
            review_status=review.get("review_status"),
            range_covered=review.get("range_covered"),
        )
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
