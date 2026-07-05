#!/usr/bin/env python3
"""Validate AI-DEV-145 controlled dashboard preview publish artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "templates/four_window_dashboard_preview_publish_input.example.json"
DEFAULT_PLAN = ROOT / "templates/four_window_dashboard_preview_publish.example.json"
DEFAULT_HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
DEFAULT_ROUTE_ARTIFACT = ROOT / "templates/four_window_dashboard_route_integration.example.json"
DEFAULT_PUBLIC_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"
SECRET_PATTERNS = ["Authorization:", "Bearer ", "api_key", "access_token", "token=", "password=", "BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY", ".env"]
WINDOW_MARKERS = [
    "pre_open_0700", "盤前預測", "Pre-open Forecast",
    "intraday_1305", "盤中追蹤", "Intraday Tracking",
    "pre_close_1335", "close_snapshot_1335", "收盤快照", "Close Snapshot",
    "post_close_1500", "prediction_review_1500", "盤後檢討", "Prediction Review",
]
DOCS = [ROOT / "docs/four_window_dashboard_preview_publish_v1.md", ROOT / "docs/runbooks/four_window_dashboard_preview_publish_runbook.md"]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def fetch(url: str) -> tuple[bool, str, str | None]:
    try:
        with urlopen(url, timeout=10) as response:
            return True, response.read().decode("utf-8", errors="replace"), None
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, "", str(exc)


def scan_text(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [pattern for pattern in SECRET_PATTERNS if pattern in text]


def validate_payloads(published: bool) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    secret_hits: list[str] = []
    for path in [DEFAULT_INPUT, DEFAULT_PLAN, DEFAULT_HTML, DEFAULT_ROUTE_ARTIFACT, *DOCS]:
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(ROOT)}")
        else:
            secret_hits.extend([f"{path.relative_to(ROOT)}:{pattern}" for pattern in scan_text(path)])
    try:
        plan = load_json(DEFAULT_PLAN)
    except Exception as exc:
        errors.append(str(exc)); plan = {}
    try:
        request = load_json(DEFAULT_INPUT)
    except Exception as exc:
        errors.append(str(exc)); request = {}
    html_text = DEFAULT_HTML.read_text(encoding="utf-8") if DEFAULT_HTML.exists() else ""
    for marker in WINDOW_MARKERS:
        if marker not in html_text:
            errors.append(f"source preview missing marker: {marker}")
    if "Pre-close" in html_text or "收盤前" in html_text:
        errors.append("13:35 source preview contains forbidden pre-close semantic text")
    if plan.get("schema_version") != "four_window_dashboard_preview_publish_v1":
        errors.append("publish plan schema_version mismatch")
    if request.get("controlled_publish_approved") is not True:
        errors.append("controlled_publish_approved must be true")
    semantic = plan.get("semantic_policy", {}) if isinstance(plan.get("semantic_policy"), dict) else {}
    if semantic.get("close_snapshot_1335_ui_label_required") is not True:
        errors.append("close_snapshot_1335 UI label requirement missing")
    if semantic.get("pre_close_primary_semantic_allowed") is not False:
        errors.append("pre-close primary semantic must be disallowed")
    publish_state = plan.get("publish_state", {}) if isinstance(plan.get("publish_state"), dict) else {}
    for key in ["external_notification_sent", "scheduler_modified", "production_pipeline_executed", "db_write", "secrets_read", "formal_delivery_behavior_changed"]:
        if publish_state.get(key) is not False:
            errors.append(f"publish_state.{key} must be false")
    for doc in DOCS:
        if doc.exists():
            text = doc.read_text(encoding="utf-8")
            for needle in ["controlled static Dashboard preview publish", "rollback", "no LINE / Email", "no scheduler", "no DB writes", "no production pipeline"]:
                if needle not in text:
                    errors.append(f"doc {doc.relative_to(ROOT)} missing required phrase: {needle}")
    published_summary: dict[str, Any] = {"checked": False}
    if published:
        url = str(plan.get("public_url") or DEFAULT_PUBLIC_URL)
        ok, text, error = fetch(url)
        published_summary = {"checked": True, "public_url": url, "reachable": ok, "error": error}
        if not ok:
            errors.append(f"published public URL unreachable: {error}")
        else:
            for marker in WINDOW_MARKERS:
                if marker not in text:
                    errors.append(f"published route missing marker: {marker}")
            if "Pre-close" in text or "收盤前" in text:
                errors.append("published route contains forbidden 13:35 pre-close semantic text")
        root = Path(str(plan.get("dashboard_static_root", "")))
        manifest = root / "dashboard/decision-intelligence/four-window-preview/publish_manifest.json"
        if not manifest.exists():
            errors.append("published manifest missing")
        else:
            manifest_payload = load_json(manifest)
            backup_path = Path(str(manifest_payload.get("backup_path", "")))
            published_summary["backup_path"] = str(backup_path)
            published_summary["rollback_command_present"] = bool(manifest_payload.get("rollback_command"))
            if not backup_path.exists():
                errors.append("rollback backup path does not exist")
            if not manifest_payload.get("rollback_command"):
                errors.append("rollback command missing from publish manifest")
            safety = manifest_payload.get("safety_flags", {}) if isinstance(manifest_payload.get("safety_flags"), dict) else {}
            expected = {
                "production_dashboard_publish_executed": True,
                "dashboard_published": True,
                "external_notification_sent": False,
                "scheduler_modified": False,
                "production_pipeline_executed": False,
                "db_write": False,
                "secrets_read": False,
                "formal_delivery_behavior_changed": False,
            }
            for key, value in expected.items():
                if safety.get(key) is not value:
                    errors.append(f"published safety flag {key} expected {value}")
    return {
        "ok": not errors,
        "task_id": "AI-DEV-145",
        "schema_version": "four_window_dashboard_preview_publish_validation_v1",
        "published_mode": published,
        "errors": errors,
        "warnings": warnings,
        "secret_pattern_hits": secret_hits,
        "values_included_or_printed": False,
        "published_summary": published_summary,
        "safety_summary": {
            "external_notification_sent": False,
            "scheduler_modified": False,
            "production_pipeline_executed": False,
            "db_write": False,
            "secrets_read": False,
            "trading_or_order_executed": False,
            "production_rating_action_confidence_weight_mutated": False,
            "formal_delivery_behavior_changed": False
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--published", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate_payloads(args.published)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
