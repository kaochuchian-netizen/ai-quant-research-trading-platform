# 策略學習閉環隔離驗收

基準 Production/main：83d526a766352e8a803963f268ca3debb7f2fe4d。

## 安全與證據界線

採用使用者批准的方案 A：共用 supervisor 提供 run、market、window、session、mode 與時效，進度紀錄不再授權或拒絕 Capture。manual、dry-run、unknown、衝突及過期 fail closed；共用 .frozen 寫入端再次檢查。這不是同 UID 惡意程序的安全邊界。沒有改 OS 權限、排程、通知設定或交易。

US 保存同次既有行情的完整 OHLC、quote hash、接收時間、來源及 session；不增加市場或新聞請求。V2 receipt 固定原始 learning reference 與 payload，重播不讀取最新 learning。兩秒限制、外層 alarm 與非主執行緒保持安全退化。

## 隔離驗收

262 項相關單元測試通過。真實輸入副本驗收見 isolated-acceptance.json；它不是自然批次證據。
TW 使用 11/19 2330 原始卡片、CSV 及 15:00 結果，在測試時鐘重建封存。
US 使用實際於 2026-11-19T14:21:30.933561Z 接收的 AAPL 盤前行情，以及 23:39:05.072381Z 接收的當日收盤日線；在隔離路徑重建 receipt，不宣稱當時正式批次曾封存。
兩市場各 1 筆 Prediction → Outcome → Evaluation → Learning → Renderer 成功。3/10 日均不足，不產生完整分數。11/17、18、19 三份 V1 產物原樣 replay，全部來源雜湊不變。

重現：使用既有合法輸入副本，執行 scripts/orchestrator/verify_learning_closure_isolated.py --input-root INPUT --source-evidence SOURCES --output-root NEW_OUTPUT。
輸出必須與來源、程式目錄分離；驗收階段 socket 連線強制拒絕。不呼叫正式批次、外部新聞、通知或交易。dependency observed 檔僅記錄本機測試版本，CI 使用既有 Python 3.10 依賴規格。

## 版本與回退

先提交相容 reader，再於後續 commit 啟用每日 V2 writer。V1 derive/build/replay/hash/learning_id 保持不變；V2 使用獨立 .daily_evaluation_v2 命名空間。V1/V2 predecessor 分派驗證，未知版本拒絕。V2 治理分類必須驗證路徑、identity 與完整 replay。
回退到相容 reader commit `6a605b5` 時，保留全部 V2 檔案；V1 writer 偵測 V2 後拒絕另開歷史鏈，reader 仍可讀兩版本。不得直接回退到不認得 V2 的舊基準或刪除產物。正式操作須另行授權。

## 尚待正式驗收

未合併、未部署。部署後仍須 TW/US 新自然批次累積事前 frozen evidence 並確認 17:00 配對；不足 3/10 日保持樣本不足。程式與隔離測試通過不等於策略學習正式恢復。
