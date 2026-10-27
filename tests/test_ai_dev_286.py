"""Saved-bundle admission and publication lifecycle; entirely synthetic evidence."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.dashboard import correction_publication as pub
from tests import test_ai_dev_284 as fixtures


@contextmanager
def forbid_computation():
    """Actual call trace, including indirectly imported functions."""
    seen = []
    forbidden = {'correction', 'evaluate', 'evaluate_card', 'batch_gate', 'quality', 'freeze', 'bind_universe'}
    def trace(frame, event, arg):
        if event != 'call':
            return
        name, filename = frame.f_code.co_name, frame.f_code.co_filename
        if '/app/' in filename or '/scripts/orchestrator/' in filename:
            seen.append(name)
            if name in forbidden or name.startswith(('fetch', 'predict', 'render', 'send_', 'notify')):
                raise AssertionError('FORBIDDEN_COMPUTATION:' + name)
    old = sys.getprofile()
    sys.setprofile(trace)
    try:
        yield seen
    finally:
        sys.setprofile(old)


class VerifiedExistingTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CorrectionPublicationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_execution_trace_and_sources_unchanged(self):
        f = self.f
        before = {str(p): p.read_bytes() for p in f.source.iterdir()}
        with forbid_computation() as seen:
            plan = f.prepare()
            result = f.publish(verify_public=lambda *args: True)
        self.assertIn('verify_existing', seen)
        self.assertEqual(plan['verification_mode'], 'VERIFIED_EXISTING_NO_REEVALUATION')
        self.assertEqual(result['status'], 'PUBLISHED')
        self.assertEqual(before, {str(p): p.read_bytes() for p in f.source.iterdir()})

    def test_missing_saved_output_does_not_fallback(self):
        (self.f.source/'email.txt').unlink()
        with forbid_computation(), self.assertRaises(FileNotFoundError): self.f.prepare()
        self.assertFalse(self.f.audit.exists())

    def test_receipt_pin_required(self):
        with self.assertRaisesRegex(ValueError, 'RECEIPT_PIN_REQUIRED'):
            pub.prepare(self.f.source, self.f.pre_path, self.f.post_path, expected_id=self.f.id)

    def test_saved_quality_and_version_fail_closed(self):
        f = self.f
        for kind in ('quality', 'actual', 'identity', 'version', 'stages', 'side_effect'):
            receipt = deepcopy(f.artifacts['receipt.json'])
            if kind == 'quality': receipt['quality']['status'] = 'BLOCKED'
            if kind == 'actual': receipt['quality']['cards'][0]['actual']['high'] += 1
            if kind == 'identity': receipt['quality']['cards'][0]['prediction_identity'] = 'bad'
            if kind == 'version': receipt['schema_version'] = 'future_v9'
            if kind == 'stages': receipt['stages']['publication'] = 'EXECUTED'
            if kind == 'side_effect': receipt['database_write'] = True
            (f.source/'receipt.json').write_text(json.dumps(receipt))
            f.receipt_pin = pub.sha((f.source/'receipt.json').read_bytes())
            with self.subTest(kind=kind), forbid_computation(), self.assertRaises(ValueError): f.prepare()

    def test_preflight_never_writes(self):
        f = self.f
        before = {str(p):p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        result = f.publish(preflight_only=True)
        self.assertEqual(result['status'], 'READ_ONLY_PREFLIGHT')
        self.assertFalse(f.audit.exists())
        self.assertFalse(f.target.parent.exists())
        self.assertEqual(before, {str(p):p.read_bytes() for p in f.root.rglob('*') if p.is_file()})

    def test_permissions_fail_before_write(self):
        with patch.object(pub.os, 'access', return_value=False), self.assertRaisesRegex(ValueError, 'PERMISSION'):
            self.f.publish()
        self.assertFalse(self.f.audit.exists())

    def test_private_backup_permissions_fail_closed(self):
        self.f.audit.mkdir(mode=0o755)
        self.f.audit.chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'PRIVATE_AUDIT_PERMISSIONS'): self.f.publish()
        self.assertFalse(self.f.target.parent.exists())

    def test_disk_space_fail_before_write(self):
        fs = SimpleNamespace(f_bavail=0, f_frsize=4096, f_favail=0)
        with patch.object(pub.os, 'statvfs', return_value=fs), self.assertRaisesRegex(ValueError, 'SPACE'):
            self.f.publish()
        self.assertFalse(self.f.audit.exists())

    def test_persistent_transition_before_http(self):
        f = self.f
        def http(*args):
            root = f.audit/f.id
            for name,status in [('prepared','PREPARED'),('staged','STAGED'),('promoted','PUBLICATION_PENDING_HTTP')]:
                self.assertEqual(json.loads((root/(name+'.json')).read_text())['status'],status)
            self.assertFalse((root/'published.json').exists())
            return True
        f.publish(verify_public=http)
        self.assertTrue(json.loads((f.audit/f.id/'published.json').read_text())['http_verified'])

    def test_crash_after_link_blocks_retry(self):
        f = self.f
        with self.assertRaises(SystemExit):
            f.publish(verify_public=lambda *a: (_ for _ in ()).throw(SystemExit('synthetic crash')))
        self.assertTrue(f.target.exists())
        self.assertFalse((f.audit/f.id/'published.json').exists())
        with self.assertRaisesRegex(ValueError, 'ROUTE_COLLISION'): f.publish()

    def test_crash_before_link_blocks_retry(self):
        with patch.object(pub.os,'link',side_effect=SystemExit), self.assertRaises(SystemExit): self.f.publish()
        self.assertFalse(self.f.target.exists())
        with self.assertRaisesRegex(ValueError, 'PRIOR_ATTEMPT'): self.f.publish()

    def test_receipt_failure_rolls_back_only_owned_route(self):
        f = self.f
        record = pub._record
        def fail(path, data):
            if path.name == 'published.json': raise OSError('synthetic full disk')
            return record(path, data)
        with patch.object(pub,'_record',side_effect=fail), self.assertRaises(OSError): f.publish()
        self.assertFalse(f.target.exists())
        self.assertTrue(json.loads((f.audit/f.id/'failed.json').read_text())['rolled_back'])
        self.assertEqual(f.latest.read_bytes(),f.original_bytes)

    def test_prior_failure_marker_never_claims_success(self):
        self.f.publish()
        (self.f.audit/self.f.id/'failed.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'ROUTE_COLLISION'): self.f.publish()

    def test_http_cannot_mutate_sources_without_rejection(self):
        f=self.f
        def changed(*args):
            (f.source/'line.txt').write_text('changed externally')
            return True
        with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'): f.publish(verify_public=changed)
        self.assertFalse(f.target.exists())

    def test_source_symlink_swap_is_rejected_before_read(self):
        f=self.f
        copy=pub._atomic_copy
        foreign=f.root/'foreign';foreign.write_bytes((f.source/'line.txt').read_bytes())
        def swap(source,target):
            copy(source,target)
            (f.source/'line.txt').unlink(); (f.source/'line.txt').symlink_to(foreign)
        with patch.object(pub,'_atomic_copy',side_effect=swap), self.assertRaisesRegex(ValueError,'SYMLINK'):
            f.publish()
        self.assertFalse(f.target.exists())

    def test_target_swap_during_successful_http_is_not_success(self):
        f=self.f
        def changed(*args):
            f.target.unlink(); f.target.write_text('foreign')
            return True
        with self.assertRaisesRegex(ValueError,'PUBLIC_VERIFICATION'): f.publish(verify_public=changed)
        self.assertEqual(f.target.read_text(),'foreign')
        self.assertFalse((f.audit/f.id/'published.json').exists())

    def test_replaced_success_inode_blocks_idempotency(self):
        f=self.f
        f.publish()
        target=f.target.read_bytes()
        held=pub.os.open(f.target,pub.os.O_RDONLY)
        try:
            f.target.unlink();f.target.write_bytes(target)
            with self.assertRaisesRegex(ValueError,'PRIOR_ATTEMPT_IDENTITY'): f.publish()
        finally:pub.os.close(held)


if __name__ == '__main__':unittest.main()
