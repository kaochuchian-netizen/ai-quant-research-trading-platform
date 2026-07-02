"""Render a mobile-first static Dashboard Intelligence preview."""
from __future__ import annotations
from html import escape
from typing import Any, Dict
FORBIDDEN_OUTPUT_PREFIX = "/var/www/stock-ai-dashboard"

def render_preview_html(artifact: Dict[str, Any]) -> str:
    cards = []
    for stock in artifact.get("stock_cards", []):
        cards.append(f"""<article class=\"card priority-{escape(stock['dashboard_priority'])}\"><h3>{escape(stock['stock_id'])} {escape(stock['stock_name'])}</h3><p class=\"meta\">{escape(stock['rating'])} / {escape(stock['action'])} / confidence {stock['confidence']}</p><p>Priority: <strong>{escape(stock['dashboard_priority'])}</strong></p><p>Positive: {escape(', '.join(stock['top_positive_factors']))}</p><p>Negative: {escape(', '.join(stock['top_negative_factors']))}</p><p>Missing: {escape(', '.join(stock['missing_data_factors']))}</p><p class=\"safe\">Advisory only. No trade instruction.</p></article>""")
    sections = []
    for section in artifact.get("sections", []):
        if section["section_id"] == "stock_intelligence_cards":
            body = "\n".join(cards)
        else:
            body = "".join(f"<article class=\"card\"><h3>{escape(card.get('title', 'Card'))}</h3><p>{escape(str(card.get('summary', '')))}</p></article>" for card in section.get("cards", []))
        sections.append(f"<section><h2>{escape(section['title'])}</h2><p>{escape(section['summary'])}</p>{body}</section>")
    return """<!doctype html><html lang=\"zh-Hant\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Dashboard Intelligence V1 Preview</title><style>body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f7f8;color:#142027}header{padding:20px 16px;background:#12323a;color:white}main{max-width:760px;margin:0 auto;padding:12px}section{margin:14px 0;padding:12px 0;border-top:1px solid #d7e0e3}.card{background:white;border:1px solid #dbe4e7;border-radius:8px;padding:12px;margin:10px 0;box-shadow:0 1px 2px rgba(0,0,0,.04)}.priority-high{border-left:5px solid #b42318}.priority-watch{border-left:5px solid #b7791f}.priority-medium{border-left:5px solid #2f6f9f}.safe,.meta{color:#50626b;font-size:.92rem}h1,h2,h3{line-height:1.2}h1{font-size:1.45rem}h2{font-size:1.18rem}</style></head><body><header><h1>Dashboard Intelligence V1 Preview</h1><p>Repo-side, mobile-first, advisory-only preview. Not production published.</p></header><main>""" + "\n".join(sections) + "</main></body></html>\n"
