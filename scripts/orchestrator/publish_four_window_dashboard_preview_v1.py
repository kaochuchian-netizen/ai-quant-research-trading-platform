#!/usr/bin/env python3
"""Controlled static publish for the four-window dashboard preview."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "templates/four_window_dashboard_preview_publish_input.example.json"
DEFAULT_SOURCE_HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
DEFAULT_PUBLIC_BASE_URL = "http://35.201.242.167/stock-ai-dashboard"
DEFAULT_ROUTE_PATH = "/dashboard/decision-intelligence/four-window-preview"
STATIC_ROOT_CANDIDATES = [
    Path("/var/www/stock-ai-dashboard"),
    Path("/var/www/html/stock-ai-dashboard"),
    Path("/var/www/html/stock-ai-dashboard-20260701-104649"),
    Path("/var/www/stock-ai-dashboard.pre-ai-dev-111-20260701"),
]
SECRET_PATTERNS = ["Authorization:", "Bearer ", "api_key", "token=", "password=", "BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY", ".env"]
WINDOW_MARKERS = [
    "pre_open_0700", "盤前預測", "Pre-open Forecast",
    "intraday_1305", "盤中追蹤", "Intraday Tracking",
    "pre_close_1335", "close_snapshot_1335", "收盤快照", "Close Snapshot",
    "post_close_1500", "prediction_review_1500", "盤後檢討", "Prediction Review",
]
INDEX_MARKER = "AI-DEV-145 four-window decision intelligence preview"
# Compatibility audit markers describe the isolated route, never root index.html.
LEGACY_ROUTE_MARKERS = (
    "Legacy / Debug Landing",
    "不再作為正式投資決策主畫面",
    "四時段 Decision Intelligence Dashboard",
)


def stable_json(payload: Any, pretty: bool) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"JSON root must be object: {path}")
    return data


def now_taipei() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch_url(url: str, timeout: int = 8) -> tuple[bool, bytes, str | None]:
    try:
        with urlopen(url, timeout=timeout) as response:
            return True, response.read(), None
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, b"", str(exc)


def candidate_roots(extra: list[Path]) -> list[Path]:
    seen: set[str] = set()
    roots: list[Path] = []
    for path in [*extra, *STATIC_ROOT_CANDIDATES]:
        key = str(path)
        if key not in seen:
            seen.add(key)
            roots.append(path)
    return roots


def locate_dashboard_root(public_base_url: str, explicit_root: Path | None = None) -> dict[str, Any]:
    extra = [explicit_root] if explicit_root else []
    public_ok, public_index, public_error = fetch_url(public_base_url.rstrip("/") + "/index.html")
    public_hash = sha256_bytes(public_index) if public_ok else None
    inspected: list[dict[str, Any]] = []
    fallback: Path | None = None
    for root in candidate_roots(extra):
        index = root / "index.html"
        item: dict[str, Any] = {
            "path": str(root),
            "exists": root.exists(),
            "is_dir": root.is_dir(),
            "index_exists": index.exists(),
            "writable": root.exists() and root.is_dir() and os.access(root, os.W_OK),
            "matches_public_index": False,
        }
        if index.exists():
            item_hash = sha256_bytes(index.read_bytes())
            item["index_sha256"] = item_hash
            item["matches_public_index"] = bool(public_hash and item_hash == public_hash)
            if item["writable"] and fallback is None:
                fallback = root
        inspected.append(item)
        if item["writable"] and item["matches_public_index"]:
            return {"ok": True, "dashboard_static_root": str(root), "matched_public_index": True, "public_index_reachable": public_ok, "public_index_error": public_error, "inspected_roots": inspected}
    if fallback:
        return {"ok": True, "dashboard_static_root": str(fallback), "matched_public_index": False, "public_index_reachable": public_ok, "public_index_error": public_error, "inspected_roots": inspected, "warning": "using first writable dashboard root because public index hash did not match any candidate"}
    return {"ok": False, "dashboard_static_root": None, "matched_public_index": False, "public_index_reachable": public_ok, "public_index_error": public_error, "inspected_roots": inspected, "error": "no writable dashboard static root with index.html found"}


def check_source_html(source_html: Path) -> list[str]:
    errors: list[str] = []
    text = source_html.read_text(encoding="utf-8")
    for marker in WINDOW_MARKERS:
        if marker not in text:
            errors.append(f"missing window marker in source html: {marker}")
    if "Pre-close" in text or "收盤前" in text:
        errors.append("source html contains forbidden 13:35 pre-close semantic text")
    for pattern in SECRET_PATTERNS:
        if pattern in text:
            errors.append(f"source html contains forbidden secret-like pattern: {pattern}")
    return errors


def backup_existing(root: Path, target_dir: Path, timestamp: str) -> Path:
    backup_dir = root / ".ai_dev_145_rollback" / timestamp.replace(":", "").replace("+", "_")
    backup_dir.mkdir(parents=True, exist_ok=False)
    if target_dir.exists():
        shutil.copytree(target_dir, backup_dir / "four-window-preview.before_ai_dev_145")
    else:
        (backup_dir / "target_route_previously_absent.txt").write_text("target route did not exist before AI-DEV-145 publish\n", encoding="utf-8")
    return backup_dir


def write_publish_files(root: Path, source_html: Path, public_base_url: str, route_path: str, timestamp: str, add_index_link: bool) -> dict[str, Any]:
    normalized_route = route_path.strip("/")
    target_dir = root / normalized_route
    backup_dir = backup_existing(root, target_dir, timestamp)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_index = target_dir / "index.html"
    shutil.copy2(source_html, target_index)
    public_url = public_base_url.rstrip("/") + "/" + normalized_route + "/index.html"
    # Route ownership contract: legacy/compat publishing is route-local. The
    # retained argument is ignored for backward CLI compatibility.
    index_link_added = False
    rollback_command = (
        f"rm -rf {target_dir} && "
        f"if [ -d {backup_dir}/four-window-preview.before_ai_dev_145 ]; then "
        f"mkdir -p {target_dir.parent} && cp -a {backup_dir}/four-window-preview.before_ai_dev_145 {target_dir}; fi"
    )
    manifest = {
        "schema_version": "four_window_dashboard_preview_publish_manifest_v1",
        "task_id": "AI-DEV-145",
        "published_at": timestamp,
        "source_file": str(source_html),
        "target_path": str(target_index),
        "public_url": public_url,
        "backup_path": str(backup_dir),
        "rollback_command": rollback_command,
        "index_link_added": index_link_added,
        "production_root_untouched": True,
        "safety_flags": {
            "production_dashboard_publish_executed": True,
            "dashboard_published": True,
            "external_notification_sent": False,
            "scheduler_modified": False,
            "production_pipeline_executed": False,
            "db_write": False,
            "secrets_read": False,
            "formal_delivery_behavior_changed": False,
            "line_email_notification_sent": False,
            "trading_or_order_executed": False,
            "python_main_executed": False,
            "production_rating_action_confidence_weight_mutated": False,
            "nginx_system_service_modified": False,
            "firewall_or_vm_infra_modified": False
        }
    }
    (target_dir / "publish_manifest.json").write_text(stable_json(manifest, True), encoding="utf-8")
    result_dir = root / ".ai_dev_145_publish_results"
    result_dir.mkdir(exist_ok=True)
    result_path = result_dir / "latest.json"
    result_path.write_text(stable_json(manifest, True), encoding="utf-8")
    return {**manifest, "result_path": str(result_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dashboard-root", type=Path)
    parser.add_argument("--source-html", type=Path, default=DEFAULT_SOURCE_HTML)
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    parser.add_argument("--route-path", default=DEFAULT_ROUTE_PATH)
    parser.add_argument("--no-index-link", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    input_payload = load_json(args.input) if args.input.exists() else {}
    source_html = args.source_html.resolve()
    timestamp = now_taipei()
    errors = check_source_html(source_html)
    located = locate_dashboard_root(args.public_base_url, args.dashboard_root)
    if not located.get("ok"):
        errors.append(str(located.get("error")))
    root = Path(str(located.get("dashboard_static_root"))) if located.get("dashboard_static_root") else None
    public_url = args.public_base_url.rstrip("/") + "/" + args.route_path.strip("/") + "/index.html"
    publish_manifest: dict[str, Any] | None = None
    if not errors and not args.plan_only:
        publish_manifest = write_publish_files(root, source_html, args.public_base_url, args.route_path, timestamp, False)  # type: ignore[arg-type]
    result = {
        "ok": not errors,
        "schema_version": "four_window_dashboard_preview_publish_result_v1",
        "task_id": "AI-DEV-145",
        "mode": "plan_only" if args.plan_only else "controlled_static_publish",
        "publish_executed": bool(publish_manifest),
        "input_task_id": input_payload.get("task_id"),
        "dashboard_static_root": str(root) if root else None,
        "matched_public_index": located.get("matched_public_index"),
        "public_index_reachable": located.get("public_index_reachable"),
        "source_file": str(source_html),
        "target_route_path": args.route_path,
        "target_path": str(root / args.route_path.strip("/") / "index.html") if root else None,
        "public_url": public_url,
        "backup_path": publish_manifest.get("backup_path") if publish_manifest else None,
        "rollback_command": publish_manifest.get("rollback_command") if publish_manifest else None,
        "result_path": publish_manifest.get("result_path") if publish_manifest else None,
        "errors": errors,
        "inspected_roots": located.get("inspected_roots", []),
        "safety_flags": {
            "production_dashboard_publish_executed": bool(publish_manifest),
            "dashboard_published": bool(publish_manifest),
            "external_notification_sent": False,
            "scheduler_modified": False,
            "production_pipeline_executed": False,
            "db_write": False,
            "secrets_read": False,
            "formal_delivery_behavior_changed": False,
            "line_email_notification_sent": False,
            "trading_or_order_executed": False,
            "python_main_executed": False,
            "production_rating_action_confidence_weight_mutated": False,
            "nginx_system_service_modified": False,
            "firewall_or_vm_infra_modified": False
        }
    }
    print(stable_json(result, args.pretty), end="")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
