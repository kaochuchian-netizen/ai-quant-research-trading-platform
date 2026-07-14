#!/usr/bin/env python3
"""Validate stable previous-date semantics and latest-only manual rerun publish."""
from __future__ import annotations
import argparse, hashlib, json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import app.dashboard.multi_market_dashboard as dashboard
from app.dashboard.window_snapshot_archive import resolve_snapshots, same_window_change, write_snapshot
def payload(marker:str)->dict[str,object]: return {"schema_version":"manual_revision_policy_test_v1","marker":marker}
def digest(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def main()->int:
 p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args(); checks={}
 with tempfile.TemporaryDirectory(prefix="ai-dev-180-revision-") as raw:
  root=Path(raw); archive=root/"archive"; output=root/"output"; public=root/"public"
  old_archive=dashboard.WINDOW_SNAPSHOT_ARCHIVE; dashboard.WINDOW_SNAPSHOT_ARCHIVE=archive
  try:
   def put(day:str,marker:str,kind:str="scheduled",stamp:str="15:02"):
    return write_snapshot(archive,market="TW",window="post_close_1500",effective_trading_date=day,generated_at=f"{day}T{stamp}:00+08:00",source_payload=payload(marker),status="completed",run_kind=kind,run_id=f"test-{marker}")
   put("2026-07-14","day14-r1"); put("2026-07-14","day14-r2","manual_rerun","20:18"); put("2026-07-14","day14-r3","manual_rerun","21:35")
   put("2026-07-15","day15-r1")
   initial=resolve_snapshots(archive,"TW","post_close_1500"); previous_id=initial.previous["snapshot_id"]
   dashboard.build_archive_route(output,"TW","post_close_1500","latest"); dashboard.build_archive_route(output,"TW","post_close_1500","previous")
   previous_path=output/"dashboard/archive/tw/post_close_1500/previous/index.html"; previous_hash=digest(previous_path)
   first_manual=put("2026-07-15","day15-r2","manual_rerun","20:18"); dashboard.publish_archive_latest_route("TW","post_close_1500",static_root=public,output_dir=output)
   second=resolve_snapshots(archive,"TW","post_close_1500")
   checks["revision_1_to_2"] = first_manual.get("revision")==2 and second.latest["revision"]==2
   checks["previous_unchanged_after_revision_2"] = second.previous["snapshot_id"]==previous_id and digest(previous_path)==previous_hash
   second_manual=put("2026-07-15","day15-r3","manual_rerun","21:35"); dashboard.publish_archive_latest_route("TW","post_close_1500",static_root=public,output_dir=output)
   third=resolve_snapshots(archive,"TW","post_close_1500")
   checks["revision_2_to_3"] = second_manual.get("revision")==3 and third.latest["payload"]["marker"]=="day15-r3"
   checks["previous_unchanged_after_revision_3"] = third.previous["snapshot_id"]==previous_id and digest(previous_path)==previous_hash
   latest_html=(output/"dashboard/archive/tw/post_close_1500/latest/index.html").read_text(encoding="utf-8")
   checks["latest_ui_revision_and_time"] = "Revision 3" in latest_html and "最後更新 21:35" in latest_html and "共手動更新 2 次" in latest_html
   previous_html=previous_path.read_text(encoding="utf-8")
   checks["previous_ui_hides_revision"] = "Revision" not in previous_html
   checks["latest_only_public_publish"] = (public/"dashboard/archive/tw/post_close_1500/latest/index.html").exists() and not (public/"dashboard/archive/tw/post_close_1500/previous/index.html").exists()
   put("2026-07-16","day16-r1")
   next_day=resolve_snapshots(archive,"TW","post_close_1500")
   checks["next_day_advances_previous"] = next_day.latest["effective_trading_date"]=="2026-07-16" and next_day.previous["effective_trading_date"]=="2026-07-15" and next_day.previous["revision"]==3
   checks["schema_manual_metadata"] = all(third.latest.get(k) is not None for k in ("revision","manual_rerun","effective_trading_date","batch_window","revision_created_at","original_batch_time","is_latest_revision"))
   checks["comparison_baseline"] = same_window_change(next_day.latest,next_day.previous).get("previous_trading_date")=="2026-07-15"
  finally: dashboard.WINDOW_SNAPSHOT_ARCHIVE=old_archive
 checks["temporary_archive_removed"]=not Path(raw).exists(); errors=[k for k,v in checks.items() if not v]
 result={"schema_version":"manual_rerun_revision_policy_validation_v1","task_id":"AI-DEV-180","ok":not errors,"errors":errors,"checks":checks,"safety":{"line_sent":False,"email_sent":False,"production_approved_delivery":False,"scheduler_changed":False,"trading":False,"python3_main_executed":False,"secrets_accessed":False}}
 print(json.dumps(result,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True)); return 0 if result["ok"] else 1
if __name__=="__main__": raise SystemExit(main())
