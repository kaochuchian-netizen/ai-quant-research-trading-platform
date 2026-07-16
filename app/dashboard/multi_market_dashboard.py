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
from app.reports.tw_1335_snapshot_delivery import context_for_snapshot as tw_1335_context_for_snapshot, render_dashboard as render_tw_1335_dashboard

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


def _us_window_card(card: dict[str, Any], window: str) -> str:
    symbol = _escape(card.get("symbol"))
    name = _escape(card.get("name"))
    presentation = decision_presentation_v2("US", card)
    tactical = presentation.get("daily_tactical", {})
    prediction = presentation.get("prediction", {})
    reason_text = _joined_text(presentation.get("reasons"), "等待量價與資料確認")
    risk_text = _joined_text(presentation.get("risks"), "未偵測到額外風險")
    news_text = _research_v3_text(presentation, "material_news")
    sec_text = _research_v3_text(presentation, "sec")
    review_text = _research_v3_text(presentation, "review")
    report_type = {
        "us_pre_market_2000": "us-pre-market",
        "us_intraday_2300": "us-intraday-change",
        "us_post_close_review_0630": "us-post-close-review",
    }[window]
    if window == "us_pre_market_2000":
        return f"""
        <article class="stock-card decision-card window-stock-card" data-market="US" data-card-type="window-premarket" data-report-type="{report_type}">
          <div class="decision-card__head"><div><div class="decision-card__market">US｜20:00 美股盤前｜決策呈現 V3</div><h3>{symbol} {name}</h3></div><span class="decision-badge">{_escape(tactical.get('action'))}</span></div>
          <section class="decision-section" data-section="premarket-setup"><h4>Premarket / Gap / Setup</h4>{_window_metric_grid([('方向', tactical.get('direction')), ('Setup', tactical.get('setup')), ('Entry', tactical.get('entry_zone')), ('Stop', tactical.get('stop')), ('Target', tactical.get('target_1')), ('Reward/Risk', tactical.get('reward_risk'))])}</section>
          <section class="decision-section" data-section="premarket-risk"><h4>財報 / SEC / 新聞風險</h4>{_window_metric_grid([('事件風險', tactical.get('risk')), ('預測區間', prediction.get('today_range')), ('信心', tactical.get('confidence')), ('主要依據', reason_text), ('主要風險', risk_text), ('News', news_text), ('SEC', sec_text), ('Review', review_text)])}</section>
        </article>
        """
    if window == "us_intraday_2300":
        return f"""
        <article class="stock-card decision-card window-stock-card" data-market="US" data-card-type="window-intraday" data-report-type="{report_type}">
          <div class="decision-card__head"><div><div class="decision-card__market">US｜23:00 美股盤中｜決策呈現 V3</div><h3>{symbol} {name}</h3></div><span class="decision-badge">{_escape(tactical.get('action'))}</span></div>
          <section class="decision-section" data-section="us-intraday-change"><h4>開盤後變化</h4>{_window_metric_grid([('Gap follow-through', '待盤中量價確認'), ('Volume confirmation', '待盤中量價確認'), ('Entry trigger', tactical.get('entry_zone')), ('Tactical adjustment', tactical.get('action')), ('Reward/Risk', tactical.get('reward_risk'))])}</section>
          <section class="decision-section" data-section="us-proximity"><h4>Target / Stop proximity</h4>{_window_metric_grid([('Target proximity', tactical.get('target_1')), ('Stop proximity', tactical.get('stop')), ('主要依據', reason_text), ('主要風險', risk_text), ('News', news_text), ('SEC', sec_text), ('Review', review_text), ('現在是否仍可操作', tactical.get('action'))])}</section>
        </article>
        """
    return f"""
    <article class="stock-card decision-card window-stock-card" data-market="US" data-card-type="window-review" data-report-type="{report_type}">
      <div class="decision-card__head"><div><div class="decision-card__market">US｜06:30 美股檢討｜決策呈現 V3</div><h3>{symbol} {name}</h3></div><span class="decision-badge decision-badge--warn">Review</span></div>
      <section class="decision-section" data-section="us-prediction-review"><h4>Prediction review</h4>{_window_metric_grid([('Prediction range', prediction.get('today_range')), ('Win / Loss / Not Triggered', '本次檢討尚待實際結果'), ('Entry outcome', '本次檢討尚待實際結果'), ('Target outcome', tactical.get('target_1')), ('Stop outcome', tactical.get('stop')), ('Reward/Risk', tactical.get('reward_risk'))])}</section>
      <section class="decision-section" data-section="us-review-next"><h4>MFE / MAE / Next session</h4>{_window_metric_grid([('MFE', '本次檢討尚待實際結果'), ('MAE', '本次檢討尚待實際結果'), ('Overnight event update', risk_text), ('Next-session watchlist', reason_text), ('News', news_text), ('SEC', sec_text), ('Review', review_text)])}</section>
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
        "us_pre_market_2000": "Premarket、Gap、SPY / QQQ / 類股脈絡與 Entry / Stop / Target。",
        "us_intraday_2300": "開盤後變化、Gap follow-through、Volume confirmation、Entry trigger 與 Target / Stop proximity。",
        "us_post_close_review_0630": "Prediction review、Entry / Stop / Target outcome、MFE / MAE 與 next-session watchlist。",
    }[window]
    if not cards:
        body = '<article class="status-card warn"><h3>資料待接</h3><p>本批次資料尚未產生，不回退到完整 generic stock report。</p></article>'
    else:
        body = ''.join(_us_window_card(card, window) for card in cards)
    return f"""
    <section class="section window-report-section" data-market="US" data-window="{_escape(window)}" data-report-type="{report_type}">
      <h2>{_escape(contract.title)}</h2>
      <p>{_escape(intro)}</p>
      {_decision_intelligence_v4_html("US", window, artifact)}
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


