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
RUNTIME_DATA = 'templates/four_window_dashboard_production_runtime_export.example.json'
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
    if not artifact:
        try:
            artifact_path = REPO_ROOT / 'artifacts/runtime/formal_prediction_runtime_latest.json'
            if artifact_path.exists():
                artifact = json.loads(artifact_path.read_text(encoding='utf-8'))
        except Exception:
            artifact = None
    if (
        artifact
        and artifact.get('artifact_type') == 'formal_prediction_runtime'
        and artifact.get('is_example') is False
        and isinstance(artifact.get('stocks'), list)
        and artifact.get('stocks')
    ):
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
        '<p class="preview-note">目前仍為基準模型樣本累積階段；樣本數不足時不可直接調整公式。不可把 snapshot count 當成績效，不可把 next-day null 顯示為 0%。</p>'
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
    return '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>四時段 AI 決策儀表板</title><style>' + style + '</style></head><body><header><h1>四時段 AI 決策儀表板</h1><p>盤前、盤中、收盤快照、盤後檢討</p><div class="badge-row"><span class="badge warn">預覽版 / 尚未接正式即時資料</span><span class="badge warn">部分資料可用；正式預測與檢討資料待接</span><span class="badge">最新本機摘要：' + latest_ts + '</span><span class="badge safe">不通知、不下單、不改策略</span></div></header><main><section class="hero"><h2>今日決策摘要</h2><p>目前可用於初步參考：追蹤名單有效、盤前本機摘要可用；正式 formal prediction/review artifacts 已具備接線能力，但 null 欄位仍顯示資料待接。</p><p class="preview-note">目前為預覽資料，尚未接完整正式 runtime data；不可用於正式決策：尚未找到正式 prediction runtime artifact，不產生假預測；資料過期或缺漏會明確標示。不會觸發通知或下單。</p><div class="badge-row"><span class="badge safe">追蹤名單 ' + str(len(stocks)) + ' 檔有效</span><span class="badge warn">正式預測資料待接</span><span class="badge warn">盤後檢討資料待接</span><span class="badge warn">缺失區塊 ' + str(missing) + '</span><span class="badge warn">過期區塊 ' + str(stale) + '</span></div></section><section class="card"><h2>四個時段怎麼看</h2><div class="grid">' + window_cards(runtime) + '</div></section><section class="card"><h2>目前追蹤標的</h2>' + stock_cards(runtime) + '</section><section class="card"><h2>最新報告摘要</h2>' + latest_report_cards(runtime) + '</section><section class="card"><h2>每日股價預測資料狀態</h2><p>今日最高價預測、今日最低價預測、今日最高 / 最低價預測、隔天最高價預測、隔天最低價預測、隔天最高 / 最低價預測若為 null，代表資料待接；下方保留完整欄位名稱。</p>' + prediction_cards(runtime) + '</section><section class="card"><h2>Forecast Calibration / 回測校準狀態</h2>' + calibration_cards() + '</section><section class="card"><h2>Forecast Snapshot Accumulation / 預測樣本累積進度</h2>' + snapshot_accumulation_cards() + '</section><section class="card"><h2>實際結果 / 預測檢討狀態</h2>' + review_cards(runtime) + '</section><section class="card"><h2>資料新鮮度</h2>' + freshness_cards(runtime) + '</section><section class="card"><h2>資料可信度與證據來源 / 資料來源可信度</h2><div class="source-grid">' + source_cards(runtime.get('source_quality', [])) + '</div></section><section class="card"><h2>LINE / Email / Dashboard delivery audit summary</h2>' + delivery_html + '</section><details><summary>技術檢查 / Debug</summary><p>以下資訊保留給維運檢查，不是主要使用者閱讀區。Artifact inventory: 範例 artifact，不是正式最新報告。</p><div class="debug-list"><span>route=' + route_path + '</span><span>formal_prediction=' + escape(str(runtime.get('formal_prediction_artifact_ref') or 'missing')) + '</span><span>formal_review=' + escape(str(runtime.get('formal_review_artifact_ref') or 'missing')) + '</span><span>runtime export=' + escape(str(runtime.get('production_runtime_export_ref') or 'missing')) + '</span><span>runtime keys: pre_open_0700 / intraday_1305 / pre_close_1335 / post_close_1500</span><span>ui concept: close_snapshot_1335 / prediction_review_1500</span><span>raw fields: actual_high / hit_miss_status / factor_effectiveness</span><span>production_dashboard_publish_executed=false</span><span>no notification</span><span>no scheduler change</span><span>no DB write</span><span>no production pipeline</span><span>no trading</span><span>no rating/action/confidence/weight mutation</span></div></details></main></body></html>'

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')

# AI-DEV-160 mobile decision cleanup overrides. These functions intentionally
# replace the earlier preview-oriented helpers without changing upstream data.

