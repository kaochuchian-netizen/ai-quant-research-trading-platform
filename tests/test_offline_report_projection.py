"""251C synthetic fixtures reuse the unchanged 251B input factory and 251A schemas."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from test_offline_review_evaluators import improvement_fixtures
from app.evaluation.offline_review_evaluators import evaluate_stock, load_contract
from app.evaluation.offline_report_projection import (
    CONTRACT_VERSION, EVALUATOR_VERSION, ProjectionError, append_report, build_report,
    compare_reports, contract, digest, reference, validate_projection, validate_report,
)
from app.evaluation.prediction_regression_contract import canonical_json, stamp, validate_record

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/offline_report_projection_v1.json").read_text())


def inputs(day, post_metric=70):
    rows, context = improvement_fixtures()
    context["report_date"] = day
    context["calendar"]["coverage_through"] = "2026-09-26T00:00:00+08:00"
    for row in rows:
        for sample in row["fields"]["post_fix_cohort"]["value"]:
            sample["score"] = post_metric if post_metric is not None else 70
        if post_metric is None:
            row["fields"]["post_fix_cohort"]["classification"] = "MISSING"
    return {"source_kind": "SYNTHETIC", "rows": rows, "context": context}


def source(identity, content_hash, schema="synthetic_evidence_v1"):
    return {"source_path": "tests/fixtures/offline_report_projection_v1.json", "source_record_id": identity,
            "source_schema": schema, "content_hash": content_hash}


def ledgers(report_id, packet):
    template = json.loads((ROOT / "tests/fixtures/prediction_regression_contract_v1.json").read_text())
    selected = {k: deepcopy(next(r for r in template["records"] if r["entity"] == k))
                for k in ("finding_ledger", "fix_ledger", "fix_evaluation")}
    identity = {k: packet["context"][k] for k in ("market", "symbol", "strategy_id")}
    for r in selected.values():
        r.update(revision=1, supersedes_hash=None)
        r["data"].update(identity)
    finding = selected["finding_ledger"]
    finding["record_id"] = "synthetic-finding-record"
    finding["data"].update(finding_id="synthetic_finding", detected_at="2026-08-24T14:00:00+08:00",
        confirmed_at="2026-08-25T10:00:00+08:00", status="CONFIRMED", evaluation_refs=["synthetic-error-evaluation"],
        evidence_refs=["synthetic-error-evidence"])
    finding["source_refs"] = [source(name, digest({"synthetic": name})) for name in finding["data"]["evaluation_refs"] + finding["data"]["evidence_refs"]]
    finding = stamp(finding)
    fix = selected["fix_ledger"]
    fix["record_id"] = "synthetic-fix-record"
    fix["data"].update(fix_id="synthetic_fix", finding_ref=finding["record_id"], proposed_at="2026-08-25T10:30:00+08:00",
        approved_at="2026-08-25T11:00:00+08:00", effective_at="2026-08-25T12:00:00+08:00", baseline_refs=["synthetic-baseline"],
        change_ref="synthetic-change", status="IMPLEMENTED", auto_apply=False)
    fix["source_refs"] = [source(finding["record_id"], finding["content_hash"], finding["schema_version"])]
    fix = stamp(fix)
    evaluation = selected["fix_evaluation"]
    evaluation["record_id"] = "synthetic-fix-evaluation"
    evaluation["data"].update(fix_ref=fix["record_id"], evaluated_at=packet["context"]["report_date"] + "T16:00:00+08:00",
        d3_session="2026-08-28", d10_session="2026-09-09", d3_status="PENDING", d10_status="PENDING",
        recurrence_evidence_refs=["synthetic-recurrence"], status="PENDING", reason_codes=["SYNTHETIC_METADATA_ONLY"])
    result = evaluate_stock(packet["rows"], **packet["context"])
    evaluation["source_refs"] = [source(fix["record_id"], fix["content_hash"], fix["schema_version"]),
        source("evaluation:" + report_id, digest(result), EVALUATOR_VERSION)]
    evaluation = stamp(evaluation)
    records = [finding, fix, evaluation]
    refs = dict(zip(("finding", "fix", "evaluation"), (r["content_hash"] for r in records)))
    return records, refs


def artifact(report_id, packet, complete=True):
    rows, refs = ledgers(report_id, packet)
    if not complete:
        rows = [r for r in rows if r["entity"] != "fix_ledger"]
    return build_report(report_id, packet, evidence_records=rows, linkage_refs=refs)


class ProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_inputs = inputs(FIXTURE["predecessor_date"])
        cls.current_inputs = inputs(FIXTURE["current_date"])
        cls.previous_report = artifact(FIXTURE["predecessor_id"], cls.previous_inputs)
        cls.current_report = artifact(FIXTURE["current_id"], cls.current_inputs)

    def setUp(self):
        self.previous = deepcopy(self.previous_report)
        self.current = deepcopy(self.current_report)
        self.prev_inputs = deepcopy(self.previous_inputs)
        self.cur_inputs = deepcopy(self.current_inputs)
        self.pin = reference(self.previous)

    def result(self):
        return compare_reports(self.current, self.cur_inputs, self.previous, self.prev_inputs, expected_predecessor=self.pin)

    def assert_rejected(self, reason):
        result = self.result()
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["reason_codes"], [reason])
        self.assertIsNone(result["comparison"])

    def test_valid_predecessor_binding(self):
        result = self.result()
        self.assertEqual(result["status"], "COMPARABLE")
        self.assertEqual(result["predecessor_ref"], self.pin)
        self.assertEqual(result["current_ref"], reference(self.current))
        self.assertEqual(result["relationship"], "PREVIOUS_CALENDAR_REPORT")

    def test_predecessor_digest_mismatch(self):
        self.pin["content_hash"] = "0" * 64
        self.assert_rejected("PREDECESSOR_BINDING_MISMATCH")

    def test_missing_predecessor(self):
        result = compare_reports(self.current, self.cur_inputs)
        self.assertEqual(result["status"], "NO_PREDECESSOR")
        self.assertIsNone(result["comparison"])
        self.assertIsNone(result["predecessor_ref"])

    def test_pinned_but_unavailable_predecessor(self):
        result = compare_reports(self.current, self.cur_inputs, expected_predecessor=self.pin)
        self.assertEqual(result["reason_codes"], ["PINNED_PREDECESSOR_UNAVAILABLE"])
        self.assertIsNone(result["comparison"])

    def test_all_four_complete_chain_effects(self):
        for case in FIXTURE["effects"]:
            with self.subTest(effect=case["effect"]):
                packet = inputs(FIXTURE["current_date"], case["post_metric"])
                current = artifact(FIXTURE["current_id"], packet)
                result = compare_reports(current, packet, self.previous, self.prev_inputs, expected_predecessor=self.pin)
                self.assertEqual(result["evidence_chain"]["state"], case["chain"])
                self.assertEqual(result["realized_effect"]["state"], case["effect"])
                self.assertFalse(result["evidence_chain"]["success_claim"])
                self.assertFalse(result["production_ready"])

    def test_incomplete_chain_effect_exists(self):
        packet = inputs(FIXTURE["current_date"], 80)
        current = artifact(FIXTURE["current_id"], packet, complete=False)
        result = compare_reports(current, packet)
        self.assertEqual(result["evidence_chain"]["state"], "INCOMPLETE")
        self.assertEqual(result["realized_effect"]["state"], "POSITIVE")
        self.assertIn("MISSING_FIX", result["evidence_chain"]["reason_codes"])

    def test_no_lifecycle_mutation(self):
        before = canonical_json([self.current, self.previous, self.cur_inputs, self.prev_inputs])
        result = self.result()
        self.assertFalse(result["lifecycle_mutation"])
        self.assertEqual(result["evidence_chain"]["lifecycle_transition"], "NONE")
        self.assertEqual(before, canonical_json([self.current, self.previous, self.cur_inputs, self.prev_inputs]))

    def test_deterministic_replay(self):
        self.assertEqual(canonical_json(self.result()), canonical_json(self.result()))

    def test_malformed_projection_rejected(self):
        self.current["evaluation"] = {"total_score": 100}
        self.current = stamp(self.current)
        self.assert_rejected("EVALUATOR_REPLAY_MISMATCH")

    def test_unknown_field_rejected(self):
        self.current["unknown"] = 1
        self.current = stamp(self.current)
        self.assert_rejected("REPORT_SCHEMA_INVALID")

    def test_version_mismatch(self):
        self.previous["schema_version"] = "offline_evaluation_report_v2"
        self.assert_rejected("REPORT_VERSION_MISMATCH")

    def test_contract_version_mismatch(self):
        self.current["contract_version"] = "future_contract"
        self.assert_rejected("REPORT_VERSION_MISMATCH")

    def test_evaluator_version_mismatch(self):
        self.current["evaluator_version"] = "future_engine"
        self.assert_rejected("REPORT_VERSION_MISMATCH")

    def test_component_evidence_preservation(self):
        result = self.result()
        self.assertEqual(result["component_evidence"]["current"], self.current["evaluation"])
        self.assertEqual(result["component_evidence"]["predecessor"], self.previous["evaluation"])
        self.assertEqual(result["linkage_evidence"]["current"], self.current["evidence_records"])
        self.assertEqual(result["linkage_evidence"]["predecessor"], self.previous["evidence_records"])
        self.assertEqual(set(result["component_evidence"]["current"]["internal_evidence"]["evaluators"]), {"prediction", "improvement", "strategy"})

    def test_aggregate_cannot_overwrite_components(self):
        self.current["evaluation"]["user_facing"]["improvement_accuracy_score"]["score"] = 100
        self.current = stamp(self.current)
        self.assert_rejected("EVALUATOR_REPLAY_MISMATCH")

    def test_component_tampering_rehashed_still_rejected(self):
        self.current["evaluation"]["internal_evidence"]["evaluators"]["improvement"]["component_scores"]["d3_effect"] = 100
        self.current = stamp(self.current)
        self.assert_rejected("EVALUATOR_REPLAY_MISMATCH")

    def test_70_neutral_not_positive_from_total(self):
        result = self.result()
        self.assertEqual(result["component_evidence"]["current"]["user_facing"]["improvement_accuracy_score"]["score"], 70)
        self.assertEqual(result["realized_effect"]["state"], "NEUTRAL")

    def test_251a_score_guard_unchanged(self):
        f=json.loads((ROOT / "tests/fixtures/prediction_regression_contract_v1.json").read_text())
        row=deepcopy(next(r for r in f["records"] if r["entity"] == "daily_scorecard"))
        row["data"]["composite_score"] = 70
        self.assertIn("phase_a_no_scores", validate_record(stamp(row), load_contract()))

    def test_c_report_not_accepted_as_a_envelope(self):
        self.assertTrue(validate_record(self.current, load_contract()))

    def test_251b_output_unchanged(self):
        expected = evaluate_stock(self.cur_inputs["rows"], **self.cur_inputs["context"])
        self.assertEqual(self.current["evaluation"], expected)
        self.assertEqual(expected["internal_evidence"]["predecessor_report_reference"]["status"], "PENDING_251C")

    def test_pin_required_not_latest(self):
        result = compare_reports(self.current, self.cur_inputs, self.previous, self.prev_inputs)
        self.assertEqual(result["reason_codes"], ["PREDECESSOR_PIN_REQUIRED"])

    def test_pin_identity_mismatch(self):
        self.pin["report_id"] = "another_report"
        self.assert_rejected("PREDECESSOR_BINDING_MISMATCH")

    def test_pin_revision_mismatch(self):
        self.pin["revision"] = 2
        self.assert_rejected("PREDECESSOR_BINDING_MISMATCH")

    def test_report_hash_tamper(self):
        self.current["content_hash"] = "0" * 64
        self.assert_rejected("REPORT_DIGEST_MISMATCH")

    def test_input_digest_mismatch(self):
        self.current["input_digest"] = "0" * 64
        self.current = stamp(self.current)
        self.assert_rejected("EVALUATOR_REPLAY_MISMATCH")

    def test_no_skipped_predecessor_date(self):
        self.prev_inputs["context"]["report_date"] = "2026-09-23"
        self.previous = artifact("synthetic-older-report", self.prev_inputs)
        self.pin = reference(self.previous)
        self.assert_rejected("PREDECESSOR_NOT_PREVIOUS_REPORT_DATE")

    def test_no_cross_stock_comparison(self):
        self.prev_inputs["context"]["symbol"] = "OTHER_SYNTHETIC"
        self.previous = build_report("other-stock", self.prev_inputs)
        self.pin = reference(self.previous)
        self.assert_rejected("COMPARISON_IDENTITY_MISMATCH")

    def test_holiday_carried_session_disclosed(self):
        self.assertTrue(self.result()["comparison"]["same_market_session"])

    def test_missing_scores_not_zero_delta(self):
        self.cur_inputs = inputs(FIXTURE["current_date"], None)
        self.current = artifact(FIXTURE["current_id"], self.cur_inputs)
        result = self.result()
        self.assertEqual(result["status"], "INSUFFICIENT_COMPARISON")
        self.assertIsNone(result["comparison"]["scores"]["improvement_accuracy_score"]["delta_points"])

    def test_positive_report_delta_is_not_fix_causality(self):
        self.cur_inputs = inputs(FIXTURE["current_date"], 80)
        self.current = artifact(FIXTURE["current_id"], self.cur_inputs)
        result = self.result()
        self.assertEqual(result["comparison"]["scores"]["improvement_accuracy_score"]["delta_points"], 6)
        self.assertEqual(result["comparison"]["interpretation"], "DESCRIPTIVE_REPORT_DELTA_NOT_CAUSAL_EFFECT")
        self.assertFalse(result["realized_effect"]["causal_claim"])

    def test_unknown_input_fields(self):
        self.cur_inputs["live_source"] = "not_allowed"
        self.assert_rejected("INPUT_SHAPE")

    def test_no_live_source_kind(self):
        self.cur_inputs["source_kind"] = "PRODUCTION"
        self.assert_rejected("INPUT_NOT_ADMITTED")

    def test_no_raw_payload(self):
        self.current["raw_payload"] = {}
        self.assert_rejected("REPORT_NOT_ADMITTED")

    def test_projection_replay_tamper(self):
        result = self.result()
        result["evidence_chain"]["state"] = "SUCCESS"
        with self.assertRaisesRegex(ProjectionError, "PROJECTION_REPLAY_MISMATCH"):
            validate_projection(stamp(result), self.current, self.cur_inputs, self.previous, self.prev_inputs, expected_predecessor=self.pin)

    def test_projection_replay_valid(self):
        self.assertTrue(validate_projection(self.result(), self.current, self.cur_inputs, self.previous, self.prev_inputs, expected_predecessor=self.pin))

    def test_offline_no_network(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.result()["status"], "COMPARABLE")

    def test_contract_enum_mapping(self):
        self.assertEqual(contract()["effect_mapping"], {"IMPROVED":"POSITIVE", "NEUTRAL":"NEUTRAL", "REGRESSED":"NEGATIVE", "MIXED":"INSUFFICIENT_EVIDENCE", "PENDING":"INSUFFICIENT_EVIDENCE"})

    def test_report_append_idempotent(self):
        history = append_report([], self.current)
        self.assertEqual(append_report(history, self.current), history)
        self.assertIsNot(history[0], self.current)

    def test_report_revision_cannot_overwrite(self):
        changed = deepcopy(self.current)
        changed["linkage_refs"]["fix"] = None
        with self.assertRaisesRegex(ProjectionError, "IMMUTABLE_REPORT_CONFLICT"):
            append_report([self.current], stamp(changed))

    def test_report_revision_chain(self):
        revised = build_report(self.current["report_id"], self.cur_inputs, revision=2,
            supersedes_hash=self.current["content_hash"], history=[self.current])
        self.assertEqual(len(append_report([self.current], revised)), 2)

    def test_revision_skip_rejected(self):
        with self.assertRaisesRegex(ProjectionError, "REVISION_PREDECESSOR_MISSING"):
            build_report(self.current["report_id"], self.cur_inputs, revision=3, supersedes_hash=self.current["content_hash"], history=[self.current])

    def test_revision_wrong_hash(self):
        with self.assertRaisesRegex(ProjectionError, "REVISION_PREDECESSOR_MISSING"):
            build_report(self.current["report_id"], self.cur_inputs, revision=2, supersedes_hash="0"*64, history=[self.current])

    def test_no_latest_report_id(self):
        with self.assertRaisesRegex(ProjectionError, "MUTABLE_REPORT_ID"):
            build_report("latest", self.cur_inputs)

    def test_malformed_inputs_do_not_leak_payload(self):
        result = compare_reports(None, None)
        self.assertEqual(result["status"], "REJECTED")
        self.assertNotIn("component_evidence", result)

    def rebuild_records(self, records, refs):
        self.current = build_report(self.current["report_id"], self.cur_inputs, evidence_records=records, linkage_refs=refs)

    def test_finding_fix_hash_binding_mismatch(self):
        records = deepcopy(self.current["evidence_records"])
        refs = deepcopy(self.current["linkage_refs"])
        fix = next(r for r in records if r["entity"] == "fix_ledger")
        fix["source_refs"][0]["content_hash"] = "0"*64
        fixed = stamp(fix); records[records.index(fix)] = fixed; refs["fix"] = fixed["content_hash"]
        self.rebuild_records(records, refs)
        result = self.result()
        self.assertEqual(result["evidence_chain"]["state"], "INCOMPLETE")
        self.assertIn("FINDING_FIX_BINDING_MISMATCH", result["evidence_chain"]["reason_codes"])

    def test_fix_evaluation_digest_binding_mismatch(self):
        records = deepcopy(self.current["evidence_records"])
        refs = deepcopy(self.current["linkage_refs"])
        evaluation = next(r for r in records if r["entity"] == "fix_evaluation")
        evaluation["source_refs"][0]["content_hash"] = "0"*64
        changed = stamp(evaluation); records[records.index(evaluation)] = changed; refs["evaluation"] = changed["content_hash"]
        self.rebuild_records(records, refs)
        self.assertIn("FIX_EVALUATION_BINDING_MISMATCH", self.result()["evidence_chain"]["reason_codes"])

    def test_evaluator_result_digest_binding_mismatch(self):
        records = deepcopy(self.current["evidence_records"])
        refs = deepcopy(self.current["linkage_refs"])
        evaluation = next(r for r in records if r["entity"] == "fix_evaluation")
        evaluation["source_refs"][1]["content_hash"] = "0"*64
        changed = stamp(evaluation); records[records.index(evaluation)] = changed; refs["evaluation"] = changed["content_hash"]
        self.rebuild_records(records, refs)
        self.assertIn("EVALUATOR_EVIDENCE_BINDING_MISMATCH", self.result()["evidence_chain"]["reason_codes"])

    def test_link_wrong_entity(self):
        refs = deepcopy(self.current["linkage_refs"])
        refs["finding"] = refs["fix"]
        self.rebuild_records(self.current["evidence_records"], refs)
        self.assertIn("WRONG_FINDING_ENTITY", self.result()["evidence_chain"]["reason_codes"])

    def test_ledger_tamper_rejected(self):
        self.current["evidence_records"][0]["content_hash"] = "0"*64
        self.current = stamp(self.current)
        self.assert_rejected("EVIDENCE_RECORD_INVALID")

    def test_future_lifecycle_event_rejected(self):
        records = deepcopy(self.current["evidence_records"])
        evaluation = next(r for r in records if r["entity"] == "fix_evaluation")
        evaluation["data"]["evaluated_at"] = "2026-09-26T10:00:00+08:00"
        records[records.index(evaluation)] = stamp(evaluation)
        with self.assertRaisesRegex(ProjectionError, "FUTURE_LIFECYCLE_EVIDENCE"):
            self.rebuild_records(records, self.current["linkage_refs"])

    def test_evidence_input_order_canonical(self):
        records = list(reversed(self.current["evidence_records"]))
        self.rebuild_records(records, self.current["linkage_refs"])
        self.assertEqual(self.current, self.current_report)

    def test_effect_summary_cannot_be_forged(self):
        self.current["evaluation"]["internal_evidence"]["evaluators"]["improvement"]["effect_summary"]["realized_prediction_effect"] = "IMPROVED"
        self.current = stamp(self.current)
        self.assert_rejected("EVALUATOR_REPLAY_MISMATCH")

    def test_mixed_effect_insufficient(self):
        for row in self.cur_inputs["rows"]:
            for i, sample in enumerate(row["fields"]["post_fix_cohort"]["value"]):
                sample["score"] = 90 if i < 3 else 40
        self.current = artifact(FIXTURE["current_id"], self.cur_inputs)
        self.assertEqual(self.result()["realized_effect"]["state"], "INSUFFICIENT_EVIDENCE")

    def test_original_evidence_status_not_promoted(self):
        result = self.result()
        evaluation = next(r for r in result["linkage_evidence"]["current"] if r["entity"] == "fix_evaluation")
        self.assertEqual(result["evidence_chain"]["state"], "COMPLETE")
        self.assertEqual(evaluation["data"]["status"], "PENDING")

    def test_unbound_effect_attribution_disclosed(self):
        self.current = artifact(FIXTURE["current_id"], self.cur_inputs, complete=False)
        self.assertEqual(self.result()["realized_effect"]["attribution"], "EVALUATOR_SAMPLE_ONLY")

    def test_revision_cannot_change_stock_identity(self):
        changed = deepcopy(self.current)
        changed.update(revision=2, supersedes_hash=self.current["content_hash"])
        changed["identity"]["symbol"] = "OTHER"
        with self.assertRaisesRegex(ProjectionError, "REVISION_IDENTITY_CHANGED"):
            append_report([self.current], stamp(changed))

    def test_old_predecessor_pin_not_replaced_by_new_revision(self):
        revised = build_report(self.previous["report_id"], self.prev_inputs, revision=2,
            supersedes_hash=self.previous["content_hash"], history=[self.previous])
        result = compare_reports(self.current, self.cur_inputs, self.previous, self.prev_inputs,
                                 expected_predecessor=self.pin, predecessor_history=[self.previous, revised])
        self.assertEqual(result["predecessor_ref"], self.pin)
        self.assertEqual(result["predecessor_ref"]["revision"], 1)

    def test_us_latest_completed_session_comparison(self):
        self.cur_inputs["context"].update(market="US", symbol="SYNTHETIC_US")
        self.prev_inputs["context"].update(market="US", symbol="SYNTHETIC_US")
        self.current = build_report(FIXTURE["current_id"], self.cur_inputs)
        self.previous = build_report(FIXTURE["predecessor_id"], self.prev_inputs)
        self.pin = reference(self.previous)
        result = self.result()
        self.assertEqual(result["status"], "COMPARABLE")
        self.assertFalse(result["comparison"]["same_market_session"])

    def test_contract_content_digest_bound(self):
        self.assertEqual(self.current["contract_digest"], digest(contract()))
        self.assertEqual(self.result()["contract_digest"], digest(contract()))
        self.current["contract_digest"] = "0" * 64
        self.current = stamp(self.current)
        self.assert_rejected("CONTRACT_CONTENT_MISMATCH")

    def test_original_fix_identity_not_silently_reassigned(self):
        records = deepcopy(self.current["evidence_records"])
        refs = deepcopy(self.current["linkage_refs"])
        fix = next(r for r in records if r["entity"] == "fix_ledger")
        fix["data"]["fix_id"] = "another_fix"
        fixed = stamp(fix); records[records.index(fix)] = fixed; refs["fix"] = fixed["content_hash"]
        self.rebuild_records(records, refs)
        self.assertIn("EVALUATOR_FIX_IDENTITY_MISMATCH", self.result()["evidence_chain"]["reason_codes"])


if __name__ == "__main__":
    unittest.main()
