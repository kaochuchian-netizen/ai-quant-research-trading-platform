from __future__ import annotations
from copy import deepcopy

SAMPLE_INPUT = {
    "schema_version": "finmind_report_integration_input_v1",
    "as_of_date": "2026-07-03",
    "stock_id": "2330",
    "stock_name": "台積電",
    "source_kind": "offline_sample",
    "sections": {
        "monthly_revenue": {"period": "2026-06", "revenue_yoy_pct": 18.4, "revenue_mom_pct": 2.1},
        "financial_statement_summary": {"period": "2026Q1", "gross_margin_pct": 54.2, "operating_margin_pct": 42.8, "net_margin_pct": 38.7},
        "eps": {"period": "2026Q1", "eps": 8.7},
        "roe": {"period": "2026Q1", "roe_pct": 27.5},
        "margin": {"period": "2026Q1", "gross_margin_pct": 54.2, "operating_margin_pct": 42.8},
        "institutional_trading": {"period": "2026-07-03", "foreign_net_buy_shares": 1250000, "investment_trust_net_buy_shares": 180000},
        "dividend": {"year": "2025", "cash_dividend": 13.5, "stock_dividend": 0.0},
        "share_capital": {"period": "2026-07-03", "share_capital_billion_twd": 259.3},
        "market_cap": {"period": "2026-07-03", "market_cap_billion_twd": 23800.0},
    },
    "advisory_only": True,
}

def offline_sample_input() -> dict:
    return deepcopy(SAMPLE_INPUT)
