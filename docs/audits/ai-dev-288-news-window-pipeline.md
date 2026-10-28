# AI-DEV-288 — 日期區間、新聞採納與分析管線

## 範圍與根因

本次僅修復既有新聞管線；不執行正式批次、不改正式產物、不發送通知。
基準 main：6638343a0045b6539a34471fe73ccc9f4a2eb5ac。

原 RSS discovery 在日期驗證前截取五筆；CNYES 和下游 freshness
使用不同窗口；失效的 browser 仍被後續股票重用；AI prompt 在正式新聞
admission 前選取候選；Gemini exception 字串與整個分析 bundle 進入顯示層，
造成來源、內容失敗及分析失敗的語意混淆。

## 日期與來源契約

- 盤前及盤後共同使用批次 created_at 的台北時區 as_of。
- 使用既有 pinned TW session calendar；start 取 as_of 前 72 小時與上一個
  completed session close 中較早者，涵蓋週末及連假。缺少 calendar evidence
  時停止採納，不自行猜前一交易日。
- RSS 逐日重疊 after/before 查詢，最多 8 requests、400 unique candidates；
  24 秒為不再開始新 request 的時間預算，單一 request timeout 最長 8 秒。
  HTTP timeout 不是整體硬性 wall-clock watchdog。
- RSS 不提供可靠 exhaustive cursor；即使所有請求成功，coverage 仍為
  PARTIAL（有候選）或 UNKNOWN（沒有候選），絕不宣稱 COMPLETE。
  日期條件不能取代逐筆原始 timestamp 的本地驗證。
- 來源排序不可假設為日期排序。截斷、parse、transport、timeout、query/candidate
  budget 均保留 reason codes。過期、未來或不明日期不能 admitted。
- CNYES 保留 bounded lazy-load/scroll；open_article 失效後不再使用同一失效
  browser 導航，使用既有安全 HTTP extraction fallback。每 batch 最多一次
  browser replacement，沒有提高全域 timeout。

## 採納與分析

每次保存 fetched / in_window / outside_window / duplicates / deduped /
relevant / admitted / analysis_selected / analyzed。失敗候選與未分析候選保留。
正式 admission 沿用全文、股票關聯、重大性、來源與歸屬門檻；ETF 公司新聞
不適用、全文不可用、關聯未完成、來源失敗、日期未知不再被混為「不相關」。

正式 admitted 沒有五筆上限。HTTP 全文補足最多 12 次、30 秒停止啟動新請求；
已取得全文不受此數量限制。沒有全文者保留 CONTENT_BUDGET_EXHAUSTED 等原因，
不得以標題代替全文通過門檻。Gemini 僅收到 admitted evidence，依重要性排序後
最多 6 篇／每篇 900 字元／總計 3600 字元，未選者標示 ANALYSIS_BUDGET。

Gemini 狀態區分 SUCCESS、TIMEOUT、QUOTA、TRANSPORT_ERROR、PARSE_ERROR、
CONFIGURATION_ERROR、SKIPPED；沒有 admitted evidence 不呼叫 AI。
只保留穩定錯誤碼，不將 provider exception 原文放入新聞 UI。
繁中主卡呈現具體不可用原因；完整來源、窗口與 funnel 診斷預設收折。

## 隔離驗證

所有新增 fixtures 完全合成；未提交 Production payload、receipt、收件者或憑證。

- AI-DEV-288、browser lifecycle、frozen projection regression：80 tests，
  70 PASS、10 個 Linux-only process checks 在 Mac skipped；正式 Linux CI 另驗證。
- 新聞 aggregation validator：24/24 PASS。
- content/relevance/materiality validator：61/61 PASS。
- presentation contract 及 mobile decision presentation validator：PASS。
- 本機 Chromium 393px：無橫向溢出；診斷預設關閉、可展開。
- RSS 13 筆亂序合成候選（12 窗口內、1 過期）：12 筆通過同一正式 admission。
- 合成 9 筆 admitted：6 筆分析、3 筆保留 budget reason；沒有 admission 截斷。
- 2337 合成缺全文案例不得產生無證據 AI 摘要；6873 五筆合成候選，
  只有一筆日期與證據有效，另外四筆保留過期原因。
- 覆蓋長假、週末、calendar coverage 缺口、未知時間、跨日/tampered window、
  RSS 截斷、ETF、CNYES timeout/fallback、Gemini 四類錯誤及 malformed response。

既有 validator 的變更只對齊更精確的 rejection reason、明確 as_of 與中文文案；
仍要求 rejected case admitted=0。沒有新增 bypass、quarantine 或放寬新聞門檻。
完整 branch registry 由正式 GitHub CI 執行，不在本機重複啟動高成本全套。

## 剩餘限制與發布邊界

RSS 排名/截斷及 CNYES lazy-load 無法證明窗口窮盡性；HTTP paywall/403、全文補足
預算、Gemini 額度及實際網路品質仍可能使 admitted/analyzed 為零。不能據此宣稱
沒有新聞，也不能保證所有重大新聞均已蒐集。年度 calendar evidence 缺失維持
fail-closed。AI 結論的語意正確性仍需後續真實自然批次證據，測試不保證模型無幻覺。

PR/CI 不代表 Production 已修復；本任務不 merge、不 sync、不修改歷史 snapshot。
AI-DEV-282 維持 PAUSED。
