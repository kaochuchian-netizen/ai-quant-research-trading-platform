import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

creds = Credentials.from_service_account_file(
    "stock-ai-key.json",
    scopes=SCOPES
)

client = gspread.authorize(creds)

sheet = client.open("stockviewer")

worksheet = sheet.sheet1

rows = worksheet.get_all_values()

print("===== 股票清單 =====")

for row in rows[1:]:
    stock_id = row[0]
    print(stock_id)