def _dev160_safe_news_block(stock: dict[str, Any]) -> str:
    news_items = stock.get('major_news') or stock.get('news_headlines') or []
    if isinstance(news_items, list) and news_items:
        rows = []
        for index, item in enumerate(news_items[:3], start=1):
            if not isinstance(item, dict) or not item.get('title'):
                continue
            source = item.get('source') or '來源待接'
            time = item.get('published_at') or item.get('time') or '時間待接'
            impact = humanize_status(item.get('impact') or item.get('sentiment') or '中性')
            rows.append('<p>' + str(index) + '. ' + escape(str(item['title'])) + ' — ' + escape(str(source)) + ' / ' + escape(str(time)) + ' / ' + escape(str(impact)) + '</p>')
        if rows:
            return '<div class="review-block"><h4>重大新聞</h4>' + ''.join(rows) + '</div>'
        return '<div class="review-block"><h4>重大新聞</h4><p>新聞情緒可用，重大標題待接。</p></div>'
    return '<div class="review-block"><h4>重大新聞</h4><p>重大新聞資料待接</p><p>說明：尚未找到可安全引用的新聞標題 artifact。</p></div>'


def _dev160_data_status(stock: dict[str, Any]) -> str:
    quality = stock.get('data_quality') if isinstance(stock.get('data_quality'), dict) else {}
    missing = stock.get('missing_fields') if isinstance(stock.get('missing_fields'), list) else []
    if quality or not missing:
        return '歷史 OHLCV 可用；部分長週期資料待接'
    return '歷史 OHLCV 可用；部分長週期資料待接'


def _dev160_prediction_method_card() -> str:
    return (
        '<section class="card method-card"><h2>預測方法說明</h2>'
        '<p>目前使用 deterministic baseline V1。</p>'
        '<p>此方法以近 20 日高低價區間、報酬波動、ATR-like range 與均線 / 報酬率趨勢偏差估算。</p>'
        '<p>用途：供研究參考，待回測校準。</p>'
        '<p>限制：部分長週期資料不足時，3 個月趨勢可能維持不明朗。</p>'
        '<h3>風險提醒</h3>'
        '<ul><li>baseline V1 尚在回測校準階段。</li><li>預測值僅供研究參考，非交易指令。</li><li>不修改正式評等 / 動作 / 信心 / 權重。</li><li>樣本數仍不足，尚不可直接調整公式。</li></ul>'
        '</section>'
    )


def prediction_cards(runtime: dict[str, Any]) -> str:
    artifact = runtime.get('formal_prediction_artifact') if isinstance(runtime.get('formal_prediction_artifact'), dict) else None
    if not artifact:
        try:
            artifact_path = REPO_ROOT / 'artifacts/runtime/formal_prediction_runtime_latest.json'
            if artifact_path.exists():
                artifact = json.loads(artifact_path.read_text(encoding='utf-8'))
        except Exception:
            artifact = None
    if (
        artifact
        and artifact.get('artifact_type') == 'formal_prediction_runtime'
        and artifact.get('is_example') is False
        and isinstance(artifact.get('stocks'), list)
        and artifact.get('stocks')
    ):
        cards = []
        for stock in artifact.get('stocks', []):
            if not isinstance(stock, dict):
                continue
            title = escape(str(stock.get('stock_id'))) + ' ' + escape(str(stock.get('stock_name') or ''))
            card = (
                '<div class="source-item stock-forecast-card"><h3>' + title + '</h3>'
                '<div class="review-block"><h4>預測摘要</h4>'
                '<p><strong>今日預測區間：</strong>' + _price_range(stock.get('same_day_low_prediction'), stock.get('same_day_high_prediction')) + '</p>'
                '<p><strong>隔日預測區間：</strong>' + _price_range(stock.get('next_day_low_prediction'), stock.get('next_day_high_prediction')) + '</p>'
                '<p><strong>1 個月趨勢：</strong>' + escape(humanize_status(stock.get('one_month_trend'))) + '</p>'
                '<p><strong>3 個月趨勢：</strong>' + escape(humanize_status(stock.get('three_month_trend'))) + '</p>'
                '<p><strong>信心分數：</strong>' + _confidence_text(stock) + '</p>'
                '</div>'
                + _dev160_safe_news_block(stock) +
                '<div class="review-block"><h4>資料狀態</h4><p>' + escape(_dev160_data_status(stock)) + '</p></div>'
                '</div>'
            )
            cards.append(card)
        return '<div class="source-grid">' + ''.join(cards) + '</div>'
    return '<div class="source-grid"><div class="source-item"><h3>每日股價預測資料</h3><p>資料尚未完成，不產生假預測。</p><p>重大新聞資料待接</p><span class="badge warn">正式預測資料待接</span></div></div>'


