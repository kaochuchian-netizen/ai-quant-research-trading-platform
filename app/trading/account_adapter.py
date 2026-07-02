"""Read-only account adapter interface for future broker-backed implementations."""

from __future__ import annotations

from app.trading.broker_capability import AccountCapability
from app.trading.schemas import AccountStatusRequest, Balance, Position


class AccountAdapter:
    def capability(self) -> AccountCapability:
        return AccountCapability()

    def validate_status_request(self, request: AccountStatusRequest) -> AccountStatusRequest:
        if not request.include_positions and not request.include_balances:
            raise ValueError("account status request must include positions or balances")
        return request

    def normalize_positions(self, positions: tuple[Position, ...]) -> tuple[Position, ...]:
        for position in positions:
            if not position.read_only:
                raise ValueError("positions must be read-only")
        return positions

    def normalize_balances(self, balances: tuple[Balance, ...]) -> tuple[Balance, ...]:
        for balance in balances:
            if not balance.read_only:
                raise ValueError("balances must be read-only")
        return balances

