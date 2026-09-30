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
ZH = {"up": "偏多", "down": "偏空", "flat": "盤整", "sideways": "盤整",
      "hit": "符合預測", "miss": "未符合預測", "correct": "符合預測", "incorrect": "未符合預測",
      "no_forecast": "未提供預測", "no_canonical_forecast": "未提供正式方向預測",
      "insufficient_sample": "樣本不足", "blocked_input": "必要資料不足", "waiting_outcome": "等待結果成熟",
      "observe": "觀察等待", "buy": "偏多策略", "sell": "偏空策略", "hold": "續抱觀察", "reduce": "降低曝險", "avoid_overnight": "不留倉", "stop_invalidated": "停損條件失效",
      "not_evaluated": "尚未評估", "pending_evidence": "等待評估證據"}


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


def project_card(card, market, window):
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
    values = {
        "走勢預測": zh(human.get("direction")), "預測目標": price(human.get("forecast_target")),
        "預測區間": interval(human.get("forecast_low"), human.get("forecast_high")),
        "投資策略": strategy, "新聞內容摘要": news_text,
        "目前價格": price(card.get("current_price")), "盤前價格": price((card.get("premarket") or {}).get("price")),
        "進場區間": interval((plan.get("entry") or {}).get("low"), (plan.get("entry") or {}).get("high")) if active else "未建立正式進場區間",
        "停損": price(plan.get("stop")) if active else "未建立正式停損",
        "目標區": interval((plan.get("target") or {}).get("low"), (plan.get("target") or {}).get("high")) if active else "未建立正式目標區",
        "今天實際走勢": zh(card.get("actual_direction") or review.get("actual_direction") or (card.get("direction") or {}).get("actual") if isinstance(card.get("direction"), dict) else card.get("actual_direction") or review.get("actual_direction")),
        "今天實際區間": interval(card.get("actual_low", review.get("actual_low", actual.get("low", card.get("session_low")))),
                                card.get("actual_high", review.get("actual_high", actual.get("high", card.get("session_high"))))),
        "今日狀態": zh(card.get("holding_decision") or card.get("canonical_overnight_action") or card.get("data_status")),
        "方向預測結果": zh(human.get("direction_result") or (card.get("direction") or {}).get("result") if isinstance(card.get("direction"), dict) else human.get("direction_result")), "區間預測結果": zh(human.get("range_result")),
    }
    # Existing intraday products inherit their pre-open forecast. Never relabel its horizon.
    if window in {"intraday_1305", "us_intraday_2300"}:
        values["走勢預測（現在→收盤）"] = INTRADAY_MISSING
        values["預測區間"] = INTRADAY_MISSING
    # This is a display of separate canonical results, not a new combined grade.
    values["今日預測結果"] = f"方向：{values['方向預測結果']}；區間：{values['區間預測結果']}"
    return {"schema_version": VERSION, "market": market, "window": window,
            "symbol": str(card.get("symbol") or card.get("stock_id") or ""),
            "name": str(card.get("name") or card.get("stock_name") or ""),
            "source_digest": digest(original), "fields": [{"label": k, "value": values[k]} for k in LABELS[window]],
            "line_range": values["預測區間"], "news": news, "evidence": original}


def project_payload(payload, market, window):
    return {"schema_version": VERSION, "source_digest": digest(payload), "market": market, "window": window,
            "cards": [project_card(c, market, window) for c in cards_for(payload, window)]}


CSS = """.mobile-decision{box-sizing:border-box;max-width:100%;min-width:0;color:#18343c}.mobile-decision *{box-sizing:border-box;min-width:0;overflow-wrap:anywhere}.mobile-decision-card{padding:18px;margin:16px 0;background:#fff;border:1px solid #dce8eb;border-radius:14px}.mobile-decision-card h3{font-size:21px;margin:0 0 14px}.mobile-decision-card dl{margin:0;display:grid;gap:14px}.mobile-decision-card dt{font-size:13px;color:#526b73;margin-bottom:4px}.mobile-decision-card dd{margin:0;font-size:17px;line-height:1.6}.mobile-decision details{margin:16px 0;border:1px solid #dce8eb;border-radius:10px}.mobile-decision summary{cursor:pointer;min-height:44px;padding:14px;font-size:15px;font-weight:700}.mobile-decision .evidence-body{padding:12px;max-width:100%;overflow:auto}.mobile-decision pre{white-space:pre-wrap;font-size:12px}.mobile-decision .evidence-notice{font-size:13px;color:#526b73}@media(max-width:640px){.mobile-decision-card{width:100%;padding:16px}.mobile-decision-card dd{font-size:16px}}"""


def render_primary(payload, market, window):
    projection = project_payload(payload, market, window)
    out = []
    for c in projection["cards"]:
        fields = "".join(f"<div><dt>{escape(x['label'])}</dt><dd>{escape(x['value'])}</dd></div>" for x in c["fields"])
        out.append(f'<article class="mobile-decision-card" data-source-digest="{c["source_digest"]}"><h3>{escape(c["symbol"])} {escape(c["name"])}</h3><dl>{fields}</dl></article>')
    return f'<style>{CSS}</style><section class="mobile-decision" data-presentation-version="{VERSION}" data-source-digest="{projection["source_digest"]}"><h2>{TITLES[window]}</h2>{"".join(out) or "<p>本批次尚未提供正式資料。</p>"}</section>'


def render_report(payload, market, window, legacy_html):
    summary = "詳細評估、技術分析、信心／品質與研究證據" if window in {"post_close_1500", "us_post_close_review_0630"} else "技術分析、信心／品質與研究證據"
    return render_primary(payload, market, window) + f'<section class="mobile-decision"><details data-ai-dev-255-evidence><summary>{summary}</summary><div class="evidence-body"><p class="evidence-notice">以下保留既有詳細報告、來源鏈與系統診斷；原始來源可能包含英文，未改寫正式預測或評估。</p>{legacy_html}</div></details></section>'


def render_line(payload, market, window, url):
    projection = project_payload(payload, market, window)
    lines = ["【決策摘要】" + TITLES[window]]
    for card in projection["cards"]:
        fields = {x["label"]: x["value"] for x in card["fields"]}
        if window in {"post_close_1500", "us_post_close_review_0630"}:
            selected = [(k, fields[k]) for k in LABELS[window][:3]]
        elif window == "pre_close_1335":
            selected = [(k, fields[k]) for k in LABELS[window][:3]]
        else:
            direction = "走勢預測（現在→收盤）" if "intraday" in window else "走勢預測"
            selected = [(direction, fields[direction]), ("股價區間", card["line_range"]), ("投資策略", fields["投資策略"])]
        lines.append(card["symbol"] + " " + card["name"])
        lines.extend(k + "：" + v for k, v in selected)
    if not projection["cards"]:
        lines.append("本批次尚未提供正式資料，不沿用其他窗口內容。")
    lines.extend(["完整報告：", url, "僅供研究參考，非交易指令。"])
    return "\n".join(lines)
