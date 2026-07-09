#!/usr/bin/env python3
"""Validate AI-DEV-166 persistent manual-rerun runtime deployment."""
from __future__ import annotations

import argparse
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SERVICE_NAME = "stock-ai-manual-rerun-bridge.service"
PIN_FILE = Path("/home/kaochuchian/.config/stock-ai/manual_rerun_pin_hash")
BRIDGE = "http://172.19.0.1:18080"
PUBLIC = "http://35.201.242.167"
POST_PATH = "/stock-ai-dashboard/api/manual-rerun"
HEALTH_PATH = "/stock-ai-dashboard/api/manual-rerun/healthz"


def stable(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method=method, headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            parsed["http_status"] = resp.status
            parsed["content_type"] = resp.headers.get("Content-Type", "")
            return parsed
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"body": body[:500]}
        parsed["http_status"] = exc.code
        parsed["content_type"] = exc.headers.get("Content-Type", "")
        return parsed
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error_type": exc.__class__.__name__, "error_message": str(exc)}


def prohibited_processes() -> list[str]:
    proc = run(["ps", "-ef"])
    hits: list[str] = []
    needles = ["run_stock_analysis.sh", "approved_pre_open_delivery.py", "scripts/run_pipeline.py", "manual_rerun_single_window.py"]
    for line in proc.stdout.splitlines():
        if any(n in line for n in needles) and "validate_manual_rerun_runtime_persistent_deployment_v1.py" not in line:
            hits.append(line)
    return hits


