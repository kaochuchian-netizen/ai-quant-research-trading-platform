"""User-controlled news acquisition switch; disabled unless explicitly approved.

Do not set STOCK_AI_NEWS_FETCH_ENABLED=1 in Production without fresh user
approval. Missing, invalid and false values fail closed. Historical evidence
and pure research/rendering functions are deliberately independent of this flag.
"""
import os

NEWS_PAUSED = "NEWS_PAUSED"
NEWS_PAUSED_LABEL = "新聞功能暫停"


def news_fetch_enabled():
    return os.environ.get("STOCK_AI_NEWS_FETCH_ENABLED", "0") == "1"


def require_news_enabled():
    if not news_fetch_enabled():
        raise ValueError(NEWS_PAUSED)


def paused_diagnostics(market, symbol):
    from app.research.news_evidence_funnel import NEWS_STAGES
    return {"schema_version": "cross_market_research_news_funnel_v1",
            "market": market, "symbol": symbol, "news_status": NEWS_PAUSED,
            "absence_state": NEWS_PAUSED, "state_label": NEWS_PAUSED_LABEL,
            "stages": {key: 0 for key in NEWS_STAGES}, "candidate_records": [],
            "rejection_reasons": {}, "source_attempts": {},
            "retrieval": {"status": NEWS_PAUSED, "reason_code": NEWS_PAUSED,
                          "failure_reason": NEWS_PAUSED, "request_count": 0,
                          "sources_attempted": [], "sources_succeeded": [], "sources_failed": []},
            "coverage": {"status": NEWS_PAUSED, "reason_codes": [NEWS_PAUSED], "candidate_count": 0}}


def paused_tw_news(symbol):
    diagnostics = paused_diagnostics("TW", str(symbol))
    return {"schema_version": "tw_news_aggregation_v1", "items": [],
            "analysis": NEWS_PAUSED_LABEL, "news_status": NEWS_PAUSED,
            "ai_analysis": {"status": "SKIPPED", "reason_code": NEWS_PAUSED},
            "source_health": {name: {"attempted": False, "status": NEWS_PAUSED,
                              "reason": NEWS_PAUSED, "result_count": 0}
                              for name in ("GOOGLE_NEWS_RSS", "CNYES")},
            "retrieval": diagnostics["retrieval"], "evidence_funnel": diagnostics,
            "funnel": {key: 0 for key in ("fetched", "in_window", "deduped", "admitted", "analyzed")}}
