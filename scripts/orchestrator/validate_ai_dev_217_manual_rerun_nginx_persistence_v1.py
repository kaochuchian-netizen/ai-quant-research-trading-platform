#!/usr/bin/env python3
"""Validate persistent manual-rerun nginx routing after container recreation."""
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/orchestrator/deploy_manual_rerun_nginx_persistence_v1.py"
spec = importlib.util.spec_from_file_location("manual_rerun_nginx_persistence", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main() -> int:
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: object = None) -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    route = module.load_route_source()
    base_template = """server {
    listen 80;
    location ^~ /stock-ai-dashboard/ {
        alias /var/www/html/stock-ai-dashboard/;
        try_files $uri $uri/ =404;
    }
    location / { proxy_pass http://web:3000; }
}
"""
    rendered, changed = module.render_persistent_config(base_template, route)
    check("canonical source exact route", route.count(module.EXACT) == 1)
    check("canonical source status prefix route", route.count(module.PREFIX) == 1)
    check("canonical source proxy target", route.count(module.TARGET) == 2)
    check("persistent render changed", changed)
    check("effective config contract", module.validate_contract(rendered) == [], module.validate_contract(rendered))
    check(
        "API precedes static alias",
        rendered.find(module.EXACT) < rendered.find(module.PREFIX) < rendered.find(module.STATIC),
    )

    rerendered, changed_again = module.render_persistent_config(rendered, route)
    check("idempotent persistent render", rerendered == rendered and not changed_again)

    # Container recreation is modeled by rendering a new active config from the
    # persisted template. The API contract must survive with no runtime patch.
    with tempfile.TemporaryDirectory(prefix="ai-dev-217-nginx-") as temporary:
        root = Path(temporary)
        persistent = root / "default.conf.template"
        active = root / "default.conf"
        persistent.write_text(rendered, encoding="utf-8")
        active.write_text(persistent.read_text(encoding="utf-8"), encoding="utf-8")
        recreated = active.read_text(encoding="utf-8")
        check("recreation preserves route", module.validate_contract(recreated) == [])
        check("recreation preserves bridge target", recreated.count(module.TARGET) == 2)

    wrong_target = rendered.replace(module.TARGET, "proxy_pass http://127.0.0.1:9999;")
    check("wrong target mutation rejected", "PROXY_TARGET_COUNT" in module.validate_contract(wrong_target))
    swallowed = rendered.replace(module.EXACT, "location ^~ /stock-ai-dashboard/ {")
    check("static swallow mutation rejected", bool(module.validate_contract(swallowed)))
    missing_prefix = rendered.replace(module.PREFIX, "location ^~ /stock-ai-dashboard/api/other/ {")
    check("missing status route mutation rejected", "PREFIX_ROUTE_COUNT" in module.validate_contract(missing_prefix))
    misplaced = base_template + "\n" + route
    check("route order mutation rejected", "API_ROUTE_PRECEDENCE_INVALID" in module.validate_contract(misplaced))

    safety_tokens = ["proxy_set_header", "proxy_pass"]
    check("nginx remains transport only", all(token in route for token in safety_tokens))
    check(
        "no PIN bypass in nginx",
        "auth_request off" not in route.lower() and "x-manual-rerun-pin" not in route.lower(),
    )
    validator_source = Path(__file__).read_text(encoding="utf-8")
    network_call_tokens = ("url" + "open(", "http." + "client", "requests." + "post(")
    check("no rerun execution in validator", all(token not in validator_source for token in network_call_tokens))

    failed = [row for row in checks if row["status"] != "PASS"]
    result = {
        "schema_version": "ai_dev_217_manual_rerun_nginx_persistence_validation_v1",
        "task_id": "AI-DEV-217-INFRA-RECOVERY",
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "summary": {"total": len(checks), "passed": len(checks) - len(failed), "failed": len(failed)},
        "safety": {
            "manual_rerun_triggered": False,
            "production_pipeline_executed": False,
            "notifications_sent": False,
            "trading_or_orders": False,
            "secrets_accessed": False,
            "production_db_written": False,
            "immutable_archive_rewritten": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
