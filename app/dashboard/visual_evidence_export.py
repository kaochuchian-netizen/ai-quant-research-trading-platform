"""Fail-closed, index-driven Visual Evidence retrieval/export.

Selectors are canonical identities, never filesystem paths.  This layer is a
safe handoff mechanism; it does not provide direct ChatGPT transport.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from app.dashboard.visual_evidence_archive import DEFAULT_VISUAL_ROOT
from app.dashboard.market_dashboard_alias import payload_hash
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS

EXPORT_SCHEMA = "visual_evidence_export_v1"
TRANSPORT_STATUS = "DIRECT_CHATGPT_TRANSPORT_PENDING_EXTERNAL_CAPABILITY"
REVIEW_BUNDLE_SCHEMA = "chatgpt_visual_review_bundle_v1"
DEFAULT_EXPORT_ROOT = Path(os.environ.get(
    "STOCK_AI_VISUAL_EXPORT_ROOT",
    Path(__file__).resolve().parents[2] / "artifacts/runtime/visual_evidence_exports",
))
ARTIFACT_FILES = {
    "pdf": ("pdf", "dashboard_full.pdf", "application/pdf"),
    "png": ("screenshot", "screenshot_full.png", "image/png"),
    "text": ("text", "rendered_text.md", "text/markdown"),
    "html": ("html", "rendered_page.html", "text/html"),
    "canonical": ("canonical", "canonical_reference.json", "application/json"),
}
ALLOWED_REVIEW_FILES = {
    "dashboard_full.pdf", "screenshot_full.png", "rendered_page.html",
    "rendered_text.md", "canonical_reference.json", "manifest.json",
    "review_manifest.json", "review_summary.md",
}
COMPACT_REVIEW_FILES = {
    "dashboard_full.pdf", "screenshot_full.png", "rendered_text.md",
    "canonical_reference.json", "manifest.json", "review_context.json",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject(reason: str, **context: Any) -> dict[str, Any]:
    return {"schema_version": EXPORT_SCHEMA, "status": "REJECTED", "reason_code": reason,
            "chatgpt_transport_status": TRANSPORT_STATUS, **context}


def _safe_child(root: Path, relative: str) -> Path | None:
    candidate = PurePosixPath(str(relative))
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        return None
    path = root.joinpath(*candidate.parts)
    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
        return None
    return resolved


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _validate_selector(effective_date: str, market: str | None, window: str | None, artifact: str, revision: str | int) -> str | None:
    try:
        date.fromisoformat(effective_date)
    except (TypeError, ValueError):
        return "INVALID_SELECTOR"
    if artifact not in {*ARTIFACT_FILES, "manifest", "daily_bundle", "review_bundle"}:
        return "ARTIFACT_NOT_ALLOWLISTED"
    if artifact == "daily_bundle":
        return None if market is None and window is None else "INVALID_SELECTOR"
    if market not in MARKET_WINDOWS or window not in MARKET_WINDOWS[market]:
        return "UNKNOWN_MARKET_WINDOW"
    if revision != "latest_valid":
        try:
            if int(revision) <= 0:
                return "UNKNOWN_REVISION"
        except (TypeError, ValueError):
            return "UNKNOWN_REVISION"
    return None


def _select_record(root: Path, effective_date: str, market: str, window: str, revision: str | int) -> dict[str, Any] | None:
    index = _load_json(root / "index.json")
    candidates = [record for record in index.get("records", []) if isinstance(record, dict)
                  and record.get("effective_trading_date") == effective_date
                  and record.get("market") == market and record.get("window") == window
                  and record.get("capture_status") == "SUCCESS"]
    if revision == "latest_valid":
        return max(candidates, key=lambda item: (int(item.get("revision") or 0), str(item.get("created_at") or "")), default=None)
    return next((item for item in candidates if int(item.get("revision") or 0) == int(revision)), None)


def _copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + f".tmp-{os.getpid()}")
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def _single_export(root: Path, export_root: Path, effective_date: str, market: str, window: str, revision: str | int, artifact: str) -> dict[str, Any]:
    record = _select_record(root, effective_date, market, window, revision)
    if not record:
        return _reject("EVIDENCE_NOT_FOUND", effective_date=effective_date, market=market, window=window,
                       revision=revision, artifact_type=artifact)
    manifest_path = _safe_child(root, str(record.get("manifest_path") or ""))
    if manifest_path is None or manifest_path.name != "manifest.json":
        return _reject("MANIFEST_NOT_ALLOWLISTED", effective_date=effective_date, market=market, window=window)
    manifest = _load_json(manifest_path)
    if manifest.get("visual_evidence_id") != record.get("visual_evidence_id"):
        return _reject("IDENTITY_MISMATCH", effective_date=effective_date, market=market, window=window)
    if artifact == "manifest":
        source, media_type, expected_hash = manifest_path, "application/json", None
    else:
        key, filename, media_type = ARTIFACT_FILES[artifact]
        metadata = (manifest.get("files") or {}).get(key)
        if not isinstance(metadata, dict):
            reason = "PDF_NOT_CAPTURED" if artifact == "pdf" else "ARTIFACT_NOT_AVAILABLE"
            return {"schema_version": EXPORT_SCHEMA, "status": "NOT_AVAILABLE", "reason_code": reason,
                    "effective_date": effective_date, "market": market, "window": window,
                    "revision": int(record["revision"]), "visual_evidence_id": record["visual_evidence_id"],
                    "snapshot_id": record.get("source_snapshot_id"), "artifact_type": artifact,
                    "source_manifest": str(record["manifest_path"]), "chatgpt_transport_status": TRANSPORT_STATUS}
        if metadata.get("path") != filename:
            return _reject("ARTIFACT_NOT_ALLOWLISTED", effective_date=effective_date, market=market, window=window)
        source = _safe_child(manifest_path.parent, filename)
        if source is None:
            return _reject("SYMLINK_OR_PATH_ESCAPE", effective_date=effective_date, market=market, window=window)
        expected_hash = str(metadata.get("sha256") or "")
        if not expected_hash or _sha256(source) != expected_hash or source.stat().st_size != int(metadata.get("size_bytes") or -1):
            return _reject("HASH_OR_SIZE_MISMATCH", effective_date=effective_date, market=market, window=window)
    destination = export_root / effective_date / market / window / f"revision_{int(record['revision']):03d}" / source.name
    _copy_atomic(source, destination)
    digest = _sha256(destination)
    if expected_hash and digest != expected_hash:
        return _reject("EXPORT_HASH_MISMATCH", effective_date=effective_date, market=market, window=window)
    return {
        "schema_version": EXPORT_SCHEMA, "status": "SUCCESS", "reason_code": None,
        "effective_date": effective_date, "market": market, "window": window,
        "revision": int(record["revision"]), "visual_evidence_id": record["visual_evidence_id"],
        "snapshot_id": record.get("source_snapshot_id"), "artifact_type": artifact,
        "filename": destination.name, "media_type": media_type,
        "size": destination.stat().st_size, "sha256": digest,
        "safe_export_location": str(destination), "source_manifest": str(record["manifest_path"]),
        "chatgpt_transport_status": TRANSPORT_STATUS,
    }


def _daily_bundle(root: Path, export_root: Path, effective_date: str) -> dict[str, Any]:
    review_root = root / "daily_reviews" / effective_date
    try:
        review_root = review_root.resolve(strict=True)
        review_root.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return _reject("DAILY_REVIEW_NOT_FOUND", effective_date=effective_date, artifact_type="daily_bundle")
    files: list[tuple[Path, str]] = []
    for path in sorted(review_root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name not in ALLOWED_REVIEW_FILES:
            if path.is_file():
                return _reject("DAILY_BUNDLE_NON_ALLOWLISTED_FILE", effective_date=effective_date)
            continue
        relative = path.relative_to(review_root).as_posix()
        if ".." in PurePosixPath(relative).parts:
            return _reject("SYMLINK_OR_PATH_ESCAPE", effective_date=effective_date)
        files.append((path, relative))
    if not any(relative == "review_manifest.json" for _, relative in files):
        return _reject("DAILY_REVIEW_NOT_FOUND", effective_date=effective_date)
    destination = export_root / effective_date / f"daily_review_{effective_date}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=".daily-review-", suffix=".zip", dir=destination.parent)
    os.close(fd)
    temporary = Path(raw_temp)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path, relative in files:
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "schema_version": EXPORT_SCHEMA, "status": "SUCCESS", "reason_code": None,
        "effective_date": effective_date, "market": None, "window": None, "revision": "latest_valid",
        "visual_evidence_id": None, "snapshot_id": None, "artifact_type": "daily_bundle",
        "filename": destination.name, "media_type": "application/zip", "size": destination.stat().st_size,
        "sha256": _sha256(destination), "safe_export_location": str(destination),
        "source_manifest": str(review_root / "review_manifest.json"),
        "included_file_count": len(files), "chatgpt_transport_status": TRANSPORT_STATUS,
    }


def _research_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    contract = payload.get("dashboard_ready_contract") if isinstance(payload.get("dashboard_ready_contract"), dict) else {}
    cards = contract.get("cards") if isinstance(contract.get("cards"), list) else []
    symbols: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        bundle = card.get("institutional_research") if isinstance(card.get("institutional_research"), dict) else {}
        news = bundle.get("news_intelligence_v2") if isinstance(bundle.get("news_intelligence_v2"), dict) else {}
        funnel = news.get("evidence_funnel") if isinstance(news.get("evidence_funnel"), dict) else {}
        stages = funnel.get("stages") if isinstance(funnel.get("stages"), dict) else {}
        projection = bundle.get("research_intelligence_v2") if isinstance(bundle.get("research_intelligence_v2"), dict) else {}
        symbols.append({
            "symbol": card.get("symbol"),
            "research_identity": projection.get("window_research_identity") or bundle.get("research_identity"),
            "research_stance": projection.get("research_stance"),
            "news_absence_state": funnel.get("absence_state"),
            "news_counts": {key: int(stages.get(key) or 0) for key in ("DISCOVERED", "ADMITTED", "RRE_USED", "RENDERED")},
            "selected_news_count": len(news.get("selected_items") or []),
            "trade_action_export": (bundle.get("decision_context_export") or {}).get("trade_action"),
        })
    return {"symbol_count": len(symbols), "symbols": symbols}


def _review_context(root: Path, manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    canonical_path = _safe_child(manifest_path.parent, "canonical_reference.json")
    if canonical_path is None:
        return None
    canonical = _load_json(canonical_path)
    identity_keys = ("market", "window", "effective_trading_date", "snapshot_id", "revision", "payload_hash")
    if any(canonical.get(key) != manifest.get(key) for key in identity_keys):
        return None
    snapshot_path = (
        root.parent / "window_snapshots" / str(manifest["market"]).lower() / str(manifest["window"])
        / str(manifest["effective_trading_date"]) / f"revision-{int(manifest['revision']):04d}.json"
    )
    snapshot = _load_json(snapshot_path) if snapshot_path.is_file() else {}
    if snapshot and not snapshot.get("payload_hash") and isinstance(snapshot.get("payload"), dict):
        snapshot["payload_hash"] = payload_hash(snapshot["payload"])
    if snapshot and any(snapshot.get(key) != manifest.get(key) for key in identity_keys):
        return None
    return {
        "schema_version": "chatgpt_visual_review_context_v1",
        "identity": {key: manifest.get(key) for key in identity_keys},
        "visual_evidence_id": manifest.get("visual_evidence_id"),
        "batch": {
            "run_id": snapshot.get("run_id") or manifest.get("batch_id"),
            "run_kind": snapshot.get("run_kind") or manifest.get("capture_origin"),
            "runtime_provenance": snapshot.get("runtime_provenance") or manifest.get("capture_origin"),
            "generated_at": snapshot.get("generated_at") or manifest.get("generated_at"),
            "admitted": snapshot.get("admitted"),
            "capture_origin": manifest.get("capture_origin"),
        },
        "research": _research_context(snapshot),
        "decision_safety": {
            "visual_evidence_is_decision_source": False,
            "trade_action_authority": "canonical_decision_layer_only",
            "transport_modifies_decision": False,
        },
        "source_manifest": manifest_path.relative_to(root).as_posix(),
    }


def _review_bundle(root: Path, export_root: Path, effective_date: str, market: str,
                   window: str, revision: str | int) -> dict[str, Any]:
    record = _select_record(root, effective_date, market, window, revision)
    if not record:
        return _reject("ARTIFACT_NOT_FOUND", effective_date=effective_date, market=market,
                       window=window, revision=revision, artifact_type="review_bundle")
    manifest_path = _safe_child(root, str(record.get("manifest_path") or ""))
    if manifest_path is None or manifest_path.name != "manifest.json":
        return _reject("TRANSPORT_FORBIDDEN", effective_date=effective_date, market=market, window=window)
    manifest = _load_json(manifest_path)
    identity = (manifest.get("visual_evidence_id"), manifest.get("snapshot_id"), manifest.get("revision"))
    if identity != (record.get("visual_evidence_id"), record.get("source_snapshot_id"), record.get("revision")):
        return _reject("SELECTOR_IDENTITY_MISMATCH", effective_date=effective_date, market=market, window=window)
    context = _review_context(root, manifest_path, manifest)
    if context is None:
        return _reject("SELECTOR_IDENTITY_MISMATCH", effective_date=effective_date, market=market, window=window)
    sources: list[tuple[Path, str]] = []
    required = {"pdf": "dashboard_full.pdf", "screenshot": "screenshot_full.png", "text": "rendered_text.md", "canonical": "canonical_reference.json"}
    for key, filename in required.items():
        metadata = (manifest.get("files") or {}).get(key)
        source = _safe_child(manifest_path.parent, filename)
        if not isinstance(metadata, dict) or metadata.get("path") != filename or source is None:
            return _reject("ARTIFACT_NOT_FOUND", effective_date=effective_date, market=market, window=window)
        if _sha256(source) != metadata.get("sha256") or source.stat().st_size != metadata.get("size_bytes"):
            return _reject("ARTIFACT_HASH_MISMATCH", effective_date=effective_date, market=market, window=window)
        sources.append((source, filename))
    sources.append((manifest_path, "manifest.json"))
    destination = export_root / effective_date / market / window / f"revision_{int(record['revision']):03d}" / "review_bundle.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=".review-bundle-", suffix=".zip", dir=destination.parent)
    os.close(fd)
    temporary = Path(raw_temp)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for source, filename in sorted(sources, key=lambda item: item[1]):
                info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            info = zipfile.ZipInfo("review_context.json", date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            archive.writestr(info, (json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "schema_version": EXPORT_SCHEMA, "bundle_schema_version": REVIEW_BUNDLE_SCHEMA,
        "status": "SUCCESS", "reason_code": None, "effective_date": effective_date,
        "market": market, "window": window, "revision": int(record["revision"]),
        "visual_evidence_id": record["visual_evidence_id"], "snapshot_id": record.get("source_snapshot_id"),
        "artifact_type": "review_bundle", "filename": destination.name, "media_type": "application/zip",
        "size": destination.stat().st_size, "sha256": _sha256(destination),
        "safe_export_location": str(destination), "source_manifest": str(record["manifest_path"]),
        "included_files": sorted(COMPACT_REVIEW_FILES), "chatgpt_transport_status": TRANSPORT_STATUS,
        "batch_provenance": context["batch"],
    }


def export_visual_evidence(*, effective_date: str, artifact: str, market: str | None = None,
                           window: str | None = None, revision: str | int = "latest_valid",
                           visual_root: Path = DEFAULT_VISUAL_ROOT,
                           export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    reason = _validate_selector(effective_date, market, window, artifact, revision)
    if reason:
        return _reject(reason, effective_date=effective_date, market=market, window=window,
                       revision=revision, artifact_type=artifact)
    if artifact == "daily_bundle":
        return _daily_bundle(visual_root, export_root, effective_date)
    if artifact == "review_bundle":
        return _review_bundle(visual_root, export_root, effective_date, str(market), str(window), revision)
    return _single_export(visual_root, export_root, effective_date, str(market), str(window), revision, artifact)
