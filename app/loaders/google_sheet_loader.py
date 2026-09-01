import gspread
from google.oauth2.service_account import Credentials
from datetime import date
from pathlib import Path


TW_SOURCE_WORKSHEET = "工作表1"
US_SOURCE_WORKSHEET = "工作表2"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

TW_REQUIRED_HEADERS = ("stock_id", "symbol", "代號")


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


def _open_sheet(key_file="stock-ai-key.json", sheet_name="stockviewer"):
    creds = Credentials.from_service_account_file(
        key_file,
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    return client.open(sheet_name)


def load_stock_ids(
    key_file="stock-ai-key.json",
    sheet_name="stockviewer",
):
    """Backward-compatible Taiwan stock loader.

    Existing Taiwan production flows continue to read the first worksheet / 工作表1.
    """
    sheet = _open_sheet(key_file=key_file, sheet_name=sheet_name)
    worksheet = sheet.sheet1
    stock_ids, _ = _extract_tw_stock_ids(worksheet.get_all_values())
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
    try:
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
        "stock_count": len(normalized),
        "market": "TW",
        "window": "pre_open_0700",
    }


def _worksheet_records(sheet, worksheet_name):
    try:
        worksheet = sheet.worksheet(worksheet_name)
    except Exception:
        if worksheet_name == TW_SOURCE_WORKSHEET:
            worksheet = sheet.sheet1
        else:
            raise
    return worksheet.get_all_records()


def load_tw_stock_ids(
    key_file="stock-ai-key.json",
    sheet_name="stockviewer",
    worksheet_name=TW_SOURCE_WORKSHEET,
):
    """Load Taiwan stock IDs from 工作表1 only."""
    sheet = _open_sheet(key_file=key_file, sheet_name=sheet_name)
    try:
        worksheet = sheet.worksheet(worksheet_name)
    except Exception:
        worksheet = sheet.sheet1
    stock_ids, _ = _extract_tw_stock_ids(worksheet.get_all_values())
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
