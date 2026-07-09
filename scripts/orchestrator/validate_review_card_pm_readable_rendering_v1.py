#!/usr/bin/env python3
"""Validate PM-readable review card rendering and AI-DEV-150~155 regressions."""
from __future__ import annotations
import argparse, json, re, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen
ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
PUBLIC = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"
SNAPSHOT_INDEX = ROOT / "artifacts/archive/formal_forecast_snapshots/index/formal_forecast_snapshot_index_latest.json"
CALIBRATION = ROOT / "artifacts/runtime/forecast_calibration_proposal_latest.json"
BACKTEST = ROOT / "artifacts/runtime/formal_forecast_backtest_report_latest.json"
PREDICTION = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
REVIEW = ROOT / "artifacts/runtime/formal_prediction_review_runtime_latest.json"
class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.parts=[]
    def handle_data(self, data: str) -> None:
        if data.strip(): self.parts.append(data.strip())
    @property
    def text(self) -> str:
        return " ".join(self.parts)
def html_source(published: bool) -> str:
    if published:
        with urlopen(PUBLIC, timeout=10) as resp: return resp.read().decode("utf-8", errors="replace")
    return HTML.read_text(encoding="utf-8")
def text_only(source: str) -> str:
    parser=TextExtractor(); parser.feed(source); return parser.text
def section(text: str, start: str, end: str) -> str:
    if start not in text: return ""
    tail=text.split(start,1)[1]
    return tail.split(end,1)[0] if end in tail else tail
