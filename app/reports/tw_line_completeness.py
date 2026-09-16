"""TW notification symbol completeness accounting.

Pure helpers only. They do not send notifications or mutate runtime state.
"""
from __future__ import annotations

import re
from typing import Any


def payload_symbols(payload: dict[str, Any]) -> list[str]:
    values = payload.get("tracking_symbols")
    if isinstance(values, list) and values:
        return [str(value) for value in values if str(value or "").strip()]
    cards = payload.get("structured_pre_open_cards")
    if not isinstance(cards, list):
        return []
    return [
        str(card.get("symbol") or card.get("stock_id"))
        for card in cards
        if isinstance(card, dict) and str(card.get("symbol") or card.get("stock_id") or "").strip()
    ]


def rendered_symbols_from_text(content: str, expected_symbols: list[str]) -> list[str]:
    rendered: list[str] = []
    for symbol in expected_symbols:
        if re.search(rf"(?<!\d){re.escape(str(symbol))}(?!\d)", content):
            rendered.append(str(symbol))
    return rendered


def build_symbol_delivery_accounting(
    *,
    expected_symbols: list[str],
    rendered_symbols: list[str],
    policy: str,
    channel: str,
    content: str,
) -> dict[str, Any]:
    expected = [str(symbol) for symbol in expected_symbols]
    rendered = [str(symbol) for symbol in rendered_symbols if str(symbol) in set(expected)]
    omitted = [symbol for symbol in expected if symbol not in set(rendered)]
    return {
        "schema_version": "tw_symbol_delivery_accounting_v1",
        "channel": channel,
        "policy": policy,
        "expected_symbols": expected,
        "rendered_symbols": rendered,
        "omitted_symbols": omitted,
        "omission_reasons": {
            symbol: "not_rendered_in_channel_payload"
            for symbol in omitted
        },
        "expected_symbol_count": len(expected),
        "rendered_symbol_count": len(rendered),
        "omitted_symbol_count": len(omitted),
        "message_count": 1,
        "chunk_count": 1,
        "message_chars": len(content),
        "silent_omission": bool(omitted),
        "complete": not omitted,
    }
