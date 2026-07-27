#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.orchestrator.tw_four_window_validation_fixture import SYMBOLS, payloads


def validate() -> dict[str, object]:
    payload = payloads()
    maps = {window: {(card.get("symbol") or card.get("stock_id")): card for card in item["cards"]} for window, item in payload.items()}
    checks: dict[str, bool] = {}
    checks["symbol_sets"] = all(set(cards) == set(SYMBOLS) for cards in maps.values())
    checks["setup_identity"] = all(len({maps[window][symbol].get("setup_id") for window in maps}) == 1 for symbol in SYMBOLS)
    checks["parent_identity"] = all(
        maps[window][symbol].get("parent_setup_id") == maps["pre_open_0700"][symbol].get("setup_id")
        for window in ("intraday_1305", "pre_close_1335", "post_close_1500") for symbol in SYMBOLS
    )
    active_symbols = {
        symbol for symbol in SYMBOLS
        if maps["pre_open_0700"][symbol].get("entry_readiness") == "entry_ready"
    }
    watch_symbols = {
        symbol for symbol in SYMBOLS
        if maps["pre_open_0700"][symbol].get("entry_readiness") == "watch"
    }
    checks["active_levels_stable"] = all(
        len({tuple(maps[window][symbol].get(key) for key in ("entry_low", "entry_high", "stop_level", "target_1")) for window in maps}) == 1
        for symbol in active_symbols
    )
    checks["watch_not_promoted"] = all(
        maps[window][symbol].get("plan_status") == "watch"
        and maps[window][symbol].get("entry_low") is None
        and maps[window][symbol].get("stop_level") is None
        for symbol in watch_symbols for window in ("intraday_1305", "pre_close_1335", "post_close_1500")
    )
    return {"ok": all(checks.values()), "checks": checks, "symbols": SYMBOLS}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
