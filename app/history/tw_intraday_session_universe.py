"""AI-DEV-270E frozen TW 07:00 universe binding for future intraday archival.

All functions are pure/in-memory.  They neither resolve a mutable watchlist nor
write an archive; a later approved 15:00 integration must supply the admitted
07:00 snapshot and explicitly persist only successful immutable artifacts.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Callable

from app.dashboard.market_dashboard_alias import snapshot_parity_contract
from app.dashboard.window_snapshot_archive import admission_errors
from app.history.tw_intraday_1m import SCHEMA_VERSION as INTRADAY_SCHEMA_VERSION

SCHEMA_VERSION = "tw_intraday_session_universe_v1"
MARKET = "TW"
WINDOW = "pre_open_0700"
PLAN_SCHEMA_VERSION = "tw_intraday_1m_collection_plan_v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def normalize_tw_symbol(value: Any) -> str:
    """Preserve the immutable 07:00 numeric identity, including leading zeroes."""
    symbol = str(value).strip()
    if not symbol.isdigit() or len(symbol) not in {4, 5, 6}:
        raise ValueError("TW_UNIVERSE_SYMBOL_INVALID")
    return symbol


def universe_digest(*, trading_session: str, symbols: list[str], source_identity: dict[str, Any]) -> str:
    core = {"schema_version": SCHEMA_VERSION, "market": MARKET, "trading_session": trading_session,
            "symbols": symbols, "source_identity": source_identity}
    return sha256(_canonical_json(core).encode("utf-8")).hexdigest()


def bind_0700_universe(snapshot: dict[str, Any], *, trading_session: str) -> dict[str, Any]:
    """Freeze one admitted natural 07:00 universe; latest aliases are rejected."""
    if not isinstance(snapshot, dict) or admission_errors(snapshot):
        raise ValueError("TW_0700_UNIVERSE_ARTIFACT_MISSING_OR_UNADMITTED")
    identity = snapshot_parity_contract(snapshot)
    if not identity or identity["market"] != MARKET or identity["active_window"] != WINDOW:
        raise ValueError("TW_0700_UNIVERSE_IDENTITY")
    if identity["effective_trading_date"] != trading_session:
        raise ValueError("TW_0700_UNIVERSE_SESSION_MISMATCH")
    payload = snapshot.get("payload")
    symbols = payload.get("tracking_symbols") if isinstance(payload, dict) else None
    if not isinstance(symbols, list) or not symbols:
        raise ValueError("TW_0700_UNIVERSE_SYMBOLS_MISSING")
    normalized = [normalize_tw_symbol(item) for item in symbols]
    if len(normalized) != len(set(normalized)):
        raise ValueError("TW_0700_UNIVERSE_DUPLICATE_SYMBOL")
    source_identity = {"snapshot_id": identity["snapshot_id"], "revision": identity["revision"],
                       "payload_hash": identity["payload_hash"], "source_route": identity["source_route"]}
    return {"schema_version": SCHEMA_VERSION, "market": MARKET, "trading_session": trading_session,
            "symbols": normalized, "symbol_count": len(normalized), "source_0700_identity": source_identity,
            "universe_digest": universe_digest(trading_session=trading_session, symbols=normalized, source_identity=source_identity)}


def validate_bound_universe(value: dict[str, Any], *, trading_session: str) -> dict[str, Any]:
    required = {"schema_version", "market", "trading_session", "symbols", "symbol_count", "source_0700_identity", "universe_digest"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("TW_0700_UNIVERSE_SCHEMA")
    if value["schema_version"] != SCHEMA_VERSION or value["market"] != MARKET or value["trading_session"] != trading_session:
        raise ValueError("TW_0700_UNIVERSE_SESSION_MISMATCH")
    if not isinstance(value["symbols"], list) or value["symbols"] != [normalize_tw_symbol(x) for x in value["symbols"]]:
        raise ValueError("TW_0700_UNIVERSE_SYMBOLS_INVALID")
    if not value["symbols"] or len(value["symbols"]) != len(set(value["symbols"])) or value["symbol_count"] != len(value["symbols"]):
        raise ValueError("TW_0700_UNIVERSE_SYMBOLS_INVALID")
    identity = value["source_0700_identity"]
    if not isinstance(identity, dict) or set(identity) != {"snapshot_id", "revision", "payload_hash", "source_route"}:
        raise ValueError("TW_0700_UNIVERSE_IDENTITY")
    if value["universe_digest"] != universe_digest(trading_session=trading_session, symbols=value["symbols"], source_identity=identity):
        raise ValueError("TW_0700_UNIVERSE_DIGEST_MISMATCH")
    return value


def verify_universe_source(universe: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Fail closed if the supplied 07:00 artifact no longer matches the binding."""
    bound = validate_bound_universe(universe, trading_session=str(universe.get("trading_session") or ""))
    rebuilt = bind_0700_universe(snapshot, trading_session=bound["trading_session"])
    if rebuilt != bound:
        raise ValueError("TW_0700_UNIVERSE_SOURCE_MISMATCH")
    return bound


