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
US_RUNTIME_FILES = [
    REPO_ROOT / "artifacts/runtime/us_stock/us_stock_pre_market_latest.json",
    REPO_ROOT / "artifacts/runtime/us_stock/us_stock_intraday_latest.json",
    REPO_ROOT / "artifacts/runtime/us_stock/us_stock_post_close_review_latest.json",
]

US_WINDOWS = {
    "us_pre_market_2000": "美股盤前 20:00",
    "us_intraday_2300": "美股盤中 23:00",
    "us_post_close_review_0630": "美股檢討 06:30",
}

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

def _load_us_artifacts() -> list[dict[str, Any]]:
    artifacts = []
    for path in US_RUNTIME_FILES:
        data = read_json(path)
        if data and data.get("market") == "US":
            data["_source_path"] = str(path.relative_to(REPO_ROOT))
            artifacts.append(data)
    if artifacts:
        return artifacts
    try:
        from app.us_stock.batch import build_us_stock_batch_artifact, us_stock_batch_input_example
        payload = us_stock_batch_input_example()
        built = build_us_stock_batch_artifact(payload, window="us_pre_market_2000")
        built["artifact_type"] = "us_stock_dashboard_fixture_no_send"
        built["runtime_mode"] = "offline_fixture"
        built["runtime_watchlist_validation"] = {
            "mode": "offline_fixture",
            "source_sheet": "工作表2",
            "enabled_stock_count": len([r for r in payload.get("sample_us_watchlist_rows", []) if r.get("enabled", True)]),
            "private_values_printed": False,
            "credentials_read": False,
        }
        return [built]
    except Exception:
        return []

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
                <div><dt>交易所</dt><dd>{_escape(_exchange_for(artifact, symbol))}</dd></div>
                <div><dt>USD 價格</dt><dd>{_escape(card.get('price'))}</dd></div>
                <div><dt>評等 / 動作 / 信心</dt><dd>{_escape(card.get('rating'))} / {_escape(card.get('action'))} / {_escape(card.get('confidence'))}</dd></div>
                <div><dt>本次預測區間</dt><dd>{_escape(card.get('session_predicted_high_low'))}</dd></div>
                <div><dt>下次預測區間</dt><dd>{_escape(card.get('next_session_predicted_high_low'))}</dd></div>
                <div><dt>1M / 3M 趨勢</dt><dd>{_escape(card.get('one_month_trend'))} / {_escape(card.get('three_month_trend'))}</dd></div>
                <div><dt>資料狀態</dt><dd>{_escape(card.get('latest_status'))}</dd></div>
              </dl>
              <section class="news-block"><h4>Bilingual News / 雙語新聞</h4><p><strong>EN:</strong> {_escape(news.get('english_headline'))}</p><p><strong>中:</strong> {_escape(news.get('chinese_translation'))}</p><p>{_escape(news.get('investment_reading'))}</p></section>
              <section class="review-block"><h4>Prediction Review</h4><p>{_escape(artifact.get('prediction_review_contract', {}).get('review_status') or '檢討資料待接')}</p></section>
            </article>
            """)
    if not rows:
        rows.append("<article class='status-card warn'><h3>美股資料待接</h3><p>尚未找到可渲染的 US runtime artifact；不會回退到台股資料。</p></article>")
    return "\n".join(rows)

def base_css() -> str:
    return """
    body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8f9;color:#17262c;line-height:1.55}
    header,.hero{background:#0f2c33;color:white;padding:24px 18px}.wrap{max-width:1120px;margin:0 auto;padding:18px}.nav{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.nav a,.btn{display:inline-block;background:#fff;color:#0f2c33;text-decoration:none;border-radius:8px;padding:10px 12px;font-weight:800;border:1px solid #cbd8dc}.section{background:white;border:1px solid #dce5e8;border-radius:10px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.stock-card,.status-card{background:#fff;border:1px solid #d9e4e7;border-radius:10px;padding:14px}.card-kicker{font-weight:800;color:#35606b;font-size:13px}h1,h2,h3{margin:0 0 10px}dl{display:grid;gap:8px}dt{font-weight:800;color:#51666d}dd{margin:0}.badge{display:inline-block;border-radius:999px;padding:6px 10px;background:#e8f5e9;color:#225d28;font-weight:800}.warn{background:#fff9e8}.market-choice{display:block;text-decoration:none;color:#17262c}.market-choice h2{color:#0f5368}@media(max-width:640px){.wrap{padding:12px}.grid{grid-template-columns:1fr}.nav a{width:100%;box-sizing:border-box}}
    """

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
    nav = f"""<div class="wrap section" id="ai-dev-170-tw-nav"><h1>台股 AI 決策儀表板</h1><nav class="nav"><a href="/stock-ai-dashboard/index.html">回到總覽</a><a href="/stock-ai-dashboard/dashboard/tw/index.html">台股 Dashboard</a><a href="/stock-ai-dashboard/dashboard/us/index.html">美股 Dashboard</a></nav><p>TW 專用頁：07:00 / 13:05 / 13:35 / 15:00。美股內容不在此頁渲染。</p></div>"""
    if "</body>" in body:
        body = body.replace("</body>", nav + "\n</body>")
    else:
        body += nav
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
    <body><header><div class="wrap"><h1>美股 AI 決策儀表板</h1><p>美股盤前 20:00｜美股盤中 23:00｜美股檢討 06:30</p><nav class="nav"><a href="/stock-ai-dashboard/index.html">回到總覽</a><a href="/stock-ai-dashboard/dashboard/tw/index.html">台股 Dashboard</a><a href="/stock-ai-dashboard/dashboard/us/index.html">美股 Dashboard</a></nav></div></header><main class="wrap">
    <!-- AI-DEV-170-US-DASHBOARD-START -->
    <section class="section"><h2>美股 Runtime Summary</h2><p>US enabled stock count：{count}</p><p>最新更新：{html.escape(latest)}</p><p>資料來源：工作表2 / US runtime artifacts；US Dashboard 不回退到台股資料。</p></section>
    <section class="section"><h2>美股盤前 20:00</h2><p>盤前預測、評等、風險與雙語新聞。</p></section>
    <section class="section"><h2>美股盤中 23:00</h2><p>盤中狀態、區間偏離與評等有效性。</p></section>
    <section class="section"><h2>美股檢討 06:30</h2><p>盤後 prediction review、區間命中與校準狀態。</p></section>
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
