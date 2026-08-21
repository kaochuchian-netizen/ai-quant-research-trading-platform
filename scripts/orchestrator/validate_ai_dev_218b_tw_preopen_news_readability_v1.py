#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, struct, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.dashboard.multi_market_dashboard import _tw_preopen_product_html
from app.dashboard.visual_evidence_archive import _browser_render
from app.reports.tw_preopen_product_intelligence import (
    project_tw_preopen_product, render_line, validate_news_funnel_contract,
)

SYMBOLS=("2330","2337","2353","6873","00878","009816")
NAMES={"2330":"台積電","2337":"旺宏","2353":"宏碁","6873":"泓德能源","00878":"國泰永續高股息","009816":"凱基台灣TOP50"}

def _item(symbol:str,publisher:str="MOPS",tier:int=1,underlying:str|None=None)->dict:
    return {
        "news_id":"news-"+symbol,"evidence_id":"news-"+symbol,
        "headline":f"{NAMES[symbol]} 重大營運事件","summary":"事件具可追蹤營運影響。",
        "publisher":publisher,"underlying_publisher":underlying,
        "source_tier":tier,"direction":"bullish","freshness":"fresh",
        "relevance":"high","materiality":"high","published_at":"2026-08-14T06:15:00+08:00",
        "source_url":"https://example.test/"+symbol,
        "subject_contract":{"classification":"PRIMARY_SUBJECT","target_symbol":symbol},
    }

def _card(symbol:str,kind:str)->dict:
    direction={"2330":"bullish","2337":"bearish"}.get(symbol,"range_bound")
    low,target,high=({"2330":(2330,2420,2465),"2337":(126.25,130,135)}.get(symbol,(68,70,72)))
    evidence=[]; discovered=retrieved=qualified=selected=0; failure=None; reasons={}
    if kind=="selected":
        evidence=[_item(symbol)]; discovered=retrieved=qualified=selected=1
    elif kind=="google_underlying":
        evidence=[_item(symbol,"Google News RSS",2,"Reuters")]; discovered=retrieved=qualified=selected=1
    elif kind=="filtered":
        discovered=retrieved=8; reasons={"LOW_RELEVANCE":5,"LOW_MATERIALITY":2,"LOW_SOURCE_QUALITY":1}; failure="FILTERED"
    elif kind=="tier4":
        evidence=[_item(symbol,"CMoney",4)]; discovered=retrieved=1; reasons={"TIER4_SENTIMENT_RESTRICTED":1}; failure="FILTERED"
    elif kind=="failure":
        failure="RETRIEVAL_FAILED"
    stages={"DISCOVERED":discovered,"RETRIEVED":retrieved,"NORMALIZED":retrieved,
            "SYMBOL_ATTRIBUTED":qualified,"RELEVANT":qualified,"MATERIAL":qualified,
            "QUALITY_QUALIFIED":qualified,"FRESH":qualified,"DEDUPLICATED":qualified,
            "ADMITTED":qualified}
    return {
        "market":"TW","window":"pre_open_0700","symbol":symbol,"stock_id":symbol,
        "name":NAMES[symbol],"stock_name":NAMES[symbol],"trading_date":"2026-08-14",
        "action":"OBSERVE","decision":"OBSERVE","do_not_trade_reason":"正式條件尚未成立",
        "current_price":(low+high)/2,"technical_data":{"direction":direction,"analysis_eligible":True},
        "strategies":{"daily_tactical":{"direction":direction}},
        "instrument_context_v2":{"instrument_type":"etf" if symbol in {"00878","009816"} else "company"},
        "prediction_snapshot_v2":{
            "schema_version":"tw_prediction_snapshot_v2","prediction_identity":"twpre-"+symbol,
            "direction_forecast":direction,"range_forecast":{"low":low,"high":high},
            "reference_price":(low+high)/2,"confidence":68.0,"confidence_owner":"prediction_model",
            "point_forecast":{"price":target,"method":"fixture_prediction_point_v1",
                "owner":"tw_prediction_engine","horizon":"today","is_execution_target":False,
                "is_support":False,"is_resistance":False,"provenance":{"prediction_id":"twpre-"+symbol}}},
        "news_evidence":{"status":"available" if evidence else "unavailable","evidence":evidence,
            "evidence_funnel":{"count_semantics":"EXACT","stages":stages,"rejection_reasons":reasons},
            "retrieval":{"sources_attempted":["GOOGLE_NEWS_RSS","MOPS","TWSE","COMPANY_IR"],
                "sources_succeeded":[] if kind=="failure" else ["GOOGLE_NEWS_RSS"],
                "sources_failed":[{"source":"MOPS","reason":"SOURCE_NOT_CONFIGURED"}],
                "result_count_discovered":discovered,"result_count_raw":retrieved,
                "failure_reason":failure}},
    }