def _decision_intelligence_v4_html(market: str, window: str, payload: dict[str, Any] | None) -> str:
    projection = project_decision_intelligence_v4(market, window, payload)
    counts = projection["counts"]
    labels = {
        "total": "標的數", "top_opportunities": "Top opportunities", "no_trade": "No-trade",
        "chase_risk": "Chase risk", "entry_ready": "Entry readiness", "triggered": "Triggered",
        "invalidated": "Invalidated", "still_actionable": "Still actionable", "volume_confirmed": "Volume confirmed",
        "failed_gaps": "Failed gaps", "direction_hit": "Direction hit", "reviewed": "Reviewed",
    }
    count_fields = {
        "pre_open_0700": ("total", "top_opportunities", "no_trade", "chase_risk", "entry_ready"),
        "intraday_1305": ("total", "triggered", "invalidated", "still_actionable", "volume_confirmed"),
        "pre_close_1335": ("total", "still_actionable", "no_trade", "chase_risk"),
        "post_close_1500": ("total", "reviewed", "direction_hit"),
        "us_pre_market_2000": ("total", "top_opportunities", "chase_risk", "entry_ready"),
        "us_intraday_2300": ("total", "triggered", "failed_gaps", "volume_confirmed", "still_actionable", "chase_risk"),
        "us_post_close_review_0630": ("total", "reviewed", "direction_hit"),
    }[window]
    metric_rows = [(labels[key], counts[key]) for key in count_fields]
    lists = projection["lists"]
    list_rows = []
    for key, label in (("opportunities", "Top opportunities"), ("triggered", "已觸發"), ("invalidated", "已失效"), ("volume_confirmed", "量價確認"), ("failed_gaps", "Failed gaps"), ("event_risk", "事件風險"), ("still_actionable", "仍可行動"), ("no_trade", "No-trade"), ("chase_risk", "Chase-risk")):
        values = lists.get(key, [])
        if values:
            list_rows.append((label, "、".join(str(item) for item in values[:5])))
    if not list_rows:
        list_rows.append(("資料狀態", "目前 payload 沒有可安全分類的明細；不跨 window 補值。"))
    distribution_rows = []
    if window in {"post_close_1500", "us_post_close_review_0630"}:
        outcome_labels = {"win": "成功", "loss": "失敗", "not_triggered": "未觸發", "no_trade": "無交易", "pending": "待檢討"}
        distribution_rows.extend((outcome_labels.get(key, "其他"), value) for key, value in projection["outcome_distribution"].items())
    else:
        confidence_labels = {"high": "高信心", "medium": "中信心", "low": "低信心", "unknown": "信心資料待接"}
        distribution_rows.extend((confidence_labels.get(key, "其他"), value) for key, value in projection["confidence_distribution"].items())
    distribution_html = _window_metric_grid(distribution_rows) if distribution_rows else '<p class="decision-note">尚無可安全彙整的分布。</p>'
    return f"""
    <section class="decision-section decision-intelligence-v4" data-presentation-version="seven-window-decision-intelligence-v4" data-card-type="{_escape(projection['expected_card_type'])}">
      <h3>Decision Intelligence V4</h3>
      <p>{_escape(projection['question'])}</p>
      {_window_metric_grid(metric_rows)}
      <section class="decision-section"><h4>本批次決策清單</h4>{_window_metric_grid(list_rows)}</section>
      <section class="decision-section"><h4>{'Outcome distribution' if window in {'post_close_1500', 'us_post_close_review_0630'} else 'Confidence distribution'}</h4>{distribution_html}</section>
      <details class="decision-details"><summary>內容範圍與資料來源</summary><div class="decision-details__body"><p>{_escape('、'.join(projection['section_inventory']))}</p><p class="decision-note">來源：指定 market/window payload 的 tactical 與 review 欄位；不跨市場、不跨時段、不補造資料。</p></div></details>
    </section>
    """


def _first_text(items: Any, fallback: str) -> str:
    if isinstance(items, list):
        for item in items:
            text = clean_text(item, missing="")
            if text:
                return text
    return fallback


def _first_reason(presentation: dict[str, Any]) -> str:
    return _first_text(presentation.get("reasons"), "等待量價與資料確認")


def _first_risk(presentation: dict[str, Any]) -> str:
    return _first_text(presentation.get("risks"), "未偵測到額外風險")


def _joined_text(items: Any, fallback: str) -> str:
    if isinstance(items, list):
        values = [clean_text(item, missing="") for item in items]
        values = [value for value in values if value]
        if values:
            return "；".join(values)
    return fallback


def _research_v3_text(presentation: dict[str, Any], key: str, fallback: str = "資料待接") -> str:
    research_v3 = presentation.get("research_v3", {}) if isinstance(presentation.get("research_v3"), dict) else {}
    research = presentation.get("research", {}) if isinstance(presentation.get("research"), dict) else {}
    return clean_text(research_v3.get(key) or research.get(key), missing=fallback)


