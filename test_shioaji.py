import os
import shioaji as sj
from dotenv import load_dotenv

# 讀取 .env
load_dotenv()

api_key = os.getenv("SINOPAC_API_KEY")
secret_key = os.getenv("SINOPAC_SECRET_KEY")

if not api_key or not secret_key:
    raise RuntimeError("找不到 API KEY 或 SECRET KEY")

print("開始登入永豐 API...")

# 建立 API 物件
api = sj.Shioaji(simulation=True)

# 登入
accounts = api.login(
    api_key=api_key,
    secret_key=secret_key,
    contracts_timeout=10000
)

print("登入成功")
print(accounts)

# ===== 測試抓股票 =====

stock_id = "2330"

print(f"\n開始查詢股票：{stock_id}")

contract = api.Contracts.Stocks[stock_id]

# 取得 snapshot
snapshot = api.snapshots([contract])[0]

print("\n===== 股票資訊 =====")
print("股票代號:", stock_id)
print("股票名稱:", contract.name)
print("最新價:", snapshot.close)
print("開盤價:", snapshot.open)
print("最高價:", snapshot.high)
print("最低價:", snapshot.low)
print("成交量:", snapshot.volume)

# 登出
api.logout()

print("\nAPI 已登出")
