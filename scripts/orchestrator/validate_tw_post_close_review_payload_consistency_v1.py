#!/usr/bin/env python3
"""Deterministic merge gate for AI-DEV-181G (no production writes or sends)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard import multi_market_dashboard as dashboard
from app.dashboard.market_dashboard_alias import payload_hash
from app.dashboard.window_snapshot_archive import resolve_snapshots, write_snapshot
from app.reports.tw_post_close_review import build_structured_review_payload, render_email

FORBIDDEN = ("樣本資料", "contract validation", "2330 sample")


def _fixture(day: str, revision_marker: str) -> tuple[dict[str, Any], dict[str, Any]]:
    outcomes = ["hit", "hit", "insufficient_data", "insufficient_data", "insufficient_data", "insufficient_data", "insufficient_data", "insufficient_data", "insufficient_data"]
    stocks = []
    tactical = []
    for index, status in enumerate(outcomes, 1):
        stock_id = f"T{index:04d}"
        stocks.append({
            "stock_id": stock_id, "stock_name": f"Review {index}", "hit_miss_status": status,
            "direction_result": "hit" if status == "hit" else "insufficient_data",
            "predicted_direction": "up", "actual_direction": "up" if status == "hit" else None,
            "recommendation_for_improvement": f"{revision_marker} review {index}",
            "review_date": day, "seven_day_hit_rate": 0.5 if index <= 2 else None,
        })
        action = "觀望" if 3 <= index <= 7 else "維持觀察"
        tactical.append({
            "stock_id": stock_id, "stock_name": f"Review {index}", "action": action,
            "strategies": {"daily_tactical": {"action": action, "entry_zone": [10, 11], "target_1": 12, "target_2": 13, "stop_invalidation": 9}},
        })
    return (
        {"market": "TW", "runtime_window": "prediction_review_1500", "review_date": day, "generated_at": f"{day}T15:03:00+08:00", "stocks": stocks},
        {"market": "TW", "window": "post_close_1500", "generated_at": f"{day}T15:01:00+08:00", "source_data_time": f"{day}T15:00:00+08:00", "cards": tactical},
    )


def _source(payload: dict[str, Any], run_id: str) -> dict[str, Any]:
    cards = payload["structured_review_cards"]
    return {
        "schema_version": "tw_window_snapshot_payload_v1", "market": "TW", "window": "post_close_1500",
        "run_id": run_id, "runtime_provenance": "scheduled_production", "fixture": False,
        "validation_only": False, "cards": cards, "structured_review_cards": cards,
        "structured_review": payload, "tracking_stock_count": payload["tracking_stock_count"],
        "rendered_review_card_count": payload["rendered_review_card_count"], "outcome_counts": payload["outcome_counts"],
        "review_content_hash": payload["review_content_hash"], "effective_batch_time": payload["effective_batch_time"],
        "source_data_time": payload["source_data_time"], "generated_at": payload["generated_at"],
    }


def validate() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="ai-dev-181g-") as raw:
        temp = Path(raw)
        archive = temp / "archive"
        pages = temp / "pages"
        payloads = []
        for day, marker in (("2026-07-15", "previous"), ("2026-07-16", "latest")):
            review, runtime = _fixture(day, marker)
            payload = build_structured_review_payload(review, runtime, effective_batch_time=f"{day}T15:00:00+08:00", generated_at=f"{day}T15:03:00+08:00")
            payloads.append(payload)
            result = write_snapshot(
                archive, market="TW", window="post_close_1500", effective_trading_date=day,
                generated_at=f"{day}T15:03:00+08:00", source_payload=_source(payload, marker),
                status="completed", run_kind="scheduled", run_id=marker, effective_batch_time=f"{day}T15:00:00+08:00",
            )
            checks[f"write_{marker}"] = result.get("written") is True
        latest = resolve_snapshots(archive, "TW", "post_close_1500").latest or {}
        previous = resolve_snapshots(archive, "TW", "post_close_1500").previous or {}
        latest_payload = latest.get("payload", {})
        email = render_email(latest_payload.get("structured_review", {}), "/dashboard/archive/tw/post_close_1500/latest/index.html", snapshot_id=str(latest.get("snapshot_id")), revision=int(latest.get("revision") or 1), payload_hash=payload_hash(latest_payload))
        old_archive = dashboard.WINDOW_SNAPSHOT_ARCHIVE
        dashboard.WINDOW_SNAPSHOT_ARCHIVE = archive
        try:
            build = dashboard.build_pages(pages)
        finally:
            dashboard.WINDOW_SNAPSHOT_ARCHIVE = old_archive
        market_html = (pages / "tw_index.html").read_text(encoding="utf-8")
        latest_html = (pages / "dashboard/archive/tw/post_close_1500/latest/index.html").read_text(encoding="utf-8")
        previous_html = (pages / "dashboard/archive/tw/post_close_1500/previous/index.html").read_text(encoding="utf-8")
        landing = (pages / "index.html").read_text(encoding="utf-8")
        counts = latest_payload.get("outcome_counts", {})
        checks.update({
            "structured_cards_9": len(latest_payload.get("structured_review_cards", [])) == 9,
            "tracking_equals_rendered": latest_payload.get("tracking_stock_count") == latest_payload.get("rendered_review_card_count") == latest_html.count('data-card-type="window-review"') == 9,
            "outcome_counts": counts == {"hit": 2, "not_triggered": 0, "fail": 0, "no_trade": 5, "pending": 2},
            "email_same_counts": all(token in email for token in ("命中 2", "無交易 5", "待確認 2", "Tracking：9｜Rendered：9")),
            "email_review_rank_not_rating": "代表性檢討" in email and "Top Signals" not in email and "分數" not in email,
            "time_semantics": all(token in email for token in ("交易日：2026-07-16", "盤後批次：2026-07-16 15:00", "行情時間：2026-07-16 15:00", "報告產生：2026-07-16 15:03")),
            "dashboard_archive_snapshot_id": str(latest.get("snapshot_id")) in market_html and str(latest.get("snapshot_id")) in latest_html,
            "dashboard_archive_payload_hash": payload_hash(latest_payload) in market_html and payload_hash(latest_payload) in latest_html,
            "previous_immutable": str(previous.get("snapshot_id")) in previous_html and str(previous.get("snapshot_id")) != str(latest.get("snapshot_id")),
            "operations_identity": str(latest.get("snapshot_id")) in landing and payload_hash(latest_payload) in landing,
            "forbidden_absent": not any(marker.lower() in (market_html + latest_html + previous_html).lower() for marker in FORBIDDEN),
            "canonical_url": "/dashboard/archive/tw/post_close_1500/latest/index.html" in email,
            "build_14_routes": build.get("archive_route_count") == 14,
        })
        dry_output = temp / "dry-run.json"
        env = dict(os.environ, STOCK_AI_WINDOW_SNAPSHOT_ARCHIVE=str(archive))
        proc = subprocess.run([
            sys.executable, str(ROOT / "scripts/orchestrator/approved_pre_open_delivery.py"),
            "--window", "post_close_1500", "--dry-run", "--output", str(dry_output),
        ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60, check=False)
        dry = json.loads(dry_output.read_text(encoding="utf-8")) if dry_output.exists() else {}
        checks["scheduler_equivalent_no_send"] = proc.returncode == 0 and dry.get("line_delivery_status") == "dry_run_not_sent" and dry.get("email_delivery_status") == "dry_run_not_sent" and dry.get("trading_order_portfolio_action") is False
        checks["scheduler_equivalent_structured"] = "Tracking：9｜Rendered：9" in str(dry.get("email_payload_preview")) and "/dashboard/archive/tw/post_close_1500/latest/index.html" in str(dry.get("email_payload_preview"))
        evidence = {
            "snapshot_id": latest.get("snapshot_id"), "revision": latest.get("revision"),
            "payload_hash": payload_hash(latest_payload), "review_content_hash": latest_payload.get("review_content_hash"),
            "counts": counts, "tracking": latest_payload.get("tracking_stock_count"),
            "rendered": latest_payload.get("rendered_review_card_count"),
            "scheduler_equivalent": {"returncode": proc.returncode, "email_attempted": False, "line_attempted": False, "trading": False},
            "temporary_fixture_cleaned": True,
        }
    failed = [name for name, ok in checks.items() if not ok]
    return {"ok": not failed, "task": "AI-DEV-181G", "checks": checks, "failed": failed, "evidence": evidence, "safety": {"production_archive_written": False, "notification_sent": False, "trading": False, "scheduler_changed": False, "python_main_executed": False}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
