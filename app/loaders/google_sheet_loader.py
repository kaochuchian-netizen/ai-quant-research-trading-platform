import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path


TW_SOURCE_WORKSHEET = "工作表1"
US_SOURCE_WORKSHEET = "工作表2"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


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
    rows = worksheet.get_all_values()

    stock_ids = []

    for row in rows[1:]:
        if not row:
            continue

        stock_id = str(row[0]).strip()

        if not stock_id:
            continue

        stock_ids.append(stock_id)

    return stock_ids


def load_stock_ids_with_provenance(
    key_file="stock-ai-key.json",
    sheet_name="stockviewer",
    *,
    archive_root=None,
    primary_loader=None,
    fallback_loader=None,
):
    """Load the TW universe once, with a bounded admitted-snapshot fallback.

    The fallback preserves watchlist ownership from the most recent immutable,
    admitted 07:00 snapshot.  It never infers symbols from historical files,
    another market, or another window.
    """
    loader = primary_loader or load_stock_ids
    try:
        stock_ids = loader(key_file=key_file, sheet_name=sheet_name)
        source = "google_sheet_tw_watchlist"
        fallback_used = False
        failure_category = None
        source_snapshot_id = None
        source_effective_date = None
        source_revision = None
        source_payload_hash = None
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
        stock_ids = fallback.get("stock_ids") if isinstance(fallback, dict) else []
        source_snapshot_id = fallback.get("snapshot_id") if isinstance(fallback, dict) else None
        source_effective_date = fallback.get("effective_trading_date") if isinstance(fallback, dict) else None
        source_revision = fallback.get("revision") if isinstance(fallback, dict) else None
        source_payload_hash = fallback.get("source_payload_hash") if isinstance(fallback, dict) else None
        source = "latest_admitted_tw_pre_open_tracking_symbols"
        fallback_used = True
        failure_category = exc.__class__.__name__

    normalized = []
    for value in stock_ids or []:
        symbol = str(value).strip()
        if symbol and symbol not in normalized:
            normalized.append(symbol)
    if not normalized:
        raise RuntimeError("TW stock universe unavailable from primary and admitted fallback")
    return normalized, {
        "source": source,
        "fallback_used": fallback_used,
        "failure_category": failure_category,
        "source_snapshot_id": source_snapshot_id,
        "source_effective_trading_date": source_effective_date,
        "source_revision": source_revision,
        "source_payload_hash": source_payload_hash,
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
    rows = _worksheet_records(sheet, worksheet_name)
    stock_ids = []
    for row in rows:
        stock_id = str(row.get("stock_id") or row.get("symbol") or row.get("代號") or "").strip()
        if stock_id:
            stock_ids.append(stock_id)
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
