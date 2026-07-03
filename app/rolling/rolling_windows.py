from __future__ import annotations
from collections import Counter
from typing import Any
from .schemas import RollingWindowResult
WINDOW_SPECS=[('last_7_records',7),('last_20_records',20),('last_60_records',60),('all_available',None)]
def _date(r): return r.get('generated_at') or r.get('run_date') or ''
def status(n:int)->str:
    if n<5: return 'insufficient'
    if n<20: return 'unstable'
    if n<60: return 'usable'
    return 'stronger_confidence'
def build_rolling_windows(records:list[dict[str,Any]])->list[dict[str,Any]]:
    ordered=sorted(records,key=_date)
    out=[]
    for wid,n in WINDOW_SPECS:
        subset=ordered[-n:] if n else ordered
        usable=[r for r in subset if r.get('artifact_status') in {'valid','partial'}]
        excluded=[r for r in subset if r not in usable]
        dates=[_date(r)[:10] for r in subset if _date(r)]
        out.append(RollingWindowResult(wid,'record_count',dates[0] if dates else None,dates[-1] if dates else None,len(subset),len(usable),len(usable)<5,[r.get('record_id','') for r in usable],[r.get('record_id','') for r in excluded],dict(Counter(r.get('artifact_status','unknown') for r in excluded)),status(len(usable))).to_dict())
    for wid,days in [('last_7_trading_days',7),('last_20_trading_days',20)]:
        day_values=sorted({_date(r)[:10] for r in ordered if _date(r)})[-days:]
        subset=[r for r in ordered if _date(r)[:10] in day_values]
        usable=[r for r in subset if r.get('artifact_status') in {'valid','partial'}]
        out.append(RollingWindowResult(wid,'trading_days',day_values[0] if day_values else None,day_values[-1] if day_values else None,len(subset),len(usable),len(usable)<5,[r.get('record_id','') for r in usable],[r.get('record_id','') for r in subset if r not in usable],{},status(len(usable))).to_dict())
    return out
