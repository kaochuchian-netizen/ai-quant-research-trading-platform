"""AI-DEV-255: immutable, channel-shared presentation; no forecast inference."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from html import escape
import json
import math
import re

from app.reports.tw_human_summary import build_tw_human_summary
from app.us_stock.human_summary import build_us_human_summary
from app.reports.presentation_normalization import localize_enum

VERSION = "mobile_decision_presentation_v1"
MISSING = "尚未取得正式資料"
INTRADAY_MISSING = "尚未提供正式現在→收盤預測；盤前預測保留於研究證據"
LABELS = {
    "pre_open_0700": ("走勢預測", "預測目標", "預測區間", "投資策略", "新聞內容摘要"),
    "intraday_1305": ("走勢預測（現在→收盤）", "目前價格", "預測區間", "投資策略", "新聞內容摘要"),
    "pre_close_1335": ("今天實際走勢", "今天實際區間", "目前價格", "今日狀態", "新聞內容摘要"),
    "post_close_1500": ("今日預測結果", "方向預測結果", "區間預測結果", "今天實際走勢", "今天實際區間"),
    "us_pre_market_2000": ("走勢預測", "盤前價格", "進場區間", "停損", "目標區", "投資策略", "新聞內容摘要"),
    "us_intraday_2300": ("走勢預測（現在→收盤）", "目前價格", "預測區間", "投資策略", "新聞內容摘要"),
    "us_post_close_review_0630": ("今日預測結果", "方向預測結果", "區間預測結果", "今天實際走勢", "今天實際區間"),
}
TITLES = {"pre_open_0700":"07:00 台股盤前", "intraday_1305":"13:05 台股盤中", "pre_close_1335":"13:35 台股收盤快照", "post_close_1500":"15:00 台股盤後檢討", "us_pre_market_2000":"20:00 美股盤前", "us_intraday_2300":"23:00 美股盤中", "us_post_close_review_0630":"06:30 美股盤後檢討"}
CARD_KEYS = {
    "pre_open_0700": "structured_pre_open_cards", "intraday_1305": "structured_intraday_cards",
    "pre_close_1335": "structured_pre_close_cards", "post_close_1500": "structured_review_cards",
    "us_pre_market_2000": "structured_pre_market_cards", "us_intraday_2300": "structured_intraday_cards",
    "us_post_close_review_0630": "structured_review_cards",
}
ZH = {"up": "偏多", "down": "偏空", "flat": "盤整", "sideways": "盤整", "bullish": "偏多", "bearish": "偏空", "neutral": "盤整",
      "hit": "符合預測", "partial_hit": "部分符合", "miss": "未符合預測", "not_applicable": "不適用", "correct": "符合預測", "incorrect": "未符合預測",
      "no_forecast": "未提供預測", "no_canonical_forecast": "未提供正式方向預測",
      "insufficient_sample": "樣本不足", "blocked_input": "必要資料不足", "waiting_outcome": "等待結果成熟",
      "observe": "觀察等待", "buy": "偏多策略", "sell": "偏空策略", "hold": "續抱觀察", "reduce": "降低曝險", "avoid_overnight": "不留倉", "stop_invalidated": "停損條件失效",
      "not_evaluated": "尚未評估", "pending_evidence": "等待評估證據"}
QUALITY_REASON_ZH = {
    "DELIVERY_EVALUATION_INTEGRITY_FAILED": "發布預測與評估來源無法核對",
    "NO_PUBLISHED_DIRECTION_FORECAST": "未發布方向預測",
    "NO_PUBLISHED_RANGE_FORECAST": "未發布區間預測",
    "ACTUAL_OUTCOME_MISSING_OR_INVALID": "缺少可驗證的實際收盤資料",
    "DIRECTION_EVALUATION_NOT_ADMITTED": "方向評估所需證據不足",
    "RANGE_EVALUATION_NOT_ADMITTED": "區間評估所需證據不足",
    "PREDICTION_INTERVAL_INVALID": "預測區間格式無效，無法安全評估",
    "TACTICAL_FROZEN_IDENTITY_MISSING": "缺少盤前凍結預測識別",
    "TACTICAL_FROZEN_IDENTITY_MISMATCH": "盤前預測識別不一致",
    "TACTICAL_DIRECTION_FORECAST_MISSING": "未提供正式方向預測",
    "TACTICAL_DIRECTION_RESULT_MISSING": "缺少正式方向評估結果",
    "TACTICAL_DIRECTION_RESULT_INCONSISTENT": "方向評估資料不一致",
    "NO_CANONICAL_TACTICAL_DIRECTION_FORECAST": "未提供正式方向預測",
    "NO_CANONICAL_TACTICAL_RANGE_FORECAST": "未提供正式區間預測",
}
LINE_REASON_ZH = {
    "NO_CANONICAL_TACTICAL_DIRECTION_FORECAST": "未產生方向預測",
    "NO_CANONICAL_TACTICAL_RANGE_FORECAST": "未產生區間預測",
}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def zh(value, missing=MISSING):
    if value is None or value == "":
        return missing
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return str(value) if math.isfinite(value) else missing
    if not isinstance(value, str):
        return missing
    raw = value.strip()
    translated = ZH.get(raw.lower()) or localize_enum(raw.lower())
    if translated != raw.lower():
        return translated
    return raw if re.search(r"[\u3400-\u9fff]", raw) else missing


def price(value):
    try:
        n = float(value)
        return f"{n:.2f}" if not isinstance(value, bool) and math.isfinite(n) else MISSING
    except (TypeError, ValueError):
        return MISSING


def interval(low, high):
    a, b = price(low), price(high)
    if MISSING in (a, b) or float(a) > float(b):
        return MISSING
    return f"{a}–{b}"


def quality_component_public(component):
    """Render a quality-gate component without hiding a proved abstention.

    ``NOT_APPLICABLE`` is an explicit result (for example, the frozen 07:00
    card produced no tactical forecast), not a missing market-data result.
    Keep its stable reason visible in presentation while retaining the raw
    value only in the immutable evidence object.
    """
    result = component.get("result") if isinstance(component, dict) else None
    if result == "not_applicable":
        reason = QUALITY_REASON_ZH.get(component.get("reason_code"), "本項未建立正式預測")
        return f"不適用（{reason}）"
    if result:
        return zh(result)
    reason = QUALITY_REASON_ZH.get(component.get("reason_code"), "無法確認評估依據")
    return f"資料不足：{reason}"


def _finite_number(value):
    """Return a display-safe finite number without coercing booleans."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return number if number is not None and math.isfinite(number) else None


