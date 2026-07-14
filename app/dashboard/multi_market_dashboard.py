"""Multi-market Dashboard V2 renderer for TW/US route isolation."""
from __future__ import annotations

import html
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_BASE_URL = "http://35.201.242.167/stock-ai-dashboard"
LANDING_ROUTE = "/index.html"
TW_ROUTE = "/dashboard/tw/index.html"
US_ROUTE = "/dashboard/us/index.html"
OLD_ROUTE = "/dashboard/decision-intelligence/four-window-preview/index.html"
TW_URL = PUBLIC_BASE_URL + TW_ROUTE
US_URL = PUBLIC_BASE_URL + US_ROUTE
LANDING_URL = PUBLIC_BASE_URL + LANDING_ROUTE
STATIC_ROOT = Path("/var/www/stock-ai-dashboard")
TW_TEMPLATE = REPO_ROOT / "templates/four_window_dashboard_route_preview.example.html"
OUTPUT_DIR = REPO_ROOT / "templates/multi_market_dashboard_v2"
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
    return (
        data.get("market") == "US"
        and data.get("artifact_kind") == "us_stock_runtime"
        and data.get("data_source_mode") == "live"
        and data.get("fixture") is False
        and data.get("artifact_mode") == "production_runtime"
        and data.get("validation_only") is False
    )


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
        data["_source_path"] = str(path.relative_to(REPO_ROOT))
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

def base_css() -> str:
    return """
    body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8f9;color:#17262c;line-height:1.55}
    header,.hero{background:#0f2c33;color:white;padding:24px 18px}.wrap{max-width:1120px;margin:0 auto;padding:18px;padding-left:max(18px,env(safe-area-inset-left));padding-right:max(18px,env(safe-area-inset-right))}.nav{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.nav a,.btn{display:inline-block;background:#fff;color:#0f2c33;text-decoration:none;border-radius:8px;padding:10px 12px;font-weight:800;border:1px solid #cbd8dc}
    """ + SHARED_NAVIGATION_CSS + TW_TACTICAL_CSS + """
    .section{background:white;border:1px solid #dce5e8;border-radius:10px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.stock-card,.status-card{background:#fff;border:1px solid #d9e4e7;border-radius:12px;padding:16px;overflow-wrap:anywhere;word-break:break-word}.card-kicker{font-weight:800;color:#35606b;font-size:13px}h1,h2,h3{margin:0 0 10px}dl{display:grid;gap:8px}dt{font-weight:800;color:#51666d}dd{margin:0}.badge{display:inline-block;border-radius:999px;padding:6px 10px;background:#e8f5e9;color:#225d28;font-weight:800}.warn{background:#fff9e8}.market-choice{display:block;text-decoration:none;color:#17262c}.market-choice h2{color:#0f5368}@media(max-width:640px){.wrap{padding:18px;padding-left:max(18px,env(safe-area-inset-left));padding-right:max(18px,env(safe-area-inset-right))}.grid{grid-template-columns:1fr;gap:16px}.nav a{width:100%;box-sizing:border-box}}
    """



def shared_market_navigation(active_market: str, title: str, subtitle: str) -> str:
    active = html.escape(active_market)
    current_tw = ' aria-current="page"' if active_market == "TW" else ""
    current_us = ' aria-current="page"' if active_market == "US" else ""
    return f"""<div class="wrap section market-shared-navigation market-shared-navigation--v1" data-shared-navigation="tw-us" data-active-market="{active}"><h1>{html.escape(title)}</h1><nav class="market-shared-navigation__grid market-shared-navigation__grid--responsive" aria-label="Market Dashboard Navigation"><a class="market-shared-navigation__button" href="/stock-ai-dashboard/index.html">回到總覽</a><a class="market-shared-navigation__button" href="/stock-ai-dashboard/dashboard/tw/index.html"{current_tw}>台股 Dashboard</a><a class="market-shared-navigation__button" href="/stock-ai-dashboard/dashboard/us/index.html"{current_us}>美股 Dashboard</a></nav><p class="market-shared-navigation__subtitle">{html.escape(subtitle)}</p></div>"""

def render_landing_page() -> str:
    return f"""<!doctype html>
    <html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>AI Multi-Market Decision Intelligence</title><style>{base_css()}</style></head>
    <body><header><div class="wrap"><h1>AI Multi-Market Decision Intelligence</h1><p>台股與美股分流入口；LINE/Email 依市場連到正確 Dashboard。</p></div></header><main class="wrap">
    <div class="grid">
      <a class="section market-choice" href="/stock-ai-dashboard/dashboard/tw/index.html"><h2>台股 Dashboard</h2><p>07:00 盤前｜13:05 盤中｜13:35 收盤快照｜15:00 盤後／檢討</p><span class="badge">TW</span></a>
      <a class="section market-choice" href="/stock-ai-dashboard/dashboard/us/index.html"><h2>美股 Dashboard</h2><p>20:00 美股盤前｜23:00 美股盤中｜06:30 美股盤後檢討</p><span class="badge">US</span></a>
    </div>
    <section class="section"><h2>資料狀態</h2><p>Dashboard 顯示完整內容；Email 顯示完整摘要；LINE 僅作短提醒與入口。舊四時段網址保留為台股相容入口。</p></section>
    </main></body></html>\n"""

