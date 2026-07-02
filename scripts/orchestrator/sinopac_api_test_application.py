#!/usr/bin/env python3
"""Controlled Sinopac/Shioaji API test application helper.

Default commands are offline and do not read secrets, login, place orders,
touch portfolio state, modify schedules, or call production services.
Runtime login/order subcommands require explicit per-run confirmation.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime, time as wall_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


TASK_ID = "AI-DEV-116"
SCHEMA_VERSION = "sinopac_api_test_application_v1"
STATUS_SCHEMA_VERSION = "sinopac_api_test_status_v1"
MIN_SHIOAJI_VERSION = (1, 2)
DEFAULT_TEMPLATE = Path("templates/sinopac_api_test_application_request.example.json")
TAIPEI = ZoneInfo("Asia/Taipei")
LOGIN_CONFIRMATION = "RICHARD_APPROVES_SIMULATION_LOGIN_TEST"
STOCK_ORDER_CONFIRMATION = "RICHARD_APPROVES_SIMULATION_STOCK_PLACE_ORDER_TEST"
FUTURES_ORDER_CONFIRMATION = "RICHARD_APPROVES_SIMULATION_FUTURES_PLACE_ORDER_TEST"
SAFETY = {
    "simulation_only": True,
    "production_place_order_forbidden": True,
    "no_formal_trading": True,
    "no_auto_trading": True,
    "no_scheduler_integration": True,
    "no_strategy_signal_integration": True,
    "no_portfolio_modification": True,
    "no_secret_printing": True,
    "requires_richard_same_run_confirmation_for_order": True,
    "futures_order_test_default_enabled": False,
}


class SafetyGateError(RuntimeError):
    """Raised when a runtime command violates the controlled test gate."""


@dataclass(frozen=True)
class ShioajiHealth:
    import_ok: bool
    version: str | None
    version_ok: bool
    error: str | None = None


def parse_version(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts: list[int] = []
    for raw in value.split("."):
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits == "":
            break
        parts.append(int(digits))
    return tuple(parts)


def shioaji_health() -> ShioajiHealth:
    try:
        version = importlib.metadata.version("shioaji")
        __import__("shioaji")
    except Exception as exc:
        return ShioajiHealth(False, None, False, type(exc).__name__)
    version_ok = parse_version(version) >= MIN_SHIOAJI_VERSION
    return ShioajiHealth(True, version, version_ok)


def now_taipei() -> datetime:
    return datetime.now(TAIPEI)


def in_service_window(moment: datetime | None = None) -> bool:
    current = moment or now_taipei()
    if current.weekday() >= 5:
        return False
    current_time = current.time()
    return wall_time(8, 0) <= current_time <= wall_time(20, 0)


def in_taiwan_ip_only_window(moment: datetime | None = None) -> bool:
    current = moment or now_taipei()
    current_time = current.time()
    return wall_time(18, 0) <= current_time <= wall_time(20, 0)


def stable_json(payload: Any, pretty: bool = True) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True) + "\n"


def read_template(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"request template not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"request template is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("request template root must be an object")
    return payload


def side_effects(runtime_called: bool = False, login_called: bool = False, order_called: bool = False) -> dict[str, bool]:
    return {
        "read_secrets": runtime_called,
        "printed_secrets": False,
        "mutated_secrets": False,
        "login_called": login_called,
        "place_order_called": order_called,
        "production_place_order_called": False,
        "modified_portfolio": False,
        "modified_scheduler": False,
        "modified_strategy_signal": False,
        "sent_line_push": False,
        "wrote_persistent_store": False,
    }


def base_record(mode: str, run_id: str | None = None) -> dict[str, Any]:
    health = shioaji_health()
    current = now_taipei()
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id or f"sinopac-api-test-{current.strftime('%Y%m%dT%H%M%S%z')}",
        "generated_at": current.isoformat(),
        "mode": mode,
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "timezone": "Asia/Taipei",
        },
        "shioaji": {
            "import_ok": health.import_ok,
            "installed_version": health.version,
            "minimum_required_version": "1.2",
            "version_ok": health.version_ok,
            "error_class": health.error,
        },
        "service_window": {
            "official_window": "Monday-Friday 08:00-20:00 Asia/Taipei",
            "in_service_window": in_service_window(current),
            "taiwan_ip_only_window": in_taiwan_ip_only_window(current),
            "taiwan_ip_attestation_required": in_taiwan_ip_only_window(current),
        },
        "safety": dict(SAFETY),
        "side_effects": side_effects(),
    }


def build_application(args: argparse.Namespace) -> dict[str, Any]:
    template = read_template(Path(args.template))
    record = base_record("offline_application_package", args.run_id)
    record.update(
        {
            "application_request": template,
            "required_tests": {
                "login": {"required": True, "simulation": True},
                "stock_place_order": {"required": True, "simulation": True, "min_interval_seconds": 1},
                "futures_place_order": {
                    "required_for_futures_api": True,
                    "simulation": True,
                    "default_enabled": False,
                    "min_interval_seconds": 1,
                },
            },
            "runtime_commands": {
                "health_check": "python3 scripts/orchestrator/sinopac_api_test_application.py health-check --pretty",
                "status": "python3 scripts/orchestrator/sinopac_api_test_application.py status --input <record.json> --pretty",
                "login_test": (
                    "python3 scripts/orchestrator/sinopac_api_test_application.py login-test "
                    f"--confirm {LOGIN_CONFIRMATION} --output <record.json> --pretty"
                ),
                "stock_order_test": (
                    "python3 scripts/orchestrator/sinopac_api_test_application.py stock-order-test "
                    f"--confirm {STOCK_ORDER_CONFIRMATION} --output <record.json> --pretty"
                ),
            },
            "ok": True,
            "decision": "sinopac_api_test_application_package_ready",
        }
    )
    return record


def health_check(args: argparse.Namespace) -> dict[str, Any]:
    record = base_record("offline_runtime_health_check", args.run_id)
    record.update(
        {
            "ok": record["shioaji"]["import_ok"] is True and record["shioaji"]["version_ok"] is True,
            "decision": (
                "sinopac_api_runtime_health_ready"
                if record["shioaji"]["import_ok"] and record["shioaji"]["version_ok"]
                else "sinopac_api_runtime_health_blocked"
            ),
        }
    )
    return record


def status(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_template(Path(args.input))
    tests = payload.get("test_results") if isinstance(payload.get("test_results"), dict) else {}
    required = ["login", "stock_place_order"]
    missing = [name for name in required if not isinstance(tests.get(name), dict)]
    completed = {
        name: tests.get(name, {}).get("ok") is True
        for name in ["login", "stock_place_order", "futures_place_order"]
        if isinstance(tests.get(name), dict)
    }
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": payload.get("run_id"),
        "generated_at": now_taipei().isoformat(),
        "required_tests_completed": not missing and all(completed.get(name) for name in required),
        "completed_tests": completed,
        "missing_required_tests": missing,
        "futures_test_default_enabled": False,
        "safety": dict(SAFETY),
        "side_effects": side_effects(),
        "ok": not missing,
        "decision": "sinopac_api_test_status_ready" if not missing else "sinopac_api_test_status_incomplete",
    }


def require_runtime_gate(confirm: str, expected: str, allow_after_18_taiwan_ip: bool) -> None:
    if confirm != expected:
        raise SafetyGateError("missing Richard same-run confirmation phrase")
    if not in_service_window():
        raise SafetyGateError("outside official Sinopac API test service window")
    if in_taiwan_ip_only_window() and not allow_after_18_taiwan_ip:
        raise SafetyGateError("18:00-20:00 requires explicit Taiwan IP attestation")


def get_runtime_api() -> tuple[Any, Any, str, str]:
    import shioaji as sj

    api_key = os.getenv("SINOPAC_API_KEY")
    secret_key = os.getenv("SINOPAC_SECRET_KEY")
    if not api_key or not secret_key:
        raise SafetyGateError("SINOPAC_API_KEY and SINOPAC_SECRET_KEY must be present; values are never printed")
    return sj, sj.Shioaji(simulation=True), api_key, secret_key


def shioaji_constant(module: Any, group: str, name: str) -> Any:
    constants = getattr(module, "constant", None)
    group_obj = getattr(constants, group, None)
    return getattr(group_obj, name, name)


def login_test(args: argparse.Namespace) -> dict[str, Any]:
    require_runtime_gate(args.confirm, LOGIN_CONFIRMATION, args.taiwan_ip_attested)
    _, api, api_key, secret_key = get_runtime_api()
    started = now_taipei()
    accounts = api.login(api_key=api_key, secret_key=secret_key, contracts_timeout=args.contracts_timeout)
    account_count = len(accounts) if hasattr(accounts, "__len__") else None
    try:
        api.logout()
    except Exception:
        pass
    record = base_record("simulation_login_test", args.run_id)
    record.update(
        {
            "test_results": {
                "login": {
                    "ok": True,
                    "simulation": True,
                    "started_at": started.isoformat(),
                    "finished_at": now_taipei().isoformat(),
                    "account_count": account_count,
                }
            },
            "side_effects": side_effects(runtime_called=True, login_called=True),
            "ok": True,
            "decision": "sinopac_simulation_login_test_completed",
        }
    )
    return record


def stock_order_test(args: argparse.Namespace) -> dict[str, Any]:
    require_runtime_gate(args.confirm, STOCK_ORDER_CONFIRMATION, args.taiwan_ip_attested)
    sj, api, api_key, secret_key = get_runtime_api()
    started = now_taipei()
    api.login(api_key=api_key, secret_key=secret_key, contracts_timeout=args.contracts_timeout)
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
    try:
        api.logout()
    except Exception:
        pass
    record = base_record("simulation_stock_place_order_test", args.run_id)
    record.update(
        {
            "test_results": {
                "stock_place_order": {
                    "ok": True,
                    "simulation": True,
                    "started_at": started.isoformat(),
                    "finished_at": now_taipei().isoformat(),
                    "stock_id": args.stock_id,
                    "quantity": args.quantity,
                    "action": args.action,
                    "price_type": args.price_type,
                    "order_type": args.order_type,
                    "trade_status": str(getattr(trade, "status", "submitted")),
                }
            },
            "side_effects": side_effects(runtime_called=True, login_called=True, order_called=True),
            "ok": True,
            "decision": "sinopac_simulation_stock_place_order_test_completed",
        }
    )
    return record


def futures_order_test(args: argparse.Namespace) -> dict[str, Any]:
    require_runtime_gate(args.confirm, FUTURES_ORDER_CONFIRMATION, args.taiwan_ip_attested)
    if not args.enable_futures:
        raise SafetyGateError("futures place_order test is disabled unless --enable-futures is passed")
    sj, api, api_key, secret_key = get_runtime_api()
    started = now_taipei()
    api.login(api_key=api_key, secret_key=secret_key, contracts_timeout=args.contracts_timeout)
    time.sleep(max(args.min_interval_seconds, 1.0))
    contract = api.Contracts.Futures[args.futures_code][args.contract_month]
    order = api.Order(
        price=args.price,
        quantity=args.quantity,
        action=shioaji_constant(sj, "Action", args.action),
        price_type=shioaji_constant(sj, "FuturesPriceType", args.price_type),
        order_type=shioaji_constant(sj, "OrderType", args.order_type),
        account=api.futopt_account,
    )
    trade = api.place_order(contract, order)
    try:
        api.logout()
    except Exception:
        pass
    record = base_record("simulation_futures_place_order_test", args.run_id)
    record.update(
        {
            "test_results": {
                "futures_place_order": {
                    "ok": True,
                    "simulation": True,
                    "started_at": started.isoformat(),
                    "finished_at": now_taipei().isoformat(),
                    "futures_code": args.futures_code,
                    "contract_month": args.contract_month,
                    "quantity": args.quantity,
                    "action": args.action,
                    "price_type": args.price_type,
                    "order_type": args.order_type,
                    "trade_status": str(getattr(trade, "status", "submitted")),
                }
            },
            "side_effects": side_effects(runtime_called=True, login_called=True, order_called=True),
            "ok": True,
            "decision": "sinopac_simulation_futures_place_order_test_completed",
        }
    )
    return record


def write_or_print(payload: dict[str, Any], args: argparse.Namespace) -> None:
    text = stable_json(payload, pretty=args.pretty)
    output = getattr(args, "output", None)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id")
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")


def add_runtime_common(parser: argparse.ArgumentParser) -> None:
    add_common(parser)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--contracts-timeout", type=int, default=10000)
    parser.add_argument("--taiwan-ip-attested", action="store_true")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled Sinopac/Shioaji API test application helper.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-application")
    add_common(build)
    build.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    build.set_defaults(func=build_application)

    health = sub.add_parser("health-check")
    add_common(health)
    health.set_defaults(func=health_check)

    stat = sub.add_parser("status")
    stat.add_argument("--input", required=True)
    stat.add_argument("--pretty", action="store_true")
    stat.set_defaults(func=status)

    login = sub.add_parser("login-test")
    add_runtime_common(login)
    login.set_defaults(func=login_test)

    stock = sub.add_parser("stock-order-test")
    add_runtime_common(stock)
    stock.add_argument("--stock-id", default="2330")
    stock.add_argument("--price", type=float, default=1.0)
    stock.add_argument("--quantity", type=int, default=1)
    stock.add_argument("--action", default="Buy", choices=["Buy", "Sell"])
    stock.add_argument("--price-type", default="LMT")
    stock.add_argument("--order-type", default="ROD")
    stock.add_argument("--min-interval-seconds", type=float, default=1.0)
    stock.set_defaults(func=stock_order_test)

    futures = sub.add_parser("futures-order-test")
    add_runtime_common(futures)
    futures.add_argument("--enable-futures", action="store_true")
    futures.add_argument("--futures-code", default="TXF")
    futures.add_argument("--contract-month", required=True)
    futures.add_argument("--price", type=float, default=1.0)
    futures.add_argument("--quantity", type=int, default=1)
    futures.add_argument("--action", default="Buy", choices=["Buy", "Sell"])
    futures.add_argument("--price-type", default="LMT")
    futures.add_argument("--order-type", default="ROD")
    futures.add_argument("--min-interval-seconds", type=float, default=1.0)
    futures.set_defaults(func=futures_order_test)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        write_or_print(args.func(args), args)
        return 0
    except SafetyGateError as exc:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "generated_at": now_taipei().isoformat(),
            "mode": "blocked_by_safety_gate",
            "ok": False,
            "decision": "sinopac_api_test_blocked_by_safety_gate",
            "error": str(exc),
            "safety": dict(SAFETY),
            "side_effects": side_effects(),
        }
        print(stable_json(payload, pretty=True), end="", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
