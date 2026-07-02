"""Broker capability declarations for the trading gateway boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteCapability:
    snapshot: bool = True
    kbars: bool = True
    streaming: bool = False
    broker_login_required: bool = True


@dataclass(frozen=True)
class AccountCapability:
    status: bool = True
    positions_read_only: bool = True
    balances_read_only: bool = True
    broker_login_required: bool = True


@dataclass(frozen=True)
class OrderCapability:
    proposal_only: bool = True
    simulation_supported: bool = True
    simulation_default_blocked: bool = True
    production_supported: bool = False
    production_always_blocked: bool = True


@dataclass(frozen=True)
class BrokerCapability:
    broker_name: str = "sinopac_shioaji"
    quote: QuoteCapability = QuoteCapability()
    account: AccountCapability = AccountCapability()
    order: OrderCapability = OrderCapability()


def sinopac_shioaji_capability() -> BrokerCapability:
    return BrokerCapability()

