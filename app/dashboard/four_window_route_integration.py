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
REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DATA = "templates/four_window_dashboard_runtime_data.example.json"

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
    runtime = load_json(REPO_ROOT / RUNTIME_DATA) if (REPO_ROOT / RUNTIME_DATA).exists() else {}
    route_path = escape(str(artifact["route_path"]))
    status_map = {"fresh": "資料正常", "partial_data": "部分缺資料", "stale": "資料過期", "missing": "尚未接資料", "preview_only": "預覽資料"}
    global_status = escape(status_map.get(str(runtime.get("global_freshness_status", "preview_only")), "預覽資料"))
    latest_ts = escape(str(runtime.get("latest_data_timestamp") or "資料待接"))
    stocks = runtime.get("stock_universe", []) if isinstance(runtime.get("stock_universe"), list) else []
    stock_rows = [s for s in stocks if isinstance(s, dict) and s.get("stock_id")]
    usable_count = len([s for s in stock_rows if s.get("data_state") == "usable"])
    missing_count = len(runtime.get("missing_data", [])) if isinstance(runtime.get("missing_data"), list) else 0
    prediction_available = "否，資料待接" if any(isinstance(p, dict) and p.get("freshness_status") == "missing" for p in runtime.get("prediction_fields", [])) else "是"
    def badge_class(status: str) -> str:
        return "safe" if status == "fresh" else "warn" if status in {"stale", "missing"} else ""
    window_cards = []
    for w in runtime.get("four_windows", []):
        if not isinstance(w, dict):
            continue
        purpose = "Full prediction review / 完整盤後檢討" if w.get("full_prediction_review") else "查看此時段的決策資料狀態"
        if w.get("window_key") == "pre_close_1335":
            purpose = "收盤快照；完整檢討待 15:00"
        window_cards.append(f'''<article class="card window-card"><div class="window-time">{escape(str(w.get("expected_time")))}</div><div class="window-title">{escape(str(w.get("display_name")))}</div><p><strong>用途：</strong>{purpose}</p><p><strong>最新資料：</strong>{escape(str(w.get("latest_available_data_timestamp") or "資料待接"))}</p><p><strong>已接區塊：</strong>{escape(", ".join(w.get("available_sections") or ["目前尚未找到可用資料"]))}</p><p><strong>缺少區塊：</strong>{escape(", ".join(w.get("missing_sections") or ["無"]))}</p><p><strong>PM 動作：</strong>{escape(str(w.get("pm_readable_action")))}</p><span class="badge {badge_class(str(w.get("freshness_status")))}">{escape(str(w.get("freshness_label")))}</span></article>''')
    stock_cards = []
    for s in stock_rows[:12]:
        stock_cards.append(f'''<div class="source-item"><h3>{escape(str(s.get("stock_id")))} {escape(str(s.get("stock_name") or ""))}</h3><p>來源：{escape(str(s.get("source_artifact_or_table")))}</p><p>更新：{escape(str(s.get("last_updated") or "missing"))}</p><span class="badge {badge_class(str(s.get("freshness_status")))}">{escape(str(s.get("freshness_label")))}</span></div>''')
    if not stock_cards:
        stock_cards.append('<div class="source-item"><h3>資料待接</h3><p>目前尚未找到可用追蹤標的資料。</p></div>')
    pred_cards = []
    for pr in runtime.get("prediction_fields", []):
        if isinstance(pr, dict):
            pred_cards.append(f'''<div class="source-item"><h3>{escape(str(pr.get("field")))}</h3><p>{escape(str(pr.get("message")))}</p><span class="badge {badge_class(str(pr.get("freshness_status")))}">{escape(str(pr.get("freshness_status")))}</span></div>''')
    fresh_cards = []
    for fc in runtime.get("freshness_checks", [])[:16]:
        if isinstance(fc, dict):
            fresh_cards.append(f'''<div class="source-item"><h3>{escape(str(fc.get("category")))} / {escape(str(fc.get("id")))}</h3><p>timestamp: {escape(str(fc.get("timestamp") or "missing"))}</p><p>max age: {escape(str(fc.get("max_age_hours")))}h</p><span class="badge {badge_class(str(fc.get("status")))}">{escape(str(fc.get("status")))}</span></div>''')
    source_cards = []
    for q in runtime.get("source_quality", []):
        if isinstance(q, dict):
            source_cards.append(f'''<div class="source-item"><h3>{escape(str(q.get("label")))}</h3><p>可信度：{escape(str(q.get("quality")))}</p><p>用途：{escape(str(q.get("allowed_usage")))}</p></div>''')
    return f'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>四時段 AI 決策儀表板</title>
