"""Multi-window user-facing report formatter."""
from __future__ import annotations
from typing import Any
import json
from pathlib import Path
from app.dashboard.dashboard_url_registry import get_tw_dashboard_url
from app.dashboard.decision_presentation import decision_email_block_v2, decision_line_summary_v2, decision_presentation_v2
from .report_sections import base_sections, normalize_stock_cards, review_state_cards
from .window_context import ReportWindowContext, get_window_context
from .window_report_contract import get_window_report_contract
from .decision_intelligence_v4 import compact_summary, delivery_summary_lines, project_decision_intelligence_v4
STATUS_MARK = "🟡"
PREDICTION_PENDING_REASON = "資料待接：尚未找到正式 prediction runtime artifact，不產生假預測。"
PRE_OPEN_PREDICTION_FIELDS = [
    "今日最高價預測", "今日最低價預測", "隔天最高價預測", "隔天最低價預測",
    "未來 1 個月走勢", "未來 3 個月走勢", "信心分數", "主要依據",
]
DASHBOARD_URL_FALLBACK = get_tw_dashboard_url()
REPO_ROOT = Path(__file__).resolve().parents[2]
TW_DAILY_TACTICAL_RUNTIME = REPO_ROOT / "artifacts/runtime/tw_daily_tactical/tw_daily_tactical_latest.json"

