#!/usr/bin/env python3
"""Validate AI-DEV-243 known-failure quarantine governance."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.validator_known_failures import (  # noqa: E402
    KNOWN_FAILURES_PATH,
    classify_known_failure_pair,
    failure_fingerprint_from_output,
    load_known_failures,
    validate_known_failures_config,
)

EXPECTED_FINGERPRINTS = {
    "ai_dev_208_visual_evidence_archive": "12326a1826572a7c27ecea116838be0c012eeb7b7879f2539ad67f41601812a0",
    "ai_dev_209_h2_qualified_news_rre_rendering": "bb8bb8ec310bbccc08fa9579b0b0e76d9a4c425443544ff0139e826d45a75b73",
    "ai_dev_209_h3_user_visible_research_presentation": "49edf6bba36fc0da40e910314b123f5009eea9dfc33b1446a24e38cda7869a0a",
    "ai_dev_210_visual_evidence_pdf_retrieval": "5036a266a68ce554350c0ea015efef57483b6eb670906fe275ad06febddcd372",
    "ai_dev_211_chatgpt_artifact_transport": "4b3628fd36d049346b472474c586d6630f98d5651a758d63928390ea973d00f8",
    "ai_dev_212_h2_research_attribution_finalized_news_counter_argument": "75b6f899522ddc75973cd7fdcdc7dd2bd4efaaaf84e8adb0d8eeb886ef8cc88b",
    "ai_dev_212_research_semantic_visual_integrity": "2c13de744414fd41b10958a72c1393c2d6a4fcba40e44f49ec7d740203910a3d",
    "ai_dev_217_tw_prediction_news_continuity": "343cf94fa2b429592e439815d2dc44735c176a1190652faa1c1f6ceebeadac14",
    "ai_dev_218a_tw_preopen_product_intelligence": "d13e6df1ac5880c79ed740da367bc4ee9571db0cf619b1bd3c96f155ca19ff50",
    "ai_dev_218b_tw_preopen_news_readability_v1": "21eae368bd0c063313b1b41953f80ad7aade420e7afde130bf11041d93eb73a2",
}


def _classify(base_pass: bool, head_pass: bool, base_fp: str | None, head_fp: str | None, entries: list[dict]) -> dict:
    return classify_known_failure_pair(
        validator_id="ai_dev_218a_tw_preopen_product_intelligence",
        base_pass=base_pass,
        head_pass=head_pass,
        base_fingerprint=base_fp,
        head_fingerprint=head_fp,
        entries=entries,
    )


def _write_config(entries: list[dict]) -> Path:
    root = Path(tempfile.mkdtemp(prefix="ai-dev-243-known-failure-"))
    path = root / "known_validator_failures_v1.json"
    path.write_text(json.dumps({"schema_version": "known_validator_failures_v1", "version": "test", "entries": entries}), encoding="utf-8")
    return path


def run_validation() -> dict:
    data = load_known_failures(KNOWN_FAILURES_PATH)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    config_validation = validate_known_failures_config(KNOWN_FAILURES_PATH, today=date(2026, 9, 15))
    details["config_validation"] = config_validation
    checks["quarantine_config_valid"] = config_validation.get("status") == "PASS"
    checks["quarantine_contains_expected_final_entries_only"] = len(entries) == len(EXPECTED_FINGERPRINTS)
    checks["entries_are_exact_canonical_fingerprints"] = {
        (entry.get("validator_id"), entry.get("failure_fingerprint")) for entry in entries
    } == set(EXPECTED_FINGERPRINTS.items())
    required = {"validator_id", "failure_fingerprint", "reason", "issue_owner", "baseline_reference", "introduced_by", "expires_at", "review_condition"}
    checks["required_metadata_present"] = all(required <= set(entry) and all(str(entry.get(field) or "").strip() for field in required) for entry in entries)

    fp_218a = EXPECTED_FINGERPRINTS["ai_dev_218a_tw_preopen_product_intelligence"]
    exact = _classify(False, False, fp_218a, fp_218a, entries)
    changed = _classify(False, False, fp_218a, "0" * 64, entries)
    head_only = _classify(True, False, None, fp_218a, entries)
    unknown = _classify(False, False, "a" * 64, "a" * 64, entries)
    recovered = _classify(True, True, None, None, entries)
    details["classification_fixtures"] = {
        "exact": exact,
        "changed": changed,
        "head_only": head_only,
        "unknown": unknown,
        "recovered": recovered,
    }
    checks["exact_baseline_match_pass"] = exact == {"classification": "PRE_EXISTING_IDENTICAL", "decision": "ALLOW", "quarantine_match": True}
    checks["changed_fingerprint_fail"] = changed["classification"] == "PRE_EXISTING_BUT_CHANGED" and changed["decision"] == "FAIL"
    checks["head_only_failure_fail"] = head_only["classification"] == "HEAD_ONLY_FAILURE" and head_only["decision"] == "FAIL"
    checks["unknown_failure_fail"] = unknown["classification"] == "UNKNOWN_FAILURE" and unknown["decision"] == "FAIL"
    checks["recovered_validator_pass_stale_report"] = recovered["classification"] == "RECOVERED_VALIDATOR" and recovered["decision"] == "PASS_STALE_QUARANTINE_REMOVABLE"
    checks["no_regression_masking"] = all(item["decision"] == "FAIL" for item in (changed, head_only, unknown))

    temp_a = "FileNotFoundError: /var/folders/wy/abc/T/ai-dev-212-a1/visual/2026-08-13/US/us_pre_market_2000/failures/screenshot_full.png\n"
    temp_b = "FileNotFoundError: /private/var/folders/wy/def/T/ai-dev-212-b2/visual/2026-08-13/US/us_pre_market_2000/failures/screenshot_full.png\n"
    temp_c = "FileNotFoundError: /tmp/ai-dev-243-blocker-audit/base/visual/2026-08-13/US/us_pre_market_2000/failures/screenshot_full.png\n"
    diff_assertion = temp_a.replace("FileNotFoundError", "AssertionError")
    diff_path = temp_a.replace("screenshot_full.png", "rendered_text.md")
    diff_expected_actual = "AssertionError: expected=7 actual=8 field=selected_news_count\n"
    diff_expected_actual_2 = "AssertionError: expected=7 actual=9 field=selected_news_count\n"
    runtime_id_a = (
        '{"manifest_path":"/var/folders/wy/x/T/ai-dev-208-a/visual_evidence/2026-08-13/TW/intraday_1305/'
        'failures/revision_001_abcdef123456.json","visual_evidence_id":"'
        + ("a" * 64)
        + '","errors":["case_a_tw_capture_success"]}\n'
    )
    runtime_id_b = (
        '{"manifest_path":"/var/folders/wy/y/T/ai-dev-208-b/visual_evidence/2026-08-13/TW/intraday_1305/'
        'failures/revision_001_123456abcdef.json","visual_evidence_id":"'
        + ("b" * 64)
        + '","errors":["case_a_tw_capture_success"]}\n'
    )
    fp_temp_a = failure_fingerprint_from_output("", temp_a)
    details["normalization_fingerprints"] = {
        "temp_a": fp_temp_a,
        "temp_b": failure_fingerprint_from_output("", temp_b),
        "temp_c": failure_fingerprint_from_output("", temp_c),
        "diff_assertion": failure_fingerprint_from_output("", diff_assertion),
        "diff_path": failure_fingerprint_from_output("", diff_path),
        "diff_expected_actual": failure_fingerprint_from_output("", diff_expected_actual),
        "diff_expected_actual_2": failure_fingerprint_from_output("", diff_expected_actual_2),
        "runtime_id_a": failure_fingerprint_from_output("", runtime_id_a),
        "runtime_id_b": failure_fingerprint_from_output("", runtime_id_b),
    }
    checks["same_semantic_failure_different_temp_roots_same_fingerprint"] = (
        fp_temp_a
        == details["normalization_fingerprints"]["temp_b"]
        == details["normalization_fingerprints"]["temp_c"]
    )
    checks["different_semantic_assertion_different_fingerprint"] = fp_temp_a != details["normalization_fingerprints"]["diff_assertion"]
    checks["different_artifact_relative_path_different_fingerprint"] = fp_temp_a != details["normalization_fingerprints"]["diff_path"]
    checks["changed_expected_actual_different_fingerprint"] = (
        details["normalization_fingerprints"]["diff_expected_actual"]
        != details["normalization_fingerprints"]["diff_expected_actual_2"]
    )
    checks["runtime_generated_ids_same_fingerprint"] = (
        details["normalization_fingerprints"]["runtime_id_a"]
        == details["normalization_fingerprints"]["runtime_id_b"]
    )

    expired = dict(entries[0])
    expired["expires_at"] = "2026-09-01"
    expired_result = validate_known_failures_config(_write_config([expired]), today=date(2026, 9, 15))
    malformed = dict(entries[0])
    malformed.pop("issue_owner", None)
    malformed["failure_fingerprint"] = "not-a-fingerprint"
    malformed_result = validate_known_failures_config(_write_config([malformed]), today=date(2026, 9, 15))
    details["expired_config_validation"] = expired_result
    details["malformed_config_validation"] = malformed_result
    checks["expired_entry_fail"] = expired_result.get("status") == "FAIL" and any("EXPIRED" in item for item in expired_result.get("errors", []))
    checks["malformed_entry_fail"] = malformed_result.get("status") == "FAIL" and any("MISSING:issue_owner" in item for item in malformed_result.get("errors", [])) and any("INVALID_FINGERPRINT" in item for item in malformed_result.get("errors", []))

    return {
        "schema_version": "ai_dev_243_known_failure_quarantine_validation_v1",
        "task_id": "AI-DEV-243",
        "ok": all(checks.values()),
        "passed_count": sum(bool(value) for value in checks.values()),
        "total_count": len(checks),
        "checks": checks,
        "details": details,
        "safety": {
            "production_rerun": False,
            "line_or_email_sent": False,
            "db_or_sheet_write": False,
            "scheduler_modified": False,
            "credentials_touched": False,
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
