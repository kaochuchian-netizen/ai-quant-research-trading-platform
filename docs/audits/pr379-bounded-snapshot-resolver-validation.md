# PR #379：相容性修復與隔離 RSS 驗證

## 範圍與根因

既有 PR：#379；分支 `fix/oom-bounded-snapshot-resolver-20261106`。
基準 main：`9ae8e0f3d5e3aa8511f91b7e40ea5d3f3c51e087`。
修復前 PR HEAD：`85526ccdb100d07655c3c01eb77ac12b7dc0f5b2`。

`ai_dev_252_production_evidence_v1:SEMANTIC_VALIDATOR_FAILURE` 是 PR 引入的
相容性回歸。`ConsumerIsolationTests.test_sidecars_do_not_change_report_navigation_signature`
仍 import `_archive_signature`，PR 移除此介面導致 ImportError。
相同本機 Python 下，main 的原 validator 75/75 PASS，修復前 PR 為 75 項中
1 個 error，修復後為 75/75 PASS；不是 validator timeout 或治理門檻問題。

恢復 `_archive_signature(Path) -> tuple[(path, size, mtime_ns), ...]`，共用既有
sidecar 排除規則，只遍歷路徑及 stat metadata。沒有 payload 讀取、JSON parse、
全域 payload cache，沒有修改 validator、測試數門檻、registry 或 workflow。

## 回歸與 parity

指定測試：

```sh
python -m pytest tests/test_production_evidence.py tests/test_bounded_snapshot_resolver.py -q
python scripts/orchestrator/validate_ai_dev_252_production_evidence_v1.py
```

結果：82 tests PASS；semantic validator 75 tests PASS、0 skipped。
另外完成 py_compile 與 git diff --check。

新增測試驗證 signature 不讀 payload、所有七種 sidecar 不影響 signature、
不存在的目錄回傳空 tuple、metadata 改變可反映到 signature、沒有全域 cache。
使用真正 admission/write/hash 函式驗證 revision 1/2、latest/previous、無效新日期
與損壞 JSON 排除、snapshot_id 重算以及既有檔案 bytes 不變。

RSS 實驗另外跨 main 與修復版比對全部七個市場時段的 latest/previous snapshot_id、
所選日期所有 revision、payload hashes；使用原 admission_errors，沒有 mock gates。
每次量測後核對整批檔案 SHA-256 manifest，確認 immutable bytes 不變。

## Peak RSS 實測

測量日期：2026-11-06。環境：macOS 26.6.2 arm64、CPython 3.13.15。
兩版本使用同一個 `/tmp/pr379-venv/bin/python`、同一批 temporary archive bytes，
各規模各版本啟動三次全新 process，順序 main / PR 交替。
Peak RSS 使用 `resource.getrusage(RUSAGE_SELF).ru_maxrss`；macOS 原值為 bytes，
換算 MiB。資料生成在 parent，未計入 worker RSS；RSS 包含 worker import 與查詢。
不呼叫 production snapshot writer、Dashboard renderer 或任何 notification sender。

```sh
python scripts/orchestrator/benchmark_bounded_snapshot_resolver.py \
  --baseline /tmp/pr379-main --candidate /tmp/pr379-compat \
  --days 30 120 --records 256 --repeats 3
```

每個規模包含七個市場時段、每交易日兩個 revision，每 payload 256 個巢狀 records；
另有七個較新但不 admitted 的文件與七個 sidecars。每個 worker 依序對七個時段
呼叫 resolve_snapshots 與 latest 日期的 revisions_for_snapshot。

| 規模 | admitted snapshots | 全部檔案 | 實際 bytes | main RSS 中位數 | PR RSS 中位數 |
|---|---:|---:|---:|---:|---:|
| 30 trading dates | 420 | 434 | 37,787,667 | 109.83 MiB | 28.89 MiB |
| 120 trading dates | 1,680 | 1,694 | 149,291,907 | 358.64 MiB | 29.03 MiB |

較大規模 Peak RSS 減少約 91.9%。main 的 snapshot payload reads 由 427 增至
1,687；PR 兩規模均為 49（含七個 rejected 文件、latest/previous 兩日期各兩個
revision、latest revisions 再讀）。兩規模、各三次的所有 parity 檢查均 PASS。

原始逐次 RSS、耗時、dataset digest 與比對 identities 保存在
`pr379-bounded-snapshot-rss.json`。修復後 resolver 檔案 SHA-256：
`b5386bb7a9e867c013af486e7709f6784f96b5184e7382eb7344c5404d892a49`。

本實驗證明指定 resolver workload 不再隨歷史日期數量保留全庫 payload；
不是完整 production pipeline 的 memory profile，也不能宣稱所有 OOM 路徑已排除。
單一日期大量 revisions、單份超大 payload、明確要求 full archive list 的其他 caller
仍可能增加記憶體；此 PR 不變更其回傳契約。

## 安全與交付邊界

所有資料及測試在隔離 checkout / temporary directory；沒有 Production 檔案變更、
正式批次重跑、LINE/Email 發送、交易、merge 或部署。CI 結果以 PR 當前 HEAD 的
完整 GitHub Actions 檢查為準，不能以先前失敗或不同 SHA 的檢查代替。