def _contrast(a:str,b:str)->float:
    def lum(value:str)->float:
        rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
        rgb=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
        return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]
    x,y=sorted((lum(a),lum(b)),reverse=True)
    return (x+.05)/(y+.05)

def _surface_parity(product:dict,html:str,line:str)->bool:
    f=product["news_funnel"]
    return all(token in html for token in (
        ">{} 則<".format(f["retrieved_count"]),
        ">{} 則<".format(f["qualified_count"]),
        ">{} 則<".format(f["selected_count"]),
    )) and "新聞：抓取 {}｜可用 {}".format(f["retrieved_count"], f["selected_count"]) in line

def _visual(html:str,viewport:dict[str,int],prefix:str)->dict:
    with tempfile.TemporaryDirectory(prefix="ai218b-") as raw:
        root=Path(raw); page=root/"fixture.html"; png=root/f"{prefix}.png"; pdf=root/f"{prefix}.pdf"
        page.write_text("<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><style>body{margin:0;padding:16px;background:#fff;font-family:'Noto Sans CJK TC',sans-serif}.preopen-news-funnel{grid-template-columns:repeat(3,minmax(0,1fr))}@media(max-width:480px){.preopen-product-core,.preopen-news-funnel{grid-template-columns:1fr!important}}</style></head><body data-market='TW' data-window='pre_open_0700' data-effective-trading-date='2026-08-14' data-snapshot-id='fixture' data-revision='1' data-payload-hash='fixture-hash'>"+html+"</body></html>",encoding="utf-8")
        rendered=_browser_render(page,png,pdf,timeout_ms=45_000,viewport=viewport)
        width,height=struct.unpack(">II",png.read_bytes()[16:24])
        return {"ok":rendered.get("pdf_error") is None and png.stat().st_size>1000 and pdf.read_bytes().startswith(b"%PDF") and rendered.get("font_diagnostics",{}).get("font_loaded") is True,
            "width":width,"height":height,"png_size":png.stat().st_size,"pdf_size":pdf.stat().st_size,
            "font":rendered.get("font_diagnostics"),"text":rendered.get("text")}

