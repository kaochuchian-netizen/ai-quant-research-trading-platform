"""Deterministic four-window Decision Intelligence dashboard preview builder."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "four_window_decision_intelligence_dashboard_ui_v1"
TASK_ID = "AI-DEV-142"
GENERATED_AT = "2026-07-05T00:00:00Z"
SYMBOL = "2330"
MARKET = "TW"

WINDOWS: list[dict[str, Any]] = [
    {
        "window_key": "pre_open_0700",
        "ui_window_id": "pre_open_0700",
        "ui_display_name_zh": "盤前預測",
        "ui_display_name_en": "Pre-open Forecast",
        "scheduled_time_tw": "07:00",
        "market_phase": "pre_open",
        "primary_purpose": "Prepare same-day, next-day, one-month, and three-month forecast context before the market opens.",
        "allowed_sections": [
            "today_market_context",
            "same_day_high_low_forecast_context",
            "next_day_high_low_forecast_context",
            "one_month_trend_context",
            "three_month_trend_context",
            "market_regime",
            "official_source_admission_summary",
            "source_credibility_cards",
            "formal_integration_cards",
            "risk_scenario_invalidation_notes",
            "advisory_only_badge",
            "recommendation_only_badge",
        ],
        "disallowed_sections": ["full_prediction_review", "external_notification_send", "production_mutation"],
        "timing_alignment_notes": "Forecast-oriented context before market open; no delivery action is executed.",
    },
    {
        "window_key": "intraday_1305",
        "ui_window_id": "intraday_1305",
        "ui_display_name_zh": "盤中追蹤",
        "ui_display_name_en": "Intraday Tracking",
        "scheduled_time_tw": "13:05",
        "market_phase": "intraday_tracking",
        "primary_purpose": "Track whether current price action remains aligned with the pre-open scenario.",
        "allowed_sections": [
            "current_price_vs_pre_open_range_placeholder",
            "near_same_day_high_low_status",
            "pre_open_scenario_validity",
            "volume_chip_adr_external_proxy_support",
            "intraday_status_card",
            "invalidation_warning",
            "source_credibility_badges",
        ],
        "disallowed_sections": ["full_prediction_review", "seven_day_rolling_review", "external_notification_send", "production_mutation"],
        "timing_alignment_notes": "Tracking window only; it does not run full prediction review.",
    },
    {
        "window_key": "pre_close_1335",
        "ui_window_id": "close_snapshot_1335",
        "ui_display_name_zh": "收盤快照",
        "ui_display_name_en": "Close Snapshot",
        "scheduled_time_tw": "13:35",
        "market_phase": "close_snapshot",
        "primary_purpose": "Capture preliminary close snapshot quality signals while preserving the legacy runtime key.",
        "allowed_sections": [
            "actual_high_low_placeholder",
            "close_price_placeholder",
            "same_day_direction_preliminary_hit_status",
            "same_day_range_preliminary_hit_status",
            "abnormal_stock_factor_hint",
            "pre_open_forecast_preliminary_gap",
            "pending_full_review_badge",
        ],
        "disallowed_sections": ["full_prediction_review", "external_notification_send", "production_mutation"],
        "timing_alignment_notes": "Runtime key remains pre_close_1335 for compatibility; UI label is close_snapshot_1335 / 收盤快照.",
    },
    {
        "window_key": "post_close_1500",
        "ui_window_id": "prediction_review_1500",
        "ui_display_name_zh": "盤後檢討",
        "ui_display_name_en": "Prediction Review",
        "scheduled_time_tw": "15:00",
        "market_phase": "post_close_review",
        "primary_purpose": "Review forecast versus actuals and summarize decision quality feedback after close.",
        "allowed_sections": [
            "forecast_vs_actual",
            "high_low_range_hit",
            "direction_hit",
            "major_error_sources",
            "seven_day_rolling_evaluation",
            "factor_effectiveness",
            "confidence_calibration",
            "source_error_attribution",
            "decision_quality_feedback_recommendations",
            "human_review_required_for_any_mutation_badge",
            "recommendation_only_badge",
        ],
        "disallowed_sections": ["external_notification_send", "production_mutation"],
        "timing_alignment_notes": "Full review window; recommendations remain advisory and require human review for any mutation.",
    },
]

COMMON_UI_SECTIONS = [
    "Executive Decision Intelligence Summary",
    "Official Source Admission Summary",
    "Source Credibility Cards",
    "Formal Integration Cards",
    "Evidence Trace Summary",
    "Factor Rationale Cards",
    "Warning / Exclusion Cards",
    "Metadata-only Badges",
    "Advisory-only Badges",
    "Feedback Recommendation Cards",
    "Mutation Policy Summary",
]

SOURCE_POLICY = {
    "official_core_evidence_families": [
        "MOPS / 公司公告",
        "財報 / 月營收",
        "法說會 / IR",
    ],
    "contextual_evidence_families": ["industry supply chain", "peer company context"],
    "formal_integrations": ["FinMind", "TWSE", "yfinance/Yahoo"],
    "policy_badges": [
        "FinMind cannot replace official sources",
        "yfinance/Yahoo cannot replace official sources",
        "Google News RSS cannot be core forecast evidence",
        "broker target / analyst rating metadata-only",
        "Gemini / AI-generated analysis is not original evidence",
    ],
}

MUTATION_POLICY = {
    "recommendation_only": True,
    "human_review_required_for_any_mutation": True,
    "direct_rating_action_confidence_impact": False,
    "production_weight_changed": False,
    "production_confidence_changed": False,
    "production_rating_action_changed": False,
    "production_pipeline_modified": False,
    "delivery_behavior_modified": False,
}

SAFETY_POLICY = {
    "external_api_called": False,
    "secrets_read": False,
    "db_write": False,
    "scheduler_modified": False,
    "line_email_notification_sent": False,
    "production_pipeline_executed": False,
    "python_main_executed": False,
    "trading_or_order_executed": False,
    "dashboard_preview_only": True,
    "dashboard_published": False,
    "production_dashboard_runtime_modified": False,
}

DELIVERY_POLICY = {
    "line_allowed_for_summary_only": True,
    "email_allowed_for_full_report": True,
    "dashboard_allowed_for_full_report_and_drilldown": True,
    "delivery_executed": False,
    "dashboard_published": False,
    "external_notification_sent": False,
}

ARTIFACT_REFS = {
    "prediction_context": "templates/prediction_context_artifact.example.json",
    "explainability": "templates/unified_explainability_artifact.example.json",
    "report_assembly": "templates/context_based_report_assembly_artifact.example.json",
    "dashboard_decision_intelligence": "templates/dashboard_decision_intelligence_artifact.example.json",
    "decision_quality_feedback": "templates/decision_quality_feedback_artifact.example.json",
    "official_primary_source_admission": "templates/official_primary_source_context_admission_artifact.example.json",
}


def build_input() -> dict[str, Any]:
    return {
        "schema_version": "four_window_decision_intelligence_dashboard_input_v1",
        "task_id": TASK_ID,
        "generated_at": GENERATED_AT,
        "symbol": SYMBOL,
        "market": MARKET,
        "artifact_refs": ARTIFACT_REFS,
        "requested_windows": [window["window_key"] for window in WINDOWS],
        "preview_only": True,
    }


def _window_cards(window: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    for index, section in enumerate(window["allowed_sections"], start=1):
        cards.append(
            {
                "card_id": f"{window['ui_window_id']}_{section}",
                "title": section.replace("_", " ").title(),
                "summary": f"Deterministic placeholder for {window['ui_display_name_en']} / {window['ui_display_name_zh']}.",
                "sort_order": index,
                "source_refs": list(ARTIFACT_REFS.values()),
                "advisory_only": True,
                "recommendation_only": True,
            }
        )
    return cards


def build_artifact(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or build_input()
    windows = []
    for window in WINDOWS:
        item = dict(window)
        item["source_policy"] = SOURCE_POLICY
        item["decision_intelligence_artifact_refs"] = ARTIFACT_REFS
        item["delivery_channel_policy"] = DELIVERY_POLICY
        item["dashboard_cards"] = _window_cards(window)
        item["common_ui_sections"] = COMMON_UI_SECTIONS
        windows.append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "generated_at": payload.get("generated_at", GENERATED_AT),
        "symbol": payload.get("symbol", SYMBOL),
        "market": payload.get("market", MARKET),
        "dashboard_title": "Four-Window Decision Intelligence Dashboard",
        "dashboard_subtitle": "V10 decision context, evidence, report assembly, dashboard drill-down, feedback, and official-source admission preview.",
        "artifact_refs": ARTIFACT_REFS,
        "four_window_content_contract": windows,
        "common_decision_intelligence_sections": COMMON_UI_SECTIONS,
        "source_policy": SOURCE_POLICY,
        "mutation_policy": MUTATION_POLICY,
        "delivery_policy": DELIVERY_POLICY,
        "safety_policy": SAFETY_POLICY,
        "preview_outputs": {
            "json_path": "templates/four_window_decision_intelligence_dashboard_artifact.example.json",
            "html_path": "templates/four_window_decision_intelligence_dashboard_preview.example.html",
            "published_preview": False,
        },
    }


def render_html(artifact: dict[str, Any]) -> str:
    tabs = []
    sections = []
    for window in artifact["four_window_content_contract"]:
        anchor = escape(window["ui_window_id"])
        tabs.append(f'<a href="#{anchor}">{escape(window["scheduled_time_tw"])} {escape(window["ui_display_name_zh"])}</a>')
        cards = []
        for card in window["dashboard_cards"]:
            cards.append(
                "<article class=\"card\">"
                f"<h3>{escape(card['title'])}</h3>"
                f"<p>{escape(card['summary'])}</p>"
                "<div class=\"badges\"><span>advisory only</span><span>recommendation only</span></div>"
                "</article>"
            )
        sections.append(
            f"<section id=\"{anchor}\" class=\"window\">"
            f"<p class=\"time\">{escape(window['scheduled_time_tw'])}</p>"
            f"<h2>{escape(window['ui_display_name_zh'])} · {escape(window['ui_display_name_en'])}</h2>"
            f"<p class=\"purpose\">{escape(window['primary_purpose'])}</p>"
            f"<p class=\"note\">{escape(window['timing_alignment_notes'])}</p>"
            f"<div class=\"grid\">{''.join(cards)}</div>"
            "</section>"
        )
    common = "".join(f"<li>{escape(section)}</li>" for section in artifact["common_decision_intelligence_sections"])
    source_badges = "".join(f"<span>{escape(badge)}</span>" for badge in artifact["source_policy"]["policy_badges"])
    mutation = artifact["mutation_policy"]
    mutation_badges = "".join(f"<span>{escape(key)}={str(value).lower()}</span>" for key, value in mutation.items())
    return f"""<!doctype html>
