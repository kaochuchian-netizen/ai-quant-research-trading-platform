"""User-facing, side-effect-free presentation for the immutable 17:00 review."""
from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path
from typing import Any


VERSION = "daily_learning_presentation_v1"
ROUTE = "dashboard/daily-evaluation"


def _text(value: Any) -> str:
    return html.escape(str(value))


def _market_label(market: str) -> str:
    return "台股" if market == "TW" else "美股"


def _prediction_result(data: dict[str, Any]) -> str:
    eligible = correct = pending = 0
    for stock in data.get("stocks", {}).values():
        for review in stock.get("sample_reviews", {}).values():
            assessment = review.get("assessment", {})
            if assessment.get("eligible") is True:
                eligible += 1
                correct += assessment.get("direction_correct") is True
            elif assessment.get("state") == "WAITING_OUTCOME":
                pending += 1
    if eligible:
        return f"已完成 {eligible} 筆方向結果比對，其中 {correct} 筆與實際走勢一致。"
    if pending:
        return f"已有 {pending} 筆預測等待正式收盤結果，完成後才會納入檢討。"
    return "本次沒有可安全判定的預測結果；不以不完整資料下結論。"


def _lesson_text(learning: dict[str, Any]) -> tuple[str, str]:
    actionable = learning.get("actionable_learning") if isinstance(learning, dict) else {}
    if not isinstance(actionable, dict):
        actionable = {}
    finding = learning.get("finding") if isinstance(learning, dict) else None
    if finding == "DIRECTION_ERROR_OBSERVED" and actionable.get("active") is True:
        return (
            "今日部分方向判斷與實際走勢不一致，已納入下一交易日的保守處理依據。",
            "對已出現偏差的方向訊號維持較嚴格的保留條件；不調整模型、權重或交易策略。",
        )
    if finding == "OUTCOME_EVIDENCE_GAP":
        return (
            "部分預測仍等待可驗證的正式結果，暫不把未成熟資料當作成敗。",
            "待正式結果成熟後，再依既有規則完成檢討。",
        )
    return (
        "目前未發現可安全歸因的方向偏差，持續保留完整證據供後續檢討。",
        "下一交易日維持既有決策流程，並持續檢查資料完整性。",
    )


def presentation(value: dict[str, Any]) -> dict[str, Any]:
    """Project immutable evaluator output without exposing internal enums or hashes."""
    markets = value.get("markets") if isinstance(value.get("markets"), dict) else {}
    learning = value.get("learning_artifact", {}).get("markets", {}) if isinstance(value.get("learning_artifact"), dict) else {}
    sections = {}
    next_steps = []
    for market in ("TW", "US"):
        lesson, next_step = _lesson_text(learning.get(market, {}))
        sections[market] = {
            "label": _market_label(market),
            "prediction_result": _prediction_result(markets.get(market, {})),
            "strategy_review": lesson,
            "learning_adjustment": next_step,
        }
        next_steps.append(f"{_market_label(market)}：{next_step}")
    return {
        "schema_version": VERSION,
        "report_date": str(value.get("report_date") or ""),
        "markets": sections,
        "today_conclusion": "本報告僅整理已完成且可驗證的預測檢討；未成熟資料不會被當成策略結論。",
        "next_trading_day_adjustment": next_steps,
    }


def render_dashboard(value: dict[str, Any]) -> str:
    view = presentation(value)
    sections = ""
    for market in ("TW", "US"):
        item = view["markets"][market]
        sections += f'''<section class="market-card" data-market="{market}">
<h2>{_text(item["label"])}</h2>
<dl><dt>預測成果</dt><dd>{_text(item["prediction_result"])}</dd>
<dt>策略檢討</dt><dd>{_text(item["strategy_review"])}</dd>
<dt>學習調整</dt><dd>{_text(item["learning_adjustment"])}</dd></dl>
</section>'''
    adjustments = "".join(f"<li>{_text(item)}</li>" for item in view["next_trading_day_adjustment"])
    return f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>每日策略檢討</title><style>
body{{margin:0;background:#f4f7f8;color:#132b32;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif;line-height:1.55}}main{{max-width:720px;margin:auto;padding:20px 16px 42px;box-sizing:border-box}}h1{{margin:0;font-size:24px}}.date{{margin:6px 0 18px;color:#526970}}.market-card,.conclusion{{background:#fff;border:1px solid #dbe6e9;border-radius:12px;padding:16px;margin:12px 0}}h2{{margin:0 0 10px;font-size:19px}}dl{{margin:0}}dt{{font-size:13px;font-weight:800;color:#526970;margin-top:12px}}dt:first-child{{margin-top:0}}dd{{margin:3px 0 0;font-size:16px}}details{{margin-top:14px;background:#fff;border:1px solid #dbe6e9;border-radius:10px}}summary{{padding:13px;font-weight:800;cursor:pointer}}details p{{padding:0 13px 13px;margin:0;color:#526970;font-size:14px}}@media(max-width:393px){{main{{padding:16px 12px 32px}}h1{{font-size:22px}}.market-card,.conclusion{{padding:14px}}dd{{font-size:15px}}}}</style></head>
<body data-daily-learning-presentation="{VERSION}" data-report-date="{_text(view["report_date"])}"><main><header><h1>【每日策略檢討】{_text(view["report_date"])}</h1><p class="date">台股與美股分別依其完成交易日檢討。</p></header>{sections}<section class="conclusion"><h2>今日結論</h2><p>{_text(view["today_conclusion"])}</p><h2>下一交易日調整</h2><ul>{adjustments}</ul></section><details><summary>詳細評估資料</summary><p>完整預測、結果、證據與資料關聯已保留在 immutable evaluation artifact，供稽核與回放；本頁不顯示內部診斷或原始列舉值。</p></details></main></body></html>\n'''


def render_line_summary(value: dict[str, Any]) -> str:
    """A no-send formatter; delivery activation remains a separate approval gate."""
    view = presentation(value)
    lines = [f"【每日策略檢討】{view['report_date']}"]
    for market in ("TW", "US"):
        item = view["markets"][market]
        lines.extend((item["label"], f"預測成果：{item['prediction_result']}", f"策略檢討：{item['strategy_review']}", f"學習調整：{item['learning_adjustment']}"))
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".daily-learning-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def publish_dashboard(value: dict[str, Any], *, static_root: Path, output_root: Path) -> dict[str, str]:
    """Publish a static sidecar only after immutable daily persistence succeeds."""
    identity = str(value.get("identity") or "")
    report_date = str(value.get("report_date") or "")
    if len(identity) != 64 or not report_date:
        raise ValueError("DAILY_PRESENTATION_IDENTITY")
    page = render_dashboard(value)
    relative = Path(ROUTE) / report_date / identity / "index.html"
    staged = Path(output_root) / relative
    latest = Path(static_root) / ROUTE / "latest" / "index.html"
    published = Path(static_root) / relative
    _atomic_write(staged, page)
    _atomic_write(published, page)
    _atomic_write(latest, page)
    return {"status": "PUBLISHED", "route": "/" + str(Path(ROUTE) / "latest" / "index.html"), "artifact_route": "/" + str(relative)}