def _formal_post_close_actual(card, quality):
    """Prefer sealed daily OHLC over sparse intraday observations.

    A Shioaji kbars artifact marked ``SPARSE_UNVERIFIED`` is valid observed
    evidence, but it cannot displace a complete official post-close OHLC
    outcome.  This helper is presentation-only: it neither creates nor
    modifies outcome evidence.
    """
    actual = quality.get("actual") if isinstance(quality, dict) else {}
    if str(card.get("actual_status") or "").lower() != "complete" or actual.get("status") != "AVAILABLE":
        return None
    low, high, close = (_finite_number(actual.get(key)) for key in ("low", "high", "close"))
    opening = _finite_number(card.get("actual_open"))
    if None in (opening, low, high, close) or low > high or not low <= close <= high:
        return None
    direction = "bullish" if close > opening else "bearish" if close < opening else "neutral"
    return {
        "status": "FORMAL_COMPLETE",
        "direction": direction,
        "low": low,
        "high": high,
        "open": opening,
        "close": close,
        "source": str(card.get("source_name") or "official_post_close"),
    }


def post_close_dashboard_summary(cards, market, window, *, quality_cards=None):
    """Return a canonical, evidence-scoped overview for the mobile page."""
    if (market, window) != ("TW", "post_close_1500"):
        return None
    from app.reports.post_close_quality_gate import evaluate_card

    evaluations = quality_cards if quality_cards is not None else [evaluate_card(card, market=market, window=window) for card in cards]

    def counts(component):
        values = [item[component].get("result") for item in evaluations]
        return {
            "hit": sum(value == "hit" for value in values),
            "partial_hit": sum(value == "partial_hit" for value in values),
            "miss": sum(value == "miss" for value in values),
            "not_applicable": sum(value == "not_applicable" for value in values),
            "effective": sum(value in {"hit", "partial_hit", "miss"} for value in values),
        }

    return {"direction": counts("direction"), "range": counts("range"), "total": len(evaluations)}


