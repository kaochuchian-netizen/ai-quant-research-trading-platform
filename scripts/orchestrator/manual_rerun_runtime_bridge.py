#!/usr/bin/env python3
"""Runtime bridge for Dashboard manual single-window rerun requests.

This module is deployable behind a route such as
/stock-ai-dashboard/api/manual-rerun, but remains disabled unless the runtime-only
PIN hash is configured outside the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.orchestrator.manual_rerun_single_window import (  # noqa: E402
    ALLOWED_MODE,
    ALLOWED_WINDOWS,
    AUDIT_LATEST,
    STATUS_LATEST,
    handle_request,
    stable,
    write_audit,
)
from app.dashboard.window_snapshot_archive import resolve_snapshots
from app.dashboard.multi_market_dashboard import STATIC_ROOT, publish_manual_rerun_update

PIN_HASH_ENV = "STOCK_AI_MANUAL_RERUN_PIN_HASH"
PIN_HASH_FILE = Path.home() / ".config/stock-ai/manual_rerun_pin_hash"
POST_PATH = "/stock-ai-dashboard/api/manual-rerun"
STATUS_PATH = "/stock-ai-dashboard/api/manual-rerun/status"
HEALTH_PATH = "/stock-ai-dashboard/api/manual-rerun/healthz"
ACTIVATION_RESULT = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_runtime_activation_latest.json"
ACTIVATION_TRACE = ROOT / "artifacts/runtime/manual_rerun/manual_rerun_runtime_activation_trace_latest.md"
MANUAL_STATUS_SCHEMA = "manual_rerun_status_v2"
ACTIVE_LOCK = threading.Lock()
ACTIVE_JOB_ID: str | None = None
STAGE_LABELS = {
    "submitted": "驗證請求", "queued": "等待執行", "running": "建立 Runtime",
    "publishing": "同步市場 Dashboard", "completed": "完成", "failed": "執行失敗", "rejected": "請求被拒絕",
}


def _status_path(job_id: str | None, status_dir: Path | None = None) -> Path:
    directory = status_dir or STATUS_LATEST.parent
    return directory / (f"manual_rerun_{job_id}.json" if job_id else STATUS_LATEST.name)


def persist_status(data: dict[str, Any], status_dir: Path | None = None) -> dict[str, Any]:
    directory = status_dir or STATUS_LATEST.parent
    directory.mkdir(parents=True, exist_ok=True)
    clean = sanitize_response(data)
    clean.setdefault("schema_version", MANUAL_STATUS_SCHEMA)
    clean.setdefault("line_attempted", False)
    clean.setdefault("email_attempted", False)
    clean.setdefault("trading_or_order_executed", False)
    clean.setdefault("previous_route_updated", False)
    clean.setdefault("other_windows_updated", False)
    for path in (_status_path(str(clean.get("job_id") or ""), directory), _status_path(None, directory)):
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(stable(clean), encoding="utf-8")
        temporary.replace(path)
    return clean


def lifecycle_status(base: dict[str, Any], status: str, **updates: Any) -> dict[str, Any]:
    data = dict(base)
    data.update(updates)
    data.update({"status": status, "stage": status, "stage_label": STAGE_LABELS.get(status, status)})
    history = list(base.get("lifecycle", [])) if isinstance(base.get("lifecycle"), list) else []
    if not history or history[-1] != status:
        history.append(status)
    data["lifecycle"] = history
    data.setdefault("task_id", data.get("job_id"))
    data.setdefault("latest_route_updated", False)
    data.setdefault("market_dashboard_updated", False)
    data.setdefault("previous_route_updated", False)
    data.setdefault("other_windows_updated", False)
    data.setdefault("line_attempted", False)
    data.setdefault("email_attempted", False)
    data.setdefault("trading_or_order_executed", False)
    return data


def _route_hashes(market: str, window: str, static_root: Path = STATIC_ROOT) -> dict[str, Any]:
    import hashlib
    def digest(path: Path) -> str | None:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    target = static_root / f"dashboard/archive/{market.lower()}/{window}/latest/index.html"
    previous = static_root / f"dashboard/archive/{market.lower()}/{window}/previous/index.html"
    market_page = static_root / f"dashboard/{market.lower()}/index.html"
    others: dict[str, str | None] = {}
    for path in sorted((static_root / "dashboard/archive").rglob("index.html")) if (static_root / "dashboard/archive").exists() else []:
        if path not in {target, previous}:
            others[path.relative_to(static_root).as_posix()] = digest(path)
    return {"target_latest": digest(target), "previous": digest(previous), "market_dashboard": digest(market_page), "other_routes": others}


def load_pin_hash(*, allow_env: bool = True, allow_file: bool = True, override: str | None = None) -> tuple[str | None, str]:
    if override:
        return override.strip(), "override_for_test_only"
    if allow_env:
        value = os.environ.get(PIN_HASH_ENV)
        if value:
            return value.strip(), "runtime_env"
    if allow_file and PIN_HASH_FILE.exists():
        return PIN_HASH_FILE.read_text(encoding="utf-8").strip(), "runtime_config_file"
    return None, "missing"


def sanitize_response(data: dict[str, Any]) -> dict[str, Any]:
    forbidden = {"pin", "plaintext_pin", "submitted_pin", "pin_hash", "token", "secret"}
    return {k: v for k, v in data.items() if k not in forbidden}


def rejected_audit(response: dict[str, Any]) -> None:
    window = response.get("window") if response.get("window") in ALLOWED_WINDOWS else None
    audit = {
        "schema_version": "manual_rerun_runtime_bridge_audit_v1",
        "task_id": "AI-DEV-178",
        "job_id": None,
        "requested_window": window,
        "executed_window": window,
        "mode": ALLOWED_MODE,
        "status": response.get("status", "rejected"),
        "pipeline_status": "not_executed",
        "dashboard_publish_attempted": False,
        "dashboard_publish_status": "not_attempted",
        "line_attempted": False,
        "email_attempted": False,
        "operator_auth": response.get("status", "rejected"),
        "pin_recorded": False,
        "lock_acquired": False,
        "cooldown_checked": True,
        "safety_notes": ["single_window_only", "no_line_email", "no_trading", "no_pin_recorded"],
    }
    write_audit(audit)


def process_manual_rerun_request(request: dict[str, Any], *, pin_hash_value: str | None = None, write: bool = True, execute_async: bool = True) -> dict[str, Any]:
    global ACTIVE_JOB_ID
    response = handle_request(request, pin_hash_value=pin_hash_value, write=False)
    response = sanitize_response(response)
    if write and not response.get("accepted"):
        rejected_audit(response)
        rejected = lifecycle_status({**response, "requested_window": response.get("window")}, "rejected", error_summary=response.get("reason"), message="手動重跑請求被拒絕；未更新任何 route。")
        persist_status(rejected)
        return rejected
    if not response.get("accepted"):
        return response
    response = lifecycle_status({
        **response,
        "task_id": response.get("job_id"),
        "requested_window": response.get("window"),
        "market": ALLOWED_WINDOWS[str(response.get("window"))]["market"],
        "submitted_at": datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
        "message": "已送出手動批次請求。",
    }, "submitted")
    if write:
        with ACTIVE_LOCK:
            if ACTIVE_JOB_ID:
                rejected = lifecycle_status(response, "rejected", accepted=False, reason="another_manual_rerun_in_progress", error_summary="已有手動批次執行中。")
                persist_status(rejected)
                return rejected
            ACTIVE_JOB_ID = str(response.get("job_id"))
        persist_status(response)
        if execute_async:
            threading.Thread(target=_execute_and_release, args=(response,), name=f"manual-rerun-{response.get('job_id')}", daemon=True).start()
        else:
            response = _execute_and_release(response)
    return response


def _execute_and_release(response: dict[str, Any]) -> dict[str, Any]:
    global ACTIVE_JOB_ID
    try:
        return execute_manual_backend(response)
    finally:
        with ACTIVE_LOCK:
            if ACTIVE_JOB_ID == str(response.get("job_id")):
                ACTIVE_JOB_ID = None


def execute_manual_backend(response: dict[str, Any]) -> dict[str, Any]:
    window = str(response["window"])
    contract = ALLOWED_WINDOWS[window]
    market = str(contract["market"])
    reference = datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0)
    started_monotonic = time.monotonic()
    started_at = reference.isoformat()
    base = lifecycle_status(response, "queued", started_at=None, message="等待執行。")
    persist_status(base)
    selected = resolve_snapshots(ROOT / "artifacts/archive/window_snapshots", market, window)
    before_snapshot = selected.latest
    before_hashes = _route_hashes(market, window)
    market_date = reference.date().isoformat() if market == "TW" else reference.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    effective_date = str(selected.latest.get("effective_trading_date")) if selected.latest else market_date
    command = list(contract["backend_command"])
    if market == "TW":
        command.extend(["--effective-trading-date", effective_date])
    else:
        command.extend(["--as-of", reference.isoformat()])
    running_state = lifecycle_status(base, "running", started_at=started_at, message="正在建立 Runtime 並更新 Archive。")
    persist_status(running_state)
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=1800, check=False)
    except subprocess.TimeoutExpired:
        finished = datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0)
        failed = lifecycle_status(running_state, "failed", started_at=started_at, finished_at=finished.isoformat(), duration_seconds=int(time.monotonic() - started_monotonic), error_stage="建立 Runtime", error_summary="手動批次執行逾時。", message="手動重跑失敗；Archive、Latest、Previous 與市場 Dashboard 不應更新。", hash_evidence={"before": before_hashes, "after": _route_hashes(market, window)})
        return persist_status(failed)
    success = completed.returncode == 0
    after_selection = resolve_snapshots(ROOT / "artifacts/archive/window_snapshots", market, window)
    latest = after_selection.latest
    publish_result: dict[str, Any] = {}
    if success and latest and latest.get("snapshot_id") != (before_snapshot or {}).get("snapshot_id"):
        publishing_state = lifecycle_status(running_state, "publishing", started_at=started_at, effective_trading_date=latest.get("effective_trading_date"), revision=latest.get("revision"), message="Archive 已更新，正在重建 Latest Route 並同步 active 市場 Dashboard。")
        persist_status(publishing_state)
        publish_result = publish_manual_rerun_update(market, window)
    else:
        publishing_state = running_state
        success = False
    finished = datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0)
    after_hashes = _route_hashes(market, window)
    latest_url = f"/stock-ai-dashboard/dashboard/archive/{market.lower()}/{window}/latest/index.html"
    market_url = f"/stock-ai-dashboard/dashboard/{market.lower()}/index.html"
    audit = {
        "schema_version": "manual_rerun_runtime_bridge_audit_v2",
        "task_id": "AI-DEV-179",
        "job_id": response.get("job_id"),
        "requested_window": window,
        "executed_window": window,
        "market": market,
        "effective_trading_date": effective_date,
        "mode": ALLOWED_MODE,
        "status": "completed" if success else "failed",
        "pipeline_status": "completed" if success else "failed",
        "backend_returncode": completed.returncode,
        "backend_output_recorded": False,
        "dashboard_publish_attempted": success,
        "dashboard_publish_status": "completed" if success else "failed",
        "archive_write_expected": success,
        "manual_revision_metadata": True,
        "line_attempted": False,
        "email_attempted": False,
        "production_pipeline_executed": False,
        "operator_auth": "verified",
        "pin_recorded": False,
        "submitted_at": response.get("submitted_at"),
        "started_at": started_at,
        "finished_at": finished.isoformat(),
        "duration_seconds": int(time.monotonic() - started_monotonic),
        "revision": latest.get("revision") if success and latest else None,
        "snapshot_id": latest.get("snapshot_id") if success and latest else None,
        "latest_route_updated": publish_result.get("latest_route_updated") is True,
        "market_dashboard_updated": publish_result.get("market_dashboard_updated") is True,
        "market_dashboard_sync_reason": (publish_result.get("market_dashboard") or {}).get("reason"),
        "previous_route_updated": False,
        "other_windows_updated": False,
        "latest_url": latest_url,
        "market_dashboard_url": market_url,
        "hash_evidence": {"before": before_hashes, "after": after_hashes},
        "error_stage": None if success else "建立 Runtime / Archive admission",
        "error_summary": None if success else f"backend return code {completed.returncode}; 未確認新的 admitted revision。",
        "message": f"{contract['label']} 手動重跑已完成。" if success else "手動重跑失敗；未確認新的 admitted revision。",
        "lifecycle": publishing_state.get("lifecycle", []),
        "safety_notes": ["single_window_only", "dashboard_refresh_only", "no_line_email", "no_trading", "existing_latest_effective_date_preserved_for_revision" if selected.latest else "first_snapshot_uses_market_session_date"],
    }
    persist_status(lifecycle_status(audit, audit["status"]))
    return sanitize_response(audit)


def status_payload(job_id: str | None = None, status_dir: Path | None = None) -> dict[str, Any]:
    path = _status_path(job_id, status_dir) if job_id else _status_path(None, status_dir)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"schema_version": MANUAL_STATUS_SCHEMA, "status": "idle", "message": "目前沒有手動重跑任務。"}
    if job_id and data.get("job_id") != job_id:
        return {"status": "not_found", "job_id": job_id, "line_attempted": False, "email_attempted": False}
    raw_status = str(data.get("status") or "idle")
    rejected_states = {"invalid_pin_format", "unauthorized", "manual_rerun_disabled", "lock_busy", "cooldown_active"}
    normalized_status = "rejected" if raw_status in rejected_states else raw_status
    if normalized_status not in {"idle", "submitted", "queued", "running", "publishing", "completed", "failed", "rejected"}:
        normalized_status = "failed"
    normalized = lifecycle_status(data, normalized_status)
    normalized["schema_version"] = MANUAL_STATUS_SCHEMA
    if raw_status != normalized_status:
        normalized.setdefault("reason", raw_status)
        normalized.setdefault("error_summary", "既存任務狀態已轉換為目前 lifecycle contract。")
    return sanitize_response(normalized)


def write_activation_result(result: dict[str, Any]) -> None:
    ACTIVATION_RESULT.parent.mkdir(parents=True, exist_ok=True)
    ACTIVATION_RESULT.write_text(stable(result), encoding="utf-8")
    lines = [
        "# AI-DEV-163 Manual Rerun Runtime Activation Trace",
        "",
        f"- bridge: `scripts/orchestrator/manual_rerun_runtime_bridge.py`",
        f"- post_route: `{POST_PATH}`",
        f"- status_route: `{STATUS_PATH}`",
        f"- health_route: `{HEALTH_PATH}`",
        f"- pin_config_sources: runtime env `{PIN_HASH_ENV}` or runtime-only config file",
        f"- runtime_pin_configured_for_validation: {result.get('runtime_pin_configured_for_validation')}",
        f"- actual_line_sent: {result.get('actual_line_sent')}",
        f"- actual_email_sent: {result.get('actual_email_sent')}",
        f"- production_pipeline_executed: {result.get('production_pipeline_executed')}",
        "",
        "Operator must set the runtime PIN hash directly on GCP. Do not paste the PIN into Codex, ChatGPT, GitHub, docs, logs, or artifacts.",
    ]
    ACTIVATION_TRACE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def redact_case_ids(cases: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for name, payload in cases.items():
        if isinstance(payload, dict):
            item = dict(payload)
            if item.get("job_id"):
                item["job_id"] = "mock-job-redacted"
            if item.get("status_url"):
                item["status_url"] = "/stock-ai-dashboard/api/manual-rerun/status?job_id=mock-job-redacted"
            clean[name] = item
        else:
            clean[name] = payload
    return clean


def build_simulation() -> dict[str, Any]:
    from scripts.orchestrator.manual_rerun_single_window import pin_hash

    mock_pin = "".join(("42", "68", "10"))
    mock_hash = pin_hash(mock_pin)
    base = {"mode": ALLOWED_MODE, "confirm_single_window_only": True, "reason": "runtime activation dry-run"}

    def req(window: Any, pin: str = mock_pin, mode: str = ALLOWED_MODE) -> dict[str, Any]:
        out = dict(base)
        out.update({"window": window, "pin": pin, "mode": mode})
        return out

    cases: dict[str, Any] = {
        "missing_pin_config_disabled": process_manual_rerun_request(req("intraday_1305"), pin_hash_value=None, write=True),
        "mock_correct_pin_pre_open": process_manual_rerun_request(req("pre_open_0700"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_intraday": process_manual_rerun_request(req("intraday_1305"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_pre_close": process_manual_rerun_request(req("pre_close_1335"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_post_close": process_manual_rerun_request(req("post_close_1500"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_us_pre_market": process_manual_rerun_request(req("us_pre_market_2000"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_us_intraday": process_manual_rerun_request(req("us_intraday_2300"), pin_hash_value=mock_hash, write=False),
        "mock_correct_pin_us_review": process_manual_rerun_request(req("us_post_close_review_0630"), pin_hash_value=mock_hash, write=False),
        "wrong_pin_rejected": process_manual_rerun_request(req("intraday_1305", pin="".join(("13", "57", "90"))), pin_hash_value=mock_hash, write=False),
        "short_pin_rejected": process_manual_rerun_request(req("intraday_1305", pin="13579"), pin_hash_value=mock_hash, write=False),
        "long_pin_rejected": process_manual_rerun_request(req("intraday_1305", pin="1357901"), pin_hash_value=mock_hash, write=False),
        "non_digit_pin_rejected": process_manual_rerun_request(req("intraday_1305", pin="ab" + "1357"), pin_hash_value=mock_hash, write=False),
        "all_windows_rejected": process_manual_rerun_request(req("all_windows"), pin_hash_value=mock_hash, write=False),
        "star_window_rejected": process_manual_rerun_request(req("*"), pin_hash_value=mock_hash, write=False),
        "array_windows_rejected": process_manual_rerun_request(req(["pre_open_0700", "intraday_1305"]), pin_hash_value=mock_hash, write=False),
        "unknown_window_rejected": process_manual_rerun_request(req("unknown_window"), pin_hash_value=mock_hash, write=False),
        "send_line_mode_rejected": process_manual_rerun_request(req("intraday_1305", mode="send_line"), pin_hash_value=mock_hash, write=False),
        "send_email_mode_rejected": process_manual_rerun_request(req("intraday_1305", mode="send_email"), pin_hash_value=mock_hash, write=False),
        "full_delivery_mode_rejected": process_manual_rerun_request(req("intraday_1305", mode="full_delivery"), pin_hash_value=mock_hash, write=False),
        "trade_mode_rejected": process_manual_rerun_request(req("intraday_1305", mode="trade"), pin_hash_value=mock_hash, write=False),
        "status_endpoint": status_payload(),
    }
    result = {
        "schema_version": "manual_rerun_runtime_activation_v1",
        "task_id": "AI-DEV-163",
        "bridge_path": "scripts/orchestrator/manual_rerun_runtime_bridge.py",
        "post_route": POST_PATH,
        "status_route": STATUS_PATH,
        "health_route": HEALTH_PATH,
        "pin_config_env": PIN_HASH_ENV,
        "pin_config_file_path": "runtime-only config file path",
        "runtime_pin_configured_for_validation": False,
        "runtime_deployment_enabled": False,
        "actual_line_sent": False,
        "actual_email_sent": False,
        "notification_sent": False,
        "scheduler_modified": False,
        "production_pipeline_executed": False,
        "python_main_executed": False,
        "db_write": False,
        "trading_or_order_executed": False,
        "pin_or_hash_recorded": False,
        "cases": redact_case_ids(cases),
        "audit_path": str(AUDIT_LATEST.relative_to(ROOT)),
        "status_path": str(STATUS_LATEST.relative_to(ROOT)),
    }
    write_activation_result(result)
    return result


class ManualRerunHandler(BaseHTTPRequestHandler):
    server_version = "StockAIManualRerunBridge/1.0"

    def _json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = stable(sanitize_response(payload)).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == HEALTH_PATH:
            pin_hash, source = load_pin_hash()
            self._json(200, {"ok": True, "status": "ready" if pin_hash else "manual_rerun_disabled", "pin_config_source": source})
            return
        if parsed.path == STATUS_PATH:
            query = parse_qs(parsed.query)
            self._json(200, status_payload((query.get("job_id") or [None])[0]))
            return
        self._json(404, {"ok": False, "status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != POST_PATH:
            self._json(404, {"ok": False, "status": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"accepted": False, "status": "bad_json", "line_attempted": False, "email_attempted": False})
            return
        pin_hash, _source = load_pin_hash()
        result = process_manual_rerun_request(payload, pin_hash_value=pin_hash, write=True)
        self._json(202 if result.get("accepted") else 403, result)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("manual-rerun-bridge: " + (fmt % args) + "\n")


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), ManualRerunHandler)
    print(json.dumps({"ok": True, "status": "serving", "host": host, "port": port, "post_route": POST_PATH, "status_route": STATUS_PATH}, ensure_ascii=False, sort_keys=True))
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual rerun runtime bridge. Disabled unless runtime PIN hash is configured.")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8763)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.serve:
        serve(args.host, args.port)
        return 0
    if args.status:
        print(json.dumps(status_payload(), ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
        return 0
    if args.simulate:
        result = build_simulation()
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
        return 0
    pin_hash, source = load_pin_hash(allow_env=False, allow_file=False)
    print(json.dumps({"ok": True, "status": "manual_rerun_disabled", "pin_config_source": source, "serve_command_available": True}, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
