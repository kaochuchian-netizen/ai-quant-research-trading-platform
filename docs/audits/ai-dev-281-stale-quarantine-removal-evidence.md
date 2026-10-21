# AI-DEV-281 stale quarantine removal evidence

## Terminal CI evidence

GitHub Actions `validate-ai-branch` run `39535566358` reached terminal `SUCCESS`.
The run's raw terminal validator result records report `PASS` and `pass=true` for
all ten validator IDs formerly listed in the active quarantine.  This document
preserves the historical fingerprints and failure descriptions below; it is
not an executable exception list.

| Validator | Historical fingerprint | Historical failure evidence | CI 39535566358 terminal result |
| --- | --- | --- | --- |
| `ai_dev_208_visual_evidence_archive` | `12326a1826572a7c27ecea116838be0c012eeb7b7879f2539ad67f41601812a0` | Pre-existing identical visual evidence archive failure: case_a_tw_capture_success and case_b_us_capture_success fail on both base and head. | PASS |
| `ai_dev_209_h2_qualified_news_rre_rendering` | `bb8bb8ec310bbccc08fa9579b0b0e76d9a4c425443544ff0139e826d45a75b73` | Pre-existing identical AI-DEV-209-H2 semantic failure: case_l_ai210_regression fails on both base and head. | PASS |
| `ai_dev_209_h3_user_visible_research_presentation` | `49edf6bba36fc0da40e910314b123f5009eea9dfc33b1446a24e38cda7869a0a` | Pre-existing identical AI-DEV-209-H3 generated-artifact failure: rendered_text.md missing under the same artifact-relative path on both base and head; only temp roots differ. | PASS |
| `ai_dev_210_visual_evidence_pdf_retrieval` | `5036a266a68ce554350c0ea015efef57483b6eb670906fe275ad06febddcd372` | Pre-existing identical AI-DEV-210 validator exit failure: KeyError 'pdf' occurs on both base and head. | PASS |
| `ai_dev_211_chatgpt_artifact_transport` | `4b3628fd36d049346b472474c586d6630f98d5651a758d63928390ea973d00f8` | Pre-existing identical AI-DEV-211 validator exit failure: KeyError 'outbox_location' occurs on both base and head. | PASS |
| `ai_dev_212_h2_research_attribution_finalized_news_counter_argument` | `75b6f899522ddc75973cd7fdcdc7dd2bd4efaaaf84e8adb0d8eeb886ef8cc88b` | Pre-existing identical AI-DEV-212-H2 generated-artifact failure: screenshot_full.png missing under the same artifact-relative path on both base and head; only temp roots differ. | PASS |
| `ai_dev_212_research_semantic_visual_integrity` | `2c13de744414fd41b10958a72c1393c2d6a4fcba40e44f49ec7d740203910a3d` | Pre-existing identical AI-DEV-212 visual integrity generated-artifact failure: screenshot_full.png missing under the same artifact-relative path on both base and head; only temp roots differ. | PASS |
| `ai_dev_217_tw_prediction_news_continuity` | `343cf94fa2b429592e439815d2dc44735c176a1190652faa1c1f6ceebeadac14` | Pre-existing identical AI-DEV-217 browser-start failure: Playwright Chromium executable missing. | PASS |
| `ai_dev_218a_tw_preopen_product_intelligence` | `d13e6df1ac5880c79ed740da367bc4ee9571db0cf619b1bd3c96f155ca19ff50` | Pre-existing identical AI-DEV-218A browser-start failure: Playwright Chromium executable missing. | PASS |
| `ai_dev_218b_tw_preopen_news_readability_v1` | `21eae368bd0c063313b1b41953f80ad7aade420e7afde130bf11041d93eb73a2` | Pre-existing identical AI-DEV-218B browser-start failure: Playwright Chromium executable missing. | PASS |

## Active-policy change

`config/governance/known_validator_failures_v1.json` now has an empty `entries`
array.  Empty is a valid state: it means no known failure is currently allowed.
The registry still fails closed for an unregistered failure, malformed config,
or expired entry.  A future exception must include a complete active entry and
pass the same fingerprint and expiry validation.

## Scope

This records governance history only.  It neither changes production batch,
Dashboard, notification, scheduler, database, nor trading behavior.