def _post_close_component_text(component, *, predicted, actual, dimension):
    public = quality_component_public(component)
    if component.get("result") not in {"hit", "partial_hit", "miss"}:
        return public
    if dimension == "direction":
        return f"{public}（預測：{zh(predicted)}／實際：{zh(actual)}）"
    if dimension == "range":
        predicted_range = interval(*(predicted or (None, None)))
        actual_range = interval(*(actual or (None, None)))
        return f"{public}（預測：{predicted_range}／實際：{actual_range}）"
    return public


def post_close_line_summary(cards, market, window):
    """Return compact, component-scoped rates from the same quality gate.

    A ``partial_hit`` remains an admitted result but is not counted as a full
    hit.  This deliberately exposes the denominator rather than silently
    treating abstentions or partial evidence as successes.
    """
    from app.reports.post_close_quality_gate import evaluate_card

    quality_rows = [evaluate_card(card, market=market, window=window) for card in cards]

    def metric(component_name):
        values = [row[component_name].get("result") for row in quality_rows]
        eligible = [value for value in values if value in {"hit", "miss", "partial_hit"}]
        hit_count = sum(value == "hit" for value in eligible)
        count = len(eligible)
        rate = f"{(hit_count / count):.1%}" if count else "不適用"
        return hit_count, count, rate

    direction_hit, direction_count, direction_rate = metric("direction")
    range_hit, range_count, range_rate = metric("range")
    return {
        "direction_hit_count": direction_hit,
        "direction_effective_count": direction_count,
        "direction_hit_rate": direction_rate,
        "range_hit_count": range_hit,
        "range_effective_count": range_count,
        "range_hit_rate": range_rate,
    }


def cards_for(payload, window):
    """Same window only. An explicit empty canonical list must stay empty."""
    if window not in LABELS:
        raise ValueError("UNSUPPORTED_PRESENTATION_WINDOW")
    candidates = [(payload, CARD_KEYS[window]), (payload, "cards")]
    if window.startswith("us_"):
        candidates.insert(0, (payload.get("dashboard_ready_contract") or {}, "cards"))
    if payload.get("window") not in (None, window):
        return []
    for container, key in candidates:
        if key in container and isinstance(container[key], list):
            return [x for x in container[key] if isinstance(x, dict)]
    return []


def news_summary(card, human):
    items = []
    for key in ("finalized_current_news_projection_v3", "finalized_tw_news_projection_v1", "us_news_product_projection_v1"):
        value = card.get(key) or {}
        if isinstance(value, dict) and value.get("selected_items"):
            items = value["selected_items"]
            break
    items = items or human.get("important_news") or []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Content summary only: impact_summary is not a substitute for article content.
        text = next((str(item[k]) for k in ("chinese_summary", "summary_zh_tw", "summary_zh", "content_summary_zh", "summary")
                     if isinstance(item.get(k), str) and re.search(r"[\u3400-\u9fff]", item[k])), None)
        source = str(item.get("publisher") or item.get("source_name") or "來源未標示")
        result.append({"summary": text or "此則新聞尚未提供繁體中文內容摘要；原文保留於研究證據", "source": source,
                       "translation_available": text is not None})
    if not result and isinstance(card.get("news_summary"), str) and re.search(r"[\u3400-\u9fff]", card["news_summary"]):
        result.append({"summary": card["news_summary"], "source": str(card.get("news_source") or "來源詳見研究證據"), "translation_available": True})
    return result


