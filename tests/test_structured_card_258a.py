import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from app.reports.structured_card_diagnostics import CardValidationError, card_stage, failure_diagnostic, CATEGORIES
from app.reports.tw_pre_open_structured import build_card, unavailable_card, render_line
from app.reports.tw_prediction_explainability import project_tw_prediction_card, validate_interval
from app.reports.tw_preopen_product_intelligence import project_tw_preopen_product

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/ai_dev_258a_partial_replay_v1.json").read_text())
DATE = "2026-10-02"
TIME = DATE + "T07:03:43+08:00"

def replay(case):
    with patch("socket.socket", side_effect=AssertionError("NETWORK_FORBIDDEN")):
        return build_card(symbol=case["symbol"], name=case["name"], trading_date=DATE,
                          generated_at=TIME, indicator=deepcopy(case["indicator"]),
                          tactical=deepcopy(case["tactical"]))

class ReplayTests(unittest.TestCase):
    def test_provenance_limit_explicit(self):
        self.assertEqual(FIXTURE["evidence_status"], "PARTIAL_RECONSTRUCTION_NOT_EXACT_INCIDENT_REPLAY")
        self.assertIn("2330 news_bundle", FIXTURE["missing_original_inputs"])

    def test_2330_partial_replay_not_fabricated_incident_reproduction(self):
        c = replay(FIXTURE["cases"][0])
        self.assertEqual(c["symbol"], "2330")
        self.assertEqual(c["prediction_snapshot_v2"]["prediction_status"], "evaluable")
        self.assertNotIn("failure_category", c)

    def test_source_tactical_unchanged(self):
        for case in FIXTURE["cases"]:
            before = deepcopy(case)
            card = replay(case)
            self.assertEqual(case, before)
            self.assertEqual(card["strategies"]["daily_tactical"], before["tactical"])

    def test_fixed_time_replay_deterministic(self):
        self.assertEqual(replay(FIXTURE["cases"][0]), replay(FIXTURE["cases"][0]))

    def test_no_symbol_specific_fix(self):
        c = deepcopy(FIXTURE["cases"][0]); c["symbol"] = "7777"; c["tactical"]["stock_id"] = "7777"
        self.assertNotIn("failure_category", replay(c))

