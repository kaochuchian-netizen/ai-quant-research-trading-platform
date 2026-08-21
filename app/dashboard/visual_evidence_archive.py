"""Read-only browser capture and immutable Visual Evidence Archive.

Visual evidence is a downstream QA projection of an admitted window snapshot.
It never feeds research, prediction, Decision, delivery, or trading ownership.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.dashboard.dashboard_url_registry import get_window_archive_path
from app.dashboard.market_dashboard_alias import snapshot_parity_contract
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS, admission_errors, resolve_snapshots

SCHEMA_VERSION = "visual_evidence_manifest_v2"
INDEX_SCHEMA_VERSION = "visual_evidence_index_v1"
REVIEW_SCHEMA_VERSION = "visual_evidence_daily_review_v1"
VIEWPORT = {"width": 1440, "height": 1200}
DEFAULT_TIMEOUT_MS = 45_000
REPO_ROOT = Path(__file__).resolve().parents[2]
USER_BROWSER_LIB_ROOT = Path.home() / ".cache/stock-ai-playwright-libs/root"
USER_CJK_FONT_ROOT = Path.home() / ".cache/stock-ai-fonts/noto-cjk-tc"
USER_CJK_FONT_CONFIG = USER_CJK_FONT_ROOT / "fonts.conf"
CJK_PROBE_TEXT = "研究證據假設風險台灣美股"
DEFAULT_VISUAL_ROOT = Path(
    os.environ.get("STOCK_AI_VISUAL_EVIDENCE_ROOT", REPO_ROOT / "artifacts/archive/visual_evidence")
)


def _now() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    temporary.write_text(_stable_json(value), encoding="utf-8")
    temporary.replace(path)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _capture_id(identity: dict[str, Any]) -> str:
    raw = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _expected_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    parity = snapshot_parity_contract(snapshot) or {}
    return {
        "market": parity.get("market"),
        "window": parity.get("active_window"),
        "effective_trading_date": parity.get("effective_trading_date"),
        "snapshot_id": parity.get("snapshot_id"),
        "revision": int(parity.get("revision") or 0),
        "payload_hash": parity.get("payload_hash"),
    }


def _normalize_observed_identity(value: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "market": value.get("market"),
        "window": value.get("window"),
        "effective_trading_date": value.get("effectiveTradingDate") or value.get("effective_trading_date"),
        "snapshot_id": value.get("snapshotId") or value.get("snapshot_id"),
        "revision": value.get("revision"),
        "payload_hash": value.get("payloadHash") or value.get("payload_hash"),
    }
    try:
        normalized["revision"] = int(normalized["revision"])
    except (TypeError, ValueError):
        pass
    return normalized


def _identity_mismatches(expected: dict[str, Any], observed: dict[str, Any]) -> list[str]:
    return [key for key, expected_value in expected.items() if observed.get(key) != expected_value]


def _browser_render(
    source: Path,
    screenshot: Path,
    pdf: Path,
    *,
    timeout_ms: int,
    viewport: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Render the final route with a real headless Chromium browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment failure
        raise RuntimeError("BROWSER_START_FAILED:playwright_not_installed") from exc

    browser_env = dict(os.environ)
    user_library_paths = [
        USER_BROWSER_LIB_ROOT / "usr/lib/x86_64-linux-gnu",
        USER_BROWSER_LIB_ROOT / "lib/x86_64-linux-gnu",
    ]
    available_library_paths = [str(path) for path in user_library_paths if path.is_dir()]
    previous_skip_validation = os.environ.get("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS")
    if available_library_paths:
        existing = browser_env.get("LD_LIBRARY_PATH")
        browser_env["LD_LIBRARY_PATH"] = ":".join(available_library_paths + ([existing] if existing else []))
        # Playwright's driver validates only the system linker cache. The
        # repo-user bundle is verified by the actual browser launch instead.
        os.environ["PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS"] = "1"
    if USER_CJK_FONT_CONFIG.is_file():
        browser_env["FONTCONFIG_FILE"] = str(USER_CJK_FONT_CONFIG)
        browser_env["FONTCONFIG_PATH"] = str(USER_CJK_FONT_ROOT)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage"],
                    env=browser_env,
                )
            except Exception as exc:  # pragma: no cover - environment failure
                raise RuntimeError("BROWSER_START_FAILED") from exc
            try:
                page = browser.new_page(viewport=viewport or VIEWPORT)
                response = page.goto(source.resolve().as_uri(), wait_until="networkidle", timeout=timeout_ms)
                if response is not None and not response.ok:
                    raise RuntimeError(f"PAGE_HTTP_ERROR:{response.status}")
                page.wait_for_selector("body[data-snapshot-id]", state="attached", timeout=timeout_ms)
                page.emulate_media(media="screen")
                font_diagnostics = page.evaluate(
                    """probe => {
                      const family = 'Noto Sans CJK TC';
                      const loaded = document.fonts.check(`24px "${family}"`, probe);
                      const signatures = [...probe].map(ch => {
                        const canvas = document.createElement('canvas');
                        canvas.width = 64; canvas.height = 64;
                        const ctx = canvas.getContext('2d');
                        ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 64, 64);
                        ctx.fillStyle = '#000'; ctx.font = `32px "${family}"`; ctx.fillText(ch, 8, 42);
                        const data = ctx.getImageData(0, 0, 64, 64).data;
                        let ink = 0, hash = 2166136261;
                        for (let i = 0; i < data.length; i += 4) {
                          if (data[i] < 245 || data[i+1] < 245 || data[i+2] < 245) ink++;
                          hash ^= data[i]; hash = Math.imul(hash, 16777619);
                        }
                        return `${ink}:${hash >>> 0}`;
                      });
                      return {contract_version: 'cjk_visual_glyph_gate_v1', family, probe,
                        font_loaded: loaded, glyph_count: signatures.length,
                        unique_glyph_signatures: new Set(signatures).size,
                        glyph_signatures: signatures};
                    }""",
                    CJK_PROBE_TEXT,
                )
                if not font_diagnostics.get("font_loaded") or int(font_diagnostics.get("unique_glyph_signatures") or 0) < 6:
                    raise RuntimeError("CJK_FONT_UNAVAILABLE")
                identity = page.locator("body").evaluate("element => ({...element.dataset})")
                # Preserve the published DOM snapshot as-is, then expand only
                # allowlisted PM-facing research details in the in-memory page
                # used for review text, screenshot and PDF evidence.
                rendered_html = page.content()
                expanded_details = page.locator('details[data-visual-review-expand="true"]')
                expanded_details_count = expanded_details.count()
                if expanded_details_count:
                    expanded_details.evaluate_all(
                        "elements => elements.forEach(element => { element.open = true; })"
                    )
                visible_text = page.locator("body").inner_text()
                page.screenshot(path=str(screenshot), full_page=True)
                pdf_error = None
                try:
                    page.emulate_media(media="print")
                    page.pdf(
                        path=str(pdf),
                        print_background=True,
                        format="A4",
                        prefer_css_page_size=True,
                    )
                    if not pdf.is_file() or pdf.stat().st_size == 0:
                        pdf_error = "PDF_WRITE_FAILED"
                except Exception:
                    pdf_error = "PDF_RENDER_FAILED"
                return {
                    "html": rendered_html,
                    "text": visible_text,
                    "identity": _normalize_observed_identity(identity),
                    "pdf_error": pdf_error,
                    "font_diagnostics": font_diagnostics,
                    "review_details": {
                        "selector": 'details[data-visual-review-expand="true"]',
                        "expanded_count": expanded_details_count,
                        "mode": "ALLOWLISTED_PM_RESEARCH_DETAILS",
                        "published_dom_modified": False,
                    },
                }
            except RuntimeError:
                raise
            except Exception as exc:  # pragma: no cover - browser-specific failure
                name = exc.__class__.__name__.lower()
                reason = "PAGE_RENDER_TIMEOUT" if "timeout" in name or "timeout" in str(exc).lower() else "HTML_CAPTURE_FAILED"
                raise RuntimeError(reason) from exc
            finally:
                browser.close()
    finally:
        if previous_skip_validation is None:
            os.environ.pop("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", None)
        else:
            os.environ["PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS"] = previous_skip_validation


def _load_index(root: Path) -> dict[str, Any]:
    path = root / "index.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    records = value.get("records") if isinstance(value.get("records"), list) else []
    return {"schema_version": INDEX_SCHEMA_VERSION, "records": records}


def _update_index(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    index = _load_index(root)
    records = [item for item in index["records"] if item.get("visual_evidence_id") != record["visual_evidence_id"]]
    records.append(record)
    records.sort(
        key=lambda item: (
            str(item.get("effective_trading_date") or ""),
            str(item.get("market") or ""),
            str(item.get("window") or ""),
            int(item.get("revision") or 0),
            str(item.get("capture_status") or ""),
            str(item.get("visual_evidence_id") or ""),
        )
    )
    index["records"] = records
    _atomic_json(root / "index.json", index)
    return index


def _failure_reason(exc: Exception) -> str:
    message = str(exc)
    for code in (
        "ROUTE_NOT_FOUND",
        "PAGE_HTTP_ERROR",
        "PAGE_RENDER_TIMEOUT",
        "BROWSER_START_FAILED",
        "SCREENSHOT_WRITE_FAILED",
        "HTML_CAPTURE_FAILED",
        "MANIFEST_WRITE_FAILED",
        "IDENTITY_MISMATCH",
        "IDENTITY_CONFLICT",
        "PDF_RENDER_FAILED",
        "PDF_WRITE_FAILED",
        "CJK_FONT_UNAVAILABLE",
    ):
        if message.startswith(code):
            return code
    return "HTML_CAPTURE_FAILED"


def _record_failure(
    root: Path,
    *,
    identity: dict[str, Any],
    dashboard_path: Path,
    visual_evidence_id: str,
    reason: str,
    capture_origin: str,
    started_at: str,
    observed_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # A failed attempt is its own immutable QA event.  It must not share the
    # successful capture identity, otherwise a later successful retry would
    # replace the failed index record and erase latest-attempt history.
    visual_evidence_id = _capture_id({
        **identity,
        "capture_status": "FAILED",
        "reason_code": reason,
        "started_at": started_at,
    })
    completed_at = _now()
    failure_dir = (
        root
        / str(identity["effective_trading_date"])
        / str(identity["market"])
        / str(identity["window"])
        / "failures"
    )
    manifest_path = failure_dir / f"revision_{int(identity['revision']):03d}_{visual_evidence_id[:12]}.json"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "visual_evidence_id": visual_evidence_id,
        **identity,
        "dashboard_route": get_window_archive_path(str(identity["market"]), str(identity["window"])),
        "dashboard_source_path": str(dashboard_path),
        "capture_origin": capture_origin,
        "requested_identity": identity,
        "capture": {
            "status": "FAILED",
            "reason_code": reason,
            "started_at": started_at,
            "completed_at": completed_at,
            "renderer": "playwright-chromium",
            "viewport": VIEWPORT,
            "full_page": True,
        },
        "observed_identity": observed_identity,
        "files": {},
    }
    _atomic_json(manifest_path, manifest)
    _update_index(
        root,
        {
            "visual_evidence_id": visual_evidence_id,
            "effective_trading_date": identity["effective_trading_date"],
            "market": identity["market"],
            "window": identity["window"],
            "revision": identity["revision"],
            "capture_status": "FAILED",
            "reason_code": reason,
            "manifest_path": _relative(manifest_path, root),
            "dashboard_route": manifest["dashboard_route"],
            "source_snapshot_id": identity["snapshot_id"],
            "created_at": completed_at,
        },
    )
    try:
        review = build_daily_review_bundle(root, str(identity["effective_trading_date"]))
    except Exception as exc:  # failure evidence remains durable even if aggregation fails
        review = {"status": "FAILED", "reason_code": "MANIFEST_WRITE_FAILED", "error_type": exc.__class__.__name__}
    return {
        "status": "FAILED",
        "reason_code": reason,
        "manifest_path": str(manifest_path),
        "visual_evidence_id": visual_evidence_id,
        "daily_review": review,
    }


def capture_snapshot_visual_evidence(
    snapshot: dict[str, Any],
    dashboard_path: Path,
    *,
    output_root: Path = DEFAULT_VISUAL_ROOT,
    capture_origin: str = "scheduled",
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    renderer: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Capture one admitted immutable snapshot without mutating its source."""
    if admission_errors(snapshot):
        return {"status": "SKIPPED_INELIGIBLE", "reason_code": "BATCH_NOT_ADMITTED", "files_written": False}
    identity = _expected_identity(snapshot)
    visual_evidence_id = _capture_id(identity)
    target = (
        output_root
        / str(identity["effective_trading_date"])
        / str(identity["market"])
        / str(identity["window"])
        / f"revision_{int(identity['revision']):03d}"
    )
    manifest_path = target / "manifest.json"
    if manifest_path.is_file():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if existing.get("visual_evidence_id") == visual_evidence_id and existing.get("capture", {}).get("status") in {"SUCCESS", "DEGRADED"}:
            files = existing.get("files") if isinstance(existing.get("files"), dict) else {}
            completed_at = str(existing.get("capture", {}).get("completed_at") or _now())
            record = {
                "visual_evidence_id": visual_evidence_id,
                "effective_trading_date": identity["effective_trading_date"],
                "market": identity["market"],
                "window": identity["window"],
                "revision": identity["revision"],
                "capture_status": existing["capture"]["status"],
                "reason_code": existing["capture"].get("reason_code"),
                "manifest_path": _relative(manifest_path, output_root),
                "screenshot_path": _relative(target / "screenshot_full.png", output_root),
                "rendered_text_path": _relative(target / "rendered_text.md", output_root),
                "pdf_path": _relative(target / "dashboard_full.pdf", output_root) if (target / "dashboard_full.pdf").is_file() else None,
                "dashboard_route": existing.get("dashboard_route"),
                "source_snapshot_id": identity["snapshot_id"],
                "capture_hash": hashlib.sha256(_stable_json(files).encode("utf-8")).hexdigest(),
                "screenshot_hash": (files.get("screenshot") or {}).get("sha256"),
                "rendered_text_hash": (files.get("text") or {}).get("sha256"),
                "pdf_hash": (files.get("pdf") or {}).get("sha256"),
                "created_at": completed_at,
            }
            _update_index(output_root, record)
            review = build_daily_review_bundle(output_root, str(identity["effective_trading_date"]))
            return {
                "status": existing["capture"]["status"],
                "reason_code": existing["capture"].get("reason_code"),
                "duplicate_suppressed": True,
                "manifest_path": str(manifest_path),
                "visual_evidence_id": visual_evidence_id,
                "daily_review": review,
            }
        return _record_failure(
            output_root,
            identity=identity,
            dashboard_path=dashboard_path,
            visual_evidence_id=visual_evidence_id,
            reason="IDENTITY_CONFLICT",
            capture_origin=capture_origin,
            started_at=_now(),
        )
    if not dashboard_path.is_file():
        return _record_failure(
            output_root,
            identity=identity,
            dashboard_path=dashboard_path,
            visual_evidence_id=visual_evidence_id,
            reason="ROUTE_NOT_FOUND",
            capture_origin=capture_origin,
            started_at=_now(),
        )

    started_at = _now()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=str(target.parent)))
    screenshot_path = temporary / "screenshot_full.png"
    pdf_path = temporary / "dashboard_full.pdf"
    observed_identity: dict[str, Any] | None = None
    try:
        rendered = (renderer or _browser_render)(dashboard_path, screenshot_path, pdf_path, timeout_ms=timeout_ms)
        observed_identity = rendered.get("identity") if isinstance(rendered.get("identity"), dict) else {}
        mismatches = _identity_mismatches(identity, observed_identity)
        if mismatches:
            raise RuntimeError("IDENTITY_MISMATCH:" + ",".join(mismatches))
        if not screenshot_path.is_file() or screenshot_path.stat().st_size == 0:
            raise RuntimeError("SCREENSHOT_WRITE_FAILED")
        html_path = temporary / "rendered_page.html"
        text_path = temporary / "rendered_text.md"
        canonical_path = temporary / "canonical_reference.json"
        html_path.write_text(str(rendered.get("html") or ""), encoding="utf-8")
        visible_text = str(rendered.get("text") or "").strip()
        text_path.write_text(f"# Rendered Dashboard Text\n\n{visible_text}\n", encoding="utf-8")
        canonical_reference = {
            "schema_version": "visual_evidence_canonical_reference_v1",
            "market": identity["market"],
            "window": identity["window"],
            "effective_trading_date": identity["effective_trading_date"],
            "snapshot_id": identity["snapshot_id"],
            "revision": identity["revision"],
            "payload_hash": identity["payload_hash"],
            "archive_path": snapshot.get("archive_path"),
            "source_artifact_path": snapshot.get("source_artifact_path"),
        }
        canonical_path.write_text(_stable_json(canonical_reference), encoding="utf-8")
        file_map = {
            "screenshot": screenshot_path,
            "html": html_path,
            "text": text_path,
            "canonical": canonical_path,
        }
        pdf_error = str(rendered.get("pdf_error") or "") or None
        if not pdf_error:
            if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
                pdf_error = "PDF_WRITE_FAILED"
            else:
                file_map["pdf"] = pdf_path
        capture_status = "DEGRADED" if pdf_error else "SUCCESS"
        completed_at = _now()
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "visual_evidence_id": visual_evidence_id,
            **identity,
            "batch_id": snapshot.get("run_id"),
            "generated_at": snapshot.get("generated_at"),
            "dashboard_route": get_window_archive_path(str(identity["market"]), str(identity["window"])),
            "dashboard_source_path": str(dashboard_path),
            "capture_origin": capture_origin,
            "capture": {
                "status": capture_status,
                "reason_code": pdf_error,
                "started_at": started_at,
                "completed_at": completed_at,
                "renderer": "playwright-chromium",
                "viewport": VIEWPORT,
                "full_page": True,
                "font_diagnostics": rendered.get("font_diagnostics") or {
                    "contract_version": "cjk_visual_glyph_gate_v1",
                    "status": "NOT_EVALUATED_BY_COMPATIBILITY_RENDERER",
                },
                "review_details": rendered.get("review_details") or {
                    "selector": 'details[data-visual-review-expand="true"]',
                    "expanded_count": 0,
                    "mode": "ALLOWLISTED_PM_RESEARCH_DETAILS",
                    "published_dom_modified": False,
                },
                "pdf": {
                    "required": True,
                    "renderer": "playwright-chromium-page-pdf",
                    "print_background": True,
                    "format": "A4",
                    "identity_source": "same_browser_page_and_dom",
                    "status": "FAILED" if pdf_error else "SUCCESS",
                    "reason_code": pdf_error,
                },
            },
            "observed_identity": observed_identity,
            "files": {
                key: {"path": path.name, "sha256": _sha256(path), "size_bytes": path.stat().st_size}
                for key, path in file_map.items()
            },
        }
        manifest["screenshot_hash"] = manifest["files"]["screenshot"]["sha256"]
        manifest["rendered_text_hash"] = manifest["files"]["text"]["sha256"]
        manifest["pdf_hash"] = (manifest["files"].get("pdf") or {}).get("sha256")
        manifest["capture_hash"] = hashlib.sha256(_stable_json(manifest["files"]).encode("utf-8")).hexdigest()
        (temporary / "manifest.json").write_text(_stable_json(manifest), encoding="utf-8")
        temporary.replace(target)
        record = {
            "visual_evidence_id": visual_evidence_id,
            "effective_trading_date": identity["effective_trading_date"],
            "market": identity["market"],
            "window": identity["window"],
            "revision": identity["revision"],
            "capture_status": capture_status,
            "reason_code": pdf_error,
            "manifest_path": _relative(manifest_path, output_root),
            "screenshot_path": _relative(target / "screenshot_full.png", output_root),
            "rendered_text_path": _relative(target / "rendered_text.md", output_root),
            "pdf_path": _relative(target / "dashboard_full.pdf", output_root) if not pdf_error else None,
            "dashboard_route": manifest["dashboard_route"],
            "source_snapshot_id": identity["snapshot_id"],
            "capture_hash": manifest["capture_hash"],
            "screenshot_hash": manifest["screenshot_hash"],
            "rendered_text_hash": manifest["rendered_text_hash"],
            "pdf_hash": manifest["pdf_hash"],
            "created_at": completed_at,
        }
        _update_index(output_root, record)
        review = build_daily_review_bundle(output_root, str(identity["effective_trading_date"]))
        return {
            "status": capture_status,
            "reason_code": pdf_error,
            "duplicate_suppressed": False,
            "manifest_path": str(manifest_path),
            "visual_evidence_id": visual_evidence_id,
            "daily_review": review,
        }
    except Exception as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        return _record_failure(
            output_root,
            identity=identity,
            dashboard_path=dashboard_path,
            visual_evidence_id=visual_evidence_id,
            reason=_failure_reason(exc),
            capture_origin=capture_origin,
            started_at=started_at,
            observed_identity=observed_identity,
        )


