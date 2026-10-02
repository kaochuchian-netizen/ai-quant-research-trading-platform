"""AI-DEV-256 synthetic-only unified TW/US daily learning regressions."""
import json
import tempfile
import unittest
from pathlib import Path
from app.evaluation.prediction_regression_contract import stamp
from app.evaluation.production_evidence import outcome
from app.evaluation.daily_evaluation import build_daily, canonical_cutoff, window_outcomes
from app.evaluation.daily_learning import derive, latest, apply, validate
from test_daily_evaluation import packet
from test_production_evidence import frozen
from test_us_session_direction import prediction, obs

class UnifiedDailyLearningTests(unittest.TestCase):
    def test_one_daily_invocation_evaluates_tw_and_us(self):
        value=build_daily("2026-09-25", packet())
        self.assertEqual(set(value["markets"]), {"TW","US"})
        self.assertEqual(value["markets"]["TW"]["status"],"VALID")
        self.assertEqual(value["markets"]["US"]["status"],"VALID")

    def test_tw_four_windows_resolve_one_origin_outcome(self):
        p=frozen()
        record=packet()["TW"]["records"][0]
        card={"symbol":"TEST","source_name":"shioaji_snapshot","actual_status":"complete",
              "actual_open":100,"actual_low":98,"actual_high":106,"actual_close":105,
              "fetched_at":"2026-09-24T13:35:00+08:00","source_record_time":"invalid-raw-provider-time"}
        window=stamp({"market":"TW","window":"post_close_1500","session":"2026-09-24",
                      "generated_at":"2026-09-24T15:10:00+08:00","source_digest":"a"*64,"cards":[card],"observations":[]})
        values, diagnostics=window_outcomes([record],[window],"2026-09-25T17:00:00+08:00")
        self.assertEqual(len(values),1)
        self.assertEqual(values[0]["sample_id"],p["sample_id"])
        self.assertEqual(diagnostics[0]["reason"],"FINAL_CLOSE_RESOLVED")

    def test_us_three_windows_resolve_correct_us_session(self):
        p=prediction()["frozen"]
        record=packet()["US"]["records"][0]
        source=obs("2026-09-24")
        source["rows"].append({"date":"2026-09-24","high":126,"low":123,"close":125})
        source["available_at"]="2026-09-24T16:30:00-04:00"; source=stamp(source)
        window=stamp({"market":"US","window":"us_post_close_review_0630","session":"2026-09-24",
                      "generated_at":"2026-09-25T06:30:00+08:00","source_digest":"b"*64,"cards":[],"observations":[source]})
        values, diagnostics=window_outcomes([record],[window],canonical_cutoff("2026-09-25"))
        self.assertEqual(len(values),1)
        self.assertEqual(values[0]["horizon"]["session_date"],"2026-09-24")
        self.assertEqual(diagnostics[0]["reason"],"FINAL_CLOSE_RESOLVED")

    def test_missing_post_close_is_explicit_not_zero_outcome(self):
        values, diagnostics=window_outcomes(packet()["TW"]["records"],[],canonical_cutoff("2026-09-25"))
        self.assertEqual(values,[])
        self.assertEqual(diagnostics[0]["status"],"WAITING_OUTCOME")
        self.assertEqual(diagnostics[0]["reason"],"POST_CLOSE_REPORT_MISSING")

    def test_finding_fix_artifact_has_no_mutation(self):
        value=build_daily("2026-09-25",packet())
        learning=value["learning_artifact"]
        self.assertEqual(validate(learning),learning)
        self.assertFalse(learning["model_mutation"])
        self.assertFalse(learning["strategy_mutation"])
        self.assertEqual(learning["markets"]["TW"]["fix"]["state"],"PROPOSED_DIAGNOSTIC_CONTROL")

    def test_next_prediction_applies_prior_learning_with_machine_proof(self):
        learning=derive("2026-09-23",{"TW":{"outcome_diagnostics":[]},"US":{"outcome_diagnostics":[]}})
        parent=stamp({"kind":"DAILY_EVALUATION","report_date":"2026-09-23","canonical_cutoff":"2026-09-23T17:00:00+08:00","learning_artifact":learning})
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"artifacts/archive/window_snapshots/.daily_evaluation/2026-09-23"
            target.mkdir(parents=True); (target/(parent["content_hash"]+".json")).write_text(json.dumps(parent))
            ref=latest(root,"TW","2026-09-24","2026-09-24T07:00:00+08:00")
            used=apply(ref,frozen_at="2026-09-24T07:00:00+08:00",feature_times=["2026-09-24T06:00:00+08:00"],horizon_open="2026-09-24T09:00:00+08:00")
        self.assertEqual(used["application"],"FROZEN_PROVENANCE_GATE_APPLIED")
        self.assertTrue(used["controls"]["feature_available_before_freeze"])
        self.assertFalse(used["model_mutation"])

    def test_learning_rejects_future_feature(self):
        with self.assertRaises(ValueError):
            apply({"control":"FROZEN_FEATURE_AND_HORIZON_PROVENANCE","market":"US"},
                  frozen_at="2026-09-24T08:00:00-04:00",feature_times=["2026-09-24T08:01:00-04:00"],
                  horizon_open="2026-09-24T09:30:00-04:00")

    def test_tw_us_learning_isolation(self):
        value=build_daily("2026-09-25",packet())
        learning=value["learning_artifact"]
        self.assertEqual(set(learning["markets"]),{"TW","US"})
        self.assertIsNot(learning["markets"]["TW"],learning["markets"]["US"])

    def test_daily_learning_is_deterministic(self):
        self.assertEqual(build_daily("2026-09-25",packet())["learning_artifact"],build_daily("2026-09-25",packet())["learning_artifact"])

