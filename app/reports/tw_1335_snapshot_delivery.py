"""TW 13:35 notification projection bound to immutable archive snapshots."""
from __future__ import annotations

from datetime import datetime
import html
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.dashboard.dashboard_url_registry import get_window_archive_url
from app.dashboard.market_dashboard_alias import payload_hash
from app.dashboard.window_snapshot_archive import load_admitted_snapshots, resolve_snapshots
from app.reports.decision_intelligence_v4 import project_decision_intelligence_v4

TAIPEI = ZoneInfo("Asia/Taipei")


def _time(value: Any) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TAIPEI)
    return parsed.astimezone(TAIPEI).replace(microsecond=0).isoformat()


def _snapshot_for_date(archive_root: Path, window: str, trading_date: str) -> dict[str, Any] | None:
    rows = [
        item for item in load_admitted_snapshots(archive_root)
        if item.get("market") == "TW"
        and item.get("window") == window
        and item.get("effective_trading_date") == trading_date
    ]
    return max(rows, key=lambda item: (int(item.get("revision") or 0), str(item.get("revision_created_at") or "")), default=None)


def _set(projection: dict[str, Any], name: str) -> set[str]:
    values = (projection.get("lists") or {}).get(name) or []
    return {str(value) for value in values}


def build_same_day_change(current: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
    if not baseline:
        return {"available": False, "message": "本次無同日 13:05 可比較基準", "baseline_snapshot_id": None}
    current_projection = current["projection"]
    baseline_projection = baseline["projection"]
    if not int((current_projection.get("counts") or {}).get("total") or 0) or not int((baseline_projection.get("counts") or {}).get("total") or 0):
        return {"available": False, "message": "同日 13:05 baseline 存在，但缺少可比較的結構化決策資料", "baseline_snapshot_id": baseline["snapshot_id"]}
    decision = current_projection.get("pre_close_decision") or {}
    hold = set(decision.get("top_hold_candidates") or [])
    avoid = set(decision.get("top_avoid_candidates") or [])
    near_target = set(decision.get("near_target_cases") or [])
    near_stop = set(decision.get("near_stop_cases") or [])
    risk = set(decision.get("late_session_risk_cases") or [])
    tomorrow = set(decision.get("tomorrow_watch") or [])
    return {
        "available": True,
        "policy": "same_market_same_effective_trading_date_intraday_1305_to_pre_close_1335",
        "baseline_snapshot_id": baseline["snapshot_id"],
        "added_watch": sorted(hold - _set(baseline_projection, "still_actionable")),
        "changed_to_avoid": sorted(avoid - _set(baseline_projection, "no_trade")),
        "new_triggered": sorted(_set(current_projection, "triggered") - _set(baseline_projection, "triggered")),
        "new_invalidated": sorted(_set(current_projection, "invalidated") - _set(baseline_projection, "invalidated")),
        "near_target_added": sorted(near_target),
        "near_stop_added": sorted(near_stop),
        "late_risk_increased": sorted(risk),
        "watchlist_added": sorted(tomorrow - _set(baseline_projection, "still_actionable")),
        "watchlist_removed": sorted(_set(baseline_projection, "still_actionable") - tomorrow),
    }


def snapshot_context(snapshot: dict[str, Any], baseline_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    projection = project_decision_intelligence_v4("TW", "pre_close_1335", payload)
    baseline = None
    if baseline_snapshot:
        baseline_payload = baseline_snapshot.get("payload") if isinstance(baseline_snapshot.get("payload"), dict) else {}
        baseline = {
            "snapshot_id": baseline_snapshot.get("snapshot_id"),
            "projection": project_decision_intelligence_v4("TW", "intraday_1305", baseline_payload),
        }
    context = {
        "market": "TW",
        "window": "pre_close_1335",
        "snapshot_id": snapshot.get("snapshot_id"),
        "effective_trading_date": snapshot.get("effective_trading_date"),
        "revision": int(snapshot.get("revision") or 1),
        "effective_batch_time": _time(payload.get("effective_batch_time") or snapshot.get("original_batch_time")),
        "source_data_time": _time(payload.get("source_data_time")),
        "source_data_date": payload.get("source_data_date") or ((payload.get("source_data_dates") or [None])[-1]),
        "generated_at": _time(payload.get("generated_at") or snapshot.get("generated_at")),
        "payload_hash": payload_hash(payload),
        "canonical_url": get_window_archive_url("TW", "pre_close_1335"),
        "projection": projection,
        "prediction_available": payload.get("prediction_available"),
        "prediction_total": payload.get("prediction_total"),
        "source_time_status": payload.get("source_data_time_status") or ("available" if payload.get("source_data_time") else "unavailable"),
    }
    context["same_day_change"] = build_same_day_change(context, baseline)
    return context


def resolve_context(archive_root: Path) -> dict[str, Any] | None:
    snapshot = resolve_snapshots(archive_root, "TW", "pre_close_1335").latest
    if not snapshot:
        return None
    baseline = _snapshot_for_date(archive_root, "intraday_1305", str(snapshot.get("effective_trading_date") or ""))
    return snapshot_context(snapshot, baseline)


def context_for_snapshot(archive_root: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    baseline = _snapshot_for_date(archive_root, "intraday_1305", str(snapshot.get("effective_trading_date") or ""))
    return snapshot_context(snapshot, baseline)


def _display_time(value: str | None) -> str:
    return value[:16].replace("T", " ") if value else "尚未取得"


def _count(value: Any) -> str:
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else "尚未取得"


def _names(values: list[str] | None) -> str:
    return "、".join(values or []) or "無"


def render_email(context: dict[str, Any]) -> str:
    decision = context["projection"].get("pre_close_decision") or {}
    change = context["same_day_change"]
    if change.get("available"):
        comparison = [
            "與 13:05 相比",
            f"新增可留意 {_names(change.get('added_watch'))}｜轉為不留倉 {_names(change.get('changed_to_avoid'))}",
            f"Setup 新觸發 {_names(change.get('new_triggered'))}｜Setup 失效 {_names(change.get('new_invalidated'))}",
        ]
    else:
        comparison = [str(change.get("message"))]
    prediction = (
        f"隔日價格預測：尚未完成（{context['prediction_available']} / {context['prediction_total']}）；收盤前決策仍使用本 window 已保存的價格、量價與策略狀態。"
        if context.get("prediction_available") == 0 and isinstance(context.get("prediction_total"), int)
        else f"隔日價格預測：{context['prediction_available']} / {context['prediction_total']}"
        if isinstance(context.get("prediction_available"), int) and isinstance(context.get("prediction_total"), int)
        else "隔日價格預測：尚未完成；收盤前決策僅使用本 window 已保存的價格、量價與策略狀態。"
    )
    return "\n".join([
        "【Stock AI】13:35 台股收盤前快照",
        f"批次時間：{_display_time(context.get('effective_batch_time'))}",
        f"行情資料時間：{_display_time(context.get('source_data_time'))}",
        f"報告產生時間：{_display_time(context.get('generated_at'))}",
        f"有效標的：{decision.get('stock_count', 0)}",
        "",
        "收盤前決策",
        f"可留倉 {_count(decision.get('hold_candidate_count'))}｜不建議留倉 {_count(decision.get('avoid_hold_count'))}｜無交易 {_count(decision.get('no_trade_count'))}",
        f"接近目標 {_count(decision.get('near_target_count'))}｜接近停損 {_count(decision.get('near_stop_count'))}｜尾盤高風險 {_count(decision.get('late_session_risk_count'))}",
        *comparison,
        "",
        "重點標的（13:35 行動排序）",
        f"優先：{_names(decision.get('ranking'))}",
        f"明日初步觀察：{_names(decision.get('tomorrow_watch'))}",
        prediction,
        "",
        "完整報告：",
        context["canonical_url"],
        "僅供研究參考，非交易指令。",
    ])


def render_line(context: dict[str, Any]) -> str:
    decision = context["projection"].get("pre_close_decision") or {}
    change = context["same_day_change"]
    comparison = (
        f"新增可留意 {len(change.get('added_watch') or [])}｜轉弱 {len(change.get('changed_to_avoid') or [])}｜Setup 失效 {len(change.get('new_invalidated') or [])}"
        if change.get("available") else str(change.get("message"))
    )
    return "\n".join([
        "【Stock AI】13:35 台股收盤前快照",
        f"可留倉 {_count(decision.get('hold_candidate_count'))}｜不留倉 {_count(decision.get('avoid_hold_count'))}｜無交易 {_count(decision.get('no_trade_count'))}",
        f"接近目標 {_count(decision.get('near_target_count'))}｜接近停損 {_count(decision.get('near_stop_count'))}｜尾盤高風險 {_count(decision.get('late_session_risk_count'))}",
        "與 13:05 相比：",
        comparison,
        "完整報告：",
        context["canonical_url"],
    ])


def render_dashboard(context: dict[str, Any]) -> str:
    decision = context["projection"].get("pre_close_decision") or {}
    change = context["same_day_change"]
    comparison = (
        f"新增可留意：{_names(change.get('added_watch'))}；轉為不留倉：{_names(change.get('changed_to_avoid'))}；"
        f"Setup 新觸發：{_names(change.get('new_triggered'))}；Setup 失效：{_names(change.get('new_invalidated'))}；"
        f"接近目標新增：{_names(change.get('near_target_added'))}；接近停損新增：{_names(change.get('near_stop_added'))}；"
        f"尾盤風險升高：{_names(change.get('late_risk_increased'))}；明日 watchlist 新增：{_names(change.get('watchlist_added'))}；移除：{_names(change.get('watchlist_removed'))}"
        if change.get("available") else str(change.get("message"))
    )
    prediction = (
        f"隔日價格預測：尚未完成（{context['prediction_available']} / {context['prediction_total']}）；收盤前決策仍使用本 window 已保存的價格、量價與策略狀態。"
        if context.get("prediction_available") == 0 and isinstance(context.get("prediction_total"), int)
        else f"隔日價格預測：{context['prediction_available']} / {context['prediction_total']}"
        if isinstance(context.get("prediction_available"), int) and isinstance(context.get("prediction_total"), int)
        else "隔日價格預測尚未完成；不影響已保存的 13:35 價格、量價與策略狀態呈現。"
    )
    rows = [
        ("批次時間", _display_time(context.get("effective_batch_time"))),
        ("行情資料時間", _display_time(context.get("source_data_time"))),
        ("報告產生時間", _display_time(context.get("generated_at"))),
        ("可留倉", _count(decision.get("hold_candidate_count"))),
        ("不建議留倉", _count(decision.get("avoid_hold_count"))),
        ("無交易", _count(decision.get("no_trade_count"))),
        ("接近目標", _count(decision.get("near_target_count"))),
        ("接近停損", _count(decision.get("near_stop_count"))),
        ("尾盤高風險", _count(decision.get("late_session_risk_count"))),
        ("明日初步觀察", _names(decision.get("tomorrow_watch"))),
    ]
    table = "".join(f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>" for label, value in rows)
    return (
        '<section class="section tw-pre-close-delivery-v1" data-window-binding="pre_close_1335">'
        '<h2>13:35 收盤前決策</h2>'
        f'<table class="decision-table"><tbody>{table}</tbody></table>'
        f'<h3>13:35 行動排序</h3><p>{html.escape(_names(decision.get("ranking")))}</p>'
        f'<h3>同日 13:05 → 13:35 變化</h3><p>{html.escape(comparison)}</p>'
        f'<p class="decision-note">{html.escape(prediction)}</p>'
        '<p class="decision-note">缺少的欄位顯示「尚未取得」，不以 0 或其他 window 時間代替。</p>'
        '</section>'
    )
