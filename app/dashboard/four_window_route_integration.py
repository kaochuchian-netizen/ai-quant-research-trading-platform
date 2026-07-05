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
    rows = []
    for row in artifact["four_window_mapping"]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(row['scheduled_time_tw']))}</td>"
            f"<td><code>{escape(str(row['window_key']))}</code></td>"
            f"<td><code>{escape(str(row['ui_window_id']))}</code></td>"
            f"<td>{escape(str(row['ui_display_name_zh']))} / {escape(str(row['ui_display_name_en']))}</td>"
            f"<td>{escape(str(row['market_phase']))}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang=\"zh-Hant\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Controlled Four-Window Dashboard Route Preview</title>
<style>
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f6f7;color:#162127;line-height:1.45}}
header{{background:#0f333b;color:#fff;padding:22px 16px}}
main{{max-width:1120px;margin:0 auto;padding:14px}}
.card{{background:#fff;border:1px solid #d9e2e5;border-radius:10px;padding:14px;margin:14px 0}}
table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{border-bottom:1px solid #dce5e8;padding:9px;text-align:left;vertical-align:top}}th{{background:#edf3f5}}
.badges{{display:flex;flex-wrap:wrap;gap:6px}}.badges span{{background:#eaf2f4;border:1px solid #cbdde2;border-radius:999px;padding:4px 8px;font-size:.84rem}}
iframe{{width:100%;height:820px;border:1px solid #d9e2e5;border-radius:10px;background:#fff}}
@media (max-width:680px){{table,thead,tbody,tr,td,th{{display:block}}th{{display:none}}td{{padding:8px 10px}}iframe{{height:900px}}}}
</style>
</head>
<body>
<header><h1>Controlled Four-Window Dashboard Route Preview</h1><p>Route path: <code>{escape(artifact['route_path'])}</code>. Static preview only; production publish is false.</p></header>
<main>
<section class=\"card\"><h2>Route Contract</h2><div class=\"badges\"><span>production_dashboard_publish_executed=false</span><span>external_notification_sent=false</span><span>scheduler_modified=false</span><span>production_pipeline_executed=false</span><span>db_write=false</span></div></section>
<section class=\"card\"><h2>Four-Window Mapping</h2><table><thead><tr><th>Time</th><th>Runtime Key</th><th>UI ID</th><th>Label</th><th>Phase</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section class=\"card\"><h2>13:35 Semantic Rule</h2><p><code>pre_close_1335</code> remains the runtime key, but the UI concept is <code>close_snapshot_1335</code> / 收盤快照 / Close Snapshot. Full prediction review remains at 15:00.</p></section>
<section class=\"card\"><h2>Embedded Static Preview</h2><iframe srcdoc=\"{escape(preview_html, quote=True)}\" title=\"Four-window dashboard preview\"></iframe></section>
</main>
</body>
</html>
"""


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
