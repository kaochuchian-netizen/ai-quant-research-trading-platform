#!/usr/bin/env python3
"""Validate AI-DEV-127 production pipeline timeout/stale-process guard V1."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.runtime.production_run_guard import guard_result
from app.runtime.runtime_diagnostics import SCHEMA_VERSION, build_guard_result
from app.runtime.timeout_policy import DEFAULT_TIMEOUT_POLICY, timeout_policy_from_env

REQUIRED_FILES = [
    "app/runtime/__init__.py",
    "app/runtime/process_guard.py",
    "app/runtime/timeout_policy.py",
    "app/runtime/production_run_guard.py",
    "app/runtime/runtime_diagnostics.py",
    "scripts/orchestrator/diagnose_pre_open_runtime_guard.py",
    "scripts/orchestrator/validate_production_pipeline_guard_v1.py",
    "templates/production_pipeline_guard_result.example.json",
    "templates/pre_open_timeout_diagnostic.example.json",
    "docs/ai_dev_127_production_pipeline_timeout_stale_process_guard_v1.md",
    "docs/runbooks/pre_open_delivery_hung_incident_runbook.md",
]

def load_json(path: str) -> dict[str, Any]:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be object")
    return data

def validate_result(payload: dict[str, Any], reasons: list[str], label: str) -> None:
    for field in ["schema_version", "generated_at", "window", "status", "timeout_seconds", "timed_out", "line_attempted", "email_attempted", "dashboard_attempted", "delivery_attempted", "operator_action_required", "diagnostics", "safety_summary"]:
        if field not in payload:
            reasons.append(f"{label} missing {field}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        reasons.append(f"{label} invalid schema_version")
    for field in ["line_attempted", "email_attempted", "dashboard_attempted", "delivery_attempted"]:
        if payload.get(field) is not False:
            reasons.append(f"{label} {field} must be false")
    safety = payload.get("safety_summary", {})
    for key in ["line_send", "email_send", "dashboard_production_publish", "production_publish_allowed", "stale_process_auto_kill", "production_pipeline_run", "python3_main_py", "trading_execution"]:
        if safety.get(key) is not False:
            reasons.append(f"{label} safety {key} must be false")

def validate_docs(reasons: list[str]) -> None:
    text = (ROOT / "docs/ai_dev_127_production_pipeline_timeout_stale_process_guard_v1.md").read_text(encoding="utf-8")
    for phrase in ["Purpose", "Incident summary", "Scope", "Non-goals", "Timeout policy", "Process guard design", "Overlapping run guard", "Stale process detection", "No fresh artifact policy", "logs/daily.log zero-byte diagnostic", "Delivery wrapper behavior on timeout", "Manual incident response procedure", "Validation commands", "Safety boundary", "Rollback plan", "Real Historical Artifact Ingestion", "Source connector live timeout hardening", "Dashboard diagnostics production publish candidate"]:
        if phrase not in text:
            reasons.append(f"doc missing {phrase}")
    runbook = (ROOT / "docs/runbooks/pre_open_delivery_hung_incident_runbook.md").read_text(encoding="utf-8")
    for phrase in ["diagnose", "hung pre_open processes", "capture evidence", "TERM", "when not to KILL", "why not to rerun or resend", "verify no delivery was sent", "verify post-merge status", "escalation"]:
        if phrase not in runbook:
            reasons.append(f"runbook missing {phrase}")

def validate_sources(reasons: list[str]) -> None:
    approved = (ROOT / "scripts/orchestrator/approved_pre_open_delivery.py").read_text(encoding="utf-8")
    for phrase in ["communicate(timeout=policy.production_pipeline_timeout_seconds)", "proc.terminate()", "proc.kill()", "evaluate_pre_open_run_guard", "approved_scheduler_delivery_timed_out_no_delivery", "dashboard_attempted", "email_attempted", "line_attempted"]:
        if phrase not in approved:
            reasons.append(f"approved_pre_open_delivery.py missing {phrase}")
    if "subprocess.run(\n        [python_bin, \"scripts/run_pipeline.py\"" in approved:
        reasons.append("approved_pre_open_delivery.py still has unbounded subprocess.run pipeline call")
    policy = timeout_policy_from_env({})
    if policy.production_pipeline_timeout_seconds != 2700 or policy.external_http_source_timeout_seconds != 15 or policy.market_data_source_timeout_seconds != 20:
        reasons.append("timeout policy defaults invalid")
    guard = guard_result()
    if guard.get("safety_summary", {}).get("stale_process_auto_kill") is not False:
        reasons.append("guard default may auto-kill stale processes")

def validate_diagnose_script(reasons: list[str]) -> None:
    proc = subprocess.run([sys.executable, "scripts/orchestrator/diagnose_pre_open_runtime_guard.py", "--pretty"], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        reasons.append(f"diagnose script failed: {proc.stderr or proc.stdout}")
        return
    try:
        data = json.loads(proc.stdout)
    except Exception as exc:
        reasons.append(f"diagnose script invalid JSON: {exc}")
        return
    if data.get("mode") != "read_only_diagnostics":
        reasons.append("diagnose script must be read-only")
    side = data.get("side_effects", {})
    for key in ["process_killed", "line_sent", "email_sent", "dashboard_published", "production_pipeline_run", "secrets_read"]:
        if side.get(key) is not False:
            reasons.append(f"diagnose script side effect {key} must be false")

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-127 production pipeline guard V1.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    reasons: list[str] = []
    for path in REQUIRED_FILES:
        if not (ROOT / path).exists():
            reasons.append(f"required file missing: {path}")
    try:
        validate_result(load_json("templates/production_pipeline_guard_result.example.json"), reasons, "guard example")
        diag = load_json("templates/pre_open_timeout_diagnostic.example.json")
        if diag.get("side_effects", {}).get("process_killed") is not False:
            reasons.append("diagnostic example must not kill by default")
        if diag.get("production_publish_allowed") is not False:
            reasons.append("diagnostic example production_publish_allowed must be false")
    except Exception as exc:
        reasons.append(f"template validation failed: {exc}")
    timeout_result = build_guard_result("timed_out", "pre_open_0700")
    validate_result(timeout_result, reasons, "generated timeout result")
    for func in [validate_sources, validate_diagnose_script, validate_docs]:
        try:
            func(reasons)
        except Exception as exc:
            reasons.append(f"{func.__name__} failed: {exc}")
    output = {"ok": True, "passed": not reasons, "required_file_count": len(REQUIRED_FILES), "timeout_policy": DEFAULT_TIMEOUT_POLICY.to_dict(), "reasons": reasons, "side_effects": {"production_pipeline_run": False, "python3_main_py": False, "line_sent": False, "email_sent": False, "dashboard_published": False, "secrets_read": False, "trading_execution": False}}
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if output["passed"] else 2
if __name__ == "__main__":
    raise SystemExit(main())
