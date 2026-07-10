import gspread
from google.oauth2.service_account import Credentials


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
