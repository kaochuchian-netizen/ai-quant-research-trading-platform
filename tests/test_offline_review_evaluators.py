"""Synthetic arithmetic and adversarial admission tests; no production adapters."""
import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.evaluation.offline_review_evaluators import (
    evaluate_prediction, evaluate_strategy, evaluate_improvement, evaluate_stock,
    improvement_effect, load_contract, session_context,
)
from app.evaluation.prediction_regression_contract import canonical_json, safety_errors

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/offline_review_evaluators_v1.json"


def fixtures():
    template = json.loads(FIXTURE.read_text())
    sessions, rows = [], []
    for market in ("TW", "US"):
        zone = ZoneInfo("Asia/Taipei" if market == "TW" else "America/New_York")
        for day in template["session_dates"]:
            opened = datetime.fromisoformat(day + ("T09:00" if market == "TW" else "T09:30")).replace(tzinfo=zone)
            closed = datetime.fromisoformat(day + ("T13:30" if market == "TW" else "T16:00")).replace(tzinfo=zone)
            predicted = opened - timedelta(minutes=30)
            sessions.append({"market": market, "session_date": day, "open_at": opened.isoformat(), "close_at": closed.isoformat()})
            row = {"market": market, "symbol": "SYNTHETIC_" + market, "strategy_id": "synthetic_daily",
                   "horizon_sessions": 1, "session_date": day, "prediction_at": predicted.isoformat(),
                   "outcome_closed_at": closed.isoformat(), "fallback_reason": None, "fields": {}}
            row["evaluation_at"] = (closed + timedelta(minutes=1)).isoformat()
            for group, role in (("signals", "signal"), ("outcomes", "outcome"), ("regret", "regret")):
                stamp = predicted if role == "signal" else closed + timedelta(minutes=1)
                for name, value in template[group].items():
                    row["fields"][name] = {"value": copy.deepcopy(value), "classification": "AVAILABLE", "role": role,
                                           "as_of": stamp.isoformat(), "available_at": stamp.isoformat(),
                                           "source_ref": f"synthetic:{market}:{day}:{name}"}
            rows.append(row)
    calendar = {"sessions": sessions, "source_ref": "synthetic_calendar_v1", "coverage_through": "2026-09-25T00:00:00+08:00"}
    rehash(calendar)
    context = {"market": "TW", "symbol": "SYNTHETIC_TW", "strategy_id": "synthetic_daily", "horizon_sessions": 1,
               "report_date": template["report_date"], "calendar": calendar}
    return rows, context


