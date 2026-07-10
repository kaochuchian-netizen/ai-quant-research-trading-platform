"""Live US market-data client and deterministic analytics.

yfinance/Yahoo is used as an external market reference, not official company
disclosure. The client normalizes missing fields and never fabricates prices.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

TAIPEI = ZoneInfo("Asia/Taipei")

def now_taipei() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()

def clean_number(value: Any) -> float | int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        number = float(value)
    except Exception:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, 4)

def pct(value: float | None) -> float | None:
    return round(value * 100, 4) if value is not None else None

def latest_value(series: pd.Series) -> float | None:
    if series is None or series.empty:
        return None
    return clean_number(series.dropna().iloc[-1]) if not series.dropna().empty else None

def rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close.dropna()) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    value = 100 - (100 / (1 + rs))
    return latest_value(value)

def macd(close: pd.Series) -> dict[str, float | None]:
    if len(close.dropna()) < 35:
        return {"macd": None, "signal": None, "histogram": None}
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    line = ema12 - ema26
    signal = line.ewm(span=9, adjust=False).mean()
    hist = line - signal
    return {"macd": latest_value(line), "signal": latest_value(signal), "histogram": latest_value(hist)}

def bollinger(close: pd.Series, period: int = 20) -> dict[str, float | None]:
    if len(close.dropna()) < period:
        return {"upper": None, "middle": None, "lower": None}
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return {"upper": latest_value(mid + 2 * std), "middle": latest_value(mid), "lower": latest_value(mid - 2 * std)}

def true_range_percent(history: pd.DataFrame) -> float | None:
    if len(history) < 20:
        return None
    high, low, close = history["High"], history["Low"], history["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high-low).abs(), (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    pct_series = tr / close.replace(0, np.nan)
    return latest_value(pct_series.rolling(20).median())

def classify_trend(close: pd.Series, ma: pd.Series, lookback: int) -> str:
    if len(close.dropna()) < lookback or ma.dropna().empty:
        return "insufficient_data"
    latest = latest_value(close)
    latest_ma = latest_value(ma)
    prior_ma = clean_number(ma.dropna().iloc[-min(lookback, len(ma.dropna()))]) if len(ma.dropna()) >= 2 else None
    if latest is None or latest_ma is None or prior_ma is None:
        return "insufficient_data"
    ret = (latest / float(close.dropna().iloc[-lookback]) - 1) if len(close.dropna()) >= lookback else 0
    slope = latest_ma - prior_ma
    if latest > latest_ma and slope > 0 and ret > 0:
        return "bullish"
    if latest < latest_ma and slope < 0 and ret < 0:
        return "bearish"
    return "neutral"

def analyze_history(history: pd.DataFrame) -> dict[str, Any]:
    if history is None or history.empty or "Close" not in history:
        return {"ok": False, "reason": "missing_history", "indicators": {}, "data_quality": {"history_days": 0}}
    history = history.dropna(how="all")
    close = history["Close"].astype(float)
    high = history["High"].astype(float)
    low = history["Low"].astype(float)
    volume = history["Volume"].astype(float) if "Volume" in history else pd.Series(dtype=float)
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    bb = bollinger(close)
    macd_values = macd(close)
    atr_pct = true_range_percent(history)
    daily_range_pct = latest_value(((high - low) / close.replace(0, np.nan)).rolling(20).median()) if len(close) >= 20 else None
    vol_pct = latest_value(np.log(close / close.shift(1)).rolling(20).std()) if len(close) >= 20 else None
    latest_close = latest_value(close)
    latest_high = latest_value(high)
    latest_low = latest_value(low)
    range_position = None
    if latest_close is not None and latest_high is not None and latest_low is not None and latest_high != latest_low:
        range_position = round((latest_close - latest_low) / (latest_high - latest_low), 4)
    indicators = {
        "latest_close": latest_close,
        "ma5": latest_value(ma5),
        "ma20": latest_value(ma20),
        "ma60": latest_value(ma60),
        "rsi14": rsi(close),
        "macd": macd_values["macd"],
        "macd_signal": macd_values["signal"],
        "macd_histogram": macd_values["histogram"],
        "bollinger_upper": bb["upper"],
        "bollinger_middle": bb["middle"],
        "bollinger_lower": bb["lower"],
        "volume_ma5": latest_value(volume.rolling(5).mean()) if not volume.empty else None,
        "volume_ma20": latest_value(volume.rolling(20).mean()) if not volume.empty else None,
        "range_position": range_position,
        "atr_like_range_pct": clean_number(atr_pct),
        "daily_range_pct": clean_number(daily_range_pct),
        "return_volatility_pct": clean_number(vol_pct),
    }
    trend_1m = classify_trend(close, ma20, min(20, len(close.dropna())))
    trend_3m = classify_trend(close, ma60, min(60, len(close.dropna()))) if len(close.dropna()) >= 60 else "insufficient_data"
    rsi_value = indicators["rsi14"]
    macd_hist = indicators["macd_histogram"]
    score = 50
    if trend_1m == "bullish": score += 12
    if trend_1m == "bearish": score -= 12
    if trend_3m == "bullish": score += 8
    if trend_3m == "bearish": score -= 8
    if rsi_value is not None:
        if 45 <= rsi_value <= 65: score += 5
        elif rsi_value > 75: score -= 8
        elif rsi_value < 30: score -= 4
    if macd_hist is not None:
        score += 5 if macd_hist > 0 else -5
    score = max(0, min(100, score))
    volatility_state = "insufficient_data"
    if atr_pct is not None:
        volatility_state = "high" if atr_pct > 0.04 else "medium" if atr_pct > 0.02 else "low"
    return {
        "ok": len(close.dropna()) >= 20,
        "indicators": indicators,
        "technical_score": score,
        "technical_summary": f"MA/RSI/MACD/Bollinger computed from {len(close.dropna())} daily OHLCV rows.",
        "trend_1m": trend_1m,
        "trend_3m": trend_3m,
        "volatility_state": volatility_state,
        "data_quality": {"history_days": int(len(close.dropna())), "minimum_prediction_days": 20, "sufficient_for_prediction": len(close.dropna()) >= 20},
    }

@dataclass
class FetchResult:
    symbol: str
    ok: bool
    quote: dict[str, Any]
    history: pd.DataFrame | None
    news: list[dict[str, Any]]
    error: str | None = None

class YFinanceUSClient:
    def __init__(self) -> None:
        self._ticker_cache: dict[str, Any] = {}

    def _ticker(self, symbol: str) -> Any:
        if symbol not in self._ticker_cache:
            self._ticker_cache[symbol] = yf.Ticker(symbol)
        return self._ticker_cache[symbol]

    def fetch_symbol(self, symbol: str, period: str = "1y") -> FetchResult:
        try:
            ticker = self._ticker(symbol)
            fast = getattr(ticker, "fast_info", {}) or {}
            info = {}
            try:
                info = ticker.get_info() or {}
            except Exception:
                info = {}
            history = ticker.history(period=period, interval="1d", auto_adjust=False, timeout=12)
            quote = {
                "last_price": clean_number(fast.get("last_price") or info.get("regularMarketPrice") or (history["Close"].iloc[-1] if history is not None and not history.empty else None)),
                "previous_close": clean_number(fast.get("previous_close") or info.get("previousClose")),
                "regular_market_open": clean_number(info.get("regularMarketOpen")),
                "day_high": clean_number(fast.get("day_high") or info.get("dayHigh")),
                "day_low": clean_number(fast.get("day_low") or info.get("dayLow")),
                "volume": clean_number(fast.get("last_volume") or info.get("volume")),
                "currency": str(fast.get("currency") or info.get("currency") or "USD"),
                "exchange": str(info.get("exchange") or fast.get("exchange") or ""),
                "market_state": str(info.get("marketState") or "unknown"),
                "pre_market_price": clean_number(info.get("preMarketPrice")),
                "post_market_price": clean_number(info.get("postMarketPrice")),
                "market_cap": clean_number(info.get("marketCap")),
                "beta": clean_number(info.get("beta")),
                "trailing_pe": clean_number(info.get("trailingPE")),
                "eps": clean_number(info.get("trailingEps")),
                "source_timestamp": now_taipei(),
            }
            news_items = []
            try:
                raw_news = ticker.news or []
            except Exception:
                raw_news = []
            for item in raw_news[:3]:
                title = item.get("title") if isinstance(item, dict) else None
                if not title:
                    continue
                provider = item.get("publisher") or item.get("providerPublishTime") or "Yahoo Finance"
                news_items.append({
                    "source": str(provider),
                    "published_at": str(item.get("providerPublishTime") or "time_unavailable"),
                    "english_headline": str(title),
                    "chinese_translation": "英文標題摘要：" + str(title),
                    "english_excerpt": None,
                    "chinese_summary": "依可取得標題整理，未複製完整文章。",
                    "vocabulary": [],
                    "investment_reading": "新聞供事件脈絡參考，不單獨決定評等。",
                    "source_quality": "external_news_reference",
                    "official_source": False,
                })
            return FetchResult(symbol=symbol, ok=quote["last_price"] is not None and history is not None and not history.empty, quote=quote, history=history, news=news_items, error=None)
        except Exception as exc:
            return FetchResult(symbol=symbol, ok=False, quote={"source_timestamp": now_taipei()}, history=None, news=[], error=f"{type(exc).__name__}: {str(exc)[:180]}")

    def fetch_context(self) -> dict[str, Any]:
        symbols = {"SPY": "S&P 500 ETF", "QQQ": "Nasdaq 100 ETF", "DIA": "Dow ETF", "^VIX": "VIX", "SOXX": "Semiconductor ETF"}
        items = {}
        for symbol, label in symbols.items():
            result = self.fetch_symbol(symbol, period="3mo")
            quote = result.quote
            last = quote.get("last_price")
            prev = quote.get("previous_close")
            change_pct = None
            if last is not None and prev not in (None, 0):
                change_pct = round((last / prev - 1) * 100, 4)
            items[symbol] = {"label": label, "ok": result.ok, "last_price": last, "previous_close": prev, "change_pct": change_pct, "error": result.error, "source_timestamp": quote.get("source_timestamp")}
        spy = items.get("SPY", {}).get("change_pct")
        qqq = items.get("QQQ", {}).get("change_pct")
        vix = items.get("^VIX", {}).get("last_price")
        score = 50
        for value in [spy, qqq]:
            if value is not None:
                score += 8 if value > 0.3 else -8 if value < -0.3 else 0
        if vix is not None:
            score += -10 if vix > 25 else 6 if vix < 16 else 0
        score = max(0, min(100, score))
        return {"items": items, "market_environment_score": score, "market_regime": "risk_on" if score >= 60 else "risk_off" if score <= 40 else "neutral", "risk_environment": "elevated" if score <= 40 else "normal", "source_timestamp": now_taipei()}
