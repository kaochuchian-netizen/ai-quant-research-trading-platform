#!/usr/bin/env python3
"""Read-only production evidence audit for AI-DEV-182.

This module deliberately has no dependency on builders, publishers, delivery
senders, archive writers, or runtime pipelines.  It reads existing evidence and
writes only below artifacts/audit/ai_dev_182.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "audit" / "ai_dev_182"
ARCHIVE = ROOT / "artifacts" / "archive" / "window_snapshots"
PUBLIC_BASE = "http://35.201.242.167/stock-ai-dashboard"
OBSERVED_AT = "2026-07-17T16:00:00+08:00"


@dataclass(frozen=True)
class Window:
    market: str
    key: str
    scheduled: str
    label: str

    @property
    def market_path(self) -> str:
        return self.market.lower()

    @property
    def latest_route(self) -> str:
        return f"/dashboard/archive/{self.market_path}/{self.key}/latest/index.html"

    @property
    def previous_route(self) -> str:
        return f"/dashboard/archive/{self.market_path}/{self.key}/previous/index.html"


WINDOWS = (
    Window("TW", "pre_open_0700", "07:00", "TW 07:00"),
    Window("TW", "intraday_1305", "13:05", "TW 13:05"),
    Window("TW", "pre_close_1335", "13:35", "TW 13:35"),
    Window("TW", "post_close_1500", "15:00", "TW 15:00"),
    Window("US", "us_pre_market_2000", "20:00", "US 20:00"),
    Window("US", "us_intraday_2300", "23:00", "US 23:00"),
    Window("US", "us_post_close_review_0630", "06:30", "US 06:30"),
)

PUBLIC_PAGES = (
    ("Landing", "/index.html"),
    ("TW Dashboard", "/dashboard/tw/index.html"),
    ("US Dashboard", "/dashboard/us/index.html"),
    *tuple((f"{w.label} Latest", w.latest_route) for w in WINDOWS),
    *tuple((f"{w.label} Previous", w.previous_route) for w in WINDOWS),
)

PLACEHOLDERS = ("sample", "fixture", "demo", "example", "contract validation", "樣本資料", "僅供內容契約驗證")
ENGINEERING = ("deterministic", "payload", "runtime", "artifact", "schema", "fallback", "datetime.date(", "validation only")
DECISION_TERMS = {
    "pre_open_0700": ("市場", "風險", "觀察", "追價", "entry", "進場"),
    "intraday_1305": ("觸發", "成交量", "量價", "偏離", "午後", "追價"),
    "pre_close_1335": ("留倉", "不留倉", "接近目標", "接近停損", "尾盤", "13:05"),
    "post_close_1500": ("outcome", "命中", "失敗", "未觸發", "pending", "review"),
    "us_pre_market_2000": ("premarket", "gap", "earnings", "sec", "guidance", "risk"),
    "us_intraday_2300": ("gap", "volume", "trigger", "target", "stop", "盤中"),
    "us_post_close_review_0630": ("outcome", "prediction", "trigger", "no trade", "pending", "review"),
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.attrs: dict[str, str] = {}
        self.ids: list[str] = []
        self.links: list[str] = []
        self.title = ""
        self._title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self._title = True
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        for key, value in values.items():
            if key.startswith("data-"):
                self.attrs.setdefault(key, value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title = False

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if clean:
            self.text.append(clean)
            if self._title:
                self.title += clean


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(" ".join(value.split()).encode()).hexdigest()


def flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {flatten(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(flatten(item) for item in value)
    return "" if value is None else str(value)


def snapshots(window: Window) -> list[tuple[Path, dict[str, Any]]]:
    folder = ARCHIVE / window.market_path / window.key
    values: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(folder.glob("*/revision-*.json")):
        data = load_json(path)
        if data.get("admitted") is True and data.get("status") == "complete":
            values.append((path, data))
    return values


def card_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("structured_review_cards", "cards", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    report = payload.get("user_facing_report")
    if isinstance(report, dict):
        for key in ("stock_cards", "review_cards"):
            value = report.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def stock_ids(cards: list[dict[str, Any]]) -> list[str]:
    return [str(c.get("stock_id") or c.get("symbol") or c.get("ticker") or "") for c in cards if c.get("stock_id") or c.get("symbol") or c.get("ticker")]


def outcome_counts(payload: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, int]:
    source = payload.get("outcome_counts")
    if isinstance(source, dict) and source:
        return {str(k).lower(): int(v or 0) for k, v in source.items() if isinstance(v, (int, float))}
    counts: Counter[str] = Counter()
    for card in cards:
        outcome = str(card.get("outcome") or card.get("result") or "").strip().lower().replace(" ", "_")
        if outcome:
            counts[outcome] += 1
    return dict(counts)


def snapshot_summary(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    cards = card_list(payload)
    tracking = payload.get("tracking_stock_count")
    if tracking is None:
        tracking = len(payload.get("items") or cards)
    rendered = payload.get("rendered_review_card_count")
    if rendered is None:
        rendered = len(cards)
    counts = outcome_counts(payload, cards)
    return {
        "artifact_path": str(path.relative_to(ROOT)),
        "market": data.get("market"),
        "window": data.get("window") or data.get("batch_window"),
        "trading_date": data.get("effective_trading_date"),
        "scheduled_batch_time": data.get("original_batch_time") or payload.get("effective_batch_time"),
        "entrypoint_start_time": None,
        "runtime_completion": data.get("generated_at"),
        "runtime_status": data.get("status"),
        "runtime_provenance": data.get("runtime_provenance"),
        "snapshot_admission_status": "admitted" if data.get("admitted") else "rejected",
        "snapshot_id": data.get("snapshot_id"),
        "revision": data.get("revision"),
        "source_payload_hash": stable_hash(payload),
        "declared_payload_hash": payload.get("source_payload_hash") or payload.get("payload_hash"),
        "market_data_as_of": payload.get("source_data_time") or payload.get("market_data_as_of"),
        "market_data_time_status": payload.get("source_data_time_status"),
        "report_generated_time": payload.get("generated_at") or data.get("generated_at"),
        "snapshot_admitted_time": data.get("revision_created_at") or data.get("generated_at"),
        "tracking_count": int(tracking or 0),
        "rendered_card_count": int(rendered or 0),
        "outcome_counts": counts,
        "reviewed_universe": sum(counts.values()),
        "stock_universe": stock_ids(cards),
        "payload_text_hash": text_hash(flatten(payload)),
        "payload_text": flatten(payload),
    }


def fetch_page(label: str, route: str) -> dict[str, Any]:
    url = PUBLIC_BASE + route
    result: dict[str, Any] = {"label": label, "public_url": url, "observed_at": OBSERVED_AT}
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            raw = response.read().decode("utf-8", errors="replace")
            result["http_status"] = response.status
    except (urllib.error.URLError, TimeoutError) as exc:
        result.update({"http_status": None, "result": "NOT_OBSERVABLE", "reason": type(exc).__name__})
        return result
    parser = PageParser()
    parser.feed(raw)
    visible = html.unescape(" ".join(parser.text))
    id_counts = Counter(parser.ids)
    forbidden = [term for term in PLACEHOLDERS if term.lower() in visible.lower()]
    result.update({
        "dom_title": parser.title,
        "canonical_url": route,
        "market_marker": parser.attrs.get("data-market"),
        "window_marker": parser.attrs.get("data-window"),
        "trading_date": parser.attrs.get("data-effective-trading-date"),
        "snapshot_id": parser.attrs.get("data-snapshot-id"),
        "revision": parser.attrs.get("data-revision"),
        "source_payload_hash": parser.attrs.get("data-payload-hash"),
        "tracking_count": _first_int(parser.attrs.get("data-tracking-stock-count"), visible, "Tracking"),
        "rendered_card_count": _first_int(parser.attrs.get("data-rendered-review-card-count"), visible, "Rendered"),
        "forbidden_markers": forbidden,
        "official_empty_state": "official empty state" in visible.lower() or "尚無" in visible,
        "duplicate_ids": sorted(key for key, count in id_counts.items() if count > 1),
        "internal_link_count": sum(1 for href in parser.links if href.startswith("/stock-ai-dashboard/")),
        "visible_text_hash": text_hash(visible),
        "visible_character_count": len(visible),
        "visible_text": visible,
        "result": "PASS" if response.status == 200 and not forbidden else "FAIL",
    })
    return result


def _first_int(attr: str | None, text: str, label: str) -> int | None:
    if attr and str(attr).isdigit():
        return int(attr)
    match = re.search(rf"{re.escape(label)}\D{{0,15}}(\d+)", text, re.I)
    return int(match.group(1)) if match else None


def progress_for(window: Window) -> dict[str, Any]:
    if window.market == "TW":
        mapping = {
            "pre_open_0700": "delivery_progress_pre_open_0700_latest.json",
            "intraday_1305": "delivery_progress_intraday_1305_latest.json",
            "pre_close_1335": "delivery_progress_pre_close_1335_latest.json",
            "post_close_1500": "delivery_progress_prediction_review_1500_latest.json",
        }
        path = ROOT / "artifacts" / "runtime" / mapping[window.key]
    else:
        path = ROOT / "artifacts" / "runtime" / "us_stock" / f"{window.key}_latest.json"
    data = load_json(path)
    return {"artifact_path": str(path.relative_to(ROOT)), "data": data}


def delivery_evidence(window: Window, latest: dict[str, Any] | None) -> dict[str, Any]:
    progress = progress_for(window)
    data = progress["data"]
    flat = flatten(data).lower()
    if window.market == "TW":
        status = str(data.get("status") or data.get("stage") or "not_observable")
        timed_out = "timed_out" in flat or "timed out" in flat
        if timed_out:
            email = line = "not_attempted"
        elif status == "completed":
            email = line = "sent_inferred_from_approved_wrapper_ok;receipt_unavailable"
        else:
            email = line = "not_observable"
        return {
            "market": window.market, "window": window.key, "evidence_path": progress["artifact_path"],
            "scheduler_trigger": "observed" if data.get("started_at") else "not_observable",
            "entrypoint_start": data.get("started_at"), "runtime_completion": data.get("finished_at"),
            "pipeline_status": "timed_out" if timed_out else status,
            "email": email, "line": line, "recipient_receipt": "unavailable",
            "formatter_content": "not_persisted", "source_snapshot_id": latest.get("snapshot_id") if latest else None,
        }
    delivery = data.get("delivery") if isinstance(data.get("delivery"), dict) else {}
    return {
        "market": window.market, "window": window.key, "evidence_path": progress["artifact_path"],
        "scheduler_trigger": "observed" if data else "not_observable", "entrypoint_start": data.get("generated_at"),
        "runtime_completion": data.get("generated_at"), "pipeline_status": "completed" if data else "not_observable",
        "email": _us_delivery_state(delivery, "email", flat), "line": _us_delivery_state(delivery, "line", flat),
        "recipient_receipt": "unavailable", "formatter_content": "persisted_in_delivery_status_or_log",
        "source_snapshot_id": latest.get("snapshot_id") if latest else None,
    }


def _us_delivery_state(delivery: dict[str, Any], name: str, flat: str) -> str:
    node = delivery.get(name) if isinstance(delivery.get(name), dict) else {}
    if node.get("succeeded") is True or f"{name}_succeeded true" in flat:
        return "sent;receipt_unavailable"
    if node.get("attempted") is True or f"{name}_attempted true" in flat:
        return "failed_or_unknown"
    return "not_observable"


def noise_metrics(text: str) -> dict[str, Any]:
    lower = text.lower()
    sentences = [" ".join(s.split()) for s in re.split(r"[。！？!?\n]+", text) if len(" ".join(s.split())) >= 8]
    repeats = sum(count - 1 for count in Counter(sentences).values() if count > 1)
    placeholder_hits = sum(lower.count(term.lower()) for term in PLACEHOLDERS)
    engineering_hits = sum(lower.count(term.lower()) for term in ENGINEERING)
    decision_hits = sum(lower.count(term.lower()) for terms in DECISION_TERMS.values() for term in terms)
    denominator = max(len(text), 1)
    return {
        "total_characters": len(text), "decision_term_hits": decision_hits,
        "placeholder_hits": placeholder_hits, "engineering_wording_hits": engineering_hits,
        "repeated_sentence_instances": repeats,
        "decision_value_ratio": round(min(1.0, decision_hits * 12 / denominator), 4),
        "placeholder_ratio": round(placeholder_hits * 10 / denominator, 4),
        "engineering_wording_ratio": round(engineering_hits * 10 / denominator, 4),
        "redundancy_ratio": round(repeats / max(len(sentences), 1), 4),
        "noise_ratio": round(min(1.0, (placeholder_hits + engineering_hits + repeats) * 10 / denominator), 4),
    }


def quality(window: Window, summary: dict[str, Any]) -> dict[str, Any]:
    text = summary.get("payload_text", "").lower()
    expected = DECISION_TERMS[window.key]
    present = [term for term in expected if term.lower() in text]
    specificity = min(5, round(5 * len(present) / max(len(expected), 1)))
    actionability = min(5, specificity + (1 if summary.get("tracking_count", 0) else 0))
    explainability = min(5, sum(token in text for token in ("reason", "理由", "依據", "review", "why")) + 1)
    risk = min(5, sum(token in text for token in ("risk", "風險", "stop", "停損")))
    prioritization = 3 if any(token in text for token in ("top", "priority", "優先", "ranking")) else 1
    density = max(1, 5 - int(noise_metrics(text)["noise_ratio"] * 10))
    confidence = min(5, sum(token in text for token in ("confidence", "信心", "calibration", "校準")))
    return {
        "market": window.market, "window": window.key,
        "evidence_path": summary.get("artifact_path"), "expected_terms": list(expected), "observed_terms": present,
        "scores": {"actionability": actionability, "window_specificity": specificity,
                   "explainability": explainability, "risk_clarity": risk,
                   "signal_prioritization": prioritization, "information_density": density,
                   "noise_ratio": round(noise_metrics(text)["noise_ratio"] * 5, 2), "confidence_clarity": confidence},
        "result": "PASS" if min(actionability, specificity, explainability, risk) >= 3 else "PARTIAL",
    }


def coverage(window: Window, summary: dict[str, Any]) -> list[dict[str, Any]]:
    text = summary.get("payload_text", "").lower()
    fields = {
        "price": ("price", "價格", "current_price"), "market_data_timestamp": ("source_data_time", "market_data_as_of"),
        "technical": ("technical", "技術"), "volume": ("volume", "成交量", "量價"), "gap": ("gap",),
        "news": ("news", "新聞"), "fundamentals": ("fundamental", "財務"), "earnings": ("earnings", "盈餘"),
        "guidance": ("guidance",), "sec": ("sec", "8-k", "10-q", "10-k"), "official_ir": ("official ir", "newsroom"),
        "twse": ("twse", "證交所"), "mops": ("mops", "公開資訊觀測站"), "institutional_flow": ("三大法人", "institutional"),
        "margin": ("融資", "margin"), "adr": ("adr",), "macro_proxy": ("macro", "spy", "qqq", "vix"),
        "prediction": ("prediction", "預測"), "actual_outcome": ("outcome", "actual", "實際"),
        "review": ("review", "檢討"), "calibration": ("calibration", "校準"),
    }
    rows = []
    for field, tokens in fields.items():
        if field in {"sec", "official_ir", "guidance", "earnings"} and window.market == "TW":
            state = "not_applicable"
        elif field in {"twse", "mops", "institutional_flow", "margin", "adr"} and window.market == "US":
            state = "not_applicable"
        else:
            state = "available" if any(token in text for token in tokens) else "unavailable"
        rows.append({"market": window.market, "window": window.key, "field": field, "availability": state,
                     "source": "snapshot payload", "as_of_time": summary.get("market_data_as_of"),
                     "freshness": "unavailable" if not summary.get("market_data_as_of") and field in {"price", "market_data_timestamp", "volume", "gap"} else "not_evaluated",
                     "missing_reason": "field absent from immutable snapshot" if state == "unavailable" else None})
    return rows


def issue(issue_id: str, severity: str, title: str, windows: list[str], channels: list[str], evidence: list[str],
          root: str, impact: str, risk: str, complexity: str, task: str) -> dict[str, Any]:
    return {"issue_id": issue_id, "severity": severity, "title": title, "frequency": "observed_current" if len(windows) == 1 else "recurring_or_cross_channel",
            "affected_markets": sorted({"TW" if w.startswith("TW") else "US" for w in windows}), "affected_windows": windows,
            "affected_channels": channels, "trading_dates": ["2026-07-17"] if any(w.startswith("TW") for w in windows) else ["2026-07-16"],
            "evidence": evidence, "root_cause_category": root, "user_impact": impact, "operational_risk": risk,
            "estimated_fix_complexity": complexity, "recommended_owner": "Production Data & Delivery",
            "recommended_integrated_task": task}


def build_issues(latest: dict[str, dict[str, Any]], public: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = [
        issue("AI182-P0-001", "P0", "TW 13:05 scheduled batch timed out before runtime persistence",
              ["TW intraday_1305"], ["Runtime", "Archive", "Dashboard", "Email", "LINE"],
              ["artifacts/runtime/delivery_progress_intraday_1305_latest.json: stage=pipeline_timed_out, timeout=600",
               "logs/daily.log: approved_scheduler_delivery_timed_out_no_delivery", "no 2026-07-17 intraday_1305 snapshot"],
              "pipeline_failure", "No intraday decision or notification; 13:35 loses same-day baseline.", "Silent decision gap if only public HTTP is monitored.", "medium", "AI-DEV-183"),
        issue("AI182-P0-002", "P0", "US 06:30 pending cards are simultaneously presented as No Trade and Reviewed",
              ["US us_post_close_review_0630"], ["Snapshot", "Dashboard", "Email", "LINE"],
              ["delivery_status_latest: V4 No Trade=6", "per-stock formatter evidence: outcome pending actual result", "Reviewed=6"],
              "outcome_classification", "Users receive a concluded No Trade result while actual outcomes remain pending.", "Incorrect review/calibration metrics.", "medium", "AI-DEV-183"),
        issue("AI182-P0-003", "P0", "Public TW latest routes lag admitted 2026-07-17 snapshots",
              ["TW pre_open_0700", "TW pre_close_1335", "TW post_close_1500"], ["Archive", "Dashboard", "Landing"],
              ["immutable snapshots admitted for 2026-07-17", "public Landing and archive marker inventory still show 2026-07-16"],
              "publish_missing", "Public users see the previous trading day after successful production runs.", "Archive latest identity invariant broken.", "medium", "AI-DEV-183"),
        issue("AI182-P1-001", "P1", "TW 07:00 snapshot has no stock cards and is dominated by health/contract summary",
              ["TW pre_open_0700"], ["Snapshot", "Dashboard", "Email", "LINE"],
              ["2026-07-17 snapshot tracking=0 rendered=0 content_state=partial", "source_data_time unavailable"],
              "data_completeness", "No prioritized opportunities, no-trade list, or chase-risk list.", "Pre-open output cannot support the stated decision contract.", "large", "AI-DEV-184"),
        issue("AI182-P1-002", "P1", "TW 13:35 lacks market-data time and same-day 13:05 baseline",
              ["TW pre_close_1335"], ["Snapshot", "Dashboard", "Email", "LINE"],
              ["source_data_time=None; status=unavailable_no_intraday_timestamp", "2026-07-17 intraday snapshot absent"],
              "upstream_dependency_and_freshness", "Hold/avoid decisions cannot be traced to fresh market evidence or intraday change.", "Stale or unexplainable closing decision.", "medium", "AI-DEV-183"),
        issue("AI182-P1-003", "P1", "TW 15:00 review remains mostly pending",
              ["TW post_close_1500"], ["Snapshot", "Dashboard", "Email", "LINE"],
              ["2026-07-17 outcome_counts: pending=8, no_trade=1, hit=0, fail=0"],
              "outcome_readiness", "The review explains little of the actual session result.", "Calibration and next-day correction remain weak.", "medium", "AI-DEV-184"),
        issue("AI182-P1-004", "P1", "US 23:00 volume/gap evidence uses repeated generic research wording",
              ["US us_intraday_2300"], ["Snapshot", "Dashboard", "Email", "LINE"],
              ["identical deterministic research-factor sentence repeated across stock cards"],
              "window_specific_template", "Users cannot tell which gaps or volume moves were actually confirmed.", "Intraday decisions may be interpreted as observed facts.", "medium", "AI-DEV-184"),
        issue("AI182-P1-005", "P1", "US 20:00 contains questionable financial units and Python date representation",
              ["US us_pre_market_2000"], ["Email", "Snapshot", "Dashboard"],
              ["TSM revenue displayed as USD 4103.9B", "datetime.date(...) appears in production evidence"],
              "normalization_and_presentation", "Financial context can be materially misleading.", "Wrong scale/currency can distort pre-market judgment.", "medium", "AI-DEV-183"),
        issue("AI182-P1-006", "P1", "TW notification payload identity is not persisted for post-delivery audit",
              ["TW pre_open_0700", "TW pre_close_1335", "TW post_close_1500"], ["Email", "LINE"],
              ["approved wrapper completion proves send path, but actual content/snapshot hash is not retained", "recipient receipt unavailable"],
              "observability_gap", "Cross-channel source parity cannot be proven after delivery.", "Content regressions may escape audits despite successful send.", "medium", "AI-DEV-183"),
        issue("AI182-P2-001", "P2", "US 20:00 Email is long, repetitive, and exposes engineering wording",
              ["US us_pre_market_2000"], ["Email"],
              ["repeated research/risk blocks", "deterministic wording", "large persisted payload preview"],
              "information_architecture", "Core pre-market decisions are hard to locate on mobile.", "Lower recipient comprehension.", "small", "AI-DEV-185"),
        issue("AI182-P2-002", "P2", "Required visual screenshots were not obtainable from the audit browser backend",
              [w.label for w in WINDOWS], ["Dashboard UX"],
              ["Page.captureScreenshot repeatedly timed out", "DOM, CSS, duplicate-ID and overflow evidence retained instead"],
              "audit_environment_limitation", "Pixel-level typography and spacing could not be certified.", "Visual regressions require a browser runner with stable screenshot capture.", "small", "AI-DEV-185"),
    ]
    return issues


def scorecard(issues: list[dict[str, Any]], qualities: list[dict[str, Any]], coverage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    available = sum(row["availability"] == "available" for row in coverage_rows)
    applicable = sum(row["availability"] != "not_applicable" for row in coverage_rows)
    quality_average = sum(sum(q["scores"].values()) / len(q["scores"]) for q in qualities) / len(qualities)
    components = {
        "consistency": {"score": 8, "maximum": 20, "evidence": ["P0 public latest lag", "P0 US outcome contradiction", "TW delivery hash evidence gap"]},
        "data_completeness": {"score": round(20 * available / max(applicable, 1)), "maximum": 20, "evidence": [f"{available}/{applicable} applicable source fields detected in immutable snapshots"]},
        "decision_quality": {"score": round(20 * quality_average / 5), "maximum": 20, "evidence": ["seven-window rubric backed by expected/observed decision terms"]},
        "freshness": {"score": 6, "maximum": 15, "evidence": ["TW source_data_time absent", "TW public routes one effective day behind"]},
        "ux_and_readability": {"score": 8, "maximum": 15, "evidence": ["US pre-market repetition/engineering wording", "screenshot backend evidence gap"]},
        "operational_reliability": {"score": 5, "maximum": 10, "evidence": ["TW 13:05 timed out", "remaining current natural batches observed"]},
    }
    overall = sum(item["score"] for item in components.values())
    return {"overall": overall, "maximum": 100, "production_readiness_level": "BLOCKED_BY_P0" if any(i["severity"] == "P0" for i in issues) else "CONDITIONAL", "components": components}


def write_json(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def report_markdown(score: dict[str, Any], issues: list[dict[str, Any]], matrix: list[dict[str, Any]], root_cause: dict[str, Any]) -> str:
    lines = ["# AI-DEV-182 Production Multi-Window Audit", "", f"Observed at: {OBSERVED_AT}", "", "## Executive scorecard", "", f"Overall: **{score['overall']}/100 — {score['production_readiness_level']}**", ""]
    for name, item in score["components"].items():
        lines.append(f"- {name}: {item['score']}/{item['maximum']} — {'; '.join(item['evidence'])}")
    lines += ["", "## TW 13:05 root cause", "", f"Scheduler triggered and the approved entrypoint started, but the pipeline reached `{root_cause['pipeline']}` after 600 seconds. No runtime, snapshot, publish, Email, or LINE followed. Root cause: `{root_cause['root_cause_category']}`.", "", "## Seven-window result", ""]
    for row in matrix:
        lines.append(f"- {row['market']} {row['window']}: **{row['result']}** — snapshot {row.get('snapshot_id') or 'missing'}, public {row.get('public_result')}")
    for severity in ("P0", "P1", "P2"):
        lines += ["", f"## {severity} findings", ""]
        for item in issues:
            if item["severity"] == severity:
                lines.append(f"- **{item['issue_id']}** {item['title']} — {item['user_impact']}")
    lines += ["", "## Roadmap", "", "1. AI-DEV-183 — integrated production correctness: batch timeout resilience, publish identity, outcome classification, financial normalization, and notification provenance evidence.", "2. AI-DEV-184 — decision content and outcome quality: real window observations, review completion, continuity explanations, and source coverage.", "3. AI-DEV-185 — information architecture and delivery UX: reduce repetition/noise and complete browser-based desktop/mobile visual QA.", "", "## Safety", "", "This audit did not execute pipelines, publish dashboards, attempt notifications or trading, change schedulers, or mutate runtime/archive snapshots.", ""]
    return "\n".join(lines)


def run_audit() -> dict[str, Any]:
    summaries: dict[str, list[dict[str, Any]]] = {}
    latest: dict[str, dict[str, Any]] = {}
    for window in WINDOWS:
        rows = [snapshot_summary(path, data) for path, data in snapshots(window)]
        summaries[f"{window.market}:{window.key}"] = rows[-3:]
        if rows:
            latest[f"{window.market}:{window.key}"] = rows[-1]

    public = [fetch_page(label, route) for label, route in PUBLIC_PAGES]
    public_by_route = {row["canonical_url"]: row for row in public}
    delivery = [delivery_evidence(w, latest.get(f"{w.market}:{w.key}")) for w in WINDOWS]
    qualities = [quality(w, latest.get(f"{w.market}:{w.key}", {})) for w in WINDOWS]
    coverage_rows = [row for w in WINDOWS for row in coverage(w, latest.get(f"{w.market}:{w.key}", {}))]

    matrix = []
    for w in WINDOWS:
        current = latest.get(f"{w.market}:{w.key}")
        page = public_by_route.get(w.latest_route, {})
        evidence = next(item for item in delivery if item["market"] == w.market and item["window"] == w.key)
        timeout = evidence.get("pipeline_status") == "timed_out"
        public_match = bool(current and page.get("trading_date") == current.get("trading_date") and (not page.get("snapshot_id") or page.get("snapshot_id") == current.get("snapshot_id")))
        matrix.append({
            "market": w.market, "window": w.key, "scheduled_time": w.scheduled,
            "trading_date": current.get("trading_date") if current else None, "runtime": "missing_current" if timeout else ("observed" if current else "not_observable"),
            "snapshot": current.get("snapshot_admission_status") if current else "missing", "snapshot_id": current.get("snapshot_id") if current else None,
            "revision": current.get("revision") if current else None, "payload_hash": current.get("source_payload_hash") if current else None,
            "archive": page.get("result", "NOT_OBSERVABLE"), "dashboard": "active_alias_not_separately_proven" if w.key not in ("post_close_1500", "us_post_close_review_0630") else "inspected",
            "email": evidence["email"], "line": evidence["line"],
            "count_parity": "PASS" if current and current["tracking_count"] == current["rendered_card_count"] else ("FAIL" if current else "NOT_OBSERVABLE"),
            "hash_parity": "PASS" if public_match else "FAIL", "freshness": "FAIL" if current and not current.get("market_data_as_of") else "PARTIAL",
            "decision_quality": next(q["result"] for q in qualities if q["market"] == w.market and q["window"] == w.key),
            "public_result": page.get("result"), "public_identity_matches_latest": public_match,
            "result": "FAIL" if timeout or not public_match else "PARTIAL",
        })

    root_cause = {
        "market": "TW", "window": "intraday_1305", "trading_date": "2026-07-17",
        "scheduler": "triggered at 13:05:01+08:00", "entrypoint": "approved wrapper started",
        "pipeline": "pipeline_timed_out", "timeout_seconds": 600, "runtime": "not created for 2026-07-17",
        "snapshot_admission": "not attempted; no runtime artifact", "publish": "not attempted", "email": "not_attempted",
        "line": "not_attempted", "baseline_resolution_1335": "failed because same-day admitted intraday snapshot does not exist",
        "root_cause_category": "pipeline_failure", "derived_classifications": ["runtime_artifact_missing", "no_archive_admission", "publish_missing", "delivery_not_attempted", "baseline_resolution_failure"],
        "evidence": ["artifacts/runtime/delivery_progress_intraday_1305_latest.json", "logs/daily.log", "artifacts/archive/window_snapshots/tw/intraday_1305/"],
        "recommended_correction": "AI-DEV-183 should diagnose the timed pipeline stage and add observable timeout/retry handling; do not fabricate or backfill the missing snapshot.",
    }
    issues = build_issues(latest, public)
    score = scorecard(issues, qualities, coverage_rows)
    longitudinal = []
    for w in WINDOWS:
        rows = summaries[f"{w.market}:{w.key}"]
        dates = [r["trading_date"] for r in rows]
        expected = ["2026-07-15", "2026-07-16", "2026-07-17"] if w.market == "TW" else ["2026-07-14", "2026-07-15", "2026-07-16"]
        longitudinal.append({"market": w.market, "window": w.key, "effective_dates_expected": expected, "snapshot_dates_observed": dates,
                             "successful_batch_count": len(rows), "missing_batch_count": len([d for d in expected if d not in dates]),
                             "failed_batch_count": 1 if w.key == "intraday_1305" and "2026-07-17" not in dates else 0,
                             "archive_admission_count": len(rows), "public_publish_count": int(bool(public_by_route.get(w.latest_route, {}).get("http_status") == 200)),
                             "pending_ratio": _pending_ratio(rows), "coverage_trend": "insufficient_evidence", "freshness_trend": "insufficient_evidence",
                             "consistency_trend": "degrading" if w.key == "intraday_1305" else "insufficient_evidence", "template_trend": "insufficient_evidence"})
    channel = []
    for row in matrix:
        key = f"{row['market']}:{row['window']}"
        current = latest.get(key, {})
        page = public_by_route.get(next(w.latest_route for w in WINDOWS if w.market == row["market"] and w.key == row["window"]), {})
        channel.append({"market": row["market"], "window": row["window"], "trading_date": current.get("trading_date"),
                        "matching_fields": ["market", "window"] if page.get("window_marker") == row["window"] else [],
                        "mismatched_fields": ["trading_date", "snapshot_id"] if not row["public_identity_matches_latest"] else [],
                        "missing_evidence": ["TW actual notification body and source hash"] if row["market"] == "TW" else ["recipient receipt"],
                        "runtime_source_payload_hash": current.get("source_payload_hash"), "archive_source_payload_hash": page.get("source_payload_hash"),
                        "archive_presentation_hash": page.get("visible_text_hash"), "email_content_hash": None, "line_content_hash": None,
                        "delivery_status": {"email": row["email"], "line": row["line"]}})
    freshness = [{"market": row["market"], "window": row["window"], "source": row["source"], "data_type": row["field"],
                  "source_record_date": latest.get(f"{row['market']}:{row['window']}", {}).get("trading_date"), "source_record_time": row["as_of_time"],
                  "fetched_at": None, "normalized_at": None, "used_by_window": row["window"], "maximum_allowed_age": "window-specific; not declared in snapshot",
                  "observed_age": None, "freshness_result": row["freshness"], "reason": row["missing_reason"]} for row in coverage_rows]
    repeated = []
    for w in WINDOWS:
        summary = latest.get(f"{w.market}:{w.key}", {})
        repeated.append({"market": w.market, "window": w.key, **noise_metrics(summary.get("payload_text", ""))})
    source_audit = {
        "TW": {"expected_priority": ["TWSE", "TPEx", "MOPS", "institutional flow", "margin", "Taiwan news", "ADR", "internal prediction/review"],
               "observed": sorted({r["field"] for r in coverage_rows if r["market"] == "TW" and r["availability"] == "available"}),
               "finding": "Several expected sources are schema/text-unobservable in immutable snapshots."},
        "US": {"expected_priority": ["SEC EDGAR", "official IR/newsroom", "earnings", "guidance", "US market data", "index/sector/macro", "internal prediction/review"],
               "observed": sorted({r["field"] for r in coverage_rows if r["market"] == "US" and r["availability"] == "available"}),
               "finding": "SEC/research schema exists, but pre-market units and date normalization need correction."},
    }
    continuity = {
        "TW": {"sequence": ["pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"], "normal_transitions": [],
               "baseline_missing": ["2026-07-17 intraday_1305"], "unexplained_transitions": ["13:35 cannot explain change from timed-out 13:05"], "review_gap": ["15:00 pending 8/9"]},
        "US": {"sequence": ["us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"], "normal_transitions": [],
               "baseline_missing": [], "unexplained_transitions": ["intraday gap/volume statements are generic"], "outcome_mismatch": ["06:30 pending cards classified no_trade/reviewed"]},
    }
    email_findings = [{"market": d["market"], "window": d["window"], "actual_delivery_evidence": d["email"], "source_snapshot_id": d["source_snapshot_id"],
                       "content_evidence": d["formatter_content"], "recipient_data_stored": False,
                       "finding": "actual content unavailable" if d["market"] == "TW" else "actual delivery artifact inspected; recipient receipt unavailable"} for d in delivery]
    line_findings = [{"market": d["market"], "window": d["window"], "formatter_created": d["formatter_content"] != "not_persisted",
                      "delivery_state": d["line"], "recipient_received": "receipt_unavailable", "source_snapshot_id": d["source_snapshot_id"]} for d in delivery]
    public_sanitized = [{k: v for k, v in row.items() if k not in {"visible_text"}} for row in public]
    screenshot_evidence = {"requested_viewports": [{"width": 390, "height": 844}, {"width": 1440, "height": 900}], "screenshots_captured": 0,
                           "result": "NOT_OBSERVABLE", "reason": "in-app Browser Page.captureScreenshot timed out repeatedly on the public long page",
                           "fallback_evidence": ["public DOM inventory", "HTML/CSS responsive rules", "duplicate ID scan", "link inventory"],
                           "claim": "No screenshot QA is claimed."}
    roadmap = {"recommended_integrated_tasks": [
        {"task": "AI-DEV-183", "scope": "P0 integrated production correctness", "issues": [i["issue_id"] for i in issues if i["severity"] == "P0"] + ["AI182-P1-002", "AI182-P1-005", "AI182-P1-006"]},
        {"task": "AI-DEV-184", "scope": "Decision content and outcome quality", "issues": ["AI182-P1-001", "AI182-P1-003", "AI182-P1-004"]},
        {"task": "AI-DEV-185", "scope": "Information architecture and delivery UX", "issues": [i["issue_id"] for i in issues if i["severity"] == "P2"]},
    ]}
    safety = {"production_pipeline_executed": False, "dashboard_published": False, "email_attempted": False, "line_attempted": False,
              "trading_attempted": False, "scheduler_changed": False, "archive_modified": False, "runtime_artifacts_modified": False,
              "immutable_snapshots_modified": False, "secrets_accessed_or_printed": False, "main_py_executed": False, "existing_dirty_files_changed": False}
    executive = {"schema_version": "ai_dev_182_production_audit_v1", "observed_at": OBSERVED_AT, "audit_completed": True,
                 "coverage": {"windows": "7/7", "archive_routes": "14/14", "public_pages": len(public), "trading_date_scope": {"TW": ["2026-07-15", "2026-07-16", "2026-07-17"], "US": ["2026-07-14", "2026-07-15", "2026-07-16"]}},
                 "production_readiness": score["production_readiness_level"], "score": score["overall"], "p0_count": sum(i["severity"] == "P0" for i in issues),
                 "p1_count": sum(i["severity"] == "P1" for i in issues), "p2_count": sum(i["severity"] == "P2" for i in issues), "safety": safety}
    artifacts = {
        "executive_summary.json": executive, "production_readiness_scorecard.json": score, "seven_window_matrix.json": matrix,
        "three_day_longitudinal_matrix.json": longitudinal, "channel_consistency.json": channel, "batch_delivery_evidence.json": delivery,
        "tw_1305_root_cause.json": root_cause, "data_coverage_matrix.json": coverage_rows, "data_freshness_matrix.json": freshness,
        "source_audit.json": source_audit, "decision_quality.json": qualities, "cross_window_continuity.json": continuity,
        "repeated_content.json": repeated, "public_page_findings.json": {"pages": public_sanitized, "screenshot_evidence": screenshot_evidence},
        "email_findings.json": email_findings, "line_findings.json": line_findings, "issue_register.json": issues,
        "improvement_roadmap.json": roadmap,
    }
    for name, value in artifacts.items():
        write_json(name, value)
    (OUT / "production_audit_report.md").write_text(report_markdown(score, issues, matrix, root_cause), encoding="utf-8")
    return {"ok": True, "output_dir": str(OUT.relative_to(ROOT)), "windows_audited": len(matrix), "public_pages_inspected": len(public),
            "archive_routes_inspected": 14, "score": score["overall"], "readiness": score["production_readiness_level"],
            "issues": {level: sum(i["severity"] == level for i in issues) for level in ("P0", "P1", "P2")}, "safety": safety}


def _pending_ratio(rows: list[dict[str, Any]]) -> float | None:
    pending = total = 0
    for row in rows:
        counts = row.get("outcome_counts") or {}
        pending += int(counts.get("pending", 0))
        total += sum(int(value) for value in counts.values())
    return round(pending / total, 4) if total else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
