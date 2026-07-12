"""TW Daily Tactical Intelligence Engine V1.

Deterministic, Taiwan-market-only tactical strategy calculations. This module is
advisory-only and never creates orders or sends notifications.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime
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


def source_status(tech: dict[str, Any]) -> dict[str, str]:
    days = int(tech.get("history_days") or 0)
    base = "available" if days >= 60 else "partial" if days >= 20 else "unavailable"
    return {
        "historical_ohlcv": base,
        "technical_engine": base,
        "twse_institutional_flow": "unavailable",
        "margin_short": "unavailable",
        "chip_engine": "partial" if days >= 20 else "unavailable",
        "news_event": "unavailable",
        "tw_market_context": "partial" if days >= 20 else "unavailable",
    }


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
    close = _num(tech.get("latest_close"))
    support_inputs = [tech.get("low_5d"), tech.get("low_10d"), tech.get("low_20d"), tech.get("ma5"), tech.get("ma10"), tech.get("ma20"), tech.get("bollinger_lower")]
    resist_inputs = [tech.get("high_5d"), tech.get("high_10d"), tech.get("high_20d"), tech.get("ma5"), tech.get("ma10"), tech.get("ma20"), tech.get("bollinger_upper")]
    supports = sorted({_round(v) for v in support_inputs if _num(v) is not None and close is not None and _num(v) < close}, reverse=True)
    resists = sorted({_round(v) for v in resist_inputs if _num(v) is not None and close is not None and _num(v) > close})
    return {
        "nearest_support": supports[0] if supports else None,
        "secondary_support": supports[1] if len(supports) > 1 else None,
        "nearest_resistance": resists[0] if resists else None,
        "secondary_resistance": resists[1] if len(resists) > 1 else None,
        "sources": ["swing_high_low", "20d_high_low", "moving_average", "bollinger_band"],
    }


def chip_tactical(stock_id: str, tech: dict[str, Any]) -> dict[str, Any]:
    is_etf = stock_id.startswith("00")
    rel_vol = _num(tech.get("relative_volume"))
    direction = "neutral"
    flow_confirmation = False
    tr = trend_state(tech)
    if rel_vol is not None and rel_vol >= 1.25 and tr == "bullish":
        direction = "positive"; flow_confirmation = True
    elif rel_vol is not None and rel_vol >= 1.25 and tr == "bearish":
        direction = "negative"
    score = 55 if direction == "positive" else 43 if direction == "negative" else 50
    if is_etf:
        score -= 4
    return {
        "chip_direction": direction,
        "chip_score": score,
        "institutional_flow": {
            "foreign_investor_net_buy_sell": None,
            "foreign_consecutive_days": None,
            "investment_trust_net_buy_sell": None,
            "investment_trust_consecutive_days": None,
            "dealer_net_buy_sell": None,
            "institutional_alignment": "unavailable",
            "data_status": "limited_for_etf" if is_etf else "partial",
        },
        "margin_risk": {
            "margin_balance_change": None,
            "short_balance_change": None,
            "margin_price_divergence": "unavailable",
            "short_interest_signal": "unavailable",
            "data_status": "limited_for_etf" if is_etf else "unavailable",
        },
        "short_interest_signal": "unavailable",
        "flow_confirmation": flow_confirmation,
        "data_quality": "limited" if is_etf else "partial",
        "notes": ["TWSE/chip runtime detail unavailable; downgraded confidence rather than fabricating flow data."] if not flow_confirmation else ["Volume/trend proxy supports chip confirmation until official flow artifact is connected."],
    }


def market_context(tech_by_stock: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trends = [trend_state(t) for t in tech_by_stock.values()]
    total = len(trends) or 1
    bullish = trends.count("bullish"); bearish = trends.count("bearish")
    rel_vols = [_num(t.get("relative_volume")) for t in tech_by_stock.values() if _num(t.get("relative_volume")) is not None]
    avg_rvol = _avg(rel_vols)
    bias = "bullish" if bullish / total >= 0.45 else "bearish" if bearish / total >= 0.45 else "neutral"
    volume_status = "expanded" if avg_rvol and avg_rvol >= 1.15 else "contracted" if avg_rvol and avg_rvol <= 0.85 else "normal"
    risk = "high" if bearish / total >= 0.5 else "medium" if bias == "neutral" else "low"
    score = 58 if bias == "bullish" else 42 if bias == "bearish" else 50
    if volume_status == "expanded" and bias == "bullish": score += 4
    if risk == "high": score -= 8
    return {"market_bias": bias, "market_risk": risk, "market_breadth_status": f"watchlist breadth bullish={bullish}/{total}, bearish={bearish}/{total}; broad TWSE breadth unavailable", "market_volume_status": volume_status, "market_regime": f"{bias}_{risk}_risk", "market_context_score": _round(_clamp(score), 2), "data_status": "partial", "unavailable_fields": ["TWSE index breadth", "OTC breadth", "market-wide advancers/decliners"]}


def chase_risk(tech: dict[str, Any]) -> tuple[str, list[str]]:
    close = _num(tech.get("latest_close")); ma5 = _num(tech.get("ma5")); ma20 = _num(tech.get("ma20")); upper = _num(tech.get("bollinger_upper")); rsi = _num(tech.get("rsi14")); atr_pct = _num(tech.get("atr_pct")); rel_vol = _num(tech.get("relative_volume"))
    points = 0; reasons: list[str] = []
    if close and ma5 and close / ma5 - 1 > 0.035: points += 1; reasons.append("價格明顯高於 MA5")
    if close and ma20 and close / ma20 - 1 > 0.08: points += 1; reasons.append("價格明顯高於 MA20")
    if close and upper and close >= upper * 0.985: points += 1; reasons.append("接近 Bollinger 上緣")
    if rsi and rsi >= 72: points += 1; reasons.append("RSI 過熱")
    if atr_pct and ma20 and close and close / ma20 - 1 > atr_pct: points += 1; reasons.append("已達一個 ATR 以上擴張")
    if rel_vol is not None and rel_vol < 1 and close and ma20 and close > ma20: points += 1; reasons.append("上攻量能未確認")
    return ("high" if points >= 3 else "medium" if points >= 1 else "low", reasons or ["追價風險未見明顯升高"])


def setup_detection(tech: dict[str, Any], market: dict[str, Any], data_quality: str) -> tuple[str, str, list[str], list[str]]:
    if data_quality == "limited":
        return "no_trade", "no_trade", ["資料品質不足，今日不建立戰術部位"], ["history < 20 or core indicator unavailable"]
    close = _num(tech.get("latest_close")); high20 = _num(tech.get("high_20d")); ma5 = _num(tech.get("ma5")); ma10 = _num(tech.get("ma10")); ma20 = _num(tech.get("ma20")); low20 = _num(tech.get("low_20d")); rsi = _num(tech.get("rsi14")); rel_vol = _num(tech.get("relative_volume")); pos = _num(tech.get("current_range_position")); tr = trend_state(tech)
    cr, chase_reasons = chase_risk(tech)
    if cr == "high":
        return "no_trade", "no_trade", ["追高風險過高，等待拉回"], chase_reasons
    if market.get("market_risk") == "high":
        return "no_trade", "no_trade", ["大盤風險偏高，先降低戰術部位"], ["market_context high risk"]
    if close and high20 and close >= high20 * 0.995 and rel_vol and rel_vol >= 1.2 and tr == "bullish" and (rsi is None or rsi < 72):
        return "bullish", "breakout", ["接近/突破 20 日高點", "量能放大", "均線趨勢偏多"], []
    if tr == "bullish" and close and any(x and abs(close / x - 1) <= 0.025 for x in [ma5, ma10, ma20]) and rel_vol is not None and rel_vol <= 1.1:
        return "bullish", "pullback", ["中期趨勢向上", "回測短中期均線", "量縮整理"], []
    if tr == "bullish" and close and ma20 and close > ma20 and (rsi is None or rsi < 68):
        return "bullish", "trend_continuation", ["價格站上 MA20", "短中期趨勢延續"], []
    if close and low20 and pos is not None and pos <= 0.25 and rsi is not None and rsi <= 38:
        return "neutral", "mean_reversion", ["價格接近 20 日區間下緣", "RSI 偏低，觀察反彈"], []
    if pos is not None and 0.25 < pos < 0.75:
        return "neutral", "range_trade", ["價格位於 20 日區間中段，適合區間觀察"], []
    if tr == "bearish":
        return "bearish", "reversal_watch", ["趨勢偏弱，僅觀察止穩訊號"], ["trend bearish"]
    return "no_trade", "no_trade", ["缺乏明確 setup，暫不操作"], ["setup not confirmed"]


def price_levels(direction: str, setup: str, tech: dict[str, Any], sr: dict[str, Any]) -> dict[str, Any]:
    close = _num(tech.get("latest_close")); atr = _num(tech.get("atr14"))
    if close is None or atr is None or atr <= 0 or setup == "no_trade":
        return {"entry_zone": None, "stop_invalidation": None, "target_1": None, "target_2": None, "expected_move_pct": None, "reward_risk": None}
    support = _num(sr.get("nearest_support")) or close - atr
    resistance = _num(sr.get("nearest_resistance")) or close + atr
    if direction == "bullish":
        if setup == "breakout":
            entry_low, entry_high = resistance, resistance + 0.25 * atr
            stop = min(close, resistance - 0.65 * atr, support)
        elif setup == "pullback":
            entry_low, entry_high = max(support, close - 0.55 * atr), min(close, close + 0.1 * atr)
            stop = min(support - 0.35 * atr, entry_low - 0.45 * atr)
        else:
            entry_low, entry_high = max(support, close - 0.25 * atr), close + 0.2 * atr
            stop = min(support - 0.3 * atr, entry_low - 0.5 * atr)
        target1_low = max(resistance, entry_high + 0.8 * atr); target1_high = target1_low + 0.35 * atr
        target2_low = target1_high + 0.25 * atr; target2_high = target2_low + 0.55 * atr
    elif direction == "bearish":
        entry_high, entry_low = min(resistance, close + 0.4 * atr), close - 0.15 * atr
        stop = max(resistance + 0.3 * atr, entry_high + 0.45 * atr)
        target1_high = min(support, entry_low - 0.7 * atr); target1_low = target1_high - 0.35 * atr
        target2_high = target1_low - 0.25 * atr; target2_low = target2_high - 0.55 * atr
    else:
        entry_low, entry_high = max(support, close - 0.45 * atr), min(resistance, close + 0.15 * atr)
        stop = entry_low - 0.45 * atr
        target1_low = min(resistance, close + 0.45 * atr); target1_high = target1_low + 0.25 * atr
        target2_low = target1_high + 0.2 * atr; target2_high = target2_low + 0.35 * atr
    entry_mid = (entry_low + entry_high) / 2; target_mid = (min(target1_low, target1_high) + max(target1_low, target1_high)) / 2
    risk = abs(entry_mid - stop); reward = abs(target_mid - entry_mid)
    return {"entry_zone": {"low": _round(min(entry_low, entry_high)), "high": _round(max(entry_low, entry_high))}, "stop_invalidation": _round(stop), "target_1": {"low": _round(min(target1_low, target1_high)), "high": _round(max(target1_low, target1_high))}, "target_2": {"low": _round(min(target2_low, target2_high)), "high": _round(max(target2_low, target2_high))}, "expected_move_pct": _round(None if close == 0 else abs(target_mid - close) / close, 5), "reward_risk": _round(None if risk <= 0 else reward / risk, 2)}


def build_tactical(stock: dict[str, Any], tech: dict[str, Any], market: dict[str, Any]) -> dict[str, Any]:
    stock_id = str(stock.get("stock_id") or stock.get("symbol") or "")
    stock_name = str(stock.get("stock_name") or stock.get("name") or "")
    data_quality = "complete" if int(tech.get("history_days") or 0) >= 60 else "partial" if int(tech.get("history_days") or 0) >= 20 else "limited"
    sr = support_resistance(tech)
    chip = chip_tactical(stock_id, tech)
    direction, setup, reasons, risk_reasons = setup_detection(tech, market, data_quality)
    levels = price_levels(direction, setup, tech, sr)
    rr = _num(levels.get("reward_risk"))
    cr, chase_reasons = chase_risk(tech)
    if rr is not None and rr < 0.8 and setup != "no_trade":
        direction, setup = "no_trade", "no_trade"
        risk_reasons.append("reward/risk below 0.8 threshold")
        levels = price_levels(direction, setup, tech, sr)
    technical_setup = 70 if setup in {"breakout", "pullback", "trend_continuation"} else 55 if setup in {"mean_reversion", "range_trade"} else 35
    volume_confirmation = 66 if tech.get("volume_expansion") else 55 if not tech.get("volume_contraction") else 42
    chip_score = _num(chip.get("chip_score")) or 45
    market_score = _num(market.get("market_context_score")) or 50
    risk_quality = 70 if cr == "low" and setup != "no_trade" else 50 if cr == "medium" else 28
    dq_score = 80 if data_quality == "complete" else 58 if data_quality == "partial" else 25
    score = technical_setup * TW_TACTICAL_WEIGHTS["technical_setup"] + volume_confirmation * TW_TACTICAL_WEIGHTS["volume_confirmation"] + chip_score * TW_TACTICAL_WEIGHTS["chip_flow"] + market_score * TW_TACTICAL_WEIGHTS["market_context"] + risk_quality * TW_TACTICAL_WEIGHTS["risk_quality"] + dq_score * TW_TACTICAL_WEIGHTS["data_quality"]
    if setup == "no_trade": score = min(score, 45)
    confidence = _clamp(30 + abs(score - 50) * 0.7 + (12 if data_quality == "complete" else 0) - (10 if cr == "high" else 0), 15, 75)
    rating = "No-Trade" if setup == "no_trade" else "A-Tactical" if score >= 72 else "B-Tactical" if score >= 60 else "C-Tactical" if score >= 48 else "D-Tactical"
    action = {"breakout": "突破確認後偏多", "pullback": "拉回承接", "trend_continuation": "拉回觀察", "mean_reversion": "區間操作", "range_trade": "區間操作", "reversal_watch": "等待止穩", "no_trade": "避免追高" if cr == "high" else "暫不操作"}.get(setup, "暫不操作")
    position_size = "avoid" if setup == "no_trade" else "small" if cr == "high" or data_quality == "limited" else "half" if confidence < 55 or cr == "medium" else "normal"
    playbook = {"breakout": "等待突破壓力並確認量能，未站穩不追價；跌回突破區下方視為失效。", "pullback": "等待回測支撐或短期均線止穩，量縮不破可觀察；跌破結構支撐取消。", "trend_continuation": "趨勢延續但不追高，優先等待短線回測或量價同步確認。", "mean_reversion": "超跌反彈只做短線觀察，未重新站回支撐不提高部位。", "range_trade": "以區間下緣到中低區觀察，接近上緣降低追價。", "reversal_watch": "等待止穩與量能確認，未轉強前偏防守。", "no_trade": "目前報酬風險不足或資料品質不完整，今日不建立戰術部位。"}[setup]
    return {"market": "TW", "stock_id": stock_id, "stock_name": stock_name, "strategy_id": TW_TACTICAL_VERSION, "strategy_type": "daily_tactical", "strategy_version": TW_TACTICAL_VERSION, "factor_version": TW_TACTICAL_FACTOR_VERSION, "factor_weights": TW_TACTICAL_WEIGHTS, "generated_at": now_taipei(), "direction": direction, "setup_type": setup, "action": action, "score": _round(score, 2), "rating": rating, "confidence": _round(confidence, 1), "entry_zone": levels.get("entry_zone"), "stop_invalidation": levels.get("stop_invalidation"), "target_1": levels.get("target_1"), "target_2": levels.get("target_2"), "expected_move_pct": levels.get("expected_move_pct"), "reward_risk": levels.get("reward_risk"), "chase_risk": cr, "event_risk": "unknown", "position_size": position_size, "time_horizon": "intraday_to_5d", "data_quality": data_quality, "source_status": source_status(tech), "technical_factors": tech, "support_resistance": sr, "chip_tactical": chip, "market_context": market, "reasons": reasons, "risk_reasons": risk_reasons or chase_reasons, "playbook": playbook, "advisory_only": True, "trading_or_order_executed": False}


def prediction_snapshot(tactical: dict[str, Any], prediction_date: str) -> dict[str, Any]:
    ez = tactical.get("entry_zone") or {}; t1 = tactical.get("target_1") or {}; t2 = tactical.get("target_2") or {}
    return {"market": "TW", "strategy_type": "daily_tactical", "strategy_id": TW_TACTICAL_VERSION, "stock_id": tactical.get("stock_id"), "stock_name": tactical.get("stock_name"), "prediction_date": prediction_date, "direction": tactical.get("direction"), "setup_type": tactical.get("setup_type"), "entry_zone_low": ez.get("low"), "entry_zone_high": ez.get("high"), "stop_invalidation": tactical.get("stop_invalidation"), "target_1_low": t1.get("low"), "target_1_high": t1.get("high"), "target_2_low": t2.get("low"), "target_2_high": t2.get("high"), "expected_move_pct": tactical.get("expected_move_pct"), "reward_risk": tactical.get("reward_risk"), "confidence": tactical.get("confidence"), "position_size": tactical.get("position_size"), "data_quality": tactical.get("data_quality")}


def review_snapshot(tactical: dict[str, Any], rows: list[dict[str, Any]], windows: list[int] | None = None) -> dict[str, Any]:
    windows = windows or [1, 3, 5]
    base = {"market": "TW", "strategy_type": "daily_tactical", "strategy_id": TW_TACTICAL_VERSION, "stock_id": tactical.get("stock_id"), "stock_name": tactical.get("stock_name"), "evaluation_windows": windows, "trigger_aware": True}
    if tactical.get("setup_type") == "no_trade":
        return {**base, "status": "no_trade", "reason": "No Trade setup intentionally avoided"}
    if not rows or not tactical.get("entry_zone"):
        return {**base, "status": "insufficient_data", "reason": "Missing outcome rows or entry zone"}
    future = rows[-max(windows):]
    entry = tactical["entry_zone"]; stop = _num(tactical.get("stop_invalidation")); t1 = tactical.get("target_1") or {}; t2 = tactical.get("target_2") or {}
    entry_low, entry_high = _num(entry.get("low")), _num(entry.get("high"))
    if entry_low is None or entry_high is None or stop is None:
        return {**base, "status": "insufficient_data", "reason": "Missing deterministic levels"}
    touched = any((r.get("low") or 0) <= entry_high and (r.get("high") or 0) >= entry_low for r in future)
    if not touched:
        return {**base, "status": "not_triggered", "entry_zone_touched": False, "not_triggered_is_not_loss": True}
    hit_stop = any((r.get("low") or 0) <= stop for r in future)
    hit_t1 = any((r.get("high") or 0) >= (_num(t1.get("low")) or 10**12) for r in future)
    hit_t2 = any((r.get("high") or 0) >= (_num(t2.get("low")) or 10**12) for r in future)
    status = "loss" if hit_stop and not hit_t1 else "breakeven" if hit_stop and hit_t1 else "win" if hit_t1 else "not_triggered"
    entry_mid = (entry_low + entry_high) / 2
    highs = [r.get("high") for r in future if r.get("high") is not None]
    lows = [r.get("low") for r in future if r.get("low") is not None]
    return {**base, "status": status, "entry_zone_touched": touched, "stop_breached": hit_stop, "target_1_reached": hit_t1, "target_2_reached": hit_t2, "mfe": _round(None if not highs else max(highs) - entry_mid), "mae": _round(None if not lows else min(lows) - entry_mid), "realized_reward_risk": tactical.get("reward_risk") if hit_t1 else None, "same_bar_policy": "conservative_stop_first"}


def build_runtime() -> dict[str, Any]:
    stocks = load_formal_stocks()
    tech_by_stock: dict[str, dict[str, Any]] = {}; rows_by_stock: dict[str, list[dict[str, Any]]] = {}
    for stock in stocks:
        sid = str(stock.get("stock_id") or "")
        rows = read_ohlcv(sid); rows_by_stock[sid] = rows; tech_by_stock[sid] = technical_factors(rows)
    market = market_context(tech_by_stock)
    generated_at = now_taipei()
    cards = []; predictions = []; reviews = []
    for stock in stocks:
        sid = str(stock.get("stock_id") or "")
        tactical = build_tactical(stock, tech_by_stock.get(sid, {}), market)
        research = {"market": "TW", "strategy_type": "research_position", "strategy_version": "tw_research_position_existing_v1", "score": stock.get("score"), "rating": stock.get("rating", "資料待接"), "action": stock.get("action", "資料待接"), "confidence": stock.get("confidence_score"), "prediction": {"same_day_high_low": {"high": stock.get("same_day_predicted_high"), "low": stock.get("same_day_predicted_low")}, "next_day_high_low": {"high": stock.get("next_day_predicted_high"), "low": stock.get("next_day_predicted_low")}, "one_month_trend": stock.get("one_month_trend"), "three_month_trend": stock.get("three_month_trend")}, "preserved_existing_behavior": True}
        pred = prediction_snapshot(tactical, generated_at[:10]); review = review_snapshot(tactical, rows_by_stock.get(sid, []))
        predictions.append(pred); reviews.append({"stock_id": sid, "stock_name": tactical.get("stock_name"), **review})
        cards.append({"stock_id": sid, "stock_name": tactical.get("stock_name"), "strategies": {"research_position": research, "daily_tactical": tactical}, "prediction_snapshot": pred, "review_snapshot": review})
    counts = {"observable": sum(1 for c in cards if c["strategies"]["daily_tactical"].get("setup_type") != "no_trade"), "no_trade": sum(1 for c in cards if c["strategies"]["daily_tactical"].get("setup_type") == "no_trade"), "high_chase_risk": sum(1 for c in cards if c["strategies"]["daily_tactical"].get("chase_risk") == "high")}
    return {"schema_version": "tw_daily_tactical_runtime_v1", "artifact_type": "tw_daily_tactical_runtime", "artifact_mode": "production_runtime", "market": "TW", "strategy_type": "daily_tactical", "strategy_id": TW_TACTICAL_VERSION, "generated_at": generated_at, "source_mode": "read_only_local_historical_ohlcv_plus_existing_tw_artifacts", "stock_count": len(cards), "factor_version": TW_TACTICAL_FACTOR_VERSION, "factor_weights": TW_TACTICAL_WEIGHTS, "market_context": market, "cards": cards, "prediction_snapshots": predictions, "review_snapshots": reviews, "line_summary": {"research_bullish": 0, "research_neutral": len(cards), "research_conservative": 0, "daily_tactical_observable": counts["observable"], "daily_tactical_no_trade": counts["no_trade"], "high_chase_risk": counts["high_chase_risk"], "line_full_report": False}, "email_contract": {"contains_research_position": True, "contains_daily_tactical": True, "contains_entry_stop_target_rr": True, "notification_sent": False}, "safety": {"notification_sent": False, "line_attempted": False, "email_attempted": False, "scheduler_modified": False, "trading_or_order_executed": False, "python_main_executed": False, "production_pipeline_executed": False, "secrets_read": False}}
