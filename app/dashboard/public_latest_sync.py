"""Admission-to-public transaction and identity verification."""
from __future__ import annotations

import json
import fcntl
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .market_dashboard_alias import resolve_active_snapshot, snapshot_parity_contract
from .multi_market_dashboard import publish_archive_latest_route, publish_market_dashboard_alias
from .window_snapshot_archive import resolve_snapshots

REPO_ROOT = Path(__file__).resolve().parents[2]
WINDOW_SNAPSHOT_ARCHIVE = Path(os.environ.get("STOCK_AI_WINDOW_SNAPSHOT_ARCHIVE", REPO_ROOT / "artifacts/archive/window_snapshots"))

IDENTITY_FIELDS = ("market", "window", "effective-trading-date", "snapshot-id", "revision", "payload-hash")


def identity_parity(*identities: dict[str, Any] | None) -> dict[str, Any]:
    """Compare retained source identities without relying on file mtimes."""
    present = [item for item in identities if isinstance(item, dict)]
    fields = ("market", "window", "effective_trading_date", "snapshot_id", "revision", "payload_hash")
    if len(present) != len(identities):
        return {"status": "not_observable", "mismatch_fields": list(fields)}
    mismatch = [field for field in fields if len({str(item.get(field)) for item in present}) != 1]
    return {"status": "verified" if not mismatch else "failed_verification", "mismatch_fields": mismatch}


def expected_latest_identity(market: str, window: str, archive_root: Path | None = None, *, admitted_snapshot: dict[str, Any] | None = None) -> dict[str, Any] | None:
    archive_root = archive_root or WINDOW_SNAPSHOT_ARCHIVE
    latest = admitted_snapshot if admitted_snapshot is not None else resolve_snapshots(archive_root, market.upper(), window).latest
    contract = snapshot_parity_contract(latest)
    if not contract:
        return None
    return {
        "market": contract["market"], "window": contract["active_window"],
        "effective_trading_date": contract["effective_trading_date"],
        "snapshot_id": contract["snapshot_id"], "revision": int(contract["revision"]),
        "payload_hash": contract["payload_hash"],
    }


def observed_html_identity(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    html = path.read_text(encoding="utf-8", errors="replace")
    values: dict[str, Any] = {}
    for field in IDENTITY_FIELDS:
        match = re.search(rf'data-{field}="([^"]*)"', html)
        if match:
            values[field.replace("-", "_")] = match.group(1)
    if "revision" in values:
        try:
            values["revision"] = int(values["revision"])
        except ValueError:
            pass
    return values or None


def verify_identity(expected: dict[str, Any], path: Path) -> dict[str, Any]:
    observed = observed_html_identity(path)
    mismatch = [key for key, value in expected.items() if not observed or observed.get(key) != value]
    return {
        "status": "verified" if not mismatch else "failed_verification",
        "expected_identity": expected, "observed_identity": observed,
        "mismatch_fields": mismatch,
        "verified_at": datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
        "path": str(path),
    }


def synchronize_admitted_latest(*, market: str, window: str, static_root: Path, output_dir: Path) -> dict[str, Any]:
    # Market alias is shared by all windows. Serialize the complete verification
    # and publish transaction, including callers using different build dirs.
    static_root.mkdir(parents=True, exist_ok=True)
    with (static_root / f".publish-{market.lower()}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _synchronize_admitted_latest(market=market, window=window, static_root=static_root, output_dir=output_dir)


def _synchronize_admitted_latest(*, market: str, window: str, static_root: Path, output_dir: Path) -> dict[str, Any]:
    market = market.upper()
    admitted_snapshot = resolve_snapshots(WINDOW_SNAPSHOT_ARCHIVE, market, window).latest
    expected = expected_latest_identity(market, window, admitted_snapshot=admitted_snapshot)
    if not expected:
        return {"status": "not_attempted", "failure_category": "admission_rejected", "reason": "no_admitted_snapshot"}
    build_started = datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()
    archive_path = static_root / f"dashboard/archive/{market.lower()}/{window}/latest/index.html"
    active = resolve_active_snapshot(WINDOW_SNAPSHOT_ARCHIVE, market)
    active_identity = expected_latest_identity(market, window, admitted_snapshot=active) if active else None
    retained_archive = verify_identity(expected, archive_path)
    retained_market = verify_identity(active_identity, static_root / f"dashboard/{market.lower()}/index.html") if active_identity else {}
    if retained_archive.get("status") == retained_market.get("status") == "verified":
        payload = admitted_snapshot.get("payload") or {}
        return {"schema_version":"admission_public_latest_sync_v1", "status":"verified",
                "publish_attempted":False, "idempotency":"already_published",
                "snapshot_id":expected["snapshot_id"], "revision":expected["revision"],
                "source_payload_hash":expected["payload_hash"],
                "rendered_symbols":[str(v) for v in payload.get("tracking_symbols", [])],
                "public_archive_verification":retained_archive, "market_dashboard_verification":retained_market,
                "failure_category":None}
    try:
        archive = publish_archive_latest_route(market, window, static_root=static_root, output_dir=output_dir / "archive")
        market_alias = publish_market_dashboard_alias(market, static_root=static_root, output_dir=output_dir / "market")
    except Exception as exc:
        return {
            "status": "route_build_failure", "failure_category": "route_build_failure",
            "failure_reason_sanitized": exc.__class__.__name__, "started_at": build_started,
        }
    archive_path = static_root / f"dashboard/archive/{market.lower()}/{window}/latest/index.html"
    archive_verification = verify_identity(expected, archive_path)
    active = resolve_active_snapshot(WINDOW_SNAPSHOT_ARCHIVE, market)
    active_expected = snapshot_parity_contract(active)
    active_identity = None if not active_expected else {
        "market": active_expected["market"], "window": active_expected["active_window"],
        "effective_trading_date": active_expected["effective_trading_date"],
        "snapshot_id": active_expected["snapshot_id"], "revision": int(active_expected["revision"]),
        "payload_hash": active_expected["payload_hash"],
    }
    dashboard_verification = verify_identity(active_identity, static_root / f"dashboard/{market.lower()}/index.html") if active_identity else {"status": "not_attempted"}
    status = "verified" if archive_verification["status"] == dashboard_verification["status"] == "verified" else "failed_verification"
    admitted_payload = admitted_snapshot.get("payload") if isinstance(admitted_snapshot, dict) and isinstance(admitted_snapshot.get("payload"), dict) else {}
    rendered_symbols = [str(value) for value in admitted_payload.get("tracking_symbols", [])]
    return {
        "schema_version": "admission_public_latest_sync_v1", "status": status,
        "started_at": build_started,
        "completed_at": datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
        "snapshot_id": expected["snapshot_id"], "revision": expected["revision"],
        "source_payload_hash": expected["payload_hash"],
        # Both rendered routes were verified against the payload hash above;
        # retain the corresponding ordered universe for downstream delivery.
        "rendered_symbols": rendered_symbols,
        "archive_build": archive, "market_dashboard_build": market_alias,
        "public_archive_verification": archive_verification,
        "market_dashboard_verification": dashboard_verification,
        "failure_category": None if status == "verified" else "public_verification_failure",
    }


def write_sync_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
