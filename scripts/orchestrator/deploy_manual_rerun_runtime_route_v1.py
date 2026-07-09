#!/usr/bin/env python3
"""Deploy the Dashboard manual-rerun nginx route into the active nginx namespace."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BRIDGE_ENDPOINT = "http://172.19.0.1:18080"
DEFAULT_PUBLIC_HEALTHZ = "http://35.201.242.167/stock-ai-dashboard/api/manual-rerun/healthz"
ROUTE_START = "    # STOCK-AI-MANUAL-RERUN-API-START"
ROUTE_END = "    # STOCK-AI-MANUAL-RERUN-API-END"
DASHBOARD_LOCATION_RE = re.compile(r"^\s*location\s+\^~\s+/stock-ai-dashboard/\s*\{", re.MULTILINE)


@dataclass
class NginxTopology:
    master_pid: int | None
    proc_config: Path | None
    durable_config: Path | None
    nginx_container: str | None
    bind_mount_source: str | None
    notes: list[str]


def run(cmd: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, input=input_text, text=True, capture_output=True, check=False)


def stable(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def find_nginx_master_pid() -> int | None:
    proc = run(["ps", "-eo", "pid=,args="])
    for line in proc.stdout.splitlines():
        if "nginx: master process" in line and "daemon off" in line:
            return int(line.strip().split(None, 1)[0])
    for line in proc.stdout.splitlines():
        if "nginx: master process" in line:
            return int(line.strip().split(None, 1)[0])
    return None


def discover_nginx_container() -> str | None:
    if not shutil.which("docker"):
        return None
    proc = run(["sudo", "docker", "ps", "--format", "{{.Names}} {{.Image}}"])
    for line in proc.stdout.splitlines():
        if "nginx" in line.lower():
            return line.split()[0]
    return None


def discover_bind_mount_source(pid: int | None) -> str | None:
    if pid is None:
        return None
    mountinfo = Path(f"/proc/{pid}/mountinfo")
    if not mountinfo.exists():
        return None
    for line in mountinfo.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) > 5 and parts[4] == "/etc/nginx/conf.d":
            return parts[3]
    return None


def _path_exists(path: Path | None, notes: list[str]) -> bool:
    if path is None:
        return False
    try:
        return path.exists()
    except PermissionError:
        notes.append(f"permission denied while checking {path}; using durable host path if available")
        return False


def discover_topology() -> NginxTopology:
    notes: list[str] = []
    pid = find_nginx_master_pid()
    proc_config = Path(f"/proc/{pid}/root/etc/nginx/conf.d/default.conf") if pid else None
    bind_source = discover_bind_mount_source(pid)
    durable = None
    if bind_source and bind_source.startswith("/"):
        candidate = Path(bind_source) / "default.conf"
        if _path_exists(candidate, notes):
            durable = candidate
            notes.append("active /etc/nginx/conf.d is bind-mounted from durable host path")
    known = Path("/home/kaochuchian/dify/docker/nginx/conf.d/default.conf")
    if durable is None and _path_exists(known, notes):
        durable = known
        notes.append("used known Dify nginx host config path")
    container = discover_nginx_container()
    if container:
        notes.append(f"detected nginx container: {container}")
    return NginxTopology(pid, proc_config if _path_exists(proc_config, notes) else None, durable, container, bind_source, notes)


def route_block(bridge_endpoint: str) -> str:
    endpoint = bridge_endpoint.rstrip("/")
    return f"""{ROUTE_START}
    location = /stock-ai-dashboard/api/manual-rerun {{
      proxy_pass {endpoint};
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_connect_timeout 5s;
      proxy_read_timeout 600s;
      add_header Cache-Control \"no-store\" always;
    }}

    location ^~ /stock-ai-dashboard/api/manual-rerun/ {{
      proxy_pass {endpoint};
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_connect_timeout 5s;
      proxy_read_timeout 600s;
      add_header Cache-Control \"no-store\" always;
    }}
{ROUTE_END}"""


def upsert_route(config_text: str, bridge_endpoint: str) -> tuple[str, bool]:
    block = route_block(bridge_endpoint)
    marker_re = re.compile(re.escape(ROUTE_START) + r".*?" + re.escape(ROUTE_END), re.DOTALL)
    if marker_re.search(config_text):
        new_text = marker_re.sub(block, config_text, count=1)
        return new_text, new_text != config_text
    match = DASHBOARD_LOCATION_RE.search(config_text)
    if not match:
        raise ValueError("could not locate /stock-ai-dashboard/ location for safe insertion")
    insert_at = match.start()
    return config_text[:insert_at] + block + "\n\n" + config_text[insert_at:], True


def nginx_test(container: str | None) -> dict[str, Any]:
    cmd = ["sudo", "docker", "exec", container, "nginx", "-t"] if container else ["sudo", "nginx", "-t"]
    proc = run(cmd)
    return {"command": " ".join(cmd), "returncode": proc.returncode, "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}


def nginx_reload(container: str | None) -> dict[str, Any]:
    cmd = ["sudo", "docker", "exec", container, "nginx", "-s", "reload"] if container else ["sudo", "nginx", "-s", "reload"]
    proc = run(cmd)
    return {"command": " ".join(cmd), "returncode": proc.returncode, "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}


def get_json(url: str) -> dict[str, Any]:
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            data["http_status"] = resp.status
            return data
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {"body": body[:500]}
        data["http_status"] = exc.code
        return data
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error_type": exc.__class__.__name__, "error_message": str(exc)}


def summarize_config(text: str, bridge_endpoint: str) -> dict[str, Any]:
    return {
        "exact_route_count": text.count("location = /stock-ai-dashboard/api/manual-rerun"),
        "prefix_route_count": text.count("location ^~ /stock-ai-dashboard/api/manual-rerun/"),
        "proxy_target_count": text.count(f"proxy_pass {bridge_endpoint.rstrip('/')};"),
        "has_route_markers": ROUTE_START.strip() in text and ROUTE_END.strip() in text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Dashboard manual rerun nginx route persistently.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--bridge-endpoint", default=DEFAULT_BRIDGE_ENDPOINT)
    parser.add_argument("--public-healthz", default=DEFAULT_PUBLIC_HEALTHZ)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    topology = discover_topology()
    errors: list[str] = []
    warnings: list[str] = []
    config_path = topology.durable_config or topology.proc_config
    config_text = ""
    new_text = ""
    changed = False
    if config_path is None:
        errors.append("active nginx default.conf not found")
    else:
        config_text = config_path.read_text(encoding="utf-8")
        try:
            new_text, changed = upsert_route(config_text, args.bridge_endpoint)
        except Exception as exc:
            errors.append(f"route upsert failed: {exc}")
            new_text = config_text

    backup_path = None
    nginx_test_result = None
    nginx_reload_result = None
    applied = False
    if args.apply and not errors and config_path is not None:
        if changed:
            backup = config_path.with_name(config_path.name + ".ai-dev-166-backup-" + time.strftime("%Y%m%d%H%M%S"))
            backup.write_text(config_text, encoding="utf-8")
            backup_path = str(backup)
            config_path.write_text(new_text, encoding="utf-8")
            nginx_test_result = nginx_test(topology.nginx_container)
            if nginx_test_result["returncode"] != 0:
                config_path.write_text(config_text, encoding="utf-8")
                errors.append("nginx config test failed; restored previous content")
            else:
                nginx_reload_result = nginx_reload(topology.nginx_container)
                applied = nginx_reload_result["returncode"] == 0
                if not applied:
                    errors.append("nginx reload failed after config test")
        else:
            nginx_test_result = nginx_test(topology.nginx_container)
            applied = nginx_test_result["returncode"] == 0
            if not applied:
                errors.append("nginx config test failed on existing route")

    final_text = config_path.read_text(encoding="utf-8") if config_path and args.apply and config_path.exists() else new_text
    result = {
        "schema_version": "manual_rerun_runtime_route_deployment_v1",
        "task_id": "AI-DEV-166",
        "ok": not errors,
        "mode": "apply" if args.apply else "dry_run",
        "errors": errors,
        "warnings": warnings,
        "topology": {
            "nginx_master_pid": topology.master_pid,
            "proc_config": str(topology.proc_config) if topology.proc_config else None,
            "durable_config": str(topology.durable_config) if topology.durable_config else None,
            "bind_mount_source": topology.bind_mount_source,
            "nginx_container": topology.nginx_container,
            "notes": topology.notes,
        },
        "config_path": str(config_path) if config_path else None,
        "changed_needed": changed,
        "applied": applied,
        "backup_path": backup_path,
        "nginx_test": nginx_test_result,
        "nginx_reload": nginx_reload_result,
        "route_summary": summarize_config(final_text, args.bridge_endpoint) if final_text else {},
        "bridge_health": get_json(args.bridge_endpoint.rstrip("/") + "/stock-ai-dashboard/api/manual-rerun/healthz"),
        "public_health": get_json(args.public_healthz),
        "safety": {
            "scheduler_modified": False,
            "production_pipeline_executed": False,
            "line_email_notification_sent": False,
            "db_write": False,
            "secrets_read": False,
            "trading_or_order_executed": False,
            "valid_manual_rerun_triggered": False,
        },
    }
    print(stable(result) if args.pretty else json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
