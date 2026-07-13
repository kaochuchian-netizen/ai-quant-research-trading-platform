"""TW Daily Tactical Intelligence Engine V1.

Deterministic, Taiwan-market-only tactical strategy calculations. This module is
advisory-only and never creates orders or sends notifications.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = REPO_ROOT / "data/historical"
FORMAL_PREDICTION = REPO_ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
TW_TACTICAL_VERSION = "tw_daily_tactical_v1"
TW_TACTICAL_FACTOR_VERSION = "tw_daily_tactical_factor_v1"
TW_TACTICAL_WEIGHTS = {
    "technical_setup": 0.22,
    "volume_confirmation": 0.16,
    "chip_flow": 0.14,
    "market_context": 0.12,
    "risk_quality": 0.18,
    "data_quality": 0.18,
}
REVIEW_STATUSES = ["win", "loss", "breakeven", "not_triggered", "no_trade", "expired", "insufficient_data"]


def now_taipei() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


def _avg(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    return None if not clean else sum(clean) / len(clean)


def _sma(values: list[float], n: int) -> float | None:
    return None if len(values) < n else _avg(values[-n:])


def _ema(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    alpha = 2 / (n + 1)
    ema = values[0]
    for value in values[1:]:
        ema = alpha * value + (1 - alpha) * ema
    return ema


def _slope(values: list[float], n: int) -> float | None:
    if len(values) < n + 5:
        return None
    now = _sma(values, n)
    prev = _avg(values[-n - 5:-5])
    if now is None or prev in (None, 0):
        return None
    return (now - prev) / prev


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _rolling_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def read_ohlcv(stock_id: str) -> list[dict[str, Any]]:
    path = HISTORICAL_DIR / f"{stock_id}_daily.csv"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            item: dict[str, Any] = {"date": row.get("date")}
            for key in ["open", "high", "low", "close", "volume"]:
                item[key] = _num(row.get(key))
            if item.get("date") and all(item.get(k) is not None for k in ["open", "high", "low", "close"]):
                rows.append(item)
    return rows


def load_formal_stocks() -> list[dict[str, Any]]:
    if not FORMAL_PREDICTION.exists():
        return []
    data = json.loads(FORMAL_PREDICTION.read_text(encoding="utf-8"))
    if data.get("market") != "TW" or data.get("is_example") is True:
        return []
    return [s for s in data.get("stocks", []) if isinstance(s, dict)]


def rsi14(closes: list[float]) -> float | None:
    if len(closes) < 15:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for prev, curr in zip(closes[-15:-1], closes[-14:]):
        diff = curr - prev
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = _avg(gains) or 0
    avg_loss = _avg(losses) or 0
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(closes: list[float]) -> dict[str, float | None]:
    if len(closes) < 35:
        return {"macd": None, "signal": None, "histogram": None}
    series: list[float] = []
    for i in range(26, len(closes) + 1):
        e12 = _ema(closes[:i], 12)
        e26 = _ema(closes[:i], 26)
        if e12 is not None and e26 is not None:
            series.append(e12 - e26)
    signal = _ema(series, 9) if len(series) >= 9 else None
    value = series[-1] if series else None
    return {"macd": value, "signal": signal, "histogram": None if value is None or signal is None else value - signal}


def technical_factors(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [float(r["close"]) for r in rows if r.get("close") is not None]
    highs = [float(r["high"]) for r in rows if r.get("high") is not None]
    lows = [float(r["low"]) for r in rows if r.get("low") is not None]
    vols = [float(r.get("volume") or 0) for r in rows]
    latest = rows[-1] if rows else {}
    ma5, ma10, ma20, ma60 = (_sma(closes, n) for n in [5, 10, 20, 60])
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1] != 0]
    true_ranges = [max(h - l, abs(h - pc), abs(l - pc)) for h, l, pc in zip(highs[1:], lows[1:], closes[:-1])]
    atr14 = _sma(true_ranges, 14)
    if atr14 is None and len(highs) >= 5 and len(lows) >= 5:
        atr14 = _avg([h - l for h, l in zip(highs[-10:], lows[-10:])])
    latest_close = closes[-1] if closes else None
    bb_mid = ma20
    std20 = _rolling_std(closes[-20:]) if len(closes) >= 20 else None
    bb_upper = None if bb_mid is None or std20 is None else bb_mid + 2 * std20
    bb_lower = None if bb_mid is None or std20 is None else bb_mid - 2 * std20
    range20_high = max(highs[-20:]) if len(highs) >= 20 else None
    range20_low = min(lows[-20:]) if len(lows) >= 20 else None
    pos = None
    if latest_close is not None and range20_high not in (None, range20_low) and range20_low is not None:
        pos = (latest_close - range20_low) / (range20_high - range20_low)
    vol_ma5 = _sma(vols, 5)
    vol_ma20 = _sma(vols, 20)
    rel_vol = None if vol_ma20 in (None, 0) or not vols else vols[-1] / vol_ma20
    m = macd(closes)
    atr_pct = None if latest_close in (None, 0) or atr14 is None else atr14 / latest_close
    return {
        "latest_date": latest.get("date"),
        "latest_close": _round(latest_close),
        "latest_open": _round(latest.get("open")),
        "latest_high": _round(latest.get("high")),
        "latest_low": _round(latest.get("low")),
        "latest_volume": _round(latest.get("volume"), 0),
        "history_days": len(rows),
        "ma5": _round(ma5), "ma10": _round(ma10), "ma20": _round(ma20), "ma60": _round(ma60),
        "ma20_slope": _round(_slope(closes, 20), 5), "ma60_slope": _round(_slope(closes, 60), 5),
        "rsi14": _round(rsi14(closes), 2),
        "macd": _round(m["macd"], 4), "macd_signal": _round(m["signal"], 4), "macd_histogram": _round(m["histogram"], 4),
        "bollinger_upper": _round(bb_upper), "bollinger_middle": _round(bb_mid), "bollinger_lower": _round(bb_lower),
        "bollinger_width": _round(None if bb_upper is None or bb_lower is None or bb_mid in (None, 0) else (bb_upper - bb_lower) / bb_mid, 5),
        "atr14": _round(atr14), "atr_pct": _round(atr_pct, 5),
        "high_5d": _round(max(highs[-5:]) if len(highs) >= 5 else None),
        "low_5d": _round(min(lows[-5:]) if len(lows) >= 5 else None),
        "high_10d": _round(max(highs[-10:]) if len(highs) >= 10 else None),
        "low_10d": _round(min(lows[-10:]) if len(lows) >= 10 else None),
        "high_20d": _round(range20_high), "low_20d": _round(range20_low),
        "current_range_position": _round(pos, 4),
        "volume_ma5": _round(vol_ma5, 0), "volume_ma20": _round(vol_ma20, 0), "relative_volume": _round(rel_vol, 3),
        "volume_expansion": bool(rel_vol is not None and rel_vol >= 1.25),
        "volume_contraction": bool(rel_vol is not None and rel_vol <= 0.75),
        "return_volatility_pct": _round((_rolling_std(returns[-20:]) or 0), 5),
    }


def tw_tick_size(price: float | None) -> float:
    if price is None:
        return 0.01
    p = abs(float(price))
    if p < 10:
        return 0.01
    if p < 50:
        return 0.05
    if p < 100:
        return 0.1
    if p < 500:
        return 0.5
    if p < 1000:
        return 1.0
    return 5.0


def round_tw_price(value: float | None) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    tick = tw_tick_size(value)
    return round(round(float(value) / tick) * tick, 2)


def instrument_type(stock_id: str) -> str:
    if stock_id.startswith("00"):
        return "etf"
    if stock_id.isdigit() and len(stock_id) == 4:
        return "common_stock"
    return "other_or_unknown"


def factor_coverage(tech: dict[str, Any], stock_id: str) -> dict[str, Any]:
    days = int(tech.get("history_days") or 0)
    hist = "available" if days >= 60 else "partial" if days >= 20 else "limited" if days >= 10 else "unavailable"
    inst_type = instrument_type(stock_id)
    etf = inst_type == "etf"
    coverage = {
        "price_trend": hist,
        "volume": "available" if days >= 20 and tech.get("volume_ma20") is not None else "partial" if days >= 5 else "unavailable",
        "support_resistance": "available" if days >= 20 else "partial" if days >= 10 else "unavailable",
        "chip": "not_applicable" if etf else "partial" if days >= 20 else "unavailable",
        "institutional_flow": "not_applicable" if etf else "unavailable",
        "margin_short": "not_applicable" if etf else "unavailable",
        "market_context": "partial" if days >= 10 else "unavailable",
        "event_news": "unavailable",
        "prediction_snapshot": "available" if days >= 10 else "unavailable",
        "review_outcome": "partial" if days >= 10 else "unavailable",
    }
    complete = sum(1 for v in coverage.values() if v == "available")
    partial = sum(1 for v in coverage.values() if v == "partial")
    unavailable = sum(1 for v in coverage.values() if v == "unavailable")
    not_applicable = sum(1 for v in coverage.values() if v == "not_applicable")
    quality = "complete" if unavailable == 0 and partial <= 2 else "partial" if days >= 20 and unavailable <= 5 else "limited" if days >= 10 else "insufficient"
    return {"statuses": coverage, "instrument_type": inst_type, "summary": {"available": complete, "partial": partial, "unavailable": unavailable, "stale": 0, "not_applicable": not_applicable}, "data_quality": quality, "downgrade_policy": "missing or stale TW tactical inputs lower confidence/position size; insufficient core OHLCV forces no_trade"}


def source_status(tech: dict[str, Any], stock_id: str = "") -> dict[str, str]:
    cov = factor_coverage(tech, stock_id).get("statuses", {})
    return {"historical_ohlcv": cov.get("price_trend", "unavailable"), "technical_engine": cov.get("price_trend", "unavailable"), "twse_institutional_flow": cov.get("institutional_flow", "unavailable"), "margin_short": cov.get("margin_short", "unavailable"), "chip_engine": cov.get("chip", "unavailable"), "news_event": cov.get("event_news", "unavailable"), "tw_market_context": cov.get("market_context", "unavailable")}


def trend_state(tech: dict[str, Any]) -> str:
    close = _num(tech.get("latest_close")); ma20 = _num(tech.get("ma20")); ma60 = _num(tech.get("ma60")); slope20 = _num(tech.get("ma20_slope")); slope60 = _num(tech.get("ma60_slope"))
    if close is None or ma20 is None:
        return "insufficient_data"
    if close > ma20 and (ma60 is None or close > ma60) and (slope20 or 0) > 0:
        return "bullish"
    if close < ma20 and (ma60 is None or close < ma60) and (slope20 or 0) < 0:
        return "bearish"
    if slope60 is None:
        return "neutral"
    return "bullish" if slope20 and slope20 > 0 and slope60 > 0 else "bearish" if slope20 and slope20 < 0 and slope60 < 0 else "neutral"


def support_resistance(tech: dict[str, Any]) -> dict[str, Any]:
    close = _num(tech.get("latest_close")); atr = _num(tech.get("atr14")) or 0
    support_inputs = [tech.get("low_5d"), tech.get("low_10d"), tech.get("low_20d"), tech.get("ma5"), tech.get("ma10"), tech.get("ma20"), tech.get("ma60"), tech.get("bollinger_lower")]
    resist_inputs = [tech.get("high_5d"), tech.get("high_10d"), tech.get("high_20d"), tech.get("ma5"), tech.get("ma10"), tech.get("ma20"), tech.get("ma60"), tech.get("bollinger_upper")]
    supports = sorted({round_tw_price(_num(v)) for v in support_inputs if _num(v) is not None and close is not None and _num(v) < close}, reverse=True)
    resists = sorted({round_tw_price(_num(v)) for v in resist_inputs if _num(v) is not None and close is not None and _num(v) > close})
    supports = [v for v in supports if v is not None]; resists = [v for v in resists if v is not None]
    return {"nearest_support": supports[0] if supports else round_tw_price(close - atr) if close is not None and atr else None, "secondary_support": supports[1] if len(supports) > 1 else round_tw_price(close - 1.5 * atr) if close is not None and atr else None, "nearest_resistance": resists[0] if resists else round_tw_price(close + atr) if close is not None and atr else None, "secondary_resistance": resists[1] if len(resists) > 1 else round_tw_price(close + 1.8 * atr) if close is not None and atr else None, "sources": ["recent_swing_high_low", "5_10_20d_high_low", "moving_average", "bollinger_band", "atr_buffer"], "tick_size_applied": True}


def chip_tactical(stock_id: str, tech: dict[str, Any]) -> dict[str, Any]:
    inst_type = instrument_type(stock_id); rel_vol = _num(tech.get("relative_volume")); tr = trend_state(tech); etf = inst_type == "etf"
    direction = "neutral"; flow_confirmation = False
    if rel_vol is not None and rel_vol >= 1.25 and tr == "bullish": direction = "positive"; flow_confirmation = True
    elif rel_vol is not None and rel_vol >= 1.25 and tr == "bearish": direction = "negative"
    score = 56 if direction == "positive" else 42 if direction == "negative" else 50
    if etf: score = 50
    institutional_status = "not_applicable" if etf else "unavailable"; margin_status = "not_applicable" if etf else "unavailable"
    return {"instrument_type": inst_type, "chip_direction": direction, "chip_score": score, "institutional_flow": {"foreign_investor_net_buy_sell": None, "foreign_consecutive_days": None, "investment_trust_net_buy_sell": None, "investment_trust_consecutive_days": None, "dealer_net_buy_sell": None, "institutional_alignment": institutional_status, "price_flow_divergence": "unavailable" if not etf else "not_applicable", "data_status": institutional_status}, "margin_risk": {"margin_balance_change": None, "short_balance_change": None, "margin_price_divergence": "unavailable" if not etf else "not_applicable", "short_interest_signal": "unavailable" if not etf else "not_applicable", "margin_overheat_risk": "unavailable" if not etf else "not_applicable", "data_status": margin_status}, "short_signal": "not_applicable" if etf else "unavailable", "short_interest_signal": "not_applicable" if etf else "unavailable", "flow_confirmation": flow_confirmation, "chip_data_quality": "not_applicable" if etf else "partial" if rel_vol is not None else "limited", "data_quality": "not_applicable" if etf else "partial" if rel_vol is not None else "limited", "notes": ["ETF 標的不硬套個股法人/融資券規則，籌碼因子列為 not_applicable。"] if etf else ["正式法人/融資券細項尚未接入；以量價代理輔助判斷並降低信心，不偽造籌碼資料。"]}


def market_context(tech_by_stock: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trends = [trend_state(t) for t in tech_by_stock.values()]
    total = len(trends) or 1; bullish = trends.count("bullish"); bearish = trends.count("bearish")
    rel_vols = [_num(t.get("relative_volume")) for t in tech_by_stock.values() if _num(t.get("relative_volume")) is not None]
    avg_rvol = _avg(rel_vols)
    bias = "bullish" if bullish / total >= 0.45 else "bearish" if bearish / total >= 0.45 else "neutral"
    volume_status = "expanded" if avg_rvol and avg_rvol >= 1.15 else "contracted" if avg_rvol and avg_rvol <= 0.85 else "normal"
    risk = "high" if bearish / total >= 0.5 else "medium" if bias == "neutral" else "low"
    score = 58 if bias == "bullish" else 42 if bias == "bearish" else 50
    if volume_status == "expanded" and bias == "bullish": score += 4
    if risk == "high": score -= 8
    return {"market_bias": bias, "market_risk": risk, "market_breadth_status": f"watchlist breadth bullish={bullish}/{total}, bearish={bearish}/{total}; broad TWSE breadth unavailable", "market_volume_status": volume_status, "market_regime": f"{bias}_{risk}_risk", "market_context_score": _round(_clamp(score), 2), "market_data_quality": "partial", "data_status": "partial", "unavailable_fields": ["TWSE index breadth", "OTC breadth", "market-wide advancers/decliners"]}


def chase_risk(tech: dict[str, Any]) -> tuple[str, list[str]]:
    close = _num(tech.get("latest_close")); ma5 = _num(tech.get("ma5")); ma20 = _num(tech.get("ma20")); upper = _num(tech.get("bollinger_upper")); rsi = _num(tech.get("rsi14")); atr_pct = _num(tech.get("atr_pct")); rel_vol = _num(tech.get("relative_volume"))
    points = 0; reasons: list[str] = []
    if close and ma5 and close / ma5 - 1 > 0.035: points += 1; reasons.append("價格明顯高於 MA5")
    if close and ma20 and close / ma20 - 1 > 0.08: points += 1; reasons.append("價格明顯高於 MA20")
    if close and upper and close >= upper * 0.985: points += 1; reasons.append("接近 Bollinger 上緣")
    if rsi and rsi >= 72: points += 1; reasons.append("RSI 過熱")
    if atr_pct and ma20 and close and close / ma20 - 1 > atr_pct: points += 1; reasons.append("已達一個 ATR 以上擴張")
    if rel_vol is not None and rel_vol < 1 and close and ma20 and close > ma20: points += 1; reasons.append("突破或上攻量能未確認")
    return ("high" if points >= 3 else "medium" if points >= 1 else "low", reasons or ["追價風險未見明顯升高"])


def setup_detection(tech: dict[str, Any], market: dict[str, Any], data_quality: str) -> tuple[str, str, list[str], list[str]]:
    if data_quality == "insufficient":
        return "no_trade", "no_trade", ["資料品質不足，今日不建立戰術部位"], ["core OHLCV/indicator coverage insufficient"]
    close = _num(tech.get("latest_close")); high20 = _num(tech.get("high_20d")); ma5 = _num(tech.get("ma5")); ma10 = _num(tech.get("ma10")); ma20 = _num(tech.get("ma20")); low20 = _num(tech.get("low_20d")); rsi = _num(tech.get("rsi14")); rel_vol = _num(tech.get("relative_volume")); pos = _num(tech.get("current_range_position")); tr = trend_state(tech)
    cr, chase_reasons = chase_risk(tech)
    if cr == "high": return "no_trade", "no_trade", ["追高風險過高，等待拉回"], chase_reasons
    if market.get("market_risk") == "high": return "no_trade", "no_trade", ["大盤風險偏高，先降低戰術部位"], ["market_context high risk"]
    if close and high20 and close >= high20 * 0.995 and rel_vol and rel_vol >= 1.2 and tr == "bullish" and (rsi is None or rsi < 72): return "bullish", "breakout", ["接近/突破 20 日高點", "量能放大", "均線趨勢偏多"], []
    if tr == "bullish" and close and any(x and abs(close / x - 1) <= 0.025 for x in [ma5, ma10, ma20]) and rel_vol is not None and rel_vol <= 1.1: return "bullish", "pullback", ["中期趨勢向上", "回測短中期均線", "量縮整理"], []
    if tr == "bullish" and close and ma20 and close > ma20 and (rsi is None or rsi < 68): return "bullish", "trend_continuation", ["價格站上 MA20", "短中期趨勢延續"], []
    if close and low20 and pos is not None and pos <= 0.25 and rsi is not None and rsi <= 38: return "neutral", "mean_reversion", ["價格接近 20 日區間下緣", "RSI 偏低，觀察反彈"], []
    if pos is not None and 0.25 < pos < 0.75: return "neutral", "range_trade", ["價格位於 20 日區間中段，適合區間觀察"], []
    if tr == "bearish": return "bearish", "reversal_watch", ["趨勢偏弱，僅觀察止穩訊號"], ["trend bearish"]
    if data_quality == "limited" and close and _num(tech.get("atr14")):
        ma10v = _num(tech.get("ma10"))
        if ma10v and close >= ma10v:
            return "neutral", "range_trade", ["歷史資料有限，但價格仍在 MA10 附近或上方", "以區間觀察，不提高部位"], ["limited history below 20 bars; confidence downgraded"]
        return "neutral", "reversal_watch", ["歷史資料有限，僅觀察止穩訊號"], ["limited history below 20 bars; trend confirmation unavailable"]
    return "no_trade", "no_trade", ["缺乏明確 setup，暫不操作"], ["setup not confirmed"]


def _stop_price(stop: Any) -> float | None:
    if isinstance(stop, dict): return _num(stop.get("price"))
    return _num(stop)


def price_levels(direction: str, setup: str, tech: dict[str, Any], sr: dict[str, Any]) -> dict[str, Any]:
    close = _num(tech.get("latest_close")); atr = _num(tech.get("atr14"))
    if close is None or atr is None or atr <= 0 or setup == "no_trade":
        return {"entry_zone": None, "stop_invalidation": None, "target_1": None, "target_2": None, "expected_move_pct": None, "reward_risk": None, "level_method": "suppressed_for_no_trade_or_insufficient_data"}
    support = _num(sr.get("nearest_support")) or close - atr; resistance = _num(sr.get("nearest_resistance")) or close + atr
    if direction == "bullish":
        if setup == "breakout": entry_low, entry_high, stop, reason = resistance, resistance + 0.25 * atr, min(close, resistance - 0.65 * atr, support), "跌回突破壓力區與 ATR buffer 下方，突破 setup 失效"
        elif setup == "pullback": entry_low, entry_high, stop, reason = max(support, close - 0.55 * atr), min(close, close + 0.1 * atr), min(support - 0.35 * atr, close - 0.75 * atr), "跌破回測支撐與 ATR 失效區，拉回承接 setup 取消"
        else: entry_low, entry_high, stop, reason = max(support, close - 0.25 * atr), close + 0.2 * atr, min(support - 0.3 * atr, close - 0.65 * atr), "跌破結構支撐與 ATR 失效區"
        target1_low = max(resistance, entry_high + 0.8 * atr); target1_high = target1_low + 0.35 * atr; target2_low = target1_high + 0.25 * atr; target2_high = target2_low + 0.55 * atr
    elif direction == "bearish":
        entry_high, entry_low, stop, reason = min(resistance, close + 0.4 * atr), close - 0.15 * atr, max(resistance + 0.3 * atr, close + 0.7 * atr), "重新站回壓力與 ATR 失效區，偏空觀察取消"
        target1_high = min(support, entry_low - 0.7 * atr); target1_low = target1_high - 0.35 * atr; target2_high = target1_low - 0.25 * atr; target2_low = target2_high - 0.55 * atr
    else:
        entry_low, entry_high, stop, reason = max(support, close - 0.45 * atr), min(resistance, close + 0.15 * atr), max(support, close - 0.45 * atr) - 0.45 * atr, "跌破區間下緣與 ATR 失效區，區間策略取消"
        target1_low = min(resistance, close + 0.45 * atr); target1_high = target1_low + 0.25 * atr; target2_low = target1_high + 0.2 * atr; target2_high = target2_low + 0.35 * atr
    entry_low, entry_high, stop = round_tw_price(entry_low), round_tw_price(entry_high), round_tw_price(stop)
    target1_low, target1_high, target2_low, target2_high = round_tw_price(target1_low), round_tw_price(target1_high), round_tw_price(target2_low), round_tw_price(target2_high)
    if None in {entry_low, entry_high, stop, target1_low, target1_high}: return {"entry_zone": None, "stop_invalidation": None, "target_1": None, "target_2": None, "expected_move_pct": None, "reward_risk": None, "level_method": "insufficient_level_inputs"}
    entry_mid = (entry_low + entry_high) / 2; target_mid = (min(target1_low, target1_high) + max(target1_low, target1_high)) / 2
    risk = abs(entry_mid - stop); reward = abs(target_mid - entry_mid)
    return {"entry_zone": {"low": min(entry_low, entry_high), "high": max(entry_low, entry_high)}, "stop_invalidation": {"price": stop, "reason": reason}, "target_1": {"low": min(target1_low, target1_high), "high": max(target1_low, target1_high)}, "target_2": {"low": min(target2_low, target2_high), "high": max(target2_low, target2_high)} if target2_low is not None and target2_high is not None else None, "expected_move_pct": _round(None if close == 0 else abs(target_mid - close) / close * 100, 2), "reward_risk": _round(None if risk <= 0 else reward / risk, 2), "level_method": "setup_specific_support_resistance_atr_tick_size_v1", "representative_entry": _round(entry_mid), "representative_stop": stop, "representative_target": _round(target_mid)}


def build_tactical(stock: dict[str, Any], tech: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    stock_id = str(stock.get("stock_id") or stock.get("symbol") or ""); stock_name = str(stock.get("stock_name") or stock.get("name") or "")
    coverage = factor_coverage(tech, stock_id); data_quality = str(coverage.get("data_quality") or "insufficient")
    sr = support_resistance(tech); chip = chip_tactical(stock_id, tech); direction, setup, reasons, risk_reasons = setup_detection(tech, market, data_quality); levels = price_levels(direction, setup, tech, sr)
    rr = _num(levels.get("reward_risk")); cr, chase_reasons = chase_risk(tech)
    if rr is not None and rr < 0.8 and setup != "no_trade": direction, setup = "no_trade", "no_trade"; risk_reasons.append("reward/risk below 0.8 threshold"); levels = price_levels(direction, setup, tech, sr)
    technical_setup = 70 if setup in {"breakout", "pullback", "trend_continuation"} else 55 if setup in {"mean_reversion", "range_trade"} else 42 if setup == "reversal_watch" else 35
    volume_confirmation = 66 if tech.get("volume_expansion") else 55 if not tech.get("volume_contraction") else 42
    chip_score = _num(chip.get("chip_score")) or 45; market_score = _num(market.get("market_context_score")) or 50; risk_quality = 72 if cr == "low" and setup != "no_trade" else 52 if cr == "medium" else 28; dq_score = 82 if data_quality == "complete" else 62 if data_quality == "partial" else 40 if data_quality == "limited" else 18
    components = {"technical_setup": _round(technical_setup * TW_TACTICAL_WEIGHTS["technical_setup"], 2), "volume_confirmation": _round(volume_confirmation * TW_TACTICAL_WEIGHTS["volume_confirmation"], 2), "chip_flow": _round(chip_score * TW_TACTICAL_WEIGHTS["chip_flow"], 2), "market_context": _round(market_score * TW_TACTICAL_WEIGHTS["market_context"], 2), "risk_quality": _round(risk_quality * TW_TACTICAL_WEIGHTS["risk_quality"], 2), "data_quality": _round(dq_score * TW_TACTICAL_WEIGHTS["data_quality"], 2)}
    score_before_penalty = sum(v for v in components.values() if v is not None)
    risk_penalty = (12 if cr == "high" else 0) + (8 if market.get("market_risk") == "high" else 0) + (6 if rr is not None and rr < 1.0 else 0)
    data_quality_penalty = 0 if data_quality == "complete" else 5 if data_quality == "partial" else 14 if data_quality == "limited" else 25
    score = _clamp(score_before_penalty - risk_penalty - data_quality_penalty)
    if setup == "no_trade": score = min(score, 45)
    confidence = _clamp(35 + (coverage["summary"].get("available", 0) * 4) + (8 if setup != "no_trade" else -5) + (6 if rr and rr >= 1.5 else 0) - risk_penalty * 0.7 - data_quality_penalty, 15, 85)
    rating = "No-Trade" if setup == "no_trade" else "A-Tactical" if score >= 72 else "B-Tactical" if score >= 60 else "C-Tactical" if score >= 48 else "D-Tactical"
    action = {"breakout": "突破確認後偏多", "pullback": "拉回承接", "trend_continuation": "拉回觀察", "mean_reversion": "區間操作", "range_trade": "區間操作", "reversal_watch": "等待止穩", "no_trade": "避免追高" if cr == "high" else "暫不操作"}.get(setup, "暫不操作")
    position_size = "avoid" if setup == "no_trade" or data_quality == "insufficient" else "small" if cr == "high" or data_quality == "limited" else "half" if confidence < 58 or cr == "medium" else "normal"
    playbook = {"breakout": "等待有效突破壓力並確認量能；未站穩突破區不追價，跌回失效區取消。", "pullback": "等待回測支撐或短期均線止穩；量縮不破可觀察，跌破結構支撐取消。", "trend_continuation": "趨勢延續但不追高，優先等待短線回測或量價同步確認。", "mean_reversion": "僅在超跌後出現止穩訊號時觀察；若中期結構繼續轉弱，不建立部位。", "range_trade": "接近區間支撐才具備操作價值；接近壓力不追價，跌破區間下緣取消。", "reversal_watch": "只列為觀察，等待止穩與量能確認，未轉強前偏防守。", "no_trade": "目前缺乏合理進場結構、資料品質不足或報酬風險不合格，暫不建立戰術部位。"}[setup]
    if setup == "no_trade" and not risk_reasons: risk_reasons.append("no actionable tactical setup")
    return {"market": "TW", "stock_id": stock_id, "stock_name": stock_name, "strategy_id": TW_TACTICAL_VERSION, "strategy_type": "daily_tactical", "strategy_version": "v1", "factor_version": TW_TACTICAL_FACTOR_VERSION, "factor_weights": TW_TACTICAL_WEIGHTS, "generated_at": now_taipei(), "direction": direction, "setup_type": setup, "action": action, "score": _round(score, 2), "rating": rating, "confidence": _round(confidence, 1), "entry_zone": levels.get("entry_zone"), "stop_invalidation": levels.get("stop_invalidation"), "target_1": levels.get("target_1"), "target_2": levels.get("target_2"), "expected_move_pct": levels.get("expected_move_pct"), "reward_risk": levels.get("reward_risk"), "level_method": levels.get("level_method"), "chase_risk": cr, "event_risk": "unknown", "position_size": position_size, "time_horizon": "intraday_to_5d", "data_quality": data_quality, "factor_coverage": coverage, "source_status": source_status(tech, stock_id), "technical_factors": tech, "support_resistance": sr, "chip_tactical": chip, "market_context": market, "score_components": components, "score_before_penalty": _round(score_before_penalty, 2), "risk_penalty": _round(risk_penalty, 2), "data_quality_penalty": _round(data_quality_penalty, 2), "final_score": _round(score, 2), "reasons": reasons, "risk_reasons": risk_reasons or chase_reasons, "playbook": {"setup_type": setup, "template": playbook, "entry_condition": "use deterministic entry_zone when present", "invalidation_condition": levels.get("stop_invalidation", {}).get("reason") if isinstance(levels.get("stop_invalidation"), dict) else "資料不足", "risk_context": risk_reasons or chase_reasons}, "advisory_only": True, "trading_or_order_executed": False}


def prediction_snapshot(tactical: dict[str, Any], prediction_date: str) -> dict[str, Any]:
    ez = tactical.get("entry_zone") or {}; t1 = tactical.get("target_1") or {}; t2 = tactical.get("target_2") or {}; stop = tactical.get("stop_invalidation")
    try: valid_until = (datetime.fromisoformat(prediction_date) + timedelta(days=7)).date().isoformat()
    except ValueError: valid_until = prediction_date
    return {"market": "TW", "strategy_type": "daily_tactical", "strategy_id": TW_TACTICAL_VERSION, "strategy_version": "v1", "factor_version": TW_TACTICAL_FACTOR_VERSION, "stock_id": tactical.get("stock_id"), "stock_name": tactical.get("stock_name"), "prediction_date": prediction_date, "valid_from": prediction_date, "valid_until": valid_until, "evaluation_windows": ["1D", "3D", "5D"], "direction": tactical.get("direction"), "setup_type": tactical.get("setup_type"), "entry_zone_low": ez.get("low"), "entry_zone_high": ez.get("high"), "stop_invalidation": _stop_price(stop), "stop_reason": stop.get("reason") if isinstance(stop, dict) else None, "target_1_low": t1.get("low"), "target_1_high": t1.get("high"), "target_2_low": t2.get("low"), "target_2_high": t2.get("high"), "expected_move_pct": tactical.get("expected_move_pct"), "reward_risk": tactical.get("reward_risk"), "confidence": tactical.get("confidence"), "position_size": tactical.get("position_size"), "data_quality": tactical.get("data_quality"), "score_components": tactical.get("score_components"), "prediction_status": "no_trade" if tactical.get("setup_type") == "no_trade" else "active" if ez else "insufficient_data"}


def review_snapshot(tactical: dict[str, Any], rows: list[dict[str, Any]], windows: list[int] | None = None) -> dict[str, Any]:
    windows = windows or [1, 3, 5]
    base = {"market": "TW", "strategy_type": "daily_tactical", "strategy_id": TW_TACTICAL_VERSION, "strategy_version": "v1", "factor_version": TW_TACTICAL_FACTOR_VERSION, "stock_id": tactical.get("stock_id"), "stock_name": tactical.get("stock_name"), "evaluation_windows": [f"{w}D" for w in windows], "trigger_aware": True, "same_bar_policy": "conservative_stop_first", "not_triggered_is_not_loss": True}
    if tactical.get("setup_type") == "no_trade":
        return {**base, "review_status": "no_trade", "status": "no_trade", "reason": "No Trade setup intentionally avoided", "entry_triggered": False, "counted_as_win_loss": False}
    if not tactical.get("entry_zone"):
        return {**base, "review_status": "insufficient_data", "status": "insufficient_data", "reason": "Missing deterministic entry zone"}
    return {**base, "review_status": "pending", "status": "pending", "reason": "Awaiting future 1D/3D/5D outcome; current prediction is persisted but not yet reviewable", "entry_triggered": None, "stop_breached": None, "target_1_reached": None, "target_2_reached": None, "mfe": None, "mae": None, "realized_reward_risk": None, "false_breakout": None, "outcome_data_quality": "pending", "counted_as_win_loss": False}


def build_runtime() -> dict[str, Any]:
    stocks = load_formal_stocks(); tech_by_stock: dict[str, dict[str, Any]] = {}; rows_by_stock: dict[str, list[dict[str, Any]]] = {}
    for stock in stocks:
        sid = str(stock.get("stock_id") or ""); rows = read_ohlcv(sid); rows_by_stock[sid] = rows; tech_by_stock[sid] = technical_factors(rows)
    market = market_context(tech_by_stock); generated_at = now_taipei(); cards = []; predictions = []; reviews = []
    for stock in stocks:
        sid = str(stock.get("stock_id") or ""); tactical = build_tactical(stock, tech_by_stock.get(sid, {}), market)
        research = {"market": "TW", "strategy_type": "research_position", "strategy_version": "tw_research_position_existing_v1", "score": stock.get("score"), "rating": stock.get("rating", "資料待接"), "action": stock.get("action", "資料待接"), "confidence": stock.get("confidence_score"), "prediction": {"same_day_high_low": {"high": stock.get("same_day_predicted_high"), "low": stock.get("same_day_predicted_low")}, "next_day_high_low": {"high": stock.get("next_day_predicted_high"), "low": stock.get("next_day_predicted_low")}, "one_month_trend": stock.get("one_month_trend"), "three_month_trend": stock.get("three_month_trend")}, "preserved_existing_behavior": True}
        pred = prediction_snapshot(tactical, generated_at[:10]); review = review_snapshot(tactical, rows_by_stock.get(sid, [])); predictions.append(pred); reviews.append({"stock_id": sid, "stock_name": tactical.get("stock_name"), **review}); cards.append({"stock_id": sid, "stock_name": tactical.get("stock_name"), "strategies": {"research_position": research, "daily_tactical": tactical}, "prediction_snapshot": pred, "review_snapshot": review})
    observable = sum(1 for c in cards if c["strategies"]["daily_tactical"].get("setup_type") != "no_trade"); no_trade = sum(1 for c in cards if c["strategies"]["daily_tactical"].get("setup_type") == "no_trade"); high_chase = sum(1 for c in cards if c["strategies"]["daily_tactical"].get("chase_risk") == "high"); limited = sum(1 for c in cards if c["strategies"]["daily_tactical"].get("data_quality") in {"limited", "insufficient"})
    quality_counts: dict[str, int] = {}
    for c in cards:
        q = str(c["strategies"]["daily_tactical"].get("data_quality")); quality_counts[q] = quality_counts.get(q, 0) + 1
    runtime_health = {"google_sheet_status": "read_via_formal_prediction_runtime", "shioaji_status": "not_initialized_by_tactical_builder", "twse_status": "not_connected_in_v1", "historical_data_status": "available" if cards else "unavailable", "news_status": "unavailable", "chip_status": "partial_or_not_applicable", "tactical_coverage": f"{len(cards)}/{len(stocks)}", "prediction_coverage": f"{len(predictions)}/{len(stocks)}", "pipeline_duration_seconds": None, "generated_at": generated_at}
    delivery_readiness = {"expected_stock_count": len(stocks), "actual_stock_count": len(cards), "research_coverage": sum(1 for c in cards if c["strategies"].get("research_position")), "tactical_coverage": len(cards), "prediction_coverage": len(predictions), "stale_artifact_count": 0, "insufficient_data_count": limited, "dashboard_ready": bool(cards), "email_ready": bool(cards), "line_ready": bool(cards), "blocking_reasons": [] if cards else ["no TW stocks loaded from formal prediction runtime"]}
    return {"schema_version": "tw_daily_tactical_runtime_v1", "artifact_type": "tw_daily_tactical_runtime", "artifact_mode": "production_runtime", "market": "TW", "strategy_type": "daily_tactical", "strategy_id": TW_TACTICAL_VERSION, "generated_at": generated_at, "source_mode": "read_only_local_historical_ohlcv_plus_existing_tw_artifacts", "stock_count": len(cards), "factor_version": TW_TACTICAL_FACTOR_VERSION, "factor_weights": TW_TACTICAL_WEIGHTS, "market_context": market, "runtime_health": runtime_health, "delivery_readiness": delivery_readiness, "data_quality_distribution": quality_counts, "cards": cards, "prediction_snapshots": predictions, "review_snapshots": reviews, "line_summary": {"research_bullish": 0, "research_neutral": len(cards), "research_conservative": 0, "daily_tactical_observable": observable, "daily_tactical_no_trade": no_trade, "high_chase_risk": high_chase, "data_limited": limited, "line_full_report": False}, "email_contract": {"contains_research_position": True, "contains_daily_tactical": True, "contains_entry_stop_target_rr": True, "notification_sent": False}, "safety": {"notification_sent": False, "line_attempted": False, "email_attempted": False, "scheduler_modified": False, "trading_or_order_executed": False, "python_main_executed": False, "production_pipeline_executed": False, "secrets_read": False}}
