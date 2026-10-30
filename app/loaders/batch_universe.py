"""Batch-owned Sheet universe. No network, alternate watchlist or current lookup."""
from copy import deepcopy
import hashlib
import json
import re

TRUE = {'true', 'yes', '1', 'y', 'enabled', 'on', '是', '啟用'}
FALSE = {'false', 'no', '0', 'n', 'disabled', 'off', '否', '停用'}
ALIASES = {
 'symbol': ('symbol','stock_id','ticker','代號','股票代號'),
 'name': ('name','company_name','公司名稱','名稱','股票名稱'),
 'english_name': ('english_name','英文名稱','company_english_name'),
 'aliases': ('aliases','alias','別名'), 'industry': ('industry','產業'),
 'market': ('market','市場'), 'enabled': ('enabled','啟用','active'),
}
def field(row,key):
 lower={str(k).strip().lower():v for k,v in row.items()}
 return next((lower[k] for k in ALIASES[key] if k in lower),None)

def enabled(value):
 text=str(value if value is not None else '').strip().lower()
 if not text: return True  # existing optional-column contract
 if text in TRUE: return True
 if text in FALSE: return False
 raise ValueError('UNKNOWN_ENABLED_VALUE')

def normalize_rows(rows,market):
 if market not in ('TW','US'): raise ValueError('UNKNOWN_MARKET')
 result=[]; seen={}
 for row in rows:
  raw=str(field(row,'symbol') or '').strip().upper()
  if not raw: continue
  declared=str(field(row,'market') or market).strip().upper()
  declared={'台股':'TW','美股':'US','TAIWAN':'TW','USA':'US'}.get(declared,declared)
  if declared!=market: raise ValueError('SHEET_MARKET_MISMATCH')
  active=enabled(field(row,'enabled'))
  if not re.fullmatch(r'[0-9]{4,6}[A-Z]?' if market=='TW' else r'[A-Z][A-Z0-9.\-]{0,14}',raw): raise ValueError('INVALID_SYMBOL')
  entry={'symbol':raw,'market':market,'enabled':active,'name':str(field(row,'name') or '').strip(),
         'english_name':str(field(row,'english_name') or '').strip(),
         'industry':str(field(row,'industry') or '').strip(),
         'aliases':list(dict.fromkeys(str(x).strip() for x in (field(row,'aliases') if isinstance(field(row,'aliases'),list) else re.split(r'[;,；，|]',str(field(row,'aliases') or ''))) if str(x).strip()))}
  for key in ('currency','exchange','note','source_sheet','source_kind'):
   if key in row: entry[key]=deepcopy(row[key])
  if raw in seen:
   if seen[raw]!=entry: raise ValueError('CONFLICTING_DUPLICATE_SYMBOL')
   continue
  seen[raw]=entry; result.append(entry)
 return result

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def freeze(rows,*,market,batch_as_of,source):
 entries=[deepcopy(x) for x in rows if x.get('enabled',True)]
 if not entries: raise ValueError('EMPTY_EFFECTIVE_UNIVERSE')
 if len({e['symbol'] for e in entries})!=len(entries) or any(e.get('market')!=market for e in entries): raise ValueError('INVALID_UNIVERSE')
 owners={}
 for e in entries:
  for name in [e.get('name'),e.get('english_name'),*e.get('aliases',[])]:
   if name: owners.setdefault(name.casefold(),set()).add(e['symbol'])
 for e in entries:
  e['ambiguous_aliases']=[name for name in [e.get('name'),e.get('english_name'),*e.get('aliases',[])] if name and len(owners[name.casefold()])>1]
 value={'schema_version':'batch_sheet_universe_v1','market':market,'batch_as_of':str(batch_as_of),'source':deepcopy(source),'entries':entries,'symbols':[e['symbol'] for e in entries]}
 return {**value,'universe_id':digest(value)}

def validate(value):
 copied=deepcopy(value); expected=copied.pop('universe_id',None)
 if expected!=digest(copied) or copied.get('schema_version')!='batch_sheet_universe_v1': raise ValueError('UNIVERSE_HASH_MISMATCH')
 if copied['symbols']!=[e['symbol'] for e in copied['entries']]: raise ValueError('UNIVERSE_SYMBOL_MISMATCH')
 return deepcopy(value)

def identity_terms(entry):
 ambiguous={str(x).casefold() for x in entry.get('ambiguous_aliases',[])}
 names=[entry.get('name'),entry.get('english_name'),*entry.get('aliases',[])]
 return list(dict.fromkeys(str(n).strip() for n in names if n and len(str(n).strip())>=2 and str(n).strip().casefold() not in ambiguous and str(n).upper()!=entry.get('symbol')))

def query(entry):
 names=identity_terms(entry)
 if not names: raise ValueError('COMPANY_IDENTITY_UNRESOLVED_OR_AMBIGUOUS')
 safe=lambda s: re.sub(r'[^\w\s.&\-\u3400-\u9fff]',' ',str(s)).strip()
 return '('+' OR '.join('"'+safe(n)+'"' for n in names)+') '+safe(entry['symbol'])+' '+safe(entry.get('industry',''))

def require_parity(universe,symbols):
 frozen=validate(universe)
 if list(symbols)!=frozen['symbols']: raise ValueError('BATCH_UNIVERSE_PARITY_MISMATCH')

def historical_universe(snapshot):
 """Only immutable input, never a live Sheet loader or latest alias."""
 if not snapshot.get('snapshot_id') or not snapshot.get('effective_trading_date'): raise ValueError('IMMUTABLE_SNAPSHOT_REQUIRED')
 payload=snapshot.get('payload') or {}
 if payload.get('batch_universe'): return validate(payload['batch_universe'])
 rows=payload.get('items') or payload.get('structured_pre_open_cards') or []
 symbols=[str(r.get('symbol') or r.get('stock_id')) for r in rows if r.get('symbol') or r.get('stock_id')]
 if not symbols: symbols=list(payload.get('tracking_symbols') or [])
 if not symbols: raise ValueError('HISTORICAL_UNIVERSE_UNAVAILABLE')
 return freeze([{'symbol':s,'market':snapshot.get('market') or payload.get('market'),'enabled':True} for s in symbols],market=snapshot.get('market') or payload['market'],batch_as_of=snapshot.get('generated_at'),source={'kind':'immutable_legacy_snapshot','snapshot_id':snapshot['snapshot_id'],'revision':snapshot.get('revision')})
