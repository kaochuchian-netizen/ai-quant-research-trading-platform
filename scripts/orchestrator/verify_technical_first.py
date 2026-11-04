#!/usr/bin/env python3
"""Frozen-input controlled rerun of native decision builders and channel previews.

No live providers, notifications, latest files, DBs or production writes. This
is an isolated replay, never a reconstruction of historical delivered output.
"""
import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.loaders.batch_universe import historical_universe, require_parity, digest
from app.prediction.technical_first import KEY, status_text


def load(path):
    return json.loads(Path(path).read_text())


def replay(tw, us, frozen_dir):
    from app.reports.tw_four_window_decision import upgrade_pre_open_card
    from app.strategy.tw_daily_tactical import build_tactical
    from app.us_stock.live_data import FetchResult
    from app.us_stock.live_pipeline import build_live_runtime_artifact
    from app.reports.mobile_decision_presentation import render_primary, render_line
    from app.reports.tw_pre_open_structured import render_email as tw_email
    from scripts.orchestrator.approved_us_stock_delivery import build_email_body
    import pandas as pd

    universe_tw, universe_us = historical_universe(tw), historical_universe(us)
    rows = {x['symbol']: x for x in us['payload']['items']}
    observations = {}
    for path in Path(frozen_dir).glob('*.json'):
        value = load(path)
        if value.get('kind') != 'US_MARKET_OBSERVATION':
            continue
        if value.get('content_hash') != digest({k:v for k,v in value.items() if k != 'content_hash'}):
            raise ValueError('FROZEN_OBSERVATION_HASH_MISMATCH')
        if value.get('review_session') != us['effective_trading_date']:
            raise ValueError('FROZEN_OBSERVATION_SESSION_MISMATCH')
        if value['symbol'] in observations:
            raise ValueError('AMBIGUOUS_FROZEN_OBSERVATION')
        observations[value['symbol']] = value
    require_parity(universe_us, [s for s in universe_us['symbols'] if s in observations])

    class FrozenClient:
        def fetch_context(self):
            return deepcopy(us['payload']['market_context'])

        def fetch_symbol(self, symbol, company=None):
            row = rows[symbol]; obs = observations[symbol]
            frame = pd.DataFrame(obs['rows']).rename(columns={'high':'High','low':'Low','close':'Close'})
            frame.index = pd.to_datetime(frame.pop('date'))
            # Frozen observation lacks volume; never manufacture it.
            return FetchResult(symbol, True, deepcopy(row['quote']), frame, deepcopy(row['news']),
                               deepcopy(row['research_intelligence']['material_news']['evidence_funnel']), None)

    class FrozenResearch:
        def build_for_symbol(self, symbol, *args):
            return deepcopy(rows[symbol]['research_intelligence'])

    tw_cards = []
    for old in tw['payload']['structured_pre_open_cards']:
        old = deepcopy(old)
        native = old['strategies']['daily_tactical']
        tactical = build_tactical({'symbol':old['symbol'],'name':old.get('name')}, native['technical_factors'], native['market_context'])
        tactical['generated_at'] = tw['generated_at']
        tactical['effective_trading_date'] = tw['effective_trading_date']
        tw_cards.append(upgrade_pre_open_card(old, tactical, source_revision=tw['revision']))
    tw_payload = {**deepcopy(tw['payload']), 'structured_pre_open_cards':tw_cards,
                  'effective_trading_date':tw['effective_trading_date'], 'tracking_symbols':universe_tw['symbols']}
    tw_payload.pop('pre_open_summary', None)
    with patch('app.us_stock.live_pipeline.YFinanceUSClient', FrozenClient), \
         patch('app.us_stock.live_pipeline.USResearchIntelligenceBuilder', FrozenResearch), \
         patch('app.us_stock.live_pipeline.now_taipei', return_value=us['generated_at']):
        us_payload = build_live_runtime_artifact('us_pre_market_2000',universe_us['entries'],
                      production_runtime=False,write_snapshots=False,reference=datetime.fromisoformat(us['generated_at']))
    payloads = {'TW':tw_payload,'US':us_payload}
    for market, payload in payloads.items():
        payload.update(artifact_mode='controlled_frozen_replay',data_source_mode='frozen_input',
                       runtime_provenance='isolated_replay',validation_only=True,
                       origin_snapshot_id=(tw if market == 'TW' else us)['snapshot_id'])
    results, previews = {}, {}
    for market, payload in payloads.items():
        window = 'pre_open_0700' if market == 'TW' else 'us_pre_market_2000'
        cards = payload['structured_pre_open_cards'] if market == 'TW' else payload['dashboard_ready_contract']['cards']
        require_parity(universe_tw if market == 'TW' else universe_us, [c['symbol'] for c in cards])
        html = render_primary(payload,market,window)
        line = render_line(payload,market,window,'https://preview.invalid/no-publish')
        email = tw_email(payload,'https://preview.invalid/no-publish') if market == 'TW' else build_email_body(payload,window)
        previews[market] = {'dashboard.html':html,'line.txt':line,'email.txt':email}
        results[market] = {'universe_parity':'PASS','rows':[]}
        for card in cards:
            final = card[KEY]['final_decision']
            text = status_text(card)
            from html import unescape
            parity = all(text in unescape(content) for content in (html,line,email))
            if not parity:
                raise ValueError('DECISION_STATUS_CHANNEL_PARITY')
            results[market]['rows'].append({'symbol':card['symbol'],'mode':final['mode'],
                'technical_research_usable':final['technical_research_usable'],
                'news_evidence_usable':final['news_evidence_usable'],
                'combined_research_usable':final['combined_research_usable'],
                'news_status':final['news_status'],'event_risk':final['event_risk'],
                'reason_codes':card[KEY]['technical_base']['reason_codes'],
                'base_id':card[KEY]['technical_base']['base_id'],'decision_id':card[KEY]['decision_id'],
                'channel_status_parity':'PASS'})
    return results, payloads, previews


