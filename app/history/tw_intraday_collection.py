"""AI-DEV-270F immutable TW 15:00 intraday collection sidecar.

The collector is deliberately independent of prediction evaluation.  It binds
only the admitted *scheduled* 07:00 snapshot for the same session, archives
one v2 evidence artifact or one explicit failure for every bound symbol, and
never resolves a mutable watchlist.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.dashboard.window_snapshot_archive import revisions_for_snapshot
from app.evaluation.session_calendar import load_calendar
from app.history.tw_intraday_1m import (
    SCHEMA_VERSION as INTRADAY_SCHEMA_VERSION,
    archive_artifact,
    build_artifact,
    canonical_json,
    fetch_shioaji_1m_rows,
    replay_artifact,
)
from app.history.tw_intraday_session_universe import (
    bind_0700_universe,
    build_1500_collection_plan,
    verify_universe_source,
)

SCHEMA_VERSION = "tw_intraday_1m_collection_manifest_v1"
MARKET = "TW"
WINDOW = "pre_open_0700"
TZ = ZoneInfo("Asia/Taipei")


def _digest(value: dict[str, Any]) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _manifest_path(root: Path | str, manifest: dict[str, Any]) -> Path:
    return (Path(root) / "tw_intraday" / "1m" / "v2" / manifest["trading_session"]
            / "_manifests" / f"{manifest['content_hash']}.json")


def _source_digest(rows: list[dict[str, Any]]) -> str:
    return sha256(canonical_json({"rows": rows}).encode("utf-8")).hexdigest()


def select_natural_0700_snapshot(snapshot_root: Path | str, *, trading_session: str) -> dict[str, Any]:
    """Select an exact-session scheduled 07:00 snapshot, never a latest alias."""
    candidates = [
        item for item in revisions_for_snapshot(Path(snapshot_root), MARKET, WINDOW, trading_session)
        if item.get("run_kind") == "scheduled"
        and item.get("runtime_provenance") == "scheduled_production"
    ]
    if not candidates:
        raise ValueError("TW_0700_NATURAL_SNAPSHOT_UNAVAILABLE")
    return max(candidates, key=lambda item: (int(item.get("revision") or 0), str(item.get("snapshot_id") or "")))


def _safe_failure(record: dict[str, Any], *, stage: str, reason: str, exc: Exception | None = None) -> dict[str, Any]:
    return {
        "symbol": record["symbol"], "status": "FAILED", "stage": stage,
        "reason_code": reason, "exception_type": type(exc).__name__ if exc else None,
    }


def _provider_revision() -> str:
    try:
        return importlib.metadata.version("shioaji")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def build_collection_manifest(
    universe: dict[str, Any], *, trading_session: str,
    fetch_rows: Callable[[str, str], list[dict[str, Any]]],
    build_canonical_artifact: Callable[[list[dict[str, Any]], str, str], dict[str, Any]],
    archive_root: Path | str | None = None,
    calendar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one terminal record per frozen symbol and optionally archive ready artifacts."""
    plan = build_1500_collection_plan(
        universe, trading_session=trading_session, fetch_rows=fetch_rows,
        build_canonical_artifact=build_canonical_artifact,
    )
    records: list[dict[str, Any]] = []
    for record in plan["records"]:
        if record["status"] != "ARTIFACT_READY":
            records.append({key: value for key, value in record.items() if key != "artifact"})
            continue
        artifact = record["artifact"]
        try:
            if archive_root is None or calendar is None:
                archive_path = None
            else:
                archive_path = archive_artifact(artifact, root=archive_root, calendar=calendar)
        except Exception as exc:
            records.append(_safe_failure(record, stage="ARCHIVE_WRITE", reason="IMMUTABLE_ARCHIVE_FAILURE", exc=exc))
            continue
        ready = {key: value for key, value in record.items() if key != "artifact"}
        ready["archive_path"] = str(archive_path.relative_to(Path(archive_root))) if archive_path else None
        records.append(ready)
    if [item["symbol"] for item in records] != plan["expected_symbols"] or len(records) != plan["expected_symbol_count"]:
        raise ValueError("TW_1500_COLLECTION_SILENT_OMISSION")
    ready = [item for item in records if item["status"] == "ARTIFACT_READY"]
    failed = [item for item in records if item["status"] == "FAILED"]
    core = {
        "schema_version": SCHEMA_VERSION, "market": MARKET, "trading_session": trading_session,
        "source_0700_identity": plan["source_0700_identity"], "universe_digest": plan["universe_digest"],
        "expected_symbols": plan["expected_symbols"], "expected_symbol_count": plan["expected_symbol_count"],
        "kbars_success_count": plan["kbars_success_count"], "artifact_success_count": len(ready),
        "failed_symbols": [item["symbol"] for item in failed],
        "symbol_coverage": len(ready) / plan["expected_symbol_count"],
        "terminal_result_coverage": len(records) / plan["expected_symbol_count"],
        "collection_status": "COMPLETE" if not failed else "PARTIAL",
        "records": records,
    }
    return {**core, "content_hash": _digest(core)}


