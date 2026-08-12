#!/usr/bin/env python3
"""Real-Chromium PDF and fail-closed retrieval gate for AI-DEV-210."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.market_dashboard_alias import identity_attributes
from app.dashboard.visual_evidence_archive import (
    _browser_render, build_daily_review_bundle, capture_published_snapshot_non_blocking,
    capture_snapshot_visual_evidence,
)
from app.dashboard.visual_evidence_export import ALLOWED_REVIEW_FILES, TRANSPORT_STATUS, export_visual_evidence
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots, write_snapshot
from scripts.orchestrator.validate_ai_dev_209_cross_market_research_news_coverage_v1 import validate as validate_ai209
from scripts.orchestrator.validate_post_merge_status import is_preserved_runtime_artifact


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        value.update(path.relative_to(root).as_posix().encode())
        value.update(path.read_bytes())
    return value.hexdigest()


def put(root: Path, market: str, window: str, day: str, marker: str, *, run_kind="scheduled") -> dict:
    return write_snapshot(root, market=market, window=window, effective_trading_date=day,
        generated_at=f"{day}T12:00:00+08:00", source_payload={"marker": marker, "runtime_provenance": "scheduled_production"},
        status="completed", run_kind=run_kind, run_id=f"ai210-{marker}")


def route(root: Path, snapshot: dict, label: str) -> Path:
    target = root / "dashboard" / "archive" / str(snapshot["market"]).lower() / str(snapshot["window"]) / "latest" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("<!doctype html><html><head><meta charset='utf-8'><style>@page{size:A4;margin:10mm}body{font-family:sans-serif}.card{height:950px;background:#eef;padding:20px;page-break-inside:avoid}</style></head>"
        f"<body {identity_attributes(snapshot)}><h1>{label}</h1><section class='card'>Research Evidence</section><section class='card'>Decision Evidence</section></body></html>", encoding="utf-8")
    return target


def valid_pdf(path: Path) -> bool:
    raw = path.read_bytes() if path.is_file() else b""
    return len(raw) > 500 and raw.startswith(b"%PDF-") and b"%%EOF" in raw[-2048:] and b"/Type /Page" in raw


def manifest_ok(path: Path) -> bool:
    value = json.loads(path.read_text(encoding="utf-8"))
    return all((path.parent / row["path"]).is_file()
               and digest(path.parent / row["path"]) == row["sha256"]
               and (path.parent / row["path"]).stat().st_size == row["size_bytes"]
               for row in value["files"].values())


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    temp_path = ""
    with tempfile.TemporaryDirectory(prefix="ai-dev-210-") as raw:
        temp_path = raw
        base = Path(raw); snapshots = base / "snapshots"; pages = base / "pages"
        visual = base / "visual"; exports = base / "exports"; day = "2026-08-14"

        put(snapshots, "TW", "intraday_1305", day, "TW1")
        tw1 = resolve_snapshots(snapshots, "TW", "intraday_1305").latest or {}
        tw_result1 = capture_snapshot_visual_evidence(tw1, route(pages, tw1, "TW PDF revision 1"), output_root=visual)
        tw_manifest1 = Path(str(tw_result1.get("manifest_path")))
        put(snapshots, "US", "us_pre_market_2000", day, "US1")
        us1 = resolve_snapshots(snapshots, "US", "us_pre_market_2000").latest or {}
        us_result = capture_snapshot_visual_evidence(us1, route(pages, us1, "US PDF revision 1"), output_root=visual)
        us_manifest = Path(str(us_result.get("manifest_path")))
        checks["case_a_tw_full_evidence"] = tw_result1.get("status") == "SUCCESS" and set(json.loads(tw_manifest1.read_text())["files"]) == {"pdf", "screenshot", "html", "text", "canonical"}
        checks["case_b_us_full_evidence"] = us_result.get("status") == "SUCCESS" and set(json.loads(us_manifest.read_text())["files"]) == {"pdf", "screenshot", "html", "text", "canonical"}
        checks["case_c_real_chromium_pdf"] = valid_pdf(tw_manifest1.parent / "dashboard_full.pdf") and valid_pdf(us_manifest.parent / "dashboard_full.pdf")
        checks["case_d_all_manifest_hashes"] = manifest_ok(tw_manifest1) and manifest_ok(us_manifest)
        tw_manifest_value = json.loads(tw_manifest1.read_text())
        checks["case_e_pdf_identity_same_revision"] = tw_manifest_value["capture"]["pdf"]["identity_source"] == "same_browser_page_and_dom" and tw_manifest_value["observed_identity"]["snapshot_id"] == tw_manifest_value["snapshot_id"] and tw_manifest_value["pdf_hash"] == tw_manifest_value["files"]["pdf"]["sha256"]

        put(snapshots, "TW", "intraday_1305", day, "TW2", run_kind="manual_rerun")
        tw2 = resolve_snapshots(snapshots, "TW", "intraday_1305").latest or {}
        tw_result2 = capture_snapshot_visual_evidence(tw2, route(pages, tw2, "TW PDF revision 2"), output_root=visual, capture_origin="manual_rerun")
        review = build_daily_review_bundle(visual, day)
        review_value = json.loads((visual / "daily_reviews" / day / "review_manifest.json").read_text())
        tw_window = next(item for item in review_value["windows"] if item["market"] == "TW" and item["window"] == "intraday_1305")
        checks["case_f_pdf_revisions_preserved"] = all((visual / day / "TW" / "intraday_1305" / f"revision_{revision:03d}" / "dashboard_full.pdf").is_file() for revision in (1, 2)) and tw_window["latest_valid_revision"] == 2 and (visual / "daily_reviews" / day / "TW" / "intraday_1305" / "dashboard_full.pdf").is_file()

        original_render = _browser_render
        def pdf_failure(source, screenshot, pdf, *, timeout_ms):
            rendered = original_render(source, screenshot, pdf, timeout_ms=timeout_ms)
            pdf.unlink(missing_ok=True); rendered["pdf_error"] = "PDF_RENDER_FAILED"; return rendered
        fail_write = put(snapshots, "US", "us_intraday_2300", day, "US-PDF-FAIL")
        fail_snapshot = resolve_snapshots(snapshots, "US", "us_intraday_2300").latest or {}
        route(pages, fail_snapshot, "US PDF failure")
        with patch("app.dashboard.visual_evidence_archive._browser_render", side_effect=pdf_failure):
            failed = capture_published_snapshot_non_blocking(market="US", window="us_intraday_2300",
                archive_write=fail_write, public_sync={"status": "verified"}, static_root=pages,
                snapshot_archive_root=snapshots, output_root=visual)
        review_value = json.loads((visual / "daily_reviews" / day / "review_manifest.json").read_text())
        failed_window = next(item for item in review_value["windows"] if item["market"] == "US" and item["window"] == "us_intraday_2300")
        checks["case_g_pdf_failure_nonblocking_truthful"] = failed.get("status") == "DEGRADED" and failed.get("reason_code") == "PDF_RENDER_FAILED" and failed.get("production_batch_continues") is True and failed_window["status"] == "DEGRADED" and failed_window["latest_attempt_status"] == "DEGRADED"

        legacy = base / "legacy"; shutil_manifest = json.loads(us_manifest.read_text())
        legacy_revision = legacy / day / "US" / "us_pre_market_2000" / "revision_001"; legacy_revision.mkdir(parents=True)
        for name in ("screenshot_full.png", "rendered_page.html", "rendered_text.md", "canonical_reference.json"):
            (legacy_revision / name).write_bytes((us_manifest.parent / name).read_bytes())
        shutil_manifest["schema_version"] = "visual_evidence_manifest_v1"; shutil_manifest["files"].pop("pdf", None); shutil_manifest.pop("pdf_hash", None); shutil_manifest["capture"].pop("pdf", None)
        (legacy_revision / "manifest.json").write_text(json.dumps(shutil_manifest), encoding="utf-8")
        legacy.mkdir(exist_ok=True); (legacy / "index.json").write_text(json.dumps({"records": [{"visual_evidence_id": shutil_manifest["visual_evidence_id"], "effective_trading_date": day, "market": "US", "window": "us_pre_market_2000", "revision": 1, "capture_status": "SUCCESS", "manifest_path": f"{day}/US/us_pre_market_2000/revision_001/manifest.json", "source_snapshot_id": shutil_manifest["snapshot_id"]}]}), encoding="utf-8")
        legacy_export = export_visual_evidence(effective_date=day, market="US", window="us_pre_market_2000", artifact="pdf", visual_root=legacy, export_root=exports)
        checks["case_h_legacy_pdf_truthful"] = legacy_export["status"] == "NOT_AVAILABLE" and legacy_export["reason_code"] == "PDF_NOT_CAPTURED"

        archive_before = tree_digest(visual)
        exported = export_visual_evidence(effective_date=day, market="TW", window="intraday_1305", artifact="pdf", visual_root=visual, export_root=exports)
        checks["case_i_safe_pdf_export"] = exported["status"] == "SUCCESS" and exported["media_type"] == "application/pdf" and exported["sha256"] == digest(tw_manifest1.parent.parent / "revision_002" / "dashboard_full.pdf") and exported["size"] > 500 and exported["chatgpt_transport_status"] == TRANSPORT_STATUS
        bundle1 = export_visual_evidence(effective_date=day, artifact="daily_bundle", visual_root=visual, export_root=exports)
        bundle2 = export_visual_evidence(effective_date=day, artifact="daily_bundle", visual_root=visual, export_root=exports)
        with zipfile.ZipFile(bundle1["safe_export_location"]) as archive:
            names = archive.namelist()
        checks["case_j_daily_bundle_allowlisted"] = bundle1["status"] == "SUCCESS" and bundle1["sha256"] == bundle2["sha256"] and all(Path(name).name in ALLOWED_REVIEW_FILES for name in names) and "review_manifest.json" in names
        checks["case_p_export_read_only"] = archive_before == tree_digest(visual)

        rejected = {
            "traversal": export_visual_evidence(effective_date="../2026-08-14", market="TW", window="intraday_1305", artifact="pdf", visual_root=visual, export_root=exports),
            "absolute": export_visual_evidence(effective_date="/etc/passwd", market="TW", window="intraday_1305", artifact="pdf", visual_root=visual, export_root=exports),
            "secret": export_visual_evidence(effective_date=day, market="TW", window="intraday_1305", artifact=".env", visual_root=visual, export_root=exports),
            "source": export_visual_evidence(effective_date=day, market="TW", window="intraday_1305", artifact="source.py", visual_root=visual, export_root=exports),
            "log": export_visual_evidence(effective_date=day, market="TW", window="intraday_1305", artifact="runtime.log", visual_root=visual, export_root=exports),
            "db": export_visual_evidence(effective_date=day, market="TW", window="intraday_1305", artifact="stock.db", visual_root=visual, export_root=exports),
            "unknown_window": export_visual_evidence(effective_date=day, market="TW", window="bad", artifact="pdf", visual_root=visual, export_root=exports),
            "unknown_revision": export_visual_evidence(effective_date=day, market="TW", window="intraday_1305", revision=999, artifact="pdf", visual_root=visual, export_root=exports),
        }
        checks["case_k_l_n_o_selectors_fail_closed"] = all(value["status"] == "REJECTED" for value in rejected.values())
        outside = base / "outside"; outside.mkdir(); (outside / "manifest.json").write_text("{}")
        symlink_root = base / "symlink"; symlink_root.mkdir(); (symlink_root / "link").symlink_to(outside, target_is_directory=True)
        (symlink_root / "index.json").write_text(json.dumps({"records": [{"visual_evidence_id": "x", "effective_trading_date": day, "market": "TW", "window": "intraday_1305", "revision": 1, "capture_status": "SUCCESS", "manifest_path": "link/manifest.json"}]}))
        symlink_result = export_visual_evidence(effective_date=day, market="TW", window="intraday_1305", artifact="manifest", visual_root=symlink_root, export_root=exports)
        checks["case_m_symlink_escape"] = symlink_result["status"] == "REJECTED"
        checks["case_q_temporary_root_isolated"] = str(visual).startswith("/tmp/") and str(exports).startswith("/tmp/")
        checks["case_r_seven_registry_windows"] = sum(len(value) for value in MARKET_WINDOWS.values()) == 7
        checks["case_s_ai208_latest_attempt_semantics"] = review["status"] == "BUILT" and tw_window["latest_attempt_revision"] == 2 and tw_window["latest_attempt_status"] == "SUCCESS"
        checks["case_t_ai209_regression"] = validate_ai209()["ok"] is True
        checks["pdf_paths_governance_preserved"] = all(is_preserved_runtime_artifact(path) for path in (
            "artifacts/archive/visual_evidence/2026-08-14/TW/intraday_1305/revision_001/dashboard_full.pdf",
            "artifacts/archive/visual_evidence/daily_reviews/2026-08-14/TW/intraday_1305/dashboard_full.pdf",
            "artifacts/runtime/visual_evidence_exports/2026-08-14/daily_review_2026-08-14.zip",
        ))
        details = {"tw": tw_result2, "us": us_result, "pdf_failure": failed, "pdf_export": exported,
                   "daily_bundle": bundle1, "rejected_selectors": rejected,
                   "chatgpt_transport_status": TRANSPORT_STATUS}
    checks["temporary_validator_root_removed"] = not Path(temp_path).exists()
    errors = [name for name, passed in checks.items() if not passed]
    return {"schema_version": "ai_dev_210_visual_evidence_pdf_retrieval_validation_v1",
        "task_id": "AI-DEV-210", "ok": not errors, "checks": checks, "errors": errors,
        "details": details, "browser_pdf_exercised": True,
        "chatgpt_transport_status": TRANSPORT_STATUS,
        "safety": {"production_pipeline": False, "publish": False, "notification": False,
                   "trading": False, "secrets": False, "production_db": False,
                   "immutable_history_rewritten": False}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = validate(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
