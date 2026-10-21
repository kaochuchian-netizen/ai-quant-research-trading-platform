from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from app.reports.tw_delivery_evaluation import (
    KEY, EVALUATION_KEY, bind_universe, complete_results, correction, digest,
    evaluate, freeze, quality,
)
from app.reports.post_close_quality_gate import evaluate_card
from app.reports.tw_four_window_decision import evaluate_post_close
from app.reports.tw_human_summary import build_tw_human_summary
from scripts.orchestrator.codex_delivery_correction import prepare

FIXTURE = json.loads((Path(__file__).parent / "fixtures/ai_dev_283_synthetic.json").read_text())
URL = "https://dashboard.example.test/stock-ai-dashboard/dashboard/archive/tw/post_close_1500/latest/index.html"


def seal(snapshot):
    snapshot["snapshot_id"] = digest({k: v for k, v in snapshot.items() if k != "snapshot_id"})
    return snapshot


def inputs(count=None, *, current=False):
    """Invented cases in independently sealed synthetic envelopes."""
    pre_cards = deepcopy(FIXTURE["pre_cards"])
    post_cards = deepcopy(FIXTURE["post_cards"])
    if count:
        pre_cards, post_cards = [], []
        for i in range(count):
            symbol = str(1000 + i) if i else "009991"
            p, q = deepcopy(FIXTURE["pre_cards"][i % len(FIXTURE["pre_cards"])]), deepcopy(FIXTURE["post_cards"][i % len(FIXTURE["post_cards"])] )
            for c in (p, q):
                c["symbol"] = c["stock_id"] = symbol
            p["prediction_snapshot_v2"]["symbol"] = symbol
            pre_cards.append(p); post_cards.append(q)
    if current:
        for c in pre_cards:
            c[KEY] = freeze(c, c["prediction_presentation_v1"])
    symbols = [c["symbol"] for c in pre_cards]
    base = {"schema_version": "window_snapshot_archive_v1", "market": "TW", "effective_trading_date": "2099-04-07",
            "revision": 1, "status": "complete", "run_kind": "scheduled", "runtime_provenance": "scheduled_production",
            "admitted": True, "admission_reason": "scheduled_production_admitted", "generated_at": "2099-04-07T07:00:00+08:00"}
    pre = seal({**base, "window": "pre_open_0700", "payload": {"market": "TW", "window": "pre_open_0700",
        "notification_universe": symbols, "tracking_symbols": symbols, "structured_pre_open_cards": pre_cards}})
    for c in post_cards:
        c.update({"source_snapshot_id": pre["snapshot_id"], "prediction_snapshot_id": pre["snapshot_id"],
                  "prediction_payload_hash": digest(pre["payload"]), "parent_source_payload_hash": digest(pre["payload"])})
    post = seal({**base, "window": "post_close_1500", "payload": {"market": "TW", "window": "post_close_1500",
        "notification_universe": symbols, "tracking_symbols": symbols, "structured_review_cards": post_cards}})
    return pre, post


def corrected(pre, post):
    return correction(pre, post, session="2099-04-07", revision=1,
                      expected_pre_id=pre["snapshot_id"], expected_post_id=post["snapshot_id"])