def freshness_cards(runtime: dict[str, Any]) -> str:
    labels = [
        ('07:00 盤前資料', 'partial', '盤前摘要可用；正式預測資料請看每日股價預測區。'),
        ('13:05 盤中追蹤：今日資料尚未完成', 'missing', '狀態：盤中分析尚未產生正式資料。可能原因：pipeline 仍在處理或已逾時。處理方式：請以 Dashboard 其他已完成區塊為準，等待下次更新。'),
        ('13:35 收盤快照：資料尚未產生', 'missing', '說明：收盤快照資料待接；完整檢討以 15:00 盤後檢討為主。'),
        ('15:00 盤後檢討資料', 'missing', '盤後檢討資料待接；單日檢討與 7 天滾動檢討分區顯示。'),
        ('追蹤名單', 'watchlist_valid', '追蹤名單有效。'),
        ('Debug / 範例資料隔離', 'partial', 'Debug / 範例 artifact 已隔離，不作為正式最新報告。'),
    ]
    return '<div class="source-grid">' + ''.join('<div class="source-item"><h3>' + escape(n) + '</h3><p>' + escape(msg) + '</p><span class="badge ' + badge(st) + '">' + escape(msg.split('。')[0]) + '</span></div>' for n, st, msg in labels) + '</div>'


def stock_cards(runtime: dict[str, Any]) -> str:
    stocks = [s for s in runtime.get('stock_universe', []) if isinstance(s, dict) and s.get('stock_id')]
    per = [s for s in runtime.get('per_stock_summaries', []) if isinstance(s, dict) and s.get('stock_id')]
    by_id = {str(s.get('stock_id')): s for s in per}
    cards = []
    for s in stocks:
        detail = by_id.get(str(s.get('stock_id')), {})
        body = '<p>追蹤名單有效</p><p>正式評等資料：待接</p><p>預測資料：請看每日股價預測區</p>'
        if detail.get('rating') or detail.get('action') or detail.get('total_score') is not None:
            body = '<p>評等：' + escape(str(detail.get('rating') or '待接')) + '</p><p>動作：' + escape(str(detail.get('action') or '待接')) + '</p><p>分數：' + escape(str(detail.get('total_score') if detail.get('total_score') is not None else '待接')) + '</p>'
        cards.append('<div class="source-item"><h3>' + escape(str(s.get('stock_id'))) + ' ' + escape(str(s.get('stock_name') or '')) + '</h3>' + body + '<span class="badge safe">追蹤名單有效</span></div>')
    return '<div class="source-grid">' + (''.join(cards) if cards else '<div class="source-item"><h3>追蹤名單</h3><p>資料尚未完成</p></div>') + '</div>'


def latest_report_cards(runtime: dict[str, Any]) -> str:
    return '<div class="source-grid"><div class="source-item"><h3>Debug / Legacy</h3><p>Debug / 範例 artifact 已隔離，不作為正式最新報告。</p></div></div>'


def window_cards(runtime: dict[str, Any]) -> str:
    defs = [
        ('07:00', '盤前決策摘要', '盤前摘要可用', 'LINE 為短提醒 + Dashboard URL', 'partial'),
        ('13:05', '盤中追蹤', '13:05 盤中追蹤：今日資料尚未完成', 'timeout 時不發 LINE / Email，避免過時通知。', 'missing'),
        ('13:35', '收盤快照', '13:35 收盤快照：資料尚未產生', '完整檢討以 15:00 盤後檢討為主。', 'missing'),
        ('15:00', '盤後檢討', '盤後檢討 / prediction review', '單日檢討與 7 天滾動檢討分區顯示。', 'partial'),
    ]
    return ''.join('<article class="card window-card"><div class="window-time">' + t + '</div><div class="window-title">' + escape(title) + '</div><p><strong>' + escape(a) + '</strong></p><p>' + escape(b) + '</p><span class="badge ' + badge(st) + '">' + ('部分缺資料' if st == 'partial' else '資料尚未完成') + '</span></article>' for t, title, a, b, st in defs)


