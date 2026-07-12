#!/usr/bin/env python3
"""Build TW Daily Tactical runtime artifacts without sending notifications."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.strategy.tw_daily_tactical import build_runtime

RUNTIME_DIR = ROOT / "artifacts/runtime/tw_daily_tactical"
LATEST_JSON = RUNTIME_DIR / "tw_daily_tactical_latest.json"
LATEST_MD = RUNTIME_DIR / "tw_daily_tactical_latest.md"
PREDICTION_DIR = RUNTIME_DIR / "prediction_snapshots"
REVIEW_DIR = RUNTIME_DIR / "review_snapshots"
EMAIL_PREVIEW = RUNTIME_DIR / "tw_daily_tactical_email_preview_latest.md"
LINE_PREVIEW = RUNTIME_DIR / "tw_daily_tactical_line_preview_latest.txt"
DASHBOARD_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/tw/index.html"


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def zone_text(zone: dict[str, Any] | None) -> str:
    if not isinstance(zone, dict):
        return "資料不足"
    return f"{zone.get('low')} ～ {zone.get('high')}"


def markdown(runtime: dict[str, Any]) -> str:
    lines = [
        "# TW Daily Tactical Intelligence V1",
        "",
        f"generated_at: {runtime.get('generated_at')}",
        f"stock_count: {runtime.get('stock_count')}",
        f"strategy_id: {runtime.get('strategy_id')}",
        "",
        "## Market Context",
        json.dumps(runtime.get("market_context", {}), ensure_ascii=False),
        "",
        "## Per-stock Tactical Summary",
    ]
    for card in runtime.get("cards", []):
        t = card["strategies"]["daily_tactical"]
        lines.extend([
            f"### {card.get('stock_id')} {card.get('stock_name')}",
            f"- Setup / Action: {t.get('setup_type')} / {t.get('action')}",
            f"- Score / Rating / Confidence: {t.get('score')} / {t.get('rating')} / {t.get('confidence')}",
            f"- Entry: {zone_text(t.get('entry_zone'))}",
            f"- Stop: {t.get('stop_invalidation')}",
            f"- Target 1: {zone_text(t.get('target_1'))}",
            f"- Target 2: {zone_text(t.get('target_2'))}",
            f"- RR / Expected Move: {t.get('reward_risk')} / {t.get('expected_move_pct')}",
            f"- Chase/Event/Position/Data: {t.get('chase_risk')} / {t.get('event_risk')} / {t.get('position_size')} / {t.get('data_quality')}",
            f"- Reasons: {'；'.join(t.get('reasons') or [])}",
            f"- Risks: {'；'.join(t.get('risk_reasons') or [])}",
            f"- Playbook: {t.get('playbook')}",
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def email_preview(runtime: dict[str, Any]) -> str:
    lines = ["【Stock AI】台股 Daily Tactical Summary", "", f"Dashboard: {DASHBOARD_URL}", "", "## Research / Position Strategy", "既有 Research / Position strategy 保持獨立，不由 Daily Tactical 覆寫。", "", "## Daily Tactical Strategy"]
    for card in runtime.get("cards", []):
        t = card["strategies"]["daily_tactical"]
        lines.append(f"- {card.get('stock_id')} {card.get('stock_name')}：{t.get('setup_type')} / {t.get('action')} / Entry {zone_text(t.get('entry_zone'))} / Stop {t.get('stop_invalidation')} / Target {zone_text(t.get('target_1'))} / RR {t.get('reward_risk')} / Confidence {t.get('confidence')} / No Trade原因 {('；'.join(t.get('risk_reasons') or []) if t.get('setup_type') == 'no_trade' else '不適用')}")
    lines.extend(["", "本信僅為 dry-run preview；notification_sent=false。"])
    return "\n".join(lines) + "\n"


def line_preview(runtime: dict[str, Any]) -> str:
    s = runtime.get("line_summary", {})
    return "\n".join([
        "台股報告已更新",
        f"Research：偏多 {s.get('research_bullish')}｜中性 {s.get('research_neutral')}｜保守 {s.get('research_conservative')}",
        f"Daily Tactical：可觀察 {s.get('daily_tactical_observable')}｜No Trade {s.get('daily_tactical_no_trade')}",
        f"高追價風險：{s.get('high_chase_risk')}",
        f"Dashboard：{DASHBOARD_URL}",
        "僅供研究參考，非交易指令。",
    ]) + "\n"


def write_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTION_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(stable_json(runtime), encoding="utf-8")
    LATEST_MD.write_text(markdown(runtime), encoding="utf-8")
    EMAIL_PREVIEW.write_text(email_preview(runtime), encoding="utf-8")
    LINE_PREVIEW.write_text(line_preview(runtime), encoding="utf-8")
    date_key = str(runtime.get("generated_at", ""))[:10] or "unknown-date"
    pred_dir = PREDICTION_DIR / date_key
    rev_dir = REVIEW_DIR / date_key
    pred_dir.mkdir(parents=True, exist_ok=True)
    rev_dir.mkdir(parents=True, exist_ok=True)
    for snap in runtime.get("prediction_snapshots", []):
        (pred_dir / f"{snap.get('stock_id')}_daily_tactical.json").write_text(stable_json(snap), encoding="utf-8")
    for snap in runtime.get("review_snapshots", []):
        (rev_dir / f"{snap.get('stock_id')}_daily_tactical_review.json").write_text(stable_json(snap), encoding="utf-8")
    return {"json": str(LATEST_JSON), "md": str(LATEST_MD), "email_preview": str(EMAIL_PREVIEW), "line_preview": str(LINE_PREVIEW), "prediction_dir": str(pred_dir), "review_dir": str(rev_dir)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    runtime = build_runtime()
    paths = {} if args.dry_run else write_runtime(runtime)
    result = {"ok": True, "dry_run": args.dry_run, "stock_count": runtime.get("stock_count"), "line_summary": runtime.get("line_summary"), "paths": paths, "safety": runtime.get("safety")}
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
