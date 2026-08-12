#!/usr/bin/env python3
"""AI-DEV-205 executable-governance and readiness semantic matrix."""
from __future__ import annotations

import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.research.tw_production_intelligence_v2 import source_health
from app.runtime.intelligence_quality import (
    coverage_dimension, intelligence_health, intelligence_readiness_v1,
    validate_health_readiness_consistency, validate_intelligence_readiness,
)
from app.runtime.validator_registry import execute_validator_gate, validate_validator_registry
from app.us_stock.institutional_research import build_bundle


def check(name: str, condition: bool, checks: dict[str, bool]) -> None:
    checks[name] = bool(condition)


def entry(validator_id: str, *, required_branch: bool = True, required_post: bool = True,
          status: str = "ACTIVE", role: str = "leaf", path: str | None = None) -> dict:
    row = {
        "validator_id": validator_id, "path": path or f"validators/{validator_id}.py",
        "status": status, "execution_role": role, "scope": "fixture",
        "introduced_by": "AI-DEV-205", "reason": "deterministic fixture",
        "required_in_branch_gate": required_branch, "required_in_post_merge": required_post,
        "last_contract_version": "fixture_v1",
    }
    return row


def fixture_registry(root: Path, rows: list[dict]) -> Path:
    for row in rows:
        path = root / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# deterministic registry fixture\n", encoding="utf-8")
    registry = root / "registry.json"
    registry.write_text(json.dumps({"schema_version": "validator_registry_v2", "version": "fixture", "validators": rows}), encoding="utf-8")
    return registry


def readiness(*, total: int, ready: int, applicability: dict[str, int] | None = None,
              zero_statuses: dict[str, str] | None = None) -> dict:
    decision_rows = [{"required_inputs": {"market_data": True, "technical_evidence": True, "research_evidence": True}} for _ in range(ready)]
    decision_rows += [{"required_inputs": {"market_data": False, "technical_evidence": False, "research_evidence": False}} for _ in range(total - ready)]
    return intelligence_readiness_v1(
        runtime_status="SUCCESS", total_symbols=total, market_ready=ready,
        history_ready=ready, technical_ready=ready, research_ready=ready,
        baseline_prediction_ready=ready, full_prediction_ready=ready,
        decision_required_inputs=decision_rows, applicability=applicability,
        zero_statuses=zero_statuses,
    )


def us_context() -> dict:
    observed = "2026-08-07T20:00:00+08:00"
    return {"items": {ticker: {
        "label": ticker, "ok": True, "last_price": 100 + move,
        "previous_close": 100, "change_pct": move, "error": None,
        "source_timestamp": observed,
        "premarket": {"price": 100 + move, "change_pct": move, "timestamp": observed,
                      "source": "yfinance", "freshness": "fresh", "availability": "available"},
    } for ticker, move in {"SPY": .1, "QQQ": .2, "SOXX": 1.4}.items()}}


def tw_card() -> dict:
    return {
        "symbol": "2330", "trading_date": "2026-08-13", "generated_at": "2026-08-13T07:00:00+08:00",
        "current_price": 100.0, "market_context": {"status": "available"},
        "technical_data": {"history_bars": 20, "history_end": "2026-08-12", "source": "fixture",
                           "source_timestamp": "2026-08-12T13:30:00+08:00",
                           "history_admission": {"admission_success": True}},
        "strategies": {"daily_tactical": {"technical_factors": {
            "history_days": 20, "latest_close": 100.0, "ma5": 101.0, "ma10": 100.0,
            "ma20": 99.0, "atr14": 2.0, "latest_date": "2026-08-12", "source": "fixture",
        }}},
        "entry_readiness": "no_trade", "action": "暫不交易",
    }


