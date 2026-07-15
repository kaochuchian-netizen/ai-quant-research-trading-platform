#!/usr/bin/env python3
"""Validate production Landing integrity and exclusive route ownership."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard import multi_market_dashboard as production
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS
from scripts.orchestrator import approved_pre_open_delivery as scheduler_legacy
from scripts.orchestrator import publish_four_window_dashboard_preview_v1 as legacy_preview

PUBLIC_URL = "http://35.201.242.167/stock-ai-dashboard/index.html"
FORBIDDEN = (
    "stock ai legacy / debug landing",
    "legacy / debug landing",
    "raw pipeline report content",
    "正式決策入口已移至四時段",
    "本次批次狀態",
)
REQUIRED_MARKERS = (
    "台股 Dashboard", "美股 Dashboard", "批次報告歷史",
    "台股手動批次", "美股手動批次", "系統營運中心",
)
EXPECTED_WINDOWS = {(market, window) for market, windows in MARKET_WINDOWS.items() for window in windows}
EXPECTED_ARCHIVE_URLS = {
    f"/stock-ai-dashboard/dashboard/archive/{market.lower()}/{window}/{selection}/index.html"
    for market, window in EXPECTED_WINDOWS for selection in ("latest", "previous")
}


class InventoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.archive_urls: list[str] = []
        self.manual: list[tuple[str, str]] = []
        self.operations: list[tuple[str, str]] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if tag == "a":
            self.links.append(values.get("href", ""))
            if "archive-browser-button" in classes:
                self.archive_urls.append(values.get("href", ""))
        if tag == "button" and "manual-batch-button" in classes:
            self.manual.append((values.get("data-market", ""), values.get("data-window", "")))
        if tag == "tr" and values.get("data-market") and values.get("data-window"):
            self.operations.append((values["data-market"], values["data-window"]))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inventory(page: str, *, exact_markers: bool = True) -> dict[str, Any]:
    parser = InventoryParser()
    parser.feed(page)
    lowered = page.lower()
    markers = {marker: marker in page for marker in REQUIRED_MARKERS}
    if not exact_markers:
        markers["批次報告歷史"] = markers["批次報告歷史"] or 'id="snapshot-archive-browser"' in page
        markers["系統營運中心"] = markers["系統營運中心"] or 'id="production-operations-center"' in page
    return {
        "markers": markers,
        "archive_buttons": len(parser.archive_urls),
        "archive_urls": parser.archive_urls,
        "manual_buttons": len(parser.manual),
        "manual_mappings": parser.manual,
        "operations_rows": len(parser.operations),
        "operations_mappings": parser.operations,
        "tw_link": "/stock-ai-dashboard/dashboard/tw/index.html" in parser.links,
        "us_link": "/stock-ai-dashboard/dashboard/us/index.html" in parser.links,
        "forbidden_hits": [marker for marker in FORBIDDEN if marker in lowered],
    }


def inventory_ok(item: dict[str, Any]) -> bool:
    return (
        all(item["markers"].values())
        and item["archive_buttons"] == 14
        and len(set(item["archive_urls"])) == 14
        and set(item["archive_urls"]) == EXPECTED_ARCHIVE_URLS
        and item["manual_buttons"] == 7
        and set(item["manual_mappings"]) == EXPECTED_WINDOWS
        and item["operations_rows"] == 7
        and set(item["operations_mappings"]) == EXPECTED_WINDOWS
        and item["tw_link"] and item["us_link"]
        and not item["forbidden_hits"]
    )


def fetch_public() -> tuple[int | None, str, str | None]:
    try:
        with urllib.request.urlopen(PUBLIC_URL, timeout=10) as response:
            return response.status, response.read().decode("utf-8", errors="replace"), None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, "", str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-public", action="store_true")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="ai-dev-181d-landing-") as raw:
        temp = Path(raw)
        stage = temp / "stage/production"
        public = temp / "public"
        production.build_pages(stage)
        source = stage / "index.html"
        source_bytes = source.read_bytes()
        source_page = source_bytes.decode("utf-8")
        source_inventory = inventory(source_page)
        checks["production_source_contract"] = inventory_ok(source_inventory)

        published = production.publish_pages(public, stage)
        root = public / "index.html"
        root_hash = sha256_bytes(root.read_bytes())
        staged_hash = sha256_bytes(source_bytes)
        checks["production_publish_contract"] = inventory_ok(inventory(root.read_text(encoding="utf-8")))
        checks["production_source_stage_public_hash"] = staged_hash == root_hash == published.get("public_landing_hash")

        sequence_hashes: dict[str, str] = {"production_publish": root_hash}
        production.publish_archive_latest_route("TW", "post_close_1500", public, temp / "tw-latest")
        sequence_hashes["archive_route_rebuild"] = sha256_bytes(root.read_bytes())
        production.publish_pages(public, stage)
        sequence_hashes["operations_rebuild"] = sha256_bytes(root.read_bytes())
        production.publish_archive_latest_route("TW", "post_close_1500", public, temp / "tw-static")
        sequence_hashes["tw_1500_static_publish"] = sha256_bytes(root.read_bytes())
        production.publish_archive_latest_route("US", "us_pre_market_2000", public, temp / "us-static")
        sequence_hashes["us_window_static_publish"] = sha256_bytes(root.read_bytes())

        legacy_result = scheduler_legacy.publish_dashboard(public, "post_close_1500", "deterministic-route-test", "2026-07-15T15:00:00+08:00", "completed", "")
        sequence_hashes["scheduler_legacy_publish"] = sha256_bytes(root.read_bytes())
        preview_result = legacy_preview.write_publish_files(
            public,
            ROOT / "templates/four_window_dashboard_route_preview.example.html",
            "http://example.invalid/stock-ai-dashboard",
            "/dashboard/decision-intelligence/four-window-preview",
            "2026-07-15T20:00:00+08:00",
            False,
        )
        sequence_hashes["legacy_preview_publish"] = sha256_bytes(root.read_bytes())
        checks["root_stable_through_publish_sequence"] = len(set(sequence_hashes.values())) == 1
        checks["legacy_scheduler_route_isolated"] = legacy_result["index_path"] == str(public / "debug/legacy/index.html")
        checks["legacy_preview_route_isolated"] = preview_result.get("production_root_untouched") is True and preview_result.get("index_link_added") is False

        legacy_source = scheduler_legacy.render_dashboard("post_close_1500", "deterministic-route-test", "2026-07-15T15:00:00+08:00", "completed", "")
        legacy_path = public / "debug/legacy/index.html"
        checks["root_differs_from_legacy"] = sha256_bytes(root.read_bytes()) != sha256_bytes(legacy_path.read_bytes())
        multi_source = (ROOT / "app/dashboard/multi_market_dashboard.py").read_text(encoding="utf-8")
        scheduler_source = (ROOT / "scripts/orchestrator/approved_pre_open_delivery.py").read_text(encoding="utf-8")
        preview_source = (ROOT / "scripts/orchestrator/publish_four_window_dashboard_preview_v1.py").read_text(encoding="utf-8")
        checks["root_owner_unique"] = production.PRODUCTION_LANDING_OWNER == "app.dashboard.multi_market_dashboard.publish_pages"
        checks["scheduler_publisher_cannot_target_root"] = 'target_dir = publish_dir / LEGACY_DEBUG_ROUTE' in scheduler_source and 'index_path = publish_dir / "index.html"' not in scheduler_source
        checks["preview_publisher_cannot_target_root"] = "def update_index(" not in preview_source and '"production_root_untouched": True' in preview_source
        checks["atomic_root_publish"] = "os.replace(staged, target)" in multi_source and "production_landing_contract_errors" in multi_source
        checks["mobile_safe_area"] = "safe-area-inset-left" in source_page and "safe-area-inset-right" in source_page
        checks["mobile_operations_overflow"] = "operations-table-scroll" in source_page and "overflow-x:auto" in source_page

        evidence.update({
            "production_source_hash": staged_hash,
            "staged_landing_hash": staged_hash,
            "public_landing_hash": root_hash,
            "legacy_source_hash": sha256_bytes(legacy_source.encode("utf-8")),
            "public_legacy_hash": sha256_bytes(legacy_path.read_bytes()),
            "root_stable_after_legacy_publish": checks["root_stable_through_publish_sequence"],
            "sequence_hashes": sequence_hashes,
            "source_inventory": source_inventory,
            "temporary_root": str(public),
        })
    checks["temporary_staging_removed"] = not Path(raw).exists()

    if args.require_public:
        status, page, error = fetch_public()
        public_inventory = inventory(page, exact_markers=False)
        checks["public_http_200"] = status == 200
        checks["public_landing_contract"] = inventory_ok(public_inventory)
        evidence["actual_public"] = {"url": PUBLIC_URL, "http": status, "hash": sha256_bytes(page.encode("utf-8")) if page else None, "inventory": public_inventory, "error": error}

    errors = [name for name, passed in checks.items() if not passed]
    result = {
        "schema_version": "production_landing_integrity_validation_v1",
        "task_id": "AI-DEV-181D",
        "ok": not errors,
        "errors": errors,
        "checks": checks,
        "evidence": evidence,
        "safety": {"email_attempted": False, "line_attempted": False, "production_pipeline_executed": False, "trading": False, "scheduler_changed": False, "python3_main_executed": False, "secrets_accessed": False},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
