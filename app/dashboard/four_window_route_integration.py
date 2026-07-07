"""Controlled route integration artifact for the four-window dashboard preview."""
from __future__ import annotations
import json
from html import escape
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 'four_window_dashboard_route_integration_v1'
TASK_ID = 'AI-DEV-144'
GENERATED_AT = '2026-07-05T00:00:00Z'
ROUTE_PATH = '/dashboard/decision-intelligence/four-window-preview'
SOURCE_PREVIEW_ARTIFACT = 'templates/four_window_decision_intelligence_dashboard_artifact.example.json'
SOURCE_PREVIEW_HTML = 'templates/four_window_decision_intelligence_dashboard_preview.example.html'
ROUTE_HTML = 'templates/four_window_dashboard_route_preview.example.html'
REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DATA = 'templates/four_window_dashboard_runtime_data.example.json'
CALIBRATION_PROPOSAL = 'artifacts/runtime/forecast_calibration_proposal_latest.json'
SNAPSHOT_INDEX = 'artifacts/archive/formal_forecast_snapshots/index/formal_forecast_snapshot_index_latest.json'
SAFETY_POLICY = {'controlled_static_route': True, 'repo_side_preview_only': True, 'external_api_called': False, 'secrets_read': False, 'db_write': False, 'scheduler_modified': False, 'external_notification_sent': False, 'line_email_notification_sent': False, 'production_pipeline_executed': False, 'python_main_executed': False, 'trading_or_order_executed': False, 'production_dashboard_publish_executed': False, 'dashboard_published': False, 'formal_delivery_behavior_changed': False, 'direct_rating_action_confidence_impact': False, 'production_rating_action_confidence_weight_mutated': False}
ROLLBACK_INSTRUCTIONS = ['Remove the controlled dashboard route mapping from the future dashboard router.', 'Restore the previous dashboard preview route configuration.', 'Keep scheduler, notification delivery, production pipeline, and DB state untouched.', 'Re-run route integration and post-merge validators after rollback.']
FIELD_LABELS = {'actual_high': '今日實際最高價', 'actual_low': '今日實際最低價', 'actual_close': '今日收盤價', 'direction_result': '方向判斷結果', 'high_low_forecast_error': '高低價預測誤差', 'hit_miss_status': '命中 / 未命中', 'review_timestamp': '檢討時間', 'review_window': '檢討區間', 'seven_day_hit_rate': '過去 7 天命中率', 'confidence_calibration': '信心校準', 'factor_effectiveness': '因子有效性', 'error_reasons': '錯誤原因', 'recommendation_for_improvement': '明日改善建議'}
PREDICTION_FIELD_LABELS = [('今日最高價預測', 'same_day_high_prediction'), ('今日最低價預測', 'same_day_low_prediction'), ('隔天最高價預測', 'next_day_high_prediction'), ('隔天最低價預測', 'next_day_low_prediction'), ('未來 1 個月走勢', 'one_month_trend'), ('未來 3 個月走勢', 'three_month_trend'), ('信心分數', 'confidence_score'), ('信心水準', 'confidence_level'), ('主要依據', 'evidence_summary'), ('風險提醒', 'risk_notes'), ('資料品質摘要', 'data_quality'), ('模型版本', 'model_version'), ('方法說明', 'method_metadata'), ('資料證據', 'source_evidence')]
PREDICTION_LABELS = [('今日最高價預測 / 今日最低價預測', 'same_day_high_low'), ('隔天最高價預測 / 隔天最低價預測', 'next_day_high_low'), ('未來 1 個月走勢', 'one_month_trend'), ('未來 3 個月走勢', 'three_month_trend'), ('信心分數', 'confidence'), ('主要依據', 'rationale')]

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def build_input() -> dict[str, Any]:
    return {'schema_version': 'four_window_dashboard_route_integration_input_v1', 'task_id': TASK_ID, 'generated_at': GENERATED_AT, 'route_path': ROUTE_PATH, 'source_preview_artifact': SOURCE_PREVIEW_ARTIFACT, 'source_preview_html': SOURCE_PREVIEW_HTML, 'controlled_route_only': True, 'production_publish_allowed': False}

def _window_mapping(preview: dict[str, Any]) -> list[dict[str, Any]]:
    return [{'window_key': w.get('window_key'), 'ui_window_id': w.get('ui_window_id'), 'ui_display_name_zh': w.get('ui_display_name_zh'), 'ui_display_name_en': w.get('ui_display_name_en'), 'scheduled_time_tw': w.get('scheduled_time_tw'), 'market_phase': w.get('market_phase'), 'primary_purpose': w.get('primary_purpose'), 'full_prediction_review_assigned': w.get('ui_window_id') == 'prediction_review_1500'} for w in preview.get('four_window_content_contract', [])]

