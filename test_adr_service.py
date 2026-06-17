from app.loaders.google_sheet_loader import load_stock_ids
from app.market.adr_service import get_adr_result


stock_ids = load_stock_ids()

print("===== ADR SERVICE TEST =====")

for stock_id in stock_ids:
    adr = get_adr_result(stock_id)

    if adr is None:
        print(f"{stock_id}：No ADR")
        continue

    print("--------------------")
    print(f"Stock ID : {stock_id}")
    print(f"ADR      : {adr['symbol']}")
    print(f"Close    : {adr['close']}")
    print(f"Change   : {adr['change_rate']}%")
    print(f"Signal   : {adr['signal']}")
