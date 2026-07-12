"""Multi-market Dashboard V2 renderer for TW/US route isolation."""
from __future__ import annotations

import html
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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

def now_taipei() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()

def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

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


def _tw_zone(zone: Any) -> str:
    if not isinstance(zone, dict):
        return "資料不足"
    low = zone.get("low")
    high = zone.get("high")
    if low is None or high is None:
        return "資料不足"
    return f"{_escape(low)} ～ {_escape(high)}"


def _tw_list(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "<li>資料待接</li>"
    return "".join(f"<li>{_escape(item)}</li>" for item in items[:4])


def render_tw_tactical_cards(artifact: dict[str, Any] | None = None) -> str:
    artifact = artifact if artifact is not None else _load_tw_tactical_artifact()
    if not artifact:
        return """<div class="wrap section" id="tw-daily-tactical-runtime" data-strategy-type="daily_tactical"><h2>每日短期操作策略</h2><p>TW Daily Tactical runtime artifact 尚未產生；不會用 Research 或 US 資料 fallback。</p></div>"""
    cards = artifact.get("cards", []) if isinstance(artifact.get("cards"), list) else []
    market_context = artifact.get("market_context", {}) if isinstance(artifact.get("market_context"), dict) else {}
    header = f"""
    <div class="wrap section" id="tw-daily-tactical-runtime" data-market="TW" data-strategy-type="daily_tactical">
      <h2>每日短期操作策略</h2>
      <p>Strategy ID：{_escape(artifact.get('strategy_id'))}｜Factor Version：{_escape(artifact.get('factor_version'))}｜更新：{_escape(artifact.get('generated_at'))}</p>
      <p>市場環境：{_escape(market_context.get('market_bias'))}｜風險：{_escape(market_context.get('market_risk'))}｜Regime：{_escape(market_context.get('market_regime'))}</p>
      <p>Research / Position Strategy 保持獨立；Daily Tactical 只使用台股技術、量能、籌碼/flow、波動與事件風險，不使用 US premarket / SPY / QQQ / VIX。</p>
      <div class="grid tw-tactical-grid">
    """
    rows: list[str] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
        research = strategies.get("research_position", {}) if isinstance(strategies.get("research_position"), dict) else {}
        tactical = strategies.get("daily_tactical", {}) if isinstance(strategies.get("daily_tactical"), dict) else {}
        review = card.get("review_snapshot", {}) if isinstance(card.get("review_snapshot"), dict) else {}
        rows.append(f"""
        <article class="stock-card tw-tactical-card" data-market="TW" data-strategy-type="daily_tactical">
          <div class="card-kicker">TW｜research_position + daily_tactical</div>
          <h3>{_escape(card.get('stock_id'))} {_escape(card.get('stock_name'))}</h3>
          <dl>
            <div><dt>中長期量化策略</dt><dd>Score {_escape(research.get('score'))}｜{_escape(research.get('rating'))}｜{_escape(research.get('action'))}｜Confidence {_escape(research.get('confidence'))}</dd></div>
            <div><dt>Daily Tactical Direction</dt><dd>{_escape(tactical.get('direction'))}｜{_escape(tactical.get('setup_type'))}｜{_escape(tactical.get('action'))}</dd></div>
            <div><dt>Tactical Score / Rating / Confidence</dt><dd>{_escape(tactical.get('score'))}｜{_escape(tactical.get('rating'))}｜{_escape(tactical.get('confidence'))}</dd></div>
            <div><dt>Entry Zone</dt><dd>{_tw_zone(tactical.get('entry_zone'))}</dd></div>
            <div><dt>Stop / Invalidation</dt><dd>{_escape(tactical.get('stop_invalidation'))}</dd></div>
            <div><dt>Target 1</dt><dd>{_tw_zone(tactical.get('target_1'))}</dd></div>
            <div><dt>Target 2</dt><dd>{_tw_zone(tactical.get('target_2'))}</dd></div>
            <div><dt>Expected Move / Reward-Risk</dt><dd>{_escape(tactical.get('expected_move_pct'))}%｜{_escape(tactical.get('reward_risk'))}</dd></div>
            <div><dt>Chase / Event / Position</dt><dd>{_escape(tactical.get('chase_risk'))}｜{_escape(tactical.get('event_risk'))}｜{_escape(tactical.get('position_size'))}</dd></div>
            <div><dt>Data Quality</dt><dd>{_escape(tactical.get('data_quality'))}</dd></div>
            <div><dt>Prediction Review</dt><dd>{_escape(review.get('review_status'))}｜Entry {_escape(review.get('entry_triggered'))}｜T1 {_escape(review.get('target_1_reached'))}｜Stop {_escape(review.get('stop_breached'))}</dd></div>
          </dl>
          <details open><summary>主要依據</summary><ul>{_tw_list(tactical.get('reasons'))}</ul></details>
          <details><summary>主要風險</summary><ul>{_tw_list(tactical.get('risk_reasons'))}</ul></details>
          <p class="risk-note">Playbook：{_escape(tactical.get('playbook'))}</p>
        </article>
        """)
    return header + "\n".join(rows) + "</div></div>"

def _strategy_html(card: dict[str, Any]) -> str:
    strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
    research = strategies.get("research_position") or card.get("research_position_summary") or {}
    tactical = strategies.get("daily_tactical") or card.get("daily_tactical_summary") or {}
    return f"""
              <section class="strategy-pair" data-strategy="dual">
                <h4>Research / Position Strategy</h4>
                <p>Score / Rating / Action / Confidence：{_escape(research.get('score'))} / {_escape(research.get('rating'))} / {_escape(research.get('action'))} / {_escape(research.get('confidence'))}</p>
                <p>Horizon：{_escape(research.get('horizon') or 'days to months')}</p>
                <h4>Daily Tactical Strategy</h4>
                <p>方向 / Setup / Action：{_escape(tactical.get('tactical_direction') or tactical.get('direction'))} / {_escape(tactical.get('setup_type'))} / {_escape(tactical.get('action'))}</p>
                <p>分數 / 等級 / 信心：{_escape(tactical.get('tactical_score') or tactical.get('score'))} / {_escape(tactical.get('tactical_grade') or tactical.get('grade'))} / {_escape(tactical.get('tactical_confidence') or tactical.get('confidence'))}</p>
                <p>進場區：{_fmt_zone(tactical.get('entry_zone'))}｜停損/失效：{_escape(tactical.get('stop_reference') or tactical.get('invalidation_level'))}｜目標一：{_fmt_zone(tactical.get('target_zone_1'))}</p>
                <p>預期波動 / 報酬風險：{_escape(tactical.get('expected_move'))} / {_escape(tactical.get('reward_risk_ratio'))}｜追高風險：{_escape(tactical.get('chase_risk'))}｜事件風險：{_escape(tactical.get('event_risk'))}</p>
                <p class="risk-note">Daily Tactical 為研究參考，不是交易指令；未觸發 setup 不算自動失敗。</p>
              </section>
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
            news = card.get("bilingual_news_snippet", {}) if isinstance(card.get("bilingual_news_snippet"), dict) else {}
            rows.append(f"""
            <article class="stock-card us-stock-card" data-market="US">
              <div class="card-kicker">{html.escape(window_label)}｜US</div>
              <h3>{_escape(symbol)} {_escape(card.get('name'))}</h3>
              <dl>
                <div><dt>交易所</dt><dd>{_escape(card.get('exchange') or _exchange_for(artifact, symbol))}</dd></div>
                <div><dt>USD 價格</dt><dd>{_escape(card.get('price'))}</dd></div>
                <div><dt>評等 / 動作 / 信心</dt><dd>{_escape(card.get('rating'))} / {_escape(card.get('action'))} / {_escape(card.get('confidence'))}</dd></div>
                <div><dt>本次預測區間</dt><dd>{_escape(card.get('session_predicted_high_low'))}</dd></div>
                <div><dt>下次預測區間</dt><dd>{_escape(card.get('next_session_predicted_high_low'))}</dd></div>
                <div><dt>1M / 3M 趨勢</dt><dd>{_escape(card.get('one_month_trend'))} / {_escape(card.get('three_month_trend'))}</dd></div>
                <div><dt>技術摘要</dt><dd>{_escape(card.get('technical_summary'))}</dd></div>
                <div><dt>財務品質</dt><dd>{_escape(card.get('financial_quality'))}</dd></div>
                <div><dt>盈餘 / 指引</dt><dd>{_escape(card.get('latest_earnings_status'))} / {_escape(card.get('guidance_direction'))}</dd></div>
                <div><dt>SEC 最新 filing</dt><dd>{_escape(card.get('latest_sec_filing'))}</dd></div>
                <div><dt>官方事件</dt><dd>{_escape(card.get('official_event_warning'))}</dd></div>
                <div><dt>研究因子</dt><dd>{_escape(card.get('research_score'))} / {_escape(card.get('research_rating'))}</dd></div>
                <div><dt>策略版本</dt><dd>research_position / daily_tactical</dd></div>
                <div><dt>資料狀態</dt><dd>{_escape(card.get('latest_status'))}</dd></div>
                <div><dt>來源新鮮度</dt><dd>{_escape(card.get('source_freshness'))}</dd></div>
              </dl>
              {_strategy_html(card)}
              <details class="news-block" open><summary>Bilingual News / 雙語新聞</summary><p><strong>EN:</strong> {_escape(news.get('english_headline'))}</p><p><strong>中:</strong> {_escape(news.get('chinese_translation'))}</p><p>{_escape(news.get('investment_reading'))}</p><p>Vocabulary：{_escape(news.get('vocabulary'))}</p></details>
              <details class="review-block"><summary>Prediction Review / 檢討</summary><p>{_escape(artifact.get('prediction_review_contract', {}).get('review_status') or '檢討資料待接')}</p></details>
            </article>
            """)
    if not rows:
        rows.append('<article class="status-card warn" data-market="US"><h3>正式美股資料尚未產生</h3><p>尚未找到 live production US runtime artifact；不會回退到台股資料，也不會渲染 validation fixture。</p></article>')
    return "\n".join(rows)

def base_css() -> str:
    return """
    body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8f9;color:#17262c;line-height:1.55}
    header,.hero{background:#0f2c33;color:white;padding:24px 18px}.wrap{max-width:1120px;margin:0 auto;padding:18px}.nav{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.nav a,.btn{display:inline-block;background:#fff;color:#0f2c33;text-decoration:none;border-radius:8px;padding:10px 12px;font-weight:800;border:1px solid #cbd8dc}
    """ + SHARED_NAVIGATION_CSS + """
    .section{background:white;border:1px solid #dce5e8;border-radius:10px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.stock-card,.status-card{background:#fff;border:1px solid #d9e4e7;border-radius:10px;padding:14px}.card-kicker{font-weight:800;color:#35606b;font-size:13px}h1,h2,h3{margin:0 0 10px}dl{display:grid;gap:8px}dt{font-weight:800;color:#51666d}dd{margin:0}.badge{display:inline-block;border-radius:999px;padding:6px 10px;background:#e8f5e9;color:#225d28;font-weight:800}.warn{background:#fff9e8}.market-choice{display:block;text-decoration:none;color:#17262c}.market-choice h2{color:#0f5368}@media(max-width:640px){.wrap{padding:12px}.grid{grid-template-columns:1fr}.nav a{width:100%;box-sizing:border-box}}
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
    <section class="section"><h2>Runtime Status</h2><p>Dashboard 顯示完整內容；Email 顯示完整摘要；LINE 僅作短提醒與入口。舊四時段網址保留為台股相容入口。</p></section>
    </main></body></html>\n"""

def render_tw_page(source_html: str | None = None) -> str:
    body = source_html if source_html is not None else (TW_TEMPLATE.read_text(encoding="utf-8") if TW_TEMPLATE.exists() else "<p>台股 Dashboard 資料待接</p>")
    nav = shared_market_navigation("TW", "台股 AI 決策儀表板", "TW 專用頁：07:00 / 13:05 / 13:35 / 15:00。美股內容不在此頁渲染。")
    dual_strategy = """<div class="wrap section" id="ai-dev-173-tw-dual-strategy"><h2>中長期量化策略</h2><p>沿用既有 TW Research / Position scoring、評等、動作與 prediction lifecycle；不由 Daily Tactical 覆寫。</p><p>策略隔離：research_position 與 daily_tactical 分開顯示、分開檢討，不互相覆蓋。</p></div>""" + render_tw_tactical_cards()
    shared_style = f'<style id="shared-market-navigation-style">{SHARED_NAVIGATION_CSS}</style>'
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
    <section class="section"><h2>美股 Runtime Summary</h2><p>US enabled stock count：{count}</p><p>最新更新：{html.escape(latest)}</p><p>資料來源：工作表2 / live production US runtime artifacts；US Dashboard 不回退到台股資料，也不渲染 validation fixture。</p></section>
    <section class="section"><h2>Market Summary</h2><p>SPY / QQQ / VIX / sector context feeds the US research score as Tier 2 market reference.</p></section>
    <section class="section"><h2>Research / Position Strategy</h2><p>US Research preserves technical, SEC, fundamentals, earnings/guidance, official events, market context, and us_research_factor_v1 evidence for days-to-months positioning.</p></section>
    <section class="section"><h2>Daily Tactical Strategy</h2><p>US Daily Tactical uses gap, momentum, relative volume, trend, volatility, benchmark/sector context, earnings/event risk and deterministic entry/stop/target levels for current/next session and 1-5 trading days.</p></section>
    <section class="section"><h2>Financial Quality</h2><p>Revenue, margins, cash flow, leverage and missing-data quality are shown per stock when available.</p></section>
    <section class="section"><h2>Earnings / Guidance</h2><p>Company-reported actuals, company guidance, and third-party estimates are separated. Missing verified guidance stays unavailable.</p></section>
    <section class="section"><h2>SEC / Official Events</h2><p>SEC EDGAR filings and company IR/newsroom metadata are Tier 1 official evidence. yfinance remains reference data.</p></section>
    <section class="section"><h2>Material News & Bilingual Reading</h2><p>Headline metadata is classified, deduplicated, and displayed with Traditional Chinese learning support. No full articles are stored.</p></section>
    <section class="section"><h2>Prediction / Review</h2><p>Predictions are deterministic and event-adjusted; reviews attribute misses to technical, market, news, official-event and data-quality causes when data exists.</p></section>
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
        path.write_text(pages[key], encoding="utf-8")
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
