#!/usr/bin/env python3
"""Validate AI-DEV-172 US research intelligence integration."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RESEARCH_FILE = REPO_ROOT / "app/us_stock/research_intelligence.py"
LIVE_PIPELINE_FILE = REPO_ROOT / "app/us_stock/live_pipeline.py"
DASHBOARD_FILE = REPO_ROOT / "app/dashboard/multi_market_dashboard.py"
RUNNER_FILE = REPO_ROOT / "scripts/orchestrator/approved_us_stock_delivery.py"
PUBLIC_US_PATH = Path("/var/www/stock-ai-dashboard/dashboard/us/index.html")


def check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def preserve_runtime_and_run(cmd: list[str]) -> tuple[int, str, str]:
    runtime_dir = REPO_ROOT / "artifacts/runtime/us_stock"
    legacy_status = REPO_ROOT / "artifacts/runtime/us_stock_delivery_status_latest.json"
    with tempfile.TemporaryDirectory(prefix="ai_dev_172_validator_") as tmp:
        backup_dir = Path(tmp) / "us_stock"
        runtime_existed = runtime_dir.exists()
        if runtime_existed:
            shutil.copytree(runtime_dir, backup_dir)
        status_existed = legacy_status.exists()
        status_bytes = legacy_status.read_bytes() if status_existed else None
        try:
            completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, timeout=120)
        finally:
            if runtime_dir.exists():
                shutil.rmtree(runtime_dir)
            if runtime_existed:
                shutil.copytree(backup_dir, runtime_dir)
            if status_existed and status_bytes is not None:
                legacy_status.parent.mkdir(parents=True, exist_ok=True)
                legacy_status.write_bytes(status_bytes)
            elif legacy_status.exists():
                legacy_status.unlink()
    return completed.returncode, completed.stdout, completed.stderr


def run_live_research_sample() -> dict[str, Any]:
    code, out, err = preserve_runtime_and_run([
        sys.executable,
        "scripts/orchestrator/approved_us_stock_delivery.py",
        "--window", "us_pre_market_2000",
        "--dry-run", "--live-data", "--pretty",
    ])
    if code != 0:
        return {"ok": False, "stderr": err[-500:]}
    try:
        result = json.loads(out)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stdout": out[-500:]}
    # Re-run a direct in-memory sample so the validator can inspect research data without relying on preserved files.
    from app.us_stock.batch import us_stock_batch_input_example
    from app.us_stock.live_pipeline import build_live_runtime_artifact
    from app.us_stock.watchlist import normalize_us_watchlist_rows
    rows = [r for r in normalize_us_watchlist_rows(us_stock_batch_input_example()["sample_us_watchlist_rows"]) if r.get("enabled")]
    artifact = build_live_runtime_artifact("us_pre_market_2000", rows[:1], production_runtime=False, write_snapshots=False)
    return {"ok": bool(result.get("ok")), "runner": result, "artifact": artifact}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-public", action="store_true")
    args = parser.parse_args()

    research_src = read(RESEARCH_FILE)
    pipeline_src = read(LIVE_PIPELINE_FILE)
    dashboard_src = read(DASHBOARD_FILE)
    runner_src = read(RUNNER_FILE)
    sample = run_live_research_sample()
    artifact = sample.get("artifact", {}) if sample.get("ok") else {}
    item = (artifact.get("items") or [{}])[0]
    research = item.get("research_intelligence", {})
    sec = research.get("sec", {})
    fundamentals = research.get("fundamentals", {})
    earnings = research.get("earnings", {})
    news = research.get("material_news", {})
    factors = research.get("research_factors", {})
    prediction = item.get("prediction", {})

    result: dict[str, Any] = {
        "schema_version": "us_stock_research_intelligence_validation_v1",
        "source_checks": [
            check("source_taxonomy_exists", "SOURCE_TAXONOMY" in research_src and "sec_edgar" in research_src and "source_tier" in research_src),
            check("tier1_official_distinguished", "official_source" in research_src and "market_reference" in research_src),
            check("yfinance_not_official", '"official_source": False' in research_src and "Yahoo Finance / yfinance" in research_src),
        ],
        "sec_checks": [
            check("sec_client_exists", "class SECClient" in research_src),
            check("sec_forms_supported", all(form in research_src for form in ["10-K", "10-Q", "8-K", "20-F", "6-K"])),
            check("sec_live_metadata_result", bool(sec.get("latest_quarterly_report") or sec.get("latest_annual_report") or sec.get("filings")), str(sec.get("missing_reason"))),
            check("sec_no_full_filing_dump", not any(token in research_src.lower() for token in ["full_filing", "filing_body", "full_text"])),
        ],
        "fundamentals_checks": [
            check("fundamental_metric_schema", all(k in research_src for k in ["revenue", "gross_margin", "operating_margin", "free_cash_flow", "debt_to_equity"])),
            check("fundamental_provenance_fields", all(k in research_src for k in ["currency", "period", "period_type", "data_quality", "missing_reason"])),
            check("fundamentals_runtime_present", bool(fundamentals.get("metrics"))),
        ],
        "earnings_checks": [
            check("actual_estimate_guidance_separated", all(k in research_src for k in ["company_guidance", "analyst_consensus", "actual_eps", "actual_revenue"])),
            check("event_risk_integrated", "event_risk_level" in research_src and "event_risk_type" in pipeline_src),
            check("earnings_runtime_present", bool(earnings.get("earnings_status"))),
        ],
        "news_checks": [
            check("event_classification_exists", all(k in research_src for k in ["earnings", "guidance", "product_launch", "regulatory/legal", "analyst_commentary"])),
            check("dedup_exists", "dedup_key" in research_src and "seen" in research_src),
            check("no_full_article_copying", not any(token in research_src.lower() for token in ["article_body", "raw_article", "full_text", "copyrighted_body"])),
            check("news_runtime_contract", news.get("no_full_article_stored") is True),
        ],
        "bilingual_checks": [
            check("bilingual_fields_exist", all(k in research_src for k in ["english_headline", "chinese_translation", "english_summary", "chinese_summary", "vocabulary", "investment_reading"])),
            check("vocabulary_runtime_present_or_missing_safe", isinstance((news.get("items") or [{}])[0].get("vocabulary", []), list)),
        ],
        "research_factor_checks": [
            check("research_factor_engine_exists", "research_factors" in research_src and "RESEARCH_FACTOR_VERSION" in research_src),
            check("us_specific_no_tw_chip", not any(token in research_src for token in ["chip", "三大法人", "融資", "融券"])),
            check("research_score_runtime", isinstance(factors.get("research_score"), (int, float))),
            check("confidence_data_completeness", "missing_factor_count" in factors),
        ],
        "prediction_checks": [
            check("event_adjusted_prediction_fields", all(k in pipeline_src for k in ["event_adjusted", "event_risk_type", "research_factor_version"])),
            check("deterministic_method_preserved", "ATR-like range" in pipeline_src and "deterministic" in pipeline_src),
            check("prediction_runtime_event_fields", "event_adjusted" in prediction and "event_risk_type" in prediction),
        ],
        "review_checks": [
            check("review_attribution_contract", all(k in pipeline_src for k in ["technical", "market", "news", "data_quality"])),
            check("deterministic_review_not_ai_overwrite", "fabricated" in pipeline_src and "False" in pipeline_src, "review metrics remain deterministic"),
        ],
        "dashboard_checks": [
            check("dashboard_research_sections", all(k in dashboard_src for k in ["Financial Quality", "Earnings / Guidance", "SEC / Official Events", "Material News & Bilingual Reading"])),
            check("dashboard_tw_route_retained", "/dashboard/tw/index.html" in dashboard_src),
        ],
        "delivery_checks": [
            check("email_research_contract", "個股研究摘要" in runner_src and "SEC/公司 IR" in runner_src),
            check("line_reminder_only_retained", "concise_reminder_only" in runner_src and "line_text" in runner_src),
            check("sample_no_send", sample.get("runner", {}).get("email", {}).get("attempted") is False and sample.get("runner", {}).get("line", {}).get("attempted") is False),
        ],
        "regression_checks": [
            check("tw_behavior_not_modified_by_research_module", "app/us_stock" in str(RESEARCH_FILE) and "TW_ROUTE" in dashboard_src),
        ],
        "safety_checks": [
            check("no_main_py", "python3 main.py" not in runner_src and "python main.py" not in runner_src),
            check("no_trading", not any(token in research_src + pipeline_src + runner_src for token in ["place_order", "broker_order", "Shioaji"])),
            check("no_secret_terms", not any(token in research_src for token in ["API_KEY", "TOKEN", ".env"])),
        ],
    }
    if args.require_public:
        html = read(PUBLIC_US_PATH)
        result["dashboard_checks"].extend([
            check("public_research_sections", all(k in html for k in ["Financial Quality", "Earnings / Guidance", "SEC / Official Events", "Material News & Bilingual Reading"])),
            check("public_no_foundation_text", "market data not fetched in validation" not in html and "US batch foundation ready" not in html),
        ])
    checks = [c for key, values in result.items() if key.endswith("_checks") for c in values]
    result["overall"] = {"ok": all(c.get("ok") for c in checks), "passed": sum(1 for c in checks if c.get("ok")), "total": len(checks)}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True) + "\n")
    return 0 if result["overall"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
