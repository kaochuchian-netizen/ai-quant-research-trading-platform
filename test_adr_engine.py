from app.market.adr_mapper import get_adr_symbol
from app.market.adr_loader import get_adr_change
from app.market.adr_analyzer import judge_adr_signal


stock_id = "2330"

symbol = get_adr_symbol(stock_id)

if not symbol:
    print("No ADR mapping found")
    exit()

result = get_adr_change(symbol)

signal = judge_adr_signal(
    result["change_rate"]
)

print("===== ADR TEST =====")
print(f"Stock ID : {stock_id}")
print(f"ADR      : {symbol}")
print(f"Close    : {result['close']}")
print(f"Change   : {result['change_rate']}%")
print(f"Signal   : {signal}")