def project_card(card, market, window, *, quality=None):
    """Read existing human-summary semantics without mutating canonical evidence."""
    original = deepcopy(card)
    human = (build_tw_human_summary if market == "TW" else build_us_human_summary)(deepcopy(card), window)
    review = card.get("review") or card.get("review_snapshot") or {}
    actual = review.get("actual_range") or card.get("actual_range") or {}
    plan = card.get("trade_plan") or {}
    active = (card.get("eligibility") or {}).get("actionable") is True
    news = news_summary(card, human)
    news_text = "；".join(f"{x['summary']}（來源：{x['source']}）" for x in news) or "尚無可用新聞內容摘要"
    strategy = zh(card.get("canonical_intraday_action") or card.get("tactical_adjustment") or card.get("action") or card.get("action_rationale"))
    unavailable_prediction = (
        window == "pre_open_0700"
        and (card.get("availability_status") == "unavailable" or bool(card.get("failure_category")))
    )
    if quality is None and window in {"post_close_1500", "us_post_close_review_0630"}:
        from app.reports.post_close_quality_gate import evaluate_card
        quality = evaluate_card(card, market=market, window=window)
    intraday = card.get("intraday_observed_path_evidence_v1") if isinstance(card.get("intraday_observed_path_evidence_v1"), dict) else {}
    observed_only = intraday.get("evidence_status") == "OBSERVED_ONLY"
    observed_direction = intraday.get("observed_close_vs_open_direction")
    observed_range = (intraday.get("observed_low"), intraday.get("observed_high"))
    formal_actual = _formal_post_close_actual(card, quality) if quality and market == "TW" and window == "post_close_1500" else None
    actual_trend = (
        f"{zh(formal_actual['direction'])}（正式資料）" if formal_actual else
        f"分時觀測{zh(observed_direction)}（未驗證完整）" if observed_only and observed_direction else
        zh(observed_direction) if intraday.get("evidence_status") == "COMPLETE_PATH" and observed_direction else
        zh(card.get("actual_direction") or review.get("actual_direction") or (card.get("direction") or {}).get("actual") if isinstance(card.get("direction"), dict) else card.get("actual_direction") or review.get("actual_direction"))
    )
    actual_range = (
        f"{interval(formal_actual['low'], formal_actual['high'])}（正式資料）" if formal_actual else
        f"分時觀測 {interval(observed_range[0], observed_range[1])}（未驗證完整）" if observed_only else
        interval(card.get("actual_low", review.get("actual_low", actual.get("low", card.get("session_low")))),
                 card.get("actual_high", review.get("actual_high", actual.get("high", card.get("session_high")))))
    )
    direction_value = quality["direction"].get("result") if quality else (human.get("direction_result") or (card.get("direction") or {}).get("result") if isinstance(card.get("direction"), dict) else human.get("direction_result"))
    range_value = quality["range"].get("result") if quality else human.get("range_result")
    if quality and market == "TW" and window == "post_close_1500":
        source = card.get("source_trade_plan") if isinstance(card.get("source_trade_plan"), dict) else {}
        forecast = source.get("forecast") if isinstance(source.get("forecast"), dict) else {}
        predicted_direction = quality["direction"].get("forecast") or card.get("predicted_direction") or forecast.get("direction")
        actual_direction = formal_actual["direction"] if formal_actual else quality["direction"].get("actual")
        predicted_range = (forecast.get("predicted_low", card.get("predicted_low")), forecast.get("predicted_high", card.get("predicted_high")))
        if quality["range"].get("scope") == "TW_FROZEN_DELIVERED_FORECAST":
            predicted_range = (quality["range"].get("forecast_low"), quality["range"].get("forecast_high"))
        actual_interval = (formal_actual["low"], formal_actual["high"]) if formal_actual else (None, None)
        direction_public = _post_close_component_text(quality["direction"], predicted=predicted_direction, actual=actual_direction, dimension="direction")
        range_public = _post_close_component_text(quality["range"], predicted=predicted_range, actual=actual_interval, dimension="range")
    else:
        direction_public = quality_component_public(quality["direction"]) if quality else (zh(direction_value) if direction_value else MISSING)
        range_public = quality_component_public(quality["range"]) if quality else (zh(range_value) if range_value else MISSING)
    values = {
        "走勢預測": "資料不足，暫不判斷" if unavailable_prediction else zh(human.get("direction")), "預測目標": price(human.get("forecast_target")),
        "預測區間": interval(human.get("forecast_low"), human.get("forecast_high")),
        "投資策略": strategy, "新聞內容摘要": news_text,
        "目前價格": price(card.get("current_price")), "盤前價格": price((card.get("premarket") or {}).get("price")),
        "進場區間": interval((plan.get("entry") or {}).get("low"), (plan.get("entry") or {}).get("high")) if active else "未建立正式進場區間",
        "停損": price(plan.get("stop")) if active else "未建立正式停損",
        "目標區": interval((plan.get("target") or {}).get("low"), (plan.get("target") or {}).get("high")) if active else "未建立正式目標區",
        "今天實際走勢": actual_trend,
        "今天實際區間": actual_range,
        "今日狀態": zh(card.get("holding_decision") or card.get("canonical_overnight_action") or card.get("data_status")),
        "方向預測結果": direction_public, "區間預測結果": range_public,
    }
    # Existing intraday products inherit their pre-open forecast. Never relabel its horizon.
    if window in {"intraday_1305", "us_intraday_2300"}:
        values["走勢預測（現在→收盤）"] = INTRADAY_MISSING
        values["預測區間"] = INTRADAY_MISSING
    # This is a display of separate canonical results, not a new combined grade.
    if quality:
        components = (quality["direction"].get("result"), quality["range"].get("result"))
        if "not_applicable" in components:
            values["今日預測結果"] = "正式行情已完成；未提供預測項目列為不適用"
        elif quality["status"] == "EVALUATED" and formal_actual:
            values["今日預測結果"] = "已完成正式方向與區間評估"
        elif quality["status"] == "EVALUATED":
            values["今日預測結果"] = "已完成評估；未提供預測項目列為不適用"
        else:
            values["今日預測結果"] = "部分評估：僅呈現已具備正式證據的項目"
    else:
        values["今日預測結果"] = "已有評估結果" if all(values[k] != MISSING for k in ("方向預測結果", "區間預測結果")) else "評估資料待補"
    return {"schema_version": VERSION, "market": market, "window": window,
            "symbol": str(card.get("symbol") or card.get("stock_id") or ""),
            "name": str(card.get("name") or card.get("stock_name") or ""),
            "source_digest": digest(original), "fields": [{"label": k, "value": values[k]} for k in LABELS[window]],
            "line_range": values["預測區間"], "news": news, "evidence": original}


