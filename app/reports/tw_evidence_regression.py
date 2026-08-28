"""Bounded append-only TW evidence metadata ledger (never a Decision authority)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "tw_evidence_regression_record_v1"
LEDGER_ROOT = Path("artifacts/runtime/tw/evidence_regression_ledger/v1")
MAX_RECORDS_PER_SYMBOL_WINDOW = 64
FORBIDDEN_KEYS = {"article_body", "full_text", "raw_html", "content_body", "transcript"}


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canonical_event_identity(item: dict[str, Any], symbol: str) -> str:
    headline = " ".join(str(item.get("headline") or item.get("title") or "").lower().split())
    for token in ("reuters", "bloomberg", "中央社", "經濟日報", "工商時報", "yahoo", "google news"):
        headline = headline.replace(token, "")
    date_bucket = str(item.get("published_at") or item.get("event_date") or "")[:10]
    facts = item.get("material_facts") if isinstance(item.get("material_facts"), list) else []
    return "tw_event_" + stable_hash([symbol, item.get("event_type") or item.get("event_family"), headline.strip(" -|"), date_bucket, sorted(map(str, facts))])[:24]


def build_regression_records(*, card: dict[str, Any], window: str, trading_date: str, generated_at: str) -> list[dict[str, Any]]:
    symbol = str(card.get("symbol") or card.get("stock_id") or "").zfill(4)
    summary = card.get("tw_human_decision_summary_v1") if isinstance(card.get("tw_human_decision_summary_v1"), dict) else {}
    prediction_id = summary.get("origin_prediction_identity") or "tw_pred_" + stable_hash([symbol, window, trading_date, summary.get("direction"), summary.get("forecast_target")])[:24]
    snapshot = summary.get("current_snapshot_identity") or "tw_prearchive_" + stable_hash([symbol, window, trading_date, prediction_id])[:24]
    candidates = card.get("news_candidate_records") if isinstance(card.get("news_candidate_records"), list) else []
    if not candidates:
        contract = card.get("news_contract") if isinstance(card.get("news_contract"), dict) else {}
        candidates = contract.get("candidate_records") if isinstance(contract.get("candidate_records"), list) else []
    output: list[dict[str, Any]] = []
    for item in candidates[:MAX_RECORDS_PER_SYMBOL_WINDOW]:
        if not isinstance(item, dict): continue
        event_id = item.get("canonical_event_identity") or item.get("canonical_event_id") or canonical_event_identity(item, symbol)
        record = {
            "record_version": SCHEMA_VERSION, "record_kind": "news", "market": "TW", "symbol": symbol,
            "window": window, "trading_date": trading_date, "snapshot_identity": snapshot,
            "candidate_id": item.get("candidate_id") or item.get("news_id") or "candidate_" + stable_hash(item)[:20],
            "news_event_id": event_id, "canonical_event_identity": event_id,
            "publisher": item.get("publisher"), "source_reference": item.get("source_reference") or item.get("source_url"),
            "published_at": item.get("published_at"), "fetched_at": item.get("fetched_at") or generated_at,
            "source_tier": item.get("source_tier"), "source_quality": item.get("source_quality"),
            "primary_subject": item.get("primary_subject"), "relationship_type": item.get("relationship_type") or "unattributed",
            "related_symbols": item.get("related_symbols") or [], "event_type": item.get("event_type"),
            "materiality": item.get("materiality") or "UNKNOWN", "relevance": item.get("relevance") or "UNKNOWN",
            "freshness": item.get("freshness"), "admission_status": item.get("admission_status"),
            "rejection_reason": item.get("rejection_reason"), "duplicate_group": event_id,
            "research_role": item.get("research_role") or "NOT_USED", "counted_in_synthesis": bool(item.get("counted_in_synthesis")),
            "evidence_id": item.get("evidence_id"), "hypothesis_identity": card.get("hypothesis_identity"),
            "prediction_identity": prediction_id, "evaluation_identity": summary.get("evaluation_identity"),
            "copyright_policy": "metadata_and_derived_summary_only_no_article_body",
        }
        record["record_id"] = "tw_ledger_" + stable_hash(record)[:28]
        output.append(record)
    chip = card.get("chip_result") if isinstance(card.get("chip_result"), dict) else card.get("chip_analysis") or {}
    for metric, value in chip.items() if isinstance(chip, dict) else []:
        if metric in {"status", "source", "as_of", "freshness"} or isinstance(value, (dict, list)): continue
        status = str(chip.get(f"{metric}_status") or chip.get("status") or "unavailable")
        record = {
            "record_version": SCHEMA_VERSION, "record_kind": "chip_flow", "market": "TW", "symbol": symbol,
            "window": window, "trading_date": trading_date, "snapshot_identity": snapshot,
            "candidate_id": f"chip:{symbol}:{metric}:{trading_date}:{window}", "admission_status": "ADMITTED" if status not in {"missing", "unavailable"} else "REJECTED",
            "rejection_reason": None if status not in {"missing", "unavailable"} else "source_unavailable",
            "metric": metric, "value": None if status in {"missing", "unavailable"} else value, "status": status,
            "source": chip.get("source"), "as_of": chip.get("as_of"), "freshness": chip.get("freshness"),
            "research_role": "NOT_USED", "counted_in_synthesis": False, "prediction_identity": prediction_id,
            "evaluation_identity": summary.get("evaluation_identity"), "copyright_policy": "structured_market_metadata_only",
        }
        record["record_id"] = "tw_ledger_" + stable_hash(record)[:28]
        output.append(record)
    technical = card.get("technical_data") if isinstance(card.get("technical_data"), dict) else card.get("technical") or {}
    if isinstance(technical, dict) and technical:
        record = {
            "record_version": SCHEMA_VERSION, "record_kind": "technical", "market": "TW", "symbol": symbol,
            "window": window, "trading_date": trading_date, "snapshot_identity": snapshot,
            "candidate_id": f"technical:{symbol}:{trading_date}:{window}", "admission_status": "ADMITTED" if technical.get("analysis_eligible") is True else "REJECTED",
            "rejection_reason": None if technical.get("analysis_eligible") is True else technical.get("missing_reason") or "technical_not_admitted",
            "source": technical.get("source"), "as_of": technical.get("latest_date") or technical.get("as_of"),
            "freshness": technical.get("freshness_status"), "factor_version": technical.get("factor_version") or "existing_tw_technical_contract",
            "evidence_id": technical.get("evidence_id") or "tech_" + stable_hash([symbol, window, technical.get("source"), technical.get("latest_date")])[:20],
            "research_role": "USED" if technical.get("analysis_eligible") is True else "NOT_USED", "counted_in_synthesis": technical.get("analysis_eligible") is True,
            "prediction_identity": prediction_id, "evaluation_identity": summary.get("evaluation_identity"), "copyright_policy": "factor_metadata_only_no_ohlcv_duplication",
        }
        record["record_id"] = "tw_ledger_" + stable_hash(record)[:28]
        output.append(record)
    return output[:MAX_RECORDS_PER_SYMBOL_WINDOW]


def validate_record(record: dict[str, Any]) -> list[str]:
    errors = [f"missing:{key}" for key in ("record_version", "record_kind", "market", "symbol", "window", "trading_date", "snapshot_identity", "candidate_id", "admission_status", "prediction_identity", "record_id") if not record.get(key)]
    if record.get("record_version") != SCHEMA_VERSION or record.get("market") != "TW": errors.append("identity")
    if any(key in record for key in FORBIDDEN_KEYS): errors.append("copyright_content")
    if record.get("admission_status") == "REJECTED" and not record.get("rejection_reason"): errors.append("rejected_without_reason")
    if record.get("record_kind") == "chip_flow" and record.get("status") in {"missing", "unavailable"} and record.get("value") is not None: errors.append("missing_zero_interpreted")
    expected = "tw_ledger_" + stable_hash({key: value for key, value in record.items() if key != "record_id"})[:28]
    if record.get("record_id") != expected: errors.append("record_identity")
    return sorted(set(errors))


def append_records(records: Iterable[dict[str, Any]], root: Path = LEDGER_ROOT) -> dict[str, Any]:
    written = existing = 0
    for record in records:
        errors = validate_record(record)
        if errors: raise ValueError("INVALID_TW_REGRESSION_RECORD:" + ",".join(errors))
        path = root / str(record["trading_date"]) / str(record["window"]) / str(record["symbol"]) / f"{record['record_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        try: descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError:
            if path.read_text(encoding="utf-8") != payload: raise ValueError("IMMUTABLE_TW_LEDGER_IDENTITY_CONFLICT")
            existing += 1; continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle: handle.write(payload)
        written += 1
    return {"schema_version": "tw_evidence_regression_append_result_v1", "written": written, "existing": existing, "append_only": True}
