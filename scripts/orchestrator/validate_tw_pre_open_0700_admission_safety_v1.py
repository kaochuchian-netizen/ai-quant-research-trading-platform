#!/usr/bin/env python3
"""Ensure incomplete TW 07:00 structured payloads fail closed."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard.window_snapshot_archive import resolve_snapshots, write_snapshot
from app.reports.tw_pre_open_structured import aggregate, build_card
from scripts.orchestrator.validate_tw_pre_open_0700_structured_payload_v1 import SYMBOLS, fixture_payload


def attempt(root: Path, payload: dict, run_id: str) -> dict:
    return write_snapshot(
        root, market="TW", window="pre_open_0700", effective_trading_date="2099-07-17",
        generated_at="2099-07-17T07:06:00+08:00", source_payload=payload,
        status="completed", run_kind="scheduled", run_id=run_id,
        effective_batch_time="2099-07-17T07:00:00+08:00",
    )


def validate() -> dict:
    cases = {}
    with tempfile.TemporaryDirectory(prefix="ai184-admission-") as temporary:
        root = Path(temporary)
        cards_zero = fixture_payload()
        cards_zero["structured_pre_open_cards"] = []
        cards_zero["cards"] = []
        cards_zero["structured_card_count"] = 0
        cards_zero["rendered_card_count"] = 0
        cases["tracking_9_cards_0"] = attempt(root, cards_zero, "cards-zero")

        duplicate = fixture_payload()
        duplicate["structured_pre_open_cards"][-1] = dict(duplicate["structured_pre_open_cards"][0])
        duplicate["cards"] = duplicate["structured_pre_open_cards"]
        cases["duplicate_symbol"] = attempt(root, duplicate, "duplicate")

        wrong_order = fixture_payload()
        wrong_order["tracking_symbols"] = list(reversed(SYMBOLS))
        cases["symbol_order_mismatch"] = attempt(root, wrong_order, "order")

        wrong_window = fixture_payload()
        wrong_window["structured_pre_open_cards"][0]["window"] = "intraday_1305"
        wrong_window["cards"] = wrong_window["structured_pre_open_cards"]
        cases["wrong_window_card"] = attempt(root, wrong_window, "wrong-window")

        fixture = fixture_payload()
        fixture["fixture"] = True
        cases["fixture"] = attempt(root, fixture, "fixture")

        valid = attempt(root, fixture_payload(), "valid")
        partial = fixture_payload()
        partial["structured_pre_open_cards"][0] = build_card(
            symbol=SYMBOLS[0], name="partial", trading_date="2099-07-17",
            indicator={"date": "2099-07-16", "close": 100, "trend": "整理"},
            adr={}, news=[], chip={}, score={"total_score": 60, "rating": "B", "action": "中性觀察"},
            analysis={}, missing_fields=["adr", "news", "chip"],
            generated_at="2099-07-17T07:06:00+08:00",
        )
        partial["cards"] = partial["structured_pre_open_cards"]
        partial["pre_open_summary"] = aggregate(partial["structured_pre_open_cards"], SYMBOLS)
        partial_admission = attempt(Path(temporary) / "partial", partial, "partial")

        stability_root = Path(temporary) / "stability"
        baseline = attempt(stability_root, fixture_payload(), "baseline")
        baseline_id = (resolve_snapshots(stability_root, "TW", "pre_open_0700").latest or {}).get("snapshot_id")
        rejected_newer = fixture_payload()
        rejected_newer["effective_trading_date"] = "2099-07-18"
        rejected_newer["structured_pre_open_cards"] = []
        rejected_newer["cards"] = []
        rejected_newer["structured_card_count"] = 0
        rejected_newer["rendered_card_count"] = 0
        rejected_newer_result = write_snapshot(
            stability_root, market="TW", window="pre_open_0700", effective_trading_date="2099-07-18",
            generated_at="2099-07-18T07:06:00+08:00", source_payload=rejected_newer,
            status="completed", run_kind="scheduled", run_id="rejected-newer",
            effective_batch_time="2099-07-18T07:00:00+08:00",
        )
        stable_latest_id = (resolve_snapshots(stability_root, "TW", "pre_open_0700").latest or {}).get("snapshot_id")
    checks = {
        name: result.get("written") is False
        for name, result in cases.items()
    }
    checks["valid_admitted"] = valid.get("written") is True
    checks["partial_retained_and_admitted"] = partial_admission.get("written") is True and len(partial["structured_pre_open_cards"]) == 9
    checks["structured_reason"] = cases["tracking_9_cards_0"].get("reason") == "structured_pre_open_payload_invalid"
    checks["rejected_latest_unchanged"] = baseline.get("written") is True and rejected_newer_result.get("written") is False and baseline_id == stable_latest_id
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "rejections": {name: value.get("reason") for name, value in cases.items()},
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
