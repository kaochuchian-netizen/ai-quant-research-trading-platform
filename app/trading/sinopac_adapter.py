"""Read-only Sinopac/Shioaji runtime adapter boundary.

This module may import Shioaji for package availability checks, but it does not
read environment configuration, login, or execute orders.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import asdict, dataclass
from typing import Any

from app.trading.account_adapter import AccountAdapter
from app.trading.broker_capability import AccountCapability, BrokerCapability, OrderCapability, QuoteCapability
from app.trading.quote_adapter import QuoteAdapter
from app.trading.schemas import ProductionOrderRequest, SimulationOrderRequest


class SinopacRuntimeBlocked(RuntimeError):
    """Raised when a blocked runtime action is requested."""


class SinopacLoginBlocked(SinopacRuntimeBlocked):
    """Raised when login is attempted without an explicit future approval path."""


class SinopacOrderBlocked(SinopacRuntimeBlocked):
    """Raised when any order execution path is requested."""


@dataclass(frozen=True)
class ShioajiImportStatus:
    import_available: bool
    version: str | None
    error_class: str | None = None


@dataclass(frozen=True)
class RuntimeCapability:
    broker_name: str
    shioaji_import_available: bool
    shioaji_version: str | None
    quote_adapter_available: bool
    account_adapter_available: bool
    order_adapter_blocked: bool
    login_default_blocked: bool
    simulation_order_blocked: bool
    production_order_blocked: bool


def get_shioaji_version() -> str | None:
    """Return the installed Shioaji package version without broker login."""

    try:
        return importlib.metadata.version("shioaji")
    except importlib.metadata.PackageNotFoundError:
        return None


def check_import_available() -> ShioajiImportStatus:
    """Check whether Shioaji can be imported without constructing a client."""

    try:
        version = get_shioaji_version()
        __import__("shioaji")
    except Exception as exc:
        return ShioajiImportStatus(import_available=False, version=None, error_class=type(exc).__name__)
    return ShioajiImportStatus(import_available=True, version=version)


class SinopacQuoteAdapter(QuoteAdapter):
    """Quote capability skeleton for a future Shioaji-backed runtime."""

    def capability(self) -> QuoteCapability:
        return QuoteCapability(snapshot=True, kbars=True, streaming=False, broker_login_required=True)

    def runtime_ready(self) -> bool:
        return True


class SinopacAccountAdapter(AccountAdapter):
    """Read-only account capability skeleton for a future Shioaji-backed runtime."""

    def capability(self) -> AccountCapability:
        return AccountCapability(status=True, positions_read_only=True, balances_read_only=True, broker_login_required=True)

    def runtime_ready(self) -> bool:
        return True


def build_runtime_capability(import_status: ShioajiImportStatus | None = None) -> RuntimeCapability:
    """Build the read-only runtime capability declaration."""

    status = import_status or check_import_available()
    return RuntimeCapability(
        broker_name="sinopac_shioaji",
        shioaji_import_available=status.import_available,
        shioaji_version=status.version,
        quote_adapter_available=True,
        account_adapter_available=True,
        order_adapter_blocked=True,
        login_default_blocked=True,
        simulation_order_blocked=True,
        production_order_blocked=True,
    )


def build_broker_capability() -> BrokerCapability:
    """Build the gateway-facing broker capability with order execution blocked."""

    return BrokerCapability(
        broker_name="sinopac_shioaji",
        quote=SinopacQuoteAdapter().capability(),
        account=SinopacAccountAdapter().capability(),
        order=OrderCapability(
            proposal_only=True,
            simulation_supported=False,
            simulation_default_blocked=True,
            production_supported=False,
            production_always_blocked=True,
        ),
    )


class SinopacRuntimeAdapter:
    """Read-only Sinopac runtime adapter bundle.

    Login is present as an explicit future boundary. AI-DEV-118 keeps runtime
    login blocked and does not accept credentials.
    """

    def __init__(
        self,
        quote_adapter: SinopacQuoteAdapter | None = None,
        account_adapter: SinopacAccountAdapter | None = None,
    ) -> None:
        self.quote_adapter = quote_adapter or SinopacQuoteAdapter()
        self.account_adapter = account_adapter or SinopacAccountAdapter()
        self.capability = build_broker_capability()

    def runtime_capability(self) -> RuntimeCapability:
        return build_runtime_capability()

    def login(self, *, explicit_approval: bool = False) -> None:
        if not explicit_approval:
            raise SinopacLoginBlocked("Sinopac login is blocked by default")
        raise SinopacLoginBlocked("Sinopac login execution is outside AI-DEV-118")

    def submit_simulation_order(self, request: SimulationOrderRequest | None = None) -> None:
        raise SinopacOrderBlocked("Sinopac simulation order execution is blocked")

    def submit_production_order(self, request: ProductionOrderRequest | None = None) -> None:
        raise SinopacOrderBlocked("Sinopac production order execution is blocked")

    def as_dict(self) -> dict[str, Any]:
        return {
            "runtime_capability": asdict(self.runtime_capability()),
            "broker_capability": asdict(self.capability),
        }


def build_runtime_adapter() -> SinopacRuntimeAdapter:
    return SinopacRuntimeAdapter()
