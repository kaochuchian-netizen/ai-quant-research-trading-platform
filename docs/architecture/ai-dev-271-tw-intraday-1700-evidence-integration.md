# AI-DEV-271：TW 1 分鐘觀測證據與 17:00 整合設計

15:00 先以同交易日、immutable 07:00 `payload.tracking_symbols` 綁定的 v2 collection manifest 為唯一來源。每個 symbol 僅能引用該 manifest 中的 content-addressed artifact，或引用其 terminal structured failure；不得從 current watchlist、其他交易日或 mutable latest 補值。

`SPARSE_UNVERIFIED` 只會形成 `tw_intraday_observed_path_evidence_v1`：保留 artifact digest、source、calendar、觀測/預期/缺失分鐘、coverage 與 observed open/close/high/low。它的 `evidence_status=OBSERVED_ONLY`、`path_metrics_status=INSUFFICIENT_EVIDENCE`，不得提供 first touch、occupancy、MFE、MAE 或宣稱完整日內高低與完整走勢。只有未來有 authoritative full-session proof 的 `COMPLETE` artifact 才可在既有 contract 下形成 full-path metrics。

17:00 的後續整合應只讀取 immutable 15:00 card 的 `intraday_observed_path_evidence_v1` 與同 session manifest，並以 digest 驗證 07:00 universe binding。17:00 可把 observed-only 資訊列為診斷證據與 coverage/missingness；不得把它併入 prediction hit/miss、strategy score、finding/fix 閾值或 MFE/MAE。若某 symbol 是 collection failure，17:00 應保留其 structured failure，不得以另一 symbol 或前日資料補足。

此設計不改變 17:00 Learning Loop 的現有 scoring；需要獨立 approval 才能把 verified full-path metrics 納入任何 evaluation 或 learning decision。