<style>:root{{--ink:#132227;--line:#d8e2e6;--ok:#e8f5ee;--warn:#fff7e5;--blue:#e9f3fb}}*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f7f8;color:var(--ink);line-height:1.55}}header{{background:linear-gradient(135deg,#103640,#1d5a63);color:#fff;padding:26px 16px 22px}}main{{max-width:1120px;margin:0 auto;padding:16px}}h1{{font-size:clamp(28px,4vw,44px);margin:0 0 8px}}h2{{font-size:22px;margin:0 0 12px}}h3{{font-size:18px;margin:0 0 8px}}p{{margin:0 0 10px}}.badge-row{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}}.badge{{display:inline-flex;border-radius:999px;padding:6px 10px;background:#e9f3fb;color:#123b44;font-weight:700;font-size:14px;border:1px solid rgba(18,59,68,.18)}}.badge.warn{{background:var(--warn);color:#6e4d00}}.badge.safe{{background:var(--ok);color:#23533b}}.card{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0;box-shadow:0 1px 0 rgba(14,39,46,.04)}}.hero{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin-top:-12px;box-shadow:0 8px 24px rgba(14,39,46,.08)}}.grid,.source-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}.window-card{{display:flex;flex-direction:column;gap:8px;min-height:260px}}.window-time{{font-size:28px;font-weight:800;color:#123b44}}.window-title{{font-size:24px;font-weight:800}}.preview-note{{background:var(--blue);border:1px solid #c8dcea;border-radius:10px;padding:12px;color:#244f64}}.source-item{{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fbfdfe}}details{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px;margin:14px 0}}summary{{font-weight:800;cursor:pointer}}.debug-list{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}}.debug-list span{{background:#f6f8f9;border:1px solid #e0e7ea;border-radius:8px;padding:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}}@media (max-width:760px){{main{{padding:12px}}.grid,.source-grid,.debug-list{{grid-template-columns:1fr}}.window-time{{font-size:24px}}.window-title{{font-size:21px}}.hero,.card{{border-radius:10px;padding:14px}}}}</style></head>
<body><header><h1>四時段 AI 決策儀表板</h1><p>盤前、盤中、收盤快照、盤後檢討</p><div class="badge-row"><span class="badge warn">預覽版 / 尚未接正式即時資料</span><span class="badge">最新資料：{latest_ts}</span><span class="badge warn">{global_status}</span><span class="badge safe">不通知、不下單、不改策略</span></div></header><main>
<section class="hero"><h2>今日決策摘要</h2><p>這個頁面整合本機安全資料、freshness 狀態與四時段 Dashboard。若資料缺失或過期，會明確標示，不會產生假預測。</p><p class="preview-note">目前為預覽資料，尚未接正式 runtime data。非投資建議，不會觸發通知或下單。</p><div class="badge-row"><span class="badge">追蹤標的 {len(stock_rows)}</span><span class="badge">可用資料 {usable_count}</span><span class="badge warn">缺失/過期區塊 {missing_count}</span><span class="badge warn">預測欄位：{prediction_available}</span><span class="badge">證據資料：是，已接政策層；實際 evidence 仍需正式 runtime</span></div></section>
<section class="card"><h2>四個時段怎麼看</h2><div class="grid">{''.join(window_cards)}</div></section>
<section class="card"><h2>目前追蹤標的</h2><div class="source-grid">{''.join(stock_cards)}</div></section>
<section class="card"><h2>預測資料狀態</h2><div class="source-grid">{''.join(pred_cards)}</div></section>
<section class="card"><h2>資料新鮮度</h2><div class="source-grid">{''.join(fresh_cards)}</div></section>
<section class="card"><h2>資料可信度與證據來源 / 資料來源可信度</h2><div class="source-grid">{''.join(source_cards)}</div></section>
<details><summary>技術檢查 / Debug</summary><p>以下資訊保留給維運檢查，不是主要使用者閱讀區。</p><div class="debug-list"><span>route={route_path}</span><span>runtime keys: pre_open_0700 / intraday_1305 / pre_close_1335 / post_close_1500</span><span>ui concept: close_snapshot_1335 / prediction_review_1500</span><span>production_dashboard_publish_executed=false</span><span>no notification</span><span>no scheduler change</span><span>no DB write</span><span>no production pipeline</span><span>no trading</span><span>no rating/action/confidence/weight mutation</span><span>fabricated_market_data=false</span></div></details>
</main></body></html>'''


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