def build_daily_review_bundle(root: Path, effective_trading_date: str) -> dict[str, Any]:
    """Build an incremental self-contained PM/ChatGPT review directory."""
    index = _load_index(root)
    day_records = [item for item in index["records"] if item.get("effective_trading_date") == effective_trading_date]
    expected = [(market, window) for market, windows in MARKET_WINDOWS.items() for window in windows]
    review_root = root / "daily_reviews" / effective_trading_date
    review_root.mkdir(parents=True, exist_ok=True)
    windows: list[dict[str, Any]] = []
    for market, window in expected:
        candidates = [
            item for item in day_records
            if item.get("market") == market and item.get("window") == window and item.get("capture_status") == "SUCCESS"
        ]
        latest = max(candidates, key=lambda item: (int(item.get("revision") or 0), str(item.get("created_at") or "")), default=None)
        failures = [
            item for item in day_records
            if item.get("market") == market and item.get("window") == window and item.get("capture_status") in {"DEGRADED", "FAILED"}
        ]
        attempts = candidates + failures
        latest_attempt = max(
            attempts,
            key=lambda item: (int(item.get("revision") or 0), str(item.get("created_at") or "")),
            default=None,
        )
        if latest:
            source = (root / str(latest["manifest_path"])).parent
            destination = review_root / market / window
            destination.mkdir(parents=True, exist_ok=True)
            review_files = ("dashboard_full.pdf", "screenshot_full.png", "rendered_page.html", "rendered_text.md", "manifest.json", "canonical_reference.json")
            # Avoid a stale PDF surviving when a later legacy-compatible valid
            # revision does not contain PDF evidence.
            for name in review_files:
                (destination / name).unlink(missing_ok=True)
            for name in review_files:
                if (source / name).is_file():
                    shutil.copy2(source / name, destination / name)
            revision = int(latest["revision"])
        else:
            revision = None
        latest_attempt_revision = int(latest_attempt["revision"]) if latest_attempt else None
        latest_attempt_status = str(latest_attempt["capture_status"]) if latest_attempt else None
        if latest_attempt_status == "SUCCESS":
            status = "SUCCESS"
        elif latest_attempt_status in {"DEGRADED", "FAILED"} and latest:
            status = "DEGRADED"
        elif latest_attempt_status == "DEGRADED":
            status = "DEGRADED"
        elif latest_attempt_status == "FAILED":
            status = "FAILED"
        else:
            status = "PENDING"
        windows.append({
            "market": market,
            "window": window,
            "status": status,
            "latest_valid_revision": revision,
            "latest_attempt_revision": latest_attempt_revision,
            "latest_attempt_status": latest_attempt_status,
        })
    manifest = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "effective_trading_date": effective_trading_date,
        "expected_window_count": len(expected),
        "available_window_count": len([item for item in windows if item["status"] in {"SUCCESS", "DEGRADED"}]),
        "failed_window_count": len([item for item in windows if item["status"] == "FAILED"]),
        "degraded_window_count": len([item for item in windows if item["status"] == "DEGRADED"]),
        "missing_window_count": len([item for item in windows if item["status"] == "PENDING"]),
        "windows": windows,
    }
    _atomic_json(review_root / "review_manifest.json", manifest)
    lines = [f"# {effective_trading_date} Visual Evidence Review", ""]
    for market in MARKET_WINDOWS:
        lines.extend([f"## {market}", ""])
        for item in [row for row in windows if row["market"] == market]:
            suffix = f" revision {item['latest_valid_revision']}" if item["latest_valid_revision"] else ""
            lines.append(f"- {item['window']}: {item['status']}{suffix}")
        lines.append("")
    (review_root / "review_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "status": "BUILT",
        "review_root": str(review_root),
        **{
            key: manifest[key]
            for key in ("available_window_count", "failed_window_count", "degraded_window_count", "missing_window_count")
        },
    }


