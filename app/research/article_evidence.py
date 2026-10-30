"""Bounded public article evidence; discovery is never investment evidence.

Network uses the existing DNS-pinned TW transport. No cookies, credentials,
browser evasion, login or paywall bypass. Bodies remain ephemeral.
"""
from datetime import datetime,timezone
import hashlib,json,re,time
from urllib.parse import urlparse,urljoin
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import requests
from app.loaders.batch_universe import identity_terms
from app.research.tw_news_content_relevance import _validate_public_url, _request_with_verified_ip, _read_limited_response

ALLOWED_HOSTS={'news.cnyes.com','finance.yahoo.com','www.sec.gov','news.google.com'}
UA='StockAIResearch/1.0'
EVENTS=[
 (r'revenue|營收','營收','營收變化影響成長預期；仍須核對同期基準與市場預期。'),
 (r'earnings|earnings per share|每股盈餘|財報','財報','財報須與預期及一次性項目比較，不能僅憑公布方向推定股價。'),
 (r'guidance|outlook|財測|展望','財測','展望調整影響未來獲利假設；確認管理層口徑與適用期間。'),
 (r'margin|毛利率|利潤率','利潤率','利潤率變化可能影響獲利品質，需排除一次性因素。'),
 (r'acqui(?:re|red|sition)|收購','收購','需確認交易條件、核准與整合風險。'),
 (r'contract|agreement|訂單|合約','合約','需核對金額、履約期間與實際營收認列。'),
 (r'launch|production|推出|量產','產品與產能','需追蹤正式交付與需求驗證，不能將規畫當作已實現營收。'),
]

def aware(value):
 if isinstance(value,(int,float)): return datetime.fromtimestamp(value,timezone.utc)
 d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
 if not d.tzinfo: raise ValueError('TIMEZONE_REQUIRED')
 return d.astimezone(timezone.utc)