def improvement_fixtures():
    rows, context = fixtures()
    case = json.loads(FIXTURE.read_text())["improvement_case"]
    for market in ("TW", "US"):
        zone = ZoneInfo("Asia/Taipei" if market == "TW" else "America/New_York")
        def stamp(day, clock):
            return datetime.fromisoformat(day + "T" + clock).replace(tzinfo=zone).isoformat()
        def closed(day):
            return stamp(day, "13:30" if market == "TW" else "16:00")
        for day in case["baseline_dates"] + [case["effective_session"]] + case["post_dates"]:
            context["calendar"]["sessions"].append({"market": market, "session_date": day,
                "open_at": stamp(day, "09:00" if market == "TW" else "09:30"), "close_at": closed(day)})
        identity = {"market": market, "symbol": "SYNTHETIC_" + market, "strategy_id": "synthetic_daily",
                    "horizon_sessions": 1, "regime": "synthetic_flat"}
        def cohort(days, score):
            return [{"session_date": day, "matched_identity": identity.copy(), "classification": "AVAILABLE", "status": "ELIGIBLE",
                     "score": score, "source_ref": "synthetic:" + day, "metric_spec_version": "canonical_prediction_v1",
                     "closed_at": closed(day), "available_at": closed(day), "frozen_at": closed(day)} for day in days]
        values = {
            "finding": {"finding_id": "synthetic_finding", "status": "CONFIRMED", "immutable_error_ref": "synthetic:error:hash",
                        "confirmed_at": stamp("2026-08-25", "10:00")},
            "fix": {"fix_id": "synthetic_fix", "finding_id": "synthetic_finding", "status": "IMPLEMENTED", "regime": "synthetic_flat",
                    "approved_at": stamp("2026-08-25", "11:00"), "effective_at": stamp("2026-08-25", "12:00"),
                    "effective_session": case["effective_session"], "source_ref": "synthetic:fix:hash", "detector_version": "synthetic_v1",
                    "detector_frozen_at": stamp("2026-08-25", "11:00")},
            "baseline_3": cohort(case["baseline_dates"][-3:], case["baseline_metric"]),
            "baseline_10": cohort(case["baseline_dates"], case["baseline_metric"]),
            "post_fix_cohort": cohort(case["post_dates"], case["post_metric"]),
            "recurrence": [{"session_date": day, "detector_version": "synthetic_v1", "classification": "AVAILABLE",
                            "source_ref": "synthetic:detector:" + day, "available_at": closed(day),
                            "observable_opportunities": 1, "recurrence_count": 0} for day in case["post_dates"]],
        }
        for row in rows:
            if row["market"] == market:
                for name, value in values.items():
                    row["fields"][name] = {"value": copy.deepcopy(value), "classification": "AVAILABLE", "role": "outcome",
                                           "as_of": row["evaluation_at"], "available_at": row["evaluation_at"], "source_ref": "synthetic:" + name}
    rehash(context["calendar"])
    return rows, context


def rehash(calendar):
    calendar["content_hash"] = hashlib.sha256(canonical_json(calendar["sessions"]).encode()).hexdigest()


class OfflineEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.context = fixtures()

    def row(self):
        return next(r for r in self.rows if r["market"] == "TW" and r["session_date"] == "2026-09-24")

    def field(self, key):
        return self.row()["fields"][key]

    def result(self, fn=evaluate_prediction):
        return fn(self.rows, **self.context)

    def reason(self, expected, fn=evaluate_prediction):
        result = self.result(fn)
        self.assertIsNone(result["score"])
        self.assertIn(expected, result["evidence"]["2026-09-24"]["reasons"])

    def test_canonical_weights_sum(self):
        self.assertTrue(all(sum(group.values()) == 100 for group in load_contract()["weights_percent"].values()))

    def test_prediction_exact_arithmetic(self):
        self.assertAlmostEqual(self.result()["score"], 99.6)
        self.assertEqual(self.result()["evidence"]["2026-09-24"]["diagnostics"]["interval_width_atr"], 1.5)

    def test_strategy_exact_arithmetic(self):
        self.assertAlmostEqual(self.result(evaluate_strategy)["score"], 76.0)

    def test_rolling_windows_have_distinct_sessions(self):
        result = self.result()
        self.assertEqual(len(result["windows"]["3"]["sessions"]), 3)
        self.assertEqual(len(result["windows"]["10"]["sessions"]), 10)
        self.assertEqual(result["windows"]["3"]["sessions"], ["2026-09-22", "2026-09-23", "2026-09-24"])

    def test_rolling_weight_35_65_not_calendar_days(self):
        for row in self.rows:
            if row["session_date"] >= "2026-09-22":
                row["fields"]["target_price"]["value"] = 115
        result = self.result()
        self.assertAlmostEqual(result["windows"]["3"]["score"], 64.6)
        self.assertAlmostEqual(result["windows"]["10"]["score"], 89.1)
        self.assertAlmostEqual(result["score"], 64.6 * .35 + 89.1 * .65)

    def test_tw_current_us_latest_completed(self):
        self.assertEqual(self.result()["latest_session"], "2026-09-24")
        self.context.update(market="US", symbol="SYNTHETIC_US")
        self.assertEqual(self.result()["latest_session"], "2026-09-23")
        self.assertAlmostEqual(self.result()["score"], 99.6)

    def test_holiday_does_not_duplicate_stale_session(self):
        self.context["report_date"] = "2026-09-25"
        self.context["calendar"]["coverage_through"] = "2026-09-26T00:00:00+08:00"
        self.assertEqual(self.result()["latest_session"], "2026-09-24")

    def test_missing_session_insufficient(self):
        self.rows.remove(self.row())
        self.reason("MISSING_SESSION")

    def test_duplicate_session_ambiguous(self):
        self.rows.append(copy.deepcopy(self.row()))
        self.reason("AMBIGUOUS_DUPLICATE_SESSION")

    def test_partial_field_not_imputed(self):
        self.field("target_price")["classification"] = "PARTIAL"
        self.reason("PARTIAL")

    def test_missing_field_not_imputed(self):
        del self.row()["fields"]["target_price"]
        self.reason("MISSING")

    def test_ambiguous_field_not_imputed(self):
        self.field("target_price")["classification"] = "AMBIGUOUS"
        self.reason("AMBIGUOUS")

    def test_missing_classification(self):
        del self.field("target_price")["classification"]
        self.reason("INVALID_CLASSIFICATION")

    def test_future_feature_rejected(self):
        self.field("atr14")["available_at"] = "2026-09-24T10:00:00+08:00"
        self.reason("FUTURE_DATA_LEAKAGE")

    def test_unknown_future_signal_rejected(self):
        self.row()["fields"]["extra_signal"] = copy.deepcopy(self.field("atr14"))
        self.field("extra_signal")["available_at"] = "2026-09-24T10:00:00+08:00"
        self.reason("FUTURE_DATA_LEAKAGE")

    def test_hindsight_cannot_supply_signal(self):
        self.field("target_price")["role"] = "regret"
        self.reason("HINDSIGHT_ROLE_VIOLATION")

    def test_hindsight_allowed_regret(self):
        self.assertEqual(self.result(evaluate_strategy)["status"], "ELIGIBLE")

    def test_hindsight_labels_explicit(self):
        diagnostics = self.result(evaluate_strategy)["evidence"]["2026-09-24"]["diagnostics"]
        self.assertIn("timing_events", diagnostics["hindsight_labels"])
        self.assertFalse(diagnostics["causal_claim"])

    def test_not_final_outcome(self):
        self.field("close")["as_of"] = "2026-09-24T12:00:00+08:00"
        self.reason("OUTCOME_NOT_FINAL")

    def test_future_outcome_after_cutoff(self):
        self.field("close")["available_at"] = "2026-09-24T18:00:00+08:00"
        self.reason("AS_OF_VIOLATION")

    def test_missing_timestamp(self):
        self.field("atr14")["available_at"] = None
        self.reason("MISSING_TIMESTAMP")

    def test_naive_timestamp(self):
        self.field("atr14")["available_at"] = "2026-09-24T08:00:00"
        self.reason("MISSING_TIMESTAMP")

    def test_missing_source(self):
        self.field("atr14")["source_ref"] = ""
        self.reason("MISSING_EVIDENCE")

    def test_fallback_excluded(self):
        self.row()["fallback_reason"] = "SYNTHETIC_MISSING_HISTORY"
        self.reason("FALLBACK_EXCLUDED")

    def test_nonpositive_atr(self):
        self.field("atr14")["value"] = 0
        self.reason("NONPOSITIVE_SCALE")

    def test_nonfinite_input(self):
        self.field("confidence")["value"] = float("nan")
        self.reason("INVALID_NUMBER")

    def test_bool_not_numeric(self):
        self.field("confidence")["value"] = True
        self.reason("INVALID_NUMBER")

    def test_unmapped_confidence(self):
        self.field("confidence_event")["value"] = "UNMAPPED"
        self.reason("SEMANTIC_MISMATCH")

    def test_execution_target_not_forecast(self):
        self.field("target_semantics")["value"] = "EXECUTION_TARGET"
        self.reason("SEMANTIC_MISMATCH")

    def test_horizon_mismatch(self):
        self.field("outcome_horizon_sessions")["value"] = 20
        self.reason("SEMANTIC_MISMATCH")

    def test_invalid_interval(self):
        self.field("range_low")["value"] = 120
        self.reason("INVALID_PRICE_RANGE")

    def test_full_path_not_just_close(self):
        self.field("path_high")["value"] = 111
        self.assertEqual(self.result()["evidence"]["2026-09-24"]["components"]["range_coverage"], 0)

    def test_flat_atr_band(self):
        self.field("close")["value"] = 100.5
        self.field("trend")["value"] = "FLAT"
        self.assertEqual(self.result()["evidence"]["2026-09-24"]["components"]["trend"], 100)

    def test_strategy_ambiguous_intrabar(self):
        self.field("path_resolution")["value"] = "DAILY_ONLY"
        self.reason("AMBIGUOUS_INTRABAR_ORDER", evaluate_strategy)

    def test_strategy_no_positive_opportunity_na(self):
        self.field("best_feasible_net_profit")["value"] = 0
        result = self.result(evaluate_strategy)
        self.assertEqual(result["evidence"]["2026-09-24"]["status"], "N/A")
        self.assertIsNone(result["score"])

    def test_strategy_missing_cost(self):
        del self.row()["fields"]["cost_basis"]
        self.reason("MISSING", evaluate_strategy)

    def test_strategy_missing_required_event(self):
        self.field("required_timing_events")["value"].append("hedge")
        self.reason("MISSING_TIMING_EVENTS", evaluate_strategy)

    def test_strategy_no_trade_requires_avoided_loss(self):
        self.field("recommended_exposure")["value"] = 0
        self.field("avoided_loss_evidence")["value"] = ""
        self.reason("MISSING_AVOIDED_LOSS_EVIDENCE", evaluate_strategy)

    def test_calendar_hash(self):
        self.context["calendar"]["content_hash"] = "bad"
        with self.assertRaisesRegex(ValueError, "calendar_hash"):
            self.result()

    def test_calendar_coverage(self):
        self.context["calendar"]["coverage_through"] = "2026-09-23T00:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "calendar_coverage_missing"):
            self.result()

    def test_deterministic_order_independent(self):
        before = canonical_json(self.result())
        self.rows.reverse()
        self.assertEqual(canonical_json(self.result()), before)

    def test_inputs_not_mutated(self):
        before = canonical_json([self.rows, self.context])
        self.result()
        self.assertEqual(canonical_json([self.rows, self.context]), before)

    def test_synthetic_fixture_safety(self):
        self.assertEqual(safety_errors(json.loads(FIXTURE.read_text())), [])

    def test_prohibited_raw_payload_rejected(self):
        self.row()["raw_payload"] = {}
        with self.assertRaisesRegex(ValueError, "prohibited_input"):
            self.result()

    def test_other_stock_cannot_fill_missing_session(self):
        self.row()["symbol"] = "OTHER_SYNTHETIC"
        self.reason("MISSING_SESSION")

    def test_no_network_dependency(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.result()["status"], "ELIGIBLE")

    def test_wrong_calendar_session_close(self):
        self.row()["outcome_closed_at"] = "2026-09-24T12:00:00+08:00"
        self.reason("SESSION_CLOSE_MISMATCH")

    def test_prediction_after_open(self):
        self.row()["prediction_at"] = "2026-09-24T10:00:00+08:00"
        self.reason("PREDICTION_NOT_BEFORE_SESSION")

    def test_malformed_cell_fail_closed(self):
        self.row()["fields"]["atr14"] = None
        self.reason("INVALID_FIELD")

    def test_invalid_role_fail_closed(self):
        self.field("atr14")["role"] = "feature_from_future"
        self.reason("HINDSIGHT_ROLE_VIOLATION")

    def test_calendar_dst_and_early_close(self):
        calendar = {"source_ref": "synthetic_dst", "coverage_through": "2026-11-04T00:00:00+08:00", "sessions": [
            {"market": "US", "session_date": "2026-10-30", "open_at": "2026-10-30T09:30:00-04:00", "close_at": "2026-10-30T16:00:00-04:00"},
            {"market": "US", "session_date": "2026-11-02", "open_at": "2026-11-02T09:30:00-05:00", "close_at": "2026-11-02T13:00:00-05:00"}]}
        rehash(calendar)
        self.assertEqual(session_context("2026-11-02", calendar)[1]["US"], "2026-10-30")
        self.assertEqual(session_context("2026-11-03", calendar)[1]["US"], "2026-11-02")


