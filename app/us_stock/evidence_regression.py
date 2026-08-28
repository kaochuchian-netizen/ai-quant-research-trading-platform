"""Bounded immutable metadata ledger and offline-only evidence attribution tools."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

from app.us_stock.institutional_research import analyze_conflict, analyze_coverage, synthesize

LEDGER_SCHEMA_VERSION = "us_evidence_regression_record_v1"
LEDGER_ROOT = Path("artifacts/runtime/us_stock/evidence_regression_ledger/v1")
MAX_RECORDS_PER_SYMBOL_WINDOW = 64
FORBIDDEN_CONTENT_KEYS = {"article_body", "full_text", "raw_html", "content_body", "transcript"}


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _prediction_identity(symbol: str, window: str, prediction: dict[str, Any]) -> str:
    return "pred_" + stable_hash([symbol, window, prediction])[:24]


def _candidate_records(card: dict[str, Any]) -> list[dict[str, Any]]:
    bundle = card.get("institutional_research") if isinstance(card.get("institutional_research"), dict) else {}
    news = bundle.get("news_intelligence_v2") if isinstance(bundle.get("news_intelligence_v2"), dict) else {}
    funnel = news.get("evidence_funnel") if isinstance(news.get("evidence_funnel"), dict) else {}
    records = funnel.get("candidate_records") if isinstance(funnel.get("candidate_records"), list) else []
    return [dict(item) for item in records[:MAX_RECORDS_PER_SYMBOL_WINDOW] if isinstance(item, dict)]


def build_regression_records(
    *, card: dict[str, Any], runtime_item: dict[str, Any] | None, window: str,
    trading_date: str, generated_at: str,
) -> list[dict[str, Any]]:
    """Create metadata-only records without changing Research or Decision state."""
    runtime_item = runtime_item or {}
    symbol = str(card.get("symbol") or runtime_item.get("symbol") or "").upper()
    bundle = card.get("institutional_research") if isinstance(card.get("institutional_research"), dict) else {}
    research = bundle.get("research_intelligence_v2") if isinstance(bundle.get("research_intelligence_v2"), dict) else {}
    evidence = [item for item in bundle.get("evidence") or [] if isinstance(item, dict)]
    prediction = runtime_item.get("prediction") if isinstance(runtime_item.get("prediction"), dict) else {}
    prediction_id = _prediction_identity(symbol, window, prediction)
    snapshot_identity = "prearchive_" + stable_hash([
        "US", symbol, window, trading_date, bundle.get("research_identity"),
        research.get("window_research_identity"), prediction_id,
    ])[:24]
    selected = {
        str(item.get("news_event_id") or item.get("event_cluster_id")): item
        for item in (bundle.get("news_intelligence_v2") or {}).get("selected_items") or [] if isinstance(item, dict)
    }
    evidence_by_event = {
        str(item.get("news_event_id") or item.get("event_cluster_id")): item
        for item in evidence if item.get("news_event_id") or item.get("event_cluster_id")
    }
    candidates = _candidate_records(card)
    if not candidates:
        candidates = [{
            "candidate_id": item.get("news_id"), "news_event_id": item.get("news_event_id") or item.get("event_cluster_id"),
            "headline": item.get("headline"), "publisher": item.get("publisher"), "published_at": item.get("published_at"),
            "source_reference": item.get("source_reference"), "admission_status": "ADMITTED", "rejection_reason": None,
            "source_quality": item.get("source_quality_tier"), "materiality": item.get("materiality"),
            "relevance": item.get("relevance"), "freshness": item.get("freshness"),
            "entity_attribution": item.get("entity_attribution"),
        } for item in (bundle.get("news_intelligence_v2") or {}).get("items") or [] if isinstance(item, dict)]
    output: list[dict[str, Any]] = []
    for candidate in candidates[:MAX_RECORDS_PER_SYMBOL_WINDOW]:
        event_id = str(candidate.get("news_event_id") or candidate.get("canonical_event_identity") or "")
        evidence_item = evidence_by_event.get(event_id) or {}
        selected_item = selected.get(event_id) or {}
        attribution = candidate.get("entity_attribution") if isinstance(candidate.get("entity_attribution"), dict) else {}
        counted = bool(evidence_item.get("counted_in_synthesis"))
        direction = str(evidence_item.get("direction") or "unavailable")
        role = "NOT_USED"
        if counted:
            role = "SUPPORTING" if direction == "bullish" else "OPPOSING" if direction == "bearish" else "CONTEXT"
        elif selected_item:
            role = "USED"
        record = {
            "record_version": LEDGER_SCHEMA_VERSION, "market": "US", "symbol": symbol, "window": window,
            "trading_date": trading_date, "snapshot_identity": snapshot_identity,
            "snapshot_identity_kind": "canonical_pre_admission_content_identity",
            "candidate_id": candidate.get("candidate_id"), "news_event_id": event_id or None,
            "headline": candidate.get("headline"), "publisher": candidate.get("publisher"),
            "source_reference": candidate.get("source_reference"), "published_at": candidate.get("published_at"),
            "fetched_at": candidate.get("fetched_at") or generated_at,
            "source_tier": candidate.get("source_tier"), "source_quality": candidate.get("source_quality"),
            "primary_subject": attribution.get("primary_subject"), "relationship_type": attribution.get("relationship_type"),
            "related_symbols": attribution.get("related_ticker_metadata") or candidate.get("related_symbols") or [],
            "event_type": candidate.get("event_type") or evidence_item.get("event_type"),
            "materiality": candidate.get("materiality") or evidence_item.get("materiality"),
            "relevance": candidate.get("relevance") or evidence_item.get("relevance"),
            "freshness": candidate.get("freshness") or evidence_item.get("freshness"),
            "admission_status": candidate.get("admission_status"), "rejection_reason": candidate.get("rejection_reason"),
            "duplicate_group": candidate.get("duplicate_group") or event_id or None,
            "canonical_event_identity": event_id or None,
            "research_role": role, "counted_in_synthesis": counted,
            "evidence_id": evidence_item.get("evidence_id"),
            "hypothesis_identity": research.get("hypothesis_identity") or research.get("window_research_identity"),
            "prediction_identity": prediction_id,
            "prediction_direction": (card.get("us_human_decision_summary_v1") or {}).get("direction"),
            "prediction_confidence": card.get("confidence"),
            "prediction_target": (card.get("us_human_decision_summary_v1") or {}).get("forecast_target"),
            "prediction_range": {
                "low": (card.get("us_human_decision_summary_v1") or {}).get("forecast_low"),
                "high": (card.get("us_human_decision_summary_v1") or {}).get("forecast_high"),
            },
            "evaluation_identity": (card.get("prediction_evaluation_v2") or {}).get("evaluation_identity") or (card.get("review") or {}).get("review_identity"),
            "actual_outcome_linkage": card.get("trade_review_outcome") or card.get("prediction_range_result"),
            "technical_baseline": {"status": "DEFERRED_OFFLINE", "live_prediction_unchanged": True},
            "copyright_policy": "metadata_and_derived_summary_only_no_article_body",
        }
        record["record_id"] = "ledger_" + stable_hash(record)[:28]
        output.append(record)
    return output


def validate_regression_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ("record_version", "market", "symbol", "window", "trading_date", "snapshot_identity", "candidate_id", "admission_status", "prediction_identity", "record_id")
    errors.extend(f"missing:{key}" for key in required if not record.get(key))
    if record.get("record_version") != LEDGER_SCHEMA_VERSION or record.get("market") != "US": errors.append("identity")
    if any(key in record for key in FORBIDDEN_CONTENT_KEYS): errors.append("copyright_content")
    if record.get("admission_status") == "REJECTED" and not record.get("rejection_reason"): errors.append("rejected_without_reason")
    if record.get("research_role") not in {"USED", "SUPPORTING", "OPPOSING", "CONTEXT", "NOT_USED"}: errors.append("research_role")
    if record.get("counted_in_synthesis") and not record.get("evidence_id"): errors.append("evidence_linkage")
    expected = "ledger_" + stable_hash({key: value for key, value in record.items() if key != "record_id"})[:28]
    if record.get("record_id") != expected: errors.append("record_identity")
    return sorted(set(errors))


def append_regression_records(records: Iterable[dict[str, Any]], root: Path = LEDGER_ROOT) -> dict[str, Any]:
    """Persist immutable records; replay is idempotent and never rewrites history."""
    written = existing = 0
    for record in records:
        errors = validate_regression_record(record)
        if errors:
            raise ValueError("INVALID_REGRESSION_RECORD:" + ",".join(errors))
        path = root / str(record["trading_date"]) / str(record["window"]) / str(record["symbol"]) / f"{record['record_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError:
            if path.read_text(encoding="utf-8") != payload:
                raise ValueError("IMMUTABLE_LEDGER_IDENTITY_CONFLICT")
            existing += 1
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        written += 1
    return {"schema_version": "us_evidence_regression_append_result_v1", "written": written, "existing": existing, "append_only": True}


def leave_one_out_research(bundle: dict[str, Any], evidence_id: str) -> dict[str, Any]:
    """Offline-only research replay; never changes prediction or Decision outputs."""
    evidence = [dict(item) for item in bundle.get("evidence") or [] if isinstance(item, dict)]
    if not evidence or not evidence_id or not any(item.get("evidence_id") == evidence_id for item in evidence):
        return {"status": "FAIL_CLOSED", "reason": "INSUFFICIENT_REPLAY_INPUTS", "production_applied": False}
    reduced = [item for item in evidence if item.get("evidence_id") != evidence_id]
    knowledge = bundle.get("knowledge") if isinstance(bundle.get("knowledge"), dict) else {"status": "PARTIAL"}
    providers = bundle.get("providers") if isinstance(bundle.get("providers"), list) else []
    before = bundle.get("synthesis") if isinstance(bundle.get("synthesis"), dict) else synthesize(evidence, analyze_coverage(evidence, knowledge, providers), analyze_conflict(evidence))
    coverage = analyze_coverage(reduced, knowledge, providers)
    after = synthesize(reduced, coverage, analyze_conflict(reduced))
    return {
        "schema_version": "us_offline_leave_one_out_v1", "status": "EVALUATED",
        "removed_evidence_id": evidence_id,
        "before": {"research_stance": before.get("research_stance"), "research_confidence": before.get("research_confidence")},
        "after": {"research_stance": after.get("research_stance"), "research_confidence": after.get("research_confidence")},
        "production_applied": False, "weights_modified": False, "prediction_modified": False,
    }