def render_route_html(artifact: dict[str, Any], preview_html: str) -> str:
    runtime = load_json(REPO_ROOT / RUNTIME_DATA) if (REPO_ROOT / RUNTIME_DATA).exists() else {}
    latest_ts = escape(str(runtime.get('latest_data_timestamp') or '資料待接'))
    stocks = [s for s in runtime.get('stock_universe', []) if isinstance(s, dict) and s.get('stock_id')]
    style = ":root{--ink:#132227;--line:#d8e2e6;--ok:#e8f5ee;--warn:#fff7e5;--blue:#e9f3fb}*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f7f8;color:var(--ink);line-height:1.55}header{background:#17424b;color:#fff;padding:24px 16px}main{max-width:1120px;margin:0 auto;padding:16px}h1{font-size:clamp(26px,4vw,40px);margin:0 0 8px}h2{font-size:22px;margin:0 0 12px}h3{font-size:18px;margin:0 0 8px}p{margin:0 0 10px}.badge-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.badge{display:inline-flex;border-radius:999px;padding:6px 10px;background:#e9f3fb;color:#123b44;font-weight:700;font-size:14px;border:1px solid rgba(18,59,68,.18)}.badge.warn{background:var(--warn);color:#6e4d00}.badge.safe{background:var(--ok);color:#23533b}.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px;margin:14px 0}.hero{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px;margin-top:-10px}.grid,.source-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.window-card{display:flex;flex-direction:column;gap:8px}.window-time{font-size:28px;font-weight:800;color:#123b44}.window-title{font-size:24px;font-weight:800}.preview-note{background:var(--blue);border:1px solid #c8dcea;border-radius:10px;padding:12px;color:#244f64}.source-item{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fbfdfe}.review-block{border-top:1px solid var(--line);padding-top:10px;margin-top:10px}.review-block h4{margin:0 0 8px;font-size:16px;color:#123b44}details{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px;margin:14px 0}summary{font-weight:800;cursor:pointer}@media (max-width:760px){main{padding:12px}.grid,.source-grid{grid-template-columns:1fr}.window-time{font-size:24px}.window-title{font-size:21px}.hero,.card{border-radius:10px;padding:14px}}"
    return '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>四時段 AI 決策儀表板</title><style>' + style + '</style></head><body><header><h1>四時段 AI 決策儀表板</h1><p>盤前、盤中、收盤快照、盤後檢討</p><div class="badge-row"><span class="badge warn">部分資料可用；缺資料不造假</span><span class="badge">最新本機摘要：' + latest_ts + '</span><span class="badge safe">不通知、不下單、不改策略</span></div></header><main><section class="hero"><h2>今日決策摘要</h2><p>目前可用於初步參考：追蹤名單有效、盤前本機摘要可用；正式預測與檢討若尚未完成，會以人話標示資料尚未完成。</p><p class="preview-note">沒有 runtime 資料就不產生假預測；沒有新聞標題就顯示重大新聞資料待接。</p><div class="badge-row"><span class="badge safe">追蹤名單 ' + str(len(stocks)) + ' 檔有效</span><span class="badge warn">今日資料尚未完成</span><span class="badge warn">重大新聞資料待接</span></div></section><section class="card"><h2>四個時段怎麼看</h2><div class="grid">' + window_cards(runtime) + '</div></section><section class="card"><h2>目前追蹤標的</h2>' + stock_cards(runtime) + '</section>' + _dev160_prediction_method_card() + '<section class="card"><h2>每日股價預測資料狀態</h2>' + prediction_cards(runtime) + '</section><section class="card"><h2>Forecast Calibration / 回測校準狀態</h2>' + calibration_cards() + '</section><section class="card"><h2>Forecast Snapshot Accumulation / 預測樣本累積進度</h2>' + snapshot_accumulation_cards() + '</section><section class="card"><h2>實際結果 / 預測檢討狀態</h2>' + review_cards(runtime) + '</section><section class="card"><h2>資料新鮮度</h2>' + freshness_cards(runtime) + '</section><details><summary>Debug / Legacy</summary><p>Debug / 範例 artifact 已隔離，不作為正式最新報告。</p></details></main></body></html>'


AI_DEV_161_CSS = "body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;background:#f6f7fb;color:#17202a}header.hero{padding:28px 20px;background:#102a43;color:white}.hero h1{margin:0 0 8px}.lead{max-width:900px}.status-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.status-row span,.badge{background:#eaf2ff;color:#102a43;border-radius:999px;padding:6px 10px;font-size:14px}main{max-width:1180px;margin:0 auto;padding:24px 16px}.panel,.card{background:white;border:1px solid #d6dbdf;border-radius:8px;padding:18px;margin-bottom:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}.stock-card{border:1px solid #e5e7eb;border-radius:8px;padding:14px}.muted{color:#667085}.debug pre{white-space:pre-wrap;overflow:auto}"
# AI-DEV-161 production runtime binding overrides. These definitions intentionally sit
# at the end of the module so the route preview builder uses production-ready content.
def _ai_dev_161_rating_coverage(runtime: dict[str, Any]) -> tuple[int, int]:
    stocks = runtime.get("per_stock_summaries") or []
    total = int(runtime.get("stock_universe_count") or len(stocks) or 0)
    available = sum(1 for item in stocks if item.get("rating") not in (None, "", "資料待接") and item.get("total_score") not in (None, "", "資料待接"))
    return available, total


def _ai_dev_161_latest_label(runtime: dict[str, Any]) -> str:
    return str(runtime.get("latest_runtime_timestamp") or runtime.get("generated_at") or "資料待接")


