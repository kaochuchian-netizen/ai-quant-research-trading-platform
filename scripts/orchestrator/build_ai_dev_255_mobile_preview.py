#!/usr/bin/env python3
"""Render only checked-in synthetic 255 fixtures to an explicit temporary target."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.dashboard.multi_market_dashboard import render_tw_window_report, render_us_window_report, TW_TACTICAL_CSS
from app.reports.mobile_decision_presentation import render_line, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents or Path(tempfile.gettempdir()).resolve() not in output.parents:
        parser.error('Use a temporary target outside the repository; never a production publish root.')
    output.mkdir(parents=True, exist_ok=True)
    fixtures = json.loads((ROOT / 'tests/fixtures/ai_dev_255_mobile_decision_v1.json').read_text())
    assert fixtures['input_kind'] == 'SYNTHETIC'
    manifest = []
    for payload in fixtures['payloads']:
        market, window = payload['market'], payload['window']
        before = digest(payload)
        fragment = render_tw_window_report(window,payload) if market=='TW' else render_us_window_report(window,[payload])
        assert before == digest(payload)
        html = '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>七窗口決策呈現預覽</title><style>body{margin:0;background:#f3f7f8;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans CJK TC",sans-serif}main{max-width:1000px;margin:auto;padding:16px}a{color:#19586b}h1{font-size:22px}'+TW_TACTICAL_CSS+'</style></head><body><main><h1>合成資料預覽</h1><p>不代表正式預測或交易建議。</p>'+fragment+'</main></body></html>'
        (output / (window+'.html')).write_text(html)
        (output / (window+'.line.txt')).write_text(render_line(payload,market,window,'https://example.test/'+window))
        manifest.append({'window':window,'market':market,'input_kind':'SYNTHETIC','source_digest':before,'html':window+'.html'})
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','windows':len(manifest),'output':str(output),'production_mutation':'NONE'}))


if __name__ == '__main__': main()
