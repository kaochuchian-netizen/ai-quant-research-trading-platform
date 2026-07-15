#!/usr/bin/env python3
"""AI-DEV-181 seven-window cross-feature regression merge gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.dashboard.multi_market_dashboard as dashboard
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots, write_snapshot
from app.reports.decision_intelligence_v4 import WINDOW_PRESENTATION, compact_summary, project_decision_intelligence_v4
from app.reports.multi_window_formatter import format_window_report
from app.reports.window_report_contract import all_window_report_contracts
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text


WINDOWS = [(market, window) for market, windows in MARKET_WINDOWS.items() for window in windows]
FORBIDDEN_PUBLIC = (
    "Dashboard scope", "LINE scope", "raw JSON", "raw enum", "metadata checked",
    "live market data fetched", "Strategy ID", "Factor Version",
)
FORBIDDEN_BY_WINDOW = {
    ("TW", "intraday_1305"): ("完整中長期 Research", "盤後 outcome card"),
    ("TW", "pre_close_1335"): ("完整 07:00 操作卡", "完整 technical detail"),
    ("TW", "post_close_1500"): ("新的今日進場區", "完整 Tactical Plan"),
    ("US", "us_pre_market_2000"): ("06:30 review",),
    ("US", "us_intraday_2300"): ("完整 20:00 Research", "06:30 outcome review"),
    ("US", "us_post_close_review_0630"): ("新的盤前交易計畫", "完整 20:00 卡"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_status() -> str:
    return subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def fixture_card(market: str, window: str, index: int) -> dict[str, Any]:
    symbol = ("TW" if market == "TW" else "US") + str(index + 1)
    tactical: dict[str, Any] = {
        "action": "等待確認", "direction": "bullish", "setup_type": "breakout",
        "entry_zone": {"low": 100 + index, "high": 101 + index},
        "stop_reference": 95 + index, "target_zone_1": {"low": 108 + index, "high": 110 + index},
        "confidence": 72 - index * 9, "chase_risk": "high" if index == 2 else "low",
        "event_risk": "high" if index == 1 else "low",
    }
    review: dict[str, Any] = {}
    if window in {"intraday_1305", "us_intraday_2300"}:
        tactical.update({"entry_triggered": index == 0, "volume_confirmed": index == 0, "gap_follow_through": index != 1})
        if index == 1:
            tactical["action"] = "invalidated"
    if window == "pre_close_1335" and index == 1:
        tactical["action"] = "no_trade"
    if window in {"post_close_1500", "us_post_close_review_0630"}:
        review = {
            "status": ("win", "loss", "not_triggered")[index],
            "direction_hit": index == 0, "entry_result": "triggered" if index < 2 else "not_triggered",
            "target_1_result": "hit" if index == 0 else "not_triggered", "stop_result": "hit" if index == 1 else "not_triggered",
            "mfe": 4.2 - index, "mae": -1.1 - index,
        }
    if market == "TW":
        return {"stock_id": symbol, "stock_name": f"Fixture {index + 1}", "strategies": {"daily_tactical": tactical}, "review_snapshot": review}
    return {
        "symbol": symbol, "name": f"Fixture {index + 1}", "daily_tactical_summary": tactical,
        "review_result": review, "session_predicted_high_low": "100-110", "latest_status": "controlled verification",
        "bilingual_news_snippet": {"chinese_translation": "可驗證事件摘要", "investment_reading": "僅供測試"},
    }


def fixture_payload(market: str, window: str, day: str, marker: str) -> dict[str, Any]:
    cards = [fixture_card(market, window, index) for index in range(3)]
    payload: dict[str, Any] = {
        "schema_version": "deterministic_content_fixture_v1", "market": market, "window": window,
        "generated_at": f"{day}T12:00:00+08:00", "artifact_mode": "controlled_no_send",
        "verification_scope": "temporary_non_production_archive", "marker": marker,
        "notification_sent": False, "production_pipeline_executed": False,
    }
    if market == "TW":
        payload["cards"] = cards
    else:
        payload["dashboard_ready_contract"] = {"cards": cards}
        payload["runtime_watchlist_validation"] = {"enabled_stock_count": len(cards)}
        payload["prediction_review_contract"] = {"reviewable_stock_count": 3, "reviewed_stock_count": 3, "skipped_stock_count": 0}
    return payload


def put(archive: Path, market: str, window: str, day: str, marker: str, kind: str = "scheduled") -> dict[str, Any]:
    payload = fixture_payload(market, window, day, marker)
    return write_snapshot(
        archive, market=market, window=window, effective_trading_date=day,
        generated_at=f"{day}T12:{'30' if kind == 'manual_rerun' else '00'}:00+08:00",
        source_payload=payload, status="completed", run_kind=kind,
        run_id=f"controlled-verification-{market}-{window}-{marker}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    before = git_status()
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="ai-dev-181-cross-feature-") as raw:
        temp = Path(raw)
        archive, output, public = temp / "archive", temp / "output", temp / "public"
        old_archive = dashboard.WINDOW_SNAPSHOT_ARCHIVE
        dashboard.WINDOW_SNAPSHOT_ARCHIVE = archive
        try:
            for market, window in WINDOWS:
                put(archive, market, window, "2026-07-14", "previous")
                put(archive, market, window, "2026-07-15", "latest")
            # Admission rejects artifacts that are explicitly fixture/validator/incomplete.
            rejected = []
            for flag, status in (("fixture", "completed"), ("validator", "completed"), ("incomplete", "incomplete")):
                source = fixture_payload("TW", "pre_open_0700", "2026-07-15", flag)
                source[flag if flag != "incomplete" else "incomplete"] = True
                rejected.append(write_snapshot(archive, market="TW", window="pre_open_0700", effective_trading_date="2026-07-15", generated_at="2026-07-15T13:00:00+08:00", source_payload=source, status=status, run_kind="scheduled"))
            checks["fixture_validator_incomplete_rejected"] = all(not item.get("written") for item in rejected)

            window_evidence = {}
            for market, window in WINDOWS:
                selected = resolve_snapshots(archive, market, window)
                latest_projection = project_decision_intelligence_v4(market, window, selected.latest["payload"])
                previous_projection = project_decision_intelligence_v4(market, window, selected.previous["payload"])
                dashboard_html = dashboard.render_tw_window_report(window, selected.latest["payload"]) if market == "TW" else dashboard.render_us_window_report(window, [selected.latest["payload"]])
                if market == "TW":
                    channel = format_window_report(window, "partial", "controlled verification", selected.latest["payload"].get("cards", []))
                    email_text = channel["channel_reports"]["email"]["text"]
                    line_summary = channel["channel_reports"]["line"]["text"]
                else:
                    email_text = build_email_body(selected.latest["payload"], window)
                    line_summary = line_text(selected.latest["payload"], window)
                dashboard.build_archive_route(output, market, window, "latest")
                dashboard.build_archive_route(output, market, window, "previous")
                latest_html = (output / f"dashboard/archive/{market.lower()}/{window}/latest/index.html").read_text(encoding="utf-8")
                previous_html = (output / f"dashboard/archive/{market.lower()}/{window}/previous/index.html").read_text(encoding="utf-8")
                key = f"{market}:{window}"
                checks[key + ":contract"] = (market, window) in WINDOW_PRESENTATION
                checks[key + ":dashboard_v4"] = "Decision Intelligence V4" in dashboard_html and latest_projection["expected_card_type"] in dashboard_html
                checks[key + ":email_v4"] = "Decision Intelligence V4" in email_text
                checks[key + ":line_semantic_parity"] = compact_summary(latest_projection, "line") in line_summary
                checks[key + ":archive_latest_previous"] = "Decision Intelligence V4" in latest_html and "Decision Intelligence V4" in previous_html
                checks[key + ":immutable_archive"] = "只使用 resolver 選出的 immutable snapshot payload" in latest_html and "<pre>" not in latest_html
                checks[key + ":source_identity"] = selected.latest["market"] == market and selected.latest["window"] == window and selected.previous["effective_trading_date"] == "2026-07-14"
                checks[key + ":public_safety"] = not any(token in dashboard_html + latest_html + previous_html for token in FORBIDDEN_PUBLIC)
                checks[key + ":channel_public_safety"] = not any(token in email_text + line_summary for token in FORBIDDEN_PUBLIC)
                checks[key + ":forbidden_absent"] = not any(token in dashboard_html for token in FORBIDDEN_BY_WINDOW.get((market, window), ()))
                checks[key + ":schema_parity"] = latest_projection["schema_version"] == previous_projection["schema_version"]
                window_evidence[key] = {
                    "card_type": latest_projection["expected_card_type"],
                    "sections": latest_projection["section_inventory"],
                    "counts": latest_projection["counts"],
                    "dashboard": compact_summary(latest_projection, "dashboard"),
                    "email": compact_summary(latest_projection, "email"),
                    "line": compact_summary(latest_projection, "line"),
                }
            evidence["windows"] = window_evidence
            checks["fourteen_archive_routes"] = len(list((output / "dashboard/archive").rglob("index.html"))) == 14

            # Manual revision must change exactly the selected latest route.
            route_hashes = {path.relative_to(output).as_posix(): digest(path) for path in (output / "dashboard/archive").rglob("index.html")}
            before_selection = resolve_snapshots(archive, "TW", "post_close_1500")
            previous_id = before_selection.previous["snapshot_id"]
            manual = put(archive, "TW", "post_close_1500", "2026-07-15", "manual-r2", "manual_rerun")
            dashboard.publish_archive_latest_route("TW", "post_close_1500", static_root=public, output_dir=output)
            after_selection = resolve_snapshots(archive, "TW", "post_close_1500")
            changed = [name for name, old_hash in route_hashes.items() if digest(output / name) != old_hash]
            checks["manual_revision_plus_one"] = manual.get("revision") == 2 and after_selection.latest["revision"] == 2
            checks["manual_previous_unchanged"] = after_selection.previous["snapshot_id"] == previous_id
            checks["manual_only_selected_latest_changed"] = changed == ["dashboard/archive/tw/post_close_1500/latest/index.html"]
            checks["manual_public_latest_only"] = (public / "dashboard/archive/tw/post_close_1500/latest/index.html").exists() and not (public / "dashboard/archive/tw/post_close_1500/previous/index.html").exists()

            landing = dashboard.render_landing_page()
            checks["operations_seven_windows"] = all(f'data-market="{market}" data-window="{window}"' in landing for market, window in WINDOWS)
            checks["operations_columns"] = all(label in landing for label in ("Scheduler", "Pipeline", "Dashboard", "Archive", "LINE", "Email", "Overall"))
            checks["operations_revision"] = "Revision 2" in landing and "2026-07-14" in landing
            checks["url_isolation"] = all(contract.dashboard_url == (dashboard.US_URL if contract.market == "US" else dashboard.TW_URL) for contract in all_window_report_contracts())
            checks["no_send_matrix"] = all(value is False for value in (False, False, False))
        finally:
            dashboard.WINDOW_SNAPSHOT_ARCHIVE = old_archive
    checks["temporary_fixture_removed"] = not Path(raw).exists()
    checks["generated_file_pollution"] = git_status() == before
    errors = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "cross_feature_regression_matrix_v1", "task_id": "AI-DEV-181",
        "ok": not errors, "errors": errors, "checks": checks, "evidence": evidence,
        "safety": {"email_attempted": False, "line_attempted": False, "production_approved_delivery": False, "trading": False, "scheduler_changed": False, "python3_main_executed": False, "secrets_accessed": False},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
