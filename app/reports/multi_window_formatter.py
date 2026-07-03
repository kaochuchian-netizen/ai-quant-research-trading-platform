"""Multi-window user-facing report formatter."""
from __future__ import annotations
from typing import Any
from .report_sections import base_sections, normalize_stock_cards, review_state_cards
from .window_context import ReportWindowContext, get_window_context
STATUS_MARK = "🟡"
def stock_card_title(stock_id: str, stock_name: str, context: ReportWindowContext, marker: str = STATUS_MARK) -> str:
    return f"【{stock_id} {stock_name}】{context.display_label} {marker}"
def format_stock_card(card: dict[str, Any], context: ReportWindowContext) -> dict[str, Any]:
    return {"title": stock_card_title(card["stock_id"], card["stock_name"], context), "stock_id": card["stock_id"], "stock_name": card["stock_name"], "signal": card["signal"], "summary": card["summary"], "advisory_only": True}
def render_markdown_report(user_report: dict[str, Any]) -> str:
    lines = [f"# {user_report['title']}", "", str(user_report.get("subtitle", "")), "", str(user_report.get("summary", "")), ""]
    for section in user_report.get("sections", []):
        lines.extend([f"## {section.get('heading')}", str(section.get("body", "")), ""])
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
    user_report = {
        "title": context.display_title,
        "subtitle": context.primary_purpose,
        "summary": summary,
        "sections": base_sections(context.display_label, content_state, summary),
        "stock_cards": [format_stock_card(card, context) for card in normalized] if show_stock_cards else [],
        "review_cards": review_state_cards(content_state) if context.pipeline_type in {"post_close", "prediction_review"} else [],
        "warnings": warnings,
        "dashboard_url": dashboard_url,
        "advisory_only": True,
    }
    user_report["rendered_text"] = render_markdown_report(user_report)
    return user_report
def format_window_report(scheduler_window: str, content_state: str, sanitized_text: str, stock_cards: list[dict[str, Any]] | None = None, dashboard_url: str | None = None) -> dict[str, Any]:
    return build_user_facing_report(get_window_context(scheduler_window), content_state, sanitized_text, stock_cards, dashboard_url)
