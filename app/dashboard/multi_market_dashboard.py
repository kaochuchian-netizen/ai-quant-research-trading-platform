"""Multi-market Dashboard V2 renderer for TW/US route isolation."""
from __future__ import annotations

import html
import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.reports.window_report_contract import all_window_report_contracts, get_window_report_contract
from app.reports.decision_intelligence_v4 import compact_summary, project_decision_intelligence_v4
from app.dashboard.decision_presentation import (
    decision_presentation_v2,
    clean_text,
    format_availability,
    format_confidence,
    format_data_quality,
    format_direction,
    format_factor_coverage,
    format_optional_price,
    format_percent,
    format_position_size,
    format_price_zone,
    format_ratio,
    format_review_status,
    format_risk_level,
    format_score_components,
    format_setup,
    format_stop,
    format_trend,
    is_no_trade,
    limit_items,
)
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots, revisions_for_snapshot, same_window_change
from app.dashboard.market_dashboard_alias import identity_attributes, resolve_active_snapshot, snapshot_parity_contract
from app.us_stock.runtime_provenance import classify_runtime_provenance, is_dashboard_eligible
from app.us_stock.research_presentation import current_news_presentation
from app.reports.tw_1335_snapshot_delivery import context_for_snapshot as tw_1335_context_for_snapshot, render_dashboard as render_tw_1335_dashboard
from app.reports.tw_four_window_decision import (
    aggregate_cards as aggregate_tw_lifecycle,
    localize as localize_tw_value,
    normalize_lifecycle_card,
    sanitize_text as sanitize_tw_text,
)
from app.reports.presentation_normalization import (
    concise_news_summary,
    format_adr_context,
    format_distance,
    format_price_range,
    format_market_time,
    format_timestamp,
    localize_enum,
    next_action_for_outcome,
    next_session_action,
    safe_public_text,
)
from app.reports.canonical_outcomes import aggregate_us_post_close_review, normalize_review_card
from app.reports.tw_pre_open_structured import aggregate as aggregate_tw_pre_open
from app.reports.tw_pre_open_quality import data_gaps as canonical_pre_open_gaps, public_reason, public_reasons, technical_contract
from app.reports.tw_prediction_explainability import project_tw_prediction_card
from app.reports.tw_preopen_product_intelligence import portfolio_summary as tw_preopen_product_summary

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_BASE_URL = "http://35.201.242.167/stock-ai-dashboard"
LANDING_ROUTE = "/index.html"
TW_ROUTE = "/dashboard/tw/index.html"
US_ROUTE = "/dashboard/us/index.html"
OLD_ROUTE = "/dashboard/decision-intelligence/four-window-preview/index.html"
LEGACY_DEBUG_ROUTE = "/debug/legacy/index.html"
PRODUCTION_LANDING_OWNER = "app.dashboard.multi_market_dashboard.publish_pages"
TW_URL = PUBLIC_BASE_URL + TW_ROUTE
US_URL = PUBLIC_BASE_URL + US_ROUTE
LANDING_URL = PUBLIC_BASE_URL + LANDING_ROUTE
STATIC_ROOT = Path("/var/www/stock-ai-dashboard")
TW_TEMPLATE = REPO_ROOT / "templates/four_window_dashboard_route_preview.example.html"
OUTPUT_DIR = REPO_ROOT / "templates/multi_market_dashboard_v2"
WINDOW_SNAPSHOT_ARCHIVE = REPO_ROOT / "artifacts/archive/window_snapshots"
TW_DAILY_TACTICAL_RUNTIME = REPO_ROOT / "artifacts/runtime/tw_daily_tactical/tw_daily_tactical_latest.json"
US_RUNTIME_FILES = [
    REPO_ROOT / "artifacts/runtime/us_stock/us_pre_market_2000_latest.json",
    REPO_ROOT / "artifacts/runtime/us_stock/us_intraday_2300_latest.json",
    REPO_ROOT / "artifacts/runtime/us_stock/us_post_close_review_0630_latest.json",
    REPO_ROOT / "artifacts/runtime/us_stock/us_stock_pre_market_latest.json",
    REPO_ROOT / "artifacts/runtime/us_stock/us_stock_intraday_latest.json",
    REPO_ROOT / "artifacts/runtime/us_stock/us_stock_post_close_review_latest.json",
]

US_WINDOWS = {
    "us_pre_market_2000": "美股盤前 20:00",
    "us_intraday_2300": "美股盤中 23:00",
    "us_post_close_review_0630": "美股檢討 06:30",
}

SHARED_NAVIGATION_CSS = """.market-shared-navigation{background:white;color:#17262c}.market-shared-navigation__grid{display:grid;grid-template-columns:1fr;gap:12px;margin:14px 0 10px}.market-shared-navigation__button{display:block;width:100%;box-sizing:border-box;background:#fff;color:#0f2c33;text-decoration:none;border:1px solid #cbd8dc;border-radius:8px;padding:13px 14px;font-weight:800;text-align:left;box-shadow:0 1px 0 rgba(15,44,51,.04)}.market-shared-navigation__button[aria-current="page"]{border-color:#83aab4;background:#f4fbfd}.market-shared-navigation__subtitle{margin:10px 0 0;color:#51666d}@media(max-width:640px){.market-shared-navigation__grid{gap:10px}.market-shared-navigation__button{padding:14px 13px}}"""

TW_TACTICAL_CSS = """html,body{max-width:100%;overflow-x:hidden}.wrap,.section{box-sizing:border-box;max-width:100%;overflow-wrap:anywhere}.wrap,main.wrap{padding-left:max(18px,env(safe-area-inset-left));padding-right:max(18px,env(safe-area-inset-right))}.decision-grid{display:grid;width:100%;max-width:100%;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.decision-card{min-width:0;overflow-wrap:anywhere;word-break:break-word;padding:16px;border-radius:12px}.decision-card__head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap}.decision-card__market{font-size:12px;font-weight:800;color:#51666d}.decision-badge{display:inline-block;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:800;background:#eef6f7;color:#234c55}.decision-badge--warn{background:#fff2d4;color:#7a4d00}.decision-badge--ok{background:#e9f7ed;color:#1f6b35}.decision-section{border-top:1px solid #e5eef0;margin-top:12px;padding-top:12px}.decision-section h4{margin:0 0 8px;font-size:15px}.decision-summary-v2{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.decision-summary-card{background:#f7fafb;border:1px solid #dce8eb;border-radius:8px;padding:12px;min-width:0}.decision-summary-card__label{font-size:12px;font-weight:900;color:#51666d}.decision-summary-card__value{font-size:17px;font-weight:900;color:#14333a;overflow-wrap:anywhere}.decision-summary-card__sub{font-size:13px;color:#51666d;overflow-wrap:anywhere}.decision-plan{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.decision-metric{background:#f7fafb;border:1px solid #dce8eb;border-radius:8px;padding:10px;min-width:0}.decision-metric dt{font-size:12px}.decision-metric dd{font-size:15px;font-weight:800;color:#14333a}.decision-list{margin:0;padding-left:18px}.decision-list li{margin:5px 0}.decision-details{margin-top:12px;border:1px solid #dce8eb;border-radius:8px;background:#fbfdfe;overflow-wrap:anywhere}.decision-details summary{cursor:pointer;list-style:none;padding:13px 14px;font-weight:900;min-height:24px}.decision-details summary::-webkit-details-marker{display:none}.decision-details__body{padding:0 14px 14px}.decision-table{width:100%;border-collapse:collapse;table-layout:fixed}.decision-table th,.decision-table td{border-top:1px solid #e5eef0;text-align:left;padding:8px;vertical-align:top;overflow-wrap:anywhere}.decision-table th{color:#51666d;width:45%;font-size:13px}.decision-note{color:#51666d}.decision-compact{display:grid;gap:8px}.decision-status-low{color:#8a4b00}.decision-status-good{color:#1f6b35}@media(max-width:640px){.wrap,main.wrap{padding-left:max(18px,env(safe-area-inset-left));padding-right:max(18px,env(safe-area-inset-right))}.section{padding:16px}.stock-card,.status-card,.decision-card{padding:16px}.grid,.decision-grid{grid-template-columns:1fr!important;gap:16px}.decision-summary-v2{grid-template-columns:1fr}.decision-card{width:100%;box-sizing:border-box}.decision-plan{grid-template-columns:1fr}.decision-details summary{padding:14px}.decision-details__body{padding:0 14px 14px}.decision-table th,.decision-table td{display:block;width:100%;box-sizing:border-box}.decision-table td{border-top:0;padding-top:0}}"""
def now_taipei() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()

def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def stable_html(payload: str) -> str:
    return "\n".join(line.rstrip() for line in payload.splitlines()) + "\n"

def read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:
        return None
    return None

def _escape(value: Any) -> str:
    if value is None or value == "":
        return "資料待接"
    return html.escape(str(value))



def _fmt_zone(zone: Any) -> str:
    if not isinstance(zone, dict):
        return "資料不足"
    low = zone.get("low")
    high = zone.get("high")
    if low is None or high is None:
        return "資料不足"
    return f"{_escape(low)} ～ {_escape(high)}"


def _load_tw_tactical_artifact() -> dict[str, Any] | None:
    data = read_json(TW_DAILY_TACTICAL_RUNTIME)
    if not data:
        return None
    if data.get("market") != "TW" or data.get("strategy_type") != "daily_tactical":
        return None
    return data



def _html_list(items: Any, fallback: str) -> str:
    return "".join(f"<li>{_escape(item)}</li>" for item in limit_items(items, fallback=fallback))


def _table_rows(rows: list[tuple[str, Any]]) -> str:
    return "".join(f"<tr><th>{_escape(label)}</th><td>{_escape(value)}</td></tr>" for label, value in rows)


def _metric(label: str, value: Any) -> str:
    return f"<dl class=\"decision-metric\"><dt>{_escape(label)}</dt><dd>{_escape(value)}</dd></dl>"


def _source_freshness_text(value: Any) -> str:
    text = clean_text(value, missing="資料不足")
    return {
        "SEC/yfinance/news metadata checked": "SEC、yfinance 與新聞來源已檢查",
        "metadata checked": "資料來源已檢查",
        "live market data fetched": "已取得最新市場資料",
    }.get(text, text)


def _readiness_rows(readiness: Any) -> list[tuple[str, str]]:
    if not isinstance(readiness, dict):
        return [("系統準備狀態", "資料不足")]
    mapping = {
        "dashboard_ready": "Dashboard",
        "email_ready": "Email",
        "line_ready": "LINE",
        "expected_stock_count": "預期股票數",
        "actual_stock_count": "實際股票數",
        "tactical_coverage": "Tactical 覆蓋",
        "prediction_coverage": "Prediction 覆蓋",
        "insufficient_data_count": "資料不足",
    }
    rows: list[tuple[str, str]] = []
    for key, label in mapping.items():
        if key not in readiness:
            continue
        value = readiness.get(key)
        if isinstance(value, bool):
            value = "可用" if value else "未就緒"
        rows.append((label, clean_text(value, missing="資料不足")))
    return rows or [("系統準備狀態", "資料不足")]


