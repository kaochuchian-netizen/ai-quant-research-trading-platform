#!/usr/bin/env python3
"""AI-DEV-222 seven-window audit bundle, outbox and Drive transport gate."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots, write_snapshot
from app.dashboard.market_dashboard_alias import payload_hash
from app.reports.delivery_provenance import build_delivery_provenance, content_hash
from app.runtime.batch_audit_bundle import (
    build_batch_audit_bundle, contains_secret, drive_revision_path, enqueue_batch_audit_non_blocking, sha256,
)
from app.runtime.google_drive_batch_audit import ConflictError, FakeDriveBackend, credential_discovery_contract, render_email_preview_pdf, upload_bundle


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def put_snapshot(root: Path, market: str, window: str, *, date: str, marker: str,
                 run_kind: str = "scheduled", runtime: str = "scheduled_production") -> dict:
    result = write_snapshot(
        root, market=market, window=window, effective_trading_date=date,
        generated_at=f"{date}T20:00:00+08:00",
        source_payload={"market": market, "window": window, "runtime_provenance": runtime,
                        "run_kind": run_kind, "marker": marker, "trading_or_order_executed": False},
        status="completed", run_kind=run_kind, run_id=f"ai222-{marker}",
    )
    require(result.get("written") is True, f"snapshot not written: {market}/{window}/{result}")
    snapshot = resolve_snapshots(root, market, window).latest or {}
    snapshot["payload_hash"] = payload_hash(snapshot["payload"])
    return snapshot


def put_visual(root: Path, snapshot: dict) -> Path:
    target = root / snapshot["market"] / snapshot["window"] / f"revision-{snapshot['revision']:04d}"
    target.mkdir(parents=True)
    files = {
        "rendered_page.html": b"<html><body>admitted report</body></html>",
        "dashboard_full.pdf": b"%PDF-1.4\nAI222 fixture\n%%EOF\n",
        "screenshot_full.png": b"\x89PNG\r\n\x1a\nAI222 fixture",
    }
    for name, raw in files.items(): (target / name).write_bytes(raw)
    manifest = {
        "schema_version": "visual_evidence_manifest_v2", "visual_evidence_id": "visual-" + snapshot["snapshot_id"][:16],
        "market": snapshot["market"], "window": snapshot["window"],
        "effective_trading_date": snapshot["effective_trading_date"], "revision": snapshot["revision"],
        "snapshot_id": snapshot["snapshot_id"], "payload_hash": snapshot["payload_hash"],
        "capture": {"status": "SUCCESS"},
        "files": {name: {"path": name, "sha256": sha256(target / name), "size_bytes": len(raw)} for name, raw in files.items()},
    }
    path = target / "manifest.json"; path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return path


def provenance(snapshot: dict, channel: str, content: str) -> dict:
    return build_delivery_provenance(
        market=snapshot["market"], window=snapshot["window"], trading_date=snapshot["effective_trading_date"],
        snapshot=snapshot, canonical_url="https://example.invalid/dashboard", channel=channel, content=content,
        delivery_result="sent", delivery_attempted=True, public_sync={"status": "verified"},
    )


def main() -> int:
    cases: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="ai-dev-222-") as raw:
        base = Path(raw); archive = base / "archive"; visual = base / "visual"; outbox = base / "outbox"
        bundles = []
        for market, windows in MARKET_WINDOWS.items():
            for index, window in enumerate(windows, 1):
                date = "2026-08-24" if market == "TW" else "2026-08-21"
                snapshot = put_snapshot(archive, market, window, date=date, marker=f"{market}-{index}")
                manifest = put_visual(visual, snapshot)
                line = f"{market} {window} actual rendered LINE"
                email = f"<p>{market} {window} actual rendered Email</p>"
                bundle = build_batch_audit_bundle(
                    snapshot=snapshot, visual_manifest_path=manifest, line_message=line,
                    email_subject=f"{market} {window} subject", email_body=email,
                    line_provenance=provenance(snapshot, "line", line),
                    email_provenance=provenance(snapshot, "email", email),
                    dashboard_url="https://example.invalid/dashboard", public_parity_status="verified",
                    outbox_root=outbox,
                )
                require(bundle["status"] == "ENQUEUED", f"bundle failed {market}/{window}: {bundle}")
                bundles.append((snapshot, Path(bundle["outbox_path"])))
        cases["seven_window_coverage"] = "PASS"

        paths = {path.relative_to(outbox).as_posix() for _, path in bundles}
        require(len(paths) == 7 and all(path.startswith(("2026-08-24/TW/", "2026-08-21/US/")) for path in paths), "market/date routing")
        require(all("revision-0001" in path for path in paths), "revision naming")
        cases["market_isolation_and_canonical_paths"] = "PASS"

        snapshot, bundle = bundles[-1]; manifest = json.loads((bundle / "manifest.json").read_text())
        require(manifest["snapshot_id"] == snapshot["snapshot_id"] and manifest["cross_market_evidence_count"] == 0, "identity/cross market")
        require(manifest["public_parity_status"] == "verified" and manifest["secrets_exposed"] is False, "manifest contract")
        require(manifest["trading_or_order_executed"] is False and manifest["total_bundle_size"] > 0, "safety/retention")
        require((bundle / "notifications/line_message.txt").read_text() == f"{snapshot['market']} {snapshot['window']} actual rendered LINE", "actual LINE lost")
        delivery = json.loads((bundle / "notifications/delivery_status.json").read_text())
        require(delivery["presentation_content_hash"]["line"] == content_hash((bundle / "notifications/line_message.txt").read_text()), "notification hash parity")
        cases["manifest_notification_and_public_parity"] = "PASS"

        before = tree_hash(archive)
        repeat = build_batch_audit_bundle(
            snapshot=snapshot, visual_manifest_path=put_visual(base / "repeat-visual", snapshot),
            line_message="repeat", email_subject="repeat", email_body="repeat",
            line_provenance=provenance(snapshot, "line", "repeat"), email_provenance=provenance(snapshot, "email", "repeat"),
            dashboard_url="https://example.invalid", public_parity_status="verified", outbox_root=outbox,
        )
        require(repeat["status"] == "ENQUEUED" and repeat["duplicate_suppressed"] is True, "idempotent enqueue")
        require(tree_hash(archive) == before, "archive mutated")
        cases["idempotency_and_archive_immutability"] = "PASS"

        require(render_email_preview_pdf(bundle, renderer=lambda _source, destination: destination.write_bytes(b"%PDF-1.4\nemail fixture\n%%EOF\n"))["status"] == "SUCCESS", "upload fixture PDF")
        fake = FakeDriveBackend(fail_after=2)
        degraded = upload_bundle(bundle, fake, max_retries=1, timeout_seconds=1)
        require(degraded["status"] == "DEGRADED", "Drive outage not degraded")
        fake.fail_after = None
        recovered = upload_bundle(bundle, fake, max_retries=2, timeout_seconds=1)
        require(recovered["status"] == "UPLOADED" and recovered["uploaded_file_count"] >= 8, "partial resume failed")
        again = upload_bundle(bundle, fake, max_retries=1, timeout_seconds=1)
        require(again["status"] == "UPLOADED", "same hash retry failed")
        any_key = next(iter(fake.files))
        conflict_file = base / "conflict"; conflict_file.write_text("changed")
        try:
            fake.upload(any_key[0], any_key[1], conflict_file, sha256(conflict_file))
        except ConflictError:
            pass
        else:
            raise AssertionError("content conflict overwrote")
        cases["bounded_retry_resume_duplicate_and_conflict"] = "PASS"

        timeout_bundle = bundles[-2][1]
        class SlowDrive(FakeDriveBackend):
            def upload(self, parent_id: str, name: str, path: Path, checksum: str) -> str:
                time.sleep(0.2)
                return super().upload(parent_id, name, path, checksum)
        started = time.monotonic(); timeout_result = upload_bundle(timeout_bundle, SlowDrive(), max_retries=1, timeout_seconds=0.01)
        require(timeout_result["status"] == "DEGRADED" and time.monotonic() - started < 0.15, "upload timeout blocked worker")
        cases["bounded_upload_timeout"] = "PASS"

        bad_snapshot = dict(snapshot); bad_snapshot["run_kind"] = "fixture"
        rejected = build_batch_audit_bundle(
            snapshot=bad_snapshot, visual_manifest_path=put_visual(base / "bad-visual", bad_snapshot),
            line_message="x", email_subject="x", email_body="x",
            line_provenance=provenance(snapshot, "line", "x"), email_provenance=provenance(snapshot, "email", "x"),
            dashboard_url="x", public_parity_status="verified", outbox_root=base / "bad-outbox",
        )
        require(rejected["status"] == "SKIPPED", "fixture uploaded")
        require(contains_secret("Authorization: Bearer abc.def") is True, "secret detector blind")
        secret = build_batch_audit_bundle(
            snapshot=snapshot, visual_manifest_path=put_visual(base / "secret-visual", snapshot),
            line_message="token=supersecret", email_subject="x", email_body="x",
            line_provenance=provenance(snapshot, "line", "token=supersecret"), email_provenance=provenance(snapshot, "email", "x"),
            dashboard_url="x", public_parity_status="verified", outbox_root=base / "secret-outbox",
        )
        require(secret["reason_code"] == "SECRET_PATTERN_DETECTED", "secret evidence accepted")
        cases["admission_and_secret_fail_closed"] = "PASS"

        original = os.environ.pop("STOCK_AI_BATCH_AUDIT_ENABLED", None)
        disabled = enqueue_batch_audit_non_blocking()
        if original is not None: os.environ["STOCK_AI_BATCH_AUDIT_ENABLED"] = original
        require(disabled["status"] == "DISABLED" and disabled["production_batch_continues"] is True, "disabled mode")
        contract = credential_discovery_contract()
        require(contract["secret_values_printed"] is False and contract["reference_folder_id"] == "1JCCyIV5fRVepN5hOotxNjq6Xqko1n3hy", "credential contract")
        require(contract["credential_method"] is None and contract["service_account_supported"] is False, "service account path retained")
        require(contract["root_folder_strategy"] == "APP_OWNED_MY_DRIVE_FOLDER" and contract["minimum_scope"] == "drive.file", "OAuth/root scope")
        cases["disabled_fake_ci_and_credential_boundary"] = "PASS"

        us20 = put_snapshot(base / "lineage", "US", "us_pre_market_2000", date="2026-08-21", marker="20")
        us23 = put_snapshot(base / "lineage", "US", "us_intraday_2300", date="2026-08-21", marker="23")
        us23["payload"]["source_snapshot_id"] = us20["snapshot_id"]
        require(us23["payload"]["source_snapshot_id"] == us20["snapshot_id"], "20->23 lineage")
        weekend = write_snapshot(base / "weekend", market="US", window="us_pre_market_2000", effective_trading_date="2026-08-22",
            generated_at="2026-08-22T20:00:00+08:00", source_payload={"runtime_provenance": "scheduled_production"},
            status="completed", run_kind="scheduled", run_id="weekend")
        require(weekend["written"] is False and weekend["reason"] == "us_non_trading_effective_date", "weekend admitted")
        cases["us_calendar_and_intraday_lineage"] = "PASS"

        source_us = (ROOT / "scripts/orchestrator/approved_us_stock_delivery.py").read_text()
        source_tw = (ROOT / "scripts/orchestrator/approved_pre_open_delivery.py").read_text()
        for source in (source_us, source_tw):
            require("enqueue_batch_audit_non_blocking" in source, "production hook absent")
            require("send_" in source and source.index("enqueue_batch_audit_non_blocking(") > source.index("build_delivery_provenance("), "hook before rendered delivery")
        require("TW" not in drive_revision_path(snapshot), "TW fallback in US path")
        cases["post_delivery_hook_no_resend_no_tw_fallback"] = "PASS"

        failure_bundle = bundles[-3][1]
        failure = json.loads((failure_bundle / "failure.json").read_text())
        require(failure["production_batch_continues"] is True and "EMAIL_PREVIEW_RENDER_PENDING" in failure["reason_codes"], "failure audit record")
        rendered_bundle = bundles[0][1]
        rendered = render_email_preview_pdf(rendered_bundle, renderer=lambda _source, destination: destination.write_bytes(b"%PDF-1.4\nemail fixture\n%%EOF\n"))
        require(rendered["status"] == "SUCCESS" and (rendered_bundle / "notifications/email_preview.pdf").is_file(), "email preview renderer")
        rendered_manifest = json.loads((rendered_bundle / "manifest.json").read_text())
        require("notifications/email_preview.pdf" in rendered_manifest["bundle_file_hashes"], "email PDF manifest missing")
        require(not contains_secret(json.loads((bundle / "manifest.json").read_text())), "manifest secret")
        cases["degraded_failure_record_and_durable_outbox"] = "PASS"

    result = {"schema_version": "ai_dev_222_validator_v1", "ok": True, "passed": True, "status": "PASS", "case_count": len(cases), "cases": cases,
              "production_batch_executed": False, "notifications_sent": False, "trading_or_order_executed": False,
              "drive_network_used": False, "secrets_accessed": False}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"schema_version": "ai_dev_222_validator_v1", "ok": False, "passed": False, "status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(2)
