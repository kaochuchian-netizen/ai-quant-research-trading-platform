"""Synthetic inode/alias adversarial fixtures; no Production inputs."""
from copy import deepcopy
import fcntl
import json
import os
import unittest
from unittest.mock import patch
from app.dashboard import correction_publication as pub
from app.dashboard.trusted_static_root import StaticRoot, VERSION, identity, load_policy, parts
from tests import test_ai_dev_284 as fixtures


class TrustedRootTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CorrectionPublicationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.alias = self.f.root / 'static-alias'
        self.alias.symlink_to(self.f.static)
        self.policy = dict(schema_version=VERSION, logical_root=str(self.alias),
                           physical_root=str(self.f.static), alias_identity=identity(self.alias.lstat()),
                           root_identity=identity(self.f.static.stat()))

    def publish(self, **kwargs):
        f=self.f
        return pub.publish(f.source,f.pre_path,f.post_path,expected_id=f.id,expected_receipt_hash=f.receipt_pin,
                           static_root=self.alias,original_html=self.alias/f.original.name,
                           expected_original_hash=pub.sha(f.original_bytes),audit_root=f.audit,
                           trusted_root=self.policy,**kwargs)

    def test_allowed_alias_idempotent_original_latest_preserved(self):
        first=self.publish();second=self.publish()
        self.assertEqual(first['status'],'PUBLISHED');self.assertTrue(second['idempotent'])
        self.assertEqual(first['root_trust']['alias'],self.policy['alias_identity'])
        self.assertEqual(self.f.original.read_bytes(),self.f.original_bytes)
        self.assertEqual(self.f.latest.read_bytes(),self.f.original_bytes)
        self.assertEqual(self.f.target.stat().st_mode & 0o777,0o644)

    def test_no_policy_still_rejects_alias(self):
        self.policy=None
        with self.assertRaisesRegex(ValueError,'SYMLINK'):self.publish()
        self.assertFalse(self.f.audit.exists())

    def test_policy_mismatches_fail_closed(self):
        original=deepcopy(self.policy)
        for key in ('schema_version','logical_root','physical_root','alias_identity','root_identity'):
            self.policy=deepcopy(original)
            if key.endswith('identity'):self.policy[key]['inode'] += 1
            else:self.policy[key]='invalid'
            with self.subTest(key=key),self.assertRaises((ValueError,OSError)):self.publish()
        self.assertFalse(self.f.audit.exists())

    def test_unknown_policy_key(self):
        self.policy['allow_all_symlinks']=True
        with self.assertRaisesRegex(ValueError,'CONFIG_SCHEMA'):self.publish()

    def test_chained_symlink_rejected(self):
        second=self.f.root/'second';second.symlink_to(self.f.static)
        self.alias.unlink();self.alias.symlink_to(second)
        self.policy['alias_identity']=identity(self.alias.lstat())
        with self.assertRaisesRegex(ValueError,'ALIAS_MISMATCH'):self.publish()

    def test_descendant_symlink_rejected(self):
        folder=self.f.static/'dashboard'
        moved=self.f.root/'moved-dashboard';folder.rename(moved);folder.symlink_to(moved)
        with self.assertRaises(OSError):self.publish()
        self.assertFalse(self.f.target.exists())

    def test_path_traversal(self):
        for relative in ('../escape','a/../escape','/escape','a//b'):
            with self.subTest(path=relative),self.assertRaises(ValueError):parts(relative)
        self.policy['physical_root']=str(self.f.static)+'/../public'
        with self.assertRaisesRegex(ValueError,'TRAVERSAL'):self.publish()

    def test_alias_swap_during_staging(self):
        real=pub._atomic_copy
        other=self.f.root/'foreign';other.mkdir()
        def swap(s,t):
            real(s,t);self.alias.unlink();self.alias.symlink_to(other)
        with patch.object(pub,'_atomic_copy',side_effect=swap),self.assertRaises(ValueError):self.publish()
        self.assertFalse(self.f.target.exists());self.assertEqual(list(other.iterdir()),[])

    def test_root_replacement_during_staging(self):
        real=pub._atomic_copy
        old=self.f.root/'old-public'
        def swap(s,t):
            real(s,t);self.f.static.rename(old);self.f.static.mkdir()
        with patch.object(pub,'_atomic_copy',side_effect=swap),self.assertRaises(ValueError):self.publish()
        self.assertFalse((old/self.f.target.relative_to(self.f.static)).exists())
        self.assertEqual(list(self.f.static.iterdir()),[])

    def test_alias_swap_after_link_rolls_back_pinned_inode(self):
        real=os.link
        other=self.f.root/'foreign';other.mkdir()
        def swap(*a,**kw):
            real(*a,**kw);self.alias.unlink();self.alias.symlink_to(other)
        with patch.object(pub.os,'link',side_effect=swap),self.assertRaises(ValueError):self.publish()
        self.assertFalse(self.f.target.exists());self.assertEqual(list(other.iterdir()),[])
        self.assertTrue(json.loads((self.f.audit/self.f.id/'failed.json').read_text())['rolled_back'])

    def test_child_swap_after_link_rolls_back_original_directory(self):
        real=os.link
        old=self.f.root/'old-child'
        def swap(*a,**kw):
            real(*a,**kw);self.f.target.parent.rename(old);self.f.target.parent.mkdir()
        with patch.object(pub.os,'link',side_effect=swap),self.assertRaises(ValueError):self.publish()
        self.assertFalse((old/'index.html').exists());self.assertEqual(list(self.f.target.parent.iterdir()),[])

    def test_partial_copy_failure(self):
        def partial(s,t):
            t.write_bytes(b'partial');raise OSError('synthetic interrupted copy')
        with patch.object(pub,'_atomic_copy',side_effect=partial),self.assertRaises(OSError):self.publish()
        self.assertFalse(self.f.target.exists())
        self.assertEqual(self.f.latest.read_bytes(),self.f.original_bytes)

    def test_failed_http_rolls_back_and_requires_review(self):
        with self.assertRaisesRegex(ValueError,'PUBLIC_VERIFICATION'):self.publish(verify_public=lambda *a:False)
        self.assertFalse(self.f.target.exists())
        with self.assertRaisesRegex(ValueError,'PRIOR_ATTEMPT'):self.publish()

    def test_shared_lock_alias_and_physical(self):
        self.f.target.parent.mkdir(parents=True)
        with (self.f.target.parent/'.publication.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.publish()
            with self.assertRaises(BlockingIOError):self.f.publish()
        self.assertFalse(self.f.target.exists())

    def test_lock_symlink_rejected(self):
        self.f.target.parent.mkdir(parents=True)
        (self.f.target.parent/'.publication.lock').symlink_to(self.f.original)
        with self.assertRaises(OSError):self.publish()
        self.assertEqual(self.f.original.read_bytes(),self.f.original_bytes)

    def test_read_fifo_does_not_hang(self):
        os.mkfifo(self.f.static/'fifo')
        with StaticRoot(self.alias,self.policy) as root:
            with self.assertRaisesRegex(ValueError,'NONREGULAR'):root.read('fifo')

    def test_trust_file_permissions_and_symlink(self):
        path=self.f.root/'trust.json';path.write_text(json.dumps(self.policy));path.chmod(0o600)
        self.assertEqual(load_policy(path),self.policy)
        path.chmod(0o666)
        with self.assertRaisesRegex(ValueError,'PERMISSIONS'):load_policy(path)
        alias=self.f.root/'trust-alias';alias.symlink_to(path)
        with self.assertRaises(OSError):load_policy(alias)

    def test_identity_guard_unchanged(self):
        self.f.original.write_bytes(b'wrong identity')
        with self.assertRaisesRegex(ValueError,'ORIGINAL_HASH'):self.publish()
        self.assertFalse(self.f.audit.exists())

    def test_concurrent_publish_one_owner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        entered,release=Event(),Event()
        real=pub._atomic_copy
        def pause(s,t):
            real(s,t);entered.set()
            if not release.wait(5):raise TimeoutError('synthetic test synchronization')
        with ThreadPoolExecutor(max_workers=1) as pool,patch.object(pub,'_atomic_copy',side_effect=pause):
            first=pool.submit(self.publish)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(BlockingIOError):self.publish()
            finally:release.set()
            self.assertEqual(first.result(timeout=5)['status'],'PUBLISHED')
        self.assertTrue(self.publish()['idempotent'])

    def test_cli_trusted_preview_has_no_writes(self):
        import subprocess
        import sys
        from pathlib import Path
        policy=self.f.root/'root-policy.json';policy.write_text(json.dumps(self.policy));policy.chmod(0o600)
        command=[sys.executable,str(Path(__file__).parents[1]/'scripts/orchestrator/publish_tw_correction_dashboard.py'),
                 '--source-dir',str(self.f.source),'--pre-open-input',str(self.f.pre_path),
                 '--post-close-input',str(self.f.post_path),'--expected-correction-id',self.f.id,'--expected-receipt-hash',self.f.receipt_pin,
                 '--static-root',str(self.alias),'--trusted-static-root-config',str(policy)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'PREVIEW_ONLY')
        self.assertFalse(self.f.audit.exists());self.assertFalse(self.f.target.exists())

    def test_foreign_staging_replacement_is_not_deleted(self):
        real=os.link
        replaced=[]
        def replace(s,t,**kw):
            os.unlink(s,dir_fd=kw['src_dir_fd'])
            fd=os.open(s,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600,dir_fd=kw['src_dir_fd'])
            os.write(fd,b'foreign');os.close(fd)
            replaced.append(self.f.target.parent/s)
            real(s,t,**kw)
        with patch.object(pub.os,'link',side_effect=replace),self.assertRaises(ValueError):self.publish()
        self.assertEqual(replaced[0].read_bytes(),b'foreign')
        self.assertEqual(self.f.target.read_bytes(),b'foreign')

    def test_special_lock_file_rejected(self):
        self.f.target.parent.mkdir(parents=True)
        os.mkfifo(self.f.target.parent/'.publication.lock')
        with self.assertRaisesRegex(ValueError,'NONREGULAR_LOCK'):self.publish()
