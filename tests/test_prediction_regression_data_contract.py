"""Synthetic-only contract cases; no clients, market APIs or score engines."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from app.evaluation.prediction_regression_contract import (
    CONTRACT, ROOT, canonical_json, contract_errors, document_contract_block,
    record_hash, resolve_sessions, safety_errors, schema_errors, stamp, validate_record,
)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads(CONTRACT.read_text())
        self.f = json.loads((ROOT / 'tests/fixtures/prediction_regression_contract_v1.json').read_text())
        self.records = self.f['records']

    def row(self, entity):
        return copy.deepcopy(next(r for r in self.records if r['entity'] == entity))

    def errors(self, row, history=None):
        return validate_record(stamp(row), self.c, self.records if history is None else history, self.f['sessions'])

    def test_contract_complete(self):
        self.assertEqual(contract_errors(self.c), [])

    def test_every_entity_fixture(self):
        for row in self.records:
            with self.subTest(entity=row['entity']):
                self.assertEqual(self.errors(row, [r for r in self.records if r != row]), [])

    def test_required_field(self):
        row = self.row('prediction_snapshot'); del row['data']['model_version']
        self.assertIn('data:missing:model_version', self.errors(row))

    def test_extra_raw_payload(self):
        row = self.row('prediction_snapshot'); row['data']['raw_payload'] = {'price': 123}
        self.assertTrue(self.errors(row))

    def test_boolean_is_not_number(self):
        row = self.row('prediction_snapshot'); row['data']['confidence'] = True
        self.assertIn('data.confidence:type', self.errors(row))

    def test_probability_scale(self):
        row = self.row('prediction_snapshot'); row['data']['confidence'] = 75
        self.assertIn('data.confidence:range', self.errors(row))

    def test_non_finite(self):
        self.assertTrue(schema_errors(float('nan'), {'type': 'number'}))

    def test_missing_timezone(self):
        row = self.row('feature_snapshot'); row['data']['as_of'] = '2026-09-23T06:00:00'
        self.assertIn('data.as_of:format', self.errors(row))

    def test_future_feature(self):
        row = self.row('feature_snapshot'); row['data']['as_of'] = '2026-09-24T06:00:00+08:00'
        self.assertIn('future_data_leakage', self.errors(row))

    def test_late_available_feature(self):
        row = self.row('feature_snapshot'); row['data']['available_at'] = '2026-09-23T08:00:00+08:00'
        self.assertIn('future_data_leakage', self.errors(row))

    def test_eligible_requires_feature_binding(self):
        row = self.row('prediction_snapshot'); row['data']['status'] = 'ELIGIBLE'
        self.assertIn('feature_binding_missing', self.errors(row, []))

    def test_unknown_original_prediction_time_is_pending(self):
        row = self.row('prediction_snapshot'); row['data']['generated_at'] = None
        self.assertEqual(self.errors(row, []), [])
        row['data']['status'] = 'ELIGIBLE'
        self.assertIn('incomplete_prediction', self.errors(row, []))

    def test_unknown_feature_time_is_pending(self):
        row = self.row('feature_snapshot'); row['data']['available_at'] = None
        self.assertEqual(self.errors(row, []), [])
        row['data']['status'] = 'ELIGIBLE'
        self.assertIn('missing_feature_time', self.errors(row, []))

    def test_inverted_range(self):
        row = self.row('prediction_snapshot'); row['data'].update(range_low=120, range_high=100)
        self.assertIn('inverted_range', self.errors(row))

    def test_premature_outcome(self):
        row = self.row('market_outcome'); row['data']['observed_at'] = '2026-09-23T09:00:00+08:00'
        self.assertIn('premature_outcome', self.errors(row))

    def test_weights_total(self):
        self.c['weights_percent']['prediction']['trend'] = 44
        self.assertIn('weight_sum', contract_errors(self.c))

    def test_weights_redistribution_rejected(self):
        self.c['weights_percent']['composite'].update(prediction=50, improvement=0, strategy=50)
        self.assertIn('weights', contract_errors(self.c))

    def test_na_pending(self):
        row = self.row('daily_scorecard'); row['data']['improvement_status'] = 'N/A'
        self.assertEqual(self.errors(row, []), [])
        row['data'].update(composite_status='ELIGIBLE', composite_score=0)
        self.assertIn('na_requires_pending', self.errors(row, []))

    def test_no_scores_in_phase_a(self):
        row = self.row('daily_scorecard'); row['data']['composite_score'] = 50
        self.assertIn('phase_a_no_scores', self.errors(row))

    def test_sample_shortfall(self):
        row = self.row('daily_scorecard')
        row['data'].update(prediction_status='ELIGIBLE', improvement_status='ELIGIBLE', strategy_status='ELIGIBLE')
        self.assertIn('insufficient_sessions', self.errors(row))

    def test_no_duplicate_session(self):
        row = self.row('daily_scorecard'); row['data']['three_session_dates'] = ['2026-09-23'] * 3
        self.assertIn('duplicate_session', self.errors(row))

    def test_immutable_revision(self):
        row = self.row('prediction_snapshot'); row['data']['trend'] = 'DOWN'
        self.assertIn('immutable_revision_conflict', self.errors(row))

    def test_idempotent_replay(self):
        row = self.row('prediction_snapshot'); self.assertEqual(self.errors(row), [])

    def test_revision_append(self):
        row = self.row('prediction_snapshot'); row['revision'] = 2; row['supersedes_hash'] = self.row('prediction_snapshot')['content_hash']
        self.assertEqual(self.errors(row), [])

    def test_revision_skip(self):
        row = self.row('prediction_snapshot'); row['revision'] = 3; row['supersedes_hash'] = '0' * 64
        self.assertIn('revision_predecessor', self.errors(row))

    def test_hash_tamper(self):
        row = self.row('prediction_snapshot'); row['content_hash'] = '0' * 64
        self.assertIn('content_hash', validate_record(row, self.c))

    def test_history_hash_tamper(self):
        prior = self.row('prediction_snapshot'); prior['content_hash'] = '0' * 64
        self.assertIn('history_hash', self.errors(self.row('feature_snapshot'), [prior]))

    def test_secret_source_reference(self):
        row = self.row('feature_snapshot'); row['source_refs'][0]['source_path'] = '.env'
        self.assertIn('unsafe_source_reference', self.errors(row, []))

    def test_complete_outcome_shape(self):
        row = self.row('market_outcome'); row['data'].update(open=100, high=90, low=80, close=95)
        self.assertIn('invalid_ohlc', self.errors(row, []))

    def test_report_link(self):
        prior = self.row('report_manifest'); row = copy.deepcopy(prior)
        row['record_id'] = 'synthetic-next-report'; row['data'].update(report_id='synthetic-next-report', report_date='2026-09-24', cutoff_at='2026-09-24T17:00:00+08:00', chain_status='LINKED', predecessor_report_id=prior['data']['report_id'], predecessor_report_date='2026-09-23', predecessor_hash=prior['content_hash'], market_session_dates={'TW':'2026-09-23','US':'2026-09-23'})
        self.assertEqual(self.errors(row, [prior]), [])
        row['data']['predecessor_hash'] = '0' * 64
        self.assertIn('report_predecessor', self.errors(row, [prior]))

    def test_missing_predecessor_pending(self):
        row = self.row('report_manifest'); row['data']['chain_status'] = 'MISSING_PREDECESSOR'
        self.assertEqual(self.errors(row, []), [])
        row['data']['status'] = 'READY'
        self.assertIn('missing_predecessor_not_pending', self.errors(row, []))

    def test_report_exact_cutoff(self):
        row = self.row('report_manifest'); row['data']['cutoff_at'] = '2026-09-23T16:00:00+08:00'
        self.assertIn('report_cutoff', self.errors(row, []))

    def test_tw_us_cutoff(self):
        self.assertEqual(resolve_sessions('2026-09-23', self.f['sessions'], '2026-09-23T17:00:00+08:00'), {'TW':'2026-09-23','US':'2026-09-22'})

    def test_calendar_coverage(self):
        with self.assertRaisesRegex(ValueError, 'coverage'):
            resolve_sessions('2026-09-23', self.f['sessions'], '2026-09-23T16:59:59+08:00')

    def test_holiday_weekend_carry(self):
        cal=[{'market':m,'session_date':'2026-09-18','open_at':'2026-09-18T09:30:00'+z,'close_at':'2026-09-18T16:00:00'+z} for m,z in [('TW','+08:00'),('US','-04:00')]]
        self.assertEqual(resolve_sessions('2026-09-20',cal,'2026-09-20T17:00:00+08:00'),{'TW':'2026-09-18','US':'2026-09-18'})

    def test_us_winter_and_early_close(self):
        cal=[{'market':'US','session_date':'2026-11-27','open_at':'2026-11-27T09:30:00-05:00','close_at':'2026-11-27T13:00:00-05:00'}]
        self.assertEqual(resolve_sessions('2026-11-28',cal,'2026-11-28T17:00:00+08:00')['US'],'2026-11-27')
        self.assertIsNone(resolve_sessions('2026-11-27',cal,'2026-11-27T17:00:00+08:00')['US'])

    def test_calendar_hash(self):
        row=self.row('report_manifest'); row['data']['calendar_hash']='0'*64
        self.assertIn('calendar_hash',self.errors(row,[]))

    def test_hindsight_separation(self):
        row=self.row('strategy_counterfactual');row['data'].update(frozen_signal_refs=['future-result'],hindsight_evidence_refs=['future-result'])
        self.assertIn('hindsight_feature_overlap',self.errors(row))

    def test_fix_approval(self):
        row=self.row('fix_ledger');row['data']['status']='IMPLEMENTED'
        self.assertIn('unapproved_fix',self.errors(row))

    def test_fix_time_order(self):
        row=self.row('fix_ledger');row['data'].update(approved_at='2026-09-23T06:00:00+08:00',effective_at='2026-09-23T05:00:00+08:00')
        self.assertIn('fix_chronology',self.errors(row,[]))

    def test_fix_maturity(self):
        row=self.row('fix_evaluation');row['data']['status']='ELIGIBLE'
        self.assertIn('immature_fix',self.errors(row))

    def test_no_auto_apply(self):
        row=self.row('fix_ledger');row['data']['auto_apply']=True
        self.assertIn('data.auto_apply:const',self.errors(row))

    def test_delivery_binding(self):
        row=self.row('delivery_ledger');row['data']['report_hash']='0'*64
        self.assertIn('delivery_report_binding',self.errors(row))

    def test_sent_requires_receipt(self):
        row=self.row('delivery_ledger');row['data']['result']='SENT'
        self.assertIn('missing_delivery_receipt',self.errors(row))

    def test_sensitive_content(self):
        for bad in [{'access_token':'synthetic'}, {'positions':[]}, {'raw_rows':[]}, {'note':'Bearer SYNTHETIC-NOT-A-REAL-TOKEN'}]:
            self.assertTrue(safety_errors(bad))

    def test_deterministic(self):
        row=self.row('feature_snapshot'); reordered=dict(reversed(list(row.items())))
        self.assertEqual(record_hash(row),record_hash(reordered))
        self.assertEqual(canonical_json(self.errors(row)),canonical_json(self.errors(row)))

    def test_document_contract_consistency(self):
        doc=(ROOT/self.c['document_path']).read_text()
        self.assertIn(document_contract_block(self.c),doc)
        for definition in self.c['metric_specs_v1'].values(): self.assertIn(definition,doc)

    def test_aggregate_inventory_only(self):
        data=json.loads((ROOT/self.c['inventory_path']).read_text())
        self.assertTrue(data['aggregate_only']);self.assertFalse(safety_errors(data))
        for family in data['families'].values():
            self.assertIsInstance(family['rows'],int)
            for stats in family['fields'].values():
                self.assertEqual(stats['denominator'],family['rows'])
                self.assertLessEqual(stats['missing_count'],stats['denominator'])

    def test_requirement_inventory_bindings(self):
        inventory=json.loads((ROOT/self.c['inventory_path']).read_text())['families']
        for row in self.c['requirements']:
            parts=row['inventory_ref'].split('.')
            self.assertIn(parts[0],inventory)
            if len(parts)==3:
                self.assertEqual(row['missingness'],inventory[parts[0]]['fields'][parts[2]])
                if row['classification']=='AVAILABLE':self.assertEqual(row['missingness']['missing_rate'],0)

    def test_inventory_read_only_deterministic(self):
        spec=importlib.util.spec_from_file_location('inventory',ROOT/'scripts/orchestrator/inventory_prediction_regression_data_contract_v1.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);before=list(root.iterdir());a=module.inventory(root);b=module.inventory(root)
            self.assertEqual(a,b);self.assertEqual(before,list(root.iterdir()))


if __name__ == '__main__':
    unittest.main()
