"""Window-specific report contracts for TW/US delivery surfaces."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.dashboard.dashboard_url_registry import get_tw_dashboard_url, get_us_dashboard_url

SCHEMA_VERSION = "window_report_contract_v1"


@dataclass(frozen=True)
class WindowReportContract:
    market: str
    window: str
    title: str
    short_label: str
    primary_question: str
    dashboard_sections: tuple[str, ...]
    email_sections: tuple[str, ...]
    line_summary_scope: tuple[str, ...]
    suppressed_sections: tuple[str, ...]
    required_markers: tuple[str, ...]
    dashboard_url: str
    manual_button_label: str
    confirmation_label: str
    backend_command: tuple[str, ...]
    artifact_scope: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = SCHEMA_VERSION
        return data


TW_DASHBOARD_URL = get_tw_dashboard_url()
US_DASHBOARD_URL = get_us_dashboard_url()

CONTRACTS: dict[tuple[str, str], WindowReportContract] = {
    ("TW", "pre_open_0700"): WindowReportContract(
        "TW", "pre_open_0700", "07:00 盤前決策", "07:00 盤前",
        "今天開盤前怎麼看？哪些標的可觀察、哪些不要追，進場／停損／目標在哪？",
        ("今日盤前重點", "市場環境", "Top opportunities", "No-trade list", "Chase-risk list", "Entry readiness", "Confidence distribution", "每日短線策略摘要", "今日預測區間", "進場區 / 停損 / 目標價", "主要依據 / 主要風險", "主要新聞與事件", "資料完整度", "與前一次 07:00 同時段的變化"),
        ("今日盤前重點", "今日可觀察標的", "高風險標的", "研究摘要", "每日短線策略摘要", "今日預測區間", "進場區 / 停損 / 目標價"),
        ("台股盤前摘要", "研究統計", "每日短線策略統計", "高風險數量", "TW Dashboard URL"),
        ("盤後檢討主文", "7 日滾動檢討長文"),
        ("07:00 盤前決策", "今日盤前重點", "今日可觀察標的"),
        TW_DASHBOARD_URL, "重跑 07:00 盤前", "確認執行台股 07:00 盤前重跑",
        ("./venv/bin/python", "scripts/orchestrator/approved_pre_open_delivery.py", "--window", "pre_open_0700", "--manual-rerun"),
        "TW artifacts / TW Dashboard only",
    ),
    ("TW", "intraday_1305"): WindowReportContract(
        "TW", "intraday_1305", "13:05 盤中變化", "13:05 盤中",
        "盤中是否出現變化？早上的 setup 是否觸發，現在還能不能做？",
        ("盤中變化摘要", "與盤前相比的變化", "已觸發 setup", "尚未觸發 setup", "已失效 setup", "Still actionable", "Target proximity ranking", "Stop risk ranking", "Price / volume confirmation", "New risk since 07:00"),
        ("盤中變化摘要", "與盤前相比的變化", "已觸發 setup", "尚未觸發 setup", "接近 stop 的標的", "接近 target 的標的", "盤中風險變化"),
        ("盤中追蹤摘要", "已觸發 setup：N", "接近 target：N", "接近 stop：N", "TW Dashboard URL"),
        ("完整中長期 Research", "完整財務體質", "完整 SEC / 基本面長文"),
        ("13:05 盤中變化", "盤中變化摘要", "已觸發 setup"),
        TW_DASHBOARD_URL, "重跑 13:05 盤中", "確認執行台股 13:05 盤中重跑",
        ("./venv/bin/python", "scripts/orchestrator/approved_pre_open_delivery.py", "--window", "intraday_1305", "--manual-rerun"),
        "TW artifacts / TW Dashboard only",
    ),
    ("TW", "pre_close_1335"): WindowReportContract(
        "TW", "pre_close_1335", "13:35 收盤快照", "13:35 收盤快照",
        "收盤前是否要調整？今天還能不能追，是否應等待明天？",
        ("收盤前快照", "留倉候選", "不留倉候選", "尾盤風險升高標的", "是否避免追高", "接近目標 / 接近停損", "當日 setup 最終狀態", "明日 watchlist 新增 / 移除", "與前一次 13:35 的同時段變化"),
        ("收盤前快照", "尾盤風險", "是否避免追高", "接近目標 / 接近停損", "當日 setup 狀態", "明日初步觀察"),
        ("收盤快照摘要", "尾盤高風險：N", "明日觀察：N", "不追價提醒", "TW Dashboard URL"),
        ("完整盤前操作計畫", "完整 Research 長文"),
        ("13:35 收盤快照", "收盤前快照", "不追價提醒"),
        TW_DASHBOARD_URL, "重跑 13:35 收盤快照", "確認執行台股 13:35 收盤快照重跑",
        ("./venv/bin/python", "scripts/orchestrator/approved_pre_open_delivery.py", "--window", "pre_close_1335", "--manual-rerun"),
        "TW artifacts / TW Dashboard only",
    ),
    ("TW", "post_close_1500"): WindowReportContract(
        "TW", "post_close_1500", "15:00 盤後檢討", "15:00 盤後檢討",
        "今天預測準不準？哪些 setup 成功，哪些沒有觸發，明天要看什麼？",
        ("盤後檢討", "今日預測 vs 實際", "Outcome distribution", "Direction hit rate", "Trigger quality", "Target effectiveness", "Stop effectiveness", "MFE / MAE", "False Breakout", "Confidence calibration", "7-day trend", "明日觀察清單", "與前一次 15:00 同時段的差異"),
        ("盤後檢討", "今日預測 vs 實際", "進場 / 目標 / 停損檢討", "成功 / 失敗 / 未觸發 / 無交易", "7 日滾動檢討", "明日觀察清單"),
        ("盤後檢討摘要", "今日命中 / 未觸發 / 失敗 數量", "7 日檢討狀態", "TW Dashboard URL"),
        ("新的盤前建議", "盤前機會主文"),
        ("15:00 盤後檢討", "今日預測 vs 實際", "7 日滾動檢討"),
        TW_DASHBOARD_URL, "重跑 15:00 盤後檢討", "確認執行台股 15:00 盤後檢討重跑",
        ("./venv/bin/python", "scripts/orchestrator/approved_pre_open_delivery.py", "--window", "post_close_1500", "--manual-rerun"),
        "TW artifacts / TW Dashboard only",
    ),
    ("US", "us_pre_market_2000"): WindowReportContract(
        "US", "us_pre_market_2000", "20:00 美股盤前", "20:00 美股盤前",
        "美股開盤前有哪些機會與風險？premarket / gap / 事件風險如何？",
        ("美股盤前重點", "Premarket movers", "Gap continuation risk", "SPY / QQQ / Sector context", "VIX / market risk", "Event-risk ranking", "Sector-relative strength", "Entry readiness", "進場 / 停損 / 目標價", "財報 / SEC / 官方事件", "近期市場新聞", "高波動 / 高追價風險", "與前一次 20:00 同時段的變化"),
        ("美股盤前重點", "Premarket / gap 狀態", "今日 Tactical setup", "進場 / 停損 / 目標價", "財報 / SEC / 官方事件", "近期市場新聞", "高波動 / 高追價風險"),
        ("美股盤前摘要", "可觀察：N", "高風險：N", "重大事件：N", "US Dashboard URL"),
        ("盤後 outcome 長文", "完整 review 表格"),
        ("20:00 美股盤前", "Premarket / gap 狀態", "今日 Tactical setup"),
        US_DASHBOARD_URL, "重跑 20:00 美股盤前", "確認執行美股 20:00 盤前重跑",
        ("./venv/bin/python", "scripts/orchestrator/approved_us_stock_delivery.py", "--window", "us_pre_market_2000", "--dry-run", "--production-artifact", "--manual-rerun", "--pretty"),
        "US artifacts / US Dashboard only",
    ),
    ("US", "us_intraday_2300"): WindowReportContract(
        "US", "us_intraday_2300", "23:00 美股盤中", "23:00 美股盤中",
        "開盤後是否符合盤前預期？setup 是否確認？",
        ("美股盤中變化", "Confirmed setups", "Failed gaps", "Volume-confirmed moves", "Still actionable", "Chase risk", "Gap follow-through", "Entry trigger", "目標 / 停損接近度", "盤中新聞 / 事件更新", "Tactical adjustment", "與 20:00 預期的偏差"),
        ("美股盤中變化", "Gap follow-through", "Volume confirmation", "進場觸發狀態", "目標 / 停損接近度", "盤中新聞 / 事件更新", "Tactical adjustment"),
        ("美股盤中摘要", "已確認 setup：N", "接近 target：N", "接近 stop：N", "US Dashboard URL"),
        ("完整 Research 長文", "完整財務卡片", "完整 SEC 長列表"),
        ("23:00 美股盤中", "Gap follow-through", "Volume confirmation"),
        US_DASHBOARD_URL, "重跑 23:00 美股盤中", "確認執行美股 23:00 盤中重跑",
        ("./venv/bin/python", "scripts/orchestrator/approved_us_stock_delivery.py", "--window", "us_intraday_2300", "--dry-run", "--production-artifact", "--manual-rerun", "--pretty"),
        "US artifacts / US Dashboard only",
    ),
    ("US", "us_post_close_review_0630"): WindowReportContract(
        "US", "us_post_close_review_0630", "06:30 美股檢討", "06:30 美股檢討",
        "美股交易日結果如何？昨天 tactical 是否有效，隔日要觀察什麼？",
        ("美股全日 outcome", "Prediction review", "Review distribution", "Direction hit", "Setup quality", "Gap effectiveness", "進場 / 停損 / 目標價 outcome", "MFE / MAE", "Confidence calibration", "財報 / SEC / overnight event update", "Next-session watchlist", "與前一次 06:30 同時段的變化"),
        ("美股盤後檢討", "預測檢討", "進場 / 停損 / 目標價 outcome", "成功 / 失敗 / 未觸發", "隔日觀察"),
        ("美股檢討摘要", "今日 review 結果", "隔日觀察", "US Dashboard URL"),
        ("盤前機會主文", "premarket 追價建議"),
        ("06:30 美股檢討", "預測檢討", "隔日觀察"),
        US_DASHBOARD_URL, "重跑 06:30 美股檢討", "確認執行美股 06:30 檢討重跑",
        ("./venv/bin/python", "scripts/orchestrator/approved_us_stock_delivery.py", "--window", "us_post_close_review_0630", "--dry-run", "--production-artifact", "--manual-rerun", "--pretty"),
        "US artifacts / US Dashboard only",
    ),
}

ALIASES = {
    ("TW", "prediction_review_1500"): ("TW", "post_close_1500"),
    ("US", "us_review_0630"): ("US", "us_post_close_review_0630"),
}


def normalize_market(market: str | None) -> str:
    value = str(market or "TW").upper()
    return "US" if value == "US" else "TW"


def normalize_window(market: str | None, window: str) -> tuple[str, str]:
    key = (normalize_market(market), str(window))
    return ALIASES.get(key, key)


def get_window_report_contract(market: str | None, window: str) -> WindowReportContract:
    key = normalize_window(market, window)
    if key not in CONTRACTS:
        raise ValueError(f"unsupported report contract: {key[0]} {key[1]}")
    return CONTRACTS[key]


def all_window_report_contracts() -> list[WindowReportContract]:
    order = [
        ("TW", "pre_open_0700"),
        ("TW", "intraday_1305"),
        ("TW", "pre_close_1335"),
        ("TW", "post_close_1500"),
        ("US", "us_pre_market_2000"),
        ("US", "us_intraday_2300"),
        ("US", "us_post_close_review_0630"),
    ]
    return [CONTRACTS[key] for key in order]


def manual_batch_contracts() -> dict[str, WindowReportContract]:
    return {contract.window: contract for contract in all_window_report_contracts()}


def no_send_matrix() -> list[dict[str, Any]]:
    rows = []
    for contract in all_window_report_contracts():
        rows.append({
            "market": contract.market,
            "window": contract.window,
            "title": contract.title,
            "dashboard_url": contract.dashboard_url,
            "email": False,
            "line": False,
            "trading": False,
            "scheduler_changed": False,
            "result": "PASS",
        })
    return rows