def render_tw_page(source_html: str | None = None) -> str:
    body = source_html if source_html is not None else (TW_TEMPLATE.read_text(encoding="utf-8") if TW_TEMPLATE.exists() else "<p>台股 Dashboard 資料待接</p>")
    body = body.replace("Prediction", "預測").replace("Research", "研究")
    nav = shared_market_navigation("TW", "台股 AI 決策儀表板", "TW 專用頁：07:00 / 13:05 / 13:35 / 15:00。美股內容不在此頁渲染。")
    dual_strategy = """<div class="wrap section" id="ai-dev-173-tw-dual-strategy"><h2>中長期量化策略</h2><p>保留既有研究／持有策略行為，回答是否值得持有；每日短期操作策略獨立回答今天到 1-5 個交易日的操作計畫。</p></div>""" + render_tw_tactical_cards()
    shared_style = f'<style id="shared-market-navigation-style">{SHARED_NAVIGATION_CSS}{TW_TACTICAL_CSS}</style>'
    if "</head>" in body and "shared-market-navigation-style" not in body:
        body = body.replace("</head>", shared_style + "</head>", 1)
    else:
        nav = shared_style + nav
    header = nav + dual_strategy
    if "<body>" in body:
        body = body.replace("<body>", "<body>" + header + "\n", 1)
    elif "<body " in body:
        idx = body.find(">", body.find("<body "))
        body = body[: idx + 1] + header + "\n" + body[idx + 1:]
    elif "</body>" in body:
        body = body.replace("</body>", header + "\n</body>")
    else:
        body = header + body
    if "<title>" in body:
        body = body.replace("<title>", "<title>台股 AI 決策儀表板 | ", 1)
    return body


def render_us_page(artifacts: list[dict[str, Any]] | None = None) -> str:
    artifacts = artifacts if artifacts is not None else _load_us_artifacts()
    count = us_stock_count(artifacts)
    latest = max([str(a.get("generated_at") or "") for a in artifacts] or ["資料待接"])
    cards = render_us_cards(artifacts)
    return f"""<!doctype html>
    <html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>美股 AI 決策儀表板</title><meta name="market" content="US"><style>{base_css()}</style></head>
    <body><header>{shared_market_navigation("US", "美股 AI 決策儀表板", "美股盤前 20:00｜美股盤中 23:00｜美股檢討 06:30")}</header><main class="wrap">
    <!-- AI-DEV-170-US-DASHBOARD-START -->
    <section class="section"><h2>美股資料摘要</h2><p>啟用股票數：{count}</p><p>最新更新：{html.escape(latest)}</p><p>資料來源：工作表2 / 正式美股 runtime；美股頁不回退到台股資料，也不渲染驗證 fixture。</p></section>
    <section class="section"><h2>市場摘要</h2><p>SPY / QQQ / VIX 與類股脈絡作為美股研究評分的第二層市場參考。</p></section>
    <section class="section"><h2>今日結論</h2><p>主畫面以中長期研究、每日短線策略、預測與信心四張摘要卡開場。</p></section>
    <section class="section"><h2>每日短線策略</h2><p>操作計畫使用跳空、動能、量能、趨勢、波動、指數與類股脈絡、財報與事件風險，以及既有 runtime 產生的進場、停損與目標價位。</p></section>
    <section class="section"><h2>中長期研究</h2><p>保留技術、SEC、基本面、財報與指引、官方事件、市場脈絡等證據，用於數日到數月的持有判斷。</p></section>
    <section class="section"><h2>財務體質</h2><p>營收、利潤率、現金流、槓桿與資料品質會在資料可用時依股票呈現。</p></section>
    <section class="section"><h2>財報與指引</h2><p>公司已公布結果、公司指引與第三方估計分開呈現；未驗證的指引不會被編造。</p></section>
    <section class="section"><h2>SEC / 官方事件</h2><p>SEC EDGAR 文件與公司 IR / 新聞室紀錄屬於第一層官方證據；yfinance 保留為市場參考資料。</p></section>
    <section class="section"><h2>近期新聞與事件</h2><p>新聞標題來源經分類、去重後呈現；不儲存完整文章，也不產生假新聞。</p></section>
    <section class="section"><h2>預測與檢討</h2><p>預測與檢討使用既有 runtime 結果；若資料存在，會區分技術、市場、新聞、官方事件與資料品質因素。</p></section>
    <section class="section"><h2>美股個股卡</h2><div class="grid">{cards}</div></section>
    <!-- AI-DEV-170-US-DASHBOARD-END -->
    </main></body></html>\n"""

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
    manifest = {
        "schema_version": "multi_market_dashboard_v2_build_v1",
        "task_id": "AI-DEV-170",
        "generated_at": now_taipei(),
        "landing_url": LANDING_URL,
        "tw_url": TW_URL,
        "us_url": US_URL,
        "old_compat_url": PUBLIC_BASE_URL + OLD_ROUTE,
        "us_stock_count": us_stock_count(artifacts),
        "market_isolation": {"tw_reads_us_artifacts": False, "us_reads_tw_artifacts": False, "cross_market_fallback": False},
        "paths": {key: str(path) for key, path in paths.items()},
    }
    (output_dir / "manifest.json").write_text(stable_json(manifest), encoding="utf-8")
    return manifest

def publish_pages(static_root: Path = STATIC_ROOT, source_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    manifest = build_pages(source_dir)
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
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sources[key], target)
    result = {
        **manifest,
        "published": True,
        "static_root": str(static_root),
        "backup_path": str(backup),
        "notification_sent": False,
        "production_pipeline_executed": False,
        "rollback_command": f"cp {backup}/landing.before_ai_dev_170.html {static_root}/index.html 2>/dev/null || true; cp {backup}/tw.before_ai_dev_170.html {static_root}/dashboard/tw/index.html 2>/dev/null || true; cp {backup}/us.before_ai_dev_170.html {static_root}/dashboard/us/index.html 2>/dev/null || true; cp {backup}/old_compat.before_ai_dev_170.html {static_root}/dashboard/decision-intelligence/four-window-preview/index.html 2>/dev/null || true",
    }
    (static_root / ".ai_dev_170_publish_latest.json").write_text(stable_json(result), encoding="utf-8")
    return result
