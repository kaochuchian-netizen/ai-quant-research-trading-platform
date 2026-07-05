"""Controlled route integration artifact for the four-window dashboard preview."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "four_window_dashboard_route_integration_v1"
TASK_ID = "AI-DEV-144"
GENERATED_AT = "2026-07-05T00:00:00Z"
ROUTE_PATH = "/dashboard/decision-intelligence/four-window-preview"
SOURCE_PREVIEW_ARTIFACT = "templates/four_window_decision_intelligence_dashboard_artifact.example.json"
SOURCE_PREVIEW_HTML = "templates/four_window_decision_intelligence_dashboard_preview.example.html"
ROUTE_HTML = "templates/four_window_dashboard_route_preview.example.html"

SAFETY_POLICY = {
    "controlled_static_route": True,
    "repo_side_preview_only": True,
    "external_api_called": False,
    "secrets_read": False,
    "db_write": False,
    "scheduler_modified": False,
    "external_notification_sent": False,
    "line_email_notification_sent": False,
    "production_pipeline_executed": False,
    "python_main_executed": False,
    "trading_or_order_executed": False,
    "production_dashboard_publish_executed": False,
    "dashboard_published": False,
    "formal_delivery_behavior_changed": False,
    "direct_rating_action_confidence_impact": False,
    "production_rating_action_confidence_weight_mutated": False,
}

ROLLBACK_INSTRUCTIONS = [
    "Remove the controlled dashboard route mapping from the future dashboard router.",
    "Restore the previous dashboard preview route configuration.",
    "Keep scheduler, notification delivery, production pipeline, and DB state untouched.",
    "Re-run route integration and post-merge validators after rollback.",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_input() -> dict[str, Any]:
    return {
        "schema_version": "four_window_dashboard_route_integration_input_v1",
        "task_id": TASK_ID,
        "generated_at": GENERATED_AT,
        "route_path": ROUTE_PATH,
        "source_preview_artifact": SOURCE_PREVIEW_ARTIFACT,
        "source_preview_html": SOURCE_PREVIEW_HTML,
        "controlled_route_only": True,
        "production_publish_allowed": False,
    }


def _window_mapping(preview: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in preview.get("four_window_content_contract", []):
        rows.append(
            {
                "window_key": window.get("window_key"),
                "ui_window_id": window.get("ui_window_id"),
                "ui_display_name_zh": window.get("ui_display_name_zh"),
                "ui_display_name_en": window.get("ui_display_name_en"),
                "scheduled_time_tw": window.get("scheduled_time_tw"),
                "market_phase": window.get("market_phase"),
                "primary_purpose": window.get("primary_purpose"),
                "full_prediction_review_assigned": window.get("ui_window_id") == "prediction_review_1500",
            }
        )
    return rows


def build_artifact(payload: dict[str, Any] | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or Path.cwd()
    payload = payload or build_input()
    preview_ref = payload.get("source_preview_artifact", SOURCE_PREVIEW_ARTIFACT)
    html_ref = payload.get("source_preview_html", SOURCE_PREVIEW_HTML)
    preview = load_json(repo_root / preview_ref)
    windows = _window_mapping(preview)
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "generated_at": payload.get("generated_at", GENERATED_AT),
        "route_path": payload.get("route_path", ROUTE_PATH),
        "route_id": "four_window_decision_intelligence_preview_route",
        "route_kind": "controlled_static_dashboard_preview",
        "source_preview_artifact": preview_ref,
        "source_preview_html": html_ref,
        "route_preview_html": ROUTE_HTML,
        "four_window_mapping": windows,
        "semantic_rules": {
            "pre_open_0700_is_pre_open_forecast": True,
            "intraday_1305_is_intraday_tracking": True,
            "pre_close_1335_runtime_key_compatible": True,
            "pre_close_1335_ui_id": "close_snapshot_1335",
            "pre_close_1335_ui_label_zh": "收盤快照",
            "pre_close_1335_ui_label_en": "Close Snapshot",
            "pre_close_1335_primary_ui_must_not_be_pre_close": True,
            "full_prediction_review_window_key": "post_close_1500",
            "full_prediction_review_ui_id": "prediction_review_1500",
        },
        "route_integration_status": {
            "static_controlled_route_artifact_created": True,
            "production_dashboard_publish_executed": False,
            "dashboard_published": False,
            "external_notification_sent": False,
            "scheduler_modified": False,
            "production_pipeline_executed": False,
            "db_write": False,
        },
        "validation_gates": [
            "validate_four_window_decision_intelligence_dashboard_ui_v1",
            "validate_four_window_dashboard_preview_review_v1",
            "validate_four_window_dashboard_route_integration_v1",
            "validate_post_merge_status",
        ],
        "rollback_instructions": ROLLBACK_INSTRUCTIONS,
        "safety_policy": SAFETY_POLICY,
    }


def render_route_html(artifact: dict[str, Any], preview_html: str) -> str:
    published_at = "2026-07-05T23:27:28+08:00"
    route_path = escape(str(artifact["route_path"]))
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>四時段 AI 決策儀表板</title>
<style>
:root{{--ink:#132227;--muted:#5f6f76;--line:#d8e2e6;--ok:#e8f5ee;--warn:#fff7e5;--blue:#e9f3fb}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f7f8;color:var(--ink);line-height:1.55}}
header{{background:linear-gradient(135deg,#103640,#1d5a63);color:#fff;padding:26px 16px 22px}}
main{{max-width:1120px;margin:0 auto;padding:16px}}
h1{{font-size:clamp(28px,4vw,44px);margin:0 0 8px;letter-spacing:0}}
h2{{font-size:22px;margin:0 0 12px;letter-spacing:0}}
h3{{font-size:18px;margin:0 0 8px;letter-spacing:0}}
p{{margin:0 0 10px}} ul{{margin:8px 0 0;padding-left:20px}} li{{margin:4px 0}}
.badge-row{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}}
.badge{{display:inline-flex;align-items:center;border-radius:999px;padding:6px 10px;background:#e9f3fb;color:#123b44;font-weight:700;font-size:14px;border:1px solid rgba(18,59,68,.18)}}
.badge.warn{{background:var(--warn);color:#6e4d00}} .badge.safe{{background:var(--ok);color:#23533b}}
.card{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0;box-shadow:0 1px 0 rgba(14,39,46,.04)}}
.hero{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin-top:-12px;box-shadow:0 8px 24px rgba(14,39,46,.08)}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
.window-card{{display:flex;flex-direction:column;gap:8px;min-height:260px}}
.window-time{{font-size:28px;font-weight:800;color:#123b44}} .window-title{{font-size:24px;font-weight:800}}
.preview-note{{background:var(--blue);border:1px solid #c8dcea;border-radius:10px;padding:12px;color:#244f64}}
.source-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
.source-item{{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fbfdfe}}
details{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px;margin:14px 0}} summary{{font-weight:800;cursor:pointer}}
.debug-list{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}}
.debug-list span{{background:#f6f8f9;border:1px solid #e0e7ea;border-radius:8px;padding:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}}
@media (max-width:760px){{main{{padding:12px}}.grid,.source-grid,.debug-list{{grid-template-columns:1fr}}.window-time{{font-size:24px}}.window-title{{font-size:21px}}.hero,.card{{border-radius:10px;padding:14px}}}}
</style>
</head>
<body>
<header>
  <h1>四時段 AI 決策儀表板</h1>
  <p>盤前、盤中、收盤快照、盤後檢討</p>
  <div class="badge-row"><span class="badge warn">預覽版 / 尚未接正式即時資料</span><span class="badge safe">不通知、不下單、不改策略</span><span class="badge">更新時間 {published_at}</span></div>
</header>
<main>
<section class="hero" aria-label="Today Decision Summary">
  <h2>今日決策摘要</h2>
  <p>這個頁面用來把一天拆成四個清楚時段：開盤前先建立預測脈絡，盤中追蹤是否偏離假設，13:35 保留收盤快照，15:00 再做完整預測檢討。</p>
  <p class="preview-note">目前為預覽資料，尚未接正式 runtime data。實際上線後，這裡會顯示每檔股票的預測區間、主要依據、風險與回測檢討。非投資建議，不會觸發通知或下單。</p>
  <div class="badge-row"><span class="badge safe">controlled preview</span><span class="badge safe">no notification</span><span class="badge safe">no trading</span><span class="badge safe">no strategy weight change</span></div>
</section>
<section class="card">
  <h2>四個時段怎麼看</h2>
  <div class="grid">
    <article class="card window-card">
      <div class="window-time">07:00</div><div class="window-title">盤前預測 / Pre-open Forecast</div>
      <p><strong>用途：</strong>開盤前建立今日、次日、1M、3M 的預測脈絡。</p>
      <p><strong>使用者該看：</strong>今日偏多/偏空因素、預測區間、風險提醒。</p>
      <p><strong>預覽內容：</strong>正式資料接上後，這裡會整理市場情境、官方來源摘要、FinMind/TWSE/yfinance 輔助脈絡與失效條件。</p>
      <span class="badge">Preview sample</span>
    </article>
    <article class="card window-card">
      <div class="window-time">13:05</div><div class="window-title">盤中追蹤 / Intraday Tracking</div>
      <p><strong>用途：</strong>檢查盤中走勢是否偏離盤前假設。</p>
      <p><strong>使用者該看：</strong>價格是否接近高低點、量能、新聞/籌碼變化。</p>
      <p><strong>預覽內容：</strong>正式上線後會用盤中狀態卡提醒假設仍有效或需要提高警覺，但不做完整 prediction review。</p>
      <span class="badge">Preview sample</span>
    </article>
    <article class="card window-card">
      <div class="window-time">13:35</div><div class="window-title">收盤快照 / Close Snapshot</div>
      <p><strong>用途：</strong>接近收盤時保留當日狀態快照。</p>
      <p><strong>使用者該看：</strong>今日走勢是否符合預測、是否需納入盤後檢討。</p>
      <p><strong>預覽內容：</strong>顯示今日高低價、收盤價與方向初步命中狀態的樣式；完整檢討延後到 15:00。</p>
      <span class="badge warn">完整檢討待 15:00</span>
    </article>
    <article class="card window-card">
      <div class="window-time">15:00</div><div class="window-title">盤後檢討 / Prediction Review</div>
      <p><strong>用途：</strong>完整檢討預測品質。</p>
      <p><strong>使用者該看：</strong>預測命中率、偏差、錯誤原因、明日改進。</p>
      <p><strong>預覽內容：</strong>正式資料接上後，這裡會呈現 forecast vs actual、7 日 rolling evaluation、factor effectiveness 與 confidence calibration。</p>
      <span class="badge safe">Full prediction review</span>
    </article>
  </div>
</section>
<section class="card">
  <h2>資料可信度與證據來源</h2>
  <div class="source-grid">
    <div class="source-item"><h3>官方公告 / 財報 / 法說會</h3><p>高可信，可作為核心證據。未來接入 MOPS、公司公告、月營收與 IR 資料時會放在這一層。</p></div>
    <div class="source-item"><h3>產業供應鏈 / 同業脈絡</h3><p>中可信，作為背景脈絡，協助理解同業與上下游影響。</p></div>
    <div class="source-item"><h3>Google News / yfinance / broker target</h3><p>輔助資訊，不直接改變評等、行動或信心分數；也不能取代官方來源。</p></div>
    <div class="source-item"><h3>Gemini / AI summary</h3><p>解釋層，不是原始證據。它只能協助整理，不可當作來源本身。</p></div>
  </div>
</section>
<section class="card">
  <h2>正式上線後會補上的內容</h2>
  <ul>
    <li>每檔股票的預測區間、主要依據、風險情境與失效條件。</li>
    <li>盤中是否偏離盤前假設，以及接近高低點時的提醒式狀態。</li>
    <li>13:35 的當日快照與 15:00 的完整 forecast vs actual 檢討。</li>
    <li>回測命中率、factor effectiveness、confidence calibration 與人工 review 建議。</li>
  </ul>
</section>
<details>
  <summary>技術檢查 / Debug</summary>
  <p>以下資訊保留給維運檢查，不是主要使用者閱讀區。</p>
  <div class="debug-list"><span>route={route_path}</span><span>runtime keys: pre_open_0700 / intraday_1305 / pre_close_1335 / post_close_1500</span><span>ui concept: close_snapshot_1335 / prediction_review_1500</span><span>production_dashboard_publish_executed=false</span><span>no notification</span><span>no scheduler change</span><span>no DB write</span><span>no production pipeline</span><span>no trading</span><span>no rating/action/confidence/weight mutation</span></div>
</details>
</main>
</body>
</html>
"""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