def build_1500_collection_plan(
    universe: dict[str, Any], *, trading_session: str,
    fetch_rows: Callable[[str, str], list[dict[str, Any]]],
    build_canonical_artifact: Callable[[list[dict[str, Any]], str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Collect every bound symbol in memory and retain terminal evidence for each.

    This is intentionally not an archive writer. A failure is an explicit
    terminal record, never a silent omission or a replacement with a newer
    watchlist.
    """
    bound = validate_bound_universe(universe, trading_session=trading_session)
    records: list[dict[str, Any]] = []
    for symbol in bound["symbols"]:
        try:
            rows = fetch_rows(symbol, trading_session)
        except Exception as exc:
            records.append({"symbol": symbol, "status": "FAILED", "stage": "KBARS_FETCH",
                            "reason_code": "KBARS_FAILURE", "exception_type": type(exc).__name__})
            continue
        try:
            artifact = build_canonical_artifact(rows, symbol, trading_session)
        except Exception as exc:
            records.append({"symbol": symbol, "status": "FAILED", "stage": "CANONICAL_BUILD",
                            "reason_code": "CANONICAL_ARTIFACT_FAILURE", "exception_type": type(exc).__name__})
            continue
        if (not isinstance(artifact, dict) or artifact.get("schema_version") != INTRADAY_SCHEMA_VERSION
                or artifact.get("symbol") != symbol or artifact.get("trading_session") != trading_session):
            records.append({"symbol": symbol, "status": "FAILED", "stage": "CANONICAL_BUILD",
                            "reason_code": "CANONICAL_ARTIFACT_IDENTITY_MISMATCH", "exception_type": None})
            continue
        records.append({"symbol": symbol, "status": "ARTIFACT_READY", "stage": "CANONICAL_BUILD",
                        "artifact_digest": artifact.get("content_hash"), "completeness": artifact.get("completeness"),
                        "artifact": artifact})
    if [row["symbol"] for row in records] != bound["symbols"] or len(records) != bound["symbol_count"]:
        raise ValueError("TW_1500_COLLECTION_SILENT_OMISSION")
    ready = [row for row in records if row["status"] == "ARTIFACT_READY"]
    failed = [row for row in records if row["status"] == "FAILED"]
    return {"schema_version": PLAN_SCHEMA_VERSION, "market": MARKET, "trading_session": trading_session,
            "universe_digest": bound["universe_digest"], "source_0700_identity": bound["source_0700_identity"],
            "expected_symbols": list(bound["symbols"]), "expected_symbol_count": bound["symbol_count"],
            "kbars_success_count": sum(row["stage"] != "KBARS_FETCH" for row in records),
            "artifact_success_count": len(ready), "failed_symbols": [row["symbol"] for row in failed],
            "symbol_coverage": len(ready) / bound["symbol_count"], "terminal_result_coverage": len(records) / bound["symbol_count"],
            "archive_completion": "READY_FOR_EXPLICIT_WRITE" if not failed else "INCOMPLETE_WITH_FAILURE_EVIDENCE",
            "records": records}
