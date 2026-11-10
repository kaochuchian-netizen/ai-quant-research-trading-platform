#!/usr/bin/env python3
"""Offline frozen-source recovery rehearsal; writes only under a fresh temp root."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SOURCES = (('TW','pre_open_0700','2026-11-06'), ('US','us_post_close_review_0630','2026-11-05'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def worker(archive, work, output):
    work = work.resolve()
    def guard(event, args):
        if event in {'socket.connect','socket.connect_ex','socket.bind','subprocess.Popen','os.system'}:
            raise RuntimeError('rehearsal_external_effect_blocked:'+event)
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.name == '.env' or path.suffix == '.env' or 'credentials' in path.name:
                raise RuntimeError('rehearsal_credentials_blocked')
            mode = args[1] or ''
            flags = args[2] or 0
            if any(c in mode for c in 'wax+') or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
                if not path.is_relative_to(work):
                    raise RuntimeError('rehearsal_write_outside_temp')
        if event in {'os.rename','os.remove','os.mkdir','os.rmdir','os.chmod'}:
            for value in args[:2] if event == 'os.rename' else args[:1]:
                if isinstance(value, (str, bytes, os.PathLike)) and not Path(os.fsdecode(value)).resolve().is_relative_to(work):
                    raise RuntimeError('rehearsal_mutation_outside_temp')
    sys.addaudithook(guard)
    from unittest.mock import patch
    from app.runtime.delivery_supervisor import checkpoint
    from app.dashboard import public_latest_sync as sync, multi_market_dashboard as dashboard
    from app.dashboard.window_snapshot_archive import admission_errors
    from app.dashboard.market_dashboard_alias import payload_hash
    from app.reports.channel_delivery_receipt import deliver_once, delivery_identity, _valid_terminal_receipt
    # Import production formatters only; no runtime entry point or sender runs.
    with patch('dotenv.load_dotenv', return_value=False):
        from scripts.orchestrator import approved_pre_open_delivery as tw, approved_us_stock_delivery as us
    sync.WINDOW_SNAPSHOT_ARCHIVE = dashboard.WINDOW_SNAPSHOT_ARCHIVE = archive
    rows=[]
    for market,window,date in SOURCES:
        source=archive/market.lower()/window/date/'revision-0001.json'
        snapshot=json.loads(source.read_text())
        assert not admission_errors(snapshot)
        assert payload_hash({k:v for k,v in snapshot.items() if k!='snapshot_id'}) == snapshot['snapshot_id']
        checkpoint('archive_publish')
        public=work/'public'; build=work/'build'/market
        first=sync.synchronize_admitted_latest(market=market,window=window,static_root=public,output_dir=build)
        assert first['status']=='verified',first
        page_hashes={str(p):digest(p) for p in public.rglob('*.html')}
        second=sync.synchronize_admitted_latest(market=market,window=window,static_root=public,output_dir=build)
        assert second.get('idempotency')=='already_published',second
        assert page_hashes=={str(p):digest(p) for p in public.rglob('*.html')}
        if market=='TW':
            content={'email':tw.build_email_body(window,snapshot.get('run_id','frozen'),snapshot['generated_at'],'completed','https://example.invalid/dashboard','',snapshot),
                     'line':tw.build_line_message(window,snapshot['generated_at'],'completed','https://example.invalid/dashboard','',snapshot)}
        else:
            content={'email':us.build_email_body(snapshot['payload'],window),'line':us.line_text(snapshot['payload'],window)}
        checkpoint('notification')
        receipts=[]
        for channel,text in content.items():
            identity=delivery_identity(snapshot=snapshot,channel=channel,market=market,window=window,content=text)
            calls=[]
            def fake_transport():
                calls.append(True)
                return {'recipients':[{'recipient':'rehearsal-a.invalid','status':'accepted'}, {'recipient':'rehearsal-b.invalid','status':'rejected'}]}
            root=work/'receipts'/market/channel
            attempt=deliver_once(receipt_root=root,identity=identity,channel=channel,sender=fake_transport)
            repeat=deliver_once(receipt_root=root,identity=identity,channel=channel,sender=fake_transport)
            assert len(calls)==1 and not repeat['send_attempted']
            receipt=attempt['receipt']; assert _valid_terminal_receipt(receipt,identity)
            assert receipt['recipient_count']==2 and receipt['accepted_recipient_count']==1
            assert receipt['transport_result']=='partial_failure' and not receipt['final_recipient_delivery_confirmed']
            receipts.append({'channel':channel,'simulated_result':receipt['transport_result'],'recipient_count':2,'accepted_recipient_count':1,'repeat_suppressed':True,'content_sha256':identity['content_sha256']})
        rows.append({'market':market,'window':window,'effective_trading_date':date,'snapshot_id':snapshot['snapshot_id'], 'source_sha256':digest(source),'public_parity':'verified','publish_repeat_suppressed':True,'receipts':receipts})
    checkpoint('completed')
    result={'ok':True,'run_id':os.environ['STOCK_AI_DELIVERY_RUN_ID'],'rows':rows,
            'real_transport_calls':0,'analysis_executed':False,'trading':False,'production_publish':False,
            'mutation_guard':'temporary_root_only','network_guard':'deny_all'}
    output.write_text(json.dumps(result,indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',action='store_true');p.add_argument('--work-root',type=Path)
    args=p.parse_args()
    if args.worker:
        worker(args.archive,args.work_root,args.output);return
    from app.runtime.delivery_supervisor import supervise
    paths=[args.archive/m.lower()/w/d/'revision-0001.json' for m,w,d in SOURCES]
    before={str(path):digest(path) for path in paths}
    with tempfile.TemporaryDirectory(prefix='delivery-recovery-rehearsal-') as temp:
        work=Path(temp)
        archive=work/'archive'
        for path in paths:
            target=archive/path.relative_to(args.archive);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        result=supervise([sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--archive',str(archive),'--work-root',str(work)],cwd=work,market='TW',window='pre_open_0700',timeout_seconds=180,evidence_root=work/'supervisor')
        result['immutable_source_parity']=before=={str(path):digest(path) for path in paths}
        result['isolated_archive_parity']=all(digest(archive/path.relative_to(args.archive))==before[str(path)] for path in paths)
        if not result.get('ok'):
            result['failure_log']=Path(result['worker']['log_path']).read_text()[-3000:]
        args.output.write_text(json.dumps(result,indent=2))
        assert result.get('ok') and result['immutable_source_parity'] and result['isolated_archive_parity'], 'rehearsal_failed_see_report'
if __name__=='__main__':main()