def runtime_available() -> bool:
    return Path("/home/kaochuchian/dify/docker/nginx/conf.d/default.conf").exists() or run(["systemctl", "is-active", SERVICE_NAME]).returncode in {0, 3}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    skipped: list[str] = []

    repo_static = {
        "route_helper_exists": (ROOT / "scripts/orchestrator/deploy_manual_rerun_runtime_route_v1.py").exists(),
        "service_helper_exists": (ROOT / "scripts/orchestrator/deploy_manual_rerun_bridge_service_v1.py").exists(),
        "bridge_exists": (ROOT / "scripts/orchestrator/manual_rerun_runtime_bridge.py").exists(),
        "single_window_handler_exists": (ROOT / "scripts/orchestrator/manual_rerun_single_window.py").exists(),
        "runbook_exists": (ROOT / "docs/runbooks/manual_rerun_runtime_persistent_deployment_v1.md").exists(),
    }
    for name, ok in repo_static.items():
        if not ok:
            errors.append(f"repo static check failed: {name}")

    gcp_runtime: dict[str, Any] = {"available": runtime_available()}
    if not gcp_runtime["available"]:
        skipped.append("gcp_runtime_checks")
    else:
        service_active = run(["systemctl", "is-active", SERVICE_NAME])
        service_enabled = run(["systemctl", "is-enabled", SERVICE_NAME])
        service_cat = run(["systemctl", "cat", SERVICE_NAME])
        gcp_runtime["service"] = {
            "active": service_active.stdout.strip(),
            "enabled": service_enabled.stdout.strip(),
            "contains_execstart": "manual_rerun_runtime_bridge.py --serve" in service_cat.stdout and "--port 18080" in service_cat.stdout,
        }
        if service_active.stdout.strip() != "active":
            errors.append("manual rerun bridge service is not active")
        if service_enabled.stdout.strip() != "enabled":
            errors.append("manual rerun bridge service is not enabled")
        if not gcp_runtime["service"]["contains_execstart"]:
            errors.append("manual rerun bridge service ExecStart is not expected bridge command")

        if PIN_FILE.exists():
            mode = stat.S_IMODE(PIN_FILE.stat().st_mode)
            gcp_runtime["pin_file"] = {"exists": True, "mode": oct(mode)[2:].zfill(4), "content_printed": False}
            if mode != 0o600:
                errors.append("runtime PIN hash file must have 0600 mode")
        else:
            gcp_runtime["pin_file"] = {"exists": False, "mode": None, "content_printed": False}
            warnings.append("runtime PIN hash file missing; manual rerun should be disabled")

        before = prohibited_processes()
        bridge_health = request_json("GET", BRIDGE + HEALTH_PATH)
        public_health = request_json("GET", PUBLIC + HEALTH_PATH)
        missing_confirm = request_json("POST", PUBLIC + POST_PATH, {"window": "intraday_1305", "mode": "dashboard_refresh_only", "pin": "abc123"})
        invalid_pin = request_json("POST", PUBLIC + POST_PATH, {"window": "intraday_1305", "mode": "dashboard_refresh_only", "pin": "abc123", "confirm_single_window_only": True})
        after = prohibited_processes()
        gcp_runtime["http_checks"] = {
            "bridge_health": bridge_health,
            "public_health": public_health,
            "missing_confirm_rejection": missing_confirm,
            "invalid_pin_rejection": invalid_pin,
        }
        gcp_runtime["prohibited_processes_before"] = before
        gcp_runtime["prohibited_processes_after"] = after
        if bridge_health.get("status") != "ready" or bridge_health.get("http_status") != 200:
            errors.append("direct bridge healthz is not ready")
        if public_health.get("status") != "ready" or public_health.get("http_status") != 200:
            errors.append("public nginx healthz is not ready")
        if missing_confirm.get("http_status") != 403 or missing_confirm.get("reason") != "single_window_confirmation_required":
            errors.append("missing confirm_single_window_only must return HTTP 403 JSON single_window_confirmation_required")
        if invalid_pin.get("http_status") != 403 or invalid_pin.get("status") != "invalid_pin_format":
            errors.append("invalid non-digit PIN must return HTTP 403 JSON invalid_pin_format")
        if "json" not in str(missing_confirm.get("content_type", "")).lower() or "json" not in str(invalid_pin.get("content_type", "")).lower():
            errors.append("manual rerun rejection routes must return JSON, not HTML")
        if after:
            errors.append("safe rejection tests started prohibited delivery/pipeline process")

        from scripts.orchestrator.deploy_manual_rerun_runtime_route_v1 import DEFAULT_BRIDGE_ENDPOINT, discover_topology

        topology = discover_topology()
        config_path = topology.durable_config or topology.proc_config
        if not config_path:
            errors.append("active nginx config path not detected")
        else:
            text = config_path.read_text(encoding="utf-8")
            exact = text.count("location = /stock-ai-dashboard/api/manual-rerun")
            prefix = text.count("location ^~ /stock-ai-dashboard/api/manual-rerun/")
            proxy = text.count(f"proxy_pass {DEFAULT_BRIDGE_ENDPOINT};")
            gcp_runtime["nginx"] = {
                "config_path": str(config_path),
                "bind_mount_source": topology.bind_mount_source,
                "nginx_container": topology.nginx_container,
                "exact_route_count": exact,
                "prefix_route_count": prefix,
                "proxy_target_count": proxy,
                "contains_backup_duplicate_in_active_config": ".bak" in str(config_path),
            }
            if exact != 1:
                errors.append(f"active nginx config must contain one exact manual rerun route, got {exact}")
            if prefix != 1:
                errors.append(f"active nginx config must contain one prefix manual rerun route, got {prefix}")
            if proxy < 2:
                errors.append("active nginx manual rerun routes must proxy to bridge endpoint")
            if topology.bind_mount_source != "/home/kaochuchian/dify/docker/nginx/conf.d":
                warnings.append("nginx conf.d bind mount source differs from current known durable path")

    result = {
        "schema_version": "manual_rerun_runtime_persistent_deployment_validation_v1",
        "task_id": "AI-DEV-166",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "repo_static_checks": repo_static,
        "gcp_runtime_checks": gcp_runtime,
        "skipped_runtime_checks": skipped,
        "safety": {
            "real_pin_used": False,
            "valid_manual_rerun_triggered": False,
            "line_email_notification_sent": False,
            "production_pipeline_executed": False,
            "db_write": False,
            "secrets_or_pin_hash_printed": False,
            "scheduler_modified": False,
            "trading_or_order_executed": False,
        },
    }
    print(stable(result) if args.pretty else json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
