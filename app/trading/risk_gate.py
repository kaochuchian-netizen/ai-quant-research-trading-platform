"""Safety gates for proposal, simulation, and production order boundaries."""

from __future__ import annotations

from decimal import Decimal

from app.trading.schemas import (
    OrderProposal,
    ProductionOrderRequest,
    RiskLimits,
    SimulationOrderRequest,
)


class TradingGatewaySafetyError(RuntimeError):
    """Raised when a trading gateway safety gate blocks a request."""


class ProductionOrderBlocked(TradingGatewaySafetyError):
    """Raised for all production order requests."""


class SimulationApprovalRequired(TradingGatewaySafetyError):
    """Raised when simulation order approval is missing."""


class OrderProposalInvalid(TradingGatewaySafetyError):
    """Raised when an order proposal is structurally invalid."""


class RiskLimitExceeded(TradingGatewaySafetyError):
    """Raised when a valid proposal violates configured risk limits."""


def assert_no_production_order(request: ProductionOrderRequest | None = None) -> None:
    raise ProductionOrderBlocked("production order requests are always blocked")


def assert_explicit_simulation_approval(request: SimulationOrderRequest) -> None:
    if request.explicit_approval is not True or not request.approval_reference:
        raise SimulationApprovalRequired("simulation order requires explicit same-run approval")


def validate_order_proposal(proposal: OrderProposal) -> None:
    if not proposal.symbol.strip():
        raise OrderProposalInvalid("symbol is required")
    if proposal.quantity <= 0:
        raise OrderProposalInvalid("quantity must be positive")
    if proposal.order_type == "limit" and proposal.price is None:
        raise OrderProposalInvalid("limit order requires price")
    if proposal.price is not None and proposal.price <= Decimal("0"):
        raise OrderProposalInvalid("price must be positive")
    if proposal.mode == "production":
        raise ProductionOrderBlocked("production proposal mode is blocked")


def validate_risk_limits(proposal: OrderProposal, limits: RiskLimits) -> None:
    validate_order_proposal(proposal)
    if proposal.quantity > limits.max_quantity:
        raise RiskLimitExceeded("quantity exceeds risk limit")
    if proposal.side not in limits.allowed_sides:
        raise RiskLimitExceeded("side is not allowed by risk limit")
    if limits.allowed_symbols and proposal.symbol not in limits.allowed_symbols:
        raise RiskLimitExceeded("symbol is not allowed by risk limit")
    if proposal.price is not None:
        notional = proposal.price * Decimal(proposal.quantity)
        if notional > limits.max_notional:
            raise RiskLimitExceeded("notional exceeds risk limit")