def _playbook_text(tactical: dict[str, Any]) -> str:
    text = clean_text(tactical.get("playbook"), missing="")
    if text:
        return text
    setup = clean_text(tactical.get("setup_type"), missing="no_trade")
    if setup == "breakout":
        return "等待有效突破壓力並確認量能；未站穩突破區不追價，跌回失效區取消。"
    if setup == "pullback":
        return "等待回測支撐或短期均線止穩；量縮不破可觀察，跌破結構支撐取消。"
    if setup == "range_trade":
        return "接近區間支撐才具備操作價值；接近壓力不追價，跌破區間下緣取消。"
    if setup == "mean_reversion":
        return "僅在超跌後出現止穩訊號時觀察；若中期結構繼續轉弱，不建立部位。"
    return "目前缺乏合理進場結構、資料品質不足或報酬風險不合格，暫不建立戰術部位。"


def _review_rows(review: dict[str, Any]) -> list[tuple[str, Any]]:
    status = review.get("status") or review.get("review_status")
    return [
        ("狀態", format_review_status(status)),
        ("是否進場", clean_text(review.get("entry_zone_touched") or review.get("entry_triggered"), missing="否")),
        ("第一目標", "已觸發" if review.get("target_1_reached") is True else "尚未觸發"),
        ("第二目標", "已觸發" if review.get("target_2_reached") is True else "尚未觸發"),
        ("停損", "已觸發" if review.get("stop_breached") is True else "尚未觸發"),
        ("MFE / MAE", f"{clean_text(review.get('mfe'), missing='暫無')} / {clean_text(review.get('mae'), missing='暫無')}"),
    ]


def _research_rows(research: dict[str, Any]) -> list[tuple[str, Any]]:
    prediction = research.get("prediction", {}) if isinstance(research.get("prediction"), dict) else {}
    return [
        ("評等", clean_text(research.get("rating"), missing="部分研究資料尚未完成")),
        ("建議", clean_text(research.get("action"), missing="部分研究資料尚未完成")),
        ("信心", format_confidence(research.get("confidence"))),
        ("1 個月", format_trend(prediction.get("one_month_trend"))),
        ("3 個月", format_trend(prediction.get("three_month_trend"))),
    ]


def _tactical_values(tactical: dict[str, Any]) -> dict[str, Any]:
    return {
        "direction": tactical.get("direction") or tactical.get("tactical_direction"),
        "setup": tactical.get("setup_type"),
        "action": tactical.get("action"),
        "score": tactical.get("score") or tactical.get("tactical_score"),
        "rating": tactical.get("rating") or tactical.get("tactical_grade") or tactical.get("grade"),
        "confidence": tactical.get("confidence") or tactical.get("tactical_confidence"),
        "entry": tactical.get("entry_zone"),
        "stop": tactical.get("stop_invalidation") or tactical.get("stop_reference") or tactical.get("invalidation_level"),
        "target1": tactical.get("target_1") or tactical.get("target_zone_1"),
        "target2": tactical.get("target_2") or tactical.get("target_zone_2"),
        "expected": tactical.get("expected_move_pct") if tactical.get("expected_move_pct") is not None else tactical.get("expected_move"),
        "rr": tactical.get("reward_risk") if tactical.get("reward_risk") is not None else tactical.get("reward_risk_ratio"),
        "chase": tactical.get("chase_risk"),
        "event": tactical.get("event_risk"),
        "position": tactical.get("position_size"),
        "data_quality": tactical.get("data_quality"),
    }


def _decision_summary(tactical: dict[str, Any]) -> str:
    if is_no_trade(tactical):
        risks = limit_items(tactical.get("risk_reasons"), limit=1, fallback="目前缺乏合理進場結構")
        return risks[0]
    reasons = limit_items(tactical.get("reasons"), limit=1, fallback="已形成可觀察的短線結構")
    return reasons[0]


def _summary_cards_v2(presentation: dict[str, Any]) -> str:
    cards = presentation.get("summary_cards", {})
    order = ["research", "daily_tactical", "prediction", "confidence"]
    labels = {"research": "中長期研究", "daily_tactical": "每日短線策略", "prediction": "預測", "confidence": "信心"}
    blocks = []
    for key in order:
        card = cards.get(key, {}) if isinstance(cards, dict) else {}
        blocks.append(
            "<div class=\"decision-summary-card\">"
            f"<div class=\"decision-summary-card__label\">{_escape(card.get('title') or labels[key])}</div>"
            f"<div class=\"decision-summary-card__value\">{_escape(card.get('value'))}</div>"
            f"<div class=\"decision-summary-card__sub\">{_escape(card.get('subvalue'))}</div>"
            "</div>"
        )
    return f"<section class=\"decision-section\"><h4>今日結論</h4><div class=\"decision-summary-v2\">{''.join(blocks)}</div></section>"


def _decision_sections_v2(presentation: dict[str, Any], review: dict[str, Any] | None = None, detail_rows: list[tuple[str, Any]] | None = None) -> str:
    tactical = presentation.get("daily_tactical", {})
    prediction = presentation.get("prediction", {})
    research = presentation.get("research", {})
    research_v3 = presentation.get("research_v3", {})
    detail = presentation.get("technical_detail", {})
    review = review or {}
    detail_rows = detail_rows or []
    daily = f"""
          <section class="decision-section"><h4>每日短線策略</h4><div class="decision-plan">{_metric('方向', tactical.get('direction'))}{_metric('策略型態', tactical.get('setup'))}{_metric('操作建議', tactical.get('action'))}{_metric('進場區', tactical.get('entry_zone'))}{_metric('停損／失效價', tactical.get('stop'))}{_metric('第一目標', tactical.get('target_1'))}{_metric('第二目標', tactical.get('target_2'))}{_metric('預期波動', tactical.get('expected_move'))}{_metric('報酬風險比', tactical.get('reward_risk'))}{_metric('信心', tactical.get('confidence'))}{_metric('風險', tactical.get('risk'))}{_metric('今日操作結論', tactical.get('conclusion'))}</div></section>
    """
    pred = f"""
          <section class="decision-section"><h4>預測</h4><div class="decision-plan">{_metric("今日預測區間", prediction.get('today_range'))}{_metric('明日預測區間', prediction.get('tomorrow_range'))}{_metric('預期區間', prediction.get('expected_range'))}{_metric('預期波動', prediction.get('expected_move'))}{_metric('信心', prediction.get('confidence'))}{_metric('狀態', prediction.get('status'))}</div><p class="decision-note">{_escape(prediction.get('reason'))}</p></section>
    """
    news_events = research_v3.get("news_events", {}) if isinstance(research_v3.get("news_events"), dict) else {}
    research_html = f"""
          <section class="decision-section"><h4>中長期研究</h4><div class="decision-plan">{_metric('一句話結論', research_v3.get('one_line_conclusion') or research.get('conclusion'))}{_metric('基本面評等', research_v3.get('research_rating') or research.get('rating'))}{_metric('財務體質', research.get('financial_quality'))}{_metric('財報', research_v3.get('earnings') or research.get('earnings'))}{_metric('最近官方文件（SEC）', research_v3.get('sec') or research.get('sec'))}{_metric('策略檢討摘要', research_v3.get('review') or research.get('review'))}{_metric('研究結論', research_v3.get('research_conclusion') or research.get('conclusion'))}{_metric('1 個月趨勢', research.get('one_month'))}{_metric('3 個月趨勢', research.get('three_month'))}</div></section>
    """
    news_html = f"""
          <section class="decision-section"><h4>近期新聞與事件</h4><div class="decision-plan">{_metric('重大官方事件', news_events.get('official'))}{_metric('近期市場新聞', news_events.get('market'))}{_metric('新聞資料狀態', news_events.get('status'))}</div></section>
    """
    reasons = f"<section class=\"decision-section\"><h4>主要依據（股票專屬）</h4><ul class=\"decision-list\">{''.join(f'<li>{_escape(item)}</li>' for item in presentation.get('reasons', []))}</ul></section>"
    risks = f"<section class=\"decision-section\"><h4>主要風險（股票專屬）</h4><ul class=\"decision-list\">{''.join(f'<li>{_escape(item)}</li>' for item in presentation.get('risks', []))}</ul></section>"
    details = f"""
          <details class="decision-details"><summary>技術與系統細節</summary><div class="decision-details__body"><h4>資料來源</h4><table class="decision-table"><tbody>{_table_rows(detail.get('factor_coverage', []))}</tbody></table><h4>分數構成</h4><table class="decision-table"><tbody>{_table_rows(detail.get('score_components', []))}</tbody></table><h4>系統資料細節</h4><table class="decision-table"><tbody>{_table_rows(detail_rows + [('策略代碼', detail.get('strategy_id')), ('因子版本', detail.get('factor_version'))])}</tbody></table></div></details>
    """
    review_html = f"<details class=\"decision-details\"><summary>策略檢討</summary><div class=\"decision-details__body\"><table class=\"decision-table\"><tbody>{_table_rows(_review_rows(review))}</tbody></table></div></details>"
    return daily + pred + research_html + reasons + risks + news_html + review_html + details

