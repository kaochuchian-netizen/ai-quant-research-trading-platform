"""Explicit synthetic substantive article fixtures; never formal-source evidence."""
from app.research.article_evidence import assess

def with_article(row,name='Tesla',as_of=None):
    row=dict(row)
    if isinstance(row.get("content"),dict):
        row["content"]=with_article(row["content"],name,as_of)
        return row
    published=row.get('pubDate') or row.get('published_at')
    identity={'symbol':(row.get('relatedTickers') or ['TSLA'])[0], 'name':name,'aliases':[]}
    body=(f'{name} reported revenue of 25 billion dollars for the third quarter of 2026. '
          f'{name} announced operating margin of 12 percent for the third quarter of 2026.')
    row['article_evidence']=assess(body,title=row['title'],entry=identity,
        source_url=row.get('link') or (row.get('canonicalUrl') or {}).get('url'),published_at=published,fetched_at=published,
        as_of=as_of or published)
    return row
