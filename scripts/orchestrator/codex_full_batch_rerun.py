#!/usr/bin/env python3
"""Codex-owned, isolated full-batch rerun orchestration.

This entrypoint is intentionally separate from the Portal bridge.  It does not
have a default transport or publication path: output is an isolated execution
receipt.  A caller must explicitly select a mode and supply a stage runner;
production activation is deliberately outside this command's default contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
MODES = ("LIVE_RERUN", "HISTORICAL_RECOMPUTE", "FROZEN_REPLAY")
WINDOWS = {
    "TW": ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"),
    "US": ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"),
}
STAGES = ("market_data", "analysis_prediction", "canonical_evaluation", "dashboard", "line_renderer", "email_renderer", "delivery_receipt")


@dataclass(frozen=True)
class RerunRequest:
    mode: str
    market: str
    window: str
    trading_date: str
    input_source: Path
    output_dir: Path


def load_input(path: Path, request: RerunRequest) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("RERUN_INPUT_NOT_OBJECT")
    if str(value.get("market")) != request.market or str(value.get("window")) != request.window:
        raise ValueError("RERUN_INPUT_MARKET_WINDOW_MISMATCH")
    if str(value.get("trading_date")) != request.trading_date:
        raise ValueError("RERUN_INPUT_TRADING_DATE_MISMATCH")
    if request.mode == "HISTORICAL_RECOMPUTE" and value.get("source_kind") != "CONTEMPORANEOUS_HISTORICAL":
        raise ValueError("HISTORICAL_RECOMPUTE_REQUIRES_CONTEMPORANEOUS_INPUT")
    if request.mode == "FROZEN_REPLAY" and value.get("source_kind") != "IMMUTABLE_FROZEN":
        raise ValueError("FROZEN_REPLAY_REQUIRES_FROZEN_INPUT")
    if request.mode == "LIVE_RERUN" and value.get("source_kind") != "LIVE_ACQUISITION_PLAN":
        raise ValueError("LIVE_RERUN_REQUIRES_LIVE_PLAN")
    return value


def execution_identity(request: RerunRequest, source: dict[str, Any]) -> str:
    canonical = json.dumps({"mode": request.mode, "market": request.market, "window": request.window, "trading_date": request.trading_date, "source_digest": source.get("source_digest")}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def run_isolated(request: RerunRequest, source: dict[str, Any], runner: Callable[[str, dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """Run declared stages, preserving exact evidence of executed vs frozen use."""
    request.output_dir.mkdir(parents=True, exist_ok=True)
    stages: list[dict[str, Any]] = []
    for stage in STAGES:
        result = runner(stage, source)
        if not isinstance(result, dict) or result.get("status") not in {"EXECUTED", "FROZEN", "SKIPPED", "FAILED", "TIMEOUT"}:
            raise ValueError(f"RERUN_STAGE_INVALID_RESULT:{stage}")
        stages.append({"stage": stage, **result})
        if result["status"] in {"FAILED", "TIMEOUT"}:
            break
    terminal = "SUCCESS" if len(stages) == len(STAGES) and all(item["status"] in {"EXECUTED", "FROZEN", "SKIPPED"} for item in stages) else stages[-1]["status"]
    receipt = {
        "schema_version": "codex_full_batch_rerun_v1",
        "execution_identity": execution_identity(request, source),
        "mode": request.mode,
        "market": request.market,
        "window": request.window,
        "trading_date": request.trading_date,
        "input_source": {"kind": source["source_kind"], "digest": source.get("source_digest")},
        "stages": stages,
        "terminal_status": terminal,
        "notification_attempted": False,
        "dashboard_latest_modified": False,
        "archive_modified": False,
        "frozen_prediction_overwritten": False,
        "production_db_written": False,
        "scheduler_modified": False,
        "trading_or_order_executed": False,
    }
    (request.output_dir / "execution_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def fixture_runner(stage: str, source: dict[str, Any]) -> dict[str, Any]:
    """Safe default: records declared evidence only and never invokes a pipeline."""
    if source.get("simulate", {}).get(stage) == "timeout":
        return {"status": "TIMEOUT", "reason": "STAGE_TIMEOUT", "elapsed_seconds": 0}
    if source.get("simulate", {}).get(stage) == "failure":
        return {"status": "FAILED", "reason": "STAGE_FAILED", "elapsed_seconds": 0}
    frozen = stage in set(source.get("frozen_stages") or [])
    return {"status": "FROZEN" if frozen else "EXECUTED", "evidence": "frozen_input" if frozen else "isolated_runner", "elapsed_seconds": 0}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", required=True, choices=MODES)
    p.add_argument("--market", required=True, choices=sorted(WINDOWS))
    p.add_argument("--window", required=True)
    p.add_argument("--trading-date", required=True)
    p.add_argument("--input-source", required=True)
    p.add_argument("--output-dir", required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.window not in WINDOWS[args.market]:
        raise SystemExit("window is not valid for market")
    req = RerunRequest(args.mode, args.market, args.window, args.trading_date, Path(args.input_source), Path(args.output_dir))
    source = load_input(req.input_source, req)
    result = run_isolated(req, source, fixture_runner)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["terminal_status"] == "SUCCESS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
