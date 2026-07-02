"""Quote adapter interface for future broker-backed implementations."""

from __future__ import annotations

from app.trading.broker_capability import QuoteCapability
from app.trading.schemas import KbarsRequest, SnapshotRequest


class QuoteAdapter:
    def capability(self) -> QuoteCapability:
        return QuoteCapability()

    def validate_snapshot_request(self, request: SnapshotRequest) -> SnapshotRequest:
        if not request.symbols:
            raise ValueError("at least one symbol is required")
        for symbol in request.symbols:
            if not symbol.strip():
                raise ValueError("snapshot symbols must be non-empty")
        return request

    def validate_kbars_request(self, request: KbarsRequest) -> KbarsRequest:
        if not request.symbol.strip():
            raise ValueError("kbars symbol is required")
        if request.start > request.end:
            raise ValueError("kbars start date must not be after end date")
        return request

