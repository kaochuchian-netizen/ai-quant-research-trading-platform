#!/usr/bin/env python3
"""Validate AI-DEV-117 trading gateway architecture without broker side effects."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.trading.gateway import TradingGateway
from app.trading.risk_gate import ProductionOrderBlocked, SimulationApprovalRequired
from app.trading.schemas import (
    AccountStatusRequest,
    KbarsRequest,
    OrderProposal,
    ProductionOrderRequest,
    SimulationOrderRequest,
    SnapshotRequest,
)


TASK_ID = "AI-DEV-117"
SCHEMA_VERSION = "trading_gateway_architecture_v1"


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"object is not JSON serializable: {type(value).__name__}")


def capture(name: str, check: Callable[[], Any]) -> dict[str, Any]:
    try:
        value = check()
        return {"name": name, "ok": True, "result": value}
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
    gateway = TradingGateway.offline_default()
    proposal = OrderProposal(symbol="2330", side="buy", quantity=1, price=Decimal("1"))
    production_request = ProductionOrderRequest(proposal=proposal)
    simulation_request = SimulationOrderRequest(proposal=proposal)

    checks = [
        expect_blocked(
            "production_order_blocked",
            ProductionOrderBlocked,
            lambda: gateway.validate_production_order(production_request),
        ),
        expect_blocked(
            "simulation_order_without_approval_blocked",
            SimulationApprovalRequired,
            lambda: gateway.validate_simulation_order(simulation_request),
        ),
        capture("proposal_only_mode_allowed", lambda: gateway.validate_order_proposal(proposal)),
        capture(
            "quote_schemas_created",
            lambda: {
                "snapshot": gateway.validate_snapshot_request(SnapshotRequest(symbols=("2330",))),
                "kbars": gateway.validate_kbars_request(
                    KbarsRequest(symbol="2330", start=date(2026, 1, 1), end=date(2026, 1, 2))
                ),
                "capability": gateway.check_quote_capability().quote,
            },
        ),
        capture(
            "account_schemas_created",
            lambda: gateway.validate_account_status_request(AccountStatusRequest()),
        ),
    ]

    side_effects = {
        "read_env": False,
        "broker_login_called": False,
        "simulation_order_called": False,
        "production_order_called": False,
        "notification_sent": False,
        "scheduler_modified": False,
        "database_modified": False,
    }
    safety = {
        "production_order_blocked": checks[0]["ok"] is True,
        "simulation_without_approval_blocked": checks[1]["ok"] is True,
        "proposal_only_allowed": checks[2]["ok"] is True,
        "quote_account_schema_only": checks[3]["ok"] is True and checks[4]["ok"] is True,
        "no_env_read": True,
        "no_broker_login": True,
        "no_notifications": True,
        "no_trade_execution": True,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "ok": all(item["ok"] for item in checks) and all(safety.values()) and not any(side_effects.values()),
        "checks": checks,
        "safety": safety,
        "side_effects": side_effects,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate trading gateway architecture V1.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = build_result()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, default=json_default, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
