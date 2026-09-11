#!/usr/bin/env python3
"""Deterministic AI-DEV-239 Google Sheets retry resilience gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.loaders import google_sheet_loader as loader
from app.reports.tw_pre_open_delivery_contract import universe_eligibility


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class FakeAPIError(Exception):
    def __init__(self, status_code: int, message: str = "provider error"):
        super().__init__(f"[{status_code}]: {message}")
        self.response = FakeResponse(status_code)


class FakeTransportError(Exception):
    pass


class FakeCredentialError(Exception):
    pass


class FakeWorksheetNotFound(Exception):
    def __init__(self):
        super().__init__("[404]: worksheet not found")
        self.response = FakeResponse(404)


class FakeWorksheet:
    def __init__(self, rows: list[list[str]]):
        self.rows = rows

    def get_all_values(self) -> list[list[str]]:
        return self.rows

    def get_all_records(self) -> list[dict[str, str]]:
        headers = self.rows[0]
        return [dict(zip(headers, row)) for row in self.rows[1:]]


class FakeSheet:
    def __init__(self, rows: list[list[str]]):
        self.sheet1 = FakeWorksheet(rows)

    def worksheet(self, _name: str) -> FakeWorksheet:
        return self.sheet1


class FakeClient:
    def __init__(self, failures: list[Exception], rows: list[list[str]]):
        self.failures = list(failures)
        self.rows = rows
        self.open_calls = 0

    def open(self, _name: str) -> FakeSheet:
        self.open_calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return FakeSheet(self.rows)


class FakeCredentials:
    @staticmethod
    def from_service_account_file(_key_file: str, scopes: list[str]) -> object:
        return {"scopes": scopes}


def check(value: object, name: str, checks: list[dict[str, object]], detail: object = None) -> None:
    ok = bool(value)
    item: dict[str, object] = {"name": name, "ok": ok}
    if detail is not None:
        item["detail"] = detail
    checks.append(item)
    if not ok:
        raise AssertionError(name)


def with_fake_gspread(client: FakeClient, fn):
    original_credentials = loader.Credentials
    original_gspread = loader.gspread
    try:
        loader.Credentials = FakeCredentials
        loader.gspread = SimpleNamespace(authorize=lambda _creds: client)
        return fn()
    finally:
        loader.Credentials = original_credentials
        loader.gspread = original_gspread


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: list[dict[str, object]] = []

    rows = [["stock_id"], ["2330"], ["3293"]]
    client = FakeClient([FakeAPIError(503, "The service is currently unavailable"), FakeAPIError(503, "The service is currently unavailable")], rows)
    symbols, evidence = with_fake_gspread(client, lambda: loader.load_stock_ids_with_provenance())
    retry_evidence = evidence["google_sheets_retry_evidence"]
    check(symbols == ["2330", "3293"], "Google Sheets succeeds after bounded 503 retry", checks)
    check(client.open_calls == 3, "retry contract uses max 3 total attempts when third attempt succeeds", checks, client.open_calls)
    check(
        all(item.get("provider") == "google_sheets" and item.get("stage") == "historical_csv_update" for item in retry_evidence),
        "structured retry evidence identifies provider and stage",
        checks,
        retry_evidence,
    )
    check(
        [item["attempt"] for item in retry_evidence[:3]] == [1, 2, 3]
        and retry_evidence[0]["http_status"] == 503
        and retry_evidence[0]["retryable"] is True
        and retry_evidence[2]["outcome"] == "success",
        "retry evidence records attempts, http status, retryability and success",
        checks,
    )

    for status in (429, 500, 502, 503, 504):
        calls = {"count": 0}

        def always_fails() -> None:
            calls["count"] += 1
            raise FakeAPIError(status, "retryable")

        try:
            loader._call_google_sheets_provider("validator.retryable_status", always_fails, sleep=lambda _seconds: None)
        except FakeAPIError as exc:
            attempt_evidence = getattr(exc, "google_sheets_retry_evidence", [])
            check(calls["count"] == 3, f"HTTP {status} is retried up to bounded max attempts", checks)
            check(attempt_evidence[-1]["retry_exhausted"] is True, f"HTTP {status} marks retry exhausted", checks)
        else:
            raise AssertionError(f"HTTP {status} must fail after retry exhaustion")

    for exc in (FakeAPIError(403, "permission denied"), FakeAPIError(404, "spreadsheet not found"), FakeCredentialError("bad credentials")):
        calls = {"count": 0}

        def non_retryable() -> None:
            calls["count"] += 1
            raise exc

        try:
            loader._call_google_sheets_provider("validator.non_retryable", non_retryable, sleep=lambda _seconds: None)
        except Exception as raised:
            attempt_evidence = getattr(raised, "google_sheets_retry_evidence", [])
            check(calls["count"] == 1, f"{exc.__class__.__name__}/{loader._google_sheets_http_status(exc)} is not retried", checks)
            check(attempt_evidence[0]["retryable"] is False, "non-retryable evidence is explicit", checks)
        else:
            raise AssertionError("non-retryable error must fail without retry")

    calls = {"count": 0}

    def transient_transport() -> None:
        calls["count"] += 1
        raise FakeTransportError("connection timed out")

    try:
        loader._call_google_sheets_provider("validator.transport", transient_transport, sleep=lambda _seconds: None)
    except FakeTransportError as exc:
        attempt_evidence = getattr(exc, "google_sheets_retry_evidence", [])
        check(calls["count"] == 3 and attempt_evidence[-1]["retry_exhausted"], "transient transport errors are retried and bounded", checks)
    else:
        raise AssertionError("transport error must fail after retry exhaustion")

    schema_client = FakeClient([], [["not_stock_id"], ["台積電"]])
    try:
        with_fake_gspread(schema_client, lambda: loader.load_stock_ids_with_provenance(fallback_loader=lambda: {"stock_ids": []}))
    except RuntimeError:
        check(schema_client.open_calls == 1, "schema/parsing failures are not retried as provider failures", checks)
    else:
        raise AssertionError("empty fallback after schema error must fail closed")

    fallback_client = FakeClient([FakeAPIError(503, "The service is currently unavailable")] * 3, rows)
    symbols, fallback_evidence = with_fake_gspread(
        fallback_client,
        lambda: loader.load_stock_ids_with_provenance(
            fallback_loader=lambda: {
                "stock_ids": ["2330", "3293"],
                "snapshot_id": "tw-0700-admitted",
                "effective_trading_date": "2026-09-10",
                "revision": 4,
                "source_payload_hash": "hash-admitted",
            },
            as_of_date="2026-09-11",
        ),
    )
    eligibility = universe_eligibility({"stock_universe_evidence": fallback_evidence})
    check(symbols == ["2330", "3293"], "admitted fallback can supply bounded degraded universe after retry exhaustion", checks)
    check(fallback_evidence["fallback_used"] is True and fallback_evidence["fallback_snapshot_age"] == 1, "fallback freshness evidence is preserved", checks)
    check(fallback_evidence["google_sheets_retry_evidence"][-1]["retry_exhausted"] is True, "fallback records exhausted Google Sheets retry evidence", checks)
    check(
        eligibility["eligible"] is False
        and eligibility["fallback_used"] is True
        and eligibility["reason"] in {"watchlist_fallback_not_authoritative", "watchlist_drift_unknown"},
        "fallback remains non-authoritative under existing governance limits",
        checks,
        eligibility,
    )

    result = {
        "schema_version": "validate_ai_dev_239_google_sheets_retry_v1",
        "ok": all(item["ok"] for item in checks),
        "passed": sum(bool(item["ok"]) for item in checks),
        "total": len(checks),
        "checks": checks,
        "safety": {
            "production_rerun": False,
            "notification_sent": False,
            "db_or_sheet_write": False,
            "scheduler_mutation": False,
            "trading_executed": False,
            "network_called": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