class FrozenDeliveryEvaluationTests(unittest.TestCase):
    def test_synthetic_conflicting_forecast_results(self):
        pre, post = inputs()
        rows = corrected(pre, post)["payload"]["structured_review_cards"]
        expected_direction = ["hit", "hit", "miss", "miss"]
        self.assertEqual([r[EVALUATION_KEY]["direction"]["result"] for r in rows], expected_direction)
        self.assertEqual([r[EVALUATION_KEY]["range"]["result"] for r in rows], ["partial_hit", "partial_hit", "hit", "miss"])
        for row, original in zip(rows, post["payload"]["structured_review_cards"]):
            # Raw legacy tactical scores are retained, never relabelled.
            self.assertEqual(row["predicted_direction"], original["predicted_direction"])
            self.assertEqual(row["direction_hit"], original["direction_hit"])

    def test_dynamic_universe_and_leading_zero(self):
        for count in (8, 10, 15, 30):
            with self.subTest(count=count):
                pre, post = inputs(count, current=True)
                symbols, bound = bind_universe(pre, session="2099-04-07")
                self.assertEqual(len(symbols), count)
                self.assertEqual(symbols[0], "009991")
                self.assertEqual(len(corrected(pre, post)["payload"]["structured_review_cards"]), count)

    def test_normal_pipeline_requires_persisted_projection(self):
        pre, _ = inputs()
        with self.assertRaisesRegex(ValueError, "PROJECTION_SCHEMA"):
            bind_universe(pre, session="2099-04-07")

    def test_legacy_is_explicit_and_cannot_reconstruct_conflicting_public_fields(self):
        pre, _ = inputs()
        pre["payload"]["structured_pre_open_cards"][0]["prediction_presentation_v1"]["direction"] = "bullish"
        seal(pre)
        with self.assertRaises(ValueError):
            bind_universe(pre, session="2099-04-07", allow_legacy=True)

    def test_no_trade_is_not_absent_published_forecast(self):
        pre, post = inputs()
        rows = {r["symbol"]: r for r in corrected(pre, post)["payload"]["structured_review_cards"]}
        for symbol in ("009991", "9104"):
            self.assertEqual(rows[symbol][EVALUATION_KEY]["direction"]["status"], "EVALUATED")
            self.assertEqual(rows[symbol][EVALUATION_KEY]["range"]["status"], "EVALUATED")

    def test_preopen_render_uses_frozen_projection_despite_tactical_change(self):
        pre, _ = inputs(current=True)
        card = pre["payload"]["structured_pre_open_cards"][0]
        card["predicted_direction"] = "neutral"
        human = build_tw_human_summary(card, "pre_open_0700")
        self.assertEqual(human["direction"], "BEARISH")
        self.assertEqual((human["forecast_low"], human["forecast_high"]), (40.00, 60.00))

    def test_actual_canonical_evaluator_calls_delivery_scoring(self):
        pre, post = inputs(current=True)
        _, bound = bind_universe(pre, session="2099-04-07")
        observed = deepcopy(post["payload"]["structured_review_cards"][0])
        observed.update({"session_open": observed["actual_open"], "session_high": observed["actual_high"],
                         "session_low": observed["actual_low"], "current_price": observed["actual_close"]})
        result = evaluate_post_close(observed, bound[observed["symbol"]])
        self.assertEqual(result[EVALUATION_KEY]["direction"]["result"], "hit")
        self.assertEqual(result["predicted_direction"], "bullish")

    def test_raw_hash_and_identity_fail_closed(self):
        for field, value in (("market", "US"), ("effective_trading_date", "2099-04-06"), ("snapshot_id", "x")):
            pre, _ = inputs(current=True); pre[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                bind_universe(pre, session="2099-04-07")

    def test_unbound_projection_retains_ohlc_with_structured_failure(self):
        pre, post = inputs(current=True)
        setup = pre["payload"]["structured_pre_open_cards"][0]
        original = post["payload"]["structured_review_cards"][0]
        observed = {**original, "session_open": original["actual_open"],
                    "session_high": original["actual_high"], "session_low": original["actual_low"],
                    "current_price": original["actual_close"]}
        result = evaluate_post_close(observed, setup)
        self.assertEqual(result["actual_close"], original["actual_close"])
        self.assertEqual(result[EVALUATION_KEY]["reason_code"], "DELIVERY_EVALUATION_IDENTITY_MISMATCH")
        self.assertIsNone(evaluate_card({**observed, **result}, market="TW", window="post_close_1500")["direction"]["result"])

    def test_universe_duplicate_missing_extra_rejected(self):
        for mutation in ("duplicate", "missing", "extra"):
            pre, _ = inputs(current=True)
            symbols = pre["payload"]["notification_universe"]
            if mutation == "duplicate": symbols.append(symbols[0])
            if mutation == "missing": symbols.pop()
            if mutation == "extra": symbols.append("123456")
            seal(pre)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                bind_universe(pre, session="2099-04-07")

    def test_results_identity_and_outcome_tamper_cannot_fallback_to_tactical(self):
        pre, post = inputs()
        row = corrected(pre, post)["payload"]["structured_review_cards"][0]
        for field, value in (("source_snapshot_id", "bad"), ("prediction_revision", 3), ("prediction_payload_hash", "bad"),
                             ("trading_date", "2099-04-06"), ("symbol", "9999"), ("actual_close", 51)):
            bad = deepcopy(row); bad[field] = value
            with self.subTest(field=field):
                result = evaluate_card(bad, market="TW", window="post_close_1500")
                self.assertIsNone(result["direction"]["result"])
                self.assertIsNone(result["range"]["result"])

    def test_projection_and_result_hash_tamper_rejected(self):
        pre, post = inputs(); row = corrected(pre, post)["payload"]["structured_review_cards"][0]
        for key in (KEY, EVALUATION_KEY):
            bad = deepcopy(row)
            if key == KEY: bad[key]["low"] = 1
            else: bad[key]["range"]["result"] = "hit"
            self.assertIsNone(quality(bad)[0]["result"])

    def test_partial_provisional_and_invalid_ohlc_fail_closed(self):
        pre, post = inputs(); row = corrected(pre, post)["payload"]["structured_review_cards"][0]
        for change in ({"actual_status": "provisional"}, {"actual_open": None}, {"actual_low": 70}):
            bad = {**row, **change}; bad[EVALUATION_KEY] = evaluate(bad, bad)
            self.assertIsNone(quality(bad)[0]["result"])

    def test_invalid_interval_and_nan_rejected(self):
        card = deepcopy(FIXTURE["pre_cards"][0])
        for low, high in ((50, 40), (float("nan"), 50), (None, 40)):
            public = deepcopy(card["prediction_presentation_v1"])
            public["today_range"] = {"predicted_low": low, "predicted_high": high}
            with self.assertRaises(ValueError): freeze(card, public)

    def test_missing_stock_retained_as_unassessable_not_filtered(self):
        pre, post = inputs(current=True); symbols, bound = bind_universe(pre, session="2099-04-07")
        rows = complete_results([], symbols, bound, [{"stock_id": symbols[0], "reason": "HISTORY_STALE"}])
        self.assertEqual([r["symbol"] for r in rows], symbols)
        self.assertEqual(rows[0]["actual_missing_reason"], "HISTORY_STALE")
        self.assertIsNone(quality(rows[0])[0]["result"])

    def test_no_published_forecast_is_na_not_strategy_based(self):
        pre, post = inputs(current=True)
        card = pre["payload"]["structured_pre_open_cards"][0]
        card["availability_status"] = "unavailable"
        card[KEY] = freeze(card, card["prediction_presentation_v1"])
        seal(pre)
        _, bound = bind_universe(pre, session="2099-04-07")
        row = post["payload"]["structured_review_cards"][0]
        row.update({"source_snapshot_id": pre["snapshot_id"], "prediction_snapshot_id": pre["snapshot_id"], "prediction_payload_hash": digest(pre["payload"])})
        result = evaluate(row, bound[row["symbol"]])
        self.assertEqual(result["direction"]["result"], "not_applicable")
        self.assertEqual(result["range"]["result"], "not_applicable")

    def test_render_all_channels_full_html_and_preserve_inputs(self):
        pre, post = inputs(); original = digest([pre, post])
        result = prepare(pre, post, session="2099-04-07", revision=1, expected_pre_id=pre["snapshot_id"],
                         expected_post_id=post["snapshot_id"], dashboard_url=URL)
        self.assertEqual(digest([pre, post]), original)
        html = result["index.html"]
        self.assertIn("<!doctype html>", html)
        self.assertIn("方向符合：2/4", html)
        self.assertIn("區間完全符合：1/4｜部分符合：2", html)
        self.assertIn("@media(max-width:640px)", html)
        self.assertIn("data-ai-dev-255-evidence", html)
        self.assertIn("40.00", html)
        for channel in ("line.txt", "email.txt"):
            for symbol in pre["payload"]["notification_universe"]:
                self.assertEqual(result[channel].count(symbol), 1)
            self.assertIn("04/07 15:00 更正報告", result[channel])
            self.assertIn(URL, result[channel])
            self.assertNotIn("不適用", result[channel])
        self.assertFalse(result["receipt.json"]["notification_sent"])

    def test_correction_idempotency_and_revision_separation(self):
        pre, post = inputs()
        self.assertEqual(corrected(pre, post), corrected(pre, post))
        second = correction(pre, post, session="2099-04-07", revision=2, expected_pre_id=pre["snapshot_id"], expected_post_id=post["snapshot_id"])
        self.assertNotEqual(second["snapshot_id"], corrected(pre, post)["snapshot_id"])

    def test_correction_rejects_wrong_expected_snapshot(self):
        pre, post = inputs()
        with self.assertRaisesRegex(ValueError, "EXPECTED_IDENTITY"):
            correction(pre, post, session="2099-04-07", revision=1, expected_pre_id="wrong", expected_post_id=post["snapshot_id"])

    def test_cli_has_no_send_or_publish_option(self):
        cli = Path(__file__).parents[1] / "scripts/orchestrator/codex_delivery_correction.py"
        result = subprocess.run([sys.executable, str(cli), "--help"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--send", result.stdout)
        self.assertNotIn("--publish", result.stdout)

    def test_cli_outputs_are_exclusive_and_inputs_unchanged(self):
        pre, post = inputs()
        cli = Path(__file__).parents[1] / "scripts/orchestrator/codex_delivery_correction.py"
        with TemporaryDirectory() as raw:
            root = Path(raw)
            for name, data in (("pre", pre), ("post", post)):
                (root / (name + ".json")).write_text(json.dumps(data), encoding="utf-8")
            originals = [(root / (name + ".json")).read_bytes() for name in ("pre", "post")]
            command = [sys.executable, str(cli), "--pre-open-input", str(root / "pre.json"),
                       "--post-close-input", str(root / "post.json"), "--expected-pre-id", pre["snapshot_id"],
                       "--expected-post-id", post["snapshot_id"], "--session", "2099-04-07",
                       "--correction-revision", "1", "--dashboard-url", URL, "--output-dir", str(root / "correction")]
            first = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt_path = root / "correction/receipt.json"
            receipt = receipt_path.read_bytes()
            repeat = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(repeat.returncode, 0)
            self.assertEqual(receipt_path.read_bytes(), receipt)
            self.assertEqual(originals, [(root / (name + ".json")).read_bytes() for name in ("pre", "post")])
            import hashlib
            saved = json.loads(receipt)
            for filename, key in (("line.txt", "line_sha256"), ("email.txt", "email_sha256"), ("index.html", "html_sha256")):
                self.assertEqual(hashlib.sha256((root / "correction" / filename).read_bytes()).hexdigest(), saved[key])


if __name__ == "__main__":
    unittest.main()
