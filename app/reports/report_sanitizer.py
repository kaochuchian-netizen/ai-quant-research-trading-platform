"""Deterministic suppression of operational logs from user-facing report content."""
from __future__ import annotations
import json, re
from dataclasses import asdict, dataclass
from typing import Any
RAW_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("shioaji_or_solace_session", re.compile(r"Shioaji|Solace|Session up|APISUB/|P2P/|host '210\.59|Response Code:|Event Code:|Event:", re.I)),
    ("sqlite_operational", re.compile(r"SQLite 已寫入", re.I)),
    ("stock_analysis_operational", re.compile(r"開始分析股票|selected stock ids|full LINE report disabled|historical CSV update skipped", re.I)),
    ("pipeline_summary_dump", re.compile(r"pipeline_report_summary:|^\s*\{\s*\"pipeline_type\"|^\s*\{\s*'pipeline_type'", re.I)),
    ("traceback", re.compile(r"Traceback \(most recent call last\):|File \".*\", line \d+|Exception:|Error:", re.I)),
]
@dataclass(frozen=True)
class SanitizationResult:
    sanitized_text: str
    suppressed_log_count: int
    suppressed_log_categories: dict[str, int]
    raw_traceback_suppressed: bool
    operational_log_suppressed: bool
    raw_log_suppressed: bool
    removed_examples: list[str]
    def to_dict(self) -> dict[str, Any]: return asdict(self)
def _looks_like_json_dump(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith(("{", "[")):
        return False
    try:
        json.loads(stripped)
        return True
    except Exception:
        return False
def sanitize_report_text(text: str) -> SanitizationResult:
    kept: list[str] = []
    categories: dict[str, int] = {}
    examples: list[str] = []
    for line in text.splitlines():
        category = None
        for name, pattern in RAW_PATTERNS:
            if pattern.search(line):
                category = name; break
        if category is None and _looks_like_json_dump(line):
            category = "raw_json_dump"
        if category:
            categories[category] = categories.get(category, 0) + 1
            if len(examples) < 8: examples.append(line[:180])
            continue
        kept.append(line)
    sanitized = "\n".join(kept).strip()
    return SanitizationResult(sanitized, sum(categories.values()), categories, categories.get("traceback", 0) > 0, any(k in categories for k in ("sqlite_operational", "stock_analysis_operational", "pipeline_summary_dump", "raw_json_dump")), bool(categories), examples)
def user_facing_is_clean(text: str) -> bool:
    return sanitize_report_text(text).suppressed_log_count == 0