def _load_tw_tactical_runtime() -> dict[str, Any] | None:
    try:
        data = json.loads(TW_DAILY_TACTICAL_RUNTIME.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("market") != "TW" or data.get("strategy_type") != "daily_tactical":
        return None
    return data

def _tw_presentations() -> list[dict[str, Any]]:
    runtime = _load_tw_tactical_runtime()
    if not runtime:
        return []
    return [decision_presentation_v2("TW", card) for card in runtime.get("cards", []) if isinstance(card, dict)]

def _tw_tactical_email_body() -> str:
    presentations = _tw_presentations()
    if not presentations:
        return "TW Daily Tactical runtime artifact 尚未產生；不會用 Research 或 US 資料 fallback。"
    lines = ["Decision Presentation V3", "", "Research / Daily Tactical / Prediction"]
    for item in presentations[:9]:
        lines.extend(["", decision_email_block_v2(item)])
    return "\n".join(lines)

def _tw_tactical_line_summary(dashboard_url: str | None = None) -> str:
    presentations = _tw_presentations()
    if not presentations:
        return "Daily Tactical：資料待接"
    return decision_line_summary_v2("台股", presentations, dashboard_url or DASHBOARD_URL_FALLBACK)
def stock_card_title(stock_id: str, stock_name: str, context: ReportWindowContext, marker: str = STATUS_MARK) -> str:
    return f"【{stock_id} {stock_name}】{context.display_label} {marker}"
def format_stock_card(card: dict[str, Any], context: ReportWindowContext) -> dict[str, Any]:
    return {"title": stock_card_title(card["stock_id"], card["stock_name"], context), "stock_id": card["stock_id"], "stock_name": card["stock_name"], "signal": card["signal"], "summary": card["summary"], "advisory_only": True}
def prediction_field_blocks(context: ReportWindowContext) -> list[dict[str, Any]]:
    if context.scheduler_window != "pre_open_0700":
        return []
    return [{"label": label, "value": "資料待接", "reason": PREDICTION_PENDING_REASON, "fabricated": False} for label in PRE_OPEN_PREDICTION_FIELDS]
def contract_sections(context: ReportWindowContext) -> list[dict[str, str]]:
    contract = get_window_report_contract("TW", context.scheduler_window)
    rows = [{"heading": contract.title, "body": contract.primary_question}]
    for section in contract.email_sections:
        rows.append({"heading": section, "body": f"{contract.title} 本段聚焦 {section}，不重播其他時段完整報告。"})
    return rows

def strategy_v2_sections(context: ReportWindowContext) -> list[dict[str, str]]:
    if context.scheduler_window == "pre_open_0700":
        return [*contract_sections(context), {"heading": "每日短期操作策略", "body": _tw_tactical_email_body()}]
    return contract_sections(context)
def line_notification_text(
    context: ReportWindowContext,
    dashboard_url: str,
    projection: dict[str, Any] | None = None,
    review_payload: dict[str, Any] | None = None,
) -> str:
    contract = get_window_report_contract("TW", context.scheduler_window)
    parts = [f"【Stock AI】{contract.title}已更新"]
    if projection:
        parts.extend(delivery_summary_lines(projection, review_payload=review_payload))
    else:
        parts.append("批次摘要：資料待接，待正式 artifact 完成後更新")
    if context.scheduler_window == "pre_open_0700":
        extra = _tw_tactical_line_summary(dashboard_url)
        if extra:
            parts.append(extra)
            return "\n".join(parts)
    parts.extend(["Dashboard：", dashboard_url, "僅供研究參考，非交易指令。"] )
    return "\n".join(parts)
def render_markdown_report(user_report: dict[str, Any]) -> str:
    lines = [f"# {user_report['title']}", "", str(user_report.get("subtitle", "")), "", str(user_report.get("summary", "")), ""]
    if user_report.get("decision_intelligence_v4"):
        projection = user_report["decision_intelligence_v4"]
        lines.extend(["## Decision Intelligence V4", compact_summary(projection, "email"), "", "內容範圍：" + "、".join(projection["section_inventory"]), ""])
    for section in user_report.get("sections", []):
        lines.extend([f"## {section.get('heading')}", str(section.get("body", "")), ""])
    if user_report.get("prediction_fields"):
        lines.append("## 每日股價預測欄位")
        for field in user_report["prediction_fields"]:
            lines.append(f"- {field['label']}：{field['value']}（{field['reason']}）")
        lines.append("")
    for card in user_report.get("stock_cards", []):
        lines.extend([f"## {card.get('title')}", str(card.get("summary", "")), ""])
    for card in user_report.get("review_cards", []):
        lines.extend([f"## {card.get('title')}", str(card.get("summary", "")), ""])
    for warning in user_report.get("warnings", []):
        lines.append(f"- {warning}")
    if user_report.get("dashboard_url"):
        lines.extend(["", f"Dashboard: {user_report['dashboard_url']}"])
    lines.extend(["", "advisory_only: true"])
    return "\n".join(lines).strip() + "\n"
def build_channel_reports(context: ReportWindowContext, user_report: dict[str, Any], dashboard_url: str | None) -> dict[str, Any]:
    url = dashboard_url or DASHBOARD_URL_FALLBACK
    contract = get_window_report_contract("TW", context.scheduler_window)
    email_sections = list(contract.email_sections)
    return {
        "line": {"channel": "line", "mode": "link_only_notification", "line_summary_required": True, "full_report": False, "dashboard_url": url, "text": line_notification_text(context, url, user_report.get("decision_intelligence_v4")), "semantic_contract": "seven_window_decision_intelligence_v4", "raw_logs_included": False, "notification_sent": False},
        "email": {"channel": "email", "mode": "full_report", "email_full_report_required": True, "dashboard_url": url, "sections": email_sections, "summary": compact_summary(user_report["decision_intelligence_v4"], "email"), "semantic_contract": "seven_window_decision_intelligence_v4", "text": user_report.get("rendered_text", ""), "notification_sent": False},
        "dashboard": {"channel": "dashboard", "mode": "window_specific_contract", "dashboard_full_state_required": True, "dashboard_url": url, "sections": list(contract.dashboard_sections), "semantic_contract": "seven_window_decision_intelligence_v4", "published_by_formatter": False},
    }
def build_user_facing_report(context: ReportWindowContext, content_state: str, sanitized_text: str, stock_cards: list[dict[str, Any]] | None = None, dashboard_url: str | None = None) -> dict[str, Any]:
    summary = sanitized_text.strip() or context.primary_purpose
    warnings: list[str] = []
    if content_state in {"prediction_review_pending", "prediction_review_insufficient_data"}:
        summary = "今日預測檢討資料尚不足。部分 actual outcome 尚未完成，目前顯示盤後摘要與待檢討狀態。"
        warnings.append("prediction review 尚未完整，不應視為完整績效檢討。")
    if content_state == "no_fresh_artifact": warnings.append("尚未找到今日新鮮 delivery artifact。")
    if content_state == "pipeline_timed_out": warnings.append("pipeline 已逾時，僅顯示診斷摘要。")
    normalized = normalize_stock_cards(stock_cards)
    show_stock_cards = content_state in {"stock_analysis_reports_available", "partial", "prediction_review_pending", "prediction_review_insufficient_data"} and context.scheduler_window != "prediction_review_1500"
    sections = [*strategy_v2_sections(context), *base_sections(context.display_label, content_state, summary)]
    user_report = {
        "title": get_window_report_contract("TW", context.scheduler_window).title,
        "subtitle": get_window_report_contract("TW", context.scheduler_window).primary_question,
        "summary": summary,
        "sections": sections,
        "prediction_fields": prediction_field_blocks(context),
        "stock_cards": [format_stock_card(card, context) for card in normalized] if show_stock_cards else [],
        "review_cards": review_state_cards(content_state) if context.pipeline_type in {"post_close", "prediction_review"} else [],
        "warnings": warnings,
        "dashboard_url": dashboard_url or DASHBOARD_URL_FALLBACK,
        "advisory_only": True,
        "strategy_v2_aligned": True,
        "fabricated_forecast_values": False,
        "decision_intelligence_v4": project_decision_intelligence_v4("TW", context.scheduler_window, {"cards": stock_cards or []}),
    }
    user_report["rendered_text"] = render_markdown_report(user_report)
    user_report["channel_reports"] = build_channel_reports(context, user_report, dashboard_url)
    return user_report
def format_window_report(scheduler_window: str, content_state: str, sanitized_text: str, stock_cards: list[dict[str, Any]] | None = None, dashboard_url: str | None = None) -> dict[str, Any]:
    return build_user_facing_report(get_window_context(scheduler_window), content_state, sanitized_text, stock_cards, dashboard_url)