def _tw_intraday_card(card: dict[str, Any]) -> str:
    stock_id, stock_name, tactical, _review, presentation = _tw_card_base(card)
    values = _tactical_values(tactical)
    no_trade = is_no_trade(tactical)
    return f"""
    <article class="stock-card decision-card window-stock-card" data-market="TW" data-card-type="window-intraday" data-report-type="intraday-change">
      <div class="decision-card__head"><div><div class="decision-card__market">TW｜13:05 盤中變化</div><h3>{stock_id} {stock_name}</h3></div><span class="decision-badge {'decision-badge--warn' if no_trade else 'decision-badge--ok'}">{_escape(presentation['daily_tactical']['action'])}</span></div>
      <section class="decision-section" data-section="intraday-status"><h4>盤中變化</h4>{_window_metric_grid([('方向', presentation['daily_tactical'].get('direction')), ('Setup 是否觸發', '等待確認' if no_trade else '可觀察'), ('進場是否觸發', '否' if no_trade else '接近條件'), ('現在是否仍可操作', '避免追價' if no_trade else '等待量價確認')])}</section>
      <section class="decision-section" data-section="intraday-proximity"><h4>目標 / 停損接近度</h4>{_window_metric_grid([('接近目標', format_price_zone(values.get('target1'))), ('接近停損', format_stop(values.get('stop')),), ('量價確認', _first_reason(presentation)), ('盤中風險變化', _first_risk(presentation))])}</section>
    </article>
    """


def _tw_pre_close_card(card: dict[str, Any]) -> str:
    stock_id, stock_name, tactical, _review, presentation = _tw_card_base(card)
    values = _tactical_values(tactical)
    no_trade = is_no_trade(tactical)
    action = "避免追價，等待明日" if no_trade else "接近條件才處理"
    return f"""
    <article class="stock-card decision-card window-stock-card" data-market="TW" data-card-type="window-snapshot" data-report-type="pre-close-snapshot">
      <div class="decision-card__head"><div><div class="decision-card__market">TW｜13:35 收盤快照</div><h3>{stock_id} {stock_name}</h3></div><span class="decision-badge decision-badge--warn">{_escape(action)}</span></div>
      <section class="decision-section" data-section="pre-close-summary"><h4>收盤前摘要</h4>{_window_metric_grid([('最新可用價格', clean_text(card.get('close') or card.get('price'))), ('今日 setup 狀態', presentation['daily_tactical'].get('setup')), ('是否進場', '否' if no_trade else '等待確認'), ('尾盤行動', action)])}</section>
      <section class="decision-section" data-section="pre-close-risk"><h4>尾盤風險</h4>{_window_metric_grid([('避免追價', '是'), ('接近第一目標', format_price_zone(values.get('target1'))), ('接近第二目標', format_price_zone(values.get('target2'))), ('接近停損', format_stop(values.get('stop')))])}</section>
      <section class="decision-section" data-section="next-watch"><h4>明日初步觀察</h4><p>{_escape(_first_reason(presentation))}</p></section>
    </article>
    """


def _review_result_text(tactical: dict[str, Any], review: dict[str, Any]) -> str:
    status = clean_text(review.get("status") or review.get("hit_miss_status") or review.get("direction_result"), missing="")
    if status == "no_trade":
        return "無交易"
    if status and status != "資料待接":
        return status
    if is_no_trade(tactical):
        return "無交易"
    return "本次檢討尚待實際結果"


def _tw_post_close_card(card: dict[str, Any]) -> str:
    stock_id, stock_name, tactical, review, presentation = _tw_card_base(card)
    prediction = presentation.get("prediction", {})
    result = _review_result_text(tactical, review)
    return f"""
    <article class="stock-card decision-card window-stock-card" data-market="TW" data-card-type="window-review" data-report-type="post-close-review">
      <div class="decision-card__head"><div><div class="decision-card__market">TW｜15:00 盤後檢討</div><h3>{stock_id} {stock_name}</h3></div><span class="decision-badge decision-badge--warn">{_escape(result)}</span></div>
      <section class="decision-section" data-section="prediction-review"><h4>今日預測 vs 實際</h4>{_window_metric_grid([('今日預測區間', prediction.get('today_range')), ('實際高低區間', clean_text(review.get('actual_range'), missing='本次檢討尚待實際結果')), ('方向是否命中', clean_text(review.get('direction_result'), missing='本次檢討尚待實際結果')), ('結果分類', result)])}</section>
      <section class="decision-section" data-section="outcome-review"><h4>進場 / 目標 / 停損結果</h4>{_window_metric_grid([('是否進場', clean_text(review.get('entry_result'), missing='本次檢討尚待實際結果')), ('第一目標結果', clean_text(review.get('target_1_result'), missing='未觸發 / 待確認')), ('第二目標結果', clean_text(review.get('target_2_result'), missing='未觸發 / 待確認')), ('停損結果', clean_text(review.get('stop_result'), missing='未觸發 / 待確認'))])}</section>
      <section class="decision-section" data-section="mfe-mae"><h4>MFE / MAE</h4>{_window_metric_grid([('MFE', clean_text(review.get('mfe'), missing='本次檢討尚待實際結果')), ('MAE', clean_text(review.get('mae'), missing='本次檢討尚待實際結果')), ('False Breakout', clean_text(review.get('false_breakout'), missing='待累積')), ('明日觀察', _first_risk(presentation))])}</section>
    </article>
    """


