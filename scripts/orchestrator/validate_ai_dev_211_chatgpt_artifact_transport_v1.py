#!/usr/bin/env python3
"""AI-DEV-211 selector-based review bundle and connector-outbox gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.visual_evidence_export import COMPACT_REVIEW_FILES, TRANSPORT_STATUS, export_visual_evidence
from app.dashboard.visual_evidence_transport import prepare_chatgpt_transport, prepare_transport_non_blocking
from app.dashboard.market_dashboard_alias import payload_hash
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, resolve_snapshots, write_snapshot


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        value.update(path.relative_to(root).as_posix().encode()); value.update(path.read_bytes())
    return value.hexdigest()


def put_snapshot(root: Path, *, run_kind: str, marker: str) -> dict:
    write_snapshot(
        root, market="US", window="us_pre_market_2000", effective_trading_date="2026-08-14",
        generated_at="2026-08-14T20:00:00+08:00",
        source_payload={
            "runtime_provenance": "manual_rerun" if run_kind == "manual_rerun" else "scheduled_production",
            "dashboard_ready_contract": {"cards": [{
                "symbol": "AAPL", "institutional_research": {
                    "research_identity": f"research-{marker}",
                    "news_intelligence_v2": {"selected_items": [{"headline": f"{marker} evidence"}], "evidence_funnel": {
                        "absence_state": "NEWS_SELECTED_AND_RENDERED",
                        "stages": {"DISCOVERED": 2, "ADMITTED": 1, "RRE_USED": 1, "RENDERED": 1},
                    }},
                    "research_intelligence_v2": {"window_research_identity": f"window-{marker}", "research_stance": "neutral"},
                    "decision_context_export": {"trade_action": None},
                },
            }]},
        },
        status="completed", run_kind=run_kind, run_id=f"ai211-{marker}",
    )
    return resolve_snapshots(root, "US", "us_pre_market_2000").latest or {}


def put_visual(root: Path, snapshot: dict) -> Path:
    target = root / "2026-08-14" / "US" / "us_pre_market_2000" / f"revision_{int(snapshot['revision']):03d}"
    target.mkdir(parents=True)
    content = {
        "dashboard_full.pdf": b"%PDF-1.4\nfixture\n%%EOF\n",
        "screenshot_full.png": b"\x89PNG\r\n\x1a\nfixture",
        "rendered_text.md": b"AAPL current research evidence\n",
    }
    for name, raw in content.items(): (target / name).write_bytes(raw)
    snapshot = {**snapshot, "payload_hash": payload_hash(snapshot["payload"])}
    canonical = {key: snapshot[key] for key in ("market", "window", "effective_trading_date", "snapshot_id", "revision", "payload_hash")}
    canonical["schema_version"] = "visual_evidence_canonical_reference_v1"
    (target / "canonical_reference.json").write_text(json.dumps(canonical, sort_keys=True), encoding="utf-8")
    files = {
        "pdf": ("dashboard_full.pdf", "application/pdf"),
        "screenshot": ("screenshot_full.png", "image/png"),
        "text": ("rendered_text.md", "text/markdown"),
        "canonical": ("canonical_reference.json", "application/json"),
    }
    manifest = {
        "schema_version": "visual_evidence_manifest_v2", "visual_evidence_id": f"visual-{snapshot['revision']}",
        **{key: snapshot[key] for key in ("market", "window", "effective_trading_date", "snapshot_id", "revision", "payload_hash")},
        "batch_id": snapshot["run_id"], "generated_at": snapshot["generated_at"], "capture_origin": snapshot["run_kind"],
        "capture": {"status": "SUCCESS"},
        "files": {key: {"path": name, "sha256": digest(target / name), "size_bytes": (target / name).stat().st_size} for key, (name, _) in files.items()},
    }
    (target / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return target


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    temp_path = ""
    with tempfile.TemporaryDirectory(prefix="ai-dev-211-") as raw:
        temp_path = raw; base = Path(raw); archive = base / "archive"; snapshots = archive / "window_snapshots"
        visual = archive / "visual_evidence"; exports = base / "exports"; outbox = base / "outbox"
        scheduled = put_snapshot(snapshots, run_kind="scheduled", marker="scheduled"); scheduled_dir = put_visual(visual, scheduled)
        manual = put_snapshot(snapshots, run_kind="manual_rerun", marker="manual"); manual_dir = put_visual(visual, manual)
        records = []
        for snapshot, target in ((scheduled, scheduled_dir), (manual, manual_dir)):
            records.append({
                "visual_evidence_id": f"visual-{snapshot['revision']}", "effective_trading_date": "2026-08-14",
                "market": "US", "window": "us_pre_market_2000", "revision": snapshot["revision"],
                "capture_status": "SUCCESS", "manifest_path": target.relative_to(visual).joinpath("manifest.json").as_posix(),
                "source_snapshot_id": snapshot["snapshot_id"], "created_at": snapshot["generated_at"],
            })
        visual.mkdir(parents=True, exist_ok=True); (visual / "index.json").write_text(json.dumps({"records": records}), encoding="utf-8")
        archive_before = tree_digest(visual)

        pdf = prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000",
            revision=2, artifact="pdf", visual_root=visual, export_root=exports, outbox_root=outbox)
        review = prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000",
            revision="latest_valid", artifact="review_bundle", visual_root=visual, export_root=exports, outbox_root=outbox)
        checks["case_a_exact_pdf"] = pdf["status"] == "READY_FOR_EXTERNAL_CONNECTOR" and pdf["sha256"] == digest(manual_dir / "dashboard_full.pdf")
        checks["case_b_review_bundle"] = review["status"] == "READY_FOR_EXTERNAL_CONNECTOR" and review["artifact_type"] == "review_bundle"
        bundle_path = Path(review["outbox_location"]) / review["filename"]
        with zipfile.ZipFile(bundle_path) as bundle:
            names = set(bundle.namelist()); context = json.loads(bundle.read("review_context.json"))
        checks["case_c_allowlist_only"] = names == COMPACT_REVIEW_FILES
        checks["case_d_bundle_identity_hash"] = context["identity"]["snapshot_id"] == manual["snapshot_id"] and digest(bundle_path) == review["sha256"]
        checks["case_e_manual_provenance"] = context["batch"]["run_kind"] == "manual_rerun" and context["batch"]["runtime_provenance"] == "manual_rerun"
        scheduled_review = export_visual_evidence(effective_date="2026-08-14", market="US", window="us_pre_market_2000",
            revision=1, artifact="review_bundle", visual_root=visual, export_root=exports)
        with zipfile.ZipFile(scheduled_review["safe_export_location"]) as bundle:
            scheduled_context = json.loads(bundle.read("review_context.json"))
        checks["case_f_scheduled_provenance"] = scheduled_context["batch"]["run_kind"] == "scheduled" and scheduled_context["batch"]["runtime_provenance"] == "scheduled_production"

        rejected = {
            "traversal": prepare_chatgpt_transport(effective_date="../2026-08-14", market="US", window="us_pre_market_2000", artifact="pdf", visual_root=visual, export_root=exports, outbox_root=outbox),
            "absolute": prepare_chatgpt_transport(effective_date="/etc/passwd", market="US", window="us_pre_market_2000", artifact="pdf", visual_root=visual, export_root=exports, outbox_root=outbox),
            "secret": prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000", artifact=".env", visual_root=visual, export_root=exports, outbox_root=outbox),
            "db": prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000", artifact="stock.db", visual_root=visual, export_root=exports, outbox_root=outbox),
            "log": prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000", artifact="runtime.log", visual_root=visual, export_root=exports, outbox_root=outbox),
            "source": prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000", artifact="source.py", visual_root=visual, export_root=exports, outbox_root=outbox),
            "unknown_window": prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="bad", artifact="pdf", visual_root=visual, export_root=exports, outbox_root=outbox),
            "unknown_revision": prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000", revision=999, artifact="pdf", visual_root=visual, export_root=exports, outbox_root=outbox),
        }
        checks["case_g_h_j_security_rejected"] = all(value["status"] == "FAILED" for value in rejected.values())
        outside = base / "outside"; outside.mkdir(); (outside / "manifest.json").write_text("{}")
        symlink_visual = base / "symlink_visual"; symlink_visual.mkdir(); (symlink_visual / "link").symlink_to(outside, target_is_directory=True)
        (symlink_visual / "index.json").write_text(json.dumps({"records": [{**records[0], "manifest_path": "link/manifest.json"}]}))
        symlink = prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000", revision=1, artifact="manifest", visual_root=symlink_visual, export_root=exports, outbox_root=outbox)
        checks["case_i_symlink_escape"] = symlink["status"] == "FAILED" and symlink["reason_code"] == "TRANSPORT_FORBIDDEN"
        original_manifest_bytes = (manual_dir / "manifest.json").read_bytes()
        mismatch_manifest = json.loads(original_manifest_bytes); mismatch_manifest["snapshot_id"] = "mutated"
        (manual_dir / "manifest.json").write_text(json.dumps(mismatch_manifest), encoding="utf-8")
        mismatch = prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000", revision=2, artifact="review_bundle", visual_root=visual, export_root=exports, outbox_root=outbox)
        checks["case_k_identity_mismatch"] = mismatch["status"] == "FAILED" and mismatch["reason_code"] == "SELECTOR_IDENTITY_MISMATCH"
        (manual_dir / "manifest.json").write_bytes(original_manifest_bytes)
        checks["case_l_unknown_selector"] = rejected["unknown_window"]["status"] == "FAILED" and rejected["unknown_revision"]["status"] == "FAILED"
        nonblocking = prepare_transport_non_blocking(effective_date="2099-01-01", market="US", window="us_pre_market_2000", artifact="pdf", visual_root=visual, export_root=exports, outbox_root=outbox)
        checks["case_m_failure_nonblocking"] = nonblocking["status"] == "FAILED" and nonblocking["production_batch_continues"] is True
        repeat = prepare_chatgpt_transport(effective_date="2026-08-14", market="US", window="us_pre_market_2000", revision=2, artifact="pdf", visual_root=visual, export_root=exports, outbox_root=outbox)
        checks["case_n_deterministic_envelope"] = repeat["request_id"] == pdf["request_id"] and repeat["envelope_sha256"] == pdf["envelope_sha256"]
        checks["case_o_archive_read_only"] = archive_before == tree_digest(visual)
        checks["case_q_seven_windows"] = sum(len(items) for items in MARKET_WINDOWS.values()) == 7
        checks["case_t_truthful_transport_boundary"] = review["transport_status"] == TRANSPORT_STATUS and review["external_connector_required"] is True and review["reason_code"] == "TRANSPORT_NOT_CONFIGURED"
        details = {"pdf": pdf, "review_bundle": review, "rejected": rejected, "transport_capability": TRANSPORT_STATUS}

        ai210 = subprocess.run([sys.executable, str(ROOT / "scripts/orchestrator/validate_ai_dev_210_visual_evidence_pdf_retrieval_v1.py")], cwd=ROOT, text=True, capture_output=True)
        h3 = subprocess.run([sys.executable, str(ROOT / "scripts/orchestrator/validate_ai_dev_209_h3_user_visible_research_presentation_v1.py")], cwd=ROOT, text=True, capture_output=True)
        checks["case_r_ai210_regression"] = ai210.returncode == 0 and bool(json.loads(ai210.stdout).get("ok"))
        checks["case_s_h3_regression"] = h3.returncode == 0 and bool(json.loads(h3.stdout).get("ok"))
    checks["case_p_temporary_root_cleaned"] = not Path(temp_path).exists()
    errors = [name for name, passed in checks.items() if not passed]
    return {"schema_version": "ai_dev_211_transport_validation_v1", "task_id": "AI-DEV-211", "ok": not errors,
        "checks": checks, "errors": errors, "details": details,
        "direct_chatgpt_transport_status": TRANSPORT_STATUS,
        "safety": {"network_transport": False, "public_endpoint": False, "secrets": False, "production_pipeline": False,
                   "notification": False, "trading": False, "production_db": False, "immutable_history_rewritten": False}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = validate(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
