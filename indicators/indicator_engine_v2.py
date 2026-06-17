import pandas as pd


def load_daily_price(csv_path):
    df = pd.read_csv(csv_path)

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    return df


def calculate_ma(df):
    df["ma5"] = df["close"].rolling(window=5).mean()
    df["ma20"] = df["close"].rolling(window=20).mean()
    df["ma60"] = df["close"].rolling(window=60).mean()

    return df

def calculate_rsi(df, period=14):
    delta = df["close"].diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    df["rsi14"] = 100 - (100 / (1 + rs))

    return df

def calculate_macd(df):
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()

    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    return df

def calculate_bollinger_bands(df, period=20):
    middle = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()

    df["bb_middle"] = middle
    df["bb_upper"] = middle + 2 * std
    df["bb_lower"] = middle - 2 * std

    return df

def calculate_volume_ma(df):
    df["volume_ma5"] = df["volume"].rolling(window=5).mean()
    df["volume_ma20"] = df["volume"].rolling(window=20).mean()

    return df

def judge_momentum_signal(latest):
    rsi = latest["rsi14"]

    if rsi >= 70:
        return "overheated"
    if rsi >= 60:
        return "healthy_bullish"
    if rsi >= 50:
        return "slightly_bullish"
    if rsi >= 40:
        return "neutral_weak"
    return "bearish"


def judge_macd_signal(latest):
    macd = latest["macd"]
    signal = latest["macd_signal"]
    hist = latest["macd_hist"]

    if macd > 0 and hist > 0:
        return "bullish_expanding"

    if macd > 0 and hist < 0:
        return "positive_but_weakening"

    if macd < 0 and hist > 0:
        return "recovering"

    if macd < 0 and hist < 0:
        return "bearish_expanding"

    return "neutral"


def judge_bollinger_signal(latest):
    close = latest["close"]
    upper = latest["bb_upper"]
    middle = latest["bb_middle"]
    lower = latest["bb_lower"]

    if close > upper:
        return "above_upper_band"

    if close > middle:
        return "upper_half"

    if close < lower:
        return "below_lower_band"

    if close < middle:
        return "lower_half"

    return "middle_band"


def judge_volume_signal(latest):
    volume = latest["volume"]
    volume_ma5 = latest["volume_ma5"]
    volume_ma20 = latest["volume_ma20"]

    if volume > volume_ma5 * 1.5 and volume > volume_ma20 * 1.5:
        return "breakout_volume"

    if volume > volume_ma5 and volume > volume_ma20:
        return "above_average_volume"

    if volume < volume_ma5 * 0.7 and volume < volume_ma20 * 0.7:
        return "low_volume"

    return "normal_volume"

def calculate_score(latest):
    bullish_score = 0
    risk_score = 0

    trend = judge_trend(latest)
    momentum = judge_momentum_signal(latest)
    macd = judge_macd_signal(latest)
    bollinger = judge_bollinger_signal(latest)
    volume = judge_volume_signal(latest)

    # Trend
    if trend == "strong_uptrend":
        bullish_score += 30
    elif trend == "uptrend":
        bullish_score += 20

    # RSI
    if momentum == "healthy_bullish":
        bullish_score += 15

    elif momentum == "slightly_bullish":
        bullish_score += 10

    elif momentum == "overheated":
        bullish_score += 10
        risk_score += 20

    # MACD

    if macd == "bullish_expanding":
        bullish_score += 20

    elif macd == "positive_but_weakening":
        bullish_score += 10
        risk_score += 10

    elif macd == "bearish_expanding":
        risk_score += 20

    # Bollinger

    if bollinger == "above_upper_band":
        bullish_score += 10
        risk_score += 15

    # Volume

    if volume == "breakout_volume":
        bullish_score += 20

    elif volume == "above_average_volume":
        bullish_score += 10

    return {
        "bullish_score": bullish_score,
        "risk_score": risk_score
    }


def judge_rating(score):
    bullish = score["bullish_score"]
    risk = score["risk_score"]

    if bullish >= 70 and risk <= 30:
        return "strong_bullish"

    if bullish >= 50:
        return "bullish"

    if bullish >= 30:
        return "neutral"

    return "bearish"

def judge_trend(latest):
    close = latest["close"]
    ma5 = latest["ma5"]
    ma20 = latest["ma20"]
    ma60 = latest["ma60"]

    if close > ma5 > ma20 > ma60:
        return "strong_uptrend"

    if close > ma20 and ma5 > ma20:
        return "uptrend"

    if close < ma5 < ma20 < ma60:
        return "strong_downtrend"

    if close < ma20 and ma5 < ma20:
        return "downtrend"

    return "sideways"


def build_indicator_result(stock_id, csv_path):
    df = load_daily_price(csv_path)
    df = calculate_ma(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)
    df = calculate_volume_ma(df)

    latest = df.iloc[-1]

    score = calculate_score(latest)

    result = {
        "stock_id": stock_id,
        "date": latest["date"].strftime("%Y-%m-%d"),
        "close": round(float(latest["close"]), 2),
        "ma":
 {
            "ma5": round(float(latest["ma5"]), 2),
            "ma20": round(float(latest["ma20"]), 2),
            "ma60": round(float(latest["ma60"]), 2),
        },
        "rsi": {
            "rsi14": round(float(latest["rsi14"]), 2),
        },

        "macd": {
            "macd": round(float(latest["macd"]), 2),
            "signal": round(float(latest["macd_signal"]), 2),
            "hist": round(float(latest["macd_hist"]), 2),
        },

        "bollinger": {
            "upper": round(float(latest["bb_upper"]), 2),
            "middle": round(float(latest["bb_middle"]), 2),
            "lower": round(float(latest["bb_lower"]), 2),
        },

        "volume": {
            "volume": int(latest["volume"]),
            "volume_ma5": round(float(latest["volume_ma5"]), 2),
            "volume_ma20": round(float(latest["volume_ma20"]), 2),
        },

        "trend": judge_trend(latest),

        "signals": {
            "trend_signal": judge_trend(latest),
            "momentum_signal": judge_momentum_signal(latest),
            "macd_signal": judge_macd_signal(latest),
            "bollinger_signal": judge_bollinger_signal(latest),
            "volume_signal": judge_volume_signal(latest),
        },

        "score": {
            "bullish_score": score["bullish_score"],
            "risk_score": score["risk_score"],
            "overall_rating": judge_rating(score)
        },


    }

    return result
