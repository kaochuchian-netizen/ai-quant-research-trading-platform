"""251C immutable offline projections; no stores, clients or lifecycle actions.

251A envelopes remain unchanged. 251B results are replayed from caller-supplied
synthetic/sanitized aggregate inputs, never inferred from a report's total score.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from app.evaluation.offline_review_evaluators import evaluate_stock, load_contract
from app.evaluation.prediction_regression_contract import (
    aware, canonical_json, record_hash, safety_errors, schema_errors, stamp, validate_record,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/governance/offline_report_projection_contract_v1.json"
REPORT_VERSION = "offline_evaluation_report_v1"
PROJECTION_VERSION = "offline_report_comparison_v1"
CONTRACT_VERSION = "ai_dev_251c_offline_report_projection_v1"
EVALUATOR_VERSION = "ai_dev_251b_offline_evaluators_v1"
IDENTITY_KEYS = ("market", "symbol", "strategy_id", "horizon_sessions")
LEDGER_ENTITIES = {"finding_ledger", "fix_ledger", "fix_evaluation"}
SCORES = ("prediction_accuracy_score", "improvement_accuracy_score", "investment_strategy_score")


class ProjectionError(ValueError):
    """Stable reason codes only; never echo payloads or sensitive values."""


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def contract():
    result = json.loads(CONTRACT_PATH.read_text())
    if result.get("schema_version") != CONTRACT_VERSION:
        raise ProjectionError("CONTRACT_VERSION_MISMATCH")
    return result


def cutoff(report_date):
    return datetime.combine(date.fromisoformat(report_date), time(17), ZoneInfo("Asia/Taipei"))


def reference(report):
    return {key: deepcopy(report[key]) for key in ("report_id", "revision", "schema_version", "content_hash")}


def _inputs(inputs):
    if not isinstance(inputs, dict) or set(inputs) != {"source_kind", "rows", "context"}:
        raise ProjectionError("INPUT_SHAPE")
    if inputs["source_kind"] not in {"SYNTHETIC", "SANITIZED_AGGREGATE"} or safety_errors(inputs):
        raise ProjectionError("INPUT_NOT_ADMITTED")
    context = inputs["context"]
    if not isinstance(context, dict) or set(context) != {*IDENTITY_KEYS, "report_date", "calendar"}:
        raise ProjectionError("CONTEXT_SHAPE")
    if not isinstance(inputs["rows"], list):
        raise ProjectionError("INPUT_SHAPE")
    # Preserve supplied array order and calendar hash; no rewriting inputs.
    result = evaluate_stock(deepcopy(inputs["rows"]), **deepcopy(context))
    return digest(inputs), result


def _records(records, report_date):
    if not isinstance(records, list):
        raise ProjectionError("EVIDENCE_RECORDS_SHAPE")
    a = load_contract()
    unique = {}
    for row in records:
        if not isinstance(row, dict) or row.get("entity") not in LEDGER_ENTITIES:
            raise ProjectionError("EVIDENCE_ENTITY_NOT_ALLOWED")
        errors = validate_record(row, a, history=records)
        if errors:
            raise ProjectionError("EVIDENCE_RECORD_INVALID")
        identity = (row["entity"], row["record_id"], row["revision"])
        if identity in unique and canonical_json(unique[identity]) != canonical_json(row):
            raise ProjectionError("IMMUTABLE_EVIDENCE_CONFLICT")
        unique[identity] = row
        for key, value in row["data"].items():
            if key.endswith("_at") and value is not None and aware(value) > cutoff(report_date):
                raise ProjectionError("FUTURE_LIFECYCLE_EVIDENCE")
    return sorted((deepcopy(row) for row in unique.values()), key=lambda r: (r["entity"], r["record_id"], r["revision"]))


def _shape(report):
    if not isinstance(report, dict) or safety_errors(report):
        raise ProjectionError("REPORT_NOT_ADMITTED")
    if report.get("schema_version") != REPORT_VERSION or report.get("contract_version") != CONTRACT_VERSION or report.get("evaluator_version") != EVALUATOR_VERSION:
        raise ProjectionError("REPORT_VERSION_MISMATCH")
    if schema_errors(report, contract()["report_schema"]):
        raise ProjectionError("REPORT_SCHEMA_INVALID")
    if report["contract_digest"] != digest(contract()):
        raise ProjectionError("CONTRACT_CONTENT_MISMATCH")
    if report["content_hash"] != record_hash(report):
        raise ProjectionError("REPORT_DIGEST_MISMATCH")
    if report["report_id"].lower() == "latest":
        raise ProjectionError("MUTABLE_REPORT_ID")
    if canonical_json(_records(report["evidence_records"], report["report_date"])) != canonical_json(report["evidence_records"]):
        raise ProjectionError("NONCANONICAL_EVIDENCE_ORDER")


def build_report(report_id, inputs, *, revision=1, supersedes_hash=None,
                 evidence_records=(), linkage_refs=None, history=()):
    """Build a separate C artifact, never a scored A-phase daily_scorecard."""
    try:
        input_hash, evaluation = _inputs(inputs)
        context = inputs["context"]
        result = stamp({
            "schema_version": REPORT_VERSION, "contract_version": CONTRACT_VERSION,
            "contract_digest": digest(contract()),
            "evaluator_version": EVALUATOR_VERSION, "report_id": report_id,
            "revision": revision, "supersedes_hash": supersedes_hash,
            "report_date": context["report_date"],
            "identity": {k: context[k] for k in IDENTITY_KEYS},
            "input_digest": input_hash, "evaluation": deepcopy(evaluation),
            "evidence_records": _records(list(evidence_records), context["report_date"]),
            "linkage_refs": deepcopy(linkage_refs) if linkage_refs is not None else {"finding": None, "fix": None, "evaluation": None},
        })
        _shape(result)
        append_report(history, result)
        return result
    except ProjectionError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ProjectionError("INVALID_EVALUATOR_INPUT") from None


def validate_report(report, inputs, history=()):
    _shape(report)
    rebuilt = build_report(report["report_id"], inputs, revision=report["revision"],
                           supersedes_hash=report["supersedes_hash"],
                           evidence_records=report["evidence_records"], linkage_refs=report["linkage_refs"], history=history)
    if canonical_json(rebuilt) != canonical_json(report):
        raise ProjectionError("EVALUATOR_REPLAY_MISMATCH")


def append_report(history, report):
    """Pure append-only history projection for the existing history owner; no I/O."""
    _shape(report)
    rows = {}
    for item in history:
        _shape(item)
        key = (item["report_id"], item["revision"])
        if key in rows and rows[key]["content_hash"] != item["content_hash"]:
            raise ProjectionError("IMMUTABLE_REPORT_CONFLICT")
        rows[key] = deepcopy(item)
    key = (report["report_id"], report["revision"])
    if key in rows:
        if canonical_json(rows[key]) != canonical_json(report):
            raise ProjectionError("IMMUTABLE_REPORT_CONFLICT")
    else:
        rows[key] = deepcopy(report)
    for item in rows.values():
        prior = rows.get((item["report_id"], item["revision"] - 1))
        if item["revision"] == 1:
            if item["supersedes_hash"] is not None:
                raise ProjectionError("UNEXPECTED_SUPERSEDES")
        elif prior is None or item["supersedes_hash"] != prior["content_hash"]:
            raise ProjectionError("REVISION_PREDECESSOR_MISSING")
        elif item["identity"] != prior["identity"] or item["report_date"] != prior["report_date"]:
            raise ProjectionError("REVISION_IDENTITY_CHANGED")
    return [rows[key] for key in sorted(rows)]


def _source_bound(row, target_id, target_hash, target_schema=None):
    return any(ref["source_record_id"] == target_id and ref["content_hash"] == target_hash
               and (target_schema is None or ref["source_schema"] == target_schema) for ref in row["source_refs"])


def evidence_chain(report):
    """Completeness is referential integrity, never success/resolution/permission."""
    by_hash = {r["content_hash"]: r for r in report["evidence_records"]}
    selected = {name: by_hash.get(value) for name, value in report["linkage_refs"].items()}
    reasons = []
    expected = {"finding": "finding_ledger", "fix": "fix_ledger", "evaluation": "fix_evaluation"}
    for name, entity in expected.items():
        row = selected[name]
        if row is None:
            reasons.append("MISSING_" + name.upper())
        elif row["entity"] != entity:
            reasons.append("WRONG_" + name.upper() + "_ENTITY")
        elif any(row["data"][k] != report["identity"][k] for k in ("market", "symbol", "strategy_id")):
            reasons.append("LINK_IDENTITY_MISMATCH")
    if not reasons:
        finding, fix, evaluation = (selected[k] for k in ("finding", "fix", "evaluation"))
        finding_refs = set(finding["data"]["evidence_refs"] + finding["data"]["evaluation_refs"])
        if not finding["data"]["evidence_refs"] or not finding["data"]["evaluation_refs"] or not finding_refs <= {r["source_record_id"] for r in finding["source_refs"]}:
            reasons.append("FINDING_EVIDENCE_MISSING")
        if fix["data"]["finding_ref"] != finding["record_id"] or not _source_bound(fix, finding["record_id"], finding["content_hash"], finding["schema_version"]):
            reasons.append("FINDING_FIX_BINDING_MISMATCH")
        if evaluation["data"]["fix_ref"] != fix["record_id"] or not _source_bound(evaluation, fix["record_id"], fix["content_hash"], fix["schema_version"]):
            reasons.append("FIX_EVALUATION_BINDING_MISMATCH")
        if not _source_bound(evaluation, "evaluation:" + report["report_id"], digest(report["evaluation"]), EVALUATOR_VERSION):
            reasons.append("EVALUATOR_EVIDENCE_BINDING_MISMATCH")
        observed_ids = {r["diagnostics"]["fix_id"] for r in report["evaluation"]["internal_evidence"]["evaluators"]["improvement"]["evidence"].values() if r["status"] == "ELIGIBLE"}
        if observed_ids and observed_ids != {fix["data"]["fix_id"]}:
            reasons.append("EVALUATOR_FIX_IDENTITY_MISMATCH")
    return {"state": "INCOMPLETE" if reasons else "COMPLETE", "reason_codes": sorted(set(reasons)),
            "bindings": deepcopy(report["linkage_refs"]),
            "meaning": "REQUIRED_EVIDENCE_CHAIN_ONLY", "lifecycle_transition": "NONE",
            "success_claim": False, "deployment_permission": False}


def realized_effect(report):
    improvement = report["evaluation"]["internal_evidence"]["evaluators"]["improvement"]
    label = improvement["effect_summary"]["realized_prediction_effect"]
    mapping = contract()["effect_mapping"]
    return {"state": mapping.get(label, "INSUFFICIENT_EVIDENCE"), "source_label": label,
            "source": "251B.improvement.effect_summary.realized_prediction_effect",
            "component_scores": deepcopy(improvement["component_scores"]),
            "effect_summary": deepcopy(improvement["effect_summary"]), "causal_claim": False,
            "explanation": "描述既有離線 evaluator 的樣本效果；不代表 finding 已解決、fix 成功或 production 安全。"}


def _seal_projection(result):
    result = {**result, "contract_digest": digest(contract())}
    sealed = stamp(result)
    key = "rejected_projection_schema" if result["status"] == "REJECTED" else "projection_schema"
    if schema_errors(sealed, contract()[key]):
        raise ProjectionError("PROJECTION_SCHEMA_INVALID")
    return sealed


def compare_reports(current, current_inputs, predecessor=None, predecessor_inputs=None, *, expected_predecessor=None,
                    current_history=(), predecessor_history=()):
    """Fail-closed deterministic comparison with an externally pinned predecessor."""
    try:
        validate_report(current, current_inputs, current_history)
        chain = evidence_chain(current)
        effect = realized_effect(current)
        effect["attribution"] = "LINKED_EVALUATOR_EVIDENCE" if chain["state"] == "COMPLETE" else "EVALUATOR_SAMPLE_ONLY"
        result = {"schema_version": PROJECTION_VERSION, "contract_version": CONTRACT_VERSION,
                  "status": "NO_PREDECESSOR", "reason_codes": ["PREDECESSOR_ABSENT"],
                  "current_ref": reference(current), "predecessor_ref": None,
                  "relationship": "PREVIOUS_CALENDAR_REPORT", "comparison": None,
                  "evidence_chain": chain, "realized_effect": effect,
                  "component_evidence": {"current": deepcopy(current["evaluation"]), "predecessor": None},
                  "linkage_evidence": {"current": deepcopy(current["evidence_records"]), "predecessor": None},
                  "lifecycle_mutation": False, "production_ready": False}
        if predecessor is None:
            if expected_predecessor is not None:
                result["reason_codes"] = ["PINNED_PREDECESSOR_UNAVAILABLE"]
            return _seal_projection(result)
        validate_report(predecessor, predecessor_inputs, predecessor_history)
        if expected_predecessor is None or schema_errors(expected_predecessor, contract()["reference_schema"]):
            raise ProjectionError("PREDECESSOR_PIN_REQUIRED")
        if expected_predecessor != reference(predecessor):
            raise ProjectionError("PREDECESSOR_BINDING_MISMATCH")
        if current["identity"] != predecessor["identity"]:
            raise ProjectionError("COMPARISON_IDENTITY_MISMATCH")
        if date.fromisoformat(predecessor["report_date"]) != date.fromisoformat(current["report_date"]) - timedelta(days=1):
            raise ProjectionError("PREDECESSOR_NOT_PREVIOUS_REPORT_DATE")
        if current["report_id"] == predecessor["report_id"]:
            raise ProjectionError("DAILY_REPORT_ID_REUSED")
        scores = {}
        for key in SCORES:
            before = predecessor["evaluation"]["user_facing"][key]["score"]
            after = current["evaluation"]["user_facing"][key]["score"]
            scores[key] = {"predecessor": before, "current": after,
                           "delta_points": after - before if before is not None and after is not None else None,
                           "status": "COMPARABLE" if before is not None and after is not None else "INSUFFICIENT_EVIDENCE"}
        result.update(status="COMPARABLE" if all(r["status"] == "COMPARABLE" for r in scores.values()) else "INSUFFICIENT_COMPARISON",
                      reason_codes=[] if all(r["status"] == "COMPARABLE" for r in scores.values()) else ["SCORE_EVIDENCE_INCOMPLETE"],
                      predecessor_ref=reference(predecessor), comparison={"scores": scores,
                        "same_market_session": current["evaluation"]["internal_evidence"]["evaluators"]["prediction"]["latest_session"] == predecessor["evaluation"]["internal_evidence"]["evaluators"]["prediction"]["latest_session"],
                        "interpretation": "DESCRIPTIVE_REPORT_DELTA_NOT_CAUSAL_EFFECT"})
        result["component_evidence"]["predecessor"] = deepcopy(predecessor["evaluation"])
        result["linkage_evidence"]["predecessor"] = deepcopy(predecessor["evidence_records"])
        return _seal_projection(result)
    except (ProjectionError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        reason = str(error) if isinstance(error, ProjectionError) else "MALFORMED_PROJECTION_INPUT"
        return _seal_projection({"schema_version": PROJECTION_VERSION, "contract_version": CONTRACT_VERSION,
                      "status": "REJECTED", "reason_codes": [reason], "comparison": None,
                      "lifecycle_mutation": False, "production_ready": False})


def validate_projection(projection, *args, **kwargs):
    """Verify the complete projection by deterministic replay, including components."""
    expected = compare_reports(*args, **kwargs)
    if canonical_json(projection) != canonical_json(expected):
        raise ProjectionError("PROJECTION_REPLAY_MISMATCH")
    return expected["status"] != "REJECTED"
