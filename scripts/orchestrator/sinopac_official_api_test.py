#!/usr/bin/env python3
"""Controlled Sinopac/Shioaji official API online test evidence tool.

Dry-run mode is offline and does not read secrets, login, or place orders.
Execute mode is limited to Shioaji simulation=True login and simulation orders
after same-run Richard approval flags are present.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
from datetime import datetime, time as wall_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


TASK_ID = "AI-DEV-119"
SCHEMA_VERSION = "sinopac_official_api_test_result_v1"
MIN_SHIOAJI_VERSION = (1, 5, 4)
MIN_SHIOAJI_VERSION_TEXT = "1.5.4"
TAIPEI = ZoneInfo("Asia/Taipei")
RICHARD_APPROVAL_PHRASE = "RICHARD_APPROVES_AI_DEV_119_SIMULATION_LOGIN_AND_ORDER"
MASKED = "***MASKED***"

SAFETY = {
    "simulation_only": True,
    "production_blocked": True,
    "production_order_forbidden": True,
    "formal_order_forbidden": True,
    "stock_test_default_enabled": True,
    "futures_test_default_enabled": False,
    "requires_richard_same_run_approval": True,
    "requires_explicit_login_flag": True,
    "requires_explicit_order_flag": True,
    "no_strategy_signal_integration": True,
    "no_scheduler_cron_systemd_integration": True,
    "no_line_email_notification": True,
    "no_production_db_write": True,
    "no_secret_or_account_printing": True,
}

SIDE_EFFECT_FALSE_KEYS = {
    "production_client_created": False,
    "production_order_called": False,
    "formal_order_called": False,
    "strategy_signal_connected": False,
    "scheduler_modified": False,
    "cron_modified": False,
    "systemd_modified": False,
    "line_sent": False,
    "email_sent": False,
    "production_db_modified": False,
    "secret_printed": False,
    "account_number_printed": False,
}

SENSITIVE_KEY_PARTS = ("api_key", "secret", "token", "password", "account", "ca_passwd")


class SafetyGateError(RuntimeError):
    """Raised when an execution request is outside the approved safety gate."""


def parse_version(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts: list[int] = []
    for raw in value.split("."):
        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def shioaji_health() -> dict[str, Any]:
    try:
        version = importlib.metadata.version("shioaji")
        __import__("shioaji")
    except Exception as exc:
        return {
            "import_ok": False,
            "installed_version": None,
            "minimum_required_version": MIN_SHIOAJI_VERSION_TEXT,
            "version_ok": False,
            "error_class": type(exc).__name__,
        }
    return {
        "import_ok": True,
        "installed_version": version,
        "minimum_required_version": MIN_SHIOAJI_VERSION_TEXT,
        "version_ok": parse_version(version) >= MIN_SHIOAJI_VERSION,
        "error_class": None,
    }


def now_taipei() -> datetime:
    return datetime.now(TAIPEI)


def in_service_window(moment: datetime) -> bool:
    if moment.weekday() >= 5:
        return False
    return wall_time(8, 0) <= moment.time() <= wall_time(20, 0)


def taiwan_ip_only_window(moment: datetime) -> bool:
    return wall_time(18, 0) <= moment.time() <= wall_time(20, 0)


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                if isinstance(item, bool) or item in (None, "", [], {}):
                    result[key] = item
                elif isinstance(item, (str, int, float)):
                    result[key] = MASKED
                else:
                    result[key] = mask_sensitive(item)
            else:
                result[key] = mask_sensitive(item)
        return result
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [mask_sensitive(item) for item in value]
    return value


def stable_json(payload: dict[str, Any], pretty: bool) -> str:
    return json.dumps(mask_sensitive(payload), ensure_ascii=False, indent=2 if pretty else None, sort_keys=True) + "\n"


def side_effects(*, secrets_read: bool = False, login_called: bool = False, simulation_order_called: bool = False) -> dict[str, bool]:
    result = {
        "secrets_read": secrets_read,
        "simulation_login_called": login_called,
        "simulation_order_called": simulation_order_called,
    }
    result.update(SIDE_EFFECT_FALSE_KEYS)
    return result


def base_result(mode: str, run_id: str | None) -> dict[str, Any]:
    current = now_taipei()
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id or f"sinopac-official-api-test-{current.strftime('%Y%m%dT%H%M%S%z')}",
        "generated_at": current.isoformat(),
        "mode": mode,
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "timezone": "Asia/Taipei",
        },
        "official_requirements": {
            "simulation_login_required": True,
            "simulation_place_order_required": True,
            "shioaji_minimum_version": MIN_SHIOAJI_VERSION_TEXT,
            "execution_window": "Monday-Friday 08:00-20:00 Asia/Taipei",
            "taiwan_ip_required_between": "18:00-20:00 Asia/Taipei",
            "stock_and_futures_tested_separately": True,
            "minimum_order_interval_seconds": 1,
            "api_key_must_have_trading_permission": True,
        },
        "service_window": {
            "in_service_window": in_service_window(current),
            "taiwan_ip_only_window": taiwan_ip_only_window(current),
            "taiwan_ip_attestation_required": taiwan_ip_only_window(current),
        },
        "shioaji": shioaji_health(),
        "test_plan": {
            "stock": {"enabled": True, "simulation": True, "default_symbol": "2330"},
            "futures": {"enabled": False, "simulation": True, "requires_enable_futures": True},
        },
        "credential_redaction": {
            "api_key": MASKED,
            "secret_key": MASKED,
            "stock_account": MASKED,
            "futures_account": MASKED,
        },
        "safety": dict(SAFETY),
        "side_effects": side_effects(),
    }


def dry_run(args: argparse.Namespace) -> dict[str, Any]:
    result = base_result("dry-run", args.run_id)
    result.update(
        {
            "ok": True,
            "decision": "sinopac_official_api_test_dry_run_ready",
            "test_results": {
                "login": {"status": "not_run", "simulation": True, "reason": "dry_run"},
                "stock_place_order": {"status": "not_run", "simulation": True, "reason": "dry_run"},
                "futures_place_order": {"status": "disabled", "simulation": True, "reason": "disabled_by_default"},
            },
            "approval": {
                "richard_same_run_approval_present": False,
                "simulation_login_flag_present": False,
                "simulation_order_flag_present": False,
            },
        }
    )
    return result


def require_execute_gate(args: argparse.Namespace) -> None:
    if args.production:
        raise SafetyGateError("production mode is blocked; this tool only supports simulation=True")
    if not args.i_understand_this_runs_simulation_login:
        raise SafetyGateError("missing --i-understand-this-runs-simulation-login")
    if not args.i_understand_this_runs_simulation_order:
        raise SafetyGateError("missing --i-understand-this-runs-simulation-order")
    if args.richard_approval != RICHARD_APPROVAL_PHRASE:
        raise SafetyGateError("missing Richard same-run approval phrase")
    current = now_taipei()
    if not in_service_window(current):
        raise SafetyGateError("outside official Sinopac API test window: Monday-Friday 08:00-20:00 Asia/Taipei")
    if taiwan_ip_only_window(current) and not args.taiwan_ip_attested:
        raise SafetyGateError("18:00-20:00 Asia/Taipei requires explicit Taiwan IP attestation")


def runtime_api() -> tuple[Any, Any, str, str]:
    import shioaji as sj

    api_key = os.getenv("SINOPAC_API_KEY")
    secret_key = os.getenv("SINOPAC_SECRET_KEY")
    if not api_key or not secret_key:
        raise SafetyGateError("SINOPAC_API_KEY and SINOPAC_SECRET_KEY are required for execute; values are never printed")
    return sj, sj.Shioaji(simulation=True), api_key, secret_key


def shioaji_constant(module: Any, group: str, name: str) -> Any:
    constants = getattr(module, "constant", None)
    group_obj = getattr(constants, group, None)
    return getattr(group_obj, name, name)


def execute(args: argparse.Namespace) -> dict[str, Any]:
    require_execute_gate(args)
    sj, api, api_key, secret_key = runtime_api()
    started = now_taipei()
    accounts = api.login(api_key=api_key, secret_key=secret_key, contracts_timeout=args.contracts_timeout)
    time.sleep(max(args.min_interval_seconds, 1.0))
    contract = api.Contracts.Stocks[args.stock_id]
    order = api.Order(
        price=args.price,
        quantity=args.quantity,
        action=shioaji_constant(sj, "Action", args.action),
        price_type=shioaji_constant(sj, "StockPriceType", args.price_type),
        order_type=shioaji_constant(sj, "OrderType", args.order_type),
        account=api.stock_account,
    )
    trade = api.place_order(contract, order)

    futures_result = {"status": "disabled", "simulation": True, "reason": "disabled_by_default"}
    if args.enable_futures:
        if not args.futures_contract_month:
            raise SafetyGateError("--futures-contract-month is required when --enable-futures is used")
        time.sleep(max(args.min_interval_seconds, 1.0))
        futures_contract = api.Contracts.Futures[args.futures_code][args.futures_contract_month]
        futures_order = api.Order(
            price=args.futures_price,
            quantity=args.futures_quantity,
            action=shioaji_constant(sj, "Action", args.futures_action),
            price_type=shioaji_constant(sj, "FuturesPriceType", args.futures_price_type),
            order_type=shioaji_constant(sj, "OrderType", args.futures_order_type),
            account=api.futopt_account,
        )
        futures_trade = api.place_order(futures_contract, futures_order)
        futures_result = {
            "status": "completed",
            "ok": True,
            "simulation": True,
            "futures_code": args.futures_code,
            "contract_month": args.futures_contract_month,
            "quantity": args.futures_quantity,
            "action": args.futures_action,
            "price_type": args.futures_price_type,
            "order_type": args.futures_order_type,
            "trade_status": str(getattr(futures_trade, "status", "submitted")),
        }

    try:
        api.logout()
    except Exception:
        pass

    result = base_result("execute", args.run_id)
    result["test_plan"]["futures"]["enabled"] = bool(args.enable_futures)
    result.update(
        {
            "ok": True,
            "decision": "sinopac_official_api_simulation_tests_completed",
            "approval": {
                "richard_same_run_approval_present": True,
                "simulation_login_flag_present": True,
                "simulation_order_flag_present": True,
            },
            "test_results": {
                "login": {
                    "status": "completed",
                    "ok": True,
                    "simulation": True,
                    "started_at": started.isoformat(),
                    "finished_at": now_taipei().isoformat(),
                    "account_count": len(accounts) if hasattr(accounts, "__len__") else None,
                },
                "stock_place_order": {
                    "status": "completed",
                    "ok": True,
                    "simulation": True,
                    "stock_id": args.stock_id,
                    "quantity": args.quantity,
                    "action": args.action,
                    "price_type": args.price_type,
                    "order_type": args.order_type,
                    "trade_status": str(getattr(trade, "status", "submitted")),
                },
                "futures_place_order": futures_result,
            },
            "side_effects": side_effects(secrets_read=True, login_called=True, simulation_order_called=True),
        }
    )
    return result


def blocked_result(error: str, args: argparse.Namespace) -> dict[str, Any]:
    result = base_result("blocked", getattr(args, "run_id", None))
    result.update(
        {
            "ok": False,
            "decision": "sinopac_official_api_test_blocked_by_safety_gate",
            "error": error,
            "test_results": {
                "login": {"status": "blocked", "simulation": True, "reason": "safety_gate"},
                "stock_place_order": {"status": "blocked", "simulation": True, "reason": "safety_gate"},
                "futures_place_order": {"status": "disabled", "simulation": True, "reason": "disabled_by_default"},
            },
            "approval": {
                "richard_same_run_approval_present": getattr(args, "richard_approval", None) == RICHARD_APPROVAL_PHRASE,
                "simulation_login_flag_present": bool(getattr(args, "i_understand_this_runs_simulation_login", False)),
                "simulation_order_flag_present": bool(getattr(args, "i_understand_this_runs_simulation_order", False)),
            },
        }
    )
    return result


def write_or_print(payload: dict[str, Any], args: argparse.Namespace) -> None:
    text = stable_json(payload, args.pretty)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled Sinopac official API online test evidence tool.")
    parser.add_argument("--mode", choices=["dry-run", "execute"], required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--production", action="store_true", help="Always blocked; included so production requests fail closed.")
    parser.add_argument("--richard-approval")
    parser.add_argument("--i-understand-this-runs-simulation-login", action="store_true")
    parser.add_argument("--i-understand-this-runs-simulation-order", action="store_true")
    parser.add_argument("--taiwan-ip-attested", action="store_true")
    parser.add_argument("--contracts-timeout", type=int, default=10000)
    parser.add_argument("--min-interval-seconds", type=float, default=1.0)
    parser.add_argument("--stock-id", default="2330")
    parser.add_argument("--price", type=float, default=1.0)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--action", choices=["Buy", "Sell"], default="Buy")
    parser.add_argument("--price-type", default="LMT")
    parser.add_argument("--order-type", default="ROD")
    parser.add_argument("--enable-futures", action="store_true")
    parser.add_argument("--futures-code", default="TXF")
    parser.add_argument("--futures-contract-month")
    parser.add_argument("--futures-price", type=float, default=1.0)
    parser.add_argument("--futures-quantity", type=int, default=1)
    parser.add_argument("--futures-action", choices=["Buy", "Sell"], default="Buy")
    parser.add_argument("--futures-price-type", default="LMT")
    parser.add_argument("--futures-order-type", default="ROD")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = dry_run(args) if args.mode == "dry-run" else execute(args)
        write_or_print(payload, args)
        return 0
    except SafetyGateError as exc:
        write_or_print(blocked_result(str(exc), args), args)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
