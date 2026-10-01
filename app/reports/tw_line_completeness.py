"""TW notification symbol completeness accounting.

Pure helpers only. They do not send notifications or mutate runtime state.
"""
from __future__ import annotations

import re
from typing import Any


def payload_symbols(payload: dict[str, Any]) -> list[str]:
    values = payload.get("notification_universe") or payload.get("tracking_symbols")
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
    from app.reports.line_chunks import chunk_evidence
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
        **chunk_evidence(content),
        "message_chars": len(content),
        "silent_omission": bool(omitted),
        "complete": not omitted,
    }


def notification_universe_evidence(runtime):
    """Freeze requested symbols and admission reasons, not new analysis cards."""
    rows = runtime.get("historical_symbol_admission") or []
    symbols = [str(r["symbol"]) for r in rows if isinstance(r, dict) and r.get("symbol")]
    return {"notification_universe": list(dict.fromkeys(symbols or runtime.get("tracking_symbols", []))),
            "notification_exclusions": {str(r["symbol"]): str(r.get("exclusion_reason") or "UNAVAILABLE")
                for r in rows if isinstance(r, dict) and r.get("symbol") and r.get("status") != "ADMITTED"}}


def complete_line_universe(content, payload, rendered_symbols):
    """Every requested symbol has either a card or an explicit exclusion."""
    expected = payload_symbols(payload)
    if len(rendered_symbols) != len(set(rendered_symbols)):
        raise ValueError("duplicate_line_symbol")
    exclusions = payload.get("notification_exclusions") or {}
    labels = {"STALE": "歷史資料未更新至應有交易日，未納入本次分析",
              "INSUFFICIENT_LOOKBACK": "歷史資料筆數不足，未納入本次分析"}
    for symbol in expected:
        if symbol not in rendered_symbols:
            reason = exclusions.get(symbol)
            if not reason:
                raise ValueError("unexplained_line_symbol_omission")
            content += "\n" + symbol + "：" + labels.get(reason, "必要歷史資料未通過驗證，未納入本次分析")
    return content