def render_tw_window_report(window: str, artifact: dict[str, Any] | None = None) -> str:
    contract = get_window_report_contract("TW", window)
    artifact = artifact if artifact is not None else _load_tw_tactical_artifact()
    cards_key = "structured_review_cards" if window == "post_close_1500" else "cards"
    cards = artifact.get(cards_key, []) if isinstance(artifact, dict) and isinstance(artifact.get(cards_key), list) else []
    presentation_artifact = dict(artifact) if isinstance(artifact, dict) else {}
    if window == "post_close_1500":
        presentation_artifact["cards"] = cards
    if window == "pre_open_0700":
        return f"""
        <section class="section window-report-section" data-market="TW" data-window="{_escape(window)}" data-report-type="pre-open-decision">
          <h2>{_escape(contract.title)}</h2>
          <p>今日盤前重點、市場環境、可觀察標的與短線操作計畫。</p>
          {_decision_intelligence_v4_html("TW", window, presentation_artifact)}
          {render_tw_tactical_cards(artifact)}
        </section>
        """
    card_renderers = {
        "intraday_1305": _tw_intraday_card,
        "pre_close_1335": _tw_pre_close_card,
        "post_close_1500": _tw_post_close_card,
    }
    renderer = card_renderers[window]
    if not cards:
        body = ('<article class="status-card warn official-review-empty-state" data-review-state="official-empty">'
                '<h3>正式 Review Payload 尚未建立</h3><p>本批次尚未建立正式 Review Payload。'
                '不跨 window 補值，不使用範例或測試資料。</p></article>') if window == "post_close_1500" else '<article class="status-card warn"><h3>資料待接</h3><p>本批次資料尚未產生，不回退到完整 generic stock report。</p></article>'
    else:
        body = ''.join(renderer(card) for card in cards if isinstance(card, dict))
    section_intro = {
        "pre_open_0700": "今日盤前重點、市場環境、可觀察標的與短線操作計畫。",
        "intraday_1305": "盤中變化、setup 觸發、目標 / 停損接近度與即時風險。",
        "pre_close_1335": "收盤前摘要、尾盤風險、避免追價與明日初步觀察。",
        "post_close_1500": "今日預測 vs 實際、進場 / 目標 / 停損結果、MFE / MAE 與明日觀察清單。",
    }[window]
    return f"""
    <section class="section window-report-section" data-market="TW" data-window="{_escape(window)}" data-report-type="{_escape({'pre_open_0700':'pre-open-decision','intraday_1305':'intraday-change','pre_close_1335':'pre-close-snapshot','post_close_1500':'post-close-review'}[window])}">
      <h2>{_escape(contract.title)}</h2>
      <p>{_escape(section_intro)}</p>
      {_decision_intelligence_v4_html("TW", window, presentation_artifact)}
      {('<p class="decision-note review-card-count" data-tracking-stock-count="' + str(artifact.get('tracking_stock_count', len(cards))) + '" data-rendered-review-card-count="' + str(len(cards)) + '">Tracking ' + str(artifact.get('tracking_stock_count', len(cards))) + '｜Rendered ' + str(len(cards)) + '</p>') if window == 'post_close_1500' else ''}
      <div class="grid decision-grid">{body}</div>
    </section>
    """

def shared_market_navigation(active_market: str, title: str, subtitle: str) -> str:
    active = html.escape(active_market)
    current_tw = ' aria-current="page"' if active_market == "TW" else ""
    current_us = ' aria-current="page"' if active_market == "US" else ""
    return f"""<div class="wrap section market-shared-navigation market-shared-navigation--v1" data-shared-navigation="tw-us" data-active-market="{active}"><h1>{html.escape(title)}</h1><nav class="market-shared-navigation__grid market-shared-navigation__grid--responsive" aria-label="Market Dashboard Navigation"><a class="market-shared-navigation__button" href="/stock-ai-dashboard/index.html">回到總覽</a><a class="market-shared-navigation__button" href="/stock-ai-dashboard/dashboard/tw/index.html"{current_tw}>台股 Dashboard</a><a class="market-shared-navigation__button" href="/stock-ai-dashboard/dashboard/us/index.html"{current_us}>美股 Dashboard</a></nav><p class="market-shared-navigation__subtitle">{html.escape(subtitle)}</p></div>"""


def _snapshot_decision_content(snapshot: dict[str, Any]) -> str:
    market = str(snapshot.get("market") or "")
    window = str(snapshot.get("window") or snapshot.get("scheduler_window") or "")
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    if market == "US":
        return render_us_window_report(window, [payload])
    if window == "post_close_1500":
        return render_tw_window_report(window, payload)
    report = payload.get("user_facing_report") if isinstance(payload.get("user_facing_report"), dict) else {}
    cards = report.get("stock_cards") if isinstance(report.get("stock_cards"), list) else []
    cards_html = "".join(
        f'<article class="stock-card decision-card snapshot-stock-card"><h3>{_escape(card.get("title") or card.get("stock_id"))}</h3><p>{_escape(card.get("summary"))}</p></article>'
        for card in cards if isinstance(card, dict)
    )
    return (
        _decision_intelligence_v4_html("TW", window, payload)
        + (f'<div class="grid decision-grid">{cards_html}</div>' if cards_html else '<p class="decision-note">此 snapshot 尚無可顯示的個股卡片。</p>')
    )