def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--pretty",action="store_true"); parser.add_argument("--published",action="store_true"); args=parser.parse_args()
    errors=[]; warnings=[]; source=html_source(args.published); text=text_only(source); main_text=text.split("技術檢查 / Debug",1)[0]; review=section(main_text,"實際結果 / 預測檢討狀態","資料新鮮度")
    if not review: errors.append("review card section missing")
    for raw in ["generated_at","data_quality","insufficient_data","reviewable single day","single-day deterministic evaluation"]:
        if raw in review: errors.append(f"raw review term leaked in main review card: {raw}")
    for raw_status in [" correct "," hit "," partial_hit "," miss "," incorrect "]:
        if raw_status in f" {review} ": errors.append(f"raw review status leaked in main review card: {raw_status.strip()}")
    for phrase in ["產生時間","資料品質摘要","單日檢討","7 天滾動檢討"]:
        if phrase not in review: errors.append(f"review card missing: {phrase}")
    if "正確" not in review and "資料待接" not in review: errors.append("review card must show 正確 or 資料待接")
    if "命中" not in review and "資料待接" not in review: errors.append("review card must show 命中 or 資料待接")
    if "7 天滾動檢討：資料不足，需累積更多正式 prediction / actual outcome artifact" not in review: errors.append("seven-day insufficient-data explanation missing")
    if "命中狀態可用；誤差明細欄位待接" in review and "高低價預測誤差：資料待接" in review: errors.append("review card shows inconsistent error fallback")
    if "fake high_low_forecast_error" in review: errors.append("fake high_low_forecast_error marker found")
    for phrase in ["部分資料可用","每日股價預測：資料待接","盤後檢討","未驗證實際送達內容","範例 artifact，不是正式最新報告"]:
        if phrase not in text: errors.append(f"AI-DEV-150 regression marker missing: {phrase}")
    if "資料正常" in main_text or "fresh" in main_text: errors.append("raw or over-optimistic freshness wording leaked into main UI")
    for phrase in ["formal prediction artifact 已接線","formal review artifact 已接線","deterministic_baseline_v1","待回測校準","資料待接"]:
        if phrase not in text: errors.append(f"AI-DEV-151/152 regression marker missing: {phrase}")
    pred=load(PREDICTION); rev=load(REVIEW)
    if pred.get("artifact_type")!="formal_prediction_runtime" or pred.get("forecast_value_count")!=36: errors.append("formal prediction runtime binding regressed")
    if pred.get("model_version")!="deterministic_baseline_v1": errors.append("deterministic_baseline_v1 missing from prediction artifact")
    if rev.get("artifact_type")!="formal_prediction_review_runtime" or rev.get("reviewable_stock_count")!=9: errors.append("formal review runtime binding regressed")
    backtest=load(BACKTEST)
    if backtest.get("method_under_test")!="deterministic_baseline_v1": errors.append("backtest method regressed")
    metrics=backtest.get("metrics") if isinstance(backtest.get("metrics"),dict) else {}
    if metrics.get("next_day_interval_hit_rate") not in (None,): warnings.append("next-day backtest hit rate is no longer null; verify data availability")
    calibration=load(CALIBRATION)
    if calibration.get("eligible_sample_count")!=9: errors.append("calibration sample count must remain 9")
    if calibration.get("tuning_gate_status")!="blocked_insufficient_sample": errors.append("calibration gate must remain blocked_insufficient_sample")
    for phrase in ["樣本數不足，不代表穩定績效","尚不可直接修改公式"]:
        if phrase not in text: errors.append(f"AI-DEV-154 dashboard marker missing: {phrase}")
    idx=load(SNAPSHOT_INDEX); minimum={"prediction_snapshot_count":1,"actual_outcome_snapshot_count":1,"review_snapshot_count":1,"eligible_same_day_sample_count":9}
    for key,val in minimum.items():
        if not isinstance(idx.get(key), int) or idx.get(key) < val: errors.append(f"snapshot index {key} expected >= {val}, got {idx.get(key)}")
    if idx.get("eligible_next_day_sample_count") != 0: warnings.append("next-day eligible sample count is no longer 0; verify next-day actual availability")
    progress=idx.get("calibration_gate_progress",{})
    if progress.get("ready_for_shadow_tuning_threshold")!=30 or progress.get("ready_for_formula_change_threshold")!=100: errors.append("snapshot thresholds regressed")
    if progress.get("current_gate_status")!="blocked_insufficient_sample": errors.append("snapshot gate must remain blocked_insufficient_sample")
    for row in idx.get("snapshots",[]):
        pred_path=row.get("prediction_snapshot_path")
        if pred_path:
            snap=load(ROOT/pred_path); meta=snap.get("snapshot_metadata",{})
            if snap.get("is_example") is True or meta.get("is_fake_backfilled_forecast") is not False: errors.append("prediction snapshot fake/example policy regressed")
    for phrase in ["Forecast Snapshot Accumulation / 預測樣本累積進度","已歸檔 prediction snapshots","Shadow tuning 門檻：30","Formula change 門檻：100","blocked_insufficient_sample"]:
        if phrase not in text: errors.append(f"AI-DEV-155 dashboard marker missing: {phrase}")
    secret_hits=[]
    for pattern in [r"Authorization:\s*Bearer\s+",r"api[_-]?key\s*[:=]",r"token\s*[:=]",r"BEGIN (?:RSA |OPENSSH )?PRIVATE KEY",r"\.env"]:
        if re.search(pattern,source,flags=re.I): secret_hits.append(pattern)
    if secret_hits: errors.append("secret-like pattern found in dashboard html")
    result={"ok":not errors,"published_mode":args.published,"errors":errors,"warnings":warnings,"summary":{"review_card_pm_readable":not errors,"single_day_review_present":"單日檢討" in review,"seven_day_review_present":"7 天滾動檢討" in review,"snapshot_gate":progress.get("current_gate_status"),"calibration_sample_count":calibration.get("eligible_sample_count"),"secret_pattern_hits":len(secret_hits)},"side_effects":{"files_modified":False,"db_write":False,"notification_sent":False,"production_pipeline_executed":False}}
    json.dump(result,sys.stdout,ensure_ascii=False,indent=2 if args.pretty else None,sort_keys=True); sys.stdout.write("\n"); return 0 if result["ok"] else 2
if __name__=="__main__": raise SystemExit(main())