def archive_collection_manifest(manifest: dict[str, Any], *, root: Path | str) -> Path:
    validate_collection_manifest(manifest)
    target = _manifest_path(root, manifest)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json(manifest) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != encoded:
            raise ValueError("IMMUTABLE_COLLECTION_MANIFEST_COLLISION")
        return target
    temporary = target.with_suffix(".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(target)
    return target


def validate_collection_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "market", "trading_session", "source_0700_identity", "universe_digest",
        "expected_symbols", "expected_symbol_count", "kbars_success_count", "artifact_success_count",
        "failed_symbols", "symbol_coverage", "terminal_result_coverage", "collection_status", "records", "content_hash",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("COLLECTION_MANIFEST_SCHEMA")
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["market"] != MARKET:
        raise ValueError("COLLECTION_MANIFEST_IDENTITY")
    expected = manifest["expected_symbols"]
    records = manifest["records"]
    if (not isinstance(expected, list) or not expected or manifest["expected_symbol_count"] != len(expected)
            or not isinstance(records, list) or [item.get("symbol") for item in records] != expected
            or len(records) != len(expected)):
        raise ValueError("COLLECTION_MANIFEST_COVERAGE")
    if any(item.get("status") not in {"ARTIFACT_READY", "FAILED"} for item in records):
        raise ValueError("COLLECTION_MANIFEST_TERMINAL")
    ready = [item for item in records if item["status"] == "ARTIFACT_READY"]
    failed = [item for item in records if item["status"] == "FAILED"]
    if (manifest["artifact_success_count"] != len(ready) or manifest["failed_symbols"] != [item["symbol"] for item in failed]
            or manifest["kbars_success_count"] < len(ready) or manifest["terminal_result_coverage"] != 1.0
            or manifest["symbol_coverage"] != len(ready) / len(expected)
            or manifest["collection_status"] != ("COMPLETE" if not failed else "PARTIAL")):
        raise ValueError("COLLECTION_MANIFEST_ACCOUNTING")
    if manifest["content_hash"] != _digest({key: value for key, value in manifest.items() if key != "content_hash"}):
        raise ValueError("COLLECTION_MANIFEST_DIGEST")
    return manifest


def replay_collection_manifest(
    *, root: Path | str, snapshot_root: Path | str, trading_session: str,
    content_hash: str, calendar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = Path(root) / "tw_intraday" / "1m" / "v2" / trading_session / "_manifests" / f"{content_hash}.json"
    if not target.is_file():
        raise FileNotFoundError("COLLECTION_MANIFEST_MISSING")
    manifest = validate_collection_manifest(json.loads(target.read_text(encoding="utf-8")))
    if manifest["content_hash"] != content_hash:
        raise ValueError("COLLECTION_MANIFEST_IDENTITY")
    snapshot = select_natural_0700_snapshot(snapshot_root, trading_session=trading_session)
    universe = bind_0700_universe(snapshot, trading_session=trading_session)
    verify_universe_source(universe, snapshot)
    if universe["universe_digest"] != manifest["universe_digest"] or universe["source_0700_identity"] != manifest["source_0700_identity"] or universe["symbols"] != manifest["expected_symbols"]:
        raise ValueError("COLLECTION_MANIFEST_UNIVERSE_MISMATCH")
    calendar = calendar or load_calendar(MARKET)
    for item in manifest["records"]:
        if item["status"] == "ARTIFACT_READY":
            replay_artifact(root=root, trading_session=trading_session, symbol=item["symbol"], content_hash=item["artifact_digest"], calendar=calendar)
    return manifest


def collect_session(
    *, trading_session: str, snapshot_root: Path | str, archive_root: Path | str,
    api: Any | None, available_at: str | None = None, calendar: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    """Production sidecar entrypoint. No prediction/evaluation/delivery mutation."""
    calendar = calendar or load_calendar(MARKET)
    snapshot = select_natural_0700_snapshot(snapshot_root, trading_session=trading_session)
    universe = bind_0700_universe(snapshot, trading_session=trading_session)
    verify_universe_source(universe, snapshot)
    available_at = available_at or datetime.now(TZ).replace(microsecond=0).isoformat()

    def fetch(symbol: str, session: str) -> list[dict[str, Any]]:
        if api is None:
            raise RuntimeError("SHIOAJI_PROVIDER_UNAVAILABLE")
        return fetch_shioaji_1m_rows(api, symbol=symbol, trading_session=session)

    def canonical(rows: list[dict[str, Any]], symbol: str, session: str) -> dict[str, Any]:
        return build_artifact(
            rows, symbol=symbol, trading_session=session, calendar=calendar,
            source={"name": "shioaji_kbars", "revision": _provider_revision(), "source_digest": _source_digest(rows)},
            available_at=available_at,
            provenance={"source_0700_identity": universe["source_0700_identity"], "universe_digest": universe["universe_digest"]},
        )

    manifest = build_collection_manifest(
        universe, trading_session=trading_session, fetch_rows=fetch,
        build_canonical_artifact=canonical, archive_root=archive_root, calendar=calendar,
    )
    return manifest, archive_collection_manifest(manifest, root=archive_root)