class ImprovementEffectTests(unittest.TestCase):
    def setUp(self):
        self.identity = {"market": "TW", "symbol": "SYNTHETIC", "strategy_id": "synthetic",
                         "horizon_sessions": 1, "regime": "synthetic_flat"}
        self.baseline = []
        self.post = []
        for n in range(3):
            for target, day in ((self.baseline, 14 + n), (self.post, 21 + n)):
                stamp = f"2026-09-{day:02}T14:00:00+08:00"
                target.append({"session_date": f"2026-09-{day:02}", "matched_identity": copy.deepcopy(self.identity),
                               "classification": "AVAILABLE", "status": "ELIGIBLE", "score": 70,
                               "source_ref": f"synthetic:{day}", "metric_spec_version": "canonical_prediction_v1",
                               "closed_at": stamp, "available_at": stamp, "frozen_at": stamp})

    def result(self):
        return improvement_effect(self.baseline, self.post, expected_sessions=["2026-09-21", "2026-09-22", "2026-09-23"],
                                  matched_identity=self.identity, effective_at="2026-09-18T14:00:00+08:00",
                                  cutoff="2026-09-24T17:00:00+08:00")

    def test_no_change_effect_50(self):
        self.assertEqual(self.result()["score"], 50)
        self.assertEqual(self.result()["interpretation"], "UNCHANGED")

    def test_improvement_effect_above_50(self):
        for row in self.post:
            row["score"] = 80
        self.assertEqual(self.result()["score"], 60)

    def test_regression_effect_below_50(self):
        for row in self.post:
            row["score"] = 50
        self.assertEqual(self.result()["score"], 30)

    def test_missing_samples_not_zero(self):
        self.post.pop()
        self.assertEqual(self.result()["status"], "INSUFFICIENT_SAMPLE")
        self.assertIsNone(self.result()["score"])

    def test_baseline_frozen_after_fix(self):
        self.baseline[0]["frozen_at"] = "2026-09-19T00:00:00+08:00"
        self.assertEqual(self.result()["reasons"], ["BASELINE_NOT_FROZEN"])

    def test_unmatched_regime(self):
        self.post[0]["matched_identity"]["regime"] = "different"
        self.assertEqual(self.result()["reasons"], ["UNMATCHED_COHORT"])

    def test_ambiguous_cohort(self):
        self.post[0]["classification"] = "AMBIGUOUS"
        self.assertEqual(self.result()["reasons"], ["INELIGIBLE_COHORT"])

    def test_mismatched_metric(self):
        self.post[0]["metric_spec_version"] = "different_metric"
        self.assertEqual(self.result()["reasons"], ["METRIC_VERSION_MISMATCH"])

    def test_effect_not_causal(self):
        self.assertFalse(self.result()["causal_claim"])

    def test_effect_deterministic(self):
        expected = self.result()
        self.post.reverse()
        self.baseline.reverse()
        self.assertEqual(self.result(), expected)


class ImprovementAndPresentationTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.context = improvement_fixtures()

    def change(self, field, mutate):
        for row in self.rows:
            mutate(row["fields"][field]["value"])

    def result(self):
        return evaluate_improvement(self.rows, **self.context)

    def test_confirmed_neutral_no_recurrence_is_70(self):
        case = json.loads(FIXTURE.read_text())["improvement_case"]
        result = self.result()
        self.assertEqual(result["score"], case["expected_score"])
        self.assertEqual(result["status"], case["expected_status"])
        self.assertEqual(result["component_scores"], case["expected_components"])
        self.assertEqual(result["effect_summary"]["realized_prediction_effect"], "NEUTRAL")
        self.assertEqual(result["unique_fix_count"], 1)

    def test_interpretation_saved_in_canonical(self):
        interpretation = load_contract()["metric_specs_v1"]["improvement.interpretation"]
        self.assertIn("100/50/50/100 yield 70", interpretation)
        self.assertIn("never claim prediction accuracy improved", interpretation)

    def test_improvement_preserves_component_evidence_per_session(self):
        result = self.result()
        for row in result["evidence"].values():
            self.assertEqual(set(row["components"]), {"finding_confirmed", "d3_effect", "d10_effect", "non_recurrence"})
            self.assertEqual(row["source_references"]["fix"], "synthetic:fix")

    def test_partial_improvement_pending(self):
        for row in self.rows:
            row["fields"]["fix"]["classification"] = "PARTIAL"
        self.assertIsNone(self.result()["score"])

    def test_ambiguous_improvement_pending(self):
        for row in self.rows:
            row["fields"]["fix"]["classification"] = "AMBIGUOUS"
        self.assertIsNone(self.result()["score"])

    def test_missing_improvement_pending(self):
        for row in self.rows:
            del row["fields"]["fix"]
        self.assertIsNone(self.result()["score"])

    def test_nonrecurrence_invalid_count(self):
        self.change("recurrence", lambda v: v[0].update(recurrence_count=2))
        self.assertIsNone(self.result()["score"])

    def test_no_network_all_three(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = evaluate_stock(self.rows, **self.context)
        self.assertEqual(result["user_facing"]["improvement_accuracy_score"]["score"], 70)

    def test_recurrence_na_composite_pending(self):
        self.change("recurrence", lambda v: [r.update(observable_opportunities=0) for r in v])
        self.assertEqual(evaluate_stock(self.rows, **self.context)["internal_evidence"]["composite"], {"score": None, "status": "PENDING"})

    def test_user_explanation_regression(self):
        self.change("post_fix_cohort", lambda v: [r.update(score=50) for r in v])
        block = evaluate_stock(self.rows, **self.context)["user_facing"]["improvement_accuracy_score"]
        self.assertEqual(block["effect_summary"]["realized_prediction_effect"], "REGRESSED")
        self.assertIn("退步", block["explanation"])

    def test_us_improvement(self):
        self.context.update(market="US", symbol="SYNTHETIC_US")
        self.assertEqual(self.result()["score"], 70)

    def test_no_fix_pending_not_zero(self):
        self.change("fix", lambda v: v.update(status="PROPOSED"))
        self.assertEqual(self.result()["status"], "PENDING")
        self.assertIsNone(self.result()["score"])

    def test_no_samples_pending(self):
        self.change("post_fix_cohort", lambda v: v.clear())
        self.assertIsNone(self.result()["score"])

    def test_no_opportunities_na(self):
        self.change("recurrence", lambda v: [r.update(observable_opportunities=0) for r in v])
        self.assertEqual(self.result()["status"], "N/A")
        self.assertIsNone(self.result()["score"])

    def test_unconfirmed_finding_pending(self):
        self.change("finding", lambda v: v.update(status="PROPOSED"))
        self.assertIsNone(self.result()["score"])

    def test_missing_error_evidence(self):
        self.change("finding", lambda v: v.update(immutable_error_ref=""))
        self.assertIsNone(self.result()["score"])

    def test_future_approval(self):
        self.change("fix", lambda v: v.update(approved_at="2026-09-24T17:00:00+08:00"))
        self.assertIsNone(self.result()["score"])

    def test_detector_cannot_change(self):
        self.change("recurrence", lambda v: v[0].update(detector_version="different"))
        self.assertIsNone(self.result()["score"])

    def test_effective_session_mismatch(self):
        self.change("fix", lambda v: v.update(effective_session="2026-09-24"))
        self.assertIsNone(self.result()["score"])

    def test_immature_d10(self):
        self.change("fix", lambda v: v.update(effective_session="2026-09-23", effective_at="2026-09-23T12:00:00+08:00"))
        self.assertIsNone(self.result()["score"])

    def test_duplicate_recurrence_session(self):
        self.change("recurrence", lambda v: v[0].update(session_date=v[1]["session_date"]))
        self.assertIsNone(self.result()["score"])

    def test_future_cohort_not_backfilled_into_earlier_evaluation(self):
        self.change("post_fix_cohort", lambda v: v[0].update(available_at="2026-09-24T14:00:00+08:00"))
        self.assertIsNone(self.result()["score"])

    def test_improved_effect_labeled_not_causal(self):
        self.change("post_fix_cohort", lambda v: [r.update(score=80) for r in v])
        self.assertEqual(self.result()["effect_summary"]["realized_prediction_effect"], "IMPROVED")
        self.assertEqual(self.result()["score"], 76)

    def test_mixed_effect_not_claimed_sustained(self):
        self.change("post_fix_cohort", lambda v: [r.update(score=90 if i < 3 else 40) for i, r in enumerate(v)])
        self.assertEqual(self.result()["effect_summary"]["realized_prediction_effect"], "MIXED")

    def test_user_score_and_explanation(self):
        block = evaluate_stock(self.rows, **self.context)["user_facing"]["improvement_accuracy_score"]
        self.assertEqual(block["score"], 70)
        self.assertIn("不能宣稱預測準確度已提升", block["explanation"])
        self.assertEqual(block["effect_summary"]["realized_prediction_effect"], "NEUTRAL")

    def test_user_internal_separation(self):
        result = evaluate_stock(self.rows, **self.context)
        self.assertEqual(set(result["user_facing"]), {"prediction_accuracy_score", "improvement_accuracy_score", "investment_strategy_score",
                                                     "next_prediction_improvements", "next_improvement_loop_actions", "next_strategy_actions"})
        self.assertNotIn("source_ref", canonical_json(result["user_facing"]))
        internal = result["internal_evidence"]
        self.assertEqual(internal["evaluators"]["improvement"]["component_scores"], {"finding_confirmed": 100, "d3_effect": 50, "d10_effect": 50, "non_recurrence": 100})
        for key in ("source_coverage", "missing_fields", "sample_size", "confidence", "evidence_grade", "predecessor_report_reference"):
            self.assertIn(key, internal)
        self.assertEqual(internal["predecessor_report_reference"]["status"], "PENDING_251C")

    def test_pending_composite_no_reweight(self):
        self.change("fix", lambda v: v.update(status="PROPOSED"))
        result = evaluate_stock(self.rows, **self.context)
        self.assertEqual(result["internal_evidence"]["composite"], {"score": None, "status": "PENDING"})

    def test_complete_composite_fixed_weights(self):
        result = evaluate_stock(self.rows, **self.context)
        self.assertAlmostEqual(result["internal_evidence"]["composite"]["score"], 99.6 * .4 + 70 * .2 + 76 * .4)

    def test_output_deterministic_and_no_mutation(self):
        before = canonical_json(self.rows)
        expected = canonical_json(evaluate_stock(self.rows, **self.context))
        self.assertEqual(before, canonical_json(self.rows))
        self.rows.reverse()
        self.assertEqual(expected, canonical_json(evaluate_stock(self.rows, **self.context)))


if __name__ == "__main__":
    unittest.main()
