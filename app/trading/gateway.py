"""Offline trading gateway facade.

The facade wires quote, account, and order boundaries without importing a
broker SDK or reading environment configuration.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.trading.account_adapter import AccountAdapter
from app.trading.broker_capability import BrokerCapability, sinopac_shioaji_capability
from app.trading.order_adapter import OrderAdapter
from app.trading.quote_adapter import QuoteAdapter
from app.trading.schemas import (
    AccountStatusRequest,
    KbarsRequest,
    OrderProposal,
    ProductionOrderRequest,
    SimulationOrderRequest,
    SnapshotRequest,
)
from app.trading.sinopac_adapter import SinopacRuntimeAdapter, build_runtime_adapter


@dataclass
class TradingGateway:
    quote_adapter: QuoteAdapter
    account_adapter: AccountAdapter
    order_adapter: OrderAdapter
    capability: BrokerCapability
    runtime_adapter: SinopacRuntimeAdapter | None = None

    @classmethod
    def offline_default(cls) -> "TradingGateway":
        return cls(
            quote_adapter=QuoteAdapter(),
            account_adapter=AccountAdapter(),
            order_adapter=OrderAdapter(),
            capability=sinopac_shioaji_capability(),
        )

    @classmethod
    def with_sinopac_runtime_adapter(cls) -> "TradingGateway":
        runtime_adapter = build_runtime_adapter()
        return cls(
            quote_adapter=runtime_adapter.quote_adapter,
            account_adapter=runtime_adapter.account_adapter,
            order_adapter=OrderAdapter(),
            capability=runtime_adapter.capability,
            runtime_adapter=runtime_adapter,
        )

    def check_quote_capability(self) -> BrokerCapability:
        return self.capability

    def validate_snapshot_request(self, request: SnapshotRequest) -> SnapshotRequest:
        return self.quote_adapter.validate_snapshot_request(request)

    def validate_kbars_request(self, request: KbarsRequest) -> KbarsRequest:
        return self.quote_adapter.validate_kbars_request(request)

    def validate_account_status_request(self, request: AccountStatusRequest) -> AccountStatusRequest:
        return self.account_adapter.validate_status_request(request)

    def validate_order_proposal(self, proposal: OrderProposal) -> dict[str, object]:
        return self.order_adapter.build_proposal_only_result(proposal)

    def validate_simulation_order(self, request: SimulationOrderRequest) -> dict[str, object]:
        return self.order_adapter.validate_simulation_request(request)

    def validate_production_order(self, request: ProductionOrderRequest) -> dict[str, object]:
        return self.order_adapter.validate_production_request(request)
