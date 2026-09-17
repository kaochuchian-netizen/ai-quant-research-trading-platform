from datetime import datetime, timezone

from analysis.news_fetcher import fetch_stock_news
from app.research.tw_news_content_relevance import enrich_news_items
from analysis.news_prompt_builder import build_news_prompt
from analysis.gemini_client import generate_analysis


def analyze_news(stock_id, stock_name, *, include_evidence=False):
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    failure_reason = None
    try:
        news_items = fetch_stock_news(stock_id, stock_name)
        if not news_items:
            failure_reason = "NO_RESULT"
    except Exception as exc:
        news_items = []
        failure_reason = "SOURCE_TIMEOUT" if "timeout" in exc.__class__.__name__.lower() else "PARSER_FAILED"

    prompt = build_news_prompt(
        stock_id,
        stock_name,
        news_items
    )

    result = generate_analysis(prompt)

    if not include_evidence:
        return result

    enrichment = {
        "schema_version": "tw_news_content_relevance_enrichment_v1",
        "items_total": len(news_items),
        "content_success": 0,
        "content_failed": 0,
        "evaluated": 0,
        "admission_ready": 0,
        "rejection_reasons": {},
    }
    if news_items:
        news_items, enrichment = enrich_news_items(
            news_items,
            stock_id=str(stock_id),
            stock_name=str(stock_name),
        )

    completed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "analysis": result,
        "items": news_items,
        "content_relevance_enrichment": enrichment,
        "retrieval": {
            "lookback_hours": 72,
            "sources_attempted": ["GOOGLE_NEWS_RSS"],
            "sources_succeeded": ["GOOGLE_NEWS_RSS"] if news_items else [],
            "sources_failed": ([{"source": "GOOGLE_NEWS_RSS", "reason": failure_reason}] if failure_reason else []) + [
                {"source": source, "reason": "SOURCE_NOT_CONFIGURED"}
                for source in ("MOPS", "TWSE", "COMPANY_IR")
            ],
            "query_started_at": started_at,
            "query_completed_at": completed_at,
            "result_count_raw": len(news_items),
            "result_count_deduped": len(news_items),
            "result_count_admitted": 0,
            "result_count_evaluation_ready": int(enrichment.get("admission_ready") or 0),
            "failure_reason": failure_reason,
        },
    }