def build_artifact(payload: dict[str, Any] | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or Path.cwd()
    payload = payload or build_input()
    preview_ref = payload.get('source_preview_artifact', SOURCE_PREVIEW_ARTIFACT)
    html_ref = payload.get('source_preview_html', SOURCE_PREVIEW_HTML)
    preview = load_json(repo_root / preview_ref)
    return {'schema_version': SCHEMA_VERSION, 'task_id': TASK_ID, 'generated_at': payload.get('generated_at', GENERATED_AT), 'route_path': payload.get('route_path', ROUTE_PATH), 'route_id': 'four_window_decision_intelligence_preview_route', 'route_kind': 'controlled_static_dashboard_preview', 'source_preview_artifact': preview_ref, 'source_preview_html': html_ref, 'route_preview_html': ROUTE_HTML, 'four_window_mapping': _window_mapping(preview), 'semantic_rules': {'pre_open_0700_is_pre_open_forecast': True, 'intraday_1305_is_intraday_tracking': True, 'pre_close_1335_runtime_key_compatible': True, 'pre_close_1335_ui_id': 'close_snapshot_1335', 'pre_close_1335_ui_label_zh': '收盤快照', 'pre_close_1335_ui_label_en': 'Close Snapshot', 'pre_close_1335_primary_ui_must_not_be_pre_close': True, 'full_prediction_review_window_key': 'post_close_1500', 'full_prediction_review_ui_id': 'prediction_review_1500'}, 'route_integration_status': {'static_controlled_route_artifact_created': True, 'production_dashboard_publish_executed': False, 'dashboard_published': False, 'external_notification_sent': False, 'scheduler_modified': False, 'production_pipeline_executed': False, 'db_write': False}, 'validation_gates': ['validate_four_window_decision_intelligence_dashboard_ui_v1', 'validate_four_window_dashboard_preview_review_v1', 'validate_four_window_dashboard_route_integration_v1', 'validate_dashboard_decision_state_semantics_v1', 'validate_formal_prediction_runtime_artifact_v1', 'validate_formal_prediction_review_runtime_artifact_v1'], 'rollback_instructions': ROLLBACK_INSTRUCTIONS, 'safety_policy': SAFETY_POLICY}

def badge(status: str) -> str:
    return 'safe' if status in {'available', 'watchlist_valid', 'contract_backed'} else 'warn' if status in {'partial', 'missing', 'stale', 'not_for_formal_decision', 'insufficient_data'} else ''


def humanize_status(value: Any) -> str:
    mapping = {
        'correct': '正確',
        'incorrect': '錯誤',
        'hit': '命中',
        'partial_hit': '部分命中',
        'miss': '未命中',
        'insufficient_data': '資料不足',
        'reviewable_single_day': '單日資料可檢討',
        'single-day deterministic evaluation; seven-day review requires accumulated artifacts': '單日 deterministic baseline 評估；7 天檢討需累積更多正式 prediction / actual outcome artifact',
        'fresh': '資料新鮮',
        'stale': '資料過期',
        'missing': '資料待接',
        'partial': '部分資料可用',
        'insufficient_data': '資料不足',
        'sufficient_for_baseline_range': '足夠產生 baseline 區間',
        'artifact-level deterministic baseline formula capped at 75': 'artifact 層 deterministic baseline 公式，信心上限 75',
        'bullish': '偏多',
        'neutral': '中性',
        'bearish': '偏空',
        'uncertain': '不明朗',
        'low': '低',
        'medium': '中',
        'medium_high': '中高',
    }
    text = str(value)
    return mapping.get(text, text.replace('_', ' '))

def display_value(value: Any) -> str:
    if value is None or value == [] or value == {}:
        return '資料待接'
    if isinstance(value, list):
        return '、'.join(escape(str(v)) for v in value) if value else '資料待接'
    if isinstance(value, dict):
        parts = []
        if value.get('completeness'):
            parts.append('完整度：' + humanize_status(value.get('completeness')))
        if value.get('freshness'):
            parts.append('資料時效：' + humanize_status(value.get('freshness')))
        if value.get('confidence_basis'):
            parts.append('信心依據：' + humanize_status(value.get('confidence_basis')))
        if value.get('blocking_missing_fields'):
            parts.append('待接欄位數：' + str(len(value.get('blocking_missing_fields', []))))
        return escape('；'.join(parts) or '資料待接')
    return escape(str(value))

def source_cards(items: list[dict[str, Any]]) -> str:
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append('<div class="source-item"><h3>' + escape(str(item.get('label') or item.get('source_family') or 'source')) + '</h3><p>可信度：' + escape(str(item.get('quality') or item.get('credibility'))) + '</p><p>用途：' + escape(str(item.get('allowed_usage'))) + '</p></div>')
    return ''.join(out) or '<div class="source-item"><h3>資料來源政策</h3><p>資料待接。</p></div>'

def _price_range(low: Any, high: Any) -> str:
    if low is None or high is None:
        return '資料待接'
    return escape(str(low)) + ' ～ ' + escape(str(high))


def _confidence_text(stock: dict[str, Any]) -> str:
    score = stock.get('confidence_score')
    level = humanize_status(stock.get('confidence_level')) if stock.get('confidence_level') is not None else '資料待接'
    if score is None:
        return '資料待接'
    return escape(str(score)) + ' / 75，' + escape(level)


def _method_text(stock: dict[str, Any]) -> str:
    if stock.get('model_version') == 'deterministic_baseline_v1' or stock.get('method_metadata'):
        return 'deterministic baseline V1'
    return '資料待接'


def _method_note(stock: dict[str, Any]) -> str:
    if stock.get('method_metadata') or stock.get('evidence_summary'):
        return '以近 20 日高低價區間、報酬波動、ATR-like range 與均線/報酬率趨勢偏差估算。'
    return '方法資料待接。'


def _risk_items(stock: dict[str, Any]) -> list[str]:
    risks = [str(item) for item in stock.get('risk_notes', []) if item]
    cleaned = []
    for item in risks:
        text = item.replace('deterministic baseline V1', 'baseline V1')
        text = text.replace('production rating/action/confidence/weight', '正式評等 / 動作 / 信心 / 權重')
        text = text.replace('uncertainty / missing_fields', '不明朗狀態與待接欄位')
        cleaned.append(text)
    defaults = [
        'baseline V1 尚在回測校準階段。',
        '不修改正式評等 / 動作 / 信心 / 權重。',
    ]
    if stock.get('missing_fields'):
        defaults.append('部分長週期資料不足，3 個月趨勢維持不明朗。')
    return (cleaned or defaults)[:3]


def _quality_items(stock: dict[str, Any]) -> list[str]:
    quality = stock.get('data_quality') if isinstance(stock.get('data_quality'), dict) else {}
    source_rows = 0
    latest = quality.get('latest_ohlcv_date') or '資料待接'
    for source in stock.get('source_evidence', []):
        if isinstance(source, dict) and source.get('source_type') == 'historical_ohlcv_csv':
            source_rows = int(source.get('row_count') or source_rows or 0)
            latest = source.get('latest_ohlcv_date') or latest
    rows_text = str(source_rows) if source_rows else '資料待接'
    context_text = '待接' if stock.get('missing_fields') else '可用'
    return [
        '歷史 OHLCV：可用，' + rows_text + ' 筆。',
        '資料時效：' + str(latest) + '。',
        '補充分析脈絡：' + context_text + '。',
    ]


def _news_block(stock: dict[str, Any]) -> str:
    news_items = stock.get('major_news') or stock.get('news_headlines') or []
    if isinstance(news_items, list) and news_items:
        rows = []
        for index, item in enumerate(news_items[:3], start=1):
            if isinstance(item, dict):
                title = item.get('title') or '新聞標題待接'
                source = item.get('source') or '來源待接'
                time = item.get('published_at') or item.get('time') or '時間待接'
                impact = humanize_status(item.get('impact') or item.get('sentiment') or '中性')
                rows.append('<p>' + str(index) + '. ' + escape(str(title)) + ' — ' + escape(str(source)) + ' / ' + escape(str(time)) + ' / 影響：' + escape(str(impact)) + '</p>')
            else:
                rows.append('<p>' + str(index) + '. ' + escape(str(item)) + '</p>')
        return '<div class="review-block"><h4>重大新聞</h4>' + ''.join(rows) + '</div>'
    return '<div class="review-block"><h4>重大新聞</h4><p>重大新聞資料待接</p><p>說明：尚未找到可安全引用的新聞標題 artifact。</p></div>'

def prediction_cards(runtime: dict[str, Any]) -> str:
    artifact = runtime.get('formal_prediction_artifact') if isinstance(runtime.get('formal_prediction_artifact'), dict) else None
    if artifact and artifact.get('artifact_type') == 'formal_prediction_runtime' and artifact.get('is_example') is False:
        cards = []
        for stock in artifact.get('stocks', []):
            if not isinstance(stock, dict):
                continue
            title = escape(str(stock.get('stock_id'))) + ' ' + escape(str(stock.get('stock_name') or ''))
            summary = (
                '<div class="review-block"><h4>預測摘要</h4>'
                '<p><strong>今日預測區間：</strong>' + _price_range(stock.get('same_day_low_prediction'), stock.get('same_day_high_prediction')) + '</p>'
                '<p><strong>隔日預測區間：</strong>' + _price_range(stock.get('next_day_low_prediction'), stock.get('next_day_high_prediction')) + '</p>'
                '<p><strong>1 個月趨勢：</strong>' + escape(humanize_status(stock.get('one_month_trend'))) + '</p>'
                '<p><strong>3 個月趨勢：</strong>' + escape(humanize_status(stock.get('three_month_trend'))) + '</p>'
                '<p><strong>信心分數：</strong>' + _confidence_text(stock) + '</p>'
                '<p><strong>方法：</strong>' + escape(_method_text(stock)) + '</p>'
                '<p><strong>說明：</strong>' + escape(_method_note(stock)) + '</p>'
                '<p><strong>狀態：</strong>供研究參考，待回測校準。</p>'
                '</div>'
            )
            risks = ''.join('<li>' + escape(item) + '</li>' for item in _risk_items(stock))
            quality = ''.join('<li>' + escape(item) + '</li>' for item in _quality_items(stock))
            detail = (
                '<div class="review-block"><h4>風險與資料品質</h4>'
                '<p><strong>風險提醒：</strong></p><ul>' + risks + '</ul>'
                '<p><strong>資料品質：</strong></p><ul>' + quality + '</ul>'
                '</div>'
            )
            cards.append('<div class="source-item"><h3>' + title + '</h3>' + summary + detail + _news_block(stock) + '<span class="badge warn">deterministic baseline V1｜待回測校準｜不自動交易</span></div>')
        note = '<p class="preview-note">正式 prediction runtime artifact 已接線；Dashboard 主畫面只顯示 PM-readable 決策摘要。今日最高價預測、今日最低價預測、隔天最高價預測、隔天最低價預測已整合為今日 / 隔日預測區間；未來 1 個月走勢、未來 3 個月走勢與主要依據已整合為趨勢、方法與說明；工程欄位僅保留於 Debug/validator 使用。</p>'
        return note + '<div class="source-grid">' + ''.join(cards) + '</div>'
    out = []
    for label, _key in PREDICTION_LABELS:
        out.append('<div class="source-item"><h3>' + escape(label) + '</h3><p>資料待接</p><p>尚未找到正式 prediction runtime artifact，不產生假預測。</p><span class="badge warn">正式預測資料待接</span></div>')
    return '<div class="source-grid">' + ''.join(out) + '</div>'


def calibration_cards() -> str:
    path = REPO_ROOT / CALIBRATION_PROPOSAL
    if not path.exists():
        return '<p class="preview-note">Forecast Calibration / 回測校準狀態：資料待接。尚未找到 calibration proposal artifact，不產生假績效。</p>'
    data = load_json(path)
    same_day = data.get('same_day_interval_hit_rate')
    next_day = data.get('next_day_interval_hit_rate')
    recommendations = data.get('calibration_recommendations') if isinstance(data.get('calibration_recommendations'), list) else []
    rec_summary = '資料待接'
    if recommendations:
        first = recommendations[0] if isinstance(recommendations[0], dict) else {}
        rec_summary = str(first.get('proposal') or first.get('recommendation_id') or 'proposal only')
    sample = data.get('eligible_sample_count')
    gate = str(data.get('tuning_gate_status') or '資料待接')
    next_day_text = '資料不足' if next_day is None else str(next_day) + '%'
    same_day_text = '資料待接' if same_day is None else str(same_day) + '%'
    limitations = data.get('sample_limitations') if isinstance(data.get('sample_limitations'), list) else []
    limitation_text = '；'.join(str(item) for item in limitations) or '樣本限制資料待接'
    return (
        '<div class="source-grid">'
        '<div class="source-item"><h3>Forecast Calibration / 回測校準狀態</h3>'
        '<p><strong>方法：</strong>' + escape(str(data.get('method_under_test') or 'deterministic_baseline_v1')) + '</p>'
        '<p><strong>樣本數：</strong>' + escape(str(sample if sample is not None else '資料待接')) + '</p>'
        '<span class="badge warn">樣本數：' + escape(str(sample if sample is not None else '資料待接')) + '</span>'
        '<p><strong>今日高低價區間命中率：</strong>' + escape(same_day_text) + '</p>'
        '<p><strong>隔日高低價區間命中率：</strong>' + escape(next_day_text) + '</p>'
        '<p><strong>校準狀態：</strong>' + escape(gate) + '</p>'
        '<span class="badge warn">樣本數不足，不代表穩定績效</span></div>'
        '<div class="source-item"><h3>Method tuning gate</h3>'
        '<p><strong>調參建議：</strong>' + escape(rec_summary) + '</p>'
        '<p><strong>目前限制：</strong>' + escape(limitation_text) + '</p>'
        '<p><strong>下一步：</strong>累積更多 formal forecast / actual outcome artifacts。</p>'
        '<span class="badge warn">尚不可直接修改公式</span></div>'
        '</div>'
        '<p class="preview-note">目前為 baseline V1 回測初步結果，樣本數不足，不代表穩定績效；不可把 55.5556% 包裝成已通過完整驗證，也不可把隔日 null 顯示為 0%。</p>'
    )


def snapshot_accumulation_cards() -> str:
    path = REPO_ROOT / SNAPSHOT_INDEX
    if not path.exists():
        return '<p class="preview-note">Forecast Snapshot Accumulation / 預測樣本累積進度：資料待接。尚未建立 snapshot index，不產生假樣本。</p>'
    data = load_json(path)
    progress = data.get('calibration_gate_progress') if isinstance(data.get('calibration_gate_progress'), dict) else {}
    prediction_count = data.get('prediction_snapshot_count', 0)
    actual_count = data.get('actual_outcome_snapshot_count', 0)
    review_count = data.get('review_snapshot_count', 0)
    same_day = data.get('eligible_same_day_sample_count', 0)
    next_day = data.get('eligible_next_day_sample_count', 0)
    gate = progress.get('current_gate_status') or 'blocked_insufficient_sample'
    remaining_shadow = progress.get('remaining_samples_to_shadow_tuning', '資料待接')
    remaining_formula = progress.get('remaining_samples_to_formula_change', '資料待接')
    return (
        '<div class="source-grid">'
        '<div class="source-item"><h3>Forecast Snapshot Accumulation / 預測樣本累積進度</h3>'
        '<p><strong>已歸檔 prediction snapshots：</strong>' + escape(str(prediction_count)) + '</p>'
        '<p><strong>已歸檔 actual outcome snapshots：</strong>' + escape(str(actual_count)) + '</p>'
        '<p><strong>已歸檔 review snapshots：</strong>' + escape(str(review_count)) + '</p>'
        '<p><strong>可評估 same-day samples：</strong>' + escape(str(same_day)) + '</p>'
        '<p><strong>可評估 next-day samples：</strong>' + escape(str(next_day) if next_day else '資料不足') + '</p>'
        '<span class="badge warn">樣本累積，不是績效</span></div>'
        '<div class="source-item"><h3>Calibration Gate Progress</h3>'
        '<p><strong>Shadow tuning 門檻：30</strong></p>'
        '<p><strong>Formula change 門檻：100</strong></p>'
        '<p><strong>目前 gate：</strong>' + escape(str(gate)) + '</p>'
        '<p><strong>距離 shadow tuning 還差：</strong>' + escape(str(remaining_shadow)) + ' samples</p>'
        '<p><strong>距離 formula change 還差：</strong>' + escape(str(remaining_formula)) + ' samples</p>'
        '<span class="badge warn">blocked_insufficient_sample</span></div>'
        '</div>'
        '<p class="preview-note">目前仍為 deterministic baseline V1 樣本累積階段；樣本數不足時不可直接調整公式。不可把 snapshot count 當成績效，不可把 next-day null 顯示為 0%。</p>'
    )

def _review_status(value: Any) -> str:
    return humanize_status(value) if value is not None else '資料待接'


def _review_error_detail(stock: dict[str, Any]) -> str:
    error = stock.get('high_low_forecast_error')
    hit_status = stock.get('hit_miss_status')
    if isinstance(error, dict) and error:
        return (
            '<p><strong>高低價預測誤差：</strong>明細如下。</p>'
            '<p><strong>最高價誤差：</strong>' + display_value(error.get('high_error_abs')) + '</p>'
            '<p><strong>最低價誤差：</strong>' + display_value(error.get('low_error_abs')) + '</p>'
            '<p><strong>最高價誤差百分比：</strong>' + display_value(error.get('high_error_pct')) + '</p>'
            '<p><strong>最低價誤差百分比：</strong>' + display_value(error.get('low_error_pct')) + '</p>'
        )
    if hit_status:
        return '<p><strong>高低價預測誤差：</strong>命中狀態可用；誤差明細欄位待接。</p>'
    return '<p><strong>高低價預測誤差：</strong>資料待接</p>'


def _review_data_quality(stock: dict[str, Any]) -> str:
    quality = stock.get('data_quality') if isinstance(stock.get('data_quality'), dict) else {}
    parts = []
    if quality.get('completeness'):
        parts.append('完整度：' + humanize_status(quality.get('completeness')))
    if quality.get('freshness'):
        parts.append('資料狀態：' + humanize_status(quality.get('freshness')))
    if quality.get('confidence_basis'):
        parts.append('評估方式：' + humanize_status(quality.get('confidence_basis')))
    if quality.get('blocking_missing_fields'):
        parts.append('待接欄位數：' + str(len(quality.get('blocking_missing_fields', []))))
    return escape('；'.join(parts) or '資料待接')


def review_cards(runtime: dict[str, Any]) -> str:
    artifact = runtime.get('formal_review_artifact') if isinstance(runtime.get('formal_review_artifact'), dict) else None
    if artifact and artifact.get('artifact_type') == 'formal_prediction_review_runtime' and artifact.get('is_example') is False:
        cards = []
        for stock in artifact.get('stocks', []):
            if not isinstance(stock, dict):
                continue
            single_day = (
                '<div class="review-block"><h4>單日檢討</h4>'
                '<p><strong>今日實際最高價：</strong>' + display_value(stock.get('actual_high')) + '</p>'
                '<p><strong>今日實際最低價：</strong>' + display_value(stock.get('actual_low')) + '</p>'
                '<p><strong>今日收盤價：</strong>' + display_value(stock.get('actual_close')) + '</p>'
                '<p><strong>方向判斷結果：</strong>' + escape(_review_status(stock.get('direction_result'))) + '</p>'
                '<p><strong>命中 / 未命中：</strong>' + escape(_review_status(stock.get('hit_miss_status'))) + '</p>'
                + _review_error_detail(stock) +
                '<p><strong>檢討區間：</strong>' + escape(str(stock.get('review_window_start') or '資料待接')) + ' ~ ' + escape(str(stock.get('review_window_end') or '資料待接')) + '</p>'
                '<p><strong>產生時間：</strong>' + escape(str(artifact.get('generated_at') or stock.get('created_at') or '資料待接')) + '</p>'
                '<p><strong>資料品質摘要：</strong>' + _review_data_quality(stock) + '</p>'
                '</div>'
            )
            rolling_values_missing = stock.get('seven_day_hit_rate') is None or stock.get('confidence_calibration') == 'insufficient_data' or stock.get('factor_effectiveness') == 'insufficient_data'
            rolling_note = '<p class="preview-note">7 天滾動檢討：資料不足，需累積更多正式 prediction / actual outcome artifact。</p>' if rolling_values_missing else ''
            rolling = (
                '<div class="review-block"><h4>7 天滾動檢討</h4>'
                '<p><strong>過去 7 天命中率：</strong>' + display_value(stock.get('seven_day_hit_rate')) + '</p>'
                '<p><strong>信心校準：</strong>' + escape(_review_status(stock.get('confidence_calibration'))) + '</p>'
                '<p><strong>因子有效性：</strong>' + escape(_review_status(stock.get('factor_effectiveness'))) + '</p>'
                '<p><strong>錯誤原因：</strong>' + display_value(stock.get('error_reasons')) + '</p>'
                '<p><strong>明日改善建議：</strong>' + display_value(stock.get('recommendation_for_improvement')) + '</p>'
                + rolling_note +
                '</div>'
            )
            cards.append('<div class="source-item"><h3>' + escape(str(stock.get('stock_id'))) + ' ' + escape(str(stock.get('stock_name') or '')) + '</h3>' + single_day + rolling + '<span class="badge warn">正式檢討資料已接線；缺資料維持資料待接</span></div>')
        note = '<p class="preview-note">正式 prediction review runtime artifact 已接線；主畫面已轉為 PM 可讀狀態，不產生假命中率或假檢討；不得產生假命中率。</p>'
        return note + '<div class="source-grid">' + ''.join(cards) + '</div>'
    rows = []
    rows.append('<div class="source-item"><h3>單日檢討</h3><p>資料待接</p><p>尚未找到正式盤後檢討 runtime artifact。</p><span class="badge warn">盤後檢討資料待接</span></div>')
    rows.append('<div class="source-item"><h3>7 天滾動檢討</h3><p>7 天滾動檢討：資料不足，需累積更多正式 prediction / actual outcome artifact。</p><span class="badge warn">資料不足</span></div>')
    return '<div class="source-grid">' + ''.join(rows) + '</div>'

def freshness_cards(runtime: dict[str, Any]) -> str:
    labels = [('07:00 盤前資料', 'partial', '盤前摘要可用；正式預測資料待接'), ('13:05 盤中資料', 'missing', '尚未找到正式盤中 runtime artifact'), ('13:35 收盤快照資料', 'missing', '尚未找到正式收盤快照 runtime artifact'), ('15:00 盤後檢討資料', 'missing', '目前僅找到盤前本機摘要，不能代表盤後檢討資料'), ('追蹤名單', 'watchlist_valid', '名單有效，預測資料另見下方'), ('正式預測資料', 'contract_backed' if runtime.get('formal_prediction_artifact') else 'missing', 'formal prediction artifact 已接線；deterministic_baseline_v1；null 欄位為資料待接' if runtime.get('formal_prediction_artifact') else '正式預測資料待接'), ('正式檢討資料', 'contract_backed' if runtime.get('formal_review_artifact') else 'missing', 'formal review artifact 已接線；null 欄位為資料待接' if runtime.get('formal_review_artifact') else '盤後檢討資料待接'), ('最新本機分析摘要', 'available', '盤前摘要可用於初步參考')]
    return '<div class="source-grid">' + ''.join('<div class="source-item"><h3>' + escape(n) + '</h3><p>' + escape(msg) + '</p><span class="badge ' + badge(st) + '">' + escape(msg.split('；')[0]) + '</span></div>' for n, st, msg in labels) + '</div>'

def stock_cards(runtime: dict[str, Any]) -> str:
    stocks = [s for s in runtime.get('stock_universe', []) if isinstance(s, dict) and s.get('stock_id')]
    per = [s for s in runtime.get('per_stock_summaries', []) if isinstance(s, dict) and s.get('stock_id')]
    by_id = {str(s.get('stock_id')): s for s in per}
    cards = []
    for s in stocks:
        detail = by_id.get(str(s.get('stock_id')), {})
        cards.append('<div class="source-item"><h3>' + escape(str(s.get('stock_id'))) + ' ' + escape(str(s.get('stock_name') or '')) + '</h3><p>追蹤名單有效，預測資料另見下方。</p><p>評等/動作：' + escape(str(detail.get('rating') or '資料待接')) + ' / ' + escape(str(detail.get('action') or '資料待接')) + '</p><p>分數：' + escape(str(detail.get('total_score') if detail.get('total_score') is not None else '資料待接')) + '</p><span class="badge safe">追蹤名單有效</span></div>')
    note = '<p class="preview-note">個股狀態摘要覆蓋 ' + str(len(per)) + ' / ' + str(len(stocks)) + ' 檔；其他個股待正式 report artifact 接線。</p>' if len(per) < len(stocks) else ''
    return note + '<div class="source-grid">' + (''.join(cards) if cards else '<div class="source-item"><h3>追蹤名單資料待接</h3></div>') + '</div>'

def latest_report_cards(runtime: dict[str, Any]) -> str:
    real = [r for r in runtime.get('latest_reports', []) if isinstance(r, dict) and r.get('report_window') == 'latest_local_analysis_results']
    out = []
    for r in real:
        out.append('<div class="source-item"><h3>最新本機分析摘要</h3><p>盤前摘要可用於初步參考，不代表正式預測資料已完成。</p><p>股票數：' + escape(str(r.get('stock_count') or '資料待接')) + '</p><span class="badge warn">部分資料可用</span></div>')
    out.append('<div class="source-item debug-only"><h3>Artifact inventory</h3><p>範例 artifact，不是正式最新報告；詳細清單保留在 Debug。</p></div>')
    return '<div class="source-grid">' + ''.join(out) + '</div>'

def window_cards(runtime: dict[str, Any]) -> str:
    pred_state = '每日股價預測：資料待接（formal prediction artifact 已接線；deterministic_baseline_v1；null 欄位為資料待接）' if runtime.get('formal_prediction_artifact') else '每日股價預測：資料待接'
    review_state = '盤後檢討：資料待接（formal review artifact 已接線；null 欄位為資料待接）' if runtime.get('formal_review_artifact') else '盤後檢討：資料待接'
    defs = [('07:00', '盤前預測 / Pre-open Forecast', '盤前摘要：可用', pred_state, '整體狀態：部分缺資料', 'partial'), ('13:05', '盤中追蹤 / Intraday Tracking', '盤中追蹤：資料待接', '尚未找到正式盤中 runtime artifact', '整體狀態：資料待接', 'missing'), ('13:35', '收盤快照 / Close Snapshot', '收盤快照：資料待接', '尚未找到正式收盤快照 runtime artifact', '完整檢討待 15:00', 'missing'), ('15:00', '盤後檢討 / Prediction Review', review_state, '7 天滾動檢討：資料待接', '目前僅找到盤前本機摘要，不能代表盤後檢討資料', 'partial' if runtime.get('formal_review_artifact') else 'missing')]
    return ''.join('<article class="card window-card"><div class="window-time">' + t + '</div><div class="window-title">' + escape(title) + '</div><p><strong>' + escape(a) + '</strong></p><p>' + escape(b) + '</p><p>' + escape(c) + '</p><p>' + ('Full prediction review：資料待接' if 'Prediction Review' in title else '') + '</p><span class="badge ' + badge(st) + '">' + ('部分缺資料' if st == 'partial' else '資料待接') + '</span></article>' for t, title, a, b, c, st in defs)

def render_route_html(artifact: dict[str, Any], preview_html: str) -> str:
    runtime = load_json(REPO_ROOT / RUNTIME_DATA) if (REPO_ROOT / RUNTIME_DATA).exists() else {}
    route_path = escape(str(artifact['route_path']))
    latest_ts = escape(str(runtime.get('latest_data_timestamp') or '資料待接'))
    stocks = [s for s in runtime.get('stock_universe', []) if isinstance(s, dict) and s.get('stock_id')]
    missing = len(runtime.get('missing_data', [])) if isinstance(runtime.get('missing_data'), list) else 0
    stale = len(runtime.get('stale_data', [])) if isinstance(runtime.get('stale_data'), list) else 0
    delivery_html = '<div class="source-grid"><div class="source-item"><h3>LINE</h3><p>本次僅做 read-only contract audit，未重送，也未驗證實際送達內容。</p></div><div class="source-item"><h3>Email</h3><p>本次僅做 read-only contract audit，未重送，也未驗證實際送達內容。</p></div><div class="source-item"><h3>Dashboard</h3><p>已發布並可驗證。</p></div></div>'
    style = ":root{--ink:#132227;--line:#d8e2e6;--ok:#e8f5ee;--warn:#fff7e5;--blue:#e9f3fb}*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f7f8;color:var(--ink);line-height:1.55}header{background:linear-gradient(135deg,#103640,#1d5a63);color:#fff;padding:26px 16px 22px}main{max-width:1120px;margin:0 auto;padding:16px}h1{font-size:clamp(28px,4vw,44px);margin:0 0 8px}h2{font-size:22px;margin:0 0 12px}h3{font-size:18px;margin:0 0 8px}p{margin:0 0 10px}.badge-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.badge{display:inline-flex;border-radius:999px;padding:6px 10px;background:#e9f3fb;color:#123b44;font-weight:700;font-size:14px;border:1px solid rgba(18,59,68,.18)}.badge.warn{background:var(--warn);color:#6e4d00}.badge.safe{background:var(--ok);color:#23533b}.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0;box-shadow:0 1px 0 rgba(14,39,46,.04)}.hero{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin-top:-12px;box-shadow:0 8px 24px rgba(14,39,46,.08)}.grid,.source-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.window-card{display:flex;flex-direction:column;gap:8px;min-height:230px}.window-time{font-size:28px;font-weight:800;color:#123b44}.window-title{font-size:24px;font-weight:800}.preview-note{background:var(--blue);border:1px solid #c8dcea;border-radius:10px;padding:12px;color:#244f64}.source-item{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fbfdfe}.review-block{border-top:1px solid var(--line);padding-top:10px;margin-top:10px}.review-block h4{margin:0 0 8px;font-size:16px;color:#123b44}details{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px;margin:14px 0}summary{font-weight:800;cursor:pointer}.debug-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.debug-list span{background:#f6f8f9;border:1px solid #e0e7ea;border-radius:8px;padding:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}@media (max-width:760px){main{padding:12px}.grid,.source-grid,.debug-list{grid-template-columns:1fr}.window-time{font-size:24px}.window-title{font-size:21px}.hero,.card{border-radius:10px;padding:14px}}"
    return '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>四時段 AI 決策儀表板</title><style>' + style + '</style></head><body><header><h1>四時段 AI 決策儀表板</h1><p>盤前、盤中、收盤快照、盤後檢討</p><div class="badge-row"><span class="badge warn">預覽版 / 尚未接正式即時資料</span><span class="badge warn">部分資料可用；正式預測與檢討資料待接</span><span class="badge">最新本機摘要：' + latest_ts + '</span><span class="badge safe">不通知、不下單、不改策略</span></div></header><main><section class="hero"><h2>今日決策摘要</h2><p>目前可用於初步參考：追蹤名單有效、盤前本機摘要可用；正式 formal prediction/review artifacts 已具備接線能力，但 null 欄位仍顯示資料待接。</p><p class="preview-note">目前為預覽資料，尚未接完整正式 runtime data；不可用於正式決策：尚未找到正式 prediction runtime artifact，不產生假預測；資料過期或缺漏會明確標示。不會觸發通知或下單。</p><div class="badge-row"><span class="badge safe">追蹤名單 ' + str(len(stocks)) + ' 檔有效</span><span class="badge warn">正式預測資料待接</span><span class="badge warn">盤後檢討資料待接</span><span class="badge warn">缺失區塊 ' + str(missing) + '</span><span class="badge warn">過期區塊 ' + str(stale) + '</span></div></section><section class="card"><h2>四個時段怎麼看</h2><div class="grid">' + window_cards(runtime) + '</div></section><section class="card"><h2>目前追蹤標的</h2>' + stock_cards(runtime) + '</section><section class="card"><h2>最新報告摘要</h2>' + latest_report_cards(runtime) + '</section><section class="card"><h2>每日股價預測資料狀態</h2><p>今日最高 / 最低價預測、隔天最高 / 最低價預測若為 null，代表資料待接；下方保留完整欄位名稱。</p>' + prediction_cards(runtime) + '</section><section class="card"><h2>Forecast Calibration / 回測校準狀態</h2>' + calibration_cards() + '</section><section class="card"><h2>Forecast Snapshot Accumulation / 預測樣本累積進度</h2>' + snapshot_accumulation_cards() + '</section><section class="card"><h2>實際結果 / 預測檢討狀態</h2>' + review_cards(runtime) + '</section><section class="card"><h2>資料新鮮度</h2>' + freshness_cards(runtime) + '</section><section class="card"><h2>資料可信度與證據來源 / 資料來源可信度</h2><div class="source-grid">' + source_cards(runtime.get('source_quality', [])) + '</div></section><section class="card"><h2>LINE / Email / Dashboard delivery audit summary</h2>' + delivery_html + '</section><details><summary>技術檢查 / Debug</summary><p>以下資訊保留給維運檢查，不是主要使用者閱讀區。Artifact inventory: 範例 artifact，不是正式最新報告。</p><div class="debug-list"><span>route=' + route_path + '</span><span>formal_prediction=' + escape(str(runtime.get('formal_prediction_artifact_ref') or 'missing')) + '</span><span>formal_review=' + escape(str(runtime.get('formal_review_artifact_ref') or 'missing')) + '</span><span>runtime export=' + escape(str(runtime.get('production_runtime_export_ref') or 'missing')) + '</span><span>runtime keys: pre_open_0700 / intraday_1305 / pre_close_1335 / post_close_1500</span><span>ui concept: close_snapshot_1335 / prediction_review_1500</span><span>raw fields: actual_high / hit_miss_status / factor_effectiveness</span><span>production_dashboard_publish_executed=false</span><span>no notification</span><span>no scheduler change</span><span>no DB write</span><span>no production pipeline</span><span>no trading</span><span>no rating/action/confidence/weight mutation</span></div></details></main></body></html>'

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
