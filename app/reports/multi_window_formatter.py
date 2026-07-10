"""Multi-window user-facing report formatter."""
from __future__ import annotations
from typing import Any
from .report_sections import base_sections, normalize_stock_cards, review_state_cards
from .window_context import ReportWindowContext, get_window_context
STATUS_MARK = "🟡"
PREDICTION_PENDING_REASON = "資料待接：尚未找到正式 prediction runtime artifact，不產生假預測。"
PRE_OPEN_PREDICTION_FIELDS = [
    "今日最高價預測", "今日最低價預測", "隔天最高價預測", "隔天最低價預測",
    "未來 1 個月走勢", "未來 3 個月走勢", "信心分數", "主要依據",
]
DASHBOARD_URL_FALLBACK = "http://35.201.242.167/stock-ai-dashboard/dashboard/tw/index.html"
def stock_card_title(stock_id: str, stock_name: str, context: ReportWindowContext, marker: str = STATUS_MARK) -> str:
    return f"【{stock_id} {stock_name}】{context.display_label} {marker}"
def format_stock_card(card: dict[str, Any], context: ReportWindowContext) -> dict[str, Any]:
    return {"title": stock_card_title(card["stock_id"], card["stock_name"], context), "stock_id": card["stock_id"], "stock_name": card["stock_name"], "signal": card["signal"], "summary": card["summary"], "advisory_only": True}
def prediction_field_blocks(context: ReportWindowContext) -> list[dict[str, Any]]:
    if context.scheduler_window != "pre_open_0700":
        return []
    return [{"label": label, "value": "資料待接", "reason": PREDICTION_PENDING_REASON, "fabricated": False} for label in PRE_OPEN_PREDICTION_FIELDS]
def strategy_v2_sections(context: ReportWindowContext) -> list[dict[str, str]]:
    if context.scheduler_window == "pre_open_0700":
        return [
            {"heading": "台股盤前預測", "body": "今日盤前主報告，包含高低價、1M/3M 趨勢、confidence、rationale、風險與 Dashboard URL。"},
            {"heading": "台指期夜盤觀察", "body": "資料待接：夜盤觀察尚未找到正式 runtime artifact。"},
            {"heading": "美股盤後摘要狀態", "body": "美股資料待接：尚未提供美股股票代號或正式 runtime artifact。"},
        ]
    if context.scheduler_window == "intraday_1305":
        return [{"heading": "盤中分析", "body": "目前價格狀態、是否接近今日預測高低區間、量能/籌碼/ADR/外部市場與盤前假設有效性。"}]
    if context.scheduler_window == "pre_close_1335":
        return [{"heading": "收盤快照", "body": "今日高 / 低 / 收盤狀態與 07:00 預測區間初步比對；完整檢討待 15:00。"}]
    if context.scheduler_window in {"post_close_1500", "prediction_review_1500"}:
        return [{"heading": "盤後檢討 / Prediction Review", "body": "過去 7 天預測命中率、forecast vs actual、誤差來源、confidence calibration、factor effectiveness 與隔日改善建議。"}]
    return []

def line_notification_text(context: ReportWindowContext, dashboard_url: str) -> str:
    templates = {
        "pre_open_0700": ("【Stock AI】07:00 盤前決策摘要已更新", "今日盤前報告、baseline 預測、資料品質與風險提示請看 Dashboard。"),
        "intraday_1305": ("【Stock AI】13:05 盤中追蹤已更新", "盤中狀態、風險變化與資料完整度請看 Dashboard。"),
        "pre_close_1335": ("【Stock AI】13:35 收盤快照已更新", "收盤快照、當日狀態與後續檢討進度請看 Dashboard。"),
        "post_close_1500": ("【Stock AI】15:00 盤後檢討已更新", "單日檢討、7 天滾動檢討、樣本累積與校準狀態請看 Dashboard。"),
        "prediction_review_1500": ("【Stock AI】15:00 盤後檢討已更新", "單日檢討、7 天滾動檢討、樣本累積與校準狀態請看 Dashboard。"),
    }
    title, body = templates.get(context.scheduler_window, templates["pre_open_0700"])
    return "\n".join([title, body, "Dashboard：", dashboard_url, "僅供研究參考，非交易指令。"])

def render_markdown_report(user_report: dict[str, Any]) -> str:
    lines = [f"# {user_report['title']}", "", str(user_report.get("subtitle", "")), "", str(user_report.get("summary", "")), ""]
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
    email_sections = [s.get("heading") for s in user_report.get("sections", [])]
    return {
        "line": {"channel": "line", "mode": "link_only_notification", "line_summary_required": True, "full_report": False, "dashboard_url": url, "text": line_notification_text(context, url), "raw_logs_included": False, "notification_sent": False},
        "email": {"channel": "email", "mode": "full_report", "email_full_report_required": True, "dashboard_url": url, "sections": email_sections, "text": user_report.get("rendered_text", ""), "notification_sent": False},
        "dashboard": {"channel": "dashboard", "mode": "full_state_freshness_missing_data", "dashboard_full_state_required": True, "dashboard_url": url, "sections": ["今日決策摘要", "四批次內容狀態", "預測資料狀態", "LINE / Email / Dashboard delivery audit summary", "資料新鮮度", "技術檢查 / Debug"], "published_by_formatter": False},
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
        "title": context.display_title,
        "subtitle": context.primary_purpose,
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
    }
    user_report["rendered_text"] = render_markdown_report(user_report)
    user_report["channel_reports"] = build_channel_reports(context, user_report, dashboard_url)
    return user_report
def format_window_report(scheduler_window: str, content_state: str, sanitized_text: str, stock_cards: list[dict[str, Any]] | None = None, dashboard_url: str | None = None) -> dict[str, Any]:
    return build_user_facing_report(get_window_context(scheduler_window), content_state, sanitized_text, stock_cards, dashboard_url)
