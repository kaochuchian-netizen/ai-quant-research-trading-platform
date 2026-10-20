"""Snapshot-bound, no-pipeline TW 15:00 reissue presentation.

This module deliberately reads one immutable snapshot.  It neither fetches
market data nor publishes Dashboard files, and its default operation is a
no-send preview.  Transport is delegated to the existing receipt-backed
channel senders only after the caller provides explicit confirmation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.dashboard.market_dashboard_alias import snapshot_parity_contract
from app.reports.channel_delivery_receipt import delivery_identity
from app.reports.mobile_decision_presentation import LINE_REASON_ZH, post_close_line_summary
from app.reports.post_close_quality_gate import evaluate_card

MARKET = "TW"
WINDOW = "post_close_1500"
TRADING_DATE = "2026-10-19"
SNAPSHOT_ID = "0d88522b685531753e76ab92ed7edf2cf12e4f4048dec53d17ce249f1c361056"
REVISION = 1
REISSUE_LABEL = "【2026-10-19 15:00 補發／修正版】"


@dataclass(frozen=True)
class ReissueContent:
    snapshot: dict[str, Any]
    line: str
    email: str
    rows: tuple[dict[str, str], ...]
    summary: dict[str, Any]


def load_bound_snapshot(path: Path) -> dict[str, Any]:
    """Load only the approved immutable 2026-10-19 revision-one snapshot."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    parity = snapshot_parity_contract(value)
    if not parity:
        raise ValueError("REISSUE_SNAPSHOT_PARITY_INVALID")
    if (
        str(value.get("effective_trading_date") or "") != TRADING_DATE
        or str(parity.get("snapshot_id") or "") != SNAPSHOT_ID
        or int(parity.get("revision") or 0) != REVISION
    ):
        raise ValueError("REISSUE_SNAPSHOT_BINDING_MISMATCH")
    payload = value.get("payload")
    if not isinstance(payload, dict) or payload.get("market") not in {None, MARKET}:
        raise ValueError("REISSUE_SNAPSHOT_PAYLOAD_INVALID")
    if payload.get("window") not in {None, WINDOW}:
        raise ValueError("REISSUE_SNAPSHOT_WINDOW_MISMATCH")
    cards = payload.get("structured_review_cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("REISSUE_CARD_UNIVERSE_INVALID")
    return value


def _result_text(component: dict[str, Any], *, dimension: str) -> str:
    result = component.get("result")
    if result == "hit":
        return "符合"
    if result == "partial_hit":
        return "部分符合"
    if result == "miss":
        return "未符合"
    if result == "not_applicable":
        reason = LINE_REASON_ZH.get(component.get("reason_code"), f"未產生{dimension}預測")
        return f"不適用（{reason}）"
    raise ValueError(f"REISSUE_{dimension.upper()}_NOT_ADMITTED")


def canonical_rows(snapshot: dict[str, Any]) -> tuple[dict[str, str], ...]:
    payload = snapshot["payload"]
    cards = payload["structured_review_cards"]
    # Historical post-close snapshots use notification_universe; newer payloads
    # may expose tracking_symbols. Both are frozen in the selected payload.
    universe = payload.get("notification_universe")
    if universe is None:
        universe = payload.get("tracking_symbols")
    expected = [str(item) for item in universe or []]
    if not expected or len(set(expected)) != len(expected):
        raise ValueError("REISSUE_TRACKING_SYMBOLS_INVALID")
    if len(cards) != len(expected):
        raise ValueError("REISSUE_CARD_SYMBOL_IDENTITY_MISMATCH")
    by_symbol = {str(card.get("symbol") or card.get("stock_id") or ""): card for card in cards if isinstance(card, dict)}
    if len(by_symbol) != len(expected) or set(by_symbol) != set(expected):
        raise ValueError("REISSUE_CARD_SYMBOL_IDENTITY_MISMATCH")
    rows: list[dict[str, str]] = []
    for symbol in expected:
        card = by_symbol[symbol]
        quality = evaluate_card(card, market=MARKET, window=WINDOW)
        rows.append({
            "symbol": symbol,
            "name": str(card.get("name") or card.get("stock_name") or ""),
            "direction": _result_text(quality["direction"], dimension="方向"),
            "range": _result_text(quality["range"], dimension="區間"),
        })
    return tuple(rows)


def _summary(cards: list[dict[str, Any]]) -> dict[str, Any]:
    return post_close_line_summary(cards, MARKET, WINDOW)


def _summary_lines(summary: dict[str, Any]) -> list[str]:
    return [
        f"方向：{summary['direction_hit_count']}/{summary['direction_effective_count']} 符合（{summary['direction_hit_rate']}）｜區間：{summary['range_hit_count']}/{summary['range_effective_count']} 符合（{summary['range_hit_rate']}）",
        f"有效樣本：方向 {summary['direction_effective_count']}｜區間 {summary['range_effective_count']}",
    ]


def delivery_identities(prepared: ReissueContent) -> dict[str, dict[str, Any]]:
    """Return per-channel identities without creating receipts or sending."""
    return {
        "line": delivery_identity(snapshot=prepared.snapshot, channel="line", market=MARKET, window=WINDOW, content=prepared.line),
        "email": delivery_identity(snapshot=prepared.snapshot, channel="email", market=MARKET, window=WINDOW, content=prepared.email),
    }


def prepare_reissue(snapshot: dict[str, Any], dashboard_url: str) -> ReissueContent:
    """Render both channels from the same canonical tactical evaluation."""
    # Revalidate when callers pass an in-memory snapshot.
    parity = snapshot_parity_contract(snapshot)
    if not parity or str(parity.get("snapshot_id")) != SNAPSHOT_ID or int(parity.get("revision") or 0) != REVISION:
        raise ValueError("REISSUE_SNAPSHOT_BINDING_MISMATCH")
    payload = snapshot["payload"]
    rows = canonical_rows(snapshot)
    summary = _summary(payload["structured_review_cards"])
    detail = [f"{row['symbol']} {row['name']}｜方向：{row['direction']}｜區間：{row['range']}" for row in rows]
    footer = [f"完整報告：{dashboard_url}", "僅供研究參考，非交易指令。"]
    line = "\n".join([REISSUE_LABEL, "【決策摘要】15:00 台股盤後檢討", *_summary_lines(summary), *detail, *footer])
    email = "\n".join([REISSUE_LABEL, "【Stock AI】15:00 台股盤後檢討", "交易日：2026-10-19", *_summary_lines(summary), *detail, *footer])
    return ReissueContent(snapshot=snapshot, line=line, email=email, rows=rows, summary=summary)