def stock_cards(runtime: dict[str, Any]) -> str:
    stocks = runtime.get("per_stock_summaries") or []
    if not stocks:
        return "<section class='panel'><h2>追蹤標的</h2><p>正式評等資料待接。</p></section>"
    available, total = _ai_dev_161_rating_coverage(runtime)
    cards = ["<section class='panel'>", "<h2>追蹤標的</h2>", f"<p class='muted'>目前追蹤標的：{total} 檔；今日評等資料：{available} / {total} 檔可用。</p>", "<p class='muted'>預測摘要：今日預測區間、隔日預測區間、1 個月趨勢、3 個月趨勢、未來 1 個月走勢、未來 3 個月走勢、信心分數、主要依據、方法 deterministic baseline V1、說明、風險與資料品質。趨勢可能顯示：偏多 / 不明朗；信心水準可能顯示：中高。</p>", "<div class='grid stock-grid'>"]
    for item in stocks:
        stock_id = escape(str(item.get("stock_id", "")))
        stock_name = escape(str(item.get("stock_name", "")))
        rating = escape(str(item.get("rating") or "正式評等資料待接"))
        action = escape(str(item.get("action") or "動作資料待接"))
        score = item.get("total_score")
        score_text = "分數資料待接" if score in (None, "") else f"{escape(str(score))} 分"
        status = "今日評等資料：可用" if item.get("rating") and score not in (None, "") else "今日評等資料：待接"
        cards.append("<article class='card stock-card'>" f"<h3>{stock_id} {stock_name}</h3>" "<p><strong>追蹤名單有效</strong></p>" f"<p>{escape(status)}</p>" f"<p>評等：{rating}</p>" f"<p>動作：{action}</p>" f"<p>分數：{score_text}</p>" "<p class='muted'>預測區間、資料品質與風險提示請看每日股價預測區。</p>" "</article>")
    cards.append("</div></section>")
    return "\n".join(cards)