def render_immutable_snapshot_section(snapshot: dict[str, Any], *, show_revision: bool = True) -> str:
    contract = snapshot_parity_contract(snapshot)
    assert contract is not None
    updated = str(snapshot.get("revision_created_at") or snapshot.get("generated_at") or "")
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    marker = payload.get("marker")
    marker_text = f'<p class="decision-note">內容識別：{_escape(marker)}</p>' if marker else ""
    revision_text = f'｜Revision {contract["revision"]}' if show_revision and int(contract["revision"]) > 1 else ""
    updated_text = f'｜最後更新 {_escape(updated[11:16])}' if show_revision and len(updated) >= 16 else ""
    provenance = f'Runtime Provenance：{_escape(snapshot.get("runtime_provenance"))}｜Admission：{_escape(snapshot.get("admission_reason"))}｜Admitted：{str(snapshot.get("admitted") is True).lower()}'
    return f'''<section class="section immutable-snapshot-payload" {identity_attributes(snapshot)}>
      <h2>Snapshot 決策內容</h2>
      <p>有效交易日：{_escape(contract["effective_trading_date"])}{revision_text}{updated_text}</p>
      <p class="decision-note">Active Window：{_escape(contract["active_window"])}｜Source Route：{_escape(contract["source_route"])}</p>
      <p class="decision-note">{provenance}</p>
      {marker_text}
      {_snapshot_decision_content(snapshot)}
      <p class="decision-note">本頁只使用 resolver 選出的 immutable snapshot payload；不讀取全域 latest runtime。</p>
    </section>'''

def render_landing_page() -> str:
    archive_buttons: dict[str, list[str]] = {"TW": [], "US": []}
    health_rows = []
    for market, windows in MARKET_WINDOWS.items():
        for window in windows:
            selected = resolve_snapshots(WINDOW_SNAPSHOT_ARCHIVE, market, window)
            latest = selected.latest
            previous = selected.previous
            latest_date = str(latest.get("effective_trading_date")) if latest else "尚無資料"
            revision = int(latest.get("revision") or 1) if latest else 0
            updated = str(latest.get("revision_created_at") or latest.get("generated_at") or "") if latest else ""
            updated_time = updated[11:16] if len(updated) >= 16 else ""
            latest_meta = latest_date
            if revision > 1:
                latest_meta += f"｜Revision {revision}"
            if updated_time:
                latest_meta += f"｜最後更新 {updated_time}"
            previous_meta = str(previous.get("effective_trading_date")) if previous else "尚無上一有效交易日"
            runtime_provenance = _operations_runtime_provenance(market, window, latest)
            provenance_label = "Validation Only" if runtime_provenance in {"fixture", "validator", "preview", "dry_run", "controlled_no_send"} else runtime_provenance
            archive_buttons[market].extend([
                f'<a class="market-shared-navigation__button archive-browser-button" data-market="{market}" data-window="{window}" data-selection="latest" href="/stock-ai-dashboard/dashboard/archive/{market.lower()}/{window}/latest/index.html">{market}｜{window}｜Latest<br><small>{_escape(latest_meta)}</small></a>',
                f'<a class="market-shared-navigation__button archive-browser-button" data-market="{market}" data-window="{window}" data-selection="previous" href="/stock-ai-dashboard/dashboard/archive/{market.lower()}/{window}/previous/index.html">{market}｜{window}｜Previous<br><small>{_escape(previous_meta)}</small></a>',
            ])
            archive_status = "已累積" if latest else "等待首筆正式資料"
            overall_status = "可用" if latest else "等待資料（非失敗）"
            parity = snapshot_parity_contract(latest) or {}
            latest_payload = latest.get("payload") if isinstance(latest, dict) and isinstance(latest.get("payload"), dict) else {}
            health_rows.append(f'<tr data-market="{market}" data-window="{window}" data-snapshot-id="{_escape(parity.get("snapshot_id"))}" data-payload-hash="{_escape(parity.get("payload_hash"))}" data-tracking-stock-count="{_escape(latest_payload.get("tracking_stock_count"))}"><th>{market}｜{_escape(window)}</th><td>{_escape(latest_date)}</td><td>{revision or "—"}</td><td>{_escape(previous_meta)}</td><td>{_escape(provenance_label)}</td><td>設定維持</td><td>依正式批次</td><td>可建置</td><td>{_escape(archive_status)}</td><td>未發送</td><td>未發送</td><td>{_escape(overall_status)}</td></tr>')
    archive_buttons_html = "".join(
        f'<section class="archive-market-group" data-market="{market}"><h3>{"台股批次" if market == "TW" else "美股批次"}</h3><div class="market-shared-navigation__grid">{"".join(archive_buttons[market])}</div></section>'
        for market in ("TW", "US")
    )
    health_rows_html = "".join(health_rows)
    return f"""<!doctype html>
    <html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>AI Multi-Market Decision Intelligence</title><style>{base_css()}</style></head>
    <body><header><div class="wrap"><h1>AI Multi-Market Decision Intelligence</h1><p>台股與美股分流入口；LINE/Email 依市場連到正確 Dashboard。</p></div></header><main class="wrap">
    <div class="grid">
      <a class="section market-choice" href="/stock-ai-dashboard/dashboard/tw/index.html"><h2>台股 Dashboard</h2><p>07:00 盤前｜13:05 盤中｜13:35 收盤快照｜15:00 盤後／檢討</p><span class="badge">TW</span></a>
      <a class="section market-choice" href="/stock-ai-dashboard/dashboard/us/index.html"><h2>美股 Dashboard</h2><p>20:00 美股盤前｜23:00 美股盤中｜06:30 美股盤後檢討</p><span class="badge">US</span></a>
    </div>
    <section class="section" id="snapshot-archive-browser"><h2>批次報告歷史</h2><p>Latest 是最新有效交易日最高 revision；Previous 永遠是上一有效交易日最高 revision。</p>{archive_buttons_html}</section>
    <section class="section" id="production-operations-center"><h2>系統營運中心</h2><p class="decision-note">Production health 內容投影不改變既有 health source；archive empty state 是等待資料，不是批次失敗。</p><div class="operations-table-scroll" role="region" aria-label="Production Operations Center" tabindex="0"><table class="decision-table operations-table"><thead><tr><th>Market / Window</th><th>Latest</th><th>Revision</th><th>Previous</th><th>Runtime Provenance</th><th>Scheduler</th><th>Pipeline</th><th>Dashboard</th><th>Archive</th><th>LINE</th><th>Email</th><th>Overall</th></tr></thead><tbody>{health_rows_html}</tbody></table></div></section>
    {render_manual_control_center()}
    <section class="section"><h2>Runtime 狀態摘要</h2><p>Dashboard 顯示完整內容；Email 顯示 window-specific 摘要；LINE 僅作短提醒與入口。舊四時段網址保留為台股相容入口。</p></section>
    </main></body></html>\n"""