def project_payload(payload, market, window, *, quality_projection=None):
    quality_by_symbol = None
    if quality_projection is not None:
        if (
            quality_projection.get("market") != market
            or quality_projection.get("window") != window
            or not isinstance(quality_projection.get("quality_by_symbol"), dict)
        ):
            raise ValueError("PRESENTATION_QUALITY_PROJECTION_MISMATCH")
        quality_by_symbol = quality_projection["quality_by_symbol"]
    cards = cards_for(payload, window)
    if quality_by_symbol is not None:
        symbols = [str(card.get("symbol") or card.get("stock_id") or "") for card in cards]
        if len(symbols) != len(set(symbols)) or set(symbols) != set(quality_by_symbol):
            raise ValueError("PRESENTATION_QUALITY_PROJECTION_CARD_MISMATCH")
    return {"schema_version": VERSION, "source_digest": digest(payload), "market": market, "window": window,
            "cards": [project_card(c, market, window, quality=None if quality_by_symbol is None else quality_by_symbol[str(c.get("symbol") or c.get("stock_id") or "")]) for c in cards]}


CSS = """.mobile-decision{box-sizing:border-box;max-width:100%;min-width:0;color:#18343c}.mobile-decision *{box-sizing:border-box;min-width:0;overflow-wrap:anywhere}.mobile-decision-overview{padding:16px;margin:16px 0;background:#f4fafb;border:1px solid #cde1e5;border-radius:14px}.mobile-decision-overview h3{font-size:18px;margin:0 0 10px}.mobile-decision-overview p{font-size:16px;line-height:1.55;margin:6px 0}.mobile-decision-card{padding:18px;margin:16px 0;background:#fff;border:1px solid #dce8eb;border-radius:14px}.mobile-decision-card h3{font-size:21px;margin:0 0 14px}.mobile-decision-card dl{margin:0;display:grid;gap:14px}.mobile-decision-card dt{font-size:13px;color:#526b73;margin-bottom:4px}.mobile-decision-card dd{margin:0;font-size:17px;line-height:1.6}.mobile-decision details{margin:16px 0;border:1px solid #dce8eb;border-radius:10px}.mobile-decision summary{cursor:pointer;min-height:44px;padding:14px;font-size:15px;font-weight:700}.mobile-decision .evidence-body{padding:12px;max-width:100%;overflow:auto}.mobile-decision pre{white-space:pre-wrap;font-size:12px}.mobile-decision .evidence-notice{font-size:13px;color:#526b73}@media(max-width:640px){.mobile-decision-card{width:100%;padding:16px}.mobile-decision-card dd{font-size:16px}.mobile-decision-overview{padding:14px}}"""


