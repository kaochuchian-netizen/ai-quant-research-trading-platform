from app.market.adr_mapper import (
    get_adr_symbol
)

from app.market.adr_loader import (
    get_adr_change
)

from app.market.adr_analyzer import (
    judge_adr_signal
)


def get_adr_result(stock_id):

    symbol = get_adr_symbol(stock_id)

    if not symbol:
        return None

    result = get_adr_change(symbol)

    signal = judge_adr_signal(
        result["change_rate"]
    )

    return {
        "symbol": symbol,
        "close": result["close"],
        "change_rate": result["change_rate"],
        "signal": signal,
    }
