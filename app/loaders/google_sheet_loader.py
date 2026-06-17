import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def load_stock_ids(
    key_file="stock-ai-key.json",
    sheet_name="stockviewer",
):
    creds = Credentials.from_service_account_file(
        key_file,
        scopes=SCOPES,
    )

    client = gspread.authorize(creds)
    sheet = client.open(sheet_name)
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
