from datetime import datetime, timezone

from analysis.news_fetcher import fetch_stock_news
from analysis.gemini_client import generate_analysis
from app.research.tw_news_aggregation import build_aggregation_news_prompt, collect_tw_news, select_prompt_news_items


def _empty_enrichment() -> dict:
    return {
        "schema_version": "tw_news_content_relevance_enrichment_v1",
        "items_total": 0,
        "content_success": 0,
        "content_failed": 0,
        "evaluated": 0,
        "admission_ready": 0,
        "rejection_reasons": {},
    }


def analyze_news(stock_id, stock_name, *, include_evidence=False, aggregation_session=None, reference=None):
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        aggregation = collect_tw_news(
            stock_id,
            stock_name,
            reference=reference or started_at,
            session=aggregation_session,
            google_fetcher=fetch_stock_news,
            include_cnyes=aggregation_session is not None,
        )
    except Exception as exc:
        completed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        aggregation = {
            "schema_version": "tw_news_aggregation_v1",
            "items": [],
            "content_relevance_enrichment": _empty_enrichment(),
            "source_health": {
                "GOOGLE_NEWS_RSS": {"attempted": True, "status": "failed", "reason": exc.__class__.__name__, "result_count": 0},
                "CNYES": {"attempted": True, "status": "degraded", "reason": "AGGREGATION_FAILED", "result_count": 0},
            },
            "retrieval": {
                "lookback_hours": 72,
                "sources_attempted": ["GOOGLE_NEWS_RSS", "CNYES"],
                "sources_succeeded": [],
                "sources_failed": [{"source": "TW_NEWS_AGGREGATION", "reason": exc.__class__.__name__}],
                "sources_degraded": ["CNYES"],
                "query_started_at": started_at,
                "query_completed_at": completed_at,
                "result_count_raw": 0,
                "result_count_deduped": 0,
                "result_count_admitted": 0,
                "result_count_evaluation_ready": 0,
                "failure_reason": "AGGREGATION_FAILED",
            },
        }

    news_items = aggregation.get("items", [])
    prompt_items = select_prompt_news_items(news_items)
    prompt = build_aggregation_news_prompt(stock_id, stock_name, prompt_items)
    result = generate_analysis(prompt)

    if not include_evidence:
        return result

    retrieval = dict(aggregation.get("retrieval") or {})
    retrieval.setdefault("query_started_at", started_at)
    retrieval.setdefault("query_completed_at", datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    return {
        "analysis": result,
        "items": news_items,
        "content_relevance_enrichment": aggregation.get("content_relevance_enrichment") or _empty_enrichment(),
        "source_health": aggregation.get("source_health") or {},
        "cnyes_collection": aggregation.get("cnyes_collection"),
        "prompt_policy": aggregation.get("prompt_policy") or {},
        "retrieval": retrieval,
    }
