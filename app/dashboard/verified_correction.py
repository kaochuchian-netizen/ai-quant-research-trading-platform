"""Read-only admission of already evaluated/rendered correction bundles.

Never call an evaluator, projection builder, quality gate or renderer. The
operator's independently approved receipt hash anchors saved output bytes and
quality evidence; the correction ID anchors the canonical evaluation digest.
"""
from datetime import date
import hashlib
import re

from app.reports.tw_delivery_evaluation import (
    KEY, EVALUATION_KEY, digest, number, snapshot_identity, validate_projection,
)


def require(condition, reason):
    if not condition:
        raise ValueError('CORRECTION_' + reason)


def verify_receipt_pin(raw, expected):
    require(isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected), 'RECEIPT_PIN_REQUIRED')
    require(hashlib.sha256(raw).hexdigest() == expected, 'RECEIPT_PIN_MISMATCH')


def verify_existing(pre, post, value, receipt, expected_id):
    """Check saved contracts and equality only; do not derive hit/miss results."""
    session = value['effective_trading_date']
    require(date.fromisoformat(session).isoformat() == session, "SESSION_FORMAT")
    pre_id = snapshot_identity(pre, window='pre_open_0700', session=session)
    post_id = snapshot_identity(post, window='post_close_1500', session=session)
    require(pre.get('run_kind') == 'scheduled' and not pre.get('manual_rerun'), 'NATURAL_SOURCE_REQUIRED')
    require(post.get('run_kind') == 'scheduled' and not post.get('manual_rerun'), 'NATURAL_SOURCE_REQUIRED')
    symbols = pre['payload'].get('notification_universe')
    require(isinstance(symbols, list) and bool(symbols)
            and all(isinstance(s, str) and re.fullmatch(r'[0-9]{4,6}', s) for s in symbols)
            and len(set(symbols)) == len(symbols), 'UNIVERSE_INVALID')
    require(set(pre['payload'].get('tracking_symbols', [])) == set(symbols), 'UNIVERSE_MISMATCH')
    require(post['payload'].get('notification_universe') == symbols, 'UNIVERSE_MISMATCH')
    revision = value.get('correction_revision')
    require(type(revision) is int and revision > 0, 'REVISION_INVALID')
    payload = value['payload']
    cards = payload.get('structured_review_cards', [])
    def indexed(rows):
        require(isinstance(rows, list) and len(rows) == len(symbols), 'UNIVERSE_CARD_MISMATCH')
        mapped = {str(c.get('symbol') or c.get('stock_id') or ''): c for c in rows}
        require(set(mapped) == set(symbols) and len(mapped) == len(rows), 'UNIVERSE_CARD_MISMATCH')
        return mapped
    setups = indexed(pre['payload'].get('structured_pre_open_cards'))
    originals = indexed(post['payload'].get('structured_review_cards'))
    indexed(cards)
    require([str(c.get('symbol') or c.get('stock_id')) for c in cards] == symbols, 'UNIVERSE_ORDER')
    prov = payload.get('correction_provenance', {})
    expected_prov = {'schema_version': 'tw_delivery_correction_v1', 'session': session,
                     'correction_revision': revision,
                     'pre': {**pre_id, 'universe_digest': digest(symbols), 'symbol': symbols[0]},
                     'post': post_id, 'universe_digest': digest(symbols),
                     'evaluations_digest': digest([c.get(EVALUATION_KEY) for c in cards])}
    require(prov == expected_prov and digest(prov) == value.get('snapshot_id') == expected_id,
            'CANONICAL_IDENTITY')
    # Every other envelope/payload/source-card field must still be the original.
    expected_envelope = {**post, 'payload': payload, 'snapshot_id': expected_id,
        'run_kind': 'isolated_correction', 'runtime_provenance': 'isolated_correction',
        'admitted': False, 'admission_reason': 'publication_requires_explicit_approval',
        'correction_revision': revision, 'parent_snapshot_id': post_id['snapshot_id']}
    require(value == expected_envelope, 'CANONICAL_ENVELOPE')
    expected_payload = {**post['payload'], 'cards': cards, 'structured_review_cards': cards,
        'notification_universe': symbols, 'tracking_symbols': symbols, 'correction_provenance': prov,
        'marker': f'{session} 15:00 更正報告（隔離驗證，未發布）'}
    require(payload == expected_payload, 'CANONICAL_PAYLOAD')
    require(receipt.get('schema_version') == 'tw_delivery_correction_validation_v1'
        and receipt.get('correction_id') == expected_id and receipt.get('provenance') == prov
        and receipt.get('expected_symbols') == symbols
        and all(receipt.get(k) is False for k in ('notification_sent','database_write','latest_write','archive_write')),
        'RECEIPT_BINDING')
    stages = {'market_acquisition': 'NOT_EXECUTED_FROZEN_OFFICIAL_OHLC',
        'prediction_generation': 'NOT_EXECUTED_FROZEN_PUBLIC_FORECAST',
        'canonical_evaluation': 'EXECUTED', 'quality_gate': 'EXECUTED',
        'dashboard_renderer': 'EXECUTED', 'line_renderer': 'EXECUTED', 'email_renderer': 'EXECUTED',
        'publication': 'NOT_EXECUTED', 'transport': 'NOT_EXECUTED'}
    require(receipt.get('stages') == stages, 'RECEIPT_STAGE_VERSION')
    gate = receipt.get('quality', {})
    require(gate.get('schema_version') == 'post_close_decision_quality_gate_v2'
        and gate.get('market') == 'TW' and gate.get('window') == 'post_close_1500'
        and gate.get('status') == 'QUALIFIED' and gate.get('line_send_allowed') is True,
        'QUALITY_REJECTED')
    quality = indexed(gate.get('cards'))
    require([c.get('symbol') for c in gate['cards']] == symbols, 'QUALITY_ORDER')
    for card in cards:
        symbol = str(card.get('symbol') or card.get('stock_id'))
        setup = setups[symbol]
        projection = validate_projection(card.get(KEY))
        evaluation = card.get(EVALUATION_KEY, {})
        identity = {**pre_id, 'universe_digest': digest(symbols), 'symbol': symbol}
        require(card == {**originals[symbol], KEY: projection, EVALUATION_KEY: evaluation,
                         'delivery_source_identity': identity}, 'SOURCE_CARD_MUTATION')
        require(card.get('trading_date') == projection.get('trading_date') == session
            and projection.get('symbol') == symbol and setup.get('trading_date') == session,
            'PER_SYMBOL_IDENTITY')
        require(card.get('source_snapshot_id') == identity['snapshot_id']
            and card.get('prediction_snapshot_id',card.get('source_snapshot_id')) == identity['snapshot_id']
            and card.get('prediction_revision',card.get('source_revision')) == identity['revision']
            and card.get('prediction_payload_hash',card.get('parent_source_payload_hash')) == identity['payload_hash'],
            'PREDICTION_IDENTITY')
        presentation = setup.get('prediction_presentation_v1')
        require(isinstance(presentation, dict) and projection.get('source_field') == 'prediction_presentation_v1'
            and projection.get('representation_hash') == digest(presentation)
            and projection.get('prediction_id') == presentation.get('prediction_id'), 'FROZEN_REPRESENTATION')
        if KEY in setup:
            require(projection == setup[KEY], 'FROZEN_REPRESENTATION')
        else:
            # Legacy source already has the exact public values and prediction ID.
            # Compare them; never construct a new projection or call freeze().
            research = setup.get('prediction_snapshot_v2', {})
            interval = research.get('range_forecast', {})
            require(research.get('symbol') == symbol and research.get('effective_trading_date') == session
                and research.get('prediction_identity') == projection.get('prediction_id')
                and research.get('direction_forecast') == projection.get('direction')
                and (interval.get('low'),interval.get('high')) == (projection.get('low'),projection.get('high')),
                'LEGACY_REPRESENTATION')
        public_range = presentation.get('today_range') or {}
        unavailable = setup.get('availability_status') == 'unavailable' or bool(setup.get('failure_category'))
        direction = presentation.get('direction')
        direction = 'neutral' if direction == 'range_bound' else direction
        direction = direction if direction in ('bullish','bearish','neutral') else None
        require((projection.get('direction'),projection.get('low'),projection.get('high')) ==
                ((None,None,None) if unavailable else (direction,number(public_range.get('predicted_low')),number(public_range.get('predicted_high')))),
                'FROZEN_PUBLIC_VALUES')
        values = [number(card.get('actual_' + k)) for k in ('open','high','low','close')]
        require(card.get('actual_status') == 'complete' and None not in values
            and 0 < values[2] <= min(values[0],values[3]) <= max(values[0],values[3]) <= values[1], 'ACTUAL_EVIDENCE')
        require(evaluation.get('schema_version') == EVALUATION_KEY
            and evaluation.get('scoring_contract') == 'tw_open_close_neutral_0.005_and_range_endpoint_overlap_v1'
            and evaluation.get('projection_digest') == projection['digest']
            and evaluation.get('actual_digest') == digest({'ohlc':values,'status':card.get('actual_status'),
                       'as_of':card.get('market_data_as_of'),'source':card.get('source_name')}), 'EVALUATION_BINDING')
        q = quality[symbol]
        require(q.get('schema_version') == gate['schema_version'] and q.get('market') == 'TW'
            and q.get('window') == 'post_close_1500' and q.get('status') == 'EVALUATED'
            and q.get('prediction_identity') == ((card.get('source_trade_plan') or {}).get('source_snapshot_id') or card.get('source_snapshot_id')),
            'QUALITY_IDENTITY')
        # The saved gate must describe the same official OHLC, never another range.
        require(q.get('actual') == {'status':'AVAILABLE','low':values[2],'high':values[1],'close':values[3]}, 'QUALITY_ACTUAL')
        for part in ('direction','range'):
            component = evaluation.get(part, {})
            require(component == q.get(part) and component.get('identity') == identity
                and component.get('scope') == 'TW_FROZEN_DELIVERED_FORECAST', 'QUALITY_COMPONENT')
            allowed = {'hit','miss'} if part == 'direction' else {'hit','partial_hit','miss'}
            if component.get('status') == 'NOT_APPLICABLE':
                require(component.get('result') == 'not_applicable' and bool(component.get('reason_code')),
                        'COMPONENT_NA_REASON')
                require(projection.get('direction' if part == 'direction' else 'low') is None, 'COMPONENT_NA_FORECAST')
            else:
                require(component.get('status') == 'EVALUATED' and component.get('result') in allowed
                    and component.get('reason_code') is None, 'COMPONENT_STATUS')
                if part == 'direction':
                    require(component.get('forecast') == projection.get('direction')
                        and component.get('actual') in ('bullish','bearish','neutral'), 'COMPONENT_FORECAST')
                else:
                    require((component.get('forecast_low'),component.get('forecast_high')) ==
                            (projection.get('low'),projection.get('high')), 'COMPONENT_FORECAST')
    return gate
