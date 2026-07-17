"""Full diagnostic provenance consumed by Operations Center summaries."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def build_operations_provenance(*, market: str, window: str, runtime_status: str, runtime_trading_date: str, snapshot: dict[str, Any], public_sync: dict[str, Any], email_result: str, line_result: str) -> dict[str, Any]:
    archive_observed = ((public_sync.get("public_archive_verification") or {}).get("observed_identity"))
    dashboard_observed = ((public_sync.get("market_dashboard_verification") or {}).get("observed_identity"))
    return {
        "schema_version": "operations_window_provenance_v1", "market": market, "window": window,
        "latest_runtime_status": runtime_status, "latest_runtime_trading_date": runtime_trading_date,
        "latest_admitted_snapshot_id": snapshot.get("snapshot_id"),
        "latest_admitted_trading_date": snapshot.get("effective_trading_date"),
        "revision": int(snapshot.get("revision") or 0),
        "payload_hash": (public_sync.get("source_payload_hash") or (public_sync.get("expected_identity") or {}).get("payload_hash")),
        "public_archive_observed_identity": archive_observed,
        "market_dashboard_observed_identity": dashboard_observed,
        "public_parity_status": public_sync.get("status") or "not_attempted",
        "email_delivery_result": email_result, "line_delivery_result": line_result,
    }

def write_operations_provenance(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    temporary.replace(path)
