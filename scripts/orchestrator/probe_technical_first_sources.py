#!/usr/bin/env python3
"""Bounded public-source read-only probe; never backfill historical predictions."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.research.article_evidence import ArticleRetriever, assess


def main():
    cases=[('TW','2330','台積電','https://news.cnyes.com/news/id/6641359'),
           ('TW','6438','迅得','https://news.cnyes.com/news/id/6644200'),
           ('US','AAPL','蘋果','https://news.cnyes.com/news/id/6644734')]
    retriever=ArticleRetriever(request_budget=8,time_budget=45)
    rows=[]
    for market,symbol,name,url in cases:
        fetched=retriever.fetch(url)
        cutoff=datetime.now(timezone.utc).isoformat()
        ev=assess(fetched.get('text',''),title=fetched.get('title') or '',
                  entry={'market':market,'symbol':symbol,'name':name},source_url=fetched['source_url'],
                  published_at=fetched.get('published_at'),modified_at=fetched.get('modified_at'),
                  fetched_at=fetched['fetched_at'],as_of=cutoff)
        if fetched.get('failure_reason'):
            ev.update(article_content_status='FAILED',investment_usable=False,reason=fetched['failure_reason'])
        rows.append({'market':market,'symbol':symbol,'company':name,'title':fetched.get('title'),
                     'source_url':url,'published_at':fetched.get('published_at'),
                     'body_length':len(fetched.get('text','')),'assessment':ev,'as_of':cutoff,
                     'scope':'CURRENT_SOURCE_PROBE_NOT_HISTORICAL_OR_SHEET_UNIVERSE_COVERAGE'})
    print(json.dumps(rows,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
