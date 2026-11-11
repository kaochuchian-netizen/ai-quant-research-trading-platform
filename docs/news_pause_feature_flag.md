# 台美股新聞抓取暫停

預設停用：未設定、`0` 或無效值均輸出 `NEWS_PAUSED`／「新聞功能暫停」。
唯一啟用值為 `STOCK_AI_NEWS_FETCH_ENABLED=1`。Production 未經使用者新的明確批准，不得設定啟用值，亦不得由自動重試、fallback 或健康檢查重新啟用。

停用涵蓋 Yahoo ticker.news、Google RSS、CNYES 搜尋／瀏覽器建立與恢復、共用全文 HTTP／DNS 與新聞 AI。停用檢查在搜尋、瀏覽器及正文入口執行，不能靠傳入 session 或命中舊正文 cache 繞過。股價、歷史價格、技術分析、預測、策略學習及 SEC 財報資料流程維持原本程式；LINE／Email／Dashboard 仍照原排程執行，只顯示新聞暫停。

不修改歷史新聞或 immutable snapshots。純研究／呈現函式仍可處理歷史 frozen evidence，不依現在的 flag 改寫過去結果。台股新聞分數維持原本中性 50，不捏造新聞。

驗證：`env -u STOCK_AI_NEWS_FETCH_ENABLED python -m unittest tests.test_news_pause`。測試阻擋任何 DNS／HTTP 並斷言 Yahoo news、搜尋、瀏覽器、重試及新聞 AI 沒有被呼叫；驗證行情及台美股暫停呈現。
既有 acquisition fixtures 在 CI 明確以 flag=1 驗證原功能，不刪除安全與品質測試。新增必要 pause job 會移除該旗標，且測試內清除環境，以證明預設停用。CI 的測試設定不得帶入 Production。

恢復方式：只有取得使用者明確批准後，才能以獨立受控變更將此非機密 feature flag 設為 1；本次不建立自動恢復機制、不改 cron 或 secrets。回復為 0 或移除設定即可重新停用。
