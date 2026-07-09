#!/usr/bin/env python3
"""Deploy/check the Stock AI manual rerun bridge systemd service."""
from __future__ import annotations

import argparse
import json
import stat
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SERVICE_NAME = "stock-ai-manual-rerun-bridge.service"
SERVICE_PATH = Path("/etc/systemd/system") / SERVICE_NAME
PIN_FILE = Path("/home/kaochuchian/.config/stock-ai/manual_rerun_pin_hash")
DEFAULT_HOST = "172.19.0.1"
DEFAULT_PORT = 18080


def stable(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def run(cmd: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, input=input_text, text=True, capture_output=True, check=False)


def unit_text(host: str, port: int) -> str:
    return f"""[Unit]
Description=Stock AI Dashboard Manual Rerun Bridge
After=network.target

[Service]
Type=simple
User=kaochuchian
WorkingDirectory=/home/kaochuchian/stock-ai
ExecStart=/usr/bin/python3 /home/kaochuchian/stock-ai/scripts/orchestrator/manual_rerun_runtime_bridge.py --serve --host {host} --port {port}
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/home/kaochuchian/stock-ai/artifacts/runtime /home/kaochuchian/.config/stock-ai /tmp

[Install]
WantedBy=multi-user.target
"""


def pin_metadata() -> dict[str, Any]:
    if not PIN_FILE.exists():
        return {"exists": False, "mode": None, "owner_uid": None, "manual_rerun_enabled": False}
    st = PIN_FILE.stat()
    mode = stat.S_IMODE(st.st_mode)
    return {"exists": True, "mode": oct(mode)[2:].zfill(4), "owner_uid": st.st_uid, "manual_rerun_enabled": mode == 0o600}


def health(host: str, port: int) -> dict[str, Any]:
    url = f"http://{host}:{port}/stock-ai-dashboard/api/manual-rerun/healthz"
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            data["http_status"] = resp.status
            data["url"] = url
            return data
    except HTTPError as exc:
        return {"ok": False, "http_status": exc.code, "url": url}
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error_type": exc.__class__.__name__, "error_message": str(exc), "url": url}


def systemd_state() -> dict[str, Any]:
    enabled = run(["systemctl", "is-enabled", SERVICE_NAME])
    active = run(["systemctl", "is-active", SERVICE_NAME])
    cat = run(["systemctl", "cat", SERVICE_NAME])
    return {
        "enabled": enabled.stdout.strip(),
        "enabled_returncode": enabled.returncode,
        "active": active.stdout.strip(),
        "active_returncode": active.returncode,
        "unit_contains_expected_execstart": "manual_rerun_runtime_bridge.py --serve" in cat.stdout and "--port 18080" in cat.stdout,
        "unit_path": str(SERVICE_PATH),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy/check manual rerun bridge service.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--bridge-host", default=DEFAULT_HOST)
    parser.add_argument("--bridge-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    desired = unit_text(args.bridge_host, args.bridge_port)
    current = SERVICE_PATH.read_text(encoding="utf-8") if SERVICE_PATH.exists() else ""
    changed_needed = current != desired
    errors: list[str] = []
    applied = False
    if args.apply:
        if changed_needed:
            proc = run(["sudo", "tee", str(SERVICE_PATH)], input_text=desired)
            if proc.returncode != 0:
                errors.append("failed to write systemd service file")
            else:
                reload_proc = run(["sudo", "systemctl", "daemon-reload"])
                enable_proc = run(["sudo", "systemctl", "enable", "--now", SERVICE_NAME])
                if reload_proc.returncode != 0 or enable_proc.returncode != 0:
                    errors.append("failed to daemon-reload or enable service")
                else:
                    applied = True
        else:
            enable_proc = run(["sudo", "systemctl", "enable", "--now", SERVICE_NAME])
            if enable_proc.returncode != 0:
                errors.append("failed to ensure service enabled/running")
            else:
                applied = True

    result = {
        "schema_version": "manual_rerun_bridge_service_deployment_v1",
        "task_id": "AI-DEV-166",
        "ok": not errors,
        "mode": "apply" if args.apply else "dry_run",
        "errors": errors,
        "changed_needed": changed_needed,
        "applied": applied,
        "service_name": SERVICE_NAME,
        "desired_execstart": f"/usr/bin/python3 /home/kaochuchian/stock-ai/scripts/orchestrator/manual_rerun_runtime_bridge.py --serve --host {args.bridge_host} --port {args.bridge_port}",
        "systemd_state": systemd_state(),
        "pin_file_metadata": pin_metadata(),
        "direct_bridge_health": health(args.bridge_host, args.bridge_port),
        "safety": {
            "pin_hash_printed": False,
            "secrets_read": False,
            "scheduler_modified": False,
            "line_email_notification_sent": False,
            "production_pipeline_executed": False,
            "db_write": False,
            "trading_or_order_executed": False,
            "valid_manual_rerun_triggered": False,
        },
    }
    print(stable(result) if args.pretty else json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
