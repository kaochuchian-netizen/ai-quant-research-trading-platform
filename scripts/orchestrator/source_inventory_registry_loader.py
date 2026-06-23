#!/usr/bin/env python3
"""Reusable read-only loader for the source inventory registry example.

This module centralizes loading and summarizing
`orchestrator/templates/source_inventory_registry.example.json` so other
orchestrator scripts can reuse the same registry view without duplicating JSON
parsing or safety checks.

The loader is read-only and does not call external services, read secrets,
modify databases, send notifications, or run production workflows.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = ROOT / "orchestrator" / "templates" / "source_inventory_registry.example.json"


@dataclass(frozen=True)
class SourceInventorySummary:
    schema_version: int | None
    registry_name: str | None
    inventory_scope: str | None
    production_status: str | None
    connected_source_ids: tuple[str, ...]
    notification_output_ids: tuple[str, ...]
    candidate_source_ids: tuple[str, ...]
    connected_source_count: int
    notification_output_count: int
    candidate_source_count: int
    total_source_count: int
    path: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "registry_name": self.registry_name,
            "inventory_scope": self.inventory_scope,
            "production_status": self.production_status,
            "connected_source_ids": list(self.connected_source_ids),
            "notification_output_ids": list(self.notification_output_ids),
            "candidate_source_ids": list(self.candidate_source_ids),
            "connected_source_count": self.connected_source_count,
            "notification_output_count": self.notification_output_count,
            "candidate_source_count": self.candidate_source_count,
            "total_source_count": self.total_source_count,
            "path": self.path,
        }


def load_source_inventory_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    registry_path = Path(path).expanduser().resolve()
    with registry_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("registry JSON root must be an object")
    return payload


def iter_source_entries(registry: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for group_name in ("connected_sources", "notification_outputs", "candidate_sources"):
        items = registry.get(group_name, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                yield item


def summarize_source_inventory_registry(
    registry: dict[str, Any],
    *,
    path: Path | str = DEFAULT_REGISTRY_PATH,
) -> SourceInventorySummary:
    connected_sources = registry.get("connected_sources", [])
    notification_outputs = registry.get("notification_outputs", [])
    candidate_sources = registry.get("candidate_sources", [])

    def collect_source_ids(items: Any) -> tuple[str, ...]:
        if not isinstance(items, list):
            return ()
        return tuple(
            item.get("source_id")
            for item in items
            if isinstance(item, dict) and isinstance(item.get("source_id"), str)
        )

    connected_source_ids = collect_source_ids(connected_sources)
    notification_output_ids = collect_source_ids(notification_outputs)
    candidate_source_ids = collect_source_ids(candidate_sources)

    total_source_count = sum(
        len(items)
        for items in (connected_sources, notification_outputs, candidate_sources)
        if isinstance(items, list)
    )

    return SourceInventorySummary(
        schema_version=registry.get("schema_version") if isinstance(registry.get("schema_version"), int) else None,
        registry_name=registry.get("registry_name") if isinstance(registry.get("registry_name"), str) else None,
        inventory_scope=registry.get("inventory_scope") if isinstance(registry.get("inventory_scope"), str) else None,
        production_status=registry.get("production_status") if isinstance(registry.get("production_status"), str) else None,
        connected_source_ids=connected_source_ids,
        notification_output_ids=notification_output_ids,
        candidate_source_ids=candidate_source_ids,
        connected_source_count=len(connected_source_ids),
        notification_output_count=len(notification_output_ids),
        candidate_source_count=len(candidate_source_ids),
        total_source_count=total_source_count,
        path=str(Path(path).expanduser().resolve()),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Load and summarize the source inventory registry example.")
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    registry = load_source_inventory_registry(args.registry_path)
    summary = summarize_source_inventory_registry(registry, path=args.registry_path)
    output = {
        "ok": True,
        "read_only": True,
        "registry_path": summary.path,
        "summary": summary.as_dict(),
        "source_ids": {
            "connected": list(summary.connected_source_ids),
            "notification_outputs": list(summary.notification_output_ids),
            "candidate": list(summary.candidate_source_ids),
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
