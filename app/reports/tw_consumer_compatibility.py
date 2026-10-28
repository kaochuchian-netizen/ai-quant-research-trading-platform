"""Read-only candidate-consumer deployment gate, never a legacy adapter.

Run from the candidate checkout against an independently pinned copy of today's
Production frozen inputs BEFORE approving source sync. No evaluation/rendering.
"""
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from app.reports.tw_delivery_evaluation import KEY, bind_universe

VERSION = "tw_consumer_deployment_compatibility_v1"


def check_snapshot(snapshot, *, session, expected_snapshot_id):
    """Use exactly the candidate consumer's strict admission (no allow_legacy)."""
    date.fromisoformat(session)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot_id or ""):
        raise ValueError("DEPLOY_EXPECTED_ID_REQUIRED")
    if not isinstance(snapshot, dict) or snapshot.get("snapshot_id") != expected_snapshot_id:
        raise ValueError("DEPLOY_SNAPSHOT_ID_MISMATCH")
    if snapshot.get("market") != "TW" or snapshot.get("window") != "pre_open_0700" or snapshot.get("effective_trading_date") != session:
        raise ValueError("DELIVERY_SNAPSHOT_IDENTITY")
    symbols, _ = bind_universe(snapshot, session=session)
    return symbols


def deployment_preflight(snapshot_root, *, session, expected_snapshot_id, candidate_sha, head_sha):
    """Missing/ambiguous inputs block; never select yesterday or mutable latest.

    The result is not registry success, deployment authorization or an assurance
    about a future changed source. Recheck its raw digest immediately before FF.
    """
    result = {"schema_version": VERSION, "status": "BLOCKED", "session": session,
              "candidate_sha": candidate_sha, "head_sha": head_sha,
              "required_projection": KEY, "registry_gate": "NOT_EXECUTED",
              "production_write": False, "evaluation_executed": False}
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", candidate_sha or "") or candidate_sha != head_sha:
            raise ValueError("DEPLOY_CANDIDATE_SHA_MISMATCH")
        if date.fromisoformat(session).isoformat() != session:
            raise ValueError("DEPLOY_SESSION_INVALID")
        root = Path(snapshot_root).resolve(strict=True)
        folder = root / "tw" / "pre_open_0700" / session
        # All revision candidates matter, including malformed/non-admitted ones;
        # never filter a conflicting revision away to obtain a PASS.
        paths = sorted(folder.glob("revision-*.json"))
        if not paths:
            raise ValueError("DEPLOY_SAME_SESSION_SNAPSHOT_MISSING")
        if len(paths) != 1:
            raise ValueError("DEPLOY_SNAPSHOT_REVISION_AMBIGUOUS")
        path = paths[0]
        if not re.fullmatch(r"revision-[0-9]{4}\.json", path.name):
            raise ValueError("DEPLOY_SNAPSHOT_PATH_INVALID")
        if path.resolve(strict=True) != path or not path.is_file():
            raise ValueError("DEPLOY_SNAPSHOT_SYMLINK_OR_PATH_ESCAPE")
        raw = path.read_bytes()
        snapshot = json.loads(raw)
        symbols = check_snapshot(snapshot, session=session, expected_snapshot_id=expected_snapshot_id)
        if snapshot["revision"] != int(path.stem.split("-")[-1]):
            raise ValueError("DEPLOY_REVISION_PATH_MISMATCH")
        # Detect changes during this read-only check, without locking/writing the
        # Production archive. The operator must repeat the digest check at sync.
        if raw != path.read_bytes():
            raise ValueError("DEPLOY_SOURCE_CHANGED")
        result.update(status="PASS", reason_code=None, snapshot_id=expected_snapshot_id,
                      revision=snapshot["revision"], snapshot_path=str(path),
                      source_sha256=hashlib.sha256(raw).hexdigest(),
                      symbols=symbols, symbol_count=len(symbols))
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
        # Never include raw input or parser messages in terminal diagnostics.
        message = str(exc)
        result["reason_code"] = message if re.fullmatch(r"[A-Z][A-Z0-9_]+", message) else "DEPLOY_INPUT_INVALID_OR_UNREADABLE"
        result["error_type"] = type(exc).__name__
    return result
