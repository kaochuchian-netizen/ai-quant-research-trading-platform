# AI-DEV-255D：archive/latest 呈現整合

## 根因與唯讀證據
Production code HEAD 為 da97737443cfd09773a89d218f11c285b614bd2c。
七個正式靜態 latest HTML 中，六個沒有 mobile_decision_presentation_v1 標記：
TW 07:00（2026-09-29 23:09 UTC）、13:05（09-24 05:14 UTC）、
13:35（09-18 05:41 UTC）、15:00（09-24 07:12 UTC）、
US 23:00（09-29 15:01 UTC）、06:30（09-29 22:31 UTC）。
US 20:00（09-30 12:01 UTC）已有新版及收折標記。
時間只是靜態檔案時間，不用來推論批次成功與否。

#336 的 code-only fast-forward 沒有重建 /var/www 靜態 HTML，
舊檔不會因 Python source 更新而自動刷新。新建 US 頁已有新版，
證明不是所有正式路徑都繞過新 renderer。

既有呼叫鏈：
approved delivery → synchronize_admitted_latest → publish_archive_latest_route
→ build_archive_route → render_snapshot_archive_page
→ render_immutable_snapshot_section → _snapshot_decision_content
→ 255 render_tw_window_report / render_us_window_report。

## 修正
保留同一正式呼叫鏈、resolver、snapshot identity、payload hash 與 publisher。
archive 頁標題及 window 選擇用繁體中文；加上 archive presentation version。
既有外層 lineage/provenance、revision history、跨日比較移到預設收折區。
TW 13:35 額外舊版 context 區塊同樣收折，不刪除。
TW 15:00 主卡固定五欄：今日預測結果、方向預測結果、區間預測結果、
今天實際走勢、今天實際區間。詳細 confidence/MFE/MAE/raw evidence 保留收折。
不改 prediction、strategy、schema、admission、delivery 或 snapshot selection。

## 驗證設計
使用既有 production-shaped synthetic admission fixture，限定 temporary root。
真正執行 write_snapshot → resolver → synchronize_admitted_latest →
temporary public archive/latest；也驗 previous route。
核對 source JSON bytes 完全不變、identity parity、重建 deterministic、
七窗口欄位及預設可見文字沒有 raw enums。
393px 實際完整 archive HTML（不是 renderer fragment）檢查欄位、收折與溢出。
所有 preview 標示 SYNTHETIC，不是 production 證據或 evaluator sample。

## Production 更新邊界
本 PR 不 deploy、不 publish、不 rerun、不通知。
因此既有 production 舊 HTML 在本任務後仍可能保留舊版；
未來核准部署時，必須把「程式同步」與「既有 snapshot 的靜態頁重建」
分開驗收，或等待原自然發布路徑。不得以本 PR CI PASS 宣稱 live UI 已更新。
沒有 scheduler、DB、secrets、nginx、model、strategy、交易或原始資料 mutation。
