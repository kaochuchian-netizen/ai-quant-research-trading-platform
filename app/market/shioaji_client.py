import os
import re
from functools import lru_cache

from app.config.settings import settings


def classify_transport_failure(exc):
    message = str(exc).lower()
    exc_name = type(exc).__name__.lower()
    status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(exc, "status_code", None)
    if "gaierror" in exc_name or "getaddrinfo" in message or "name or service not known" in message or "nodename nor servname" in message or "dns" in message:
        return "dns_failure"
    if "connectionerror" in exc_name or "connection refused" in message or "failed to establish a new connection" in message or "connect timeout" in message or "connection timed out" in message:
        return "connect_failure"
    if "timeout" in exc_name or "timed out" in message or "read timeout" in message:
        return "connect_timeout"
    if status_code is not None or re.search(r"\bhttp\s*(status|code)?\s*[45]\d\d\b", message):
        return "http_failure"
    if "transporterror" in exc_name or "response code" in message or "solace" in message or "kbars" in message:
        return "provider_api_failure"
    return "unknown_transport_failure"


def transport_failure_evidence(exc, *, provider="shioaji", stage="market_data"):
    kind = classify_transport_failure(exc)
    message = str(exc)
    return {
        "schema_version": "tw_market_data_transport_failure_evidence_v1",
        "provider": provider,
        "stage": stage,
        "failure_kind": kind,
        "exception_type": type(exc).__name__,
        "message": message[:240],
        "dns_failure": kind == "dns_failure",
        "connect_failure": kind in {"connect_failure", "connect_timeout"},
        "http_failure": kind == "http_failure",
        "provider_api_failure": kind == "provider_api_failure",
        "secret_values_printed": False,
        "trading_or_order_executed": False,
    }


def classify_shioaji_error(exc):
    message = str(exc).lower()
    transport_kind = classify_transport_failure(exc)
    if transport_kind != "unknown_transport_failure":
        return f"shioaji_{transport_kind}"
    if "no module named" in message and "shioaji" in message:
        return "shioaji_dependency_unavailable"
    if "maintenance" in message or "maintain" in message:
        return "shioaji_maintenance"
    if "version" in message or "upgrade" in message or "update" in message:
        return "shioaji_version_or_upgrade_required"
    if "login" in message or "authentication" in message or "api_key" in message or "secret" in message:
        return "shioaji_login_failed"
    if "kbars" in message or "30" in message or "range" in message:
        return "shioaji_kbars_range_or_history_limit"
    return "shioaji_runtime_error"


class ShioajiClientError(RuntimeError):
    def __init__(self, message, classification="shioaji_runtime_error"):
        super().__init__(message)
        self.classification = classification


def _contracts_timeout_ms():
    raw = os.environ.get("STOCK_AI_SHIOAJI_CONTRACTS_TIMEOUT_MS", "15000")
    try:
        value = int(raw)
    except ValueError:
        value = 15000
    return max(3000, min(value, 30000))


@lru_cache(maxsize=1)
def get_api():
    try:
        import shioaji as sj
    except Exception as exc:
        classification = classify_shioaji_error(exc)
        raise ShioajiClientError(
            f"Shioaji import failed before market-data fetch ({classification})",
            classification=classification,
        ) from exc

    api = sj.Shioaji(simulation=True)

    try:
        api.login(
            api_key=settings.SINOPAC_API_KEY,
            secret_key=settings.SINOPAC_SECRET_KEY,
            contracts_timeout=_contracts_timeout_ms(),
        )
    except Exception as exc:
        classification = classify_shioaji_error(exc)
        raise ShioajiClientError(
            f"Shioaji login failed before market-data fetch ({classification})",
            classification=classification,
        ) from exc
    return api


def get_snapshots(stock_ids):
    api = get_api()

    contracts = []
    for stock_id in stock_ids:
        contract = api.Contracts.Stocks[str(stock_id)]
        contracts.append(contract)

    snapshots = api.snapshots(contracts)

    return snapshots