def render_primary(payload, market, window, *, quality_projection=None):
    projection = project_payload(payload, market, window, quality_projection=quality_projection)
    overview = post_close_dashboard_summary(
        [item["evidence"] for item in projection["cards"]], market, window,
        quality_cards=None if quality_projection is None else quality_projection.get("cards"),
    )
    overview_html = ""
    if overview:
        direction, interval_summary = overview["direction"], overview["range"]
        overview_html = (
            '<section class="mobile-decision-overview" aria-label="盤後評估總覽">'
            '<h3>評估總覽</h3>'
            f'<p>方向符合：{direction["hit"]}/{direction["effective"]}｜不適用：{direction["not_applicable"]}</p>'
            f'<p>區間完全符合：{interval_summary["hit"]}/{interval_summary["effective"]}｜'
            f'部分符合：{interval_summary["partial_hit"]}｜未符合：{interval_summary["miss"]}｜'
            f'不適用：{interval_summary["not_applicable"]}</p>'
            '</section>'
        )
    out = []
    for c in projection["cards"]:
        fields = "".join(f"<div><dt>{escape(x['label'])}</dt><dd>{escape(x['value'])}</dd></div>" for x in c["fields"])
        out.append(f'<article class="mobile-decision-card" data-source-digest="{c["source_digest"]}"><h3>{escape(c["symbol"])} {escape(c["name"])}</h3><dl>{fields}</dl></article>')
    return f'<style>{CSS}</style><section class="mobile-decision" data-presentation-version="{VERSION}" data-source-digest="{projection["source_digest"]}"><h2>{TITLES[window]}</h2>{overview_html}{"".join(out) or "<p>本批次尚未提供正式資料。</p>"}</section>'


def render_report(payload, market, window, legacy_html, *, extra_evidence="", quality_projection=None):
    summary = "詳細評估資料"
    return render_primary(payload, market, window, quality_projection=quality_projection) + f'<section class="mobile-decision"><details data-ai-dev-255-evidence><summary>{summary}</summary><div class="evidence-body"><p class="evidence-notice">以下保留既有詳細報告、來源鏈與系統診斷；原始來源可能包含英文，未改寫正式預測或評估。</p>{legacy_html}{extra_evidence}</div></details></section>'


