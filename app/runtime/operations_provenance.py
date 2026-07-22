"""Full diagnostic provenance consumed by Operations Center summaries."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def build_operations_provenance(*, market: str, window: str, runtime_status: str, runtime_trading_date: str, snapshot: dict[str, Any], public_sync: dict[str, Any], email_result: str, line_result: str) -> dict[str, Any]:
    archive_observed = ((public_sync.get("public_archive_verification") or {}).get("observed_identity"))
    dashboard_observed = ((public_sync.get("market_dashboard_verification") or {}).get("observed_identity"))
    result = {
        "schema_version": "operations_window_provenance_v1", "market": market, "window": window,
        "latest_runtime_status": runtime_status, "latest_runtime_trading_date": runtime_trading_date,
        "latest_admitted_snapshot_id": snapshot.get("snapshot_id"),
        "latest_admitted_trading_date": snapshot.get("effective_trading_date"),
        "revision": int(snapshot.get("revision") or 0),
        "payload_hash": (public_sync.get("source_payload_hash") or (public_sync.get("expected_identity") or {}).get("payload_hash")),
        "public_archive_observed_identity": archive_observed,
        "market_dashboard_observed_identity": dashboard_observed,
        "public_parity_status": public_sync.get("status") or "not_attempted",
        "email_delivery_result": email_result, "line_delivery_result": line_result,
    }
    if market.upper() == "TW" and window == "pre_open_0700":
        payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
        result.update({
            "tracking_stock_count": int(payload.get("tracking_stock_count") or 0),
            "structured_card_count": int(payload.get("structured_card_count") or 0),
            "rendered_card_count": int(payload.get("rendered_card_count") or 0),
            "structured_payload_status": (
                "valid"
                if int(payload.get("tracking_stock_count") or 0) > 0
                and int(payload.get("tracking_stock_count") or 0)
                == int(payload.get("structured_card_count") or 0)
                == int(payload.get("rendered_card_count") or 0)
                else "structured_payload_invalid"
            ),
        })
    if market.upper() == "TW" and window in {"intraday_1305", "pre_close_1335", "post_close_1500"}:
        payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
        summary = payload.get("tw_window_summary") if isinstance(payload.get("tw_window_summary"), dict) else {}
        result.update({
            "tracking_count": int(summary.get("tracking_count") or payload.get("tracking_stock_count") or 0),
            "structured_card_count": int(summary.get("structured_card_count") or 0),
            "data_complete_count": int(summary.get("data_complete_count") or 0),
            "data_partial_count": int(summary.get("data_partial_count") or 0),
            "data_unavailable_count": int(summary.get("data_unavailable_count") or 0),
            "triggered_count": int(summary.get("triggered_count") or 0),
            "invalidated_count": int(summary.get("invalidated_count") or 0),
            "still_actionable_count": int(summary.get("still_actionable_count") or 0),
            "volume_confirmed_count": int(summary.get("volume_confirmed_count") or 0),
            "near_stop_count": int(summary.get("near_stop_count") or 0),
            "near_target_count": int(summary.get("near_target_count") or 0),
            "outcome_counts": summary.get("outcome_counts") or {},
            "tw_structured_payload_status": (
                "valid" if int(summary.get("tracking_count") or 0) > 0
                and int(summary.get("tracking_count") or 0) == int(summary.get("structured_card_count") or 0)
                and int(summary.get("data_unavailable_count") or 0) < int(summary.get("tracking_count") or 0)
                else "partial_or_unavailable"
            ),
        })
    if market.upper() == "US" and window == "us_intraday_2300":
        payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
        summary = payload.get("intraday_summary") if isinstance(payload.get("intraday_summary"), dict) else {}
        result.update({
            "tracking_count": int(summary.get("tracking_count") or payload.get("tracking_stock_count") or 0),
            "structured_card_count": int(summary.get("structured_card_count") or 0),
            "market_data_complete_count": sum(
                card.get("data_status") == "complete"
                for card in payload.get("structured_intraday_cards", []) if isinstance(card, dict)
            ),
            "market_data_unavailable_count": int(summary.get("data_unavailable_count") or 0),
            "triggered_count": int(summary.get("triggered_count") or 0),
            "volume_confirmed_count": int(summary.get("volume_confirmed_count") or 0),
            "intraday_payload_status": (
                "valid" if int(summary.get("tracking_count") or 0) > 0
                and int(summary.get("tracking_count") or 0) == int(summary.get("structured_card_count") or 0)
                and int(summary.get("data_unavailable_count") or 0) < int(summary.get("tracking_count") or 0)
                else "intraday_payload_incomplete"
            ),
        })
    if market.upper() == "US" and window == "us_pre_market_2000":
        payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
        summary = payload.get("premarket_summary") if isinstance(payload.get("premarket_summary"), dict) else {}
        result.update({
            "premarket_summary": summary,
            "tracking_count": int(summary.get("tracking_count") or payload.get("tracking_stock_count") or 0),
            "top_opportunity_count": int(summary.get("top_opportunity_count") or 0),
            "actionable_count": int(summary.get("actionable_count") or 0),
            "watch_only_count": int(summary.get("watch_only_count") or 0),
            "no_trade_count": int(summary.get("no_trade_count") or 0),
            "premarket_available_count": int(summary.get("premarket_available_count") or 0),
            "premarket_payload_status": "valid" if payload.get("premarket_contract", {}).get("valid") is True else "partial_or_invalid",
        })
    if market.upper() == "US" and window == "us_post_close_review_0630":
        from app.reports.canonical_outcomes import aggregate_us_post_close_review
        payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
        cards = payload.get("structured_review_cards") if isinstance(payload.get("structured_review_cards"), list) else []
        result["review_summary"] = aggregate_us_post_close_review([card for card in cards if isinstance(card, dict)])
    return result

def write_operations_provenance(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    temporary.replace(path)
