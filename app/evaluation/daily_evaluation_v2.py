"""Versioned coverage presentation; V1 evidence/evaluator semantics stay frozen."""
from collections import Counter
from copy import deepcopy
from app.evaluation.prediction_regression_contract import stamp
from app.evaluation.offline_report_projection import digest
from app.evaluation.production_evidence import verify

VERSION = 'daily_evaluation_integration_v2'
LEARNING_VERSION = 'daily_learning_application_v2'


def coverage(market, packet):
    stocks = market.get('stocks', {})
    samples = [r for s in stocks.values() for r in s.get('sample_reviews', {}).values()]
    paired = sum(r.get('assessment', {}).get('eligible') is True for r in samples)
    reasons = Counter(reason for record in packet.get('records', [])
                      for row in record.get('records', []) for reason in row.get('reason_codes', []))
    maturity = {n: {'required': int(n), 'mature_stock_count': sum(
        s['direction_component']['windows'][n]['sample_size'] >= int(n) for s in stocks.values()),
        'sample_sizes': {symbol: s['direction_component']['windows'][n]['sample_size']
                         for symbol, s in stocks.items()}} for n in ('3', '10')}
    if market.get('status') == 'BLOCKED_INPUT':
        state = 'BLOCKED_INPUT'
        reasons[market.get('reason', 'BLOCKED_INPUT')] += 1
    elif not samples:
        state = 'NO_ELIGIBLE_PREDICTION'
    elif not paired:
        state = 'WAITING_OUTCOME'
    elif not stocks or maturity['10']['mature_stock_count'] < len(stocks):
        state = 'INSUFFICIENT_SAMPLE'
    else:
        state = 'EVALUATED'
    return {'state': state, 'stock_count': len(stocks), 'eligible_prediction_count': len(samples),
            'paired_outcome_count': paired, 'waiting_outcome_count': len(samples)-paired,
            'maturity': maturity, 'exclusion_reasons': dict(sorted(reasons.items()))}


def build(report_date, inputs, predecessor=None):
    from app.evaluation.daily_evaluation import build_daily, STREAM, VERSION as V1
    base = build_daily(report_date, inputs)
    for market, data in base['markets'].items():
        data['coverage_summary'] = coverage(data, inputs[market])
    learning = deepcopy(base['learning_artifact'])
    learning.pop('content_hash'); learning.pop('learning_id')
    learning['schema_version'] = LEARNING_VERSION
    for market, data in learning['markets'].items():
        summary = base['markets'][market]['coverage_summary']
        data['coverage_summary'] = deepcopy(summary)
        if summary['state'] != 'EVALUATED':
            data['finding'] = summary['state']
        # This change reports evidence coverage; it does not alter learning controls.
    learning['learning_id'] = digest(learning)
    base['learning_artifact'] = stamp(learning)
    base['schema_version'] = VERSION
    base['evaluator_contracts']['254'] = VERSION
    base['identity'] = digest({'schema_version': VERSION, 'report_date': report_date,
                              'input_digest': base['input_digest'], 'contracts': base['evaluator_contracts']})
    base['predecessor'] = deepcopy(predecessor)
    base['comparison'] = {'status': 'NO_PREDECESSOR'}
    if predecessor is not None:
        verify(predecessor)
        version = predecessor.get('schema_version')
        if version not in (V1, VERSION) or predecessor.get('kind') != 'DAILY_PREDECESSOR_PROOF':
            raise ValueError('PREDECESSOR_SCHEMA')
        core = (build if version == VERSION else build_daily)(predecessor['report_date'], predecessor['inputs'])
        if predecessor['report_date'] >= report_date or predecessor.get('stream') != STREAM:
            raise ValueError('PREDECESSOR_IDENTITY')
        if core['content_hash'] != predecessor['core_digest'] or any(
                core[k] != predecessor[k] for k in ('identity', 'markets', 'stream')):
            raise ValueError('PREDECESSOR_REPLAY')
        base['comparison'] = {'status': 'BOUND', 'relationship': 'PRIOR_IMMUTABLE_DAILY_REVIEW',
            'predecessor_identity': predecessor['identity'], 'predecessor_hash': predecessor['core_digest'],
            'predecessor_schema': version, 'components': {},
            'score_comparison': 'NOT_COMPARABLE_ACROSS_COVERAGE_VERSIONS' if version == V1 else 'NOT_REQUESTED'}
    base.pop('content_hash', None)
    return stamp(base)


def replay(value):
    verify(value)
    if value.get('kind') != 'DAILY_EVALUATION' or value.get('schema_version') != VERSION:
        raise ValueError('DAILY_SCHEMA')
    if value != build(value['report_date'], value['inputs'], value['predecessor']):
        raise ValueError('DAILY_REPLAY')
    return value


def predecessor_proof(value):
    replay(value)
    core = build(value['report_date'], value['inputs'])
    return stamp({'schema_version': VERSION, 'kind': 'DAILY_PREDECESSOR_PROOF',
        'stream': value['stream'], 'identity': value['identity'], 'report_date': value['report_date'],
        'source_artifact_hash': value['content_hash'], 'core_digest': core['content_hash'],
        'inputs': deepcopy(value['inputs']), 'markets': deepcopy(value['markets'])})
