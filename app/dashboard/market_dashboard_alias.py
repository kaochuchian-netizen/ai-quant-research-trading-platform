"""Resolve each market Dashboard to one admitted immutable active snapshot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots

WINDOW_ORDER = {
    "TW": {"pre_open_0700": 1, "intraday_1305": 2, "pre_close_1335": 3, "post_close_1500": 4},
    "US": {"us_pre_market_2000": 1, "us_intraday_2300": 2, "us_post_close_review_0630": 3},
}


def payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def resolve_active_snapshot(archive_root: Path, market: str) -> dict[str, Any] | None:
    """Choose the newest trading date, then the latest batch window on that date."""
    candidates: list[dict[str, Any]] = []
    for window in MARKET_WINDOWS.get(market, ()):
        selected = resolve_snapshots(archive_root, market, window)
        if selected.latest:
            candidates.append(selected.latest)
    if not candidates:
        return None
    order = WINDOW_ORDER[market]
    return max(
        candidates,
        key=lambda item: (
            str(item.get("effective_trading_date") or ""),
            order.get(str(item.get("window") or item.get("scheduler_window") or ""), 0),
            int(item.get("revision") or 0),
            str(item.get("revision_created_at") or item.get("generated_at") or ""),
            str(item.get("snapshot_id") or ""),
        ),
    )


def snapshot_parity_contract(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not snapshot:
        return None
    market = str(snapshot.get("market") or "")
    window = str(snapshot.get("window") or snapshot.get("scheduler_window") or "")
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    return {
        "market": market,
        "active_window": window,
        "snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "effective_trading_date": str(snapshot.get("effective_trading_date") or ""),
        "revision": int(snapshot.get("revision") or 1),
        "payload_hash": payload_hash(payload),
        "source_route": f"/dashboard/archive/{market.lower()}/{window}/latest/index.html",
    }


def identity_attributes(snapshot: dict[str, Any] | None) -> str:
    contract = snapshot_parity_contract(snapshot)
    if not contract:
        return 'data-snapshot-state="empty"'
    return " ".join(
        [
            f'data-market="{contract["market"]}"',
            f'data-window="{contract["active_window"]}"',
            f'data-snapshot-id="{contract["snapshot_id"]}"',
            f'data-effective-trading-date="{contract["effective_trading_date"]}"',
            f'data-revision="{contract["revision"]}"',
            f'data-payload-hash="{contract["payload_hash"]}"',
        ]
    )