<html lang=\"zh-Hant\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{escape(artifact['dashboard_title'])}</title>
<style>
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f6f7;color:#162127;line-height:1.45}}
header{{background:#11343b;color:#fff;padding:22px 16px}}
main{{max-width:1080px;margin:0 auto;padding:14px}}
nav{{display:grid;grid-template-columns:repeat(auto-fit,minmax(138px,1fr));gap:8px;margin:12px 0}}
nav a{{background:#fff;border:1px solid #d9e2e5;border-radius:8px;padding:10px;text-decoration:none;color:#17343c;font-weight:700}}
.window{{background:#fff;border:1px solid #d9e2e5;border-radius:10px;padding:14px;margin:14px 0}}
.time{{font-weight:800;color:#2d6b79;margin:0 0 4px}}
h1{{font-size:1.45rem;margin:0 0 8px}} h2{{font-size:1.22rem;margin:0 0 6px}} h3{{font-size:1rem;margin:0 0 6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}}
.card{{border:1px solid #dfe7ea;border-radius:8px;padding:10px;background:#fbfcfc}}
.badges,.policy{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
.badges span,.policy span{{background:#eaf2f4;border:1px solid #cbdde2;border-radius:999px;padding:4px 8px;font-size:.82rem}}
.note,.purpose,.safe{{color:#53666e}}
.debug{{border-top:1px solid #d9e2e5;margin-top:18px;padding-top:12px}}
@media (max-width:560px){{main{{padding:10px}}.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header><h1>{escape(artifact['dashboard_title'])}</h1><p>Static preview only. No notification, no production pipeline, no trading, no delivery execution.</p></header>
<main>
<nav>{''.join(tabs)}</nav>
<section class=\"window\"><h2>Executive Decision Intelligence Summary</h2><ul>{common}</ul><div class=\"policy\">{source_badges}</div><div class=\"policy\">{mutation_badges}</div></section>
{''.join(sections)}
<section class=\"debug\"><h2>Preview Diagnostics</h2><p class=\"safe\">Artifact references are deterministic repo templates. Raw JSON is intentionally kept out of the main view.</p></section>
</main>
</body>
</html>
"""


def write_json(path: Path, payload: dict[str, Any], pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True) + "\n", encoding="utf-8")
