"""Order adapter interface with dry-run safety gates."""

from __future__ import annotations

from app.trading.broker_capability import OrderCapability
from app.trading.risk_gate import (
    assert_explicit_simulation_approval,
    assert_no_production_order,
    validate_order_proposal,
    validate_risk_limits,
)
from app.trading.schemas import (
    OrderProposal,
    ProductionOrderRequest,
    RiskLimits,
    SimulationOrderRequest,
)


class OrderAdapter:
    def __init__(self, risk_limits: RiskLimits | None = None) -> None:
        self.risk_limits = risk_limits or RiskLimits()

    def capability(self) -> OrderCapability:
        return OrderCapability()

    def validate_proposal(self, proposal: OrderProposal) -> OrderProposal:
        validate_risk_limits(proposal, self.risk_limits)
        return proposal

    def build_proposal_only_result(self, proposal: OrderProposal) -> dict[str, object]:
        self.validate_proposal(proposal)
        return {
            "ok": True,
            "mode": "proposal",
            "accepted_for_execution": False,
            "validated": True,
        }

    def validate_simulation_request(self, request: SimulationOrderRequest) -> dict[str, object]:
        validate_order_proposal(request.proposal)
        assert_explicit_simulation_approval(request)
        validate_risk_limits(request.proposal, self.risk_limits)
        return {
            "ok": True,
            "mode": "simulation",
            "accepted_for_execution": False,
            "validated": True,
            "approval_reference": request.approval_reference,
        }

    def validate_production_request(self, request: ProductionOrderRequest) -> dict[str, object]:
        assert_no_production_order(request)
        return {"ok": False, "mode": "production", "accepted_for_execution": False}

