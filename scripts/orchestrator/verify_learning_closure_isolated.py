#!/usr/bin/env python3
"""Offline acceptance on legally obtained input copies; never natural batch proof.

Requires the Nov 19 TW snapshots/CSV, immutable V1 daily artifacts and the
separately timestamped AAPL pre-open/close source captures. No acquisition.
Output must be a fresh directory outside the source tree and repository.
"""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import json,hashlib,shutil,socket
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
from contextlib import contextmanager
from unittest.mock import patch
import pandas as pd
from app.runtime.capture_context import make_context,CONTEXT_ENV,RUN_ENV
from app.evaluation.prediction_capture import capture_and_persist
from app.evaluation.us_session_direction import capture_existing,receipt_key,replay_prediction,STREAM
from app.dashboard.production_evidence_archive import project
from app.dashboard.window_snapshot_archive import snapshot_id
from app.dashboard.daily_evaluation_archive import collect_windows
from app.evaluation.daily_evaluation import replay,window_outcomes,predecessor_proof
from app.evaluation.daily_evaluation_v2 import build
from app.evaluation.prediction_regression_contract import stamp
from app.evaluation.session_calendar import load_calendar
from app.dashboard.daily_learning_presentation import publish_dashboard
parser=argparse.ArgumentParser()
parser.add_argument('--input-root',type=Path,required=True)
parser.add_argument('--source-evidence',type=Path,required=True)
parser.add_argument('--output-root',type=Path,required=True)
args=parser.parse_args()
src=args.input_root.resolve();e=args.source_evidence.resolve();out=args.output_root.resolve()
if any(out == p or p in out.parents or out in p.parents for p in (src,e,ROOT)):
 raise ValueError('OUTPUT_MUST_BE_SEPARATE')
out.mkdir(exist_ok=False)
archive=src/'artifacts/archive/window_snapshots'
files=list(src.rglob('*.json'))+list(src.rglob('*.csv'))+[e/n for n in ('AAPL-observed-history.csv','AAPL-close-history.csv','us-source-result.json','us-close-result.json')]
def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
before=hashes()
@contextmanager
def context(market,window,at):
 at=datetime.fromisoformat(at)
 c=make_context(run_id='ISOLATED-REHEARSAL',market=market,window=window,mode='scheduled',now=at)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at if tz is None else at.astimezone(tz)
 with patch.dict('os.environ',{CONTEXT_ENV:json.dumps(c),RUN_ENV:c['run_id']}),patch('app.runtime.capture_context.datetime',Clock):yield

