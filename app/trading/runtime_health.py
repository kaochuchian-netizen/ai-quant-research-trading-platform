"""Trading runtime health summary for the read-only Sinopac adapter."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from app.trading.sinopac_adapter import build_runtime_capability, check_import_available


RuntimeHealthStatus = Literal["runtime_ready", "runtime_degraded", "runtime_failed"]


def compute_runtime_status(summary: dict[str, object]) -> RuntimeHealthStatus:
    required_safety = [
        "order_adapter_blocked",
        "login_default_blocked",
        "simulation_order_blocked",
        "production_order_blocked",
    ]
    safety_ok = all(summary.get(name) is True for name in required_safety)
    adapter_ok = summary.get("quote_adapter_available") is True and summary.get("account_adapter_available") is True
    if summary.get("shioaji_installed") is True and adapter_ok and safety_ok:
        return "runtime_ready"
    if adapter_ok and safety_ok:
        return "runtime_degraded"
    return "runtime_failed"


def build_trading_runtime_health() -> dict[str, object]:
    import_status = check_import_available()
    capability = build_runtime_capability(import_status)
    summary: dict[str, object] = {
        "schema_version": "sinopac_runtime_health_v1",
        "broker_name": capability.broker_name,
        "shioaji_installed": import_status.import_available,
        "shioaji_version": import_status.version,
        "shioaji_error_class": import_status.error_class,
        "quote_adapter_available": capability.quote_adapter_available,
        "account_adapter_available": capability.account_adapter_available,
        "order_adapter_blocked": capability.order_adapter_blocked,
        "login_default_blocked": capability.login_default_blocked,
        "simulation_order_blocked": capability.simulation_order_blocked,
        "production_order_blocked": capability.production_order_blocked,
        "capability": asdict(capability),
        "side_effects": {
            "read_env": False,
            "broker_login_called": False,
            "simulation_order_called": False,
            "production_order_called": False,
            "notification_sent": False,
            "scheduler_modified": False,
            "database_modified": False,
            "strategy_signal_connected": False,
        },
    }
    summary["status"] = compute_runtime_status(summary)
    summary["ok"] = summary["status"] in {"runtime_ready", "runtime_degraded"} and not any(
        bool(value) for value in summary["side_effects"].values()
    )
    return summary
