"""Top-level read-only projection for Research Reasoning Engine V1."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .evidence import normalize_many
from .hypothesis import build_hypothesis, validate_hypothesis
from .knowledge import get_knowledge, validate_knowledge
from .narrative import build_market_narrative
from .reasoning import build_reasoning, validate_reasoning

MODEL_BOUNDARY = {"read_only": True, "strategy_modified": False, "scoring_modified": False,
                  "ranking_modified": False, "prediction_modified": False, "trade_action_exported": False,
                  "auto_learning": False}


def build_research_reasoning_projection(market: str, effective_date: str, evidence_by_symbol: dict[str, list[dict[str, Any]]], triggers: dict[str, dict[str, str]]) -> dict[str, Any]:
    market = market.upper()
    if market not in {"TW", "US"}: raise ValueError("unsupported market")
    bundles = []
    for symbol in sorted(evidence_by_symbol):
        evidence = normalize_many(evidence_by_symbol[symbol], market=market)
        knowledge = get_knowledge(market, symbol)
        reasoning = build_reasoning(market, symbol, evidence, knowledge)
        spec = triggers.get(symbol) or {}
        hypothesis = build_hypothesis(reasoning, expected_trigger=str(spec.get("expected_trigger") or "新增證據確認目前研究方向"), invalidation=str(spec.get("invalidation") or "核心反向證據成立或資料時效失效"))
        bundles.append({"symbol": symbol.upper(), "evidence": evidence, "knowledge": knowledge, "reasoning": reasoning, "hypothesis": hypothesis})
    projection = {"schema_version": "research_reasoning_engine_v1", "market": market, "effective_date": effective_date,
                  "bundles": bundles, "market_narrative": build_market_narrative(market, [x["reasoning"] for x in bundles]),
                  "review_hooks": {"window": "post_close_review", "automatic_learning": False,
                                   "dimensions": ["hypothesis", "evidence", "conflict", "missing_evidence"]},
                  "model_boundary": MODEL_BOUNDARY}
    raw = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    projection["research_reasoning_identity"] = "rre_" + hashlib.sha256(raw.encode()).hexdigest()[:24]
    return projection


def validate_projection(value: dict[str, Any]) -> list[str]:
    errors = []
    market = value.get("market")
    for bundle in value.get("bundles", []):
        if any(x.get("market") != market for x in bundle.get("evidence", [])): errors.append("cross_market_evidence")
        errors.extend(f"{bundle.get('symbol')}:knowledge:{x}" for x in validate_knowledge(bundle.get("knowledge", {})))
        ids = {x["evidence_id"] for x in bundle.get("evidence", [])}
        errors.extend(f"{bundle.get('symbol')}:reasoning:{x}" for x in validate_reasoning(bundle.get("reasoning", {}), ids))
        errors.extend(f"{bundle.get('symbol')}:hypothesis:{x}" for x in validate_hypothesis(bundle.get("hypothesis", {})))
    if value.get("model_boundary") != MODEL_BOUNDARY: errors.append("model_boundary")
    if not value.get("market_narrative", {}).get("narrative"): errors.append("market_narrative")
    return errors
