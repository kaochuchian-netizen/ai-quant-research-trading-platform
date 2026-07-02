"""Typed request and response schemas for the trading gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal


Market = Literal["TSE", "OTC", "EMERGING", "UNKNOWN"]
OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
TradingMode = Literal["proposal", "simulation", "production"]
TimeInForce = Literal["rod", "ioc", "fok"]


@dataclass(frozen=True)
class SnapshotRequest:
    symbols: tuple[str, ...]
    market: Market = "UNKNOWN"
    include_odd_lot: bool = False


@dataclass(frozen=True)
class KbarsRequest:
    symbol: str
    start: date
    end: date
    interval: Literal["1m", "5m", "15m", "30m", "60m", "1d"] = "1d"


@dataclass(frozen=True)
class AccountStatusRequest:
    include_positions: bool = True
    include_balances: bool = True


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: int
    average_price: Decimal | None = None
    market_value: Decimal | None = None
    read_only: bool = True


@dataclass(frozen=True)
class Balance:
    currency: str
    available: Decimal
    settled: Decimal | None = None
    read_only: bool = True


@dataclass(frozen=True)
class OrderProposal:
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = "limit"
    price: Decimal | None = None
    time_in_force: TimeInForce = "rod"
    mode: TradingMode = "proposal"
    reason: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationOrderRequest:
    proposal: OrderProposal
    explicit_approval: bool = False
    approval_reference: str | None = None


@dataclass(frozen=True)
class ProductionOrderRequest:
    proposal: OrderProposal
    explicit_approval: bool = False
    approval_reference: str | None = None


@dataclass(frozen=True)
class RiskLimits:
    max_quantity: int = 1000
    max_notional: Decimal = Decimal("1000000")
    allowed_symbols: tuple[str, ...] = ()
    allowed_sides: tuple[OrderSide, ...] = ("buy", "sell")

