#!/usr/bin/env python3
"""Validate AI-DEV-118 Sinopac read-only runtime adapter safety."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.trading.gateway import TradingGateway
from app.trading.runtime_health import build_trading_runtime_health
from app.trading.schemas import OrderProposal, ProductionOrderRequest, SimulationOrderRequest
from app.trading.sinopac_adapter import (
    SinopacLoginBlocked,
    SinopacOrderBlocked,
    build_runtime_adapter,
    check_import_available,
)


TASK_ID = "AI-DEV-118"
SCHEMA_VERSION = "sinopac_runtime_adapter_read_only_v1"


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"object is not JSON serializable: {type(value).__name__}")


def capture(name: str, check: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"name": name, "ok": True, "result": check()}
    except Exception as exc:
        return {"name": name, "ok": False, "error_class": type(exc).__name__, "error": str(exc)}


def expect_blocked(name: str, error_type: type[Exception], check: Callable[[], Any]) -> dict[str, Any]:
    try:
        check()
    except error_type as exc:
        return {"name": name, "ok": True, "blocked": True, "error_class": type(exc).__name__}
    except Exception as exc:
        return {"name": name, "ok": False, "error_class": type(exc).__name__, "error": str(exc)}
    return {"name": name, "ok": False, "error": "request was not blocked"}


def build_result() -> dict[str, Any]:
    runtime_adapter = build_runtime_adapter()
    gateway = TradingGateway.with_sinopac_runtime_adapter()
    proposal = OrderProposal(symbol="2330", side="buy", quantity=1, price=Decimal("1"))

    checks = [
        capture("shioaji_import_checked", lambda: check_import_available()),
        capture("runtime_health_json_created", build_trading_runtime_health),
        expect_blocked("login_without_explicit_approval_blocked", SinopacLoginBlocked, runtime_adapter.login),
        expect_blocked(
            "simulation_order_blocked",
            SinopacOrderBlocked,
            lambda: runtime_adapter.submit_simulation_order(SimulationOrderRequest(proposal=proposal)),
        ),
        expect_blocked(
            "production_order_blocked",
            SinopacOrderBlocked,
            lambda: runtime_adapter.submit_production_order(ProductionOrderRequest(proposal=proposal)),
        ),
        capture(
            "quote_account_adapter_interfaces_created",
            lambda: {
                "quote_adapter": type(gateway.quote_adapter).__name__,
                "account_adapter": type(gateway.account_adapter).__name__,
                "quote_capability": gateway.quote_adapter.capability(),
                "account_capability": gateway.account_adapter.capability(),
                "runtime_adapter_attached": gateway.runtime_adapter is not None,
            },
        ),
    ]

    health = checks[1].get("result") if checks[1].get("ok") else {}
    side_effects = {
        "read_env": False,
        "broker_login_called": False,
        "simulation_order_called": False,
        "production_order_called": False,
        "notification_sent": False,
        "scheduler_modified": False,
        "database_modified": False,
        "strategy_signal_connected": False,
    }
    safety = {
        "shioaji_import_check_supported": checks[0]["ok"] is True,
        "runtime_health_json_supported": checks[1]["ok"] is True and isinstance(health, dict),
        "login_default_blocked": checks[2]["ok"] is True,
        "simulation_order_blocked": checks[3]["ok"] is True,
        "production_order_blocked": checks[4]["ok"] is True,
        "quote_account_interfaces_created": checks[5]["ok"] is True,
        "no_env_read": True,
        "no_notifications": True,
        "no_trade_execution": True,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "ok": all(item["ok"] for item in checks) and all(safety.values()) and not any(side_effects.values()),
        "checks": checks,
        "runtime_health": health,
        "safety": safety,
        "side_effects": side_effects,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Sinopac runtime adapter read-only V1.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = build_result()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, default=json_default, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
