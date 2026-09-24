"""Pure, offline contract validation. No score calculation, ingestion or writes."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/governance/prediction_regression_data_contract_v1.json"
ENTITIES = {"prediction_snapshot", "feature_snapshot", "market_outcome", "forecast_evaluation",
            "strategy_counterfactual", "finding_ledger", "fix_ledger", "fix_evaluation",
            "daily_scorecard", "report_manifest", "delivery_ledger"}
WEIGHTS = {"prediction": {"trend": 45, "atr_target": 35, "range_coverage": 10, "confidence_calibration": 10},
           "improvement": {"finding_confirmed": 25, "d3_effect": 20, "d10_effect": 40, "non_recurrence": 15},
           "strategy": {"direction_exposure": 25, "opportunity_capture": 25, "risk_avoidance": 25,
                        "entry_hedge_timing": 15, "relative_market": 10},
           "time": {"last_3_sessions": 35, "last_10_sessions": 65},
           "composite": {"prediction": 40, "improvement": 20, "strategy": 40}}
SENSITIVE_KEYS = re.compile(r"^(?:.*(?:secret|password|credential|private_key|access_token|refresh_token|authorization)|raw_payload|raw_rows|positions|holdings|recipient|recipients|email_address)$", re.I)
SENSITIVE_TEXT = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+\S+|\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[A-Z0-9]{16}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", re.I)


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def record_hash(record):
    return hashlib.sha256(canonical_json({k: v for k, v in record.items() if k != "content_hash"}).encode()).hexdigest()


def stamp(record):
    return {**record, "content_hash": record_hash(record)}


def aware(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone_required")
    return parsed


def safety_errors(value, path="$"):
    errors = []
    if isinstance(value, dict):
        for key, item in value.items():
            if SENSITIVE_KEYS.fullmatch(key): errors.append(path + ":prohibited_field")
            errors.extend(safety_errors(item, path + "." + key))
    elif isinstance(value, list):
        for item in value: errors.extend(safety_errors(item, path + "[]"))
    elif isinstance(value, str) and SENSITIVE_TEXT.search(value):
        errors.append(path + ":sensitive_text")
    return errors


def schema_errors(value, schema, path="$"):
    """Validate the deliberately bounded JSON Schema subset used by this contract."""
    errors = []
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    valid = {"null": value is None, "string": isinstance(value, str), "boolean": type(value) is bool,
             "integer": type(value) is int, "number": type(value) in (int, float) and math.isfinite(value),
             "array": isinstance(value, list), "object": isinstance(value, dict)}
    if types and not any(valid.get(t, False) for t in types): return [path + ":type"]
    if "const" in schema and value != schema["const"]: errors.append(path + ":const")
    if "enum" in schema and value not in schema["enum"]: errors.append(path + ":enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0): errors.append(path + ":empty")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value): errors.append(path + ":pattern")
        try:
            if schema.get("format") == "date-time": aware(value)
            if schema.get("format") == "date": date.fromisoformat(value)
        except (TypeError, ValueError): errors.append(path + ":format")
    if type(value) in (float, int):
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf): errors.append(path + ":range")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0): errors.append(path + ":minItems")
        for item in value: errors.extend(schema_errors(item, schema.get("items", {}), path + "[]"))
    if isinstance(value, dict):
        props = schema.get("properties", {})
        errors += [path + ":missing:" + k for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            errors += [path + ":unknown:" + k for k in value if k not in props]
        for k in value.keys() & props.keys(): errors.extend(schema_errors(value[k], props[k], path + "." + k))
    return errors


def contract_errors(contract):
    errors = []
    if contract.get("program_id") != "AI-DEV-251" or contract.get("phase") != "A": errors.append("program_phase")
    if set(contract.get("entities", {})) != ENTITIES: errors.append("entities")
    if contract.get("weights_percent") != WEIGHTS: errors.append("weights")
    for weights in contract.get("weights_percent", {}).values():
        if sum(weights.values()) != 100: errors.append("weight_sum")
    required = {"source", "timezone", "frequency", "historical_range", "join_key", "confidence", "gap", "inventory_ref", "missingness"}
    seen = set()
    for row in contract.get("requirements", []):
        identity = (row.get("market"), row.get("field"))
        if identity in seen: errors.append("duplicate_requirement")
        seen.add(identity)
        if not required <= row.keys(): errors.append("inventory_metadata")
        if row.get("classification") not in {"AVAILABLE", "PARTIAL", "MISSING", "AMBIGUOUS"}: errors.append("classification")
    fields = {"prediction_id", "generated_at", "session", "window", "strategy", "trend", "target_price", "range_low", "range_high",
              "confidence", "technical", "news", "chip", "market_features", "fallback", "missingness", "latency", "feature_as_of",
              "feature_available_at", "atr_at_prediction", "git_sha", "model_version", "schema_version", "realized_prices",
              "subsequent_price_path", "notification_artifacts", "report_artifacts", "finding_tracking", "fix_tracking",
              "benchmark_cost_basis", "trading_calendar"}
    if seen != {(m, f) for m in ("TW", "US") for f in fields}: errors.append("requirements_incomplete")
    for entity in contract.get("entities", {}).values():
        for key in ("canonical_schema_owner", "canonical_storage_owner"):
            if not (ROOT / entity.get(key, "NONEXISTENT")).is_file(): errors.append("canonical_owner_missing")
        schema = entity.get("data_schema", {})
        if not schema.get("required") or schema.get("additionalProperties") is not False: errors.append("open_entity_schema")
    return sorted(set(errors))


def resolve_sessions(report_date, sessions, coverage_through):
    """Select from a caller-supplied authoritative exchange calendar, never guess holidays."""
    cutoff = datetime.combine(date.fromisoformat(report_date), time(17), ZoneInfo("Asia/Taipei"))
    if aware(coverage_through) < cutoff: raise ValueError("calendar_coverage_missing")
    grouped = {"TW": [], "US": []}; seen = set()
    for row in sessions:
        market = row["market"]; identity = (market, row["session_date"])
        if identity in seen or market not in grouped: raise ValueError("calendar_identity")
        seen.add(identity)
        opened, closed = aware(row["open_at"]), aware(row["close_at"])
        zone = ZoneInfo("Asia/Taipei" if market == "TW" else "America/New_York")
        if closed <= opened or opened.astimezone(zone).date().isoformat() != row["session_date"]: raise ValueError("calendar_session")
        if closed <= cutoff: grouped[market].append(row["session_date"])
    return {market: sorted(values)[-1] if values else None for market, values in grouped.items()}


def validate_record(record, contract, history=(), sessions=None):
    errors = schema_errors(record, contract["envelope_schema"]) + safety_errors(record)
    entity = record.get("entity")
    if entity not in contract["entities"]: return sorted(set(errors + ["unknown_entity"]))
    errors += schema_errors(record.get("data"), contract["entities"][entity]["data_schema"], "data")
    if errors: return sorted(set(errors))
    if record["content_hash"] != record_hash(record): errors.append("content_hash")
    if any(r.get("content_hash") != record_hash(r) for r in history): errors.append("history_hash")
    for ref in record["source_refs"]:
        parts = Path(ref["source_path"]).parts
        if ".." in parts or Path(ref["source_path"]).is_absolute() or any(re.search(r"(?:^\.env$|credential|secret|private.key)", part, re.I) for part in parts):
            errors.append("unsafe_source_reference")
    prior = [r for r in history if r["entity"] == entity and r["record_id"] == record["record_id"]]
    same = [r for r in prior if r["revision"] == record["revision"]]
    if same and any(canonical_json(r) != canonical_json(record) for r in same): errors.append("immutable_revision_conflict")
    if record["revision"] == 1:
        if record["supersedes_hash"] is not None: errors.append("unexpected_supersedes")
    else:
        previous = [r for r in prior if r["revision"] == record["revision"] - 1]
        if not previous or record["supersedes_hash"] != previous[0]["content_hash"]: errors.append("revision_predecessor")
    d = record["data"]
    if entity == "feature_snapshot":
        if any(d[k] is None for k in ("as_of", "available_at", "prediction_at")):
            if d["status"] == "ELIGIBLE": errors.append("missing_feature_time")
        elif not aware(d["as_of"]) <= aware(d["available_at"]) <= aware(d["prediction_at"]): errors.append("future_data_leakage")
    if entity == "prediction_snapshot":
        features = [r for r in history if r["entity"] == "feature_snapshot" and r["record_id"] == d["feature_ref"]]
        if d["range_low"] is not None and d["range_high"] is not None and d["range_low"] > d["range_high"]: errors.append("inverted_range")
        if d["status"] == "ELIGIBLE":
            if not features:
                errors.append("feature_binding_missing")
            else:
                feature = features[-1]["data"]
                if any(feature[k] != d[k] for k in ("market", "symbol", "strategy_id", "prediction_id")): errors.append("feature_binding_identity")
                if d["generated_at"] is None or any(feature[k] is None for k in ("prediction_at", "as_of", "available_at")):
                    errors.append("missing_feature_time")
                else:
                    if aware(feature["prediction_at"]) != aware(d["generated_at"]): errors.append("feature_binding_identity")
                    if not aware(feature["as_of"]) <= aware(feature["available_at"]) <= aware(d["generated_at"]): errors.append("future_data_leakage")
            if any(d[k] is None for k in ("generated_at", "target_price", "range_low", "range_high", "confidence", "atr_at_prediction", "reference_price", "git_sha")): errors.append("incomplete_prediction")
            if d["atr_at_prediction"] is not None and d["atr_at_prediction"] <= 0: errors.append("invalid_atr")
            if d["confidence_event"] != "direction_correct" or d["trend"] == "UNKNOWN": errors.append("unmapped_prediction")
    if entity == "market_outcome":
        if any(d[k] is None for k in ("session_close_at", "observed_at", "available_at")):
            if d["status"] == "COMPLETE": errors.append("missing_outcome_time")
        elif not aware(d["session_close_at"]) <= aware(d["observed_at"]) <= aware(d["available_at"]): errors.append("premature_outcome")
        if d["status"] == "COMPLETE" and (any(d[k] is None for k in ("open", "high", "low", "close")) or d["corporate_action_basis"] == "UNKNOWN"): errors.append("incomplete_outcome")
        if all(d[k] is not None for k in ("open", "high", "low", "close")) and not d["low"] <= min(d["open"], d["close"]) <= max(d["open"], d["close"]) <= d["high"]: errors.append("invalid_ohlc")
    if entity == "daily_scorecard":
        all_ready = all(d[k] == "ELIGIBLE" for k in ("prediction_status", "improvement_status", "strategy_status"))
        if not all_ready and (d["composite_status"] != "PENDING" or d["composite_score"] is not None): errors.append("na_requires_pending")
        if d["composite_score"] is not None: errors.append("phase_a_no_scores")
        for key, count in [("three_session_dates", 3), ("ten_session_dates", 10)]:
            if len(d[key]) != len(set(d[key])): errors.append("duplicate_session")
            if all_ready and len(d[key]) != count: errors.append("insufficient_sessions")
    if entity == "fix_evaluation" and d["status"] == "ELIGIBLE" and (d["d3_status"] != "ELIGIBLE" or d["d10_status"] != "ELIGIBLE"):
        errors.append("immature_fix")
    if entity == "fix_ledger" and d["status"] == "IMPLEMENTED" and any(d[k] is None for k in ("approved_at", "effective_at", "change_ref")):
        errors.append("unapproved_fix")
    if entity == "fix_ledger" and d["approved_at"] and d["effective_at"] and not aware(d["proposed_at"]) <= aware(d["approved_at"]) <= aware(d["effective_at"]): errors.append("fix_chronology")
    if entity == "strategy_counterfactual" and set(d["hindsight_evidence_refs"]) & set(d["frozen_signal_refs"]): errors.append("hindsight_feature_overlap")
    if entity == "report_manifest":
        expected = datetime.combine(date.fromisoformat(d["report_date"]), time(17), ZoneInfo("Asia/Taipei"))
        if aware(d["cutoff_at"]) != expected: errors.append("report_cutoff")
        links = [d[k] for k in ("predecessor_report_id", "predecessor_hash", "predecessor_report_date")]
        reports = [r for r in history if r["entity"] == "report_manifest" and r["record_id"] != record["record_id"]]
        if d["chain_status"] == "GENESIS":
            if any(x is not None for x in links) or reports: errors.append("invalid_genesis")
        elif d["chain_status"] == "MISSING_PREDECESSOR":
            if d["status"] != "PENDING" or any(x is not None for x in links): errors.append("missing_predecessor_not_pending")
        else:
            expected_date = (date.fromisoformat(d["report_date"]) - timedelta(days=1)).isoformat()
            matches = [r for r in reports if r["data"]["report_id"] == d["predecessor_report_id"] and r["content_hash"] == d["predecessor_hash"]]
            if d["predecessor_report_date"] != expected_date or not matches or matches[0]["data"]["report_date"] != expected_date: errors.append("report_predecessor")
        if sessions is None:
            errors.append("calendar_required")
        else:
            try:
                actual = resolve_sessions(d["report_date"], sessions, d["calendar_coverage_through"])
                if d["calendar_hash"] != hashlib.sha256(canonical_json(sessions).encode()).hexdigest(): errors.append("calendar_hash")
                if actual != d["market_session_dates"]: errors.append("market_cutoff")
            except (KeyError, ValueError): errors.append("calendar_invalid")
    if entity == "delivery_ledger":
        if not any(r["entity"] == "report_manifest" and r["data"]["report_id"] == d["report_ref"] and r["content_hash"] == d["report_hash"] for r in history): errors.append("delivery_report_binding")
        if d["result"] == "SENT" and not d["receipt_ref"]: errors.append("missing_delivery_receipt")
    return sorted(set(errors))


def document_contract_block(contract):
    """One generated section binds human-readable rules to the JSON authority."""
    digest = hashlib.sha256(canonical_json(contract).encode()).hexdigest()
    lines = ["<!-- BEGIN CANONICAL CONTRACT -->", f"Canonical JSON SHA-256: `{digest}`", "",
             "### Frozen v1 weights (percent)", "", "| Group | Components |", "|---|---|"]
    for group, weights in contract["weights_percent"].items():
        lines.append(f"| {group} | " + ", ".join(f"{k}={v}%" for k, v in weights.items()) + " |")
    lines += ["", "### Canonical ownership (logical views, no parallel raw store)", "", "| Entity | Schema owner | Storage owner | Binding |", "|---|---|---|---|"]
    for name, entity in contract["entities"].items():
        lines.append(f"| {name} | `{entity['canonical_schema_owner']}` | `{entity['canonical_storage_owner']}` | {entity['binding']} |")
    lines += ["", "### Requirement inventory", "", "Counts measure structural presence only. Dates, denominators and missing rates are in the aggregate inventory; metadata and semantic gaps are per field in the JSON contract.", "", "| Market | Field | Classification | Source | Gap |", "|---|---|---|---|---|"]
    for row in contract["requirements"]:
        lines.append(f"| {row['market']} | {row['field']} | {row['classification']} | `{row['source']}` | {row['gap']} |")
    lines += ["", "### Normative policies", ""]
    for key, value in contract["policies"].items():
        lines.append(f"- **{key}**: {', '.join(value) if isinstance(value, list) else value}")
    lines += ["", "<!-- END CANONICAL CONTRACT -->"]
    return "\n".join(lines)
