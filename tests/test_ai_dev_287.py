"""Entirely synthetic deployment/admission cases; no Production fixtures."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.reports.tw_consumer_compatibility import deployment_preflight
from app.reports.tw_delivery_evaluation import KEY
from tests.test_ai_dev_283 import inputs, seal

SHA = "a" * 40
SESSION = "2099-04-07"


class DeploymentCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'tw/pre_open_0700' / SESSION
        self.folder.mkdir(parents=True)
        self.path = self.folder / 'revision-0001.json'
        self.pre, _ = inputs(current=True)

    def run_gate(self, pre=None, **kwargs):
        pre = pre or self.pre
        self.path.write_text(json.dumps(pre))
        before = self.path.read_bytes()
        result = deployment_preflight(self.root, session=SESSION,
                expected_snapshot_id=pre['snapshot_id'], candidate_sha=SHA,
                head_sha=kwargs.get('head_sha', SHA))
        self.assertEqual(before, self.path.read_bytes())
        return result

    def assert_blocked(self, pre, code):
        result = self.run_gate(pre)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['reason_code'], code)

    def test_current_snapshot_pass_no_recomputation(self):
        with patch('app.reports.tw_delivery_evaluation.evaluate', side_effect=AssertionError('no evaluate')):
            result = self.run_gate()
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(result['production_write'])
        self.assertFalse(result['evaluation_executed'])
        self.assertEqual(result['registry_gate'], 'NOT_EXECUTED')

    def test_legacy_blocks_not_automatically_adapted(self):
        pre, _ = inputs()
        self.assert_blocked(pre, 'DELIVERY_PROJECTION_SCHEMA')

    def test_one_missing_projection_blocks_whole_deployment(self):
        del self.pre['payload']['structured_pre_open_cards'][-1][KEY]
        self.assert_blocked(seal(self.pre), 'DELIVERY_PROJECTION_SCHEMA')

    def test_wrong_projection_schema(self):
        self.pre['payload']['structured_pre_open_cards'][0][KEY]['schema_version'] = 'unknown_v9'
        self.assert_blocked(seal(self.pre), 'DELIVERY_PROJECTION_SCHEMA')

    def test_modified_payload_hash(self):
        self.pre['payload']['tracking_symbols'].append('9999')
        self.assert_blocked(self.pre, 'DELIVERY_SNAPSHOT_HASH')

    def test_projection_hash_mismatch(self):
        self.pre['payload']['structured_pre_open_cards'][0][KEY]['direction'] = 'neutral'
        self.assert_blocked(seal(self.pre), 'DELIVERY_PROJECTION_DIGEST')

    def test_wrong_market(self):
        self.pre['market'] = 'US'
        self.assert_blocked(seal(self.pre), 'DELIVERY_SNAPSHOT_IDENTITY')

    def test_cross_day_no_fallback(self):
        self.pre['effective_trading_date'] = '2099-04-06'
        self.assert_blocked(seal(self.pre), 'DELIVERY_SNAPSHOT_IDENTITY')

    def test_missing_today_does_not_use_yesterday(self):
        yesterday = self.folder.parent / '2099-04-06'
        yesterday.mkdir(); (yesterday / self.path.name).write_text(json.dumps(self.pre))
        result = deployment_preflight(self.root, session=SESSION, expected_snapshot_id=self.pre['snapshot_id'],candidate_sha=SHA,head_sha=SHA)
        self.assertEqual(result['reason_code'], 'DEPLOY_SAME_SESSION_SNAPSHOT_MISSING')

    def test_ambiguous_revisions(self):
        (self.folder / 'revision-0002.json').write_text('{}')
        self.assert_blocked(self.pre, 'DEPLOY_SNAPSHOT_REVISION_AMBIGUOUS')

    def test_wrong_revision_path(self):
        self.pre['revision'] = 2
        self.assert_blocked(seal(self.pre), 'DEPLOY_REVISION_PATH_MISMATCH')

    def test_manual_source_not_allowed(self):
        self.pre['run_kind'] = 'manual'
        self.assertEqual(self.run_gate(seal(self.pre))['status'], 'BLOCKED')

    def test_candidate_sha_mismatch(self):
        self.assertEqual(self.run_gate(head_sha='b'*40)['reason_code'],'DEPLOY_CANDIDATE_SHA_MISMATCH')

    def test_dirty_candidate_blocks(self):
        self.assertEqual(self.run_gate(head_sha='DIRTY_OR_UNKNOWN_CANDIDATE')['status'],'BLOCKED')

    def test_independent_snapshot_pin(self):
        self.path.write_text(json.dumps(self.pre))
        result=deployment_preflight(self.root,session=SESSION,expected_snapshot_id='0'*64,candidate_sha=SHA,head_sha=SHA)
        self.assertEqual(result['reason_code'],'DEPLOY_SNAPSHOT_ID_MISMATCH')

    def test_pin_required(self):
        self.path.write_text(json.dumps(self.pre))
        result=deployment_preflight(self.root,session=SESSION,expected_snapshot_id=None,candidate_sha=SHA,head_sha=SHA)
        self.assertEqual(result['reason_code'],'DEPLOY_EXPECTED_ID_REQUIRED')

    def test_dynamic_universe(self):
        for count in (8,15,30):
            pre,_=inputs(count,current=True)
            result=self.run_gate(pre)
            self.assertEqual(result['symbol_count'],count)
            self.assertEqual(result['symbols'][0],'009991')

    def test_symlink_rejected(self):
        outside=self.root/'elsewhere.json';outside.write_text(json.dumps(self.pre));self.path.symlink_to(outside)
        result=deployment_preflight(self.root,session=SESSION,expected_snapshot_id=self.pre['snapshot_id'],candidate_sha=SHA,head_sha=SHA)
        self.assertEqual(result['reason_code'],'DEPLOY_SNAPSHOT_SYMLINK_OR_PATH_ESCAPE')

    def test_invalid_json_not_echoed(self):
        self.path.write_text('private input not JSON')
        result=deployment_preflight(self.root,session=SESSION,expected_snapshot_id=self.pre['snapshot_id'],candidate_sha=SHA,head_sha=SHA)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertNotIn('private input',json.dumps(result))

    def test_source_changed_during_check(self):
        self.path.write_text(json.dumps(self.pre));raw=self.path.read_bytes()
        with patch.object(Path,'read_bytes',side_effect=[raw,b'changed']):
            result=deployment_preflight(self.root,session=SESSION,expected_snapshot_id=self.pre['snapshot_id'],candidate_sha=SHA,head_sha=SHA)
        self.assertEqual(result['reason_code'],'DEPLOY_SOURCE_CHANGED')

class NativeEntryTests(unittest.TestCase):
    def test_native_mode_blocks_before_any_registry_or_platform_activity(self):
        from types import SimpleNamespace
        from scripts.orchestrator import validate_post_merge_status as native
        import contextlib, io
        for status, exit_code in [('BLOCKED',2),('PASS',0)]:
            args=SimpleNamespace(repo_root='.',tw_deployment_preflight=Path('/synthetic'),
                expected_pre_open_id='0'*64,expected_candidate_sha=SHA,pretty=False)
            with patch.object(native,'parse_args',return_value=args), \
                 patch.object(native.subprocess,'run',side_effect=[SimpleNamespace(returncode=0,stdout=SHA),SimpleNamespace(returncode=0,stdout='')]), \
                 patch('app.reports.tw_consumer_compatibility.deployment_preflight',return_value={'status':status,'registry_gate':'NOT_EXECUTED'}) as check, \
                 patch.object(native,'build_platform_status_report',side_effect=AssertionError('must not invoke platform/registry')), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(native.main(),exit_code)
                self.assertEqual(check.call_args.kwargs['head_sha'],SHA)
                self.assertEqual(check.call_args.kwargs['candidate_sha'],SHA)


if __name__ == "__main__": unittest.main()
