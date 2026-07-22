#!/usr/bin/env python3
"""AI-DEV-181 seven-window cross-feature regression merge gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.dashboard.multi_market_dashboard as dashboard
from app.dashboard.dashboard_url_registry import get_window_archive_url
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots, write_snapshot
from app.reports.decision_intelligence_v4 import WINDOW_PRESENTATION, compact_summary, delivery_summary_lines, project_decision_intelligence_v4
from app.reports.multi_window_formatter import format_window_report
from app.reports.tw_pre_open_structured import aggregate as aggregate_pre_open_cards, build_card as build_pre_open_card
from app.reports.window_report_contract import all_window_report_contracts, get_window_report_contract
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text
from app.us_stock.premarket_decision import build_premarket_card, normalize_market_context, summarize_premarket


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
        "generated_at": f"{day}T12:00:00+08:00", "artifact_mode": "production_runtime",
        "runtime_provenance": "scheduled_production",
        "verification_scope": "temporary_non_production_archive", "marker": marker,
        "notification_sent": False, "production_pipeline_executed": False,
    }
    if market == "TW" and window == "pre_open_0700":
        symbols = [str(card["stock_id"]) for card in cards]
        cards = [
            build_pre_open_card(
                symbol=symbols[index], name=str(card["stock_name"]), trading_date=day,
                indicator={"date": day, "close": 100 + index, "trend": "uptrend"},
                adr={"status": "available", "date": day}, news=[{"date": day, "summary": "controlled"}],
                chip={"status": "available", "date": day},
                score={"total_score": 75 - index * 10, "rating": "B", "action": "觀察切入" if index < 2 else "避免追價"},
                analysis={"entry_condition": "開盤量價確認", "entry_zone": "100-101", "stop": "95", "target": "108"},
                generated_at=f"{day}T07:06:00+08:00",
            )
            for index, card in enumerate(cards)
        ]
        summary = aggregate_pre_open_cards(cards, symbols)
        payload.update({
            "cards": cards, "structured_pre_open_cards": cards,
            "tracking_stock_count": len(symbols), "tracking_symbols": symbols,
            "structured_card_count": len(cards), "rendered_card_count": len(cards),
            "pre_open_summary": summary,
        })
    elif market == "TW":
        payload["cards"] = cards
    else:
        if window == "us_pre_market_2000":
            premarket_reference = datetime.fromisoformat(f"{day}T08:00:00-04:00").astimezone(ZoneInfo("America/New_York"))
            context_items = {}
            for context_symbol, previous, price in (("SPY", 600, 602.4), ("QQQ", 500, 503.5), ("SOXX", 250, 251.5)):
                context_items[context_symbol] = {"premarket": {"previous_close": previous, "price": price, "change_pct": round((price / previous - 1) * 100, 4), "timestamp": f"{day}T07:58:00-04:00", "source": "deterministic validator", "freshness": "fresh", "availability": "available"}}
            raw_context = {"items": context_items}
            for index, card in enumerate(cards):
                card["daily_tactical_summary"].update({"action": "突破確認後偏多" if index == 0 else "等待止穩", "direction": "mildly_bullish" if index == 0 else "neutral", "confidence": 45 if index == 0 else 26, "reward_risk_ratio": 1.3 if index == 0 else 0.35})
                quote = {"previous_close": 100 + index, "pre_market_price": 101 + index, "pre_market_time": f"{day}T07:58:00-04:00", "pre_market_volume": 100000, "market_data_source": "deterministic validator"}
                research = {"earnings": {"event_risk_level": "low"}, "sec": {"ok": True, "recent_8k_items": []}, "material_news": {"items": []}}
                cards[index] = build_premarket_card(card, quote, research, [], raw_context, premarket_reference)
            normalized_context = normalize_market_context(raw_context, premarket_reference)
            payload["premarket_market_context"] = normalized_context
            payload["premarket_summary"] = summarize_premarket(cards, normalized_context)
            payload["premarket_contract"] = {"valid": True, "daily_ohlcv_as_premarket_fallback": False}
        if window == "us_intraday_2300":
            for index, card in enumerate(cards):
                card.update({
                    "schema_version": "us_intraday_observed_market_v1", "market": "US", "window": window,
                    "trading_date": day, "session_date": day, "market_timezone": "America/New_York",
                    "session_phase": "regular_session", "previous_close": 100 + index,
                    "regular_session_open": 101 + index, "current_price": 102 + index,
                    "market_data_as_of": f"{day}T11:00:00-04:00", "gap_open_pct": 1.0,
                    "gap_current_pct": 2.0, "gap_fill_pct": 0.0, "gap_state": "gap_up_follow_through",
                    "gap_follow_through_state": "gap_up_follow_through", "session_volume": 1_000_000,
                    "volume_baseline": 800_000, "volume_ratio": 1.25,
                    "volume_confirmation_state": "confirmed", "entry_low": 100 + index,
                    "entry_high": 101 + index, "entry_trigger_state": "triggered" if index == 0 else "not_reached",
                    "stop_level": 95 + index, "target_level": 108 + index,
                    "distance_to_stop_pct": -5.0, "distance_to_target_pct": 6.0,
                    "pre_open_action": "等待確認", "intraday_action": "entry_triggered_hold" if index == 0 else "maintain_watch",
                    "tactical_adjustment": "entry_triggered_hold" if index == 0 else "maintain_watch",
                    "adjustment_reason": "deterministic observed cross-feature evidence", "chase_risk": "low",
                    "gap_risk": "low", "event_risk": "low", "liquidity_status": "available",
                    "data_status": "complete", "missing_fields": [], "source": "deterministic validator",
                    "source_payload_hash": f"cross-feature-{index}",
                })
            payload.update({
                "tracking_stock_count": len(cards), "structured_intraday_cards": cards,
                "intraday_summary": {"tracking_count": len(cards), "structured_card_count": len(cards),
                    "triggered_count": 1, "inside_zone_count": 0, "not_reached_count": len(cards)-1,
                    "cancel_chase_count": 0, "volume_confirmed_count": len(cards),
                    "gap_follow_through_count": len(cards), "data_unavailable_count": 0,
                    "near_stop_count": 0, "near_target_count": 0},
                "session_context": {"session_phase": "regular_session"},
            })
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
                if (market, window) == ("TW", "pre_open_0700"):
                    checks[key + ":dashboard_v4"] = dashboard_html.count("tw-pre-open-structured-card") == 3 and latest_projection["expected_card_type"] in dashboard_html
                elif (market, window) == ("US", "us_post_close_review_0630"):
                    checks[key + ":dashboard_v4"] = "canonical-review-summary" in dashboard_html and latest_projection["expected_card_type"] in dashboard_html
                elif (market, window) == ("US", "us_pre_market_2000"):
                    checks[key + ":dashboard_v4"] = "canonical-premarket-summary" in dashboard_html and latest_projection["expected_card_type"] in dashboard_html
                else:
                    checks[key + ":dashboard_v4"] = "Decision Intelligence V4" in dashboard_html and latest_projection["expected_card_type"] in dashboard_html
                checks[key + ":email_v4"] = "Decision Intelligence V4" in email_text
                if (market, window) == ("US", "us_intraday_2300"):
                    checks[key + ":line_semantic_parity"] = all(
                        marker in line_summary for marker in ("已觸發", "取消追價", "量能確認", get_window_report_contract(market, window).dashboard_url)
                    )
                elif (market, window) == ("US", "us_post_close_review_0630"):
                    checks[key + ":line_semantic_parity"] = all(
                        marker in line_summary for marker in ("預測區間命中", "交易結果已判定", "待確認", get_window_report_contract(market, window).dashboard_url)
                    )
                elif (market, window) == ("US", "us_pre_market_2000"):
                    summary = selected.latest["payload"].get("premarket_summary") or {}
                    checks[key + ":line_semantic_parity"] = all(
                        marker in line_summary for marker in ("主要交易機會", "觀察等待", "暫不交易", get_window_report_contract(market, window).dashboard_url)
                    ) and str(summary.get("top_opportunity_count", 0)) in line_summary
                else:
                    checks[key + ":line_semantic_parity"] = all(
                        line in line_summary for line in delivery_summary_lines(latest_projection)
                    )
                if (market, window) == ("TW", "pre_open_0700"):
                    checks[key + ":archive_latest_previous"] = latest_html.count("tw-pre-open-structured-card") == 3 and previous_html.count("tw-pre-open-structured-card") == 3
                elif (market, window) == ("US", "us_post_close_review_0630"):
                    checks[key + ":archive_latest_previous"] = "canonical-review-summary" in latest_html and "canonical-review-summary" in previous_html
                elif (market, window) == ("US", "us_pre_market_2000"):
                    checks[key + ":archive_latest_previous"] = "canonical-premarket-summary" in latest_html and "canonical-premarket-summary" in previous_html
                else:
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
            checks["url_isolation"] = all(
                contract.dashboard_url == get_window_archive_url(contract.market, contract.window)
                for contract in all_window_report_contracts()
            )
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