class ActionableLearningTests(unittest.TestCase):
    @staticmethod
    def failing_market(direction):
        return {"stocks":{"X":{"sample_reviews":{"s":{"prediction_direction":direction,"assessment":{"eligible":True,"direction_correct":False}}}}},"outcome_diagnostics":[]}

    def test_evaluation_error_derives_actionable_learning(self):
        learning=derive("2026-09-23",{"TW":self.failing_market("UP"),"US":{"stocks":{},"outcome_diagnostics":[]}})
        item=learning["markets"]["TW"]["actionable_learning"]
        self.assertTrue(item["active"]);self.assertEqual(item["avoid_directions"],["UP"])

    def test_next_prediction_actually_applies_error_learning(self):
        ref={"control":"FROZEN_FEATURE_AND_HORIZON_PROVENANCE","market":"TW","actionable_learning":{"active":True,"avoid_directions":["UP"]}}
        used=apply(ref,frozen_at="2026-09-24T07:00:00+08:00",feature_times=["2026-09-24T06:00:00+08:00"],horizon_open="2026-09-24T09:00:00+08:00",direction="UP")
        self.assertEqual(used["decision_effect"],"ABSTAIN_NO_FORECAST")
        self.assertEqual(used["applied_learning"]["avoid_directions"],["UP"])

    def test_no_applicable_learning_preserves_existing_decision(self):
        ref={"control":"FROZEN_FEATURE_AND_HORIZON_PROVENANCE","market":"US","actionable_learning":{"active":True,"avoid_directions":["DOWN"]}}
        used=apply(ref,frozen_at="2026-09-24T08:00:00-04:00",feature_times=["2026-09-24T07:00:00-04:00"],horizon_open="2026-09-24T09:30:00-04:00",direction="UP")
        self.assertEqual(used["decision_effect"],"RETAIN_EXISTING_DECISION")

    def test_tw_us_actionable_learning_isolated(self):
        learning=derive("2026-09-23",{"TW":self.failing_market("UP"),"US":self.failing_market("DOWN")})
        self.assertEqual(learning["markets"]["TW"]["actionable_learning"]["avoid_directions"],["UP"])
        self.assertEqual(learning["markets"]["US"]["actionable_learning"]["avoid_directions"],["DOWN"])

    def test_us_prediction_path_abstains_on_applied_learning(self):
        from test_us_session_direction import obs
        from app.evaluation.us_session_direction import predict
        from app.evaluation.session_calendar import load_calendar
        ref={"control":"FROZEN_FEATURE_AND_HORIZON_PROVENANCE","market":"US","actionable_learning":{"active":True,"avoid_directions":["UP"]}}
        value=predict(obs(),load_calendar("US"),frozen_at="2026-09-24T08:01:00-04:00",learning_reference=ref)
        self.assertEqual(value["status"],"NO_FORECAST")
        self.assertEqual(value["learning_used"]["decision_effect"],"ABSTAIN_NO_FORECAST")
