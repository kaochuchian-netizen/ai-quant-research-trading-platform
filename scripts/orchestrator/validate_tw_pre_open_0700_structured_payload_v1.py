#!/usr/bin/env python3
"""Deterministic no-send validation for the TW 07:00 structured payload."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard import multi_market_dashboard as dashboard_module
from app.dashboard import public_latest_sync as sync_module
from app.dashboard.market_dashboard_alias import payload_hash, snapshot_parity_contract
from app.dashboard.multi_market_dashboard import render_snapshot_archive_page, render_tw_window_report
from app.dashboard.public_latest_sync import synchronize_admitted_latest
from app.dashboard.window_snapshot_archive import resolve_snapshots, same_window_change, write_snapshot
from app.reports.delivery_provenance import build_delivery_provenance
from app.runtime.operations_provenance import build_operations_provenance
from app.pipelines import pre_open_pipeline as pipeline_module
from app.reports.tw_pre_open_structured import aggregate, build_card, render_email, render_line, validate_payload

SYMBOLS = ["2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409"]


def fixture_payload() -> dict:
    cards = []
    for index, symbol in enumerate(SYMBOLS):
        cards.append(build_card(
            symbol=symbol,
            name=f"測試標的 {index + 1}",
            trading_date="2099-07-17",
            indicator={"date": "2099-07-16", "close": 100 + index, "trend": "偏多" if index < 4 else "整理"},
            adr={"status": "中性", "market_summary": "隔夜市場可用"},
            news=[{"summary": "無新增重大事件"}],
            chip={"status": "籌碼穩定"},
            score={"total_score": 76 - index * 4, "rating": "A" if index < 3 else "B", "action": "觀察切入" if index < 5 else "避免追價"},
            analysis={"entry_condition": "開盤量價確認", "entry_zone": "100-101", "stop": "98", "target": "105", "risk_reward": "2.0"},
            missing_fields=["fundamental"] if index == 7 else [],
            generated_at="2099-07-17T07:06:00+08:00",
        ))
    summary = aggregate(cards, SYMBOLS)
    return {
        "schema_version": "tw_window_snapshot_payload_v1",
        "runtime_provenance": "scheduled_production",
        "market": "TW",
        "window": "pre_open_0700",
        "effective_trading_date": "2099-07-17",
        "effective_batch_time": "2099-07-17T07:00:00+08:00",
        "generated_at": "2099-07-17T07:06:00+08:00",
        "tracking_stock_count": 9,
        "tracking_symbols": SYMBOLS,
        "structured_card_count": 9,
        "rendered_card_count": 9,
        "structured_pre_open_cards": cards,
        "cards": cards,
        "pre_open_summary": summary,
    }


def validate() -> dict:
    payload = fixture_payload()
    canonical_url = "/dashboard/archive/tw/pre_open_0700/latest/index.html"
    email = render_email(payload, canonical_url)
    line = render_line(payload, canonical_url)
    with tempfile.TemporaryDirectory(prefix="ai184-tw0700-") as temporary:
        temporary_root = Path(temporary)
        archive = temporary_root / "archive"
        runtime_path = temporary_root / "runtime" / "pre_open_0700_latest.json"
        original_runtime_path = pipeline_module.PRE_OPEN_RUNTIME_PATH
        try:
            pipeline_module.PRE_OPEN_RUNTIME_PATH = runtime_path
            runtime_payload = pipeline_module._write_pre_open_runtime(
                {"pipeline_run_id": "ai184-controlled-no-send", "run_date": "2099-07-17"},
                payload["structured_pre_open_cards"],
                SYMBOLS,
            )
        finally:
            pipeline_module.PRE_OPEN_RUNTIME_PATH = original_runtime_path
        payload.update({
            key: runtime_payload[key]
            for key in (
                "tracking_stock_count", "tracking_symbols", "structured_card_count",
                "rendered_card_count", "structured_pre_open_cards", "cards", "pre_open_summary",
            )
        })
        admission = write_snapshot(
            archive,
            market="TW",
            window="pre_open_0700",
            effective_trading_date="2099-07-17",
            generated_at="2099-07-17T07:06:00+08:00",
            source_payload=payload,
            status="completed",
            run_kind="scheduled",
            run_id="ai184-controlled-no-send",
            effective_batch_time="2099-07-17T07:00:00+08:00",
        )
        snapshot = resolve_snapshots(archive, "TW", "pre_open_0700").latest or {}
        dashboard = render_tw_window_report("pre_open_0700", snapshot.get("payload", {}))
        archive_html = render_snapshot_archive_page(
            "TW", "pre_open_0700", "latest", snapshot, same_window_change(snapshot, None)
        )
        original_sync_archive = sync_module.WINDOW_SNAPSHOT_ARCHIVE
        original_dashboard_archive = dashboard_module.WINDOW_SNAPSHOT_ARCHIVE
        try:
            sync_module.WINDOW_SNAPSHOT_ARCHIVE = archive
            dashboard_module.WINDOW_SNAPSHOT_ARCHIVE = archive
            sync = synchronize_admitted_latest(
                market="TW", window="pre_open_0700",
                static_root=temporary_root / "public",
                output_dir=temporary_root / "build",
            )
            public_archive_html = (temporary_root / "public/dashboard/archive/tw/pre_open_0700/latest/index.html").read_text(encoding="utf-8")
            market_dashboard_html = (temporary_root / "public/dashboard/tw/index.html").read_text(encoding="utf-8")
        finally:
            sync_module.WINDOW_SNAPSHOT_ARCHIVE = original_sync_archive
            dashboard_module.WINDOW_SNAPSHOT_ARCHIVE = original_dashboard_archive
        email_provenance = build_delivery_provenance(
            market="TW", window="pre_open_0700", trading_date="2099-07-17",
            snapshot=snapshot, canonical_url=canonical_url, channel="email", content=email,
            delivery_result="dry_run_not_sent", delivery_attempted=False,
        )
        line_provenance = build_delivery_provenance(
            market="TW", window="pre_open_0700", trading_date="2099-07-17",
            snapshot=snapshot, canonical_url=canonical_url, channel="line", content=line,
            delivery_result="dry_run_not_sent", delivery_attempted=False,
        )
        operations = build_operations_provenance(
            market="TW", window="pre_open_0700", runtime_status="completed",
            runtime_trading_date="2099-07-17", snapshot=snapshot, public_sync=sync,
            email_result="dry_run_not_sent", line_result="dry_run_not_sent",
        )
        temporary_runtime_written = runtime_path.is_file()
    identity = snapshot_parity_contract(snapshot) or {}
    checks = {
        "payload_valid": validate_payload(payload) == [],
        "tracking_9": payload["tracking_stock_count"] == 9,
        "structured_cards_9": len(payload["structured_pre_open_cards"]) == 9,
        "unique_symbols": len({card["symbol"] for card in payload["structured_pre_open_cards"]}) == 9,
        "partial_semantics": payload["structured_pre_open_cards"][7]["availability_status"] == "partial",
        "admitted": admission.get("written") is True,
        "identity_hash": identity.get("payload_hash") == payload_hash(snapshot.get("payload", {})),
        "dashboard_cards_9": dashboard.count("tw-pre-open-structured-card") == 9,
        "archive_cards_9": archive_html.count("tw-pre-open-structured-card") == 9,
        "rendered_symbol_parity": all(f'data-symbol="{symbol}"' in archive_html for symbol in SYMBOLS),
        "temporary_runtime_written": temporary_runtime_written,
        "runtime_contract": runtime_payload.get("schema_version") == "tw_pre_open_decision_runtime_v1" and runtime_payload.get("runtime_provenance") == "scheduled_production",
        "temporary_public_verified": sync.get("status") == "verified",
        "public_archive_cards_9": public_archive_html.count("tw-pre-open-structured-card") == 9,
        "market_dashboard_cards_9": market_dashboard_html.count("tw-pre-open-structured-card") == 9,
        "count_marker": 'data-tracking-stock-count="9" data-rendered-card-count="9"' in archive_html,
        "email_decision_content": all(marker in email for marker in ("主要交易機會", "觀察等待", "暫不交易", "避免追價", canonical_url)),
        "line_decision_content": all(marker in line for marker in ("主要交易機會", "觀察等待", "暫不交易", "避免追價", "資料覆蓋", canonical_url)) and "Top 3" not in line,
        "no_sample_fixture": not any(marker in archive_html.lower() for marker in ("樣本資料", "contract validation", "fixture card")),
        "no_python_repr": "datetime.date(" not in archive_html and "datetime.datetime(" not in archive_html,
        "no_unsafe_financial_unit": "usd 4103.9b" not in archive_html.lower(),
        "no_cross_window_content": 'data-window="intraday_1305"' not in archive_html and 'data-window="pre_close_1335"' not in archive_html,
        "notification_source_parity": email_provenance["source_payload_hash"] == line_provenance["source_payload_hash"] == identity.get("payload_hash"),
        "operations_counts": operations.get("tracking_stock_count") == operations.get("structured_card_count") == operations.get("rendered_card_count") == 9,
        "operations_structured_valid": operations.get("structured_payload_status") == "valid",
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "snapshot_id": snapshot.get("snapshot_id"),
        "payload_hash": identity.get("payload_hash"),
        "temporary_public_status": sync.get("status"),
        "tracking_stock_count": 9,
        "rendered_card_count": archive_html.count("tw-pre-open-structured-card"),
        "email_attempted": False,
        "line_attempted": False,
        "production_publish": False,
        "production_archive_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
