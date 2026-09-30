#!/usr/bin/env python3
"""Real 393px browser check against seven synthetic offline report pages."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    from playwright.sync_api import sync_playwright
    results = []
    with tempfile.TemporaryDirectory(prefix='ai255-mobile-') as tmp:
        target = Path(tmp)
        subprocess.run([sys.executable, str(ROOT/'scripts/orchestrator/build_ai_dev_255_mobile_preview.py'), '--output', tmp], check=True, stdout=subprocess.PIPE)
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
                        collapsed:[...document.querySelectorAll('details[data-ai-dev-255-evidence]')].every(x=>!x.open),
                        badBounds:[...document.querySelectorAll('.mobile-decision-card,.mobile-decision-card dd')].filter(x=>x.getBoundingClientRect().right>393||x.getBoundingClientRect().left<0).length})''')
                    page.locator('details[data-ai-dev-255-evidence] > summary').click()
                    after = page.evaluate("() => ({width:document.documentElement.scrollWidth,open:document.querySelector('details[data-ai-dev-255-evidence]').open})")
                    results.append({'window':row['window'],'pass':before['width']<=393 and before['collapsed'] and before['badBounds']==0 and after['width']<=393 and after['open']})
                    page.close()
            finally:
                browser.close()
    ok = len(results)==7 and all(r['pass'] for r in results)
    print(json.dumps({'schema_version':'ai_dev_255_mobile_viewport_v1','status':'PASS' if ok else 'FAIL','width':393,'results':results,'input_kind':'SYNTHETIC','production_mutation':'NONE'}))
    return 0 if ok else 1


if __name__ == '__main__': raise SystemExit(main())