def assess(text,*,title,entry,source_url,published_at,fetched_at,as_of,modified_at=None):
 base={'article_content_status':'HEADLINE_ONLY','investment_usable':False,'source_url':source_url,'published_at':published_at,'fetched_at':fetched_at,'content_length':len(text or ''),'facts':[],'direction':'unavailable','direction_status':'NOT_EVALUATED','prediction_consumed':False}
 try:
  cutoff=aware(as_of)
  if aware(published_at)>cutoff or (modified_at and aware(modified_at)>cutoff): return {**base,'article_content_status':'FAILED','reason':'AFTER_BATCH_AS_OF'}
 except (ValueError,TypeError,OverflowError): return {**base,'article_content_status':'FAILED','reason':'CONTENT_TIME_UNVERIFIED'}
 names=identity_terms(entry)
 if not names: return {**base,'reason':'COMPANY_IDENTITY_UNRESOLVED_OR_AMBIGUOUS'}
 clean=re.sub(r'\s+',' ',text or '').strip()
 if not clean or clean.casefold()==title.casefold(): return {**base,'reason':'HEADLINE_ONLY'}
 if re.search(r'subscribe to (?:continue|read)|sign in to (?:continue|read)|訂閱後閱讀|登入後閱讀',clean,re.I): return {**base,'article_content_status':'FAILED','reason':'ACCESS_RESTRICTED'}
 def belongs(sentence):
  return any(re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',sentence,re.I) if n.isascii() else n in sentence for n in names)
 facts=[]; categories=[]
 for sentence in re.split(r'(?<=[!?。！？])\s*|(?<=\.)\s+',clean):
  if len(sentence)<35 or sentence.casefold()==title.casefold() or not belongs(sentence): continue
  if re.search(r'disclaimer|all rights reserved|cookies|免責聲明|版權所有|may |might |could |rumou?r|傳聞|可能|據傳',sentence,re.I): continue
  event=next(((label,reading) for pattern,label,reading in EVENTS if re.search(pattern,sentence,re.I)),None)
  if not event or not re.search(r'\d',sentence): continue
  if sentence in [f['text'] for f in facts]: continue
  categories.append(event)
  facts.append({'text':sentence[:240],'source_url':source_url,'locator':'text-sha256:'+hashlib.sha256(sentence.encode()).hexdigest(),'confirmed':'reported_by_source_not_independently_verified'})
  if len(facts)==3: break
 if len(facts)<2: return {**base,'article_content_status':'PARTIAL','reason':'INSUFFICIENT_ATTRIBUTABLE_EVENT_FACTS','facts':facts}
 # Summary states only categories/numbers extracted from facts. No invented translation.
 name=entry.get('name') or entry.get('english_name') or entry['symbol']
 labels=list(dict.fromkeys(label for label,_ in categories))
 numbers=list(dict.fromkeys(re.findall(r'\d[\d,.]*(?:%|億|萬|million|billion)?',' '.join(f['text'] for f in facts))))[:8]
 return {**base,'article_content_status':'FULL_OR_SUBSTANTIVE','investment_usable':True,'reason':'ATTRIBUTABLE_FACTS_VERIFIED',
         'facts':facts,'content_sha256':hashlib.sha256(clean.encode()).hexdigest(),
         'chinese_summary':f'{name}：來源報導涉及'+ '、'.join(labels)+'；原文數據包含'+ '、'.join(numbers)+'。期間與單位請參照所附事實定位。',
         'investment_reading':' '.join(dict.fromkeys(reading for _,reading in categories)),
         'uncertainty':'單一來源敘述，尚未與公告及市場預期交叉驗證；證據不足，無法判斷價格方向。',
         'confirmation_condition':'核對公司公告、適用期間、數值單位與同期基準。','invalidation_condition':'來源更正、時間不符或公司歸屬不成立。','confidence':'limited'}

class ArticleRetriever:
 def __init__(self,*,request_budget=12,time_budget=30):
  self.remaining=request_budget; self.deadline=time.monotonic()+time_budget; self.robots={}; self.cache={}; self.last_request=0.0; self.minimum_interval=0.25
 def _get(self,url):
  parsed=urlparse(url)
  if parsed.scheme!='https' or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in (None,443): raise ValueError('SOURCE_NOT_ALLOWLISTED')
  if self.remaining<=0 or time.monotonic()>=self.deadline: raise ValueError('CONTENT_FETCH_BUDGET_EXHAUSTED')
  ok,reason,ips=_validate_public_url(url)
  if not ok: raise ValueError(reason)
  delay=max(0,self.minimum_interval-(time.monotonic()-self.last_request))
  if time.monotonic()+delay>=self.deadline: raise ValueError('CONTENT_FETCH_BUDGET_EXHAUSTED')
  if delay: time.sleep(delay)
  self.remaining-=1; self.last_request=time.monotonic()
  response=_request_with_verified_ip(requests,url,resolved_ip=ips[0],timeout=max(1,min(5,int(self.deadline-time.monotonic()))),headers={'User-Agent':UA})
  try:
   status=response.status_code; headers=dict(response.headers); body,err=_read_limited_response(response,max_bytes=1000000)
   if err: raise ValueError(err)
   return status,headers,body
  finally: response.close()
 def fetch(self,url):
  if url in self.cache: return dict(self.cache[url])
  original=url
  try:
   for _ in range(4):
    host=urlparse(url).hostname
    if host not in self.robots:
     status,_,text=self._get('https://'+str(host)+'/robots.txt')
     if status!=200: raise ValueError('ROBOTS_POLICY_UNAVAILABLE')
     robot=RobotFileParser(); robot.parse(text.splitlines()); self.robots[host]=robot
    if not self.robots[host].can_fetch(UA,url): raise ValueError('ROBOTS_DISALLOWED')
    policy=self.robots[host]; rate=policy.request_rate(UA)
    self.minimum_interval=max(0.25,float(policy.crawl_delay(UA) or 0),rate.seconds/rate.requests if rate and rate.requests else 0)
    status,headers,html=self._get(url)
    if status in (301,302,303,307,308):
     url=urljoin(url,headers.get('location') or headers.get('Location') or ''); continue
    if status!=200: raise ValueError('HTTP_'+str(status))
    content_type=(headers.get('content-type') or headers.get('Content-Type') or '').lower()
    if content_type and 'text/html' not in content_type and 'application/xhtml+xml' not in content_type: raise ValueError('NON_HTML_CONTENT')
    soup=BeautifulSoup(html,'html.parser')
    if urlparse(url).hostname=='news.google.com':
     # Only an explicit canonical publisher reference. Never guess/decode a URL.
     links=[x.get('href') for x in soup.select('link[rel="canonical"], a[href]')]
     targets=list(dict.fromkeys(u for u in links if urlparse(u or '').hostname in ALLOWED_HOSTS-{'news.google.com'} and ('/news/' in urlparse(u).path or '/news/id/' in urlparse(u).path)))
     target=targets[0] if len(targets)==1 else None
     if not target: raise ValueError('PUBLISHER_REDIRECT_UNRESOLVED')
     url=target; continue
    for node in soup(['nav','footer','script','style','aside','header']):
     if node.name=='script' and node.get('type')=='application/ld+json': continue
     node.decompose()
    bodies=[]; published=None; modified=None
    def inspect(value):
     nonlocal published,modified
     if isinstance(value,dict):
      types=value.get('@type') or []
      if isinstance(types,str): types=[types]
      if value.get('articleBody') or any(t in ('NewsArticle','Article','ReportageNewsArticle','AnalysisNewsArticle') for t in types):
       if value.get('articleBody'): bodies.append(str(value['articleBody']))
       if value.get('datePublished'): published=value['datePublished']
       if value.get('dateModified'): modified=value['dateModified']
      for v in value.values(): inspect(v)
     elif isinstance(value,list):
      for v in value: inspect(v)
    for node in soup.select('script[type="application/ld+json"]'):
     try: inspect(json.loads(node.string or '{}'))
     except (ValueError,TypeError): pass
     node.decompose()
    if not bodies:
     node=soup.select_one('article, [itemprop="articleBody"]')
     if node: bodies=[node.get_text(' ',strip=True)]
    if not published:
     node=soup.select_one('meta[property="article:published_time"]')
     published=node.get('content') if node else None
    result={'text':' '.join(bodies)[:24000],'source_url':url,'published_at':published,'modified_at':modified,'fetched_at':datetime.now(timezone.utc).isoformat(),'failure_reason':None}
    self.cache[original]=result; return dict(result)
   raise ValueError('REDIRECT_LIMIT')
  except Exception as exc:
   reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
   result={'text':'','source_url':url,'fetched_at':datetime.now(timezone.utc).isoformat(),'failure_reason':reason}
   self.cache[original]=result; return dict(result)

def enrich(items,*,entry,as_of,retriever):
 result=[]
 historical=(datetime.now(timezone.utc)-aware(as_of)).total_seconds()>1800
 for raw in items:
  value=dict(raw); item=dict(value.get('content') or value)
  url=item.get('canonicalUrl') or item.get('clickThroughUrl') or item.get('link') or item.get('url')
  if isinstance(url,dict): url=url.get('url')
  if historical:
   evidence={'article_content_status':'FAILED','investment_usable':False,'reason':'HISTORICAL_CONTENT_REFETCH_FORBIDDEN','facts':[]}
  else:
   fetched=retriever.fetch(str(url or ''))
   evidence=assess(fetched['text'],title=str(item.get('title') or ''),entry=entry,source_url=fetched['source_url'],published_at=fetched.get('published_at'),modified_at=fetched.get('modified_at'),fetched_at=fetched['fetched_at'],as_of=as_of)
   if fetched.get('failure_reason'): evidence.update(article_content_status='FAILED',investment_usable=False,reason=fetched['failure_reason'])
  item['article_evidence']=evidence; item['company_identity']=entry
  if evidence.get('published_at'): item['pubDate']=evidence['published_at']
  if 'content' in value: value['content']=item
  else: value.update(item)
  result.append(value)
 return result
