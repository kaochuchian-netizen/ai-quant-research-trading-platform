#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, tempfile, sys
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from app.runtime.stage_timing import StageTimingRecorder, TW_INTRADAY_1305_BUDGET

REQUIRED = {"overall_hard_timeout_seconds", "stage_soft_timeout_seconds", "external_request_timeout_seconds", "max_retry_count", "retry_backoff_seconds", "heartbeat_interval_seconds"}

def validate() -> dict:
    checks = []
    budget = TW_INTRADAY_1305_BUDGET
    checks.append(("hard_timeout_not_increased", budget.overall_hard_timeout_seconds == 600))
    checks.append(("external_timeout_bounded", 0 < budget.external_request_timeout_seconds < budget.stage_soft_timeout_seconds))
    checks.append(("retry_bounded", 0 <= budget.max_retry_count <= 2))
    with tempfile.TemporaryDirectory(prefix="ai183-stage-") as tmp:
        path = Path(tmp) / "timing.json"
        recorder = StageTimingRecorder(path, market="TW", window="intraday_1305", run_id="deterministic", budget=budget)
        with recorder.stage("market_data"):
            recorder.heartbeat("market_data", "fixture-free deterministic check")
        failed = recorder.fail(stage="news", category="external_source_timeout", reason="TimeoutError", retry_count=1)
        evidence = json.loads(path.read_text(encoding="utf-8"))
        failure = evidence["failure"]
        checks.extend([
            ("timing_persisted", evidence["stages"][0]["elapsed_seconds"] is not None),
            ("heartbeat_persisted", bool(evidence["last_heartbeat_at"])),
            ("failure_stage_retained", failure["failure_stage"] == "news"),
            ("failure_safe_no_runtime", failure["runtime_persisted"] is False),
            ("failure_safe_no_snapshot", failure["snapshot_admitted"] is False),
            ("failure_safe_no_publish", failure["public_publish_attempted"] is False),
            ("failure_safe_no_delivery", failure["email_attempted"] is failure["line_attempted"] is False),
        ])
    sources = [(REPO_ROOT/path).read_text() for path in (Path("analysis/gemini_client.py"), Path("analysis/news_fetcher.py"), Path("scripts/orchestrator/approved_pre_open_delivery.py"))]
    joined = "\n".join(sources)
    checks.extend([
        ("gemini_timeout_present", "timeout=12_000" in joined),
        ("news_timeout_present", "timeout=8" in joined),
        ("unbuffered_child", 'PYTHONUNBUFFERED' in joined),
        ("no_stale_runtime_fallback", "stale runtime fallback" not in joined.lower()),
    ])
    failures = [name for name, ok in checks if not ok]
    return {"ok": not failures, "checks": [{"name": n, "ok": o} for n, o in checks], "failures": failures, "production_pipeline_executed": False, "notification_attempted": False}

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args=parser.parse_args()
    result=validate(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)); return 0 if result["ok"] else 1
if __name__ == "__main__": raise SystemExit(main())