class ValidationTests(unittest.TestCase):
    def test_reversed_interval_still_rejected(self):
        with self.assertRaises(CardValidationError) as ctx: validate_interval(102, 100)
        self.assertEqual(ctx.exception.validation_codes, ["prediction_interval_reversed"])
        self.assertEqual(ctx.exception.validation_values["prediction_range.low"], 102)

    def test_incomplete_interval_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "prediction_interval_incomplete"): validate_interval(None, 100)

    def test_valid_interval_unchanged(self):
        self.assertEqual(validate_interval(100, 102), (100, 102))

    def test_next_interval_field_identity(self):
        with self.assertRaises(CardValidationError) as ctx: validate_interval(10, 9, name="next_session")
        self.assertEqual(ctx.exception.validation_values, {"next_session_range.low":10,"next_session_range.high":9})

    def test_semantic_conflict_still_rejected(self):
        c={"predicted_direction":"bullish","reasoning":"偏空","predicted_low":1,"predicted_high":2}
        with self.assertRaisesRegex(ValueError, "same_horizon_semantic_conflict"): project_tw_prediction_card(c,"pre_open_0700")

    def test_unknown_window(self):
        with self.assertRaisesRegex(ValueError, "unsupported_tw_prediction_window"): project_tw_prediction_card({},"bad")

    def test_product_target_still_rejected(self):
        c=replay(FIXTURE["cases"][1])
        c["prediction_snapshot_v2"]["point_forecast"]["price"]=99999
        with self.assertRaises(CardValidationError) as ctx: project_tw_preopen_product(c)
        self.assertIn("prediction_target_outside_interval",ctx.exception.validation_codes)
        self.assertEqual(ctx.exception.validation_values["point_forecast.price"],99999)

    def test_product_news_count_still_rejected(self):
        c=replay(FIXTURE["cases"][1])
        with patch("app.reports.tw_preopen_product_intelligence._news_funnel", return_value={"retrieved_count":1,"qualified_count":2,"selected_count":0}):
            with self.assertRaises(CardValidationError) as ctx: project_tw_preopen_product(c)
        self.assertIn("news_qualified_exceeds_retrieved",ctx.exception.validation_codes)

    def test_inner_stage_preserved(self):
        try:
            with card_stage("TACTICAL_UPGRADE"):
                with card_stage("PRODUCT_PROJECTION"):
                    raise CardValidationError("missing_prediction_target")
        except ValueError as e:
            d=failure_diagnostic(e,stage="STRUCTURED_CARD_BUILD",symbol="2330",run_id="fixed")
        self.assertEqual(d["substage"],"PRODUCT_PROJECTION")
        self.assertEqual(d["category"],"structured_card_validation_failed")
        self.assertEqual(d["validation_fields"],["point_forecast.price"])
        self.assertTrue(d["traceback_frames"])

    def test_build_card_actual_projection_substage(self):
        case=FIXTURE["cases"][0]
        with patch("app.reports.tw_four_window_decision.project_tw_preopen_product", side_effect=CardValidationError("missing_prediction_target")):
            with self.assertRaises(CardValidationError) as ctx: replay(case)
        self.assertEqual(failure_diagnostic(ctx.exception,stage="STRUCTURED_CARD_BUILD")["substage"],"PRODUCT_PROJECTION")

    def test_unknown_value_error_fail_closed_without_unsafe_text(self):
        e=ValueError("SENSITIVE_CANARY token=do_not_log")
        d=failure_diagnostic(e,stage="STRUCTURED_CARD_BUILD")
        self.assertEqual(d["reason_code"],"structured_card_validation_failed")
        self.assertNotIn("SENSITIVE_CANARY",json.dumps(d))

    def test_unknown_runtime_error_is_analysis(self):
        self.assertEqual(failure_diagnostic(RuntimeError("unknown"),stage="STRUCTURED_CARD_BUILD")["category"],"analysis_failed")

    def test_timeout_not_validation(self):
        self.assertEqual(failure_diagnostic(TimeoutError("private url"),stage="STRUCTURED_CARD_BUILD")["category"],"analysis_failed")

    def test_historical_invalid(self):
        self.assertEqual(failure_diagnostic(ValueError("bad"),stage="HISTORICAL_INDICATORS")["category"],"historical_data_invalid")

    def test_missing_file(self):
        self.assertEqual(failure_diagnostic(FileNotFoundError("private path"),stage="HISTORICAL_INDICATORS")["category"],"market_data_missing")

    def test_malicious_fields_redacted(self):
        e=CardValidationError("prediction_target_outside_interval",values={"point_forecast.price":"SENSITIVE_CANARY","token":"SENSITIVE_CANARY"})
        self.assertNotIn("SENSITIVE_CANARY",json.dumps(failure_diagnostic(e)))

    def test_traceback_does_not_include_locals_or_source(self):
        try:
            secret_canary="SENSITIVE_CANARY"
            raise RuntimeError(secret_canary)
        except Exception as e:
            d=failure_diagnostic(e)
        self.assertTrue(d["traceback_frames"])
        self.assertNotIn("SENSITIVE_CANARY",json.dumps(d))
        self.assertTrue(all(set(f)=={"file","function","line"} for f in d["traceback_frames"]))

    def test_unknown_code_redacted(self):
        d=failure_diagnostic(CardValidationError("SENSITIVE_CANARY"))
        self.assertNotIn("SENSITIVE_CANARY",json.dumps(d))

    def test_multiple_validation_codes_retained(self):
        e=CardValidationError(["missing_prediction_target","invalid_prediction_interval"])
        self.assertEqual(len(failure_diagnostic(e)["validation_codes"]),2)

    def test_diagnostic_id_stable(self):
        e=CardValidationError("missing_prediction_target")
        self.assertEqual(failure_diagnostic(e),failure_diagnostic(e))

