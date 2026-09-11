from datetime import date
from pathlib import Path
import re
import time

import gspread
from google.oauth2.service_account import Credentials


TW_SOURCE_WORKSHEET = "工作表1"
US_SOURCE_WORKSHEET = "工作表2"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

TW_REQUIRED_HEADERS = ("stock_id", "symbol", "代號")
GOOGLE_SHEETS_PROVIDER = "google_sheets"
GOOGLE_SHEETS_STAGE = "historical_csv_update"
GOOGLE_SHEETS_MAX_ATTEMPTS = 3
GOOGLE_SHEETS_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
GOOGLE_SHEETS_BACKOFF_SECONDS = (0.2, 0.4)


class TWWatchlistSchemaError(ValueError):
    """Sanitized schema failure with optional non-sensitive observed symbols."""

    def __init__(self, reason, *, observed_symbols=None):
        super().__init__(reason)
        self.observed_symbols = list(observed_symbols or [])


def _normalize_tw_symbols(values):
    """Preserve Sheet order/leading zeroes and keep the first duplicate."""
    symbols = []
    duplicates = []
    for value in values or []:
        symbol = str(value).strip()
        if not symbol:
            continue
        if symbol in symbols:
            if symbol not in duplicates:
                duplicates.append(symbol)
            continue
        symbols.append(symbol)
    return symbols, duplicates


def _extract_tw_stock_ids(rows):
    """Parse only the required TW symbol column; unrelated headers are ignored."""
    rows = list(rows or [])
    if not rows:
        raise TWWatchlistSchemaError("TW_WATCHLIST_EMPTY_SHEET")
    headers = [str(value).strip() for value in rows[0]]
    matches = [index for index, header in enumerate(headers) if header in TW_REQUIRED_HEADERS]
    if not matches:
        raise TWWatchlistSchemaError("TW_WATCHLIST_STOCK_ID_HEADER_MISSING")
    column = matches[0]
    raw_symbols = [row[column] for row in rows[1:] if len(row) > column]
    symbols, duplicates = _normalize_tw_symbols(raw_symbols)
    if not symbols:
        raise TWWatchlistSchemaError("TW_WATCHLIST_HAS_NO_SYMBOLS")
    return symbols, duplicates


def _google_sheets_http_status(exc):
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None) or getattr(response, "status", None)
    if status is None:
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status is not None:
        try:
            return int(status)
        except (TypeError, ValueError):
            pass
    match = re.search(r"\[(\d{3})\]", str(exc))
    if match:
        return int(match.group(1))
    return None


def _is_transient_google_transport_error(exc):
    name = exc.__class__.__name__.lower()
    module = exc.__class__.__module__.lower()
    text = str(exc).lower()
    if any(token in name for token in ("permission", "credential", "auth", "forbidden", "notfound")):
        return False
    if "google.auth" in module:
        return False
    transport_markers = (
        "timeout", "connectionerror", "connecttimeout", "readtimeout",
        "transporterror", "connection", "temporarily unavailable",
    )
    return (
        any(marker in name for marker in transport_markers)
        or ("requests" in module and any(marker in name for marker in transport_markers))
        or ("urllib3" in module and any(marker in name for marker in transport_markers))
        or any(marker in text for marker in ("timed out", "connection aborted", "temporary failure"))
    )


def _is_retryable_google_sheets_error(exc):
    status = _google_sheets_http_status(exc)
    if status is not None:
        return status in GOOGLE_SHEETS_RETRYABLE_HTTP_STATUS
    return _is_transient_google_transport_error(exc)


def _google_sheets_attempt_evidence(*, attempt, exc=None, retry_exhausted=False, call_site=None, outcome="failure"):
    return {
        "provider": GOOGLE_SHEETS_PROVIDER,
        "stage": GOOGLE_SHEETS_STAGE,
        "attempt": attempt,
        "http_status": _google_sheets_http_status(exc) if exc is not None else None,
        "retryable": _is_retryable_google_sheets_error(exc) if exc is not None else False,
        "retry_exhausted": bool(retry_exhausted),
        "exception_type": exc.__class__.__name__ if exc is not None else None,
        "call_site": call_site,
        "outcome": outcome,
    }


def _call_google_sheets_provider(call_site, operation, *, sleep=None, max_attempts=GOOGLE_SHEETS_MAX_ATTEMPTS):
    sleeper = time.sleep if sleep is None else sleep
    attempts = []
    for attempt in range(1, max_attempts + 1):
        try:
            result = operation()
            attempts.append(_google_sheets_attempt_evidence(attempt=attempt, call_site=call_site, outcome="success"))
            return result, attempts
        except Exception as exc:
            retryable = _is_retryable_google_sheets_error(exc)
            retry_exhausted = retryable and attempt >= max_attempts
            attempts.append(
                _google_sheets_attempt_evidence(
                    attempt=attempt,
                    exc=exc,
                    retry_exhausted=retry_exhausted,
                    call_site=call_site,
                )
            )
            if not retryable or retry_exhausted:
                setattr(exc, "google_sheets_retry_evidence", list(attempts))
                raise
            backoff = GOOGLE_SHEETS_BACKOFF_SECONDS[min(attempt - 1, len(GOOGLE_SHEETS_BACKOFF_SECONDS) - 1)]
            sleeper(backoff)
    raise RuntimeError("unreachable_google_sheets_retry_state")