def _post_close_line_items(card, market, window):
    """Compact, evidence-scoped comparison.  It never infers a result."""
    from app.reports.post_close_quality_gate import evaluate_card

    quality = evaluate_card(card, market=market, window=window)
    review = card.get("review") if isinstance(card.get("review"), dict) else {}
    evaluation = review.get("prediction_evaluation_v2") if isinstance(review.get("prediction_evaluation_v2"), dict) else {}
    if not evaluation and isinstance(card.get("prediction_evaluation_v2"), dict):
        evaluation = card["prediction_evaluation_v2"]
    direction_eval = evaluation.get("direction") if isinstance(evaluation.get("direction"), dict) else {}
    source = card.get("source_trade_plan") if isinstance(card.get("source_trade_plan"), dict) else card.get("trade_plan") or {}
    forecast = source.get("forecast") if isinstance(source.get("forecast"), dict) else {}
    predicted_direction = direction_eval.get("forecast") or direction_eval.get("predicted_direction") or forecast.get("direction") or (card.get("direction") or {}).get("forecast")
    actual_direction = direction_eval.get("actual") or (card.get("direction") or {}).get("actual") or review.get("actual_direction")
    actual = review.get("actual_range") if isinstance(review.get("actual_range"), dict) else {}
    predicted_low = forecast.get("predicted_low", card.get("predicted_low"))
    predicted_high = forecast.get("predicted_high", card.get("predicted_high"))
    actual_low = review.get("actual_low", actual.get("low", card.get("actual_low")))
    actual_high = review.get("actual_high", actual.get("high", card.get("actual_high")))
    direction_result = quality["direction"].get("result")
    range_result = quality["range"].get("result")
    direction_public = zh(direction_result) if direction_result else f"資料不足：{QUALITY_REASON_ZH.get(quality['direction']['reason_code'], '無法確認評估依據')}"
    range_public = zh(range_result) if range_result else f"資料不足：{QUALITY_REASON_ZH.get(quality['range']['reason_code'], '無法確認評估依據')}"
    return [
        ("方向預測結果", f"{direction_public}（預測：{zh(predicted_direction)}／實際：{zh(actual_direction)}）"),
        ("區間預測結果", f"{range_public}（預測：{interval(predicted_low, predicted_high)}／實際：{interval(actual_low, actual_high)}）"),
    ]


def _post_close_compact_line(card, market, window):
    """One line per symbol for mobile LINE; details remain on Dashboard."""
    from app.reports.post_close_quality_gate import evaluate_card

    quality = evaluate_card(card, market=market, window=window)

    short = {"hit": "符合", "partial_hit": "部分符合", "miss": "未符合", "not_applicable": "不適用"}

    def result(component):
        value = component.get("result")
        if value == "not_applicable":
            reason = LINE_REASON_ZH.get(component.get("reason_code"), "未建立正式預測")
            return "不適用（" + reason + "）"
        if value:
            return short.get(value, zh(value))
        return "資料不足（" + QUALITY_REASON_ZH.get(component.get("reason_code"), "無法確認評估依據") + "）"

    symbol = str(card.get("symbol") or card.get("stock_id") or "")
    name = str(card.get("name") or card.get("stock_name") or "")
    display_name = f" {name}" if name else ""
    return f"{symbol}{display_name}｜方向：{result(quality['direction'])}｜區間：{result(quality['range'])}"


def post_close_canonical_cards(payload, market, window, *, require_frozen_universe=False):
    """Order delivery rows by a frozen 07:00 notification universe when present.

    Legacy/synthetic presentation payloads can predate ``notification_universe``.
    They keep their supplied immutable card order for offline display only.  Any
    delivery or replay boundary sets ``require_frozen_universe`` and fails
    closed rather than silently substituting a mutable watchlist.
    """
    cards = cards_for(payload, window)
    universe = payload.get("notification_universe")
    if universe is None:
        if require_frozen_universe:
            raise ValueError("POST_CLOSE_FROZEN_UNIVERSE_MISSING")
        return cards
    symbols = [str(value) for value in universe]
    by_symbol = {str(card.get("symbol") or card.get("stock_id") or ""): card for card in cards}
    if not symbols or len(symbols) != len(set(symbols)) or len(cards) != len(symbols) or set(by_symbol) != set(symbols):
        if require_frozen_universe:
            raise ValueError("POST_CLOSE_FROZEN_UNIVERSE_CARD_MISMATCH")
        return cards
    return [by_symbol[symbol] for symbol in symbols]


def post_close_canonical_lines(payload, market, window):
    """One LINE/Email-compatible outcome row for every frozen symbol."""
    return [_post_close_compact_line(card, market, window) for card in post_close_canonical_cards(payload, market, window)]