def main() -> int:
    checks: dict[str, bool] = {}

    # Executable registry policy and deterministic recursion protection.
    with tempfile.TemporaryDirectory(prefix="ai-dev-205-registry-") as raw:
        root = Path(raw)
        rows = [
            entry("z_leaf"), entry("a_leaf"),
            entry("not_branch", required_branch=False),
            entry("deprecated", required_branch=False, required_post=False, status="DEPRECATED"),
            entry("branch_gate", required_post=False, role="orchestrator"),
            entry("post_merge_status", required_branch=False, role="orchestrator"),
        ]
        registry = fixture_registry(root, rows)
        calls: list[str] = []
        def passing_runner(path: Path) -> dict:
            calls.append(path.stem)
            return {"returncode": 0, "stdout": json.dumps({"status": "PASS"}), "stderr": "", "duration_seconds": .001}
        branch = execute_validator_gate("branch", caller_validator_id="branch_gate", registry_path=registry, root=root, runner=passing_runner)
        post = execute_validator_gate("post_merge", caller_validator_id="post_merge_status", registry_path=registry, root=root, runner=passing_runner)
        check("registry_active_required_executes", branch["executed_validator_ids"] == ["a_leaf", "z_leaf"], checks)
        check("registry_not_required_not_executed", "not_branch" not in branch["selected_validator_ids"], checks)
        check("registry_inactive_not_selected", "deprecated" not in branch["selected_validator_ids"], checks)
        check("registry_deterministic_order", branch["selected_validator_ids"] == ["a_leaf", "branch_gate", "z_leaf"], checks)
        check("branch_recursion_guard", branch["recursion_guard_validator_ids"] == ["branch_gate"] and "validate_ai_branch" not in calls, checks)
        check("post_merge_recursion_guard", post["recursion_guard_validator_ids"] == ["post_merge_status"], checks)
        check("registry_no_unexplained_skip", not branch["unexplained_skipped_validator_ids"] and branch["status"] == "PASS", checks)

        def exception_runner(_path: Path) -> dict:
            raise RuntimeError("fixture")
        exception = execute_validator_gate("branch", caller_validator_id="branch_gate", registry_path=registry, root=root, runner=exception_runner)
        check("registry_exception_fails", exception["status"] == "FAIL" and exception["failed_count"] == 2, checks)

        def exit_runner(path: Path) -> dict:
            return {"returncode": 3 if path.stem == "a_leaf" else 0, "stdout": "{}", "stderr": "fixture"}
        exit_failure = execute_validator_gate("branch", caller_validator_id="branch_gate", registry_path=registry, root=root, runner=exit_runner)
        check("registry_exit_failure_fails", exit_failure["status"] == "FAIL", checks)

        def semantic_runner(path: Path) -> dict:
            payload = {"status": "FAIL"} if path.stem == "z_leaf" else {"status": "PASS"}
            return {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""}
        semantic_failure = execute_validator_gate("branch", caller_validator_id="branch_gate", registry_path=registry, root=root, runner=semantic_runner)
        check("registry_semantic_failure_fails", semantic_failure["status"] == "FAIL", checks)

        missing_rows = [entry("missing", path="validators/missing.py"), entry("branch_gate", required_post=False, role="orchestrator")]
        missing_registry = root / "missing-registry.json"
        missing_registry.write_text(json.dumps({"schema_version":"validator_registry_v2", "version":"fixture", "validators": missing_rows}), encoding="utf-8")
        missing = execute_validator_gate("branch", caller_validator_id="branch_gate", registry_path=missing_registry, root=root, runner=passing_runner)
        check("registry_missing_required_fails", missing["status"] == "FAIL" and "REGISTRY_INVALID" in missing["errors"], checks)

    # Per-dimension applicability and denominator integrity.
    applicable_ready = coverage_dimension(1, 1)
    applicable_missing = coverage_dimension(0, 1)
    not_applicable = coverage_dimension(0, 0)
    not_evaluated = coverage_dimension(0, 0, zero_status="NOT_EVALUATED", reason_codes=["NOT_EVALUATED_IN_RESEARCH_BUNDLE"])
    check("applicable_ready_complete", applicable_ready["status"] == "COMPLETE", checks)
    check("applicable_ready_semantics", applicable_ready["applicability"] == "APPLICABLE", checks)
    check("applicable_missing_none", applicable_missing["status"] == "NONE", checks)
    check("applicable_missing_semantics", applicable_missing["applicability"] == "APPLICABLE", checks)
    check("zero_applicable_not_applicable", not_applicable["status"] == "NOT_APPLICABLE" and not_applicable["applicability"] == "OUT_OF_SCOPE", checks)
    check("zero_applicable_not_evaluated", not_evaluated["status"] == "NOT_EVALUATED" and not_evaluated["coverage_ratio"] is None and not_evaluated["applicability"] == "NOT_EVALUATED", checks)
    try:
        coverage_dimension(1, 0)
        ready_gt_applicable_rejected = False
    except ValueError:
        ready_gt_applicable_rejected = True
    check("ready_greater_than_applicable_rejected", ready_gt_applicable_rejected, checks)
    contradictory = readiness(total=1, ready=0, applicability={"historical_data": 0}, zero_statuses={"historical_data": "NOT_EVALUATED"})
    contradictory["historical_data"]["reason_codes"] = ["INSUFFICIENT_LOOKBACK"]
    check("out_of_scope_reason_contradiction_rejected", "historical_data:OUT_OF_SCOPE_REASON_CONTRADICTION" in validate_intelligence_readiness(contradictory)["reason_codes"], checks)
    applicability_contradiction = readiness(total=1, ready=0, applicability={"historical_data": 0}, zero_statuses={"historical_data": "NOT_EVALUATED"})
    applicability_contradiction["historical_data"]["applicability"] = "OUT_OF_SCOPE"
    check("not_evaluated_out_of_scope_rejected", "historical_data:APPLICABILITY_STATUS_MISMATCH" in validate_intelligence_readiness(applicability_contradiction)["reason_codes"], checks)

    # US research-only bundle: non-consumer dimensions are not evaluated in this bundle.
    observed = "2026-08-07T20:00:00+08:00"
    research = {"sec": {"ok": False}, "official_sources": {}, "fundamentals": {}, "earnings": {}, "material_news": {"items": []}}
    us = build_bundle("NVDA", research, us_context(), observed)
    us_ready = us["intelligence_readiness_v1"]
    for name in ("historical_data", "technical_evidence", "baseline_prediction", "full_prediction", "outcome_evaluation"):
        check(f"us_{name}_not_evaluated", us_ready[name]["status"] == "NOT_EVALUATED" and us_ready[name]["total_applicable_symbols"] == 0 and us_ready[name]["applicability"] == "NOT_EVALUATED", checks)
    check("us_decision_not_evaluated", us_ready["decision_input"]["status"] == "NOT_EVALUATED" and us_ready["decision_input"]["applicability"] == "NOT_EVALUATED", checks)
    check("us_out_of_scope_does_not_degrade", us_ready["overall_intelligence"]["status"] == "READY", checks)
    check("us_prediction_health_truthful", us["intelligence_health"]["prediction_status"] == "NOT_EVALUATED", checks)
    check("us_health_consistency", us["intelligence_health"]["health_readiness_consistency"]["status"] == "PASS", checks)
    check("us_decision_boundary_unchanged", us["decision_context_export"]["trade_action"] is None and us["decision_engine_boundary"]["consumer"] == "existing_decision_engine" and us["decision_engine_boundary"]["trade_action_exported"] is False, checks)

    mutated_health = deepcopy(us["intelligence_health"]); mutated_health["prediction_status"] = "AVAILABLE"
    check("health_not_evaluated_available_rejected", validate_health_readiness_consistency(mutated_health)["status"] == "FAIL", checks)

    full = readiness(total=1, ready=1)
    full_health = intelligence_health(runtime_status="SUCCESS", data_quality_status="HEALTHY", research_status="COMPLETE", prediction_status="AVAILABLE", decision_status="SUFFICIENT", degradation={"status":"HEALTHY", "reason_codes":[]}, readiness=full)
    check("health_actual_prediction_available_pass", full_health["prediction_status"] == "AVAILABLE" and full_health["health_readiness_consistency"]["status"] == "PASS", checks)
    degraded = readiness(total=1, ready=0)
    degraded_health = intelligence_health(runtime_status="SUCCESS", data_quality_status="DEGRADED", research_status="NONE", prediction_status="INSUFFICIENT", decision_status="INSUFFICIENT", degradation={"status":"HEALTHY_WITH_GAPS", "reason_codes":[]}, readiness=degraded)
    check("runtime_success_not_intelligence_success", degraded_health["runtime_status"] == "SUCCESS" and degraded_health["intelligence_status"] == "DEGRADED", checks)

    # TW remains prediction-evaluable and consumes a Decision-owned input declaration.
    tw = source_health([tw_card()])
    check("tw_baseline_prediction_evaluable", tw["intelligence_readiness_v1"]["baseline_prediction"]["status"] == "COMPLETE", checks)
    check("tw_full_prediction_ready", tw["intelligence_readiness_v1"]["full_prediction"]["status"] == "COMPLETE", checks)
    check("tw_decision_contract_owned", tw["intelligence_readiness_v1"]["decision_input"]["required_input_contract_ids"] == ["tw_decision_input_health_contract_v1"], checks)
    check("tw_required_categories_not_score_only", tw["research_readiness"][0]["required_category_ready"] and tw["research_readiness"][0]["ready"], checks)
    for name in ("market_data", "historical_data", "technical_evidence", "research_evidence", "baseline_prediction", "full_prediction", "decision_input"):
        check(f"tw_{name}_applicable_semantics", tw["intelligence_readiness_v1"][name]["applicability"] == "APPLICABLE", checks)

    check("canonical_registry_valid", validate_validator_registry()["status"] == "PASS", checks)
    failures = [name for name, passed in checks.items() if not passed]
    result = {
        "validator": "validate_ai_dev_205_governance_contract_closure_v1",
        "task_id": "AI-DEV-205", "status": "PASS" if not failures else "FAIL",
        "checks": checks, "failures": failures,
        "fixture_class": "SYNTHETIC_UNIT_AND_PRODUCTION_SHAPE_FIXTURE",
        "safety": {"production_pipeline": False, "notifications": False, "trading": False, "writes": "temporary_fixture_only"},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())