def snap(market,window,day):return json.loads((archive/market/window/day/'revision-0001.json').read_text())
def save(name,value):
 (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
 return value
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(socket,'create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 old=[]
 for p in sorted((archive/'.daily_evaluation').glob('*/*.json')):
  v=json.loads(p.read_text());replay(v);old.append(v)
 tw=snap('tw','pre_open_0700','2026-11-19')
 cards=tw['payload']['structured_pre_open_cards']
 card=next(c for c in cards if str(c.get('symbol'))=='2330')
 dest=out/'data/historical/2330_daily.csv';dest.parent.mkdir(parents=True);shutil.copyfile(src/'data/historical/2330_daily.csv',dest)
 # Controlled historical clock proves pipeline mechanics, not historical capture.
 tw_at=tw['generated_at']
 with context('TW','pre_open_0700',tw_at):
  tr=capture_and_persist(card,root=out,clock=lambda:tw_at)
 assert tr['capture']['status']=='FROZEN',tr
 tw_record=project(tw,{card['prediction_snapshot_v2']['prediction_identity']:tr})
 tw_windows=collect_windows(archive,'TW',['2026-11-19'],'2026-11-20T17:00:00+08:00')
 tw_out,tw_diag=window_outcomes([tw_record],tw_windows,'2026-11-20T17:00:00+08:00')
 assert len(tw_out)==1,tw_diag
 meta=json.loads((e/'us-source-result.json').read_text());closemeta=json.loads((e/'us-close-result.json').read_text())
 def history(name):
  df=pd.read_csv(e/name,index_col=0);df.index=pd.to_datetime(df.index,utc=True);return df
 quote={'last_price':meta['last_price'],'market_data_as_of':datetime.fromtimestamp(meta['regularMarketTime'],timezone.utc).isoformat()}
 at=meta['received_at']
 with context('US',STREAM,at):
  capture_existing('AAPL',quote,history('AAPL-observed-history.csv'),'2026-11-19',STREAM,root=out,clock=lambda:at)
 receipt=json.loads((out/'artifacts/archive/window_snapshots/us'/STREAM/'2026-11-19/.frozen'/(receipt_key('AAPL','2026-11-19')+'.json')).read_text())
 assert receipt['capture']['status']=='FROZEN',receipt['capture'].get('reason')
 replay_prediction(receipt['capture'])
 us=deepcopy(snap('us',STREAM,'2026-11-19'))
 item=next(i for i in us['payload']['items'] if i['symbol']=='AAPL')
 item['quote']=quote;us['payload']['items']=[item];us['generated_at']=at
 us['snapshot_id']=snapshot_id({k:v for k,v in us.items() if k!='snapshot_id'})
 record=project(us,{'AAPL':receipt})
 assert record['records'][0]['direction_sample_count']==1,record['records'][0]['reason_codes']
 cat=closemeta['received_at'];closewin='us_post_close_review_0630'
 cq={'last_price':closemeta['last_price'],'market_data_as_of':datetime.fromtimestamp(closemeta['regularMarketTime'],timezone.utc).isoformat()}
 with context('US',closewin,cat):
  capture_existing('AAPL',cq,history('AAPL-close-history.csv'),'2026-11-19',closewin,root=out,clock=lambda:cat)
 obs=[json.loads(p.read_text()) for p in (out/'artifacts/archive/window_snapshots/us'/closewin/'2026-11-19/.frozen').glob('*.json')]
 win=stamp({'kind':'DAILY_WINDOW_EVIDENCE','market':'US','window':closewin,'session':'2026-11-19','generated_at':cat,'observations':obs,'cards':[],'source_digest':obs[0]['content_hash']})
 us_out,us_diag=window_outcomes([record],[win],'2026-11-20T17:00:00+08:00')
 assert len(us_out)==1,us_diag
 inputs={m:{'calendar':load_calendar(m),'records':[r],'outcomes':o,'window_evidence':w,'outcome_diagnostics':d} for m,r,o,w,d in [('TW',tw_record,tw_out,tw_windows,tw_diag),('US',record,us_out,[win],us_diag)]}
 value=build('2026-11-20',inputs,predecessor_proof(old[-1]));replay(value)
 for m in ('TW','US'):
  summary=value['markets'][m]['coverage_summary'];assert summary['paired_outcome_count']==1,summary
  assert summary['state']=='INSUFFICIENT_SAMPLE',summary
 save('daily-v2.json',value)
 page=publish_dashboard(value,static_root=out/'public',output_root=out/'staging')
 assert page['status']=='PUBLISHED'
 assert hashes()==before
 save('acceptance.json',{'status':'PASS','mode':'ISOLATED_CONTROLLED_CLOCK_REHEARSAL_NOT_NATURAL_EVIDENCE','tw':'historical input copy with controlled freeze clock; no point-in-time capture claim','us':'real Nov19 pre-open and post-close observations; reconstructed isolated receipt, not natural batch','legacy_replay_count':len(old),'coverage':{m:value['markets'][m]['coverage_summary'] for m in ('TW','US')},'input_hashes':before,'input_hash_parity':True,'network_requests':0,'notification_calls':0,'trade_calls':0,'production_writes':0})
 print(json.dumps({'status':'PASS','legacy_replay_count':len(old),'coverage':{m:value['markets'][m]['coverage_summary'] for m in ('TW','US')}},ensure_ascii=False))
