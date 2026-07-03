"""Reusable report section builders."""
from __future__ import annotations
from typing import Any
def normalize_stock_cards(raw_cards: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    cards = raw_cards or [{"stock_id": "2330", "stock_name": "台積電", "signal": "中性", "summary": "樣本資料，僅供內容契約驗證。", "advisory_only": True}]
    return [{"stock_id": str(c.get("stock_id", "unknown")), "stock_name": str(c.get("stock_name", "unknown")), "signal": str(c.get("signal", "中性")), "summary": str(c.get("summary", "資料不足，維持觀察。")), "advisory_only": bool(c.get("advisory_only", True))} for c in cards]
def review_state_cards(content_state: str) -> list[dict[str, Any]]:
    if content_state == "prediction_review_available":
        return [{"title": "預測檢討摘要", "state": "available", "summary": "已產生預測命中與待追蹤摘要。"}]
    if content_state == "prediction_review_insufficient_data":
        return [{"title": "今日預測檢討資料尚不足", "state": "insufficient_data", "summary": "部分 actual outcome 或 evaluation records 尚未完成。"}]
    return [{"title": "今日預測檢討待完成", "state": "pending", "summary": "目前顯示盤後摘要與待檢討狀態。"}]
def base_sections(display_label: str, content_state: str, summary: str) -> list[dict[str, Any]]:
    return [{"heading": f"{display_label}摘要", "body": summary}, {"heading": "內容狀態", "body": content_state}]
