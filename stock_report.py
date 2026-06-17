import os
from datetime import datetime

import shioaji as sj
import requests
from dotenv import load_dotenv
from app.loaders.google_sheet_loader import load_stock_ids

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GOOGLE_KEY_FILE = os.getenv(
    "GOOGLE_KEY_FILE",
    os.path.join(BASE_DIR, "stock-ai-key.json")
)

SHEET_NAME = os.getenv("SHEET_NAME", "stockviewer")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "工作表1")

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

SHIOAJI_API_KEY = os.getenv("SINOPAC_API_KEY")
SHIOAJI_SECRET_KEY = os.getenv("SINOPAC_SECRET_KEY")



def login_shioaji():
    api = sj.Shioaji(simulation=True)

    api.login(
        api_key=SHIOAJI_API_KEY,
        secret_key=SHIOAJI_SECRET_KEY
    )

    return api


def get_stock_snapshot(api, stock_id):
    contract = api.Contracts.Stocks[stock_id]
    snapshots = api.snapshots([contract])

    if not snapshots:
        return None

    return snapshots[0]


def build_report(stock_ids, snapshots):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("AI 股票行情報告")
    lines.append(f"時間：{now}")
    lines.append("")
    lines.append("追蹤清單：")

    for stock_id in stock_ids:
        snapshot = snapshots.get(stock_id)

        if snapshot is None:
            lines.append(f"{stock_id}：查無資料")
            continue

        lines.append(
            f"{stock_id}｜"
            f"現價 {snapshot.close}｜"
            f"漲跌 {snapshot.change_price}｜"
            f"漲跌幅 {snapshot.change_rate}%｜"
            f"成交量 {snapshot.total_volume}"
        )

    lines.append("")
    lines.append("備註：目前為 Shioaji snapshot 行情，尚未接 AI 分析。")

    return "\n".join(lines)


def push_line_message(message):
    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)

    print("LINE status:", response.status_code)
    print("LINE response:", response.text)

    response.raise_for_status()


def main():
    stock_ids = load_stock_ids(
    key_file=GOOGLE_KEY_FILE,
    sheet_name=SHEET_NAME,
    )
    print("股票清單：", stock_ids)

    api = login_shioaji()

    snapshots = {}

    for stock_id in stock_ids:
        try:
            snapshot = get_stock_snapshot(api, stock_id)
            snapshots[stock_id] = snapshot
            print(f"{stock_id} OK")
        except Exception as e:
            snapshots[stock_id] = None
            print(f"{stock_id} ERROR:", e)

    report = build_report(stock_ids, snapshots)

    print("\n===== 報告內容 =====")
    print(report)

    push_line_message(report)

    api.logout()


if __name__ == "__main__":
    main()
