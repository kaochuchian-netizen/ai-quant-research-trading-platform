#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.dashboard.multi_market_dashboard import _tw_preopen_product_html
from app.dashboard.visual_evidence_archive import _browser_render
from app.reports.tw_pre_open_structured import render_line
from app.reports.tw_preopen_product_intelligence import portfolio_summary, project_tw_preopen_product

def _news(title:str,tier:int=1)->dict:
 return {"evidence_id":"ev-"+str(abs(hash(title))),"headline":title,"summary":title+" 對今日價格判斷具可追蹤影響。","publisher":"MOPS" if tier==1 else "CMoney","source_tier":tier,"source_class":tier,"direction":"bullish","direction_status":"EVALUATED","freshness":"fresh","materiality":"high","published_at":"2026-08-14T06:30:00+08:00","source_url":"https://example.test/news","subject_contract":{"classification":"PRIMARY_SUBJECT","target_symbol":"2330"}}

def _card(symbol:str,direction:str,low:float,target:float,high:float,tier:int=1)->dict:
 names={"2330":"台積電","2337":"旺宏","6873":"泓德能源"}
 return {"market":"TW","window":"pre_open_0700","symbol":symbol,"stock_id":symbol,"name":names[symbol],"stock_name":names[symbol],"trading_date":"2026-08-14","action":"OBSERVE","decision":"OBSERVE","do_not_trade_reason":"正式條件尚未成立","current_price":(low+high)/2,"technical_data":{"direction":direction,"analysis_eligible":True},"strategies":{"daily_tactical":{"direction":direction}},"prediction_snapshot_v2":{"schema_version":"tw_prediction_snapshot_v2","prediction_identity":"twpre-"+symbol,"direction_forecast":direction,"range_forecast":{"low":low,"high":high},"reference_price":(low+high)/2,"confidence":68.0,"confidence_owner":"prediction_model","point_forecast":{"price":target,"method":"fixture_prediction_point_v1","owner":"tw_prediction_engine","horizon":"today","is_execution_target":False,"is_support":False,"is_resistance":False,"provenance":{"prediction_id":"twpre-"+symbol}}},"news_evidence":{"status":"available","evidence":[_news(symbol+" 重大營運事件",tier)],"evidence_funnel":{"count_semantics":"EXACT","stages":{"DISCOVERED":1,"RETRIEVED":1,"NORMALIZED":1,"SYMBOL_ATTRIBUTED":1,"MATERIAL":1,"FRESH":1,"ADMITTED":1}}}}

def _reject(base:dict,mutation)->bool:
 row=copy.deepcopy(base); mutation(row)
 try: project_tw_preopen_product(row)
 except ValueError: return True
 return False

def _chromium(html:str)->dict:
 with tempfile.TemporaryDirectory(prefix="ai218a-") as raw:
  root=Path(raw); page=root/"fixture.html"; png=root/"desktop.png"; pdf=root/"fixture.pdf"
  page.write_text("<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><style>body{font-family:'Noto Sans CJK TC',sans-serif}.preopen-product-core{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}@media(max-width:480px){.preopen-product-core{grid-template-columns:1fr}}</style></head><body data-market='TW' data-window='pre_open_0700' data-effective-trading-date='2026-08-14' data-snapshot-id='fixture' data-revision='1' data-payload-hash='fixture-hash'>"+html+"</body></html>",encoding="utf-8")
  rendered=_browser_render(page,png,pdf,timeout_ms=45_000); text=str(rendered.get("text") or "")
  ok=rendered.get("pdf_error") is None and png.exists() and pdf.exists() and png.stat().st_size>1000 and pdf.read_bytes().startswith(b"%PDF") and bool(rendered.get("font_diagnostics",{}).get("font_loaded"))
  return {"ok":ok,"png_size":png.stat().st_size if png.exists() else 0,"pdf_size":pdf.stat().st_size if pdf.exists() else 0,"text":text,"font":rendered.get("font_diagnostics")}