def render_tw_tactical_cards(artifact: dict[str, Any] | None = None) -> str:
    artifact = artifact if artifact is not None else _load_tw_tactical_artifact()
    if not artifact:
        return """<div class="wrap section" id="tw-daily-tactical-runtime" data-strategy-type="daily_tactical"><h2>每日短期操作策略</h2><p>TW Daily Tactical runtime artifact 尚未產生；不會用 Research 或 US 資料 fallback。</p></div>"""
    cards = artifact.get("cards", []) if isinstance(artifact.get("cards"), list) else []
    market_context = artifact.get("market_context", {}) if isinstance(artifact.get("market_context"), dict) else {}
    readiness = artifact.get("delivery_readiness")
    header = f"""
    <div class="wrap section" id="tw-daily-tactical-runtime" data-market="TW" data-strategy-type="daily_tactical">
      <h2>每日短期操作策略</h2>
      <p class="decision-note">更新：{_escape(artifact.get('generated_at'))}｜市場：{_escape(format_direction(market_context.get('market_bias')))}｜風險：{_escape(format_risk_level(market_context.get('market_risk')))}</p>
      <p class="decision-note">主畫面優先呈現今日結論、操作計畫與風險；資料來源與分數構成收合在技術與資料細節。</p>
      <details class="decision-details"><summary>系統準備狀態</summary><div class="decision-details__body"><table class="decision-table"><tbody>{_table_rows(_readiness_rows(readiness))}</tbody></table></div></details>
      <div class="grid decision-grid tw-tactical-grid">
    """
    rows: list[str] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
        research = strategies.get("research_position", {}) if isinstance(strategies.get("research_position"), dict) else {}
        tactical = strategies.get("daily_tactical", {}) if isinstance(strategies.get("daily_tactical"), dict) else {}
        review = card.get("review_snapshot", {}) if isinstance(card.get("review_snapshot"), dict) else {}
        values = _tactical_values(tactical)
        no_trade = is_no_trade(tactical)
        action = "暫不操作" if no_trade else clean_text(values.get("action"), missing="等待確認")
        badge_class = "decision-badge--warn" if no_trade else "decision-badge--ok"
        entry = "暫無" if no_trade else format_price_zone(values.get("entry"))
        stop = "暫無" if no_trade else format_stop(values.get("stop"))
        target1 = "暫無" if no_trade else format_price_zone(values.get("target1"))
        target2 = "暫無" if no_trade else format_price_zone(values.get("target2"))
        factor_rows = format_factor_coverage(tactical.get("factor_coverage") or tactical.get("source_status"))
        score_rows = format_score_components(tactical.get("score_components"))
        detail_rows = [
            ("策略代號", clean_text(tactical.get("strategy_id"))),
            ("策略版本", clean_text(tactical.get("strategy_version"))),
            ("因子版本", clean_text(tactical.get("factor_version"))),
            ("產生時間", clean_text(tactical.get("generated_at"))),
        ]
        presentation = decision_presentation_v2("TW", card)
        detail_rows = [
            ("產生時間", clean_text(tactical.get("generated_at"))),
            ("資料完整度", format_data_quality(tactical.get("data_quality"))),
        ]
        rows.append(f"""
        <article class="stock-card decision-card tw-tactical-card" data-market="TW" data-strategy-type="daily_tactical" data-presentation-version="decision_presentation_v3">
          <div class="decision-card__head"><div><div class="decision-card__market">TW｜決策呈現 V3</div><h3>{_escape(card.get('stock_id'))} {_escape(card.get('stock_name'))}</h3></div><span class="decision-badge {'decision-badge--warn' if is_no_trade(tactical) else 'decision-badge--ok'}">{_escape(presentation['daily_tactical']['action'])}</span></div>
          {_summary_cards_v2(presentation)}
          {_decision_sections_v2(presentation, review, detail_rows)}
        </article>
        """)
    return header + "\n".join(rows) + "</div></div>"

def _strategy_html(card: dict[str, Any]) -> str:
    strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
    research = strategies.get("research_position") or card.get("research_position_summary") or {}
    tactical = strategies.get("daily_tactical") or card.get("daily_tactical_summary") or {}
    values = _tactical_values(tactical if isinstance(tactical, dict) else {})
    no_trade = is_no_trade(tactical) if isinstance(tactical, dict) else False
    entry = "暫無" if no_trade else format_price_zone(values.get("entry"))
    stop = "暫無" if no_trade else format_stop(values.get("stop"))
    target1 = "暫無" if no_trade else format_price_zone(values.get("target1"))
    target2 = "暫無" if no_trade else format_price_zone(values.get("target2"))
    research_rows = [
        ("Score / Rating", f"{clean_text(research.get('score'), missing='資料不足')} / {clean_text(research.get('rating'), missing='資料不足')}"),
        ("Action", clean_text(research.get("action"), missing="資料不足")),
        ("Confidence", format_confidence(research.get("confidence"))),
        ("Horizon", clean_text(research.get("horizon"), missing="days to months")),
    ]
    return f"""
              <section class="decision-section strategy-pair" data-strategy="dual">
                <h4>Research / Position Strategy</h4>
                <table class="decision-table"><tbody>{_table_rows(research_rows)}</tbody></table>
              </section>
              <section class="decision-section">
                <h4>Daily Tactical Strategy</h4>
                <div class="decision-plan">{_metric('今日建議', '暫不操作' if no_trade else clean_text(values.get('action'), missing='等待確認'))}{_metric('方向', format_direction(values.get('direction')))}{_metric('策略', format_setup(values.get('setup')))}{_metric('信心', format_confidence(values.get('confidence')))}</div>
              </section>
              <section class="decision-section"><h4>操作計畫</h4><div class="decision-plan">{_metric('進場區', entry)}{_metric('停損／策略失效', stop)}{_metric('第一目標', target1)}{_metric('第二目標', target2)}{_metric('報酬風險比', format_ratio(values.get('rr')))}{_metric('部位建議', format_position_size(values.get('position')))}</div></section>
              <section class="decision-section"><h4>信心與風險</h4><div class="decision-plan">{_metric('追價風險', format_risk_level(values.get('chase')))}{_metric('事件風險', format_risk_level(values.get('event')))}{_metric('資料完整度', format_data_quality(values.get('data_quality')))}{_metric('預期波動', format_percent(values.get('expected')))}</div></section>
              <section class="decision-section"><h4>主要依據</h4><ul class="decision-list">{_html_list(tactical.get('reasons') if isinstance(tactical, dict) else [], '目前沒有足夠依據')}</ul></section>
              <section class="decision-section"><h4>主要風險</h4><ul class="decision-list">{_html_list(tactical.get('risk_notes') or tactical.get('risk_reasons') if isinstance(tactical, dict) else [], '目前未偵測到額外風險')}</ul></section>
              <section class="decision-section"><h4>操作劇本</h4><p>{_escape(_playbook_text(tactical if isinstance(tactical, dict) else {}))}</p></section>
              <details class="decision-details"><summary>技術與資料細節</summary><div class="decision-details__body"><h4>資料來源狀態</h4><table class="decision-table"><tbody>{_table_rows(format_factor_coverage(tactical.get('factor_coverage') if isinstance(tactical, dict) else None))}</tbody></table><h4>分數構成</h4><table class="decision-table"><tbody>{_table_rows(format_score_components(tactical.get('score_components') if isinstance(tactical, dict) else None))}</tbody></table></div></details>
    """

def _is_authoritative_us_artifact(data: dict[str, Any]) -> bool:
    return is_dashboard_eligible(data)


def _load_us_artifacts() -> list[dict[str, Any]]:
    artifacts = []
    seen_windows: set[str] = set()
    for path in US_RUNTIME_FILES:
        data = read_json(path)
        if not data:
            continue
        if not _is_authoritative_us_artifact(data):
            continue
        window = str(data.get("window") or path.name)
        if window in seen_windows:
            continue
        try:
            data["_source_path"] = str(path.relative_to(REPO_ROOT))
        except ValueError:
            data["_source_path"] = str(path)
        artifacts.append(data)
        seen_windows.add(window)
    return artifacts

def us_stock_count(artifacts: list[dict[str, Any]]) -> int:
    symbols: set[str] = set()
    for artifact in artifacts:
        for card in artifact.get("dashboard_ready_contract", {}).get("cards", []):
            symbol = card.get("symbol") if isinstance(card, dict) else None
            if symbol:
                symbols.add(str(symbol))
    return len(symbols)


def _operations_runtime_provenance(market: str, window: str, latest: dict[str, Any] | None) -> str:
    if market == "US":
        for path in US_RUNTIME_FILES:
            data = read_json(path)
            if data and str(data.get("window")) == window:
                return classify_runtime_provenance(data)
    return str(latest.get("runtime_provenance")) if latest else "尚無正式 Runtime"

def _exchange_for(artifact: dict[str, Any], symbol: str) -> str:
    for item in artifact.get("us_watchlist", []):
        if isinstance(item, dict) and item.get("symbol") == symbol:
            return str(item.get("exchange") or "資料待接")
    return "資料待接"

def _card_key(card: dict[str, Any], window: str) -> str:
    return str(card.get("symbol") or "") + "::" + window