def capture_published_snapshot_non_blocking(
    *,
    market: str,
    window: str,
    archive_write: dict[str, Any],
    public_sync: dict[str, Any],
    static_root: Path,
    snapshot_archive_root: Path,
    output_root: Path = DEFAULT_VISUAL_ROOT,
    capture_origin: str = "scheduled",
) -> dict[str, Any]:
    """Production-safe wrapper: every visual failure is returned, never raised."""
    try:
        if archive_write.get("written") is not True:
            return {"status": "SKIPPED_INELIGIBLE", "reason_code": "BATCH_NOT_ADMITTED"}
        canonical_market = str(archive_write.get("market") or market).upper()
        canonical_window = str(archive_write.get("window") or window)
        publish_result = archive_write.get("publish_result") if isinstance(archive_write.get("publish_result"), dict) else {}
        manual_ready = bool(archive_write.get("routes_rebuilt") and publish_result.get("latest_route_updated") is True)
        if public_sync.get("status") != "verified" and not manual_ready:
            return {"status": "SKIPPED_INELIGIBLE", "reason_code": "DASHBOARD_NOT_READY"}
        snapshot = resolve_snapshots(snapshot_archive_root, canonical_market, canonical_window).latest
        if not snapshot or snapshot.get("snapshot_id") != archive_write.get("snapshot_id"):
            identity = {
                "market": canonical_market,
                "window": canonical_window,
                "effective_trading_date": archive_write.get("effective_trading_date"),
                "snapshot_id": archive_write.get("snapshot_id"),
                "revision": int(archive_write.get("revision") or 0),
                "payload_hash": archive_write.get("payload_hash"),
            }
            visual_evidence_id = _capture_id(identity)
            dashboard_path = static_root / get_window_archive_path(canonical_market, canonical_window).lstrip("/")
            result = _record_failure(
                output_root,
                identity=identity,
                dashboard_path=dashboard_path,
                visual_evidence_id=visual_evidence_id,
                reason="IDENTITY_MISMATCH",
                capture_origin=capture_origin,
                started_at=_now(),
                observed_identity=_expected_identity(snapshot) if snapshot else None,
            )
            result["production_batch_continues"] = True
            return result
        dashboard_path = static_root / get_window_archive_path(canonical_market, canonical_window).lstrip("/")
        result = capture_snapshot_visual_evidence(
            snapshot,
            dashboard_path,
            output_root=output_root,
            capture_origin=capture_origin,
        )
        result["production_batch_continues"] = True
        return result
    except Exception as exc:  # pragma: no cover - final isolation boundary
        return {
            "status": "FAILED",
            "reason_code": _failure_reason(exc),
            "production_batch_continues": True,
        }