def render_tw_page(source_html: str | None = None) -> str:
    nav = shared_market_navigation("TW", "台股 AI 決策儀表板", "TW 專用頁：07:00 / 13:05 / 13:35 / 15:00。美股內容不在此頁渲染。")
    active = resolve_active_snapshot(WINDOW_SNAPSHOT_ARCHIVE, "TW")
    window_reports = render_immutable_snapshot_section(active) if active else '<section class="section archive-empty-state"><h2>尚無可用 snapshot</h2><p>TW 尚無 successful admitted snapshot；不回退到 fixture、validator、preview 或 global latest runtime。</p></section>'
    manual_pointer = '<section class="section"><h2>手動批次控制</h2><p><a href="/stock-ai-dashboard/index.html#manual-batch-control-center">手動批次控制請回到總覽頁</a></p></section>'
    return f"""<!doctype html>
    <html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>台股 AI 決策儀表板</title><meta name="market" content="TW"><style>{base_css()}</style></head>
    <body {identity_attributes(active)}><header>{nav}</header><main class="wrap">
    {window_reports}
    {manual_pointer}
    </main></body></html>\n"""


def render_us_page(artifacts: list[dict[str, Any]] | None = None) -> str:
    active = resolve_active_snapshot(WINDOW_SNAPSHOT_ARCHIVE, "US")
    window_reports = render_immutable_snapshot_section(active) if active else '<section class="section archive-empty-state"><h2>尚無可用 snapshot</h2><p>US 尚無 successful admitted snapshot；不回退到 fixture、validator、preview、dry-run 或 global latest runtime。</p></section>'
    return f"""<!doctype html>
    <html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>美股 AI 決策儀表板</title><meta name="market" content="US"><style>{base_css()}</style></head>
    <body {identity_attributes(active)}><header>{shared_market_navigation("US", "美股 AI 決策儀表板", "美股盤前 20:00｜美股盤中 23:00｜美股檢討 06:30")}</header><main class="wrap">
    <!-- AI-DEV-170-US-DASHBOARD-START -->
    {window_reports}
    <!-- AI-DEV-170-US-DASHBOARD-END -->
    </main></body></html>\n"""


def _content_generated_at(artifacts: list[dict[str, Any]]) -> str:
    """Stable build identity derived from rendered inputs, not validator wall time."""
    candidates = [str(item.get("generated_at") or "") for item in artifacts]
    tw = _load_tw_tactical_artifact()
    if tw:
        candidates.append(str(tw.get("generated_at") or ""))
    for market, windows in MARKET_WINDOWS.items():
        for window in windows:
            selected = resolve_snapshots(WINDOW_SNAPSHOT_ARCHIVE, market, window)
            for snapshot in (selected.latest, selected.previous):
                if snapshot:
                    candidates.append(str(snapshot.get("revision_created_at") or snapshot.get("generated_at") or ""))
    return max([value for value in candidates if value] or ["content-not-yet-generated"])

