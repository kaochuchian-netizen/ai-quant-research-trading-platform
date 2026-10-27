"""Entirely synthetic correction publication fixtures; no runtime evidence."""
from copy import deepcopy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from app.dashboard import correction_publication as pub
from app.dashboard.market_dashboard_alias import identity_attributes
from scripts.orchestrator.codex_delivery_correction import prepare as render_correction
from scripts.orchestrator.publish_tw_correction_dashboard import http_verifier
from tests.test_ai_dev_283 import inputs, URL, seal


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class CorrectionPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'input'
        self.source.mkdir()
        self.static = self.root / 'public'
        self.static.mkdir()
        self.audit = self.root / 'private-audit'
        self.pre, self.post = inputs()
        self.pre_path, self.post_path = self.source / 'pre.json', self.source / 'post.json'
        self.write_inputs()
        self.artifacts = render_correction(self.pre, self.post, session='2099-04-07', revision=1,
                                          expected_pre_id=self.pre['snapshot_id'], expected_post_id=self.post['snapshot_id'], dashboard_url=URL)
        for name, value in self.artifacts.items():
            (self.source / name).write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
        self.receipt_pin = pub.sha((self.source / 'receipt.json').read_bytes())
        self.id = self.artifacts['correction.json']['snapshot_id']
        self.original = self.static / 'original-revision-1.html'
        self.original.write_text(f'<!doctype html><html><body {identity_attributes(self.post)}>Original synthetic legacy report</body></html>')
        self.original_bytes = self.original.read_bytes()
        self.latest = self.static / pub.PREFIX / 'latest/index.html'
        self.latest.parent.mkdir(parents=True)
        self.latest.write_bytes(self.original_bytes)
        self.target = self.static / pub.PREFIX / f'2099-04-07/corrections/{self.id}/index.html'

    def write_inputs(self):
        self.pre_path.write_text(json.dumps(self.pre))
        self.post_path.write_text(json.dumps(self.post))

    def prepare(self):
        return pub.prepare(self.source, self.pre_path, self.post_path, expected_id=self.id, expected_receipt_hash=self.receipt_pin)

    def publish(self, **kwargs):
        return pub.publish(self.source, self.pre_path, self.post_path, expected_id=self.id, expected_receipt_hash=self.receipt_pin,
                           static_root=self.static, original_html=self.original,
                           expected_original_hash=pub.sha(self.original_bytes), audit_root=self.audit, **kwargs)

    def test_prepare_no_writes_and_primary_cards_unchanged(self):
        before = {str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        plan = self.prepare()
        self.assertEqual(before, {str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        html = plan['html'].decode()
        import re
        for pattern in (r'<article\b.*?</article>', r'<div class="post-close-overview".*?</div>'):
            self.assertEqual(re.findall(pattern, html, re.S), re.findall(pattern,self.artifacts['index.html'],re.S))
        self.assertIn('2099-04-07 15:00 更正報告',html)
        self.assertIn(plan['route'],html)
        self.assertNotIn('隔離驗證版本，未正式發布',html)
        self.assertNotIn('Source Route：/'+pub.PREFIX+'/latest',html)
        self.assertIn('data-correction-revision="1"',html)
        self.assertEqual(plan['metrics'], {'direction':{'hit':2,'miss':2},'range':{'partial_hit':2,'hit':1,'miss':1}})

    def test_dynamic_universe_and_source_binding(self):
        for n in (8,15,30):
            pre,post = inputs(n)
            result=render_correction(pre,post,session='2099-04-07',revision=2,
                   expected_pre_id=pre['snapshot_id'],expected_post_id=post['snapshot_id'],dashboard_url=URL)
            self.pre_path.write_text(json.dumps(pre));self.post_path.write_text(json.dumps(post))
            for name,value in result.items():
                (self.source/name).write_text(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False))
            plan=pub.prepare(self.source,self.pre_path,self.post_path,expected_id=result['correction.json']['snapshot_id'], expected_receipt_hash=pub.sha((self.source/'receipt.json').read_bytes()))
            self.assertEqual(len(plan['snapshot']['payload']['notification_universe']),n)
            self.assertIn('009991',plan['html'].decode())

    def test_wrong_identity_date_market_revision_fail_closed(self):
        for field,value in [('market','US'),('effective_trading_date','2099-04-08'),('revision',2),('snapshot_id','0'*64)]:
            bad=deepcopy(self.artifacts['correction.json']);bad[field]=value
            (self.source/'correction.json').write_text(json.dumps(bad))
            with self.subTest(field=field), self.assertRaises((ValueError,KeyError)):
                self.prepare()
            self.assertFalse(self.target.exists())

    def test_frozen_source_and_outcome_tampering(self):
        self.pre['payload']['structured_pre_open_cards'][0]['predicted_low']=1
        self.write_inputs()
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.audit.exists())

    def test_receipt_provenance_binding(self):
        receipt=deepcopy(self.artifacts['receipt.json']);receipt['provenance']['pre']['revision']=7
        (self.source/'receipt.json').write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError,'RECEIPT_PIN_MISMATCH'):self.prepare()

    def test_hash_mismatch(self):
        for name in ('index.html','line.txt','email.txt'):
            old=(self.source/name).read_bytes();(self.source/name).write_bytes(old+b'bad')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError,'OUTPUT_HASH'):self.prepare()
            (self.source/name).write_bytes(old)

    def test_html_tamper_even_with_rehashed_receipt(self):
        page=self.artifacts['index.html'].replace('40.00','999.00')
        self.assertNotEqual(page,self.artifacts['index.html'])
        (self.source/'index.html').write_text(page)
        receipt=deepcopy(self.artifacts['receipt.json']);receipt['html_sha256']=pub.sha(page.encode())
        (self.source/'receipt.json').write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError,'RECEIPT_PIN_MISMATCH'):self.prepare()

    def test_success_backups_mode_and_idempotency(self):
        result=self.publish()
        self.assertEqual(result['status'],'PUBLISHED')
        self.assertFalse(result['http_verified'])
        self.assertEqual(self.target.stat().st_mode & 0o777,0o644)
        evidence=self.audit/self.id
        self.assertEqual((evidence/'original.html').read_bytes(),self.original_bytes)
        self.assertEqual((evidence/'latest.before.html').read_bytes(),self.original_bytes)
        self.assertEqual(json.loads((evidence/'original.snapshot.json').read_text()),self.post)
        self.assertEqual(self.original.read_bytes(),self.original_bytes)
        self.assertEqual(self.latest.read_bytes(),self.original_bytes)
        stamp=self.target.stat().st_mtime_ns
        self.assertTrue(self.publish()['idempotent'])
        self.assertEqual(stamp,self.target.stat().st_mtime_ns)

    def test_restrictive_umask_public_mode(self):
        import os
        previous=os.umask(0o077)
        try:
            self.publish()
        finally:
            os.umask(previous)
        path=self.target.parent
        while path != self.static:
            self.assertEqual(path.stat().st_mode & 0o777,0o755)
            path=path.parent
        self.assertEqual(self.target.stat().st_mode & 0o777,0o644)

    def test_existing_private_directory_not_chmodded(self):
        self.target.parent.mkdir(parents=True)
        self.target.parent.chmod(0o700)
        with self.assertRaisesRegex(ValueError,'PUBLIC_DIRECTORY_MODE'):self.publish()
        self.assertEqual(self.target.parent.stat().st_mode & 0o777,0o700)
        self.assertFalse(self.target.exists())

    def test_newer_latest_never_replaced(self):
        newer=self.original_bytes.replace(b'2099-04-07',b'2099-04-08')
        self.latest.write_bytes(newer)
        self.publish()
        self.assertEqual(self.latest.read_bytes(),newer)
        self.assertEqual(self.original.read_bytes(),self.original_bytes)

    def test_route_collision(self):
        self.target.parent.mkdir(parents=True);self.target.write_text('foreign')
        with self.assertRaisesRegex(ValueError,'ROUTE_COLLISION'):self.publish()
        self.assertEqual(self.target.read_text(),'foreign')
        self.assertFalse((self.audit/self.id).exists())

    def test_partial_write_no_publication(self):
        def broken(source,target):
            target.write_bytes(b'partial');raise OSError('fixture')
        with patch.object(pub,'_atomic_copy',side_effect=broken), self.assertRaises(OSError):self.publish()
        self.assertFalse(self.target.exists())
        self.assertEqual(json.loads((self.audit/self.id/'failed.json').read_text())['status'],'BLOCKED')
        self.assertEqual(self.latest.read_bytes(),self.original_bytes)
        self.assertFalse(list(self.target.parent.glob('.correction-*')))

    def test_bad_staged_hash_rejected(self):
        with patch.object(pub,'_atomic_copy',side_effect=lambda s,t:t.write_bytes(b'bad')), self.assertRaisesRegex(ValueError,'STAGING_HASH'):self.publish()
        self.assertFalse(self.target.exists())

    def test_verification_failure_rolls_back_only_owned_route(self):
        with self.assertRaisesRegex(ValueError,'PUBLIC_VERIFICATION'):self.publish(verify_public=lambda *a:False)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.original.read_bytes(),self.original_bytes)
        self.assertEqual(self.latest.read_bytes(),self.original_bytes)
        failed=json.loads((self.audit/self.id/'failed.json').read_text())
        self.assertTrue(failed['rolled_back'])
        self.assertTrue((self.audit/self.id/'published.html').exists())
        with self.assertRaisesRegex(ValueError,'PRIOR_ATTEMPT'):self.publish()

    def test_does_not_remove_foreign_replacement_on_rollback(self):
        def replaced(*args):
            self.target.unlink();self.target.write_text('foreign-new');return False
        with self.assertRaises(ValueError):self.publish(verify_public=replaced)
        self.assertEqual(self.target.read_text(),'foreign-new')
        self.assertFalse(json.loads((self.audit/self.id/'failed.json').read_text())['rolled_back'])

    def test_original_hash_and_identity_guard(self):
        self.original.write_bytes(self.original_bytes+b'changed')
        with self.assertRaisesRegex(ValueError,'ORIGINAL_HASH'):self.publish()
        self.assertFalse(self.audit.exists())

    def test_latest_changed_during_stage_blocks(self):
        real=pub._atomic_copy
        def changed(s,t):
            real(s,t);self.latest.write_bytes(b'natural-newer')
        with patch.object(pub,'_atomic_copy',side_effect=changed), self.assertRaisesRegex(ValueError,'LATEST_CHANGED'):self.publish()
        self.assertFalse(self.target.exists())
        self.assertEqual(self.latest.read_bytes(),b'natural-newer')

    def test_symlink_denied(self):
        self.target.parent.mkdir(parents=True);self.target.symlink_to(self.latest)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):self.publish()
        self.assertEqual(self.latest.read_bytes(),self.original_bytes)

    def test_concurrent_invocation_lock(self):
        import fcntl
        self.target.parent.mkdir(parents=True)
        with (self.target.parent/'.publication.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.publish()
        self.assertFalse(self.target.exists())

    def test_private_audit_not_public(self):
        with self.assertRaisesRegex(ValueError,'PRIVATE_AUDIT'):
            pub.publish(self.source,self.pre_path,self.post_path,expected_id=self.id, expected_receipt_hash=self.receipt_pin,static_root=self.static,
                        original_html=self.original,expected_original_hash=pub.sha(self.original_bytes),audit_root=self.static/'backup')

    def test_local_http_200_exact_bytes(self):
        handler=partial(QuietHandler,directory=str(self.static))
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        worker=Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            result=self.publish(verify_public=http_verifier(f'http://127.0.0.1:{server.server_port}'))
            self.assertTrue(result['http_verified'])
        finally:
            server.shutdown();server.server_close();worker.join(timeout=2)

    def test_cli_defaults_preview_no_send(self):
        cli=Path(__file__).parents[1]/'scripts/orchestrator/publish_tw_correction_dashboard.py'
        command=[sys.executable,str(cli),'--source-dir',str(self.source),'--pre-open-input',str(self.pre_path),
                 '--post-close-input',str(self.post_path),'--expected-correction-id',self.id,'--expected-receipt-hash',self.receipt_pin]
        result=subprocess.run(command,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'PREVIEW_ONLY')
        self.assertFalse(self.audit.exists());self.assertFalse(self.target.exists())
        result=subprocess.run(command+['--send'],capture_output=True,text=True,timeout=20)
        self.assertNotEqual(result.returncode,0)


if __name__=='__main__':unittest.main()