def main():
    p=argparse.ArgumentParser()
    for name in ('tw-snapshot','us-snapshot','us-frozen','output'): p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args()
    output=args.output.resolve()
    if output.exists() or 'latest' in output.parts or output.is_relative_to(ROOT/'artifacts'):
        raise ValueError('FRESH_ISOLATED_OUTPUT_REQUIRED')
    tw,us=load(args.tw_snapshot),load(args.us_snapshot)
    output.mkdir(parents=True,exist_ok=False)
    def guard(event, values):
        if event in {'socket.connect','socket.getaddrinfo','subprocess.Popen','os.system'}:
            raise RuntimeError('CONTROLLED_REPLAY_EXTERNAL_IO_FORBIDDEN')
        if event == 'open' and isinstance(values[0],(str,bytes)):
            path=Path(values[0]).resolve(); flags=values[2] or 0
            import os
            if flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC) and not path.is_relative_to(output):
                raise RuntimeError('CONTROLLED_REPLAY_WRITE_OUTSIDE_OUTPUT')
            if path.name=='.env' or path.suffix in {'.db','.sqlite'}:
                raise RuntimeError('CONTROLLED_REPLAY_PRIVATE_DATA_FORBIDDEN')
    sys.addaudithook(guard)
    result,payloads,previews=replay(tw,us,args.us_frozen)
    report={'kind':'CONTROLLED_FROZEN_REPLAY_NOT_PRODUCTION','status':'COMPLETED','markets':result,
            'inputs':{str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in (args.tw_snapshot,args.us_snapshot)},
            'limitations':['US frozen OHLC contains no volume; volume remains unavailable',
                           'TW recalculates tactical/card from frozen features; upstream raw OHLCV not reproduced',
                           'No current news or Sheet values inserted; live ingestion not replayed',
                           'No historical technical/news split: paired OOS performance UNKNOWN'],
            'production_written':False,'notifications_sent':False,'db_accessed':False}
    for market,payload in payloads.items():
        (output/(market+'-payload.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2))
        for name,content in previews[market].items(): (output/(market+'-'+name)).write_text(content)
    (output/'REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
