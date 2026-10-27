"""CLI + pinned alias + real local HTTP + browser; no Production fixture."""
from contextlib import redirect_stdout
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sys
from threading import Thread
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from app.dashboard.trusted_static_root import VERSION, identity
from scripts.orchestrator.publish_tw_correction_dashboard import main
from tests.test_ai_dev_283 import inputs, seal, digest, URL
from tests import test_ai_dev_284 as fixtures
from tests.test_ai_dev_284 import identity_attributes, render_correction
from tests.test_ai_dev_286 import forbid_computation
from app.dashboard import correction_publication as pub


class AliasHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if not self.path.startswith('/stock-ai-dashboard/'):
            self.send_error(404); return
        self.path=self.path[len('/stock-ai-dashboard'):]
        return super().do_GET()
    def log_message(self,*args):pass


class VerifiedExistingE2E(unittest.TestCase):
    def test_cli_alias_http_mobile_and_idempotency(self):
        f=fixtures.CorrectionPublicationTests(); f.setUp(); self.addCleanup(f.doCleanups)
        pre,post=inputs(10)
        for i,(p,q) in enumerate(zip(pre['payload']['structured_pre_open_cards'],post['payload']['structured_review_cards'])):
            direction='bearish' if i<5 else 'bullish'
            low,high=(40,60) if i<9 else (80,90)
            p['prediction_presentation_v1'].update(direction=direction,today_range={'predicted_low':low,'predicted_high':high})
            p['prediction_snapshot_v2'].update(direction_forecast=direction,range_forecast={'low':low,'high':high})
            p['tw_preopen_product_intelligence_v1'].update(today_direction=direction.upper(),predicted_low=low,predicted_high=high)
            q.update(actual_open=50,actual_high=56,actual_low=44,actual_close=46)
        seal(pre)
        for q in post['payload']['structured_review_cards']:
            q.update(source_snapshot_id=pre['snapshot_id'],prediction_snapshot_id=pre['snapshot_id'],
                     prediction_payload_hash=digest(pre['payload']),parent_source_payload_hash=digest(pre['payload']))
        seal(post)
        f.pre_path.write_text(json.dumps(pre)); f.post_path.write_text(json.dumps(post))
        # Fixture creation only; evaluator/renderer tracing starts AFTER this.
        bundle=render_correction(pre,post,session='2099-04-07',revision=1,
                                expected_pre_id=pre['snapshot_id'],expected_post_id=post['snapshot_id'],dashboard_url=URL)
        for name,value in bundle.items():
            (f.source/name).write_text(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False))
        original=f'<!doctype html><html><body {identity_attributes(post)}>Synthetic original</body></html>'.encode()
        f.original.write_bytes(original);f.latest.write_bytes(original)
        cid=bundle['correction.json']['snapshot_id']
        alias=f.root/'static-alias'; alias.symlink_to(f.static,target_is_directory=True)
        policy={'schema_version':VERSION,'logical_root':str(alias),'physical_root':str(f.static),
                'alias_identity':identity(alias.lstat()),'root_identity':identity(f.static.stat())}
        config=f.root/'trust.json';config.write_text(json.dumps(policy));config.chmod(0o600)
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(AliasHandler,directory=str(f.static)))
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base=f'http://127.0.0.1:{server.server_port}/stock-ai-dashboard'
        args=['publisher','--source-dir',str(f.source),'--pre-open-input',str(f.pre_path),
              '--post-close-input',str(f.post_path),'--expected-correction-id',cid,
              '--expected-receipt-hash',pub.sha((f.source/'receipt.json').read_bytes()),
              '--static-root',str(alias),'--trusted-static-root-config',str(config),
              '--original-html',str(f.original),'--expected-original-hash',pub.sha(original),
              '--audit-root',str(f.audit),'--public-base-url',base]
        before={str(p):p.read_bytes() for p in f.source.iterdir()}
        outputs=[]
        with forbid_computation() as trace:
            for mode in ('--preflight','--publish','--publish'):
                output=io.StringIO()
                with patch.object(sys,'argv',args+[mode]),redirect_stdout(output):main()
                outputs.append(json.loads(output.getvalue()))
        self.assertIn('verify_existing',trace)
        result=outputs[1]
        self.assertEqual(result['metrics'],{'direction':{'hit':5,'miss':5},'range':{'partial_hit':9,'miss':1}})
        self.assertTrue(result['http_verified']);self.assertTrue(outputs[2]['idempotent'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in f.source.iterdir()})
        self.assertEqual(f.latest.read_bytes(),original);self.assertEqual(f.original.read_bytes(),original)
        with sync_playwright() as browser_runtime:
            browser=browser_runtime.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':393,'height':852})
                response=page.goto(base+result['route'])
                self.assertEqual(response.status,200)
                self.assertEqual(page.locator('body').get_attribute('data-correction-id'),cid)
                self.assertEqual(page.locator('article.mobile-decision-card').count(),10)
                self.assertIn('2099-04-07',page.title())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),393)
                details=page.locator('details').first
                self.assertIsNone(details.get_attribute('open'))
                if os.environ.get('AI_DEV_286_TEST_EVIDENCE'):
                    out=Path(os.environ['AI_DEV_286_TEST_EVIDENCE'])
                    out.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(out/'synthetic-mobile-393.png'),full_page=True)
                    (out/'isolated-result.json').write_text(json.dumps({'status':'ISOLATED_E2E_PASS',
                        'metrics':result['metrics'],'computation_calls':0,'http_verified':True,
                        'production_published':False,'viewport':393},sort_keys=True))
                details.locator(':scope > summary').click()
                self.assertIsNotNone(details.get_attribute('open'))
                self.assertIn('009991',page.locator('body').inner_text())
            finally:browser.close()


if __name__=='__main__':unittest.main()