def validate()->dict:
 raw=[_card("2330","bullish",2330,2420,2465),_card("2337","bearish",126.25,130,135),_card("6873","range_bound",69,70.8,72.6)]
 cards=[project_tw_preopen_product(row) for row in raw]
 products=[row["tw_preopen_product_intelligence_v1"] for row in cards]
 by={row["symbol"]:row for row in products}; checks={}
 checks["natural_shaped_bull_bear_sideways"]=[by[s]["today_direction"] for s in ("2330","2337","6873")]==["BULLISH","BEARISH","SIDEWAYS"]
 checks["low_target_high_invariant"]=all(r["predicted_low"]<=r["target_price"]<=r["predicted_high"] for r in products)
 checks["symbol_specific_thesis"]=len({r["daily_thesis"] for r in products})==3 and all(r["symbol"] in r["daily_thesis"] for r in products)
 checks["news_attributed_and_limited"]=all(len(r["important_news"])<=3 and all(n["attribution_provenance"] for n in r["important_news"]) for r in products)
 checks["prediction_not_execution"]=all(r["target_provenance"]["owner"]=="tw_prediction_engine" and r["target_provenance"]["is_execution_target"] is False for r in products)
 checks["support_resistance_separate"]=all(r["support_resistance_alias_prediction_range"] is False for r in products)
 checks["technical_not_primary"]=all(r["technical_indicators_primary_surface"] is False for r in products)
 checks["decision_ownership"]=all(r["decision"]["ownership"]=="Decision Layer" for r in products)
 checks["portfolio_summary"]=portfolio_summary(cards)["counts"]=={"BULLISH":1,"BEARISH":1,"SIDEWAYS":1}
 line=render_line({"structured_pre_open_cards":cards},"https://example.test")
 checks["line_canonical_parity"]=all(x in line for x in ("偏多","偏空","盤整","2,420","2,330～2,465"))
 fragment="".join(_tw_preopen_product_html(row) for row in cards)
 checks["dashboard_direction_target_range_first"]=all(x in fragment for x in ("今日方向","目標價","預測區間","今日判斷","今日重要消息")) and fragment.index("今日方向")<fragment.index("今日判斷")
 checks["dashboard_no_indicator_dump"]=all(x not in fragment for x in ("RSI","MACD","KD 指標"))
 base=raw[0]
 checks["reject_reversed_range"]=_reject(base,lambda r:r["prediction_snapshot_v2"]["range_forecast"].update(low=2500,high=2300))
 checks["reject_target_below"]=_reject(base,lambda r:r["prediction_snapshot_v2"]["point_forecast"].update(price=2200))
 checks["reject_target_above"]=_reject(base,lambda r:r["prediction_snapshot_v2"]["point_forecast"].update(price=2600))
 checks["reject_missing_direction"]=_reject(base,lambda r:(r["prediction_snapshot_v2"].update(direction_forecast=None),r["technical_data"].update(direction=None),r["strategies"]["daily_tactical"].update(direction=None)))
 checks["reject_unsupported_direction"]=_reject(base,lambda r:(r["prediction_snapshot_v2"].update(direction_forecast="observe"),r["technical_data"].update(direction="observe"),r["strategies"]["daily_tactical"].update(direction="observe")))
 checks["reject_renderer_target"]=_reject(base,lambda r:r["prediction_snapshot_v2"]["point_forecast"].update(owner="renderer"))
 checks["reject_execution_target"]=_reject(base,lambda r:r["prediction_snapshot_v2"]["point_forecast"].update(is_execution_target=True))
 checks["reject_support_alias"]=_reject(base,lambda r:r["prediction_snapshot_v2"]["point_forecast"].update(is_support=True))
 checks["reject_confidence_alias"]=_reject(base,lambda r:r["prediction_snapshot_v2"].update(confidence_owner="research_evidence"))
 tier4=project_tw_preopen_product(_card("2330","bullish",2330,2420,2465,4))["tw_preopen_product_intelligence_v1"]
 checks["tier4_sentiment_not_primary"]=tier4["important_news"]==[] and tier4["today_direction"]=="BULLISH" and tier4["target_provenance"]["owner"]=="tw_prediction_engine"
 failed=_card("2330","bullish",2330,2420,2465)
 failed["news_evidence"]={"status":"retrieval_failed","evidence":[],"reason_code":"RETRIEVAL_FAILED","source_funnel":{"attempted":3,"succeeded":0}}
 failed_product=project_tw_preopen_product(failed)["tw_preopen_product_intelligence_v1"]
 checks["acquisition_failure_not_no_news"]=failed_product["news_diagnostics"]["retrieval_failed"] and "取得失敗" in failed_product["news_message"]
 many=_card("2330","bullish",2330,2420,2465)
 many["news_evidence"]["evidence"]=[_news("重大事件 "+str(i)) for i in range(4)]
 checks["primary_news_max_three"]=len(project_tw_preopen_product(many)["tw_preopen_product_intelligence_v1"]["important_news"])<=3
 visual=_chromium(fragment)
 checks["real_chromium_png_pdf_cjk"]=bool(visual["ok"]) and all(x in visual["text"] for x in ("偏多","偏空","盤整","目標價","預測區間"))
 return {"task_id":"AI-DEV-218A","contract_version":"ai_dev_218a_tw_preopen_product_intelligence_v1","ok":all(checks.values()),"checks":checks,"errors":[k for k,v in checks.items() if not v],"details":{"products":products,"visual":visual},"safety":{"production_rerun":False,"notifications":False,"trading":False,"scheduler":False,"production_db":False,"secrets":False,"immutable_history":False,"strategy_changed":False,"prediction_weights_changed":False,"execution_changed":False}}

def main()->int:
 parser=argparse.ArgumentParser(); parser.add_argument("--pretty",action="store_true"); args=parser.parse_args()
 result=validate(); print(json.dumps(result,ensure_ascii=False,indent=2 if args.pretty else None,sort_keys=True))
 return 0 if result["ok"] else 1
if __name__=="__main__": raise SystemExit(main())
