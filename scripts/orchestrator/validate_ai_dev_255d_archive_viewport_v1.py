#!/usr/bin/env python3
"""Real 393px browser check against seven synthetic offline report pages."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.reports.mobile_decision_presentation import LABELS


def main():
    from playwright.sync_api import sync_playwright
    results = []
    with tempfile.TemporaryDirectory(prefix='ai255-mobile-') as tmp:
        target = Path(tmp)
        subprocess.run([sys.executable, str(ROOT/'scripts/orchestrator/build_ai_dev_255d_archive_preview.py'), '--output', tmp], check=True, stdout=subprocess.PIPE)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport={'width':393,'height':852}, device_scale_factor=1)
                context.route('http://**/*', lambda route: route.abort())
                context.route('https://**/*', lambda route: route.abort())
                for row in json.loads((target/'manifest.json').read_text()):
                    page = context.new_page()
                    page.goto((target/row['html']).as_uri())
                    before = page.evaluate('''() => ({width:document.documentElement.scrollWidth,
                        collapsed:[...document.querySelectorAll('details')].every(x=>!x.open),
                        rawVisible:/insufficient_evidence|bullish|\bNone\b|lineage|MFE|MAE|Runtime Provenance|判定原因|決策歷程|行情解析度|證據學習|信心/.test(document.body.innerText),
                        topDetails:[...document.querySelectorAll('details')].filter(x=>!x.parentElement.closest('details')).map(x=>x.querySelector('summary').textContent),
                        fields:[...document.querySelectorAll('.mobile-decision-card')].map(x=>[...x.querySelectorAll('dt')].map(t=>t.textContent)),
                        visibleLegacy:[...document.querySelectorAll('.window-stock-card,.tw-pre-open-structured-card,.decision-card')].filter(x=>!x.closest('details:not([open])') && x.checkVisibility()).length,
                        badBounds:[...document.querySelectorAll('.mobile-decision-card,.mobile-decision-card dd')].filter(x=>x.getBoundingClientRect().right>393||x.getBoundingClientRect().left<0).length})''')
                    page.locator('details[data-ai-dev-255-evidence] > summary').click()
                    after = page.evaluate("() => ({width:document.documentElement.scrollWidth,open:document.querySelector('details[data-ai-dev-255-evidence]').open})")
                    results.append({'window':row['window'],'pass':before['width']<=393 and before['collapsed'] and before['topDetails']==['詳細評估資料'] and before['visibleLegacy']==0 and bool(before['fields']) and all(fields==list(LABELS[row['window']]) for fields in before['fields']) and not before['rawVisible'] and before['badBounds']==0 and after['width']<=393 and after['open']})
                    page.close()
            finally:
                browser.close()
    ok = len(results)==7 and all(r['pass'] for r in results)
    print(json.dumps({'schema_version':'ai_dev_255d_archive_viewport_v1','status':'PASS' if ok else 'FAIL','width':393,'results':results,'input_kind':'SYNTHETIC','production_mutation':'NONE'}))
    return 0 if ok else 1


if __name__ == '__main__': raise SystemExit(main())
