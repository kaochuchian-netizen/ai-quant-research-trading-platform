"""Immutable daily learning evidence: diagnostic controls only, never model mutation."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from app.evaluation.offline_report_projection import digest
from app.evaluation.prediction_regression_contract import stamp, aware

VERSION = "daily_learning_application_v1"
CONTROL = "FROZEN_FEATURE_AND_HORIZON_PROVENANCE"

def derive(report_date, markets):
    """Create a deterministic proposed learning control from a unified daily review."""
    scope = {}
    for market in ("TW", "US"):
        data = markets.get(market, {})
        diagnostics = data.get("outcome_diagnostics", [])
        unresolved = sorted({d.get("reason") for d in diagnostics if d.get("status") != "RESOLVED" and d.get("reason")})
        scope[market] = {
            "finding": "OUTCOME_EVIDENCE_GAP" if unresolved else "EVIDENCE_CHAIN_OBSERVED",
            "finding_reasons": unresolved,
            "fix": {"id": CONTROL, "state": "PROPOSED_DIAGNOSTIC_CONTROL",
                    "description": "Verify frozen feature provenance and session horizon before retaining native prediction evidence."},
        }
    body = {"schema_version": VERSION, "kind": "DAILY_LEARNING_ARTIFACT", "report_date": report_date,
            "markets": scope, "lifecycle_mutation": False, "model_mutation": False,
            "strategy_mutation": False, "weights_mutation": False}
    body["learning_id"] = digest(body)
    return stamp(body)

def validate(value):
    if not isinstance(value, dict) or value.get("content_hash") != digest({k:v for k,v in value.items() if k != "content_hash"}):
        raise ValueError("LEARNING_DIGEST")
    if value.get("schema_version") != VERSION or value.get("kind") != "DAILY_LEARNING_ARTIFACT" or not value.get("learning_id"):
        raise ValueError("LEARNING_SCHEMA")
    for flag in ("lifecycle_mutation", "model_mutation", "strategy_mutation", "weights_mutation"):
        if value.get(flag) is not False:
            raise ValueError("LEARNING_MUTATION")
    if set(value.get("markets", {})) != {"TW", "US"}:
        raise ValueError("LEARNING_MARKETS")
    return value

def latest(root, market, session_date, frozen_at):
    """Read a prior immutable daily artifact; never use a mutable latest pointer."""
    base = Path(root) / "artifacts/archive/window_snapshots/.daily_evaluation"
    candidates = []
    if not base.exists():
        return None
    for directory in sorted(base.glob("????-??-??"), reverse=True):
        if directory.name >= session_date:
            continue
        for path in sorted(directory.glob("*.json"), reverse=True):
            if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
                continue
            try:
                value = json.loads(path.read_text())
                if value.get("content_hash") != digest({k:v for k,v in value.items() if k != "content_hash"}) or value.get("kind") != "DAILY_EVALUATION":
                    continue
                learning = value.get("learning_artifact")
                validate(learning)
                if value.get("report_date") != directory.name or aware(value.get("canonical_cutoff")) >= aware(frozen_at):
                    continue
                if market not in learning["markets"]:
                    continue
                candidates.append((directory.name, value.get("content_hash"), learning))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue
        if candidates:
            break
    if not candidates:
        return None
    _, parent_hash, learning = min(candidates, key=lambda row:(row[0], row[1]))
    return {"daily_artifact_digest": parent_hash, "learning_digest": learning["content_hash"],
            "learning_id": learning["learning_id"], "report_date": learning["report_date"],
            "market": market, "control": CONTROL}

def apply(reference, *, frozen_at, feature_times, horizon_open):
    """Evidence that a prior diagnostic control was actually applied to this capture."""
    if reference is None:
        return None
    if reference.get("control") != CONTROL or reference.get("market") not in {"TW", "US"}:
        raise ValueError("LEARNING_REFERENCE")
    if not feature_times or any(aware(value) > aware(frozen_at) for value in feature_times):
        raise ValueError("LEARNING_FEATURE_TIME")
    if aware(frozen_at) >= aware(horizon_open):
        raise ValueError("LEARNING_HORIZON")
    return stamp({"schema_version": VERSION, "kind": "LEARNING_USED", "learning_reference": deepcopy(reference),
                  "applied_at": frozen_at, "application": "FROZEN_PROVENANCE_GATE_APPLIED",
                  "controls": {"feature_available_before_freeze": True, "horizon_open_after_freeze": True},
                  "model_mutation": False, "strategy_mutation": False, "weights_mutation": False})


def validate_used(value):
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("content_hash") != digest({k:v for k,v in value.items() if k != "content_hash"}):
        raise ValueError("LEARNING_USED_DIGEST")
    if value.get("schema_version") != VERSION or value.get("kind") != "LEARNING_USED":
        raise ValueError("LEARNING_USED_SCHEMA")
    if value.get("application") != "FROZEN_PROVENANCE_GATE_APPLIED" or value.get("controls") != {"feature_available_before_freeze": True, "horizon_open_after_freeze": True}:
        raise ValueError("LEARNING_USED_CONTROL")
    if any(value.get(flag) is not False for flag in ("model_mutation", "strategy_mutation", "weights_mutation")):
        raise ValueError("LEARNING_USED_MUTATION")
    ref=value.get("learning_reference") or {}
    if ref.get("control") != CONTROL or ref.get("market") not in {"TW", "US"}:
        raise ValueError("LEARNING_USED_REFERENCE")
    return value