def render_post_close_email(payload, market, window, url, *, require_frozen_universe=True):
    """Render a full-universe email from the same quality-gate rows as LINE."""
    if (market, window) != ("TW", "post_close_1500"):
        raise ValueError("POST_CLOSE_EMAIL_WINDOW")
    cards = post_close_canonical_cards(payload, market, window, require_frozen_universe=require_frozen_universe)
    from app.reports.post_close_quality_gate import batch_gate
    if not batch_gate(cards, market=market, window=window)["line_send_allowed"]:
        raise ValueError("POST_CLOSE_EMAIL_QUALITY_GATE_BLOCKED")
    summary = post_close_line_summary(cards, market, window)
    return "\n".join([
        "【Stock AI】15:00 台股盤後檢討",
        f"交易日：{payload.get('effective_trading_date') or '尚未取得'}",
        "方向：{}/{} 符合（{}）｜區間：{}/{} 符合（{}）".format(
            summary["direction_hit_count"], summary["direction_effective_count"], summary["direction_hit_rate"],
            summary["range_hit_count"], summary["range_effective_count"], summary["range_hit_rate"],
        ),
        "有效樣本：方向 {}｜區間 {}".format(summary["direction_effective_count"], summary["range_effective_count"]),
        *post_close_canonical_lines(payload, market, window),
        f"完整報告：{url}",
        "僅供研究參考，非交易指令。",
    ])


def render_line(payload, market, window, url, *, require_frozen_universe=False):
    projection = project_payload(payload, market, window)
    if window in {"post_close_1500", "us_post_close_review_0630"}:
        from app.reports.post_close_quality_gate import batch_gate
        gate = batch_gate([item["evidence"] for item in projection["cards"]], market=market, window=window)
        if not gate["line_send_allowed"]:
            raise ValueError("LINE_DECISION_QUALITY_GATE_BLOCKED")
    lines = ["【決策摘要】" + TITLES[window]]
    if market == "TW" and window == "post_close_1500":
        canonical_cards = post_close_canonical_cards(payload, market, window, require_frozen_universe=require_frozen_universe)
        summary = post_close_line_summary(canonical_cards, market, window)
        lines.append(
            "方向：{}/{} 符合（{}）｜區間：{}/{} 符合（{}）".format(
                summary["direction_hit_count"], summary["direction_effective_count"], summary["direction_hit_rate"],
                summary["range_hit_count"], summary["range_effective_count"], summary["range_hit_rate"],
            )
        )
        lines.append("有效樣本：方向 {}｜區間 {}".format(
            summary["direction_effective_count"], summary["range_effective_count"],
        ))
    for card in projection["cards"]:
        fields = {x["label"]: x["value"] for x in card["fields"]}
        if market == "TW" and window == "post_close_1500":
            continue
        if window in {"post_close_1500", "us_post_close_review_0630"}:
            selected = [("今日預測結果", fields["今日預測結果"]), *_post_close_line_items(card["evidence"], market, window)]
        elif window == "pre_close_1335":
            selected = [(k, fields[k]) for k in LABELS[window][:3]]
        else:
            direction = "走勢預測（現在→收盤）" if "intraday" in window else "走勢預測"
            selected = [(direction, fields[direction]), ("股價區間", card["line_range"]), ("投資策略", fields["投資策略"])]
        lines.append(card["symbol"] + " " + card["name"])
        lines.extend(k + "：" + v for k, v in selected)
    if market == "TW" and window == "post_close_1500":
        lines.extend(_post_close_compact_line(card, market, window) for card in canonical_cards)
    if not projection["cards"]:
        lines.append("本批次尚未提供正式資料，不沿用其他窗口內容。")
    lines.extend(["完整報告：", url, "僅供研究參考，非交易指令。"])
    text = "\n".join(lines)
    if market == "TW":
        from app.reports.tw_line_completeness import complete_line_universe
        text = complete_line_universe(text, payload, [c["symbol"] for c in projection["cards"]])
    return text