def render_us_cards(artifacts: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if artifact.get("market") != "US":
            rows.append("<article class='status-card warn'><h3>資料市場不符</h3><p>US Dashboard 拒絕非 US artifact。</p></article>")
            continue
        window = str(artifact.get("window") or "us_pre_market_2000")
        window_label = US_WINDOWS.get(window, window)
        for card in artifact.get("dashboard_ready_contract", {}).get("cards", []):
            if not isinstance(card, dict):
                continue
            key = _card_key(card, window)
            if key in seen:
                continue
            seen.add(key)
            symbol = str(card.get("symbol") or "")
            earnings_guidance = f"{format_availability(card.get('latest_earnings_status'))} / {format_availability(card.get('guidance_direction'))}"
            presentation = decision_presentation_v2("US", card)
            rows.append(f"""
            <article class="stock-card decision-card us-stock-card" data-market="US" data-presentation-version="decision_presentation_v3">
              <div class="decision-card__head"><div><div class="decision-card__market">{html.escape(window_label)}｜US｜決策呈現 V3</div><h3>{_escape(symbol)} {_escape(card.get('name'))}</h3></div><span class="decision-badge">{_escape(presentation['research']['rating'])}</span></div>
              {_summary_cards_v2(presentation)}
              {_decision_sections_v2(presentation, {"status": artifact.get('prediction_review_contract', {}).get('review_status')}, [("批次", window_label), ("資料新鮮度", _source_freshness_text(card.get('source_freshness')))])}
            </article>
            """)
    if not rows:
        rows.append('<article class="status-card warn" data-market="US"><h3>正式美股資料尚未產生</h3><p>尚未找到 live production US runtime artifact；不會回退到台股資料，也不會渲染 validation fixture。</p></article>')
    return "\n".join(rows)


def _us_cards_for_window(artifacts: list[dict[str, Any]], window: str) -> list[dict[str, Any]]:
    for artifact in artifacts:
        if artifact.get("market") == "US" and str(artifact.get("window")) == window:
            return [card for card in artifact.get("dashboard_ready_contract", {}).get("cards", []) if isinstance(card, dict)]
    return []

def _intraday_number(value: Any, suffix: str = "") -> str:
    try:
        return f"{float(value):.2f}{suffix}"
    except (TypeError, ValueError):
        return "尚未取得"

def _intraday_state(value: Any) -> str:
    labels = {
        "gap_up_follow_through": "向上跳空延續", "gap_up_partial_fill": "向上跳空部分回補",
        "gap_up_full_fill": "向上跳空完全回補", "gap_down_follow_through": "向下跳空延續",
        "gap_down_partial_fill": "向下跳空部分回補", "gap_down_full_fill": "向下跳空完全回補",
        "flat_open": "平盤開出", "strong": "量能強", "confirmed": "量能確認",
        "neutral": "量能中性", "weak": "量能偏弱", "insufficient_history": "同期量歷史不足",
        "source_unavailable": "成交量來源未取得", "inside_zone": "位於進場區",
        "triggered": "已觸發", "not_reached": "尚未到達", "passed_without_safe_entry": "已越過安全進場區",
        "invalidated": "已失效", "maintain_watch": "維持觀察", "entry_triggered_hold": "觸發後續抱觀察",
        "wait_for_volume": "等待量能確認", "cancel_chase": "取消追價", "reduce_risk": "降低風險",
        "stop_invalidated": "停損失效", "target_near": "接近目標", "data_unavailable": "資料不足，暫不判定",
        "market_closed": "市場休市", "stale": "行情過舊", "partial": "部分資料可用", "complete": "盤中資料完整",
        "unavailable": "盤中行情取得失敗",
    }
    return labels.get(str(value), str(value or "尚未取得"))


def _us_proximity(card: dict[str, Any], kind: str) -> str:
    value = card.get(f"distance_to_{kind}_pct")
    if value is None:
        return "不適用"
    try:
        amount = abs(float(value))
    except (TypeError, ValueError):
        return "尚未取得"
    if card.get(f"{kind}_hit"):
        return "已觸及停損" if kind == "stop" else "已觸及目標"
    return f"距停損仍有 {amount:.2f}%" if kind == "stop" else f"距目標 {amount:.2f}%"


def _institutional_research_html(card: dict[str, Any]) -> str:
    bundle = card.get("institutional_research") if isinstance(card.get("institutional_research"), dict) else {}
    if not bundle:
        return "<section class='decision-section' data-section='institutional-research'><h4>機構研究脈絡</h4><p>本歷史資料尚未包含機構研究包。</p></section>"
    synthesis = bundle.get("synthesis") or {}
    coverage = bundle.get("coverage") or {}
    conflict = bundle.get("conflict") or {}
    evidence = [item for item in bundle.get("evidence", []) if isinstance(item, dict) and item.get("counted_in_synthesis")]
    evidence_text = "；".join(
        f"{item.get('headline') or '事件'}（{item.get('provider')}｜品質 {item.get('quality_score')}｜{localize_enum(item.get('direction'))}）"
        for item in evidence[:3]
    ) or "尚無可納入研究合成的事件"
    gaps = "、".join(coverage.get("coverage_gap") or []) or "無"
    identity = str(bundle.get("research_identity") or "尚未取得")
    v2 = bundle.get("research_intelligence_v2") if isinstance(bundle.get("research_intelligence_v2"), dict) else {}
    if v2:
        hypothesis = v2.get("hypothesis") if isinstance(v2.get("hypothesis"), dict) else {}
        context = v2.get("market_sector_context") if isinstance(v2.get("market_sector_context"), dict) else {}
        effective = v2.get("effective_coverage") if isinstance(v2.get("effective_coverage"), dict) else {}
        by_id = {item.get("evidence_id"): item for item in evidence}
        evidence_line = lambda ids: "；".join(
            str((by_id.get(item_id) or {}).get("headline") or item_id) for item_id in (ids or [])[:3]
        ) or "無"
        selected_news = [item for item in (v2.get("selected_news_evidence") or []) if isinstance(item, dict)]
        selected_news_line = "；".join(
            f"{item.get('headline') or '未命名事件'}（{item.get('publisher') or item.get('source_class') or '來源未標示'}｜{item.get('published_at') or '時間未標示'}｜{item.get('source_class') or '來源類別未標示'}｜非方向性）"
            for item in selected_news[:2]
        ) or "本視窗無可選用的當期個股新聞"
        hypothesis_state = {
            "confirmed": "研究假設確認", "invalidated": "研究假設失效",
            "unchanged": "研究假設未改變",
        }.get(str(hypothesis.get("state") or ""), localize_enum(hypothesis.get("state")))
        return (
            "<section class='decision-section' data-section='institutional-research-v2'><h4>US Research Brief｜機構研究脈絡</h4>"
            f"<p>{_escape(v2.get('research_brief') or '研究摘要尚未建立')}</p>"
            + _window_metric_grid([
                ("研究立場", localize_enum(v2.get("research_stance"))),
                ("研究分數（非交易分數）", v2.get("research_score") if v2.get("research_score") is not None else "證據不足"),
                ("研究信心", v2.get("research_confidence")),
                ("有效研究覆蓋", f"{effective.get('score', 0)}%"),
                ("假設狀態", hypothesis_state),
                ("大盤環境", localize_enum(context.get("broad_market"))),
                ("成長／科技", localize_enum(context.get("growth_technology"))),
                ("類股 SOXX", localize_enum(context.get("sector"))),
                ("Window Research Identity", v2.get("window_research_identity")),
                ("Origin Research Identity", identity),
            ])
            + '<details class="research-review-details" data-visual-review-expand="true"><summary>研究證據、假設與校準</summary>'
            + _window_metric_grid([
                ("個股當期證據 Current News", selected_news_line),
                ("支持證據 Supporting", evidence_line(v2.get("supporting_evidence"))),
                ("反對證據 Opposing", evidence_line(v2.get("opposing_evidence"))),
                ("缺失證據 Missing", "、".join(v2.get("missing_evidence") or []) or "無"),
                ("研究假設 Hypothesis", hypothesis.get("statement")),
                ("確認條件 Trigger", hypothesis.get("trigger")),
                ("失效條件 Invalidation", hypothesis.get("invalidation")),
                ("主要風險 Main Risk", v2.get("primary_risk")),
                ("反方論點 Counter", hypothesis.get("counter_argument")),
                ("本視窗更新", (v2.get("window_update") or {}).get("explanation")),
            ])
            + "</details></section>"
        )
    return (
        "<section class='decision-section' data-section='institutional-research'><h4>機構研究脈絡</h4>"
        + _window_metric_grid([
            ("研究立場", localize_enum(synthesis.get("research_stance"))),
            ("研究分數（非交易分數）", synthesis.get("research_score")),
            ("研究信心", synthesis.get("research_confidence")),
            ("來源衝突", conflict.get("level")),
            ("研究覆蓋", f"{coverage.get('score', 0)}%"),
            ("覆蓋缺口", gaps),
            ("最高品質來源", "、".join(synthesis.get("highest_quality_sources") or []) or "尚無"),
            ("Research Identity", identity),
        ])
        + f"<p>{_escape(evidence_text)}</p></section>"
    )


def _us_window_card(card: dict[str, Any], window: str) -> str:
    symbol = _escape(card.get("symbol"))
    name = _escape(card.get("name"))
    presentation = decision_presentation_v2("US", card)
    tactical = presentation.get("daily_tactical", {})
    prediction = presentation.get("prediction", {})
    reason_text = _joined_text(presentation.get("reasons"), "等待量價與資料確認")
    bundle = card.get("institutional_research") if isinstance(card.get("institutional_research"), dict) else {}
    research_v2 = bundle.get("research_intelligence_v2") if isinstance(bundle.get("research_intelligence_v2"), dict) else {}
    risk_text = safe_public_text(research_v2.get("primary_risk"), missing="") or _joined_text(presentation.get("risks"), "未偵測到額外風險")
    current_news = current_news_presentation(card)
    news_text = current_news["compact_summary"]
    sec_text = _research_v3_text(presentation, "sec")
    review_text = _research_v3_text(presentation, "review")
    institutional_research = _institutional_research_html(card)
    report_type = {
        "us_pre_market_2000": "us-pre-market",
        "us_intraday_2300": "us-intraday-change",
        "us_post_close_review_0630": "us-post-close-review",
    }[window]
    if window == "us_pre_market_2000":
        pre = card.get("premarket") if isinstance(card.get("premarket"), dict) else {}
        eligibility = card.get("eligibility") if isinstance(card.get("eligibility"), dict) else {}
        plan = card.get("trade_plan") if isinstance(card.get("trade_plan"), dict) else {}
        event = card.get("event_risk") if isinstance(card.get("event_risk"), dict) else {}
        news = card.get("news_evidence") if isinstance(card.get("news_evidence"), dict) else {}
        sec = card.get("sec_evidence") if isinstance(card.get("sec_evidence"), dict) else {}
        relative = card.get("relative_strength") if isinstance(card.get("relative_strength"), dict) else {}
        active = eligibility.get("actionable") is True
        state = "主要交易機會" if eligibility.get("top_opportunity") else "僅觀察" if eligibility.get("watch_only") else "暫不交易"
        reason_labels = {
            "PREMARKET_DATA_UNAVAILABLE_OR_STALE": "盤前行情尚未取得或已過舊", "RR_BELOW_THRESHOLD": "報酬風險比未達門檻",
            "PREMARKET_SESSION_NOT_STARTED": "尚未進入美股盤前資料可用時段",
            "PREMARKET_DATA_NOT_YET_AVAILABLE": "尚未進入美股盤前資料可用時段",
            "LOW_CONFIDENCE": "信心偏低", "DIRECTION_NOT_BULLISH": "方向尚未轉為偏多", "SETUP_NOT_STABILIZED": "尚未止穩",
            "CHASE_RISK_HIGH": "追價風險偏高", "EVENT_RISK_HIGH": "事件風險偏高",
        }
        reasons = "、".join(reason_labels.get(code, "條件尚未完整") for code in eligibility.get("reason_codes") or []) or "符合盤前資料、信心、報酬風險與事件門檻"
        entry_label = "Entry 進場區" if active else "觀察區間"
        gap = f"{float(pre['gap_pct']):+.2f}%" if isinstance(pre.get("gap_pct"), (int, float)) else "尚未取得"
        change = f"{float(pre['change']):+.2f}（{float(pre['change_pct']):+.2f}%）" if isinstance(pre.get("change"), (int, float)) and isinstance(pre.get("change_pct"), (int, float)) else "尚未取得"
        forecast = card.get("us_premarket_product_projection_v1") or {}
        news_product = card.get("us_news_product_projection_v1") or {}
        availability = ((card.get("session_context") or {}).get("session_availability") or {})
        if availability.get("state") == "PREMARKET_SESSION_NOT_STARTED":
            off_session_note = "<p class='decision-note'>尚未進入美股盤前資料可用時段；此狀態不是新聞或行情來源取得失敗。</p>"
            reasons = "尚未進入美股盤前資料可用時段"
        elif availability.get("state") == "OFF_SESSION_VERIFICATION":
            off_session_note = "<p class='decision-note'>目前為美股非交易時段的 controlled verification；行情 absence 不視為來源取得失敗。</p>"
            reasons = "美股非交易時段，僅驗證產品與既有證據"
        else:
            off_session_note = ""
        direction_label = {"BULLISH": "偏多 ↑", "BEARISH": "偏空 ↓", "SIDEWAYS": "盤整 ↔"}.get(forecast.get("direction"), "盤整 ↔")
        selected_news_html = "".join(f"<li><strong>{_escape(item.get('headline') or item.get('english_headline'))}</strong><br>{_escape(item.get('publisher') or '原始來源未解析')}｜{_escape(item.get('published_at') or '時間未標示')}｜{_escape(item.get('direction_status') or 'NOT_EVALUATED')}</li>" for item in (news_product.get("selected_items") or [])[:3]) or f"<li>{_escape(news_product.get('state_label') or '目前沒有通過門檻的當期消息')}</li>"
        return f"""
        <article class="stock-card decision-card window-stock-card" data-market="US" data-card-type="window-premarket" data-contract-card-type="us-pre-market-v4" data-report-type="{report_type}">
          <div class="decision-card__head"><div><div class="decision-card__market">US｜20:00 美股盤前｜盤前決策</div><h3>{symbol} {name}</h3></div><span class="decision-badge {'decision-badge--ok' if active else 'decision-badge--warn'}">{_escape(state)}</span></div>
          <section class="decision-section us-product-intelligence" data-section="us-premarket-product"><h4>今日盤前判斷</h4>{_window_metric_grid([('方向', direction_label), ('預測目標', forecast.get('target_price')), ('預測區間', f"{forecast.get('predicted_low')} ～ {forecast.get('predicted_high')}"), ('盤前／基準價', forecast.get('reference_price'))])}<p><strong>短評：</strong>{_escape(forecast.get('short_judgment') or '預測資料不足，暫不推導價格情境。')}</p>{off_session_note}<h4>今日重要消息</h4><p>新聞抓取 {news_product.get('retrieved_count', 0)}｜通過篩選 {news_product.get('qualified_count', 0)}｜可用於判斷 {news_product.get('selected_count', 0)}</p><ul>{selected_news_html}</ul><h4>今日行動</h4><p>{_escape(state)}｜{_escape(reasons)}</p></section>
          <section class="decision-section" data-section="premarket-observed"><h4>盤前實際行情</h4>{_window_metric_grid([('盤前價格', pre.get('price')), ('前收', pre.get('previous_close')), ('盤前漲跌', change), ('Gap', gap), ('資料時間', format_timestamp(pre.get('timestamp'), timezone_name='America/New_York')), ('資料來源', pre.get('source')), ('資料狀態', localize_enum(pre.get('availability'))), ('相對 QQQ', f"{float(relative['vs_qqq_pp']):+.2f} 個百分點" if isinstance(relative.get('vs_qqq_pp'), (int, float)) else '尚未取得'), ('相對 SOXX', f"{float(relative['vs_sector_pp']):+.2f} 個百分點" if isinstance(relative.get('vs_sector_pp'), (int, float)) else '尚未取得')])}</section>
          <section class="decision-section" data-section="premarket-eligibility"><h4>行動資格</h4>{_window_metric_grid([('目前狀態', state), ('交易方向', localize_enum(card.get('direction'))), ('策略型態', safe_public_text(card.get('setup_type'))), ('市場方向衝突', '是' if card.get('market_conflict') else '否'), ('進場條件就緒', '是' if eligibility.get('entry_ready') else '否'), ('主要交易機會', '是' if eligibility.get('top_opportunity') else '否'), ('信心', tactical.get('confidence')), ('報酬風險比', plan.get('reward_risk')), ('事件風險', localize_enum(event.get('canonical_level'))), ('行動理由', safe_public_text(card.get('action_rationale'))), ('原因', reasons)])}</section>
          <section class="decision-section" data-section="premarket-plan"><h4>{'正式交易計畫' if active else '觀察與重新評估'}</h4>{_window_metric_grid([(entry_label, format_price_range(plan.get('entry') if active else plan.get('observation_zone'))), ('Stop 停損', f"{float(plan['stop']):.2f}" if active and isinstance(plan.get('stop'), (int, float)) else '不建立'), ('Target 目標', format_price_range(plan.get('target')) if active else '不建立'), ('失效條件', plan.get('invalidation_condition') if active else '不適用'), ('重新評估條件', plan.get('reassessment_condition'))])}</section>
          <section class="decision-section" data-section="premarket-research"><h4>SEC 與即時新聞</h4>{_window_metric_grid([('SEC', f"{sec.get('form') or '尚未取得'}｜{sec.get('filing_date') or '日期尚未取得'}｜{localize_enum(sec.get('materiality'))}"), ('即時新聞', news_text), ('新聞狀態', current_news.get('state_label')), ('新聞方向', '非方向性／未評估' if current_news.get('selected_count') else localize_enum(news.get('direction'))), ('策略影響', '研究脈絡；不自動建立交易行動')])}</section>
          {institutional_research}
        </article>
        """
    if window == "us_intraday_2300":
        data_status = str(card.get("data_status") or "unavailable")
        plan_status = str(card.get("plan_status") or "unavailable")
        active_plan = plan_status == "active"
        failure_note = ""
        continuity = card.get("us_intraday_research_continuity_v1") or {}
        if data_status in {"unavailable", "stale", "invalid", "market_closed"}:
            failure_note = f"<section class='status-card warn' data-section='intraday-data-status'><h4>{_escape(_intraday_state(data_status))}</h4><p>資料來源：{_escape(card.get('source'))}；行情時間：{_escape(card.get('market_data_as_of') or '尚未取得')}；缺少欄位：{_escape(', '.join(card.get('missing_fields') or []) or '無')}。本次不跨 window 補值。</p></section>"
        return f"""
        <article class="stock-card decision-card window-stock-card" data-market="US" data-card-type="window-intraday" data-report-type="{report_type}">
          <div class="decision-card__head"><div><div class="decision-card__market">US｜23:00 美股盤中｜20:00 計畫監控</div><h3>{symbol} {name}</h3></div><span class="decision-badge">{_escape(_intraday_state(card.get('tactical_adjustment')))}</span></div>
          {failure_note}
          <section class="decision-section us-continuity" data-section="us-intraday-continuity"><h4>20:00 研究判斷延續</h4>{_window_metric_grid([('延續狀態', continuity.get('continuity_state')), ('20:00 Snapshot', continuity.get('source_snapshot_id')), ('來源 Revision', continuity.get('source_revision')), ('Market', continuity.get('market_data_sufficiency')), ('Research', continuity.get('research_sufficiency')), ('News', continuity.get('news_sufficiency')), ('Lineage', continuity.get('lineage_sufficiency'))])}</section>
          <section class="decision-section" data-section="us-intraday-change"><h4>開盤後量價</h4>{_window_metric_grid([('目前價格', _intraday_number(card.get('current_price'))), ('美東行情時間', format_timestamp(card.get('market_data_as_of'), timezone_name='America/New_York')), ('Gap', _intraday_state(card.get('gap_state'))), ('開盤 Gap', _intraday_number(card.get('gap_open_pct'), '%')), ('目前 Gap', _intraday_number(card.get('gap_current_pct'), '%')), ('Gap 回補', _intraday_number(card.get('gap_fill_pct'), '%')), ('量能狀態', _intraday_state(card.get('volume_confirmation_state'))), ('成交量倍率', _intraday_number(card.get('volume_ratio'), 'x')), ('20:00 狀態', localize_enum(plan_status)), ('交易方向', localize_enum(card.get('direction'))), ('來源 Snapshot', safe_public_text((card.get('source_plan') or {}).get('source_snapshot_id')))])}</section>
          <section class="decision-section" data-section="us-proximity"><h4>{'進場／目標／停損監控' if active_plan else '觀察狀態'}</h4>{_window_metric_grid(([('進場區', f"{_intraday_number(card.get('entry_low'))}–{_intraday_number(card.get('entry_high'))}"), ('觸發狀態', _intraday_state(card.get('entry_trigger_state'))), ('停損距離', _us_proximity(card, 'stop')), ('目標距離', _us_proximity(card, 'target'))] if active_plan else [('正式交易計畫', '未建立'), ('觸發狀態', '不適用')]) + [('盤中調整', _intraday_state(card.get('tactical_adjustment'))), ('調整原因', safe_public_text(card.get('adjustment_reason'))), ('主要風險', safe_public_text(risk_text)), ('資料來源', safe_public_text(card.get('source'))), ('資料狀態', _intraday_state(data_status))])}</section>
          <section class="decision-section current-news-summary" data-section="current-news-summary"><h4>當期個股研究新聞</h4>{_window_metric_grid([('新聞狀態', current_news.get('state_label')), ('新聞摘要', news_text)])}</section>
          {institutional_research}
        </article>
        """
    card = normalize_review_card(card)
    outcome = str(card.get("trade_outcome") or "pending")
    review_outcome = str(card.get("trade_review_outcome") or "pending_evidence")
    prediction_result = str(card.get("prediction_range_result") or "pending")
    review = card.get("review") if isinstance(card.get("review"), dict) else {}
    source_plan = card.get("source_trade_plan") if isinstance(card.get("source_trade_plan"), dict) else {}
    source_sec = source_plan.get("sec_evidence") if isinstance(source_plan.get("sec_evidence"), dict) else {}
    news_display = news_text
    sec_display = "｜".join(str(value) for value in (source_sec.get("form"), source_sec.get("filing_date"), localize_enum(source_sec.get("item") or source_sec.get("materiality"))) if value) or "尚未取得"
    actual_available = all(review.get(key) is not None for key in ("actual_high", "actual_low", "actual_close"))
    return f"""
    <article class="stock-card decision-card window-stock-card" data-market="US" data-card-type="window-review" data-contract-card-type="us-post-close-review-v4" data-report-type="{report_type}">
      <div class="decision-card__head"><div><div class="decision-card__market">US｜06:30 美股檢討｜決策呈現 V3</div><h3>{symbol} {name}</h3></div><span class="decision-badge decision-badge--warn">{_escape(localize_enum(review_outcome))}</span></div>
      <section class="decision-section" data-section="us-prediction-review"><h4>預測評估／交易結果</h4>{_window_metric_grid([('預測區間結果', localize_enum(prediction_result)), ('交易結果', localize_enum(review_outcome)), ('預測區間', safe_public_text(prediction.get('today_range'))), ('實際最高／最低', f"{safe_public_text(review.get('actual_high'))} / {safe_public_text(review.get('actual_low'))}"), ('實際證據', '已取得' if actual_available else '尚未取得'), ('進場結果', localize_enum(review.get('entry_outcome'))), ('目標結果', localize_enum(review.get('target_outcome'))), ('停損結果', localize_enum(review.get('stop_outcome'))), ('來源 Snapshot', safe_public_text((card.get('source_trade_plan') or {}).get('source_snapshot_id')))])}</section>
      <section class="decision-section current-news-summary" data-section="us-review-next"><h4>最大有利／不利變動與下一交易日</h4>{_window_metric_grid([('最大有利變動', safe_public_text(review.get('mfe'), missing='待補證據')), ('最大不利變動', safe_public_text(review.get('mae'), missing='待補證據')), ('下一交易日', safe_public_text(review.get('next_session_action'), missing='補足行情時序證據後再判定。').replace('setup', '策略')), ('事件更新', localize_enum((source_plan.get('event_risk') or {}).get('canonical_level'))), ('即時新聞', news_display), ('新聞狀態', current_news.get('state_label')), ('SEC', sec_display), ('20:00 來源 Snapshot', safe_public_text(source_plan.get('source_snapshot_id'))), ('23:00 證據 Snapshot', safe_public_text((card.get('intraday_evidence') or {}).get('source_snapshot_id')))])}</section>
      {institutional_research}
    </article>
    """


def render_us_window_report(window: str, artifacts: list[dict[str, Any]]) -> str:
    contract = get_window_report_contract("US", window)
    cards = _us_cards_for_window(artifacts, window)
    artifact = next((item for item in artifacts if item.get("market") == "US" and str(item.get("window")) == window), None)
    report_type = {
        "us_pre_market_2000": "us-pre-market",
        "us_intraday_2300": "us-intraday-change",
        "us_post_close_review_0630": "us-post-close-review",
    }[window]
    intro = {
        "us_pre_market_2000": "方向、預測目標、預測區間、短評、新聞漏斗與今日行動；Entry / Stop / execution Target 為次要執行資訊。",
        "us_intraday_2300": "開盤後變化、Gap follow-through、Volume confirmation、Entry trigger 與 Target / Stop proximity。",
        "us_post_close_review_0630": "Prediction review、Entry / Stop / Target outcome、MFE / MAE 與 next-session watchlist。",
    }[window]
    if not cards:
        body = '<article class="status-card warn"><h3>本批次資料尚未取得</h3><p>不回退到其他 market/window 的 generic stock report。</p></article>'
    else:
        body = ''.join(_us_window_card(card, window) for card in cards)
    outcome_summary = ""
    if window == "us_pre_market_2000" and isinstance(artifact, dict):
        summary = artifact.get("premarket_summary") if isinstance(artifact.get("premarket_summary"), dict) else {}
        context = summary.get("market_context") if isinstance(summary.get("market_context"), dict) else {}
        spy, qqq, sector = context.get("spy") or {}, context.get("qqq") or {}, context.get("sector_proxy") or {}
        fmt = lambda value: f"{float(value):+.2f}%" if isinstance(value, (int, float)) else "尚未取得"
        groups = summary.get("groups") or {}
        outcome_summary = (
            '<section class="decision-section" data-section="canonical-premarket-summary"><h3>盤前市場環境與行動資格</h3>'
            + _window_metric_grid([
                ("SPY 盤前", fmt(spy.get("change_pct"))), ("QQQ 盤前", fmt(qqq.get("change_pct"))),
                ("類股代理 SOXX", fmt(sector.get("change_pct"))), ("市場方向", context.get("risk_direction") or "尚未取得"),
                ("主要交易機會", summary.get("top_opportunity_count", 0)), ("進場條件就緒", summary.get("entry_ready_count", 0)),
                ("觀察等待", summary.get("watch_only_count", 0)), ("暫不交易", summary.get("no_trade_count", 0)),
                ("主要機會名單", "、".join(groups.get("top_opportunity") or []) or "無"),
                ("資料時間", format_timestamp(context.get("timestamp"), timezone_name="America/New_York")),
            ]) + '</section>'
        )
    if window == "us_post_close_review_0630" and cards:
        cards = [normalize_review_card(card) for card in cards]
        summary = aggregate_us_post_close_review(cards)
        session = artifact.get("session_context", {}) if isinstance(artifact, dict) and isinstance(artifact.get("session_context"), dict) else {}
        outcome_summary = (
            '<section class="decision-section outcome-first-summary" data-section="canonical-review-summary"><h3>全日檢討結果</h3>'
            '<p>結果分類（Win / Loss / Not Triggered）以實際行情證據為準；Next-session watchlist 依逐卡交易結果與事件風險產生。</p>'
            + _window_metric_grid([
                ("檢討卡", summary["review_card_count"]), ("預測區間命中", summary["prediction_range_hit_count"]),
                ("預測區間未命中", summary["prediction_range_miss_count"]), ("交易結果已判定", summary["completed_trade_review_count"]),
                ("交易結果待補證據", summary["pending_trade_review_count"]), ("交易命中", summary["trade_hit_count"]),
                ("交易失敗", summary["trade_fail_count"]), ("交易未觸發", summary["trade_not_triggered_count"]),
                ("交易無交易", summary["trade_no_trade_count"]), ("美股交易日", session.get("session_date") or "尚未取得"),
                ("美東行情時間", format_timestamp(session.get("reference_new_york"), timezone_name="America/New_York")),
                ("台北報告時間", format_timestamp(artifact.get("generated_at") if isinstance(artifact, dict) else None)),
            ]) + '</section>'
        )
    return f"""
    <section class="section window-report-section" data-market="US" data-window="{_escape(window)}" data-report-type="{report_type}">
      <h2>{_escape(contract.title)}</h2>
      <p>{_escape(intro)}</p>
      {outcome_summary}
      {'' if window in {'us_post_close_review_0630', 'us_pre_market_2000'} else _decision_intelligence_v4_html("US", window, artifact)}
      <div class="grid decision-grid">{body}</div>
    </section>
    """

def base_css() -> str:
    return """
    body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8f9;color:#17262c;line-height:1.55}
    header,.hero{background:#0f2c33;color:white;padding:24px 18px}.wrap{max-width:1120px;margin:0 auto;padding:18px;padding-left:max(18px,env(safe-area-inset-left));padding-right:max(18px,env(safe-area-inset-right))}.nav{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.nav a,.btn{display:inline-block;background:#fff;color:#0f2c33;text-decoration:none;border-radius:8px;padding:10px 12px;font-weight:800;border:1px solid #cbd8dc}
    """ + SHARED_NAVIGATION_CSS + TW_TACTICAL_CSS + """
    .section{background:white;border:1px solid #dce5e8;border-radius:10px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.archive-market-group{margin-top:18px}.operations-table-scroll{max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}.operations-table{min-width:980px}.manual-batch-control-center{overflow-wrap:anywhere}.manual-batch-panel{border:1px solid #dce5e8;border-radius:10px;padding:16px;background:#fbfdfe}.manual-batch-buttons{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.manual-batch-button,#manual-batch-confirm{min-height:44px;border:1px solid #b9cbd1;border-radius:8px;background:#fff;color:#0f2c33;font-weight:800;padding:12px;text-align:left}.manual-batch-pin{display:grid;gap:8px;margin:12px 0;font-weight:800}.manual-batch-pin input{box-sizing:border-box;width:100%;max-width:280px;min-height:44px;border:1px solid #b9cbd1;border-radius:8px;padding:10px;font-size:16px}.stock-card,.status-card{background:#fff;border:1px solid #d9e4e7;border-radius:12px;padding:16px;overflow-wrap:anywhere;word-break:break-word}.card-kicker{font-weight:800;color:#35606b;font-size:13px}h1,h2,h3{margin:0 0 10px}dl{display:grid;gap:8px}dt{font-weight:800;color:#51666d}dd{margin:0}.badge{display:inline-block;border-radius:999px;padding:6px 10px;background:#e8f5e9;color:#225d28;font-weight:800}.warn{background:#fff9e8}.market-choice{display:block;text-decoration:none;color:#17262c}.market-choice h2{color:#0f5368}@media(max-width:640px){.wrap{padding:18px;padding-left:max(18px,env(safe-area-inset-left));padding-right:max(18px,env(safe-area-inset-right))}.grid{grid-template-columns:1fr;gap:16px}.nav a{width:100%;box-sizing:border-box}.manual-batch-buttons{grid-template-columns:1fr}.manual-batch-button,#manual-batch-confirm{width:100%;box-sizing:border-box}.manual-batch-pin input{max-width:100%}}
    """




def _contract_section_list(contract: Any, channel: str = "dashboard") -> str:
    sections = contract.dashboard_sections if channel == "dashboard" else contract.email_sections
    return "".join(f"<li>{_escape(item)}</li>" for item in sections)


def _manual_button(contract: Any) -> str:
    return (
        f'<button type="button" class="manual-batch-button" data-market="{_escape(contract.market)}" '
        f'data-window="{_escape(contract.window)}" data-label="{_escape(contract.short_label)}" '
        f'data-confirm="{_escape(contract.confirmation_label)}">{_escape(contract.manual_button_label)}</button>'
    )


def render_manual_control_center() -> str:
    contracts = all_window_report_contracts()
    tw = [c for c in contracts if c.market == "TW"]
    us = [c for c in contracts if c.market == "US"]
    return f"""
    <section class="section manual-batch-control-center" id="manual-batch-control-center">
      <h2>手動批次控制中心</h2>
      <p class="decision-note">手動批次只刷新指定市場 artifacts / Dashboard。不會發送 LINE / Email，不會執行交易。</p>
      <div class="grid manual-batch-grid">
        <section class="manual-batch-panel" data-market="TW"><h3>台股手動批次</h3><p>台股批次只刷新台股 Dashboard / artifacts。不會發送 LINE / Email，不會執行交易。</p><div class="manual-batch-buttons">{''.join(_manual_button(c) for c in tw)}</div></section>
        <section class="manual-batch-panel" data-market="US"><h3>美股手動批次</h3><p>美股批次只刷新美股 Dashboard / artifacts。不會發送 LINE / Email，不會執行交易。</p><div class="manual-batch-buttons">{''.join(_manual_button(c) for c in us)}</div></section>
      </div>
      <form id="manual-batch-form" data-endpoint="/stock-ai-dashboard/api/manual-rerun" data-status-endpoint="/stock-ai-dashboard/api/manual-rerun/status">
        <p id="manual-batch-market">已選擇市場：尚未選擇</p>
        <p id="manual-batch-window">已選擇批次：尚未選擇</p>
        <label class="manual-batch-pin">6 位數字重跑密碼 <input id="manual-batch-pin" name="pin" inputmode="numeric" autocomplete="off" pattern="[0-9]{{6}}" minlength="6" maxlength="6" placeholder="請輸入 6 位數字"></label>
        <input type="hidden" id="manual-batch-selected-window" name="window" value="">
        <button type="submit" id="manual-batch-confirm" disabled>請先選擇批次</button>
      </form>
      <section class="manual-rerun-status-card" aria-live="polite">
        <h3>最近一次手動批次</h3>
        <div class="grid">
          <div><strong>狀態</strong><p id="manual-status-state">尚未執行</p></div>
          <div><strong>目前階段</strong><p id="manual-status-stage">資料待接</p></div>
          <div><strong>任務 ID</strong><p id="manual-status-task">資料待接</p></div>
          <div><strong>批次</strong><p id="manual-status-window">資料待接</p></div>
          <div><strong>開始／完成</strong><p id="manual-status-time">資料待接</p></div>
          <div><strong>耗時</strong><p id="manual-status-duration">資料待接</p></div>
          <div><strong>有效交易日／Revision</strong><p id="manual-status-revision">資料待接</p></div>
          <div><strong>更新結果</strong><p id="manual-status-routes">資料待接</p></div>
          <div><strong>未變更項目</strong><p id="manual-status-stable">Previous、其他 windows 維持不變</p></div>
          <div><strong>安全狀態</strong><p id="manual-status-safety">LINE：未發送｜Email：未發送｜交易：未執行</p></div>
        </div>
        <p id="manual-status-message" class="decision-note">選擇批次並送出後，這裡會顯示排隊、執行、發布與完成結果。</p>
        <p><a id="manual-status-latest-link" class="market-shared-navigation__button" href="#" hidden>查看最新報告</a><a id="manual-status-market-link" class="market-shared-navigation__button" href="#" hidden>查看市場 Dashboard</a></p>
        <button type="button" id="manual-status-refresh">重新查詢最近任務</button>
      </section>
      <p class="decision-note">TW / US 共用 PIN guard 與 one-batch lock。狀態查詢最多 30 分鐘，完成、失敗或拒絕後會停止輪詢。</p>
    </section>
    <script>
      (() => {{
        const storageKey = 'stock-ai-manual-rerun-latest-task-v1';
        const terminal = new Set(['completed','failed','rejected','invalid_pin_format','unauthorized','manual_rerun_disabled','lock_busy','cooldown_active']);
        const stateLabels = {{idle:'尚未執行',submitted:'已送出',queued:'等待執行',running:'執行中',publishing:'同步 Dashboard',completed:'已完成',failed:'執行失敗',rejected:'已拒絕',invalid_pin_format:'PIN 格式錯誤',unauthorized:'PIN 錯誤',manual_rerun_disabled:'尚未啟用',lock_busy:'已有批次執行中',cooldown_active:'冷卻中'}};
        const buttons = document.querySelectorAll('.manual-batch-button');
        const selected = document.getElementById('manual-batch-selected-window');
        const market = document.getElementById('manual-batch-market');
        const batch = document.getElementById('manual-batch-window');
        const confirm = document.getElementById('manual-batch-confirm');
        const form = document.getElementById('manual-batch-form');
        let pollTimer = null;
        let pollStartedAt = 0;
        let currentTaskId = localStorage.getItem(storageKey) || '';
        const setText = (id, value) => {{ const node = document.getElementById(id); if (node) node.textContent = value || '資料待接'; }};
        const stopPolling = () => {{ if (pollTimer) window.clearInterval(pollTimer); pollTimer = null; }};
        const renderStatus = (data) => {{
          const state = String(data.status || 'idle');
          const taskId = data.task_id || data.job_id || '';
          if (taskId) {{ currentTaskId = taskId; localStorage.setItem(storageKey, taskId); }}
          setText('manual-status-state', stateLabels[state] || state);
          setText('manual-status-stage', data.stage_label || data.stage || '資料待接');
          setText('manual-status-task', taskId || '資料待接');
          setText('manual-status-window', `${{data.market || ''}} ${{data.window || data.requested_window || ''}}`.trim());
          setText('manual-status-time', `${{data.started_at || '尚未開始'}} → ${{data.finished_at || '尚未完成'}}`);
          setText('manual-status-duration', Number.isFinite(data.duration_seconds) ? `${{data.duration_seconds}} 秒` : '資料待接');
          setText('manual-status-revision', `${{data.effective_trading_date || '資料待接'}}｜${{data.revision ? `Revision ${{data.revision}}` : 'Revision 待接'}}`);
          setText('manual-status-routes', `Latest：${{data.latest_route_updated ? '已更新' : '未更新'}}｜Market Dashboard：${{data.market_dashboard_updated ? '已同步' : '未同步'}}`);
          setText('manual-status-stable', `Previous：${{data.previous_route_updated ? '已更新' : '未更新'}}｜其他 windows：${{data.other_windows_updated ? '已更新' : '未更新'}}`);
          setText('manual-status-safety', `LINE：${{data.line_attempted ? '已嘗試' : '未發送'}}｜Email：${{data.email_attempted ? '已嘗試' : '未發送'}}｜交易：${{data.trading_or_order_executed ? '已執行' : '未執行'}}`);
          setText('manual-status-message', data.message || data.error_summary || (state === 'completed' ? '手動重跑已完成。' : '狀態已更新。'));
          const latest = document.getElementById('manual-status-latest-link');
          const marketLink = document.getElementById('manual-status-market-link');
          if (data.latest_url) {{ latest.href = data.latest_url; latest.hidden = false; }}
          if (data.market_dashboard_url) {{ marketLink.href = data.market_dashboard_url; marketLink.hidden = false; }}
          if (terminal.has(state)) stopPolling();
          return state;
        }};
        const fetchStatus = async () => {{
          if (pollStartedAt && Date.now() - pollStartedAt > 30 * 60 * 1000) {{ stopPolling(); setText('manual-status-message', '狀態查詢逾時，可按「重新查詢最近任務」繼續。'); return; }}
          const suffix = currentTaskId ? `?job_id=${{encodeURIComponent(currentTaskId)}}` : '';
          try {{
            const response = await fetch(form.dataset.statusEndpoint + suffix, {{headers:{{'Accept':'application/json'}},cache:'no-store'}});
            renderStatus(await response.json());
          }} catch (_error) {{ stopPolling(); setText('manual-status-message', '狀態 endpoint 暫時無法連線，可稍後重新查詢。'); }}
        }};
        const startPolling = () => {{ stopPolling(); pollStartedAt = Date.now(); pollTimer = window.setInterval(fetchStatus, 4000); fetchStatus(); }};
        buttons.forEach((button) => button.addEventListener('click', () => {{
          if (!button.dataset.window) return;
          const label = button.dataset.label || button.dataset.window;
          const name = button.dataset.market === 'US' ? '美股' : '台股';
          selected.value = button.dataset.window || '';
          market.textContent = `已選擇市場：${{name}}`;
          batch.textContent = `已選擇批次：${{label}}`;
          confirm.disabled = false;
          confirm.textContent = button.dataset.confirm || `確認執行${{name}} ${{label}}重跑`;
        }}));
        form.addEventListener('submit', async (event) => {{
          event.preventDefault();
          const pin = document.getElementById('manual-batch-pin').value || '';
          if (!/^[0-9]{{6}}$/.test(pin) || !selected.value) {{ return; }}
          confirm.disabled = true;
          renderStatus({{status:'submitted',window:selected.value,message:'已送出手動批次請求。'}});
          try {{
            const response = await fetch(form.dataset.endpoint, {{method:'POST',headers:{{'Content-Type':'application/json','Accept':'application/json'}},body:JSON.stringify({{window:selected.value,mode:'dashboard_refresh_only',pin,confirm_single_window_only:true,reason:'manual dashboard rerun'}})}});
            document.getElementById('manual-batch-pin').value = '';
            const data = await response.json();
            renderStatus(data);
            if (data.accepted && !terminal.has(String(data.status))) startPolling();
          }} catch (_error) {{ renderStatus({{status:'failed',window:selected.value,error_summary:'手動重跑 endpoint 暫時無法連線；未重複送出。'}}); }}
          finally {{ confirm.disabled = false; }}
        }});
        document.getElementById('manual-status-refresh').addEventListener('click', () => {{ pollStartedAt = Date.now(); fetchStatus(); }});
        if (currentTaskId) startPolling(); else fetchStatus();
      }})();
    </script>
    """


def strip_embedded_manual_controls(body: str) -> str:
    return re.sub(r'<section class="panel manual-rerun-control">.*?</script>', '<section class="section"><h2>手動批次控制</h2><p><a href="/stock-ai-dashboard/index.html#manual-batch-control-center">手動批次控制請回到總覽頁</a></p></section>', body, flags=re.S)


def render_window_contract_overview(market: str) -> str:
    cards = []
    for contract in all_window_report_contracts():
        if contract.market != market:
            continue
        cards.append(
            f'<article class="status-card window-contract-card" data-market="{_escape(contract.market)}" data-window="{_escape(contract.window)}">'
            f'<h3>{_escape(contract.title)}</h3><p>{_escape(contract.primary_question)}</p>'
            f'<p class="decision-note">{_escape("、".join(contract.dashboard_sections[:3]))}</p>'
            '</article>'
        )
    return '<section class="section"><h2>各批次報告內容</h2><div class="grid">' + ''.join(cards) + '</div></section>'


def _tw_card_base(card: dict[str, Any]) -> tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
    tactical = strategies.get("daily_tactical", {}) if isinstance(strategies.get("daily_tactical"), dict) else {}
    review = card.get("review_snapshot", {}) if isinstance(card.get("review_snapshot"), dict) else {}
    presentation = decision_presentation_v2("TW", card)
    stock_id = _escape(card.get("stock_id"))
    stock_name = _escape(card.get("stock_name"))
    return stock_id, stock_name, tactical, review, presentation


def _window_metric_grid(rows: list[tuple[str, Any]]) -> str:
    return '<div class="decision-plan">' + ''.join(_metric(label, value) for label, value in rows) + '</div>'


def _tw_prediction_html(card: dict[str, Any], window: str) -> str:
    projected = project_tw_prediction_card(card, window, strict=False)
    prediction = projected["prediction_presentation_v1"]
    levels = prediction["key_levels"]
    scenario = prediction["scenario_switch"]
    progress = prediction["intraday_prediction_status"]
    today = prediction["today_range"]
    confidence = prediction["confidence"]
    direction_label = {
        "bullish": "偏多", "bearish": "偏空", "neutral": "中性",
        "range_bound": "區間", "insufficient_evidence": "證據不足",
    }.get(prediction["direction"], prediction["direction"])
    range_text = (
        f"{safe_public_text(today.get('predicted_low'), missing='尚未建立')}–"
        f"{safe_public_text(today.get('predicted_high'), missing='尚未建立')}"
    )
    confidence_text = "證據不足" if confidence["score"] is None else f"{confidence['score']:.0f}%｜{confidence['band']}"
    research = prediction["research_view"]
    tactical = prediction["daily_tactical"]
    return f"""
      <section class="decision-section tw-prediction-intelligence" data-section="prediction-intelligence" data-prediction-id="{_escape(prediction['prediction_id'])}" data-progress-status="{_escape(progress['status'])}">
        <h4>今日短線預期</h4>
        {_window_metric_grid([
            ('方向 / 路徑', f"{direction_label}｜{prediction['expected_path']}"),
            ('預測區間', range_text), ('信心', confidence_text),
            ('支撐 / 壓力', f"{safe_public_text(levels.get('support_1'), missing='尚未建立')} / {safe_public_text(levels.get('resistance_1'), missing='尚未建立')}"),
            ('轉強條件', scenario.get('bullish_trigger')), ('轉弱 / 失效', scenario.get('bearish_trigger')),
            ('目前進度', f"{progress['status']}｜現價 {safe_public_text(progress.get('current_price'), missing='盤前尚無即時價')}"),
            ('與上一時段相比', prediction.get('change_from_previous_window')),
        ])}
        <p class="decision-note">Research view（中長期）：{_escape(research.get('stance'))}｜Daily Tactical（今日）：{_escape(tactical.get('direction'))}｜正式交易計畫：{'是' if tactical.get('formal_trade_plan') else '否；研究型短線預期仍保留'}</p>
      </section>
    """


def _tw_preopen_product_html(card: dict[str, Any]) -> str:
    product = card.get("tw_preopen_product_intelligence_v1") if isinstance(card.get("tw_preopen_product_intelligence_v1"), dict) else {}
    if not product:
        return _tw_prediction_html(card, "pre_open_0700")
    funnel = product.get("news_funnel") if isinstance(product.get("news_funnel"), dict) else {}
    news_rows = []
    for item in (product.get("important_news") or [])[:3]:
        time_text = format_timestamp(item.get("published_at"), timezone_name="Asia/Taipei") if item.get("published_at") else "時間未標示"
        news_rows.append(
            f'<li style="margin:0 0 .85rem;color:#0f172a"><strong style="color:#020617">{_escape(item.get("headline"))}</strong>'
            f'<div style="color:#334155;line-height:1.55">{_escape(item.get("summary"))}</div>'
            f'<small style="color:#334155">來源：{_escape(item.get("publisher"))}｜{_escape(time_text)}｜影響：{_escape(item.get("expected_impact"))}</small></li>'
        )
    news_html = (
        f'<ul class="preopen-important-news" style="margin:.75rem 0 0;padding-left:1.25rem">{"".join(news_rows)}</ul>'
        if news_rows
        else f'<p class="decision-note" style="color:#334155">{_escape(product.get("news_message"))}</p>'
    )
    reasons = funnel.get("public_rejection_reasons") if isinstance(funnel.get("public_rejection_reasons"), dict) else {}
    reason_text = "｜".join(f"{label} {count}" for label, count in reasons.items()) or "無"
    rejection_html = (
        f'<p class="decision-note" style="color:#475569">其他未採用：{int(funnel.get("not_selected_count") or 0)} 則<br>主要原因：{_escape(reason_text)}</p>'
        if int(funnel.get("not_selected_count") or 0) else ""
    )
    direction = f'{product.get("direction_label")} {product.get("direction_arrow")}'
    direction_color = {
        "BULLISH": "#166534", "BEARISH": "#b91c1c", "SIDEWAYS": "#334155",
    }.get(str(product.get("today_direction")), "#334155")
    return f"""
      <section class="decision-section tw-preopen-product-intelligence"
        data-section="tw-preopen-product-intelligence"
        data-projection-id="{_escape(product.get('projection_id'))}"
        data-today-direction="{_escape(product.get('today_direction'))}"
        data-primary-background="#f8fafc"
        data-primary-foreground="#0f172a"
        style="border:1px solid #94a3b8;border-radius:14px;padding:1rem;background:linear-gradient(135deg,#f8fafc,#eef2ff);color:#0f172a">
        <div class="preopen-product-core" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.75rem;margin-bottom:1rem">
          <div><small style="color:#475569">今日方向</small><div style="font-size:1.65rem;font-weight:800;color:{direction_color}">{_escape(direction)}</div></div>
          <div><small style="color:#475569">目標價</small><div style="font-size:1.65rem;font-weight:800;color:#020617">{_escape(format_optional_price(product.get('target_price')))}</div></div>
          <div><small style="color:#475569">預測區間</small><div style="font-size:1.3rem;font-weight:750;color:#020617">{_escape(format_optional_price(product.get('predicted_low')))} ～ {_escape(format_optional_price(product.get('predicted_high')))}</div></div>
          <div><small style="color:#475569">目前／基準價</small><div style="font-size:1.3rem;font-weight:750;color:#020617">{_escape(format_optional_price(product.get('reference_price')))}</div></div>
        </div>
        <h4 style="color:#0f172a">今日判斷</h4>
        <p style="font-size:1.05rem;line-height:1.65;color:#1e293b">{_escape(product.get('daily_thesis'))}</p>
        <h4 style="color:#0f172a">今日重要消息</h4>
        <div class="preopen-news-funnel" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.5rem;margin:.5rem 0 .75rem">
          <div style="background:#e2e8f0;border-radius:8px;padding:.55rem;color:#0f172a"><small style="color:#475569">新聞抓取</small><strong style="display:block">{int(funnel.get('retrieved_count') or 0)} 則</strong></div>
          <div style="background:#e2e8f0;border-radius:8px;padding:.55rem;color:#0f172a"><small style="color:#475569">通過篩選</small><strong style="display:block">{int(funnel.get('qualified_count') or 0)} 則</strong></div>
          <div style="background:#e2e8f0;border-radius:8px;padding:.55rem;color:#0f172a"><small style="color:#475569">可用於今日判斷</small><strong style="display:block">{int(funnel.get('selected_count') or 0)} 則</strong></div>
        </div>
        {news_html}
        {rejection_html}
        <p class="decision-note" style="color:#475569">今日行動：{_escape((product.get('decision') or {}).get('action') or "待確認")}。預測目標不等於交易停利或委託價格。</p>
      </section>
    """

def _tw_rre_production_html(tw_v2: dict[str, Any]) -> str:
    research = tw_v2.get("research_reasoning_projection") if isinstance(tw_v2.get("research_reasoning_projection"), dict) else {}
    if not research:
        return ""
    brief = research.get("morning_or_window_brief") or {}
    note_html = []
    for note in research.get("research_notes") or []:
        hypothesis = note.get("hypothesis") or {}
        prediction = note.get("prediction_snapshot_v2") if isinstance(note.get("prediction_snapshot_v2"), dict) else {}
        forecast_range = prediction.get("range_forecast") if isinstance(prediction.get("range_forecast"), dict) else {}
        direction_label = {"bullish": "偏多", "neutral": "中性", "bearish": "偏空"}.get(
            str(prediction.get("direction_forecast")), str(prediction.get("direction_forecast") or "資料不足")
        )
        prediction_text = (
            f"{direction_label}｜"
            f"{forecast_range.get('low')}–{forecast_range.get('high')}｜"
            f"信心 {prediction.get('confidence')}%"
            if prediction.get("prediction_status") == "evaluable" else
            f"無法建立可評估預測｜{prediction.get('reason_code') or '行情證據不足'}"
        )
        supporting = "；".join(note.get("supporting") or []) or "目前沒有足以支持方向的證據"
        opposing = "；".join(note.get("opposing") or []) or "目前沒有已確認的反向證據"
        contextual = "；".join(note.get("contextual_evidence") or []) or "本批次沒有額外市場脈絡"
        missing_values = "、".join(note.get("missing") or []) or "無"
        news_diag = ((note.get("research_evidence_observability") or {}).get("news") or {})
        news_stages = news_diag.get("stages") or {}
        news_state = {
            "NO_RELEVANT_NEWS_DISCOVERED": "未發現相關新聞",
            "NEWS_DISCOVERED_BUT_FILTERED": "已發現新聞，但未通過品質／重大性門檻",
            "NEWS_ADMITTED_NOT_SELECTED": "已納入研究證據，但本次推理未選用",
            "NEWS_SELECTED_AND_RENDERED": "已納入推理並呈現",
        }.get(news_diag.get("absence_state"), news_diag.get("absence_state") or "新聞狀態未評估")
        context = "、".join(note.get("company_context") or []) or "長期公司脈絡尚未建檔"
        note_html.append(f"""
          <details class="decision-details research-note" data-symbol="{_escape(note.get('symbol'))}" data-generated-by="research_reasoning_engine_v1">
            <summary>{_escape(note.get('research_summary'))}</summary>
            <div class="decision-details__body">
              {_window_metric_grid([
             …50939 tokens truncated…else "not_applicable",
        "missed_opportunity_candidate": missed_opportunity,
        "trigger_too_strict_candidate": missed_opportunity,
        "evidence_quality_insufficient": bool(base.get("missing_evidence")),
        "auto_threshold_change": False, "auto_learning": False,
    }
    carry = {
        "unresolved_hypothesis": hypothesis_state not in {"invalidated", "confirmed"},
        "invalidated_hypothesis": hypothesis_state == "invalidated",
        "major_forecast_miss": range_hit == "miss",
        "contradictory_intraday_evidence": hypothesis_state in {"contradicted", "invalidated"},
        "missing_critical_sources": list(base.get("missing_evidence") or []),
        "carryforward_reason": "保留未解假設、重大預測誤差、盤中矛盾與關鍵來源缺口供下一個 20:00 研究。",
    }
    base.update({
        "window": "us_post_close_review_0630", "observed_at": observed_at,
        "prediction_evaluation": evaluation, "no_trade_learning": learning,
        "next_session_carryforward": carry,
        "window_update": {"state": "reviewed", "hypothesis_state": hypothesis_state, "range_result": range_hit, "trade_outcome": trade_outcome, "decision_layer_action_changed": False},
    })
    base["window_research_identity"] = "us_rv2_" + stable_hash({k: v for k, v in base.items() if k != "window_research_identity"})[:24]
    return base


def attach_initial(bundle: dict[str, Any], observed_at: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(bundle))
    updated["research_intelligence_v2"] = build_initial_projection(updated, observed_at=observed_at)
    updated["canonical_research_schema_version"] = SCHEMA_VERSION
    return updated


def validate_projection(projection: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("research_brief", "research_confidence", "supporting_evidence", "opposing_evidence", "missing_evidence", "hypothesis", "effective_coverage", "window_research_identity"):
        if projection.get(key) is None:
            errors.append(f"missing:{key}")
    hypothesis = projection.get("hypothesis") or {}
    if hypothesis.get("state") not in HYPOTHESIS_STATES:
        errors.append("invalid_hypothesis_state")
    if not hypothesis.get("trigger") or not hypothesis.get("invalidation") or not hypothesis.get("counter_argument"):
        errors.append("hypothesis_incomplete")
    boundary = projection.get("boundary") or {}
    if projection.get("decision_context_export", {}).get("trade_action") is not None:
        errors.append("research_exported_trade_action")
    if any(boundary.get(key) for key in ("eligibility_modified", "ranking_modified", "scoring_modified", "strategy_weights_modified", "prediction_model_modified", "auto_learning")):
        errors.append("layer_boundary_violation")
    return sorted(set(errors))
