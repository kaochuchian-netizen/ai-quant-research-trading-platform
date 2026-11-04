"""Read-only natural batch quality audit. Missing evidence is never success.

No providers, renderers, databases or delivery code are imported. Historical
inputs are verified in place and never supplemented from today's sources.
"""
from app.loaders.batch_universe import digest, historical_universe, identity_terms


def check_snapshot(snapshot, receipts=()):
    expected = digest({k: v for k, v in snapshot.items() if k != 'snapshot_id'})
    if snapshot.get('snapshot_id') != expected:
        return {'status': 'FAIL', 'reasons': ['IMMUTABLE_SNAPSHOT_HASH_MISMATCH'], 'symbols': []}
    payload = snapshot.get('payload') or {}
    try:
        universe = historical_universe(snapshot)
    except (ValueError, KeyError, TypeError):
        return {'status': 'FAIL', 'reasons': ['FROZEN_UNIVERSE_UNVERIFIABLE'], 'symbols': []}
    cards = payload.get('structured_pre_open_cards') or payload.get('structured_review_cards') or (payload.get('dashboard_ready_contract') or {}).get('cards') or payload.get('items') or []
    symbols = [str(c.get('symbol') or c.get('stock_id')) for c in cards]
    parity = symbols == universe['symbols']
    entries = {e['symbol']: e for e in universe['entries']}
    rows = []
    for card in cards:
        symbol = str(card.get('symbol') or card.get('stock_id'))
        news = card.get('news_evidence') or {}
        retrieval = news.get('retrieval') or card.get('news_retrieval') or {}
        items = news.get('evidence') or card.get('news_items') or []
        projection = card.get('finalized_tw_news_projection_v1') or card.get('finalized_current_news_projection_v3') or {}
        items = items or projection.get('selected_items') or []
        counts = dict(success=0, body_rejected=0, headline_only=0, acquisition_failed=0, unverified=0)
        article_rows = []
        for item in items:
            ev = item.get('article_evidence') or {}
            status = ev.get('article_content_status')
            usable = ev.get('investment_usable') is True
            facts = ev.get('facts') or []
            category = 'success' if usable and facts and ev.get('content_sha256') else 'body_rejected' if status in {'FULL_OR_SUBSTANTIVE', 'PARTIAL'} else 'headline_only' if status == 'HEADLINE_ONLY' else 'acquisition_failed' if status == 'FAILED' else 'unverified'
            counts[category] += 1
            article_rows.append({'url': ev.get('source_url') or item.get('source_url'), 'title': item.get('title') or item.get('english_headline'), 'published_at': ev.get('published_at') or item.get('published_at'), 'body_length': ev.get('content_length'), 'category': category, 'reason': ev.get('reason'), 'facts': facts})
        reasons = []
        if not identity_terms(entries.get(symbol, {})): reasons.append('COMPANY_IDENTITY_MISSING')
        if retrieval.get('failure_reason') not in (None, '', 'NO_RESULT', 'FILTERED'): reasons.append(str(retrieval['failure_reason']))
        if not items: reasons.append('NO_SAVED_ARTICLE_EVIDENCE')
        if counts['unverified']: reasons.append('ARTICLE_QUALITY_UNVERIFIED')
        if not counts['success']: reasons.append('NO_INVESTMENT_USABLE_ARTICLE')
        forecast = card.get('prediction_v2') or card.get('prediction') or {}
        plan = card.get('investment_strategy') or card.get('trade_plan') or {}
        eligibility = card.get('eligibility') or plan
        blocked = eligibility.get('actionable') is False
        plan_reasons = eligibility.get('reason_codes') or eligibility.get('blocking_reasons') or eligibility.get('reason')
        from app.prediction.technical_first import KEY
        decision = card.get(KEY) or {}
        split = decision.get('final_decision') or {}
        split_quality = {
            'technical_research_usable': ('PASS' if split['technical_research_usable'] else 'FAIL') if 'technical_research_usable' in split else 'UNKNOWN',
            'news_evidence_usable': 'PASS' if split.get('news_evidence_usable') else 'FAIL' if items or reasons else 'UNKNOWN',
            'combined_research_usable': ('PASS' if split['combined_research_usable'] else 'FAIL') if 'combined_research_usable' in split else 'UNKNOWN',
        }
        if decision and decision.get('decision_id') != digest({k:v for k,v in decision.items() if k != 'decision_id'}):
            split_quality = {k: 'FAIL' for k in split_quality}
            reasons.append('DECISION_HASH_MISMATCH')
        rows.append({'symbol': symbol, 'identity': entries.get(symbol), 'status': 'FAIL' if reasons else 'PASS', 'reasons': reasons,
                     'technical_data_quality': (decision.get('technical_base') or {}).get('technical_data_quality', {'level': 'UNKNOWN'}), 'article_body_coverage': counts, 'articles': article_rows,
                     'research_evidence': 'PASS' if counts['success'] and all(a['facts'] for a in article_rows if a['category'] == 'success') else 'UNKNOWN',
                     'prediction_factors': forecast.get('news_evidence_use') or {'status': 'UNKNOWN', 'reason': 'NEWS_FACTOR_LINEAGE_MISSING'},
                     'entry_plan_gate': 'PASS' if blocked and plan_reasons else 'UNKNOWN', 'entry_plan_reasons': plan_reasons,
                     'learning_effectiveness': 'UNKNOWN', **split_quality})
    channels = {}
    for channel in ('email', 'line'):
        matching = [r for r in receipts if (r.get('identity') or {}).get('snapshot_id') == snapshot['snapshot_id'] and (r.get('channel') or (r.get('identity') or {}).get('channel')) == channel]
        accepted = [r for r in matching if r.get('transport_result') == 'transport_accepted' and r.get('recipients') and all(x.get('status') == 'accepted' for x in r['recipients'])]
        channels[channel] = {'status': 'PASS' if accepted else 'UNKNOWN', 'scope': 'per_recipient_transport_acceptance', 'final_delivery': 'UNKNOWN', 'receipt_count': len(matching)}
    technical_status = ('FAIL' if not parity or any(r['technical_research_usable'] == 'FAIL' for r in rows)
                        else 'PASS' if rows and all(r['technical_research_usable'] == 'PASS' for r in rows) else 'UNKNOWN')
    news_status = ('FAIL' if any(r['news_evidence_usable'] == 'FAIL' for r in rows)
                   else 'PASS' if rows and all(r['news_evidence_usable'] == 'PASS' for r in rows) else 'UNKNOWN')
    return {'schema_version': 'platform_natural_quality_v1', 'status': 'FAIL' if not parity or any(r['status'] == 'FAIL' for r in rows) else 'UNKNOWN',
            'technical_batch_status': technical_status, 'news_batch_status': news_status,
            'overall_operational_status': 'UNKNOWN',  # requires production/dashboard/recipient evidence
            'snapshot_id': snapshot['snapshot_id'], 'market': snapshot.get('market'), 'window': snapshot.get('window'),
            'universe_parity': 'PASS' if parity else 'FAIL', 'symbols': rows, 'channels': channels,
            'dashboard_parity': 'UNKNOWN', 'provenance_governance': 'UNKNOWN', 'historical_integrity': 'HISTORICAL_INTEGRITY_UNVERIFIABLE'}