class FallbackTests(unittest.TestCase):
    def test_2330_incident_fallback_no_false_market_missing(self):
        c=unavailable_card("2330","台積電",DATE,"analysis_failed:ValueError",TIME)
        self.assertNotIn("market_data",c["missing_fields"])
        self.assertEqual(c["failure_category"],"analysis_failed")

    def test_category_partition(self):
        for reason in CATEGORIES:
            c=unavailable_card("2330","台積電",DATE,reason,TIME)
            self.assertEqual(c["failure_category"],reason)
            self.assertEqual("market_data" in c["missing_fields"],reason=="market_data_missing")
            self.assertEqual(c["availability_status"],"unavailable")
            self.assertEqual(c["opportunity_group"],"unavailable")

    def test_historical_reason_retained(self):
        c=unavailable_card("2330","台積電",DATE,"historical_data_admission:STALE",TIME)
        self.assertEqual(c["failure_reason_code"],"STALE")
        self.assertEqual(c["failure_category"],"historical_data_invalid")
        self.assertNotIn("market_data",c["missing_fields"])

    def test_missing_historical_file(self):
        c=unavailable_card("2330","台積電",DATE,"historical_data_admission:historical_csv_missing",TIME)
        self.assertEqual(c["failure_category"],"market_data_missing")

    def test_line_no_debug_details(self):
        c=unavailable_card("2330","台積電",DATE,"structured_card_validation_failed",TIME)
        payload={"structured_pre_open_cards":[c],"cards":[c],"tracking_symbols":["2330"]}
        text=render_line(payload,"https://example.invalid")
        for raw in ["ValueError","traceback","structured_card_validation_failed","SENSITIVE_CANARY"]:
            self.assertNotIn(raw,text)
        self.assertNotIn("traceback_frames",json.dumps(c))

    def test_unknown_reason_not_exposed(self):
        c=unavailable_card("2330","台積電",DATE,"SENSITIVE_CANARY",TIME)
        self.assertNotIn("SENSITIVE_CANARY",json.dumps(c))

    def test_hash_covers_final_fallback(self):
        from app.reports.tw_pre_open_structured import seal_card_source_payload_hash
        c=unavailable_card("2330","台積電",DATE,"structured_card_validation_failed",TIME)
        self.assertEqual(c,seal_card_source_payload_hash(c))

    def test_real_pipeline_exception_handler_offline(self):
        # Compile only the real exception handler, never import/run the pipeline.
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr
        from types import SimpleNamespace
        tree=ast.parse((ROOT/"app/pipelines/pre_open_pipeline.py").read_text())
        handler=next(n for n in ast.walk(tree) if isinstance(n,ast.ExceptHandler)
                     and any(isinstance(x,ast.Name) and x.id=="diagnostic" for x in ast.walk(n)))
        code=compile(ast.fix_missing_locations(ast.Module(body=handler.body,type_ignores=[])),"handler_only","exec")
        cards={}; finished=[]
        env={"e":CardValidationError("missing_prediction_target"),
             "analysis_substage":"STRUCTURED_CARD_BUILD","stock_id":"2330","stock_name":"台積電",
             "context":{"pipeline_run_id":"offline","run_date":DATE},"failure_diagnostic":failure_diagnostic,
             "json":json,"sys":sys,"failed_reports":[],"structured_card_by_symbol":cards,
             "_store_structured_pre_open_card":lambda mapping,card:mapping.update({card["symbol"]:card}),
             "build_unavailable_pre_open_card":unavailable_card,
             "stage_timing":SimpleNamespace(finish=lambda *a,**k:finished.append(k)),"stage_name":"stock_analysis_2330"}
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err): exec(code,env)
        d=json.loads(err.getvalue())
        self.assertEqual(d["reason_code"],"missing_prediction_target")
        self.assertEqual(cards["2330"]["failure_category"],"structured_card_validation_failed")
        self.assertNotIn("market_data",cards["2330"]["missing_fields"])
        self.assertNotIn("missing_prediction_target",out.getvalue())
        self.assertEqual(finished[0]["status"],"failed")

    def test_pipeline_logs_only_diagnostic_not_card(self):
        source=(ROOT/"app/pipelines/pre_open_pipeline.py").read_text()
        self.assertIn('print(json.dumps(diagnostic, ensure_ascii=False, sort_keys=True), file=sys.stderr',source)
        self.assertNotIn('f"analysis_failed:{reason}"',source)
        self.assertIn('analysis_substage = "STRUCTURED_CARD_BUILD"',source)

def _case_test(case):
    def test(self):
        c=replay(case)
        self.assertEqual(c["technical_data"]["history_bars"],123)
        self.assertTrue(c["technical_data"]["analysis_eligible"])
        self.assertEqual(c["predicted_direction"],case["expected_tactical_direction"])
        self.assertNotIn("failure_category",c)
    return test
for case in FIXTURE["cases"]:
    setattr(ReplayTests,"test_saved_aggregate_"+case["symbol"],_case_test(case))
if __name__=="__main__":unittest.main()
