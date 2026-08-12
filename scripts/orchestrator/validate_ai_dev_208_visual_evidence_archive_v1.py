#!/usr/bin/env python3
"""Deterministic real-browser validation for AI-DEV-208."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.market_dashboard_alias import identity_attributes
from app.dashboard.visual_evidence_archive import (
    build_daily_review_bundle,
    capture_published_snapshot_non_blocking,
    capture_snapshot_visual_evidence,
)
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots, write_snapshot
from scripts.orchestrator.validate_post_merge_status import is_preserved_runtime_artifact


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(marker: str) -> dict[str, object]:
    return {
        "schema_version": "ai_dev_208_fixture_payload_v1",
        "marker": marker,
        "cards": [{"symbol": marker, "decision": "NO_TRADE"}],
        "runtime_provenance": "scheduled_production",
    }


def _put(root: Path, market: str, window: str, day: str, marker: str, *, run_kind: str = "scheduled") -> dict[str, object]:
    return write_snapshot(
        root,
        market=market,
        window=window,
        effective_trading_date=day,
        generated_at=f"{day}T13:05:00+08:00",
        source_payload=_source(marker),
        status="completed",
        run_kind=run_kind,
        run_id=f"ai208-{marker}",
    )


def _write_route(root: Path, snapshot: dict[str, object], text: str, *, wrong_identity: bool = False) -> Path:
    market = str(snapshot["market"])
    window = str(snapshot["window"])
    target = root / "dashboard" / "archive" / market.lower() / window / "latest" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    identity = identity_attributes(snapshot)
    if wrong_identity:
        identity = identity.replace(f'data-market="{market}"', 'data-market="WRONG"')
    target.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><style>body{font-family:sans-serif}"
        ".card{height:900px;padding:24px;background:#f4f7fb}</style></head>"
        f"<body {identity}><main><h1>{text}</h1><section class='card'>Visible Decision Content</section></main></body></html>",
        encoding="utf-8",
    )
    return target


def _verify_manifest(manifest_path: Path) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"].values():
        path = manifest_path.parent / item["path"]
        if not path.is_file() or _hash(path) != item["sha256"] or path.stat().st_size != item["size_bytes"]:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="ai-dev-208-") as raw:
        base = Path(raw)
        snapshot_root = base / "window_snapshots"
        dashboard_root = base / "dashboard_root"
        visual_root = base / "visual_evidence"
        day = "2026-08-13"

        tw_write_1 = _put(snapshot_root, "TW", "intraday_1305", day, "TW-R1")
        tw_1 = resolve_snapshots(snapshot_root, "TW", "intraday_1305").latest or {}
        tw_route = _write_route(dashboard_root, tw_1, "TW 13:05 Research Dashboard Revision 1")
        source_path = Path(str(tw_1["archive_path"]))
        source_hash_before = _hash(source_path)
        tw_result_1 = capture_snapshot_visual_evidence(tw_1, tw_route, output_root=visual_root)
        tw_manifest_1 = Path(str(tw_result_1.get("manifest_path")))
        checks["case_a_tw_capture_success"] = tw_result_1.get("status") == "SUCCESS"

        us_write = _put(snapshot_root, "US", "us_pre_market_2000", day, "US-R1")
        us_1 = resolve_snapshots(snapshot_root, "US", "us_pre_market_2000").latest or {}
        us_route = _write_route(dashboard_root, us_1, "US 20:00 Research Dashboard")
        us_result = capture_snapshot_visual_evidence(us_1, us_route, output_root=visual_root)
        checks["case_b_us_capture_success"] = us_result.get("status") == "SUCCESS"
        if not checks["case_a_tw_capture_success"] or not checks["case_b_us_capture_success"]:
            payload = {
                "schema_version": "ai_dev_208_visual_evidence_validation_v1",
                "task_id": "AI-DEV-208",
                "ok": False,
                "errors": [name for name, passed in checks.items() if not passed],
                "checks": checks,
                "details": {"tw": tw_result_1, "us": us_result},
                "browser_render_exercised": True,
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
            return 1

        ineligible = dict(tw_1)
        ineligible["run_kind"] = "test"
        skipped_root = base / "ineligible_output"
        skipped = capture_snapshot_visual_evidence(ineligible, tw_route, output_root=skipped_root)
        checks["case_c_unadmitted_skipped"] = skipped.get("status") == "SKIPPED_INELIGIBLE" and not skipped_root.exists()

        mismatch_write = _put(snapshot_root, "TW", "pre_open_0700", day, "TW-MISMATCH")
        mismatch_snapshot = resolve_snapshots(snapshot_root, "TW", "pre_open_0700").latest or {}
        mismatch_route = _write_route(dashboard_root, mismatch_snapshot, "Wrong Identity", wrong_identity=True)
        mismatch = capture_snapshot_visual_evidence(mismatch_snapshot, mismatch_route, output_root=visual_root)
        checks["case_d_identity_mismatch"] = mismatch.get("status") == "FAILED" and mismatch.get("reason_code") == "IDENTITY_MISMATCH"

        fail_write = _put(snapshot_root, "TW", "pre_close_1335", day, "TW-FAIL")
        fail_snapshot = resolve_snapshots(snapshot_root, "TW", "pre_close_1335").latest or {}
        _write_route(dashboard_root, fail_snapshot, "Failure Isolation")
        with patch("app.dashboard.visual_evidence_archive._browser_render", side_effect=RuntimeError("PAGE_RENDER_TIMEOUT")):
            failed = capture_published_snapshot_non_blocking(
                market="TW",
                window="pre_close_1335",
                archive_write=fail_write,
                public_sync={"status": "verified"},
                static_root=dashboard_root,
                snapshot_archive_root=snapshot_root,
                output_root=visual_root,
            )
        checks["case_e_failure_isolated"] = (
            failed.get("status") == "FAILED"
            and failed.get("reason_code") == "PAGE_RENDER_TIMEOUT"
            and failed.get("production_batch_continues") is True
        )

        screenshot_1 = tw_manifest_1.parent / "screenshot_full.png"
        png = screenshot_1.read_bytes() if screenshot_1.is_file() else b""
        checks["case_f_real_nonempty_png"] = (
            len(png) > 100
            and png.startswith(b"\x89PNG\r\n\x1a\n")
            and int.from_bytes(png[16:20], "big") == 1440
            and int.from_bytes(png[20:24], "big") >= 1200
        )
        rendered_html_path = tw_manifest_1.parent / "rendered_page.html"
        rendered_html = rendered_html_path.read_text(encoding="utf-8") if rendered_html_path.is_file() else ""
        checks["case_g_html_identity"] = str(tw_1["snapshot_id"]) in rendered_html and "TW 13:05" in rendered_html
        rendered_text_path = tw_manifest_1.parent / "rendered_text.md"
        rendered_text = rendered_text_path.read_text(encoding="utf-8") if rendered_text_path.is_file() else ""
        checks["case_h_visible_text"] = "Visible Decision Content" in rendered_text and "<style>" not in rendered_text
        checks["case_i_manifest_hashes"] = (
            tw_result_1.get("status") == "SUCCESS"
            and us_result.get("status") == "SUCCESS"
            and _verify_manifest(tw_manifest_1)
            and _verify_manifest(Path(str(us_result["manifest_path"])))
        )
        tw_manifest_payload = json.loads(tw_manifest_1.read_text(encoding="utf-8"))
        checks["visual_qa_identity_hash_hooks"] = all(
            tw_manifest_payload.get(key)
            for key in ("visual_evidence_id", "snapshot_id", "capture_hash", "screenshot_hash", "rendered_text_hash")
        )

        tw_write_2 = _put(snapshot_root, "TW", "intraday_1305", day, "TW-R2", run_kind="manual_rerun")
        tw_2 = resolve_snapshots(snapshot_root, "TW", "intraday_1305").latest or {}
        tw_route_2 = _write_route(dashboard_root, tw_2, "TW 13:05 Research Dashboard Revision 2")
        tw_result_2 = capture_snapshot_visual_evidence(tw_2, tw_route_2, output_root=visual_root, capture_origin="manual_rerun")
        revision_1 = visual_root / day / "TW" / "intraday_1305" / "revision_001" / "manifest.json"
        revision_2 = visual_root / day / "TW" / "intraday_1305" / "revision_002" / "manifest.json"
        checks["case_j_revisions_immutable"] = revision_1.is_file() and revision_2.is_file() and tw_write_1["snapshot_id"] != tw_write_2["snapshot_id"]
        review = build_daily_review_bundle(visual_root, day)
        review_manifest = json.loads((visual_root / "daily_reviews" / day / "review_manifest.json").read_text(encoding="utf-8"))
        tw_review = next(item for item in review_manifest["windows"] if item["market"] == "TW" and item["window"] == "intraday_1305")
        checks["case_k_daily_latest_revision"] = tw_review["status"] == "SUCCESS" and tw_review["latest_valid_revision"] == 2
        checks["case_l_missing_windows_truthful"] = review["available_window_count"] == 2 and review["missing_window_count"] == 3 and review["failed_window_count"] == 2
        checks["failed_window_has_no_valid_revision"] = all(
            item["latest_valid_revision"] is None and item["latest_attempt_revision"] == 1
            for item in review_manifest["windows"] if item["status"] == "FAILED"
        )

        manifest_hash_before = _hash(revision_2)
        index_before = json.loads((visual_root / "index.json").read_text(encoding="utf-8"))
        duplicate = capture_snapshot_visual_evidence(tw_2, tw_route_2, output_root=visual_root, capture_origin="manual_rerun")
        index_after = json.loads((visual_root / "index.json").read_text(encoding="utf-8"))
        checks["case_m_duplicate_suppressed"] = (
            duplicate.get("duplicate_suppressed") is True
            and manifest_hash_before == _hash(revision_2)
            and len(index_before["records"]) == len(index_after["records"])
        )
        checks["case_n_canonical_source_unchanged"] = source_hash_before == _hash(source_path)
        checks["case_o_temporary_root_isolated"] = visual_root.is_relative_to(base) and str(visual_root).startswith("/tmp/")
        checks["seven_canonical_windows"] = sum(len(windows) for windows in MARKET_WINDOWS.values()) == 7
        checks["canonical_reference_traceable"] = json.loads((revision_2.parent / "canonical_reference.json").read_text(encoding="utf-8"))["snapshot_id"] == tw_2["snapshot_id"]
        checks["daily_review_self_contained"] = all(
            (visual_root / "daily_reviews" / day / "TW" / "intraday_1305" / name).is_file()
            for name in ("screenshot_full.png", "rendered_page.html", "rendered_text.md", "manifest.json", "canonical_reference.json")
        )
        tw_delivery_source = (ROOT / "scripts/orchestrator/approved_pre_open_delivery.py").read_text(encoding="utf-8")
        us_delivery_source = (ROOT / "scripts/orchestrator/approved_us_stock_delivery.py").read_text(encoding="utf-8")
        checks["tw_automatic_capture_wired"] = "capture_published_snapshot_non_blocking(" in tw_delivery_source and '"visual_evidence": visual_evidence' in tw_delivery_source
        checks["us_automatic_capture_wired"] = "capture_published_snapshot_non_blocking(" in us_delivery_source and '"visual_evidence": visual_evidence' in us_delivery_source
        checks["visual_archive_governance_preserved"] = all(
            is_preserved_runtime_artifact(path)
            for path in (
                "artifacts/archive/visual_evidence/index.json",
                "artifacts/archive/visual_evidence/2026-08-13/TW/intraday_1305/revision_001/screenshot_full.png",
                "artifacts/archive/visual_evidence/2026-08-13/US/us_pre_market_2000/failures/revision_001_0123456789ab.json",
                "artifacts/archive/visual_evidence/daily_reviews/2026-08-13/review_manifest.json",
                "artifacts/archive/visual_evidence/daily_reviews/2026-08-13/TW/intraday_1305/rendered_text.md",
            )
        )
        details = {
            "tw_revision_1": tw_result_1,
            "tw_revision_2": tw_result_2,
            "us": us_result,
            "identity_mismatch": mismatch,
            "failure_isolation": failed,
            "daily_review": review_manifest,
            "archive_index_records": len(index_after["records"]),
            "fixture_revision_bundle_bytes": sum(path.stat().st_size for path in revision_2.parent.iterdir() if path.is_file()),
            "fixture_daily_review_bytes": sum(path.stat().st_size for path in (visual_root / "daily_reviews" / day).rglob("*") if path.is_file()),
        }
    checks["temporary_root_removed"] = not Path(raw).exists()
    errors = [name for name, passed in checks.items() if not passed]
    payload = {
        "schema_version": "ai_dev_208_visual_evidence_validation_v1",
        "task_id": "AI-DEV-208",
        "ok": not errors,
        "errors": errors,
        "checks": checks,
        "details": details,
        "browser_render_exercised": True,
        "production_archive_used": False,
        "safety": {
            "production_pipeline_executed": False,
            "notification_sent": False,
            "trading": False,
            "production_db_written": False,
            "immutable_history_rewritten": False,
            "network_required": False,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
