#!/usr/bin/env python3
"""Persist the manual-rerun API route across nginx container lifecycles."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ROUTE_SOURCE = ROOT / "config/nginx/manual_rerun_api_proxy_v1.conf"
DEFAULT_TEMPLATE = Path("/home/kaochuchian/dify/docker/nginx/conf.d/default.conf.template")
DEFAULT_ACTIVE = Path("/home/kaochuchian/dify/docker/nginx/conf.d/default.conf")
DEFAULT_COMPOSE_DIR = Path("/home/kaochuchian/dify/docker")
DEFAULT_CONTAINER = "docker-nginx-1"
START = "# STOCK-AI-MANUAL-RERUN-API-START"
END = "# STOCK-AI-MANUAL-RERUN-API-END"
STATIC = "location ^~ /stock-ai-dashboard/ {"
EXACT = "location = /stock-ai-dashboard/api/manual-rerun {"
PREFIX = "location ^~ /stock-ai-dashboard/api/manual-rerun/ {"
TARGET = "proxy_pass http://172.19.0.1:18080;"


def stable(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_route_source(path: Path = ROUTE_SOURCE) -> str:
    text = path.read_text(encoding="utf-8").strip() + "\n"
    errors = validate_contract(text, require_static=False)
    if errors:
        raise ValueError("invalid route source: " + ",".join(errors))
    return text


def remove_managed_block(text: str) -> str:
    if START not in text and END not in text:
        return text
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("managed route markers are unbalanced")
    before, remainder = text.split(START, 1)
    _, after = remainder.split(END, 1)
    return before.rstrip() + "\n\n" + after.lstrip("\n")


def render_persistent_config(template_text: str, route_text: str) -> tuple[str, bool]:
    clean = remove_managed_block(template_text)
    marker_at = clean.find(STATIC)
    if marker_at < 0:
        raise ValueError("static Dashboard location not found")
    rendered = clean[:marker_at].rstrip() + "\n\n" + route_text.strip() + "\n\n" + clean[marker_at:]
    return rendered, rendered != template_text


def validate_contract(text: str, *, require_static: bool = True) -> list[str]:
    errors: list[str] = []
    checks = {
        "EXACT_ROUTE_COUNT": text.count(EXACT) == 1,
        "PREFIX_ROUTE_COUNT": text.count(PREFIX) == 1,
        "PROXY_TARGET_COUNT": text.count(TARGET) == 2,
        "START_MARKER_COUNT": text.count(START) == 1,
        "END_MARKER_COUNT": text.count(END) == 1,
    }
    for code, passed in checks.items():
        if not passed:
            errors.append(code)
    if require_static:
        if STATIC not in text:
            errors.append("STATIC_DASHBOARD_LOCATION_MISSING")
        elif not (text.find(EXACT) < text.find(PREFIX) < text.find(STATIC)):
            errors.append("API_ROUTE_PRECEDENCE_INVALID")
    return errors


def atomic_write(path: Path, text: str) -> str:
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    backup = path.with_name(path.name + f".ai-dev-217-backup-{stamp}")
    shutil.copy2(path, backup)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, path.stat().st_mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return str(backup)


def run(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--recreate", action="store_true", help="recreate nginx after persisting the template")
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--active-path", type=Path, default=DEFAULT_ACTIVE)
    parser.add_argument("--compose-dir", type=Path, default=DEFAULT_COMPOSE_DIR)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    backups: dict[str, str] = {}
    lifecycle: dict[str, Any] = {}
    template_before = args.template_path.read_text(encoding="utf-8")
    active_before = args.active_path.read_text(encoding="utf-8")
    route = load_route_source()
    template_after, template_changed = render_persistent_config(template_before, route)
    active_after, active_changed = render_persistent_config(active_before, route)
    errors.extend("TEMPLATE_" + code for code in validate_contract(template_after))
    errors.extend("ACTIVE_" + code for code in validate_contract(active_after))

    if args.apply and not errors:
        if template_changed:
            backups["template"] = atomic_write(args.template_path, template_after)
        if active_changed:
            backups["active"] = atomic_write(args.active_path, active_after)
        lifecycle["nginx_test_before_lifecycle"] = run(["sudo", "docker", "exec", args.container, "nginx", "-t"])
        if lifecycle["nginx_test_before_lifecycle"]["returncode"] != 0:
            errors.append("NGINX_CONFIG_TEST_FAILED")
        elif args.recreate:
            lifecycle["recreate"] = run(
                ["sudo", "docker", "compose", "up", "-d", "--force-recreate", "nginx"],
                cwd=args.compose_dir,
            )
            if lifecycle["recreate"]["returncode"] != 0:
                errors.append("NGINX_RECREATE_FAILED")
        else:
            lifecycle["reload"] = run(["sudo", "docker", "exec", args.container, "nginx", "-s", "reload"])
            if lifecycle["reload"]["returncode"] != 0:
                errors.append("NGINX_RELOAD_FAILED")

        if not errors:
            time.sleep(2)
            lifecycle["nginx_test_after_lifecycle"] = run(["sudo", "docker", "exec", args.container, "nginx", "-t"])
            if lifecycle["nginx_test_after_lifecycle"]["returncode"] != 0:
                errors.append("NGINX_POST_LIFECYCLE_TEST_FAILED")
            rendered_active = args.active_path.read_text(encoding="utf-8")
            errors.extend("POST_LIFECYCLE_" + code for code in validate_contract(rendered_active))

    result = {
        "schema_version": "manual_rerun_nginx_persistence_deployment_v1",
        "task_id": "AI-DEV-217-INFRA-RECOVERY",
        "status": "PASS" if not errors else "FAIL",
        "mode": "apply" if args.apply else "dry_run",
        "recreate_requested": bool(args.recreate),
        "persistent_source": str(args.template_path),
        "active_config": str(args.active_path),
        "canonical_route_source": str(ROUTE_SOURCE),
        "proxy_target": "http://172.19.0.1:18080",
        "template_changed": template_changed,
        "active_changed": active_changed,
        "template_sha256_before": sha256_text(template_before),
        "template_sha256_after": sha256_text(template_after),
        "backups": backups,
        "lifecycle": lifecycle,
        "errors": errors,
        "safety": {
            "manual_rerun_triggered": False,
            "production_pipeline_executed": False,
            "notifications_sent": False,
            "trading_or_orders": False,
            "secrets_modified": False,
            "production_db_written": False,
            "immutable_archive_rewritten": False,
        },
    }
    print(stable(result) if args.pretty else json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