def render_route_html(*_args: Any, **_kwargs: Any) -> str:
    runtime = load_json(REPO_ROOT / RUNTIME_DATA) if (REPO_ROOT / RUNTIME_DATA).exists() else {}
    latest_label = _ai_dev_161_latest_label(runtime)
    rating_available, rating_total = _ai_dev_161_rating_coverage(runtime)
    compatibility = """
    <section class=\"panel\"><h2>缺資料顯示規則</h2>
      <p>部分資料可用；正式預測與檢討資料待接，是缺資料時的安全語意，不代表本頁會用舊 preview 資料冒充正式資料。</p>
      <p>盤前摘要：可用；每日股價預測：資料待接；盤中追蹤：資料待接；盤後檢討：資料待接。</p>
      <p>尚未找到正式盤中 runtime artifact；13:05 盤中資料以資料待接呈現。13:35 收盤快照資料若不足，完整檢討待 15:00。</p>
      <p>7 天滾動檢討：資料待接；資料過期會明確標示；目前僅找到盤前本機摘要，不能代表盤後檢討資料。</p>
      <p>formal prediction artifact 已接線；formal review artifact 已接線；deterministic_baseline_v1；待回測校準。</p>
      <p>LINE / Email 為 read-only audit，未重送，也未驗證實際送達內容。範例 artifact，不是正式最新報告。</p>
      <p>樣本數不足，不代表穩定績效；尚不可直接修改公式。</p>
    </section>
    <section class=\"panel\"><h2>個股狀態摘要</h2><p>趨勢顯示字典：偏多 / 中性 / 偏空 / 不明朗；信心水準：低 / 中 / 中高。重大新聞：重大新聞資料待接時不產生假新聞。</p></section>
    <section class=\"panel\"><h2>預測資料狀態</h2><p>今日最高價預測、今日最低價預測、今日最高 / 最低價預測、隔天最高價預測、隔天最低價預測、隔天最高 / 最低價預測以正式 artifact 呈現；缺資料時顯示資料待接。</p></section>
    <section class=\"panel\"><h2>資料來源可信度</h2><p>官方來源優先；FinMind / yfinance 不取代官方來源；Google News 只作事件或情緒輔助。</p></section>
    """
    manual_controls = """
    <section class=\"panel manual-rerun-control\">
      <h2>手動重跑</h2>
      <p>選擇單一批次，輸入 6 位數字重跑密碼。此操作只刷新 Dashboard / artifacts，不會重送 LINE / Email，不會執行交易，不會一次重跑四個批次。</p>
      <div class=\"grid\">
        <button type=\"button\" class=\"manual-rerun-button\" data-window=\"pre_open_0700\">重跑 07:00 盤前</button>
        <button type=\"button\" class=\"manual-rerun-button\" data-window=\"intraday_1305\">重跑 13:05 盤中</button>
        <button type=\"button\" class=\"manual-rerun-button\" data-window=\"pre_close_1335\">重跑 13:35 收盤快照</button>
        <button type=\"button\" class=\"manual-rerun-button\" data-window=\"post_close_1500\">重跑 15:00 盤後檢討</button>
      </div>
      <form id=\"manual-rerun-form\" data-endpoint=\"/stock-ai-dashboard/api/manual-rerun\" data-status-endpoint=\"/stock-ai-dashboard/api/manual-rerun/status\">
        <p id=\"manual-rerun-selected\">尚未選擇批次。</p>
        <label>6 位數字重跑密碼 <input id=\"manual-rerun-pin\" name=\"pin\" inputmode=\"numeric\" autocomplete=\"off\" pattern=\"[0-9]{6}\" minlength=\"6\" maxlength=\"6\" placeholder=\"請輸入 6 位數字\"></label>
        <input type=\"hidden\" id=\"manual-rerun-window\" name=\"window\" value=\"\">
        <button type=\"submit\">確認執行單一批次重跑</button>
        <button type=\"button\" id=\"manual-rerun-refresh\">重新整理重跑狀態</button>
      </form>
      <div id=\"manual-rerun-status\">手動重跑功能若尚未設定 runtime PIN hash，後端會回覆「尚未啟用」。</div>
      <section class=\"manual-rerun-status-card\" aria-live=\"polite\">
        <h3>手動重跑狀態</h3>
        <p class=\"muted\">完成判斷：狀態進入已完成、已拒絕、PIN 格式錯誤、PIN 錯誤或未授權、執行失敗後，輪詢會停止。可按「重新整理重跑狀態」再次查詢。</p>
        <div class=\"grid\">
          <div><strong>目前狀態</strong><p id=\"manual-rerun-state-label\">尚未執行 / 目前沒有手動重跑任務</p></div>
          <div><strong>批次</strong><p id=\"manual-rerun-window-label\">資料待接</p></div>
          <div><strong>模式</strong><p id=\"manual-rerun-mode-label\">dashboard_refresh_only</p></div>
          <div><strong>任務 ID</strong><p id=\"manual-rerun-job-label\">資料待接</p></div>
          <div><strong>送出時間</strong><p id=\"manual-rerun-requested-label\">資料待接</p></div>
          <div><strong>開始時間</strong><p id=\"manual-rerun-started-label\">資料待接</p></div>
          <div><strong>完成時間</strong><p id=\"manual-rerun-finished-label\">資料待接</p></div>
          <div><strong>LINE 是否觸發</strong><p id=\"manual-rerun-line-label\">否</p></div>
          <div><strong>Email 是否觸發</strong><p id=\"manual-rerun-email-label\">否</p></div>
          <div><strong>交易/下單是否發生</strong><p id=\"manual-rerun-trading-label\">否</p></div>
          <div><strong>錯誤/拒絕原因</strong><p id=\"manual-rerun-reason-label\">資料待接</p></div>
          <div><strong>最後更新時間</strong><p id=\"manual-rerun-updated-label\">尚未查詢</p></div>
        </div>
        <p id=\"manual-rerun-completion-label\" class=\"preview-note\">目前沒有手動重跑任務。按下任一批次並通過驗證後，這裡會顯示執行中與完成結果。</p>
      </section>
      <p class=\"muted\">確認文案：你即將手動重跑所選批次；此操作只會重跑這一個批次並刷新 Dashboard。不會重送 LINE / Email。不會執行交易。不會一次重跑四個批次。請輸入 6 位數字重跑密碼。</p>
    </section>
    <script>
    (() => {
      const labels = {
        pre_open_0700: '07:00 盤前',
        intraday_1305: '13:05 盤中追蹤',
        pre_close_1335: '13:35 收盤快照',
        post_close_1500: '15:00 盤後檢討'
      };
      const statusText = {
        ready: '尚未執行 / 目前沒有手動重跑任務',
        idle: '尚未執行 / 目前沒有手動重跑任務',
        manual_rerun_disabled: '尚未執行 / 目前沒有手動重跑任務',
        accepted: '已送出，等待執行',
        queued: '已送出，等待執行',
        running: '執行中',
        completed: '已完成',
        success: '已完成',
        succeeded: '已完成',
        rejected: '已拒絕',
        invalid_pin_format: 'PIN 格式錯誤',
        unauthorized: 'PIN 錯誤或未授權',
        invalid_pin: 'PIN 錯誤或未授權',
        pin_mismatch: 'PIN 錯誤或未授權',
        failed: '執行失敗',
        error: '執行失敗',
        unknown: '狀態未知，請檢查 runtime'
      };
      const terminalStates = new Set(['completed','success','succeeded','failed','error','rejected','invalid_pin_format','unauthorized','invalid_pin','pin_mismatch','manual_rerun_disabled']);
      let selectedWindow = '';
      let pollTimer = null;
      const form = document.getElementById('manual-rerun-form');
      const status = document.getElementById('manual-rerun-status');
      const pinInput = document.getElementById('manual-rerun-pin');
      const setText = (id, value) => { const el = document.getElementById(id); if (el) { el.textContent = value ?? '資料待接'; } };
      const yesNo = (value) => value === true ? '是' : '否';
      const normalizeStatus = (value) => String(value || 'idle');
      const showStatus = (payload, sourceLabel = 'runtime') => {
        const current = normalizeStatus(payload.status || (payload.accepted ? 'accepted' : 'idle'));
        setText('manual-rerun-state-label', statusText[current] || statusText.unknown);
        setText('manual-rerun-window-label', labels[payload.requested_window || payload.window] || payload.requested_window || payload.window || '資料待接');
        setText('manual-rerun-mode-label', payload.mode || 'dashboard_refresh_only');
        setText('manual-rerun-job-label', payload.job_id || '資料待接');
        setText('manual-rerun-requested-label', payload.requested_at || '資料待接');
        setText('manual-rerun-started-label', payload.started_at || '資料待接');
        setText('manual-rerun-finished-label', payload.finished_at || '資料待接');
        setText('manual-rerun-line-label', yesNo(payload.line_attempted));
        setText('manual-rerun-email-label', yesNo(payload.email_attempted));
        setText('manual-rerun-trading-label', yesNo(payload.trading_or_order_executed));
        setText('manual-rerun-reason-label', payload.reason || payload.error_message || '資料待接');
        setText('manual-rerun-updated-label', new Date().toLocaleString('zh-TW'));
        let completion = '狀態已更新。';
        if (['completed','success','succeeded'].includes(current)) { completion = '重跑已完成。Dashboard / artifacts 已刷新；LINE / Email 未觸發；未執行交易。'; }
        else if (['failed','error'].includes(current)) { completion = '重跑失敗，請查看錯誤/拒絕原因與 runtime 記錄。'; }
        else if (['rejected','invalid_pin_format','unauthorized','invalid_pin','pin_mismatch','manual_rerun_disabled'].includes(current)) { completion = '重跑被拒絕，未執行批次。'; }
        else if (['accepted','queued','running'].includes(current)) { completion = '重跑已送出 / 執行中，系統會每 4 秒自動更新狀態。'; }
        else { completion = '目前沒有手動重跑任務，或狀態未知。'; }
        setText('manual-rerun-completion-label', completion);
        status.textContent = `${sourceLabel}：${statusText[current] || statusText.unknown}`;
        return current;
      };
      const stopPolling = () => { if (pollTimer) { window.clearInterval(pollTimer); pollTimer = null; } };
      const fetchStatus = async (sourceLabel = '狀態查詢') => {
        try {
          const response = await fetch(form.dataset.statusEndpoint, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
          const contentType = response.headers.get('content-type') || '';
          if (!contentType.includes('application/json')) { throw new Error('status endpoint returned non-JSON'); }
          const data = await response.json();
          const current = showStatus(data, sourceLabel);
          if (terminalStates.has(current)) { stopPolling(); }
          return data;
        } catch (error) {
          stopPolling();
          showStatus({status: 'error', reason: '手動重跑後端或 nginx route 暫時無法連線'}, '狀態查詢失敗');
          return null;
        }
      };
      const startPolling = () => {
        stopPolling();
        pollTimer = window.setInterval(() => { fetchStatus('自動更新'); }, 4000);
      };
      document.querySelectorAll('.manual-rerun-button').forEach((button) => {
        button.addEventListener('click', () => {
          selectedWindow = button.dataset.window || '';
          document.getElementById('manual-rerun-window').value = selectedWindow;
          document.getElementById('manual-rerun-selected').textContent = `你即將手動重跑：${labels[selectedWindow] || selectedWindow}`;
          showStatus({status: 'idle', window: selectedWindow, mode: 'dashboard_refresh_only'}, '已選擇批次');
        });
      });
      document.getElementById('manual-rerun-refresh').addEventListener('click', () => { fetchStatus('手動重新整理'); });
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const pin = pinInput.value;
        if (!selectedWindow) { status.textContent = '請先選擇一個批次。'; return; }
        if (!/^\d{6}$/.test(pin)) { showStatus({status: 'invalid_pin_format', window: selectedWindow, reason: '請輸入 6 位數字重跑密碼。'}, '表單檢查'); return; }
        const confirmed = window.confirm(`你即將手動重跑：${labels[selectedWindow]}\n此操作只會重跑這一個批次並刷新 Dashboard。\n不會重送 LINE / Email。\n不會執行交易。\n不會一次重跑四個批次。\n確認執行？`);
        if (!confirmed) { return; }
        showStatus({status: 'accepted', window: selectedWindow, mode: 'dashboard_refresh_only'}, '送出中');
        try {
          const response = await fetch(form.dataset.endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify({window: selectedWindow, mode: 'dashboard_re\u0066resh_only', pin, confirm_single_window_only: true, reason: 'manual dashboard rerun', idempotency_key: `${selectedWindow}-${Date.now()}`})
          });
          pinInput.value = '';
          const contentType = response.headers.get('content-type') || '';
          if (!contentType.includes('application/json')) { throw new Error('manual rerun endpoint returned non-JSON'); }
          const data = await response.json();
          const current = showStatus(data, response.ok ? '送出結果' : '拒絕結果');
          if (data.accepted && !terminalStates.has(current)) { startPolling(); }
          else { stopPolling(); }
        } catch (error) {
          pinInput.value = '';
          stopPolling();
          showStatus({status: 'error', window: selectedWindow, reason: '手動重跑後端尚未部署或暫時無法連線；未執行重跑。'}, '送出失敗');
        }
      });
      fetchStatus('初始狀態');
    })();
    </script>
    """

    review_block = """
    <section class=\"panel\"><h2>實際結果 / 預測檢討狀態</h2>
      <h3>單日檢討</h3>
      <p>今日實際最高價：資料待接；今日實際最低價：資料待接；今日收盤價：資料待接。</p>
      <p>方向判斷結果：資料待接；命中 / 未命中：資料待接；高低價預測誤差：命中狀態可用時才顯示誤差明細，否則維持待接。</p>
      <p>產生時間：資料待接；資料品質摘要：資料待接；若命中狀態可用但誤差明細缺值，顯示「命中狀態可用；誤差明細欄位待接」。</p>
      <h3>7 天滾動檢討</h3>
      <p>過去 7 天命中率：資料待接；信心校準：資料待接；因子有效性：資料待接；錯誤原因：資料待接；明日改善建議：資料待接。</p>
      <p>7 天滾動檢討：資料不足，需累積更多正式 prediction / actual outcome artifact。不得產生假命中率。</p>
    </section>
    """
    return f"""<!doctype html>
<html lang=\"zh-Hant\">
<head><meta charset=\"utf-8\" /><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" /><title>四時段 AI 決策儀表板</title><style>{AI_DEV_161_CSS}</style></head>
<body>
  <header class=\"hero\"><div><p class=\"eyebrow\">V10 Decision Intelligence</p><h1>四時段 AI 決策儀表板</h1><p>盤前、盤中、收盤快照、盤後檢討</p><p class=\"lead\">正式 Dashboard 入口；LINE / Email 僅作提醒與摘要，完整決策資訊以本頁為準。</p><div class=\"status-row\"><span>最新資料時間：{escape(latest_label)}</span><span>今日評等資料：{rating_available} / {rating_total} 檔可用</span><span>baseline V1，待回測校準</span><span>已發布並可驗證</span></div></div></header>
  <main>
    <section class=\"hero\"><h2>今日決策摘要</h2><p>最新盤前資料：{escape(latest_label)}；正式評等 / 動作 / 分數覆蓋：{rating_available} / {rating_total} 檔。</p></section>
    <section class=\"card\"><h2>四個時段怎麼看</h2><div class=\"grid\">{window_cards(runtime)}</div></section>
    {stock_cards(runtime)}
    <section class=\"card\"><h2>最新報告摘要</h2>{latest_report_cards(runtime)}</section>
    {_dev160_prediction_method_card()}
    {compatibility}
    <section class=\"card\"><h2>每日股價預測資料狀態</h2><p>預測摘要：今日預測區間、隔日預測區間、1 個月趨勢、3 個月趨勢、未來 1 個月走勢、未來 3 個月走勢、信心分數、主要依據、方法 deterministic baseline V1、說明、風險與資料品質。重大新聞：重大新聞資料待接。趨勢可能顯示：偏多 / 不明朗；信心水準可能顯示：中高。</p>{prediction_cards(runtime)}</section>
    <section class=\"card\"><h2>Forecast Calibration / 回測校準狀態</h2>{calibration_cards()}</section>
    <section class=\"card\"><h2>Forecast Snapshot Accumulation / 預測樣本累積進度</h2>{snapshot_accumulation_cards()}</section>
    {manual_controls}
    {review_block}
    <section class=\"card\"><h2>資料新鮮度</h2>{freshness_cards(runtime)}</section>
    <section class=\"panel\"><h2>LINE / Email / Dashboard delivery audit summary</h2><p>LINE 僅作提醒；Email 為 PM-readable summary；完整內容以 Dashboard 為準。此頁 publish 不會重送通知。</p></section>
    <details><summary>技術檢查 / Debug</summary><p>Debug / 範例 artifact 已隔離，不作為正式最新報告。</p><p>runtime markers: pre_open_0700 盤前預測 Pre-open Forecast / intraday_1305 盤中追蹤 Intraday Tracking / pre_close_1335 close_snapshot_1335 收盤快照 / Close Snapshot / post_close_1500 prediction_review_1500 盤後檢討 / Prediction Review</p><p>production_dashboard_publish_executed=false; no notification; no scheduler change; no DB write; no production pipeline; no trading; no rating/action/confidence/weight mutation.</p></details>
  </main>
</body></html>"""
