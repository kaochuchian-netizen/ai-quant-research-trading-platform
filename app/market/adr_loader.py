import yfinance as yf


def get_adr_change(symbol):

    ticker = yf.Ticker(symbol)

    hist = ticker.history(period="5d")

    if len(hist) < 2:
        raise Exception(
            f"Not enough data for {symbol}"
        )

    latest = hist["Close"].iloc[-1]
    previous = hist["Close"].iloc[-2]

    change_rate = (
        (latest - previous)
        / previous
        * 100
    )

    return {
        "symbol": symbol,
        "close": round(float(latest), 2),
        "change_rate": round(
            float(change_rate),
            2
        )
    }
