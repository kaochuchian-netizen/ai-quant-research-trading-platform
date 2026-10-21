#!/usr/bin/env python3
"""Codex-owned isolated rerun orchestration.

This command never simulates an executed pipeline stage. A stage is either
executed through an isolation-aware adapter, explicitly backed by immutable
evidence, or blocked. The legacy production entrypoints are registered for
traceability but cannot be invoked here until they enforce isolated outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MODES = ("LIVE_RERUN", "HISTORICAL_RECOMPUTE", "FROZEN_REPLAY")
WINDOWS = {
    "TW": ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"),
    "US": ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"),
}
STAGES = (
    "market_data", "analysis_prediction", "canonical_evaluation", "dashboard",
    "line_renderer", "email_renderer", "delivery_receipt",
)

# Established formal entrypoints. They are declarations only: no current one
# accepts a verified isolated output root plus no-write contract.
OFFICIAL_PIPELINE_BINDINGS = {
    ("TW", window): {
        "entrypoint": "scripts/orchestrator/approved_pre_open_delivery.py",
        "pipeline": "scripts/run_pipeline.py",
        "isolation_status": "UNSUPPORTED",
    }
    for window in WINDOWS["TW"]
} | {
    ("US", window): {
        "entrypoint": "scripts/orchestrator/approved_us_stock_delivery.py",
        "isolation_status": "UNSUPPORTED",
    }
    for window in WINDOWS["US"]
}


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
    for key, expected in (("market", request.market), ("window", request.window), ("trading_date", request.trading_date)):
        if str(value.get(key)) != expected:
            raise ValueError(f"RERUN_INPUT_{key.upper()}_MISMATCH")
    source_kinds = {
        "LIVE_RERUN": "LIVE_ACQUISITION_PLAN",
        "HISTORICAL_RECOMPUTE": "CONTEMPORANEOUS_HISTORICAL",
        "FROZEN_REPLAY": "IMMUTABLE_FROZEN",
    }
    if value.get("source_kind") != source_kinds[request.mode]:
        raise ValueError(f"{request.mode}_INPUT_KIND_REJECTED")
    stages = value.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(STAGES):
        raise ValueError("RERUN_STAGE_MANIFEST_INCOMPLETE")
    return value


def execution_identity(request: RerunRequest, source: dict[str, Any]) -> str:
    raw = json.dumps({
        "mode": request.mode, "market": request.market, "window": request.window,
        "trading_date": request.trading_date, "source_digest": source.get("source_digest"),
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _under(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _blocked_official_pipeline(stage: str, request: RerunRequest) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "reason": "OFFICIAL_PIPELINE_ISOLATION_UNSUPPORTED",
        "stage": stage,
        "official_binding": OFFICIAL_PIPELINE_BINDINGS[(request.market, request.window)],
        "executed": False,
    }


def execute_stage(stage: str, spec: dict[str, Any], *, request: RerunRequest) -> dict[str, Any]:
    """Execute only an adapter which declares the verifiable isolation contract."""
    if spec.get("kind") == "frozen_evidence":
        evidence_id = spec.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id:
            return {"status": "FAILED", "reason": "FROZEN_EVIDENCE_ID_MISSING"}
        return {"status": "FROZEN", "evidence_id": evidence_id, "executed": False}
    if spec.get("kind") == "official_pipeline":
        return _blocked_official_pipeline(stage, request)
    if spec.get("kind") != "isolated_adapter":
        return {"status": "FAILED", "reason": "ISOLATED_STAGE_ADAPTER_REQUIRED"}
    if spec.get("isolation_contract") != "ISOLATED_STAGE_ADAPTER_V1":
        return {"status": "FAILED", "reason": "ISOLATION_CONTRACT_REQUIRED"}
    command = spec.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        return {"status": "FAILED", "reason": "STAGE_COMMAND_REQUIRED"}
    forbidden = {
        "scripts/run_pipeline.py",
        "scripts/orchestrator/approved_pre_open_delivery.py",
        "scripts/orchestrator/approved_us_stock_delivery.py",
    }
    if forbidden.intersection(command):
        return _blocked_official_pipeline(stage, request)
    timeout = int(spec.get("timeout_seconds", 180))
    if timeout < 1 or timeout > 1800:
        return {"status": "FAILED", "reason": "STAGE_TIMEOUT_INVALID"}
    expected = spec.get("expected_output")
    if not isinstance(expected, str) or not expected:
        return {"status": "FAILED", "reason": "STAGE_EXPECTED_OUTPUT_REQUIRED"}
    target = (request.output_dir / expected).resolve()
    if not _under(request.output_dir, target):
        return {"status": "FAILED", "reason": "STAGE_OUTPUT_ESCAPE"}

    env = {
        "PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT),
        "STOCK_AI_RERUN_OUTPUT_DIR": str(request.output_dir),
        "STOCK_AI_NO_SEND": "1", "STOCK_AI_NO_LATEST": "1",
        "STOCK_AI_NO_ARCHIVE": "1", "STOCK_AI_NO_DB_WRITE": "1",
        "STOCK_AI_NO_TRADING": "1",
    }
    started = time.monotonic()
    try:
        proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "reason": "STAGE_TIMEOUT", "elapsed_seconds": round(time.monotonic() - started, 3)}
    result = {
        "status": "EXECUTED" if proc.returncode == 0 and target.is_file() else "FAILED",
        "returncode": proc.returncode, "elapsed_seconds": round(time.monotonic() - started, 3),
        "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest(),
        "output": str(target), "executed": True,
    }
    if result["status"] == "FAILED":
        result["reason"] = "STAGE_COMMAND_FAILED" if proc.returncode else "STAGE_OUTPUT_MISSING"
    return result


def run_isolated(request: RerunRequest, source: dict[str, Any]) -> dict[str, Any]:
    request.output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for stage in STAGES:
        spec = source["stages"][stage]
        row = execute_stage(stage, spec, request=request) if isinstance(spec, dict) else {"status": "FAILED", "reason": "STAGE_SPEC_INVALID"}
        rows.append({"stage": stage, **row})
        if row["status"] in {"BLOCKED", "FAILED", "TIMEOUT"}:
            break
    terminal = "SUCCESS" if len(rows) == len(STAGES) and all(row["status"] in {"EXECUTED", "FROZEN"} for row in rows) else rows[-1]["status"]
    receipt = {
        "schema_version": "codex_full_batch_rerun_v3",
        "execution_identity": execution_identity(request, source),
        "mode": request.mode, "market": request.market, "window": request.window, "trading_date": request.trading_date,
        "input_source": {"kind": source["source_kind"], "digest": source.get("source_digest")},
        "official_pipeline_binding": OFFICIAL_PIPELINE_BINDINGS[(request.market, request.window)],
        "stages": rows, "terminal_status": terminal,
        "notification_attempted": False, "dashboard_latest_modified": False, "archive_modified": False,
        "frozen_prediction_overwritten": False, "production_db_written": False,
        "scheduler_modified": False, "trading_or_order_executed": False,
    }
    (request.output_dir / "execution_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--market", required=True, choices=sorted(WINDOWS))
    parser.add_argument("--window", required=True)
    parser.add_argument("--trading-date", required=True)
    parser.add_argument("--input-source", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.window not in WINDOWS[args.market]:
        raise SystemExit("window is not valid for market")
    request = RerunRequest(args.mode, args.market, args.window, args.trading_date, Path(args.input_source), Path(args.output_dir))
    result = run_isolated(request, load_input(request.input_source, request))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["terminal_status"] == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
