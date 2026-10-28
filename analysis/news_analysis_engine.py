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
    if prompt_items:
        prompt = build_aggregation_news_prompt(stock_id, stock_name, prompt_items)
        ai = generate_analysis(prompt, structured=True)
    else:
        ai = {"status": "SKIPPED", "reason_code": "NO_ADMITTED_EVIDENCE", "text": ""}
    if (not isinstance(ai, dict)
            or ai.get("status") not in {"SUCCESS", "TIMEOUT", "QUOTA", "TRANSPORT_ERROR", "PARSE_ERROR", "CONFIGURATION_ERROR", "SKIPPED"}
            or ai.get("status") == "SUCCESS" and (not isinstance(ai.get("text"), str) or not ai["text"].strip())):
        ai = {"status": "PARSE_ERROR", "reason_code": "AI_INVALID_RESPONSE", "text": ""}
    labels = {"TIMEOUT": "新聞分析逾時", "QUOTA": "新聞分析服務額度受限",
              "TRANSPORT_ERROR": "新聞分析服務連線失敗", "PARSE_ERROR": "新聞分析回應格式無效",
              "CONFIGURATION_ERROR": "新聞分析服務設定不可用", "SKIPPED": "尚無通過證據門檻的新聞"}
    result = ai["text"] if ai.get("status") == "SUCCESS" else labels.get(ai.get("status"), "新聞分析未完成")
    selected = {item.get("source_url") for item in prompt_items}
    for item in news_items:
        item["analysis_status"] = ("ANALYZED" if ai.get("status") == "SUCCESS" else "AI_" + ai["status"]) if item.get("source_url") in selected else "ANALYSIS_BUDGET" if item.get("admission_status") == "ADMITTED" else "NOT_ADMITTED"
    funnel = dict(aggregation.get("funnel") or {})
    funnel["analysis_selected"] = len(prompt_items)
    funnel["analyzed"] = len(prompt_items) if ai.get("status") == "SUCCESS" else 0
    ai = {k: v for k, v in ai.items() if k != "text"}
    ai["evidence_urls"] = sorted(url for url in selected if url)

    if not include_evidence:
        return result

    retrieval = dict(aggregation.get("retrieval") or {})
    retrieval.setdefault("query_started_at", started_at)
    retrieval.setdefault("query_completed_at", datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    return {
        "analysis": result,
        "ai_analysis": ai,
        "funnel": funnel,
        "news_window": aggregation.get("news_window"),
        "items": news_items,
        "content_relevance_enrichment": aggregation.get("content_relevance_enrichment") or _empty_enrichment(),
        "source_health": aggregation.get("source_health") or {},
        "cnyes_collection": aggregation.get("cnyes_collection"),
        "prompt_policy": aggregation.get("prompt_policy") or {},
        "retrieval": retrieval,
    }
