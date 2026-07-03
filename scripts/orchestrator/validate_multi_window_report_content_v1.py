#!/usr/bin/env python3
"""Validate AI-DEV-128 multi-window report content contract V1."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.reports.report_sanitizer import sanitize_report_text
from app.reports.window_context import all_window_contexts
REQUIRED_FILES = ["app/reports/window_context.py", "app/reports/report_content_contract.py", "app/reports/report_sanitizer.py", "app/reports/multi_window_formatter.py", "app/reports/report_sections.py", "app/reports/diagnostics_separator.py", "scripts/orchestrator/build_multi_window_report_artifact.py", "scripts/orchestrator/validate_multi_window_report_content_v1.py", "templates/multi_window_report_input.example.json", "templates/multi_window_report_artifact.example.json", "templates/pre_open_report_content.example.md", "templates/intraday_report_content.example.md", "templates/pre_close_report_content.example.md", "templates/post_close_report_content.example.md", "templates/prediction_review_report_content.example.md", "docs/ai_dev_128_multi_window_report_content_contract_v1.md", "docs/runbooks/scheduled_delivery_content_quality_runbook.md"]
RAW_FORBIDDEN = ["Response Code:", "Event Code:", "Event: Session up", "APISUB/", "P2P/", "host '210.59", "SQLite 已寫入", "開始分析股票", "pipeline_report_summary:", "post_close selected stock ids:", "post_close full LINE report disabled", "Traceback (most recent call last):", "Solace"]
def run_builder(window: str) -> dict:
    proc = subprocess.run([sys.executable, "scripts/orchestrator/build_multi_window_report_artifact.py", "--window", window, "--pretty"], cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0: raise RuntimeError(proc.stderr or proc.stdout)
    data = json.loads(proc.stdout)
    if not isinstance(data, dict): raise RuntimeError("builder root must be object")
    return data
def validate_artifact(data: dict, reasons: list[str], window: str) -> None:
    for field in ["schema_version", "generated_at", "input_summary", "window_context", "content_state", "user_facing_report", "diagnostics", "sanitization_summary", "delivery_policy", "safety_summary", "future_integration"]:
        if field not in data: reasons.append(f"{window} missing {field}")
    report = data.get("user_facing_report", {})
    rendered = json.dumps(report, ensure_ascii=False)
    for bad in RAW_FORBIDDEN:
        if bad in rendered: reasons.append(f"{window} user_facing_report leaked raw log: {bad}")
    if window in {"post_close_1500", "prediction_review_1500"} and "】盤前" in rendered:
        reasons.append(f"{window} rendered 盤前 title")
    diag = data.get("diagnostics", {})
    if not isinstance(diag.get("suppressed_log_count"), int) or diag.get("suppressed_log_count", 0) < 5:
        reasons.append(f"{window} diagnostics missing suppression summary")
    if not data.get("delivery_policy", {}).get("line") or not data.get("delivery_policy", {}).get("email") or not data.get("delivery_policy", {}).get("dashboard"):
        reasons.append(f"{window} delivery policy incomplete")
    safety = data.get("safety_summary", {})
    for key in ["line_send", "email_send", "dashboard_production_publish", "production_pipeline_run", "python3_main_py", "secrets_read", "trading_order_portfolio_action"]:
        if safety.get(key) is not False: reasons.append(f"{window} safety {key} must be false")
def validate_docs(reasons: list[str]) -> None:
    text = (ROOT / "docs/ai_dev_128_multi_window_report_content_contract_v1.md").read_text(encoding="utf-8")
    for phrase in ["Purpose", "Incident summary", "Scope", "Non-goals", "Window context model", "User-facing report contract", "Diagnostics contract", "Sanitizer policy", "Multi-window formatter policy", "Post-close / prediction review content states", "Delivery wrapper integration contract", "Validation commands", "Safety boundary", "Rollback plan", "real historical artifact ingestion", "rolling evaluation", "production dashboard publish candidate", "source connector timeout hardening"]:
        if phrase not in text: reasons.append(f"doc missing {phrase}")
    runbook = (ROOT / "docs/runbooks/scheduled_delivery_content_quality_runbook.md").read_text(encoding="utf-8")
    for phrase in ["raw logs leaking", "formatter label is wrong", "user-facing content vs diagnostics", "LINE/Email/Dashboard policies", "not to resend malformed report", "validate sanitized output", "post-incident verification checklist"]:
        if phrase not in runbook: reasons.append(f"runbook missing {phrase}")
def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-128 multi-window report contract."); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args(); reasons: list[str] = []
    for path in REQUIRED_FILES:
        if not (ROOT / path).exists(): reasons.append(f"required file missing: {path}")
    labels = [ctx.display_label for ctx in all_window_contexts()]
    if len(set(labels)) != 5: reasons.append("window labels must be distinct")
    if not all(ctx.advisory_only for ctx in all_window_contexts()): reasons.append("contexts must be advisory_only")
    sanitizer = sanitize_report_text("Response Code: 200\nSQLite 已寫入\n開始分析股票\npipeline_report_summary:\n乾淨內容")
    if "乾淨內容" not in sanitizer.sanitized_text or sanitizer.suppressed_log_count < 4: reasons.append("sanitizer failed raw log suppression sample")
    for window in ["pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500", "prediction_review_1500"]:
        try: validate_artifact(run_builder(window), reasons, window)
        except Exception as exc: reasons.append(f"builder failed for {window}: {exc}")
    try: validate_artifact(json.loads((ROOT / "templates/multi_window_report_artifact.example.json").read_text(encoding="utf-8")), reasons, "template")
    except Exception as exc: reasons.append(f"artifact template invalid: {exc}")
    validate_docs(reasons)
    output = {"ok": True, "passed": not reasons, "windows": [ctx.scheduler_window for ctx in all_window_contexts()], "labels": labels, "reasons": reasons, "side_effects": {"line_sent": False, "email_sent": False, "dashboard_published": False, "production_pipeline_run": False, "python3_main_py": False, "secrets_read": False, "trading_execution": False}}
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True); sys.stdout.write("\n")
    return 0 if output["passed"] else 2
if __name__ == "__main__": raise SystemExit(main())
