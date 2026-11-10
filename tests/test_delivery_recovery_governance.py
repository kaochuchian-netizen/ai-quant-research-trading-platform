import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from app.runtime.delivery_supervisor import supervise
from app.reports.channel_delivery_receipt import delivery_identity, deliver_once
from scripts.orchestrator.validate_post_merge_status import classify_dirty_paths

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class RecoveryGovernanceTests(unittest.TestCase):
    def classify(self,root,path):
        return classify_dirty_paths(['?? '+str(path.relative_to(root))],repo_root=root)
    def test_claim_and_us_receipt_require_immutable_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            snapshot={'schema_version':'window_snapshot_archive_v1','market':'US','window':'us_post_close_review_0630','effective_trading_date':'2026-11-05','revision':1,'generated_at':'2026-11-06T06:30:00+08:00','status':'complete','run_kind':'scheduled','runtime_provenance':'scheduled_production','admitted':True,'payload':{'runtime_provenance':'scheduled_production'}}
            snapshot['snapshot_id']=digest(snapshot)
            source=root/'artifacts/archive/window_snapshots/us/us_post_close_review_0630/2026-11-05/revision-0001.json';source.parent.mkdir(parents=True);source.write_text(json.dumps(snapshot))
            receipts=root/'artifacts/runtime/us_stock/channel_delivery_receipts'
            identity=delivery_identity(snapshot=snapshot,market='US',window=snapshot['window'],channel='line',content='no-send')
            deliver_once(receipt_root=receipts,identity=identity,channel='line',sender=lambda:{'recipients':[{'recipient':'synthetic','status':'failed'}]})
            for path in receipts.iterdir():
                self.assertEqual(len(self.classify(root,path)['preserved_runtime_artifacts']),1)
            source.write_text('{}')
            for path in receipts.iterdir():
                self.assertEqual(len(self.classify(root,path)['unknown_dirty_paths']),1)
    def test_supervisor_manifest_binds_paths_and_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            script='import os,json,sys;from pathlib import Path;Path(sys.argv[-1]).write_text(json.dumps({"ok":True,"run_id":os.environ["STOCK_AI_DELIVERY_RUN_ID"]}))'
            result=supervise([sys.executable,'-c',script],cwd=root,market='TW',window='pre_open_0700',timeout_seconds=3,evidence_root=root/'artifacts/runtime/delivery_supervisor')
            directory=Path(result['worker']['evidence_dir'])
            for path in directory.iterdir():
                self.assertEqual(len(self.classify(root,path)['preserved_runtime_artifacts']),1,path)
            (directory/'worker.log').write_text('changed')
            self.assertTrue(self.classify(root,directory/'manifest.json')['unknown_dirty_paths'])
            extra=directory/'extra.py';extra.write_text('pass')
            self.assertTrue(self.classify(root,extra)['unknown_dirty_paths'])
if __name__=='__main__':unittest.main()