def _is_missing_worksheet_error(exc):
    status = _google_sheets_http_status(exc)
    return exc.__class__.__name__ == "WorksheetNotFound" or status == 404


def _open_sheet_with_retry(key_file="stock-ai-key.json", sheet_name="stockviewer", *, sleep=None):
    creds = Credentials.from_service_account_file(
        key_file,
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    return _call_google_sheets_provider("gspread.client.open", lambda: client.open(sheet_name), sleep=sleep)


def _open_sheet(key_file="stock-ai-key.json", sheet_name="stockviewer"):
    sheet, _ = _open_sheet_with_retry(key_file=key_file, sheet_name=sheet_name)
    return sheet


def _load_stock_ids_with_retry_evidence(key_file="stock-ai-key.json", sheet_name="stockviewer", *, sleep=None):
    sheet, attempts = _open_sheet_with_retry(key_file=key_file, sheet_name=sheet_name, sleep=sleep)
    worksheet = sheet.sheet1
    rows, read_attempts = _call_google_sheets_provider(
        "worksheet.get_all_values",
        lambda: worksheet.get_all_values(),
        sleep=sleep,
    )
    stock_ids, duplicates = _extract_tw_stock_ids(rows)
    return stock_ids, duplicates, [*attempts, *read_attempts]


def load_stock_ids(
    key_file="stock-ai-key.json",
    sheet_name="stockviewer",
):
    """Backward-compatible Taiwan stock loader.

    Existing Taiwan production flows continue to read the first worksheet / 工作表1.
    """
    stock_ids, _, _ = _load_stock_ids_with_retry_evidence(key_file=key_file, sheet_name=sheet_name)
    return stock_ids


def load_stock_ids_with_provenance(
    key_file="stock-ai-key.json",
    sheet_name="stockviewer",
    *,
    archive_root=None,
    primary_loader=None,
    fallback_loader=None,
    as_of_date=None,
):
    """Load the TW universe once, with a bounded admitted-snapshot fallback.

    The fallback preserves watchlist ownership from the most recent immutable,
    admitted 07:00 snapshot.  It never infers symbols from historical files,
    another market, or another window.
    """
    loader = primary_loader or load_stock_ids
    google_sheets_retry_evidence = []
    try:
        if primary_loader is None:
            stock_ids, duplicate_symbols, google_sheets_retry_evidence = _load_stock_ids_with_retry_evidence(
                key_file=key_file,
                sheet_name=sheet_name,
            )
            stock_ids, duplicate_symbols = _normalize_tw_symbols(stock_ids)
        else:
            stock_ids = loader(key_file=key_file, sheet_name=sheet_name)
            stock_ids, duplicate_symbols = _normalize_tw_symbols(stock_ids)
        source = "google_sheet_tw_watchlist"
        fallback_used = False
        failure_category = None
        source_snapshot_id = None
        source_effective_date = None
        source_revision = None
        source_payload_hash = None
        fallback_snapshot_age = 0
        source_status = "READY"
        current_symbols = list(stock_ids)
    except Exception as exc:
        google_sheets_retry_evidence = list(getattr(exc, "google_sheets_retry_evidence", google_sheets_retry_evidence))
        if fallback_loader is not None:
            fallback = fallback_loader()
        else:
            from app.dashboard.window_snapshot_archive import resolve_snapshots
            from app.dashboard.market_dashboard_alias import payload_hash

            resolved_root = Path(archive_root) if archive_root is not None else Path(__file__).resolve().parents[2] / "artifacts/archive/window_snapshots"
            latest = resolve_snapshots(resolved_root, "TW", "pre_open_0700").latest or {}
            payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
            symbols = payload.get("tracking_symbols")
            if not isinstance(symbols, list):
                summary = payload.get("pre_open_summary") if isinstance(payload.get("pre_open_summary"), dict) else {}
                symbols = summary.get("tracking_symbols")
            fallback = {
                "stock_ids": symbols if isinstance(symbols, list) else [],
                "snapshot_id": latest.get("snapshot_id"),
                "effective_trading_date": latest.get("effective_trading_date"),
                "revision": latest.get("revision"),
                "source_payload_hash": payload_hash(payload) if payload else None,
            }
        observed = getattr(exc, "observed_symbols", None)
        current_symbols, duplicate_symbols = _normalize_tw_symbols(observed or [])
        stock_ids = fallback.get("stock_ids") if isinstance(fallback, dict) else []
        source_snapshot_id = fallback.get("snapshot_id") if isinstance(fallback, dict) else None
        source_effective_date = fallback.get("effective_trading_date") if isinstance(fallback, dict) else None
        source_revision = fallback.get("revision") if isinstance(fallback, dict) else None
        source_payload_hash = fallback.get("source_payload_hash") if isinstance(fallback, dict) else None
        source = "latest_admitted_tw_pre_open_tracking_symbols"
        fallback_used = True
        failure_category = exc.__class__.__name__
        source_status = "DEGRADED_STALE_FALLBACK"
        reference = date.fromisoformat(str(as_of_date)) if as_of_date else date.today()
        try:
            fallback_snapshot_age = max(0, (reference - date.fromisoformat(str(source_effective_date)[:10])).days)
        except (TypeError, ValueError):
            fallback_snapshot_age = None

    normalized, fallback_duplicates = _normalize_tw_symbols(stock_ids)
    duplicate_symbols = list(dict.fromkeys([*duplicate_symbols, *fallback_duplicates]))
    if not normalized:
        raise RuntimeError("TW stock universe unavailable from primary and admitted fallback")
    current_set = set(current_symbols)
    fallback_set = set(normalized) if fallback_used else set()
    drift_known = fallback_used and bool(current_symbols)
    missing_symbols = sorted(current_set - fallback_set) if drift_known else []
    extra_symbols = sorted(fallback_set - current_set) if drift_known else []
    symbol_count_drift = len(normalized) - len(current_symbols) if drift_known else 0 if not fallback_used else None
    return normalized, {
        "source": source,
        "source_status": source_status,
        "fallback_used": fallback_used,
        "fallback_snapshot_age": fallback_snapshot_age,
        "failure_category": failure_category,
        "source_snapshot_id": source_snapshot_id,
        "source_effective_trading_date": source_effective_date,
        "source_revision": source_revision,
        "source_payload_hash": source_payload_hash,
        "current_symbol_count": len(current_symbols) if current_symbols else (len(normalized) if not fallback_used else None),
        "fallback_symbol_count": len(normalized) if fallback_used else 0,
        "symbol_count_drift": symbol_count_drift,
        "symbol_drift_status": "DRIFT_DETECTED" if missing_symbols or extra_symbols or (symbol_count_drift not in (None, 0)) else "NO_DRIFT" if not fallback_used or drift_known else "UNKNOWN",
        "missing_symbols": missing_symbols,
        "extra_symbols": extra_symbols,
        "duplicate_symbols": duplicate_symbols,
        "google_sheets_retry_evidence": google_sheets_retry_evidence,
        "stock_count": len(normalized),
        "market": "TW",
        "window": "pre_open_0700",
    }


def _worksheet_records(sheet, worksheet_name):
    try:
        worksheet, _ = _call_google_sheets_provider(
            "sheet.worksheet",
            lambda: sheet.worksheet(worksheet_name),
        )
    except Exception as exc:
        if worksheet_name == TW_SOURCE_WORKSHEET and _is_missing_worksheet_error(exc):
            worksheet = sheet.sheet1
        else:
            raise
    rows, _ = _call_google_sheets_provider("worksheet.get_all_records", lambda: worksheet.get_all_records())
    return rows


def load_tw_stock_ids(
    key_file="stock-ai-key.json",
    sheet_name="stockviewer",
    worksheet_name=TW_SOURCE_WORKSHEET,
):
    """Load Taiwan stock IDs from 工作表1 only."""
    sheet = _open_sheet(key_file=key_file, sheet_name=sheet_name)
    try:
        worksheet, _ = _call_google_sheets_provider("sheet.worksheet", lambda: sheet.worksheet(worksheet_name))
    except Exception as exc:
        if not _is_missing_worksheet_error(exc):
            raise
        worksheet = sheet.sheet1
    rows, _ = _call_google_sheets_provider("worksheet.get_all_values", lambda: worksheet.get_all_values())
    stock_ids, _ = _extract_tw_stock_ids(rows)
    return stock_ids


def load_us_stock_watchlist(
    key_file="stock-ai-key.json",
    sheet_name="stockviewer",
    worksheet_name=US_SOURCE_WORKSHEET,
):
    """Load normalized US watchlist rows from 工作表2 only.

    The same Google Sheet file is used, but US rows are marked market=US,
    currency=USD by default, and source_kind=google_sheet_us_watchlist.
    """
    from app.us_stock.watchlist import normalize_us_watchlist_rows

    sheet = _open_sheet(key_file=key_file, sheet_name=sheet_name)
    rows = _worksheet_records(sheet, worksheet_name)
    return normalize_us_watchlist_rows(rows, source_sheet=worksheet_name)