def build_pages(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = _load_us_artifacts()
    pages = {
        "landing": render_landing_page(),
        "tw": render_tw_page(),
        "us": render_us_page(artifacts),
        "old_compat": render_tw_page(),
    }
    paths = {
        "landing": output_dir / "index.html",
        "tw": output_dir / "tw_index.html",
        "us": output_dir / "us_index.html",
        "old_compat": output_dir / "old_four_window_index.html",
    }
    for key, path in paths.items():
        path.write_text(stable_html(pages[key]), encoding="utf-8")
    archive_routes: dict[str, str] = {}
    for market, windows in MARKET_WINDOWS.items():
        for window in windows:
            for name in ("latest", "previous"):
                route = f"dashboard/archive/{market.lower()}/{window}/{name}/index.html"
                target = output_dir / route
                build_archive_route(output_dir, market, window, name)
                archive_routes[f"{market}:{window}:{name}"] = str(target)
    manifest = {
        "schema_version": "multi_market_dashboard_v2_build_v1",
        "task_id": "AI-DEV-181",
        "generated_at": _content_generated_at(artifacts),
        "landing_url": LANDING_URL,
        "tw_url": TW_URL,
        "us_url": US_URL,
        "old_compat_url": PUBLIC_BASE_URL + OLD_ROUTE,
        "us_stock_count": us_stock_count(artifacts),
        "market_isolation": {"tw_reads_us_artifacts": False, "us_reads_tw_artifacts": False, "cross_market_fallback": False},
        "paths": {key: str(path) for key, path in paths.items()},
        "archive_routes": archive_routes,
        "archive_route_count": len(archive_routes),
    }
    (output_dir / "manifest.json").write_text(stable_json(manifest), encoding="utf-8")
    return manifest


def render_snapshot_archive_page(market: str, window: str, selection: str, snapshot: dict[str, Any] | None, comparison: dict[str, Any]) -> str:
    if snapshot is None:
        body = '<section class="section archive-empty-state"><h2>尚無可用 snapshot</h2><p>找不到符合正式、完整、非 fixture / validator 且同市場同時段的 immutable snapshot。</p></section>'
        identity = ""
    else:
        identity = identity_attributes(snapshot)
        revision = int(snapshot.get("revision") or 1)
        updated = str(snapshot.get("revision_created_at") or snapshot.get("generated_at") or "")
        revision_text = f"｜Revision {revision}" if selection == "latest" and revision > 1 else ""
        updated_text = f"｜最後更新 {updated[11:16]}" if selection == "latest" and len(updated) >= 16 else ""
        body = render_immutable_snapshot_section(snapshot, show_revision=selection == "latest")
        if market == "TW" and window == "pre_close_1335":
            body += render_tw_1335_dashboard(tw_1335_context_for_snapshot(WINDOW_SNAPSHOT_ARCHIVE, snapshot))
        if selection == "latest":
            revisions = revisions_for_snapshot(WINDOW_SNAPSHOT_ARCHIVE, market, window, str(snapshot.get("effective_trading_date")))
            manual_count = len([item for item in revisions if item.get("manual_rerun") is True or item.get("run_kind") == "manual_rerun"])
            rows = "".join(f'<tr><th>Revision {int(item.get("revision") or 1)}</th><td>{_escape(str(item.get("revision_created_at") or item.get("generated_at") or "")[11:16])}</td><td>{"Manual" if item.get("manual_rerun") is True or item.get("run_kind") == "manual_rerun" else "正式批次"}</td></tr>' for item in revisions)
            body += f'<section class="section revision-history"><h2>本交易日 Revision History</h2><p>共手動更新 {manual_count} 次</p><table class="decision-table"><tbody>{rows}</tbody></table></section>'
    if comparison.get("available"):
        changed_count = len(comparison.get("changes", []))
        change = f'<section class="section same-window-change"><h2>同時段跨交易日變化</h2><p>{_escape(comparison.get("previous_trading_date"))} → {_escape(comparison.get("current_trading_date"))}；決策來源欄位變更 {changed_count} 項。</p><p class="decision-note">比較基準固定為同市場、同 window、前一有效交易日最高 revision；不顯示原始 payload 或 runtime metadata。</p></section>'
    else:
        change = f'<section class="section same-window-change archive-empty-state"><h2>同時段跨交易日變化</h2><p>{_escape(comparison.get("empty_state"))}</p></section>'
    return f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{_escape(market)} {_escape(window)} {_escape(selection)}</title><style>{base_css()}</style></head><body {identity}><header>{shared_market_navigation(market, f"{market} Snapshot Archive", f"{window}｜{selection}")}</header><main class="wrap">{body}{change}</main></body></html>\n'


def build_archive_route(output_dir: Path, market: str, window: str, selection_name: str) -> Path:
    selected = resolve_snapshots(WINDOW_SNAPSHOT_ARCHIVE, market, window)
    snapshot = selected.latest if selection_name == "latest" else selected.previous
    comparison = same_window_change(selected.latest, selected.previous)
    target = output_dir / f"dashboard/archive/{market.lower()}/{window}/{selection_name}/index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stable_html(render_snapshot_archive_page(market, window, selection_name, snapshot, comparison)), encoding="utf-8")
    return target


def publish_archive_latest_route(market: str, window: str, static_root: Path = STATIC_ROOT, output_dir: Path = Path("/tmp/stock-ai-dashboard-archive-latest")) -> dict[str, Any]:
    """Manual rerun contract: rebuild and publish this window's latest route only."""
    source = build_archive_route(output_dir, market, window, "latest")
    target = static_root / f"dashboard/archive/{market.lower()}/{window}/latest/index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_copy(source, target)
    return {"published": True, "selection": "latest", "market": market, "window": window, "source": str(source), "target": str(target), "previous_updated": False, "other_windows_updated": False, "notification_sent": False, "production_pipeline_executed": False}


def publish_market_dashboard_alias(market: str, static_root: Path = STATIC_ROOT, output_dir: Path = Path("/tmp/stock-ai-dashboard-market-alias")) -> dict[str, Any]:
    """Publish one market wrapper from the same resolver-selected immutable payload."""
    active = resolve_active_snapshot(WINDOW_SNAPSHOT_ARCHIVE, market)
    if not active:
        return {"published": False, "market": market, "reason": "no_admitted_active_snapshot"}
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = "tw_index.html" if market == "TW" else "us_index.html"
    source = output_dir / filename
    source.write_text(stable_html(render_tw_page() if market == "TW" else render_us_page()), encoding="utf-8")
    target = static_root / f"dashboard/{market.lower()}/index.html"
    _atomic_copy(source, target)
    parity = snapshot_parity_contract(active)
    return {"published": True, "market": market, "source": str(source), "target": str(target), "parity": parity}


def publish_manual_rerun_update(market: str, window: str, static_root: Path = STATIC_ROOT, output_dir: Path = Path("/tmp/stock-ai-dashboard-manual-rerun")) -> dict[str, Any]:
    """Update target Latest and sync the market page only when the target is active."""
    latest = publish_archive_latest_route(market, window, static_root=static_root, output_dir=output_dir / "latest")
    active = resolve_active_snapshot(WINDOW_SNAPSHOT_ARCHIVE, market)
    active_window = str(active.get("window") or "") if active else None
    market_result = (
        publish_market_dashboard_alias(market, static_root=static_root, output_dir=output_dir / "market")
        if active_window == window else
        {"published": False, "market": market, "reason": "manual_window_is_not_active", "active_window": active_window}
    )
    return {
        "latest": latest,
        "market_dashboard": market_result,
        "active_window": active_window,
        "latest_route_updated": latest.get("published") is True,
        "market_dashboard_updated": market_result.get("published") is True,
        "previous_route_updated": False,
        "other_windows_updated": False,
        "notification_sent": False,
        "production_pipeline_executed": False,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(f".{target.name}.ai-dev-181d.tmp")
    shutil.copy2(source, staged)
    os.replace(staged, target)


def production_landing_contract_errors(page: str) -> list[str]:
    errors = []
    for marker in ("台股 Dashboard", "美股 Dashboard", "批次報告歷史", "台股手動批次", "美股手動批次", "系統營運中心"):
        if marker not in page:
            errors.append(f"missing:{marker}")
    expected_counts = {
        "archive_buttons": (page.count('class="market-shared-navigation__button archive-browser-button"'), 14),
        "manual_buttons": (page.count('class="manual-batch-button"'), 7),
        "operations_rows": (page.count('<tr data-market='), 7),
    }
    errors.extend(f"{name}:{actual}!={expected}" for name, (actual, expected) in expected_counts.items() if actual != expected)
    lowered = page.lower()
    for marker in ("stock ai legacy / debug landing", "legacy / debug landing", "raw pipeline report content", "正式決策入口已移至四時段"):
        if marker.lower() in lowered:
            errors.append(f"forbidden:{marker}")
    return errors


def publish_pages(static_root: Path = STATIC_ROOT, source_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    manifest = build_pages(source_dir)
    landing_source = source_dir / "index.html"
    landing_errors = production_landing_contract_errors(landing_source.read_text(encoding="utf-8"))
    if landing_errors:
        raise ValueError("production landing contract failed before publish: " + ", ".join(landing_errors))
    timestamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d-%H%M%S")
    backup = static_root / ".ai_dev_170_rollback" / timestamp
    backup.mkdir(parents=True, exist_ok=True)
    targets = {
        "landing": static_root / "index.html",
        "tw": static_root / "dashboard/tw/index.html",
        "us": static_root / "dashboard/us/index.html",
        "old_compat": static_root / "dashboard/decision-intelligence/four-window-preview/index.html",
    }
    sources = {
        "landing": source_dir / "index.html",
        "tw": source_dir / "tw_index.html",
        "us": source_dir / "us_index.html",
        "old_compat": source_dir / "old_four_window_index.html",
    }
    for key, target in targets.items():
        if target.exists():
            dest = backup / (key + ".before_ai_dev_170.html")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
        _atomic_copy(sources[key], target)
    archive_source = source_dir / "dashboard/archive"
    archive_target = static_root / "dashboard/archive"
    if archive_source.exists():
        for source in sorted(archive_source.rglob("index.html")):
            relative = source.relative_to(archive_source)
            target = archive_target / relative
            _atomic_copy(source, target)
    result = {
        **manifest,
        "published": True,
        "static_root": str(static_root),
        "backup_path": str(backup),
        "notification_sent": False,
        "production_pipeline_executed": False,
        "archive_route_count": manifest.get("archive_route_count", 0),
        "production_landing_owner": PRODUCTION_LANDING_OWNER,
        "production_source_hash": _sha256(landing_source),
        "staged_landing_hash": _sha256(landing_source),
        "public_landing_hash": _sha256(static_root / "index.html"),
        "rollback_command": f"cp {backup}/landing.before_ai_dev_170.html {static_root}/index.html 2>/dev/null || true; cp {backup}/tw.before_ai_dev_170.html {static_root}/dashboard/tw/index.html 2>/dev/null || true; cp {backup}/us.before_ai_dev_170.html {static_root}/dashboard/us/index.html 2>/dev/null || true; cp {backup}/old_compat.before_ai_dev_170.html {static_root}/dashboard/decision-intelligence/four-window-preview/index.html 2>/dev/null || true",
    }
    (static_root / ".ai_dev_170_publish_latest.json").write_text(stable_json(result), encoding="utf-8")
    return result