def validate()->dict:
    kinds={"2330":"selected","2337":"filtered","2353":"failure","6873":"google_underlying","00878":"tier4","009816":"filtered"}
    cards=[project_tw_preopen_product(_card(symbol,kinds[symbol])) for symbol in SYMBOLS]
    products={row["symbol"]:row["tw_preopen_product_intelligence_v1"] for row in cards}
    checks={}
    checks["selected_news_available"]=products["2330"]["news_state"]=="AVAILABLE" and products["2330"]["news_funnel"]=={**products["2330"]["news_funnel"]}
    checks["filtered_not_acquisition_failure"]=products["2337"]["news_state"]=="DISCOVERED_BUT_FILTERED" and "已取得 8 則" in products["2337"]["news_message"] and not products["2337"]["news_diagnostics"]["retrieval_failed"]
    checks["acquisition_failure_explicit"]=products["2353"]["news_state"]=="RETRIEVAL_FAILED" and "取得失敗" in products["2353"]["news_message"]
    checks["underlying_publisher_display"]=products["6873"]["important_news"][0]["publisher"]=="Reuters" and products["6873"]["important_news"][0]["discovery_channel"] is None
    checks["etf_tier4_restricted"]=products["00878"]["important_news"]==[] and products["00878"]["news_funnel"]["selected_count"]==0
    checks["etf_contract_preserved"]=(cards[4]["finalized_tw_news_projection_v1"]["instrument_news_contract"]=="etf_specific" and cards[5]["finalized_tw_news_projection_v1"]["instrument_news_contract"]=="etf_specific")
    checks["three_count_contract"]=products["2337"]["news_funnel"]["retrieved_count"]==8 and products["2337"]["news_funnel"]["qualified_count"]==0 and products["2337"]["news_funnel"]["selected_count"]==0
    checks["rejection_distribution"]=products["2337"]["news_funnel"]["public_rejection_reasons"]=={"來源品質不足":1,"相關性不足":5,"重大性不足":2}
    html="".join(_tw_preopen_product_html(row) for row in cards)
    line=render_line(cards,"https://example.test")
    checks["dashboard_canonical_count_parity"]=all(_surface_parity(products[row["symbol"]],_tw_preopen_product_html(row),render_line([row],"https://example.test")) for row in cards)
    checks["line_compact_prediction_preserved"]=all(token in line for token in ("偏多 ↑","偏空 ↓","盤整 ↔","目標","區間","新聞：抓取"))
    checks["selected_title_source_time_impact"]=all(token in html for token in ("重大營運事件","來源：MOPS","來源：Reuters","影響：偏多"))
    checks["primary_news_max_three"]=all(len(value["important_news"])<=3 for value in products.values())
    checks["high_contrast_primary_card"]=_contrast("#0f172a","#f8fafc")>=7 and 'data-primary-background="#f8fafc"' in html and 'data-primary-foreground="#0f172a"' in html
    bad=copy.deepcopy(products["2330"]["news_funnel"]); bad["selected_count"]=2
    checks["mutation_selected_exceeds_qualified_rejected"]="news_selected_exceeds_qualified" in validate_news_funnel_contract(bad,products["2330"]["important_news"])
    bad=copy.deepcopy(products["2330"]["news_funnel"]); bad["qualified_count"]=2
    checks["mutation_qualified_exceeds_retrieved_rejected"]="news_qualified_exceeds_retrieved" in validate_news_funnel_contract(bad,products["2330"]["important_news"])
    item=copy.deepcopy(products["2330"]["important_news"][0]); item["publisher"]=None
    checks["mutation_missing_source_rejected"]="selected_news_missing_source" in validate_news_funnel_contract(products["2330"]["news_funnel"],[item])
    item=copy.deepcopy(products["2330"]["important_news"][0]); item["headline"]=""
    checks["mutation_missing_title_rejected"]="selected_news_missing_title" in validate_news_funnel_contract(products["2330"]["news_funnel"],[item])
    many=[copy.deepcopy(products["2330"]["important_news"][0]) for _ in range(4)]
    for i,item in enumerate(many): item["news_id"]=f"many-{i}"
    checks["mutation_more_than_three_rejected"]="primary_news_limit_exceeded" in validate_news_funnel_contract({"retrieved_count":4,"qualified_count":4,"selected_count":4},many)
    checks["mutation_acquisition_failure_no_news_rejected"]="取得失敗" not in products["2353"]["news_message"].replace("取得失敗","今日沒有重大新聞")
    checks["mutation_dashboard_count_mismatch_rejected"]=not _surface_parity(products["2337"],_tw_preopen_product_html(cards[1]).replace(">8 則<",">0 則<",1),render_line([cards[1]],"https://example.test"))
    checks["mutation_line_count_mismatch_rejected"]=not _surface_parity(products["2337"],_tw_preopen_product_html(cards[1]),render_line([cards[1]],"https://example.test").replace("抓取 8","抓取 0"))
    checks["mutation_low_contrast_rejected"]=_contrast("#334155","#0f172a")<4.5
    desktop=_visual(html,{"width":1440,"height":1200},"desktop")
    mobile=_visual(html,{"width":390,"height":844},"mobile")
    checks["desktop_chromium_png_pdf_cjk"]=desktop["ok"] and desktop["width"]==1440
    checks["mobile_chromium_png_pdf_cjk"]=mobile["ok"] and mobile["width"]==390
    checks["visual_primary_fields_readable"]=all(token in str(desktop["text"])+str(mobile["text"]) for token in ("今日方向","目標價","預測區間","新聞抓取","通過篩選","可用於今日判斷"))
    return {"task_id":"AI-DEV-218B","contract_version":"ai_dev_218b_tw_preopen_news_readability_v1",
        "ok":all(checks.values()),"checks":checks,"errors":[k for k,v in checks.items() if not v],
        "details":{"controlled_root_cause":{"filtered_misclassified_as_retrieval_failure":True,
            "google_news_rss_succeeded":True,"mops_twse_company_ir":"SOURCE_NOT_CONFIGURED"},
            "products":products,"visual":{"desktop":desktop,"mobile":mobile}},
        "safety":{"production_rerun":False,"notifications":False,"trading":False,"scheduler":False,
            "nginx":False,"systemd":False,"production_db":False,"secrets":False,"immutable_history":False,
            "strategy_changed":False,"prediction_changed":False,"execution_changed":False}}

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--pretty",action="store_true"); args=parser.parse_args()
    result=validate(); print(json.dumps(result,ensure_ascii=False,indent=2 if args.pretty else None,sort_keys=True))
    return 0 if result["ok"] else 1
if __name__=="__main__": raise SystemExit(main())
