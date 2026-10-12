# AI-DEV-268A：TW 07:00 非交易日 session 與 unavailable card 修復

## 變更

- `app/market/tw_history_admission.py` 現在在未提供 fixture holiday set 時，載入 AI-DEV-251D 已治理的 pinned TWSE calendar snapshot，並以其完成 session 判定歷史資料 freshness。
- 交易日 snapshot 無法載入、驗證或解析時，admission 保持 fail-closed，回傳 `SOURCE_FAILED` 與 calendar reason；不會回退成 weekday heuristic。
- 有明確 `holiday_dates` 的既有 fixture caller 保留原本受控的 fixture 行為。
- `app/reports/mobile_decision_presentation.py` 對 07:00 unavailable card 顯示「資料不足，暫不判斷」，不再把未形成的預測投影為「盤整」。

## 2026-10-12 離線事件重播

使用 `config/governance/market_calendars/tw_2026_v1.json`（TWSE、pinned digest）解析：

- 2026-10-09：HOLIDAY
- 2026-10-10：HOLIDAY
- 2026-10-11：WEEKEND
- 2026-10-12 07:00 Asia/Taipei：current session 尚未完成
- expected completed session：`2026-10-08`

對 10 個 incident watchlist symbols 的等形狀 offline historical fixture，最新 2026-10-08、30 bars：admission `10/10 PASS`。最新 2026-10-07 仍為 `STALE`；2026-10-13 仍為 `FUTURE_DATA`；錯誤 calendar 仍 fail-closed。

10/12 production artifact 在 admission gate 後只保存 unavailable cards，沒有保存能重建成功 technical/news/model calculation 的完整 input bundle。因此本任務能證實 historical admission 修復，但不能把 synthetic fixture 冒充為 `PREDICTION_AVAILABLE=10/10` 的 production replay。下一個自然 07:00 是驗證後續 prediction/range/strategy 是否有獨立 blocker 的唯一安全證據。

## 驗證

- `tests.test_tw_non_trading_268a`：authoritative normal/weekend/holiday/consecutive-holiday/year-boundary、10 symbol incident admission、STALE/FUTURE/wrong-calendar fail-closed、unavailable LINE semantics。
- `tests.test_structured_card_258a`、`tests.test_tw_observed_257`：回歸通過。
- `validate_ai_dev_204_intelligence_health_hardening_v1.py`：PASS。
- `validate_ai_dev_229_tw_preopen_historical_admission_v1.py`：PASS。
- Python compile：PASS。

## Required status report

STATUS = IMPLEMENTED_PENDING_NATURAL_VERIFICATION
ROOT_CAUSE_FIXED = YES (authoritative calendar now owns production admission freshness)
SESSION_RESOLVER = pinned TWSE `market_calendar_snapshot_v1`; fail-closed on calendar failure
2026_10_12_EXPECTED_SESSION = 2026-10-08
HISTORICAL_ADMISSION = OFFLINE_INCIDENT_REPLAY_10_OF_10_PASS
PREDICTION_AVAILABLE = NOT_PROVABLE_OFFLINE_FROM_10_12_UNAVAILABLE_ARTIFACT
PRICE_RANGE_AVAILABLE = NOT_PROVABLE_OFFLINE_FROM_10_12_UNAVAILABLE_ARTIFACT
STRATEGY_AVAILABLE = NOT_PROVABLE_OFFLINE_FROM_10_12_UNAVAILABLE_ARTIFACT
UNAVAILABLE_CARD_FIXED = YES
INCIDENT_REPLAY = ADMISSION_PASS; no production rerun performed
LINE_PARITY = PASS (shared projection; unavailable cards render no sideways prediction)
TESTS = 95 unit/regression tests PASS; AI-DEV-204 PASS; AI-DEV-229 PASS
REGRESSION = PASS
BLOCKERS = Natural 07:00 evidence is required before claiming production prediction/range/strategy recovery.
PRODUCTION_WRITE = NO
NOTIFICATION_SENT = NO
PRODUCTION_MUTATION = NONE
NEXT = AI-DEV-268B
