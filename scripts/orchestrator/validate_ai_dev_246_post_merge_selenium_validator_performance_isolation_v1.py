#!/usr/bin/env python3
"""Validate AI-DEV-246 post-merge Selenium isolation and gate ordering."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.validator_registry import execute_validator_gate, load_validator_registry


def _run(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 120) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={**os.environ, **(env or {})},
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_seconds": round(time.monotonic() - started, 4),
    }


def _registry(rows: list[dict[str, Any]], path: Path) -> None:
    path.write_text(
        json.dumps({"schema_version": "validator_registry_v2", "version": "ai-dev-246-test", "validators": rows}),
        encoding="utf-8",
    )


def _entry(validator_id: str, *, path: str, role: str = "leaf") -> dict[str, Any]:
    return {
        "validator_id": validator_id,
        "path": path,
        "status": "ACTIVE",
        "execution_role": role,
        "scope": "ai-dev-246 test",
        "introduced_by": "AI-DEV-246",
        "reason": "test entry",
        "required_in_branch_gate": True,
        "required_in_post_merge": True,
        "last_contract_version": "ai_dev_246_test",
    }


def run_validation() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    import_probe = _run([
        sys.executable,
        "-c",
        (
            "import sys, time; "
            "t=time.monotonic(); "
            "import app.research.tw_news_content_relevance as m; "
            "print({'selenium_loaded': any(k.startswith('selenium') for k in sys.modules), "
            "'duration': round(time.monotonic()-t, 4), "
            "'search_method': m.CNYES_SEARCH_METHOD})"
        ),
    ])
    details["import_probe"] = {
        "returncode": import_probe["returncode"],
        "stdout": import_probe["stdout"].strip(),
        "stderr": import_probe["stderr"].strip()[:500],
        "duration_seconds": import_probe["duration_seconds"],
    }
    checks["cnyes_module_import_does_not_load_selenium"] = (
        import_probe["returncode"] == 0
        and "'selenium_loaded': False" in import_probe["stdout"]
        and "'SELENIUM_BROWSER'" in import_probe["stdout"]
    )

    validator_probe = _run(
        [sys.executable, "scripts/orchestrator/validate_tw_news_content_relevance_materiality_v1.py", "--pretty"],
        env={"STOCK_AI_DISABLE_LIVE_NEWS_NETWORK": "1"},
        timeout=180,
    )
    details["tw_news_validator_offline_probe"] = {
        "returncode": validator_probe["returncode"],
        "duration_seconds": validator_probe["duration_seconds"],
        "stderr": validator_probe["stderr"].strip()[:500],
    }
    try:
        validator_json = json.loads(validator_probe["stdout"])
    except json.JSONDecodeError:
        validator_json = {}
    checks["tw_news_validator_passes_with_live_network_disabled"] = (
        validator_probe["returncode"] == 0
        and validator_json.get("ok") is True
        and validator_json.get("passed_count") == validator_json.get("total_count")
    )

    validator_source = (ROOT / "scripts/orchestrator/validate_tw_news_content_relevance_materiality_v1.py").read_text(encoding="utf-8")
    module_source = (ROOT / "app/research/tw_news_content_relevance.py").read_text(encoding="utf-8")
    checks["tw_news_validator_uses_mock_browser_adapter"] = "class _BrowserAdapter" in validator_source and "webdriver.Chrome" not in validator_source
    checks["cnyes_module_browser_initialization_is_lazy"] = "webdriver.Chrome" not in module_source and "selenium" not in module_source
    checks["cnyes_live_network_kill_switch_exists"] = "STOCK_AI_DISABLE_LIVE_NEWS_NETWORK" in module_source

    required_cnyes_checks = {
        "cnyes_2330_dom_20260917_parsed",
        "cnyes_20260917_within_target_window",
        "cnyes_browser_incremental_scroll_growth",
        "cnyes_article_body_extraction_to_full_content",
        "cnyes_protection_challenge_fail_closed",
        "cnyes_prefetched_full_content_evaluates_without_http_refetch",
    }
    checks["tw_news_validator_retains_cnyes_fixture_coverage"] = all(name in validator_source for name in required_cnyes_checks)

    from app.dashboard.window_snapshot_archive import _normalized_admission_metadata, canonical_snapshot
    from app.us_stock.runtime_provenance import provenance_admission

    sample_archive_item = {
        "schema_version": "window_snapshot_archive_v1",
        "market": "TW",
        "window": "pre_open_0700",
        "effective_trading_date": "2026-09-18",
        "status": "complete",
        "run_kind": "scheduled",
        "generated_at": "2026-09-18T07:00:00+08:00",
        "payload": {
            "window": "pre_open_0700",
            "runtime_provenance": "scheduled_production",
            "admitted": True,
            "cards": [{"symbol": "2330", "title": "fixture"}],
        },
    }
    expected_normalized = canonical_snapshot(sample_archive_item)
    decision = provenance_admission(
        expected_normalized.get("payload"),
        run_kind=str(expected_normalized.get("run_kind") or ""),
    )
    expected_normalized.setdefault("runtime_provenance", decision["runtime_provenance"])
    expected_normalized.setdefault("admission_reason", decision["admission_reason"])
    expected_normalized.setdefault("admitted", decision["admitted"])
    actual_normalized = _normalized_admission_metadata(sample_archive_item)
    checks["archive_normalization_semantics_equivalent"] = actual_normalized == expected_normalized

    registry = load_validator_registry()
    active_post_merge = [
        row["validator_id"]
        for row in registry.get("validators", [])
        if row.get("status") == "ACTIVE" and row.get("required_in_post_merge") is True
    ]
    checks["post_merge_leaf_coverage_includes_ai_dev_246"] = "ai_dev_246_post_merge_selenium_validator_performance_isolation_v1" in active_post_merge
    checks["post_merge_leaf_coverage_keeps_tw_news"] = "tw_news_content_relevance_materiality_v1" in active_post_merge
    checks["post_merge_leaf_coverage_keeps_production_landing"] = "production_landing_integrity" in active_post_merge
    details["post_merge_selected_count"] = len(active_post_merge)

    with tempfile.TemporaryDirectory(prefix="ai-dev-246-registry-") as raw:
        registry_path = Path(raw) / "registry.json"
        rows = [
            _entry("z_last", path="scripts/orchestrator/validate_ai_dev_244_post_merge_validator_performance_timeout_reliability_v1.py"),
            _entry("tw_news_content_relevance_materiality_v1", path="scripts/orchestrator/validate_tw_news_content_relevance_materiality_v1.py"),
            _entry("post_merge_status", path="scripts/orchestrator/validate_post_merge_status.py", role="orchestrator"),
            _entry("production_landing_integrity", path="scripts/orchestrator/validate_production_landing_integrity_v1.py"),
            _entry("a_first", path="scripts/orchestrator/validate_ai_dev_243_known_failure_quarantine_v1.py"),
        ]
        _registry(rows, registry_path)

        def runner(path: Path) -> dict[str, Any]:
            return {"returncode": 0, "stdout": json.dumps({"ok": True}), "stderr": "", "duration_seconds": 0.001}

        gate = execute_validator_gate(
            "post_merge",
            caller_validator_id="post_merge_status",
            registry_path=registry_path,
            root=ROOT,
            runner=runner,
            overall_timeout_seconds=300,
        )
        details["ordering_gate"] = {
            "status": gate.get("status"),
            "selected_validator_ids": gate.get("selected_validator_ids"),
            "executed_validator_ids": gate.get("executed_validator_ids"),
        }
        selected = gate.get("selected_validator_ids", [])
        checks["post_merge_priority_runs_production_landing_before_alpha_tail"] = selected[:2] == [
            "production_landing_integrity",
            "a_first",
        ]
        checks["post_merge_priority_keeps_all_selected_validators"] = set(selected) == {
            "a_first",
            "post_merge_status",
            "production_landing_integrity",
            "tw_news_content_relevance_materiality_v1",
            "z_last",
        }
        checks["post_merge_recursion_guard_unchanged"] = gate.get("recursion_guard_validator_ids") == ["post_merge_status"]
        checks["post_merge_timeout_contract_unchanged"] = gate.get("status") == "PASS" and gate.get("timed_out") is False

    return {
        "schema_version": "ai_dev_246_post_merge_selenium_validator_performance_isolation_v1",
        "ok": all(checks.values()),
        "passed_count": sum(1 for value in checks.values() if value),
        "total_count": len(checks),
        "checks": checks,
        "details": details,
        "safety": {
            "production_rerun": False,
            "cnyes_live_fetch_for_validator": False,
            "line_or_email_sent": False,
            "db_or_sheet_write": False,
            "scheduler_mutation": False,
            "credential_access": False,
            "trading_or_order": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
