#!/usr/bin/env python3
"""Validate AI-DEV-146 PM-readable four-window Dashboard UX."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
HTML_PATH = ROOT / "templates/four_window_dashboard_route_preview.example.html"
ARTIFACT_PATH = ROOT / "templates/four_window_dashboard_pm_readable_ux.example.json"
DOCS = [
    ROOT / "docs/four_window_dashboard_pm_readable_ux_v1.md",
    ROOT / "docs/runbooks/four_window_dashboard_pm_readable_ux_runbook.md",
]
PUBLIC_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"
SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I),
    re.compile(r"BEGIN (RSA|OPENSSH) PRIVATE KEY", re.I),
    re.compile(r"api[_-]?key\s*[:=]", re.I),
    re.compile(r"access[_-]?token\s*[:=]", re.I),
    re.compile(r"password\s*[:=]", re.I),
]


def fetch(url: str) -> tuple[bool, str, str | None]:
    try:
        with urlopen(url, timeout=10) as response:
            return True, response.read().decode("utf-8", errors="replace"), None
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, "", str(exc)


def positions(text: str, needles: list[str]) -> dict[str, int]:
    return {needle: text.find(needle) for needle in needles}


def secret_scan(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{path.relative_to(ROOT)}:{pattern.pattern}")
    return hits


def validate_html(html: str, errors: list[str]) -> dict[str, object]:
    required = [
        "四時段 AI 決策儀表板",
        "盤前、盤中、收盤快照、盤後檢討",
        "今日決策摘要",
        "不會觸發通知或下單",
        "四個時段怎麼看",
        "07:00",
        "盤前預測 / Pre-open Forecast",
        "13:05",
        "盤中追蹤 / Intraday Tracking",
        "13:35",
        "收盤快照 / Close Snapshot",
        "15:00",
        "盤後檢討 / Prediction Review",
        "Full prediction review",
        "資料可信度與證據來源",
        "官方公告 / 財報 / 法說會",
        "Google News / yfinance / broker target",
        "Gemini / AI summary",
        "技術檢查 / Debug",
        "no notification",
        "no scheduler change",
        "no DB write",
        "no production pipeline",
        "no trading",
        "no rating/action/confidence/weight mutation",
    ]
    for needle in required:
        if needle not in html:
            errors.append(f"missing required PM-readable content: {needle}")
    allowed_runtime_state_markers = [
        "預覽版 / 尚未接正式即時資料",
        "目前為預覽資料",
        "尚未接正式 runtime data",
        "formal prediction artifact 已接線",
        "formal review artifact 已接線",
        "正式預測資料待接",
        "盤後檢討資料待接",
        "資料待接",
    ]
    if not any(marker in html for marker in allowed_runtime_state_markers):
        errors.append("missing PM-readable formal runtime state marker")
    if "<iframe" in html.lower():
        errors.append("iframe / embedded nested static preview must not be present")
    forbidden_user_phrases = ["Embedded Static Preview", "Deterministic placeholder", "Route Contract</h2>", "<table"]
    for phrase in forbidden_user_phrases:
        if phrase in html:
            errors.append(f"forbidden user-facing technical/placeholder phrase remains: {phrase}")
    if "收盤前" in html or "Pre-close" in html:
        errors.append("13:35 primary UI must not display 收盤前 or Pre-close")
    pos = positions(html, ["今日決策摘要", "四個時段怎麼看", "技術檢查 / Debug", "route=", "production_dashboard_publish_executed=false"])
    if pos["技術檢查 / Debug"] < pos["四個時段怎麼看"]:
        errors.append("Debug section must appear after main four-window content")
    if pos["route="] != -1 and pos["route="] < pos["今日決策摘要"]:
        errors.append("route/debug details must not appear before decision summary")
    if "<details>" not in html or "<summary>技術檢查 / Debug</summary>" not in html:
        errors.append("Debug / safety flags must be collapsed with details/summary")
    if "@media (max-width:760px)" not in html or "grid-template-columns:1fr" not in html:
        errors.append("mobile readability markers missing")
    if "完整檢討待 15:00" not in html:
        errors.append("13:35 card must defer full review to 15:00")
    return {"positions": pos, "html_length": len(html)}


def validate_artifact(errors: list[str]) -> dict[str, object]:
    if not ARTIFACT_PATH.exists():
        errors.append("missing PM-readable UX artifact")
        return {}
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    if artifact.get("schema_version") != "four_window_dashboard_pm_readable_ux_v1":
        errors.append("PM-readable UX artifact schema mismatch")
    if artifact.get("task_id") != "AI-DEV-146":
        errors.append("PM-readable UX artifact task_id mismatch")
    cards = artifact.get("window_cards", [])
    if not isinstance(cards, list) or len(cards) != 4:
        errors.append("PM-readable UX artifact must define four window cards")
    safety = artifact.get("safety_policy", {}) if isinstance(artifact.get("safety_policy"), dict) else {}
    for key in ["external_notification_sent", "scheduler_modified", "db_write", "production_pipeline_executed", "python_main_executed", "trading_or_order_executed", "production_rating_action_confidence_weight_mutated", "formal_delivery_behavior_changed"]:
        if safety.get(key) is not False:
            errors.append(f"safety_policy.{key} must be false")
    debug = artifact.get("debug_section", {}) if isinstance(artifact.get("debug_section"), dict) else {}
    if debug.get("placement") != "after_main_content" or debug.get("collapsed_with_details") is not True:
        errors.append("debug_section must be collapsed and after main content")
    return {"window_card_count": len(cards) if isinstance(cards, list) else 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--published", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    for path in [HTML_PATH, ARTIFACT_PATH, *DOCS]:
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(ROOT)}")
    html = HTML_PATH.read_text(encoding="utf-8") if HTML_PATH.exists() else ""
    html_summary = validate_html(html, errors) if html else {}
    artifact_summary = validate_artifact(errors)
    published_summary = {"checked": False}
    if args.published:
        ok, published_html, error = fetch(PUBLIC_URL)
        published_summary = {"checked": True, "public_url": PUBLIC_URL, "reachable": ok, "error": error}
        if not ok:
            errors.append(f"published URL unreachable: {error}")
        else:
            validate_html(published_html, errors)
    secret_hits = secret_scan([HTML_PATH, ARTIFACT_PATH, *DOCS])
    if secret_hits:
        errors.extend([f"secret-like pattern hit: {hit}" for hit in secret_hits])
    result = {
        "ok": not errors,
        "task_id": "AI-DEV-146",
        "schema_version": "four_window_dashboard_pm_readable_ux_validation_v1",
        "published_mode": args.published,
        "errors": errors,
        "summary": {
            "title_present": "四時段 AI 決策儀表板" in html,
            "four_cards_present": all(marker in html for marker in ["07:00", "13:05", "13:35", "15:00"]),
            "close_snapshot_ok": "收盤快照 / Close Snapshot" in html,
            "iframe_present": "<iframe" in html.lower(),
            "debug_after_main": html.find("技術檢查 / Debug") > html.find("四個時段怎麼看"),
            "secret_pattern_hits": len(secret_hits),
            "html_summary": html_summary,
            "artifact_summary": artifact_summary,
            "published_summary": published_summary,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
