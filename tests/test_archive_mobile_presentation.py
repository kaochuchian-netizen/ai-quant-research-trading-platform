"""Actual immutable archive -> latest -> temporary publisher regression."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from app.reports.mobile_decision_presentation import LABELS, VERSION
from scripts.orchestrator.build_ai_dev_255d_archive_preview import build_preview, require_temporary


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__();self.hidden=[];self.text=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        self.hidden.append((tag,tag in {"style","script"} or (tag=="details" and "open" not in attrs)))
        if tag in {"meta","link","br","hr","img","input"}: self.hidden.pop()
    def handle_endtag(self,tag):
        for i in range(len(self.hidden)-1,-1,-1):
            if self.hidden[i][0]==tag:
                self.hidden=self.hidden[:i];break
    def handle_data(self,data):
        if not any(h for _,h in self.hidden):self.text.append(data)


class ArchivePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="ai255d-tests-")
        cls.root=Path(cls.tmp.name);cls.rows=build_preview(cls.root)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_seven_windows(self):
        self.assertEqual({r["window"] for r in self.rows},set(LABELS))
    def test_reject_production_target(self):
        for root in ("/var/www/stock-ai-dashboard","/home/kaochuchian/stock-ai"):
            with self.assertRaises(ValueError):require_temporary(root)
    def test_fixture_not_production_sample(self):
        self.assertTrue(all(r["input_kind"]=="SYNTHETIC" for r in self.rows))
    def test_post_close_explicit_results_and_values(self):
        row=next(r for r in self.rows if r["window"]=="post_close_1500")
        html=(self.root/row["html"]).read_text()
        p=VisibleText();p.feed(html);text=" ".join(p.text)
        for value in ("符合預測","未符合預測","偏多","偏空","98.00–103.00"):
            self.assertIn(value,text)
        self.assertNotIn("synthetic-origin",text)
        # Unknown/backtest fields remain immutable in persisted source JSON.
        snapshots=list((self.root/"archive"/"tw"/"post_close_1500").rglob("*.json"))
        self.assertTrue(any("synthetic-origin" in p.read_text() for p in snapshots))

    def test_review_summary_does_not_repeat_components(self):
        for row in self.rows:
            if row["window"] not in {"post_close_1500","us_post_close_review_0630"}:continue
            html=(self.root/row["html"]).read_text()
            p=VisibleText();p.feed(html);visible=" ".join(p.text)
            self.assertNotIn("方向：",visible)
            self.assertNotIn("；區間：",visible)
            self.assertIn("今日預測結果",visible)

    def test_rebuild_idempotent_html(self):
        before={r["window"]:(self.root/r["html"]).read_bytes() for r in self.rows}
        # Re-render without creating snapshots or modifying canonical payloads.
        from unittest.mock import patch
        from app.dashboard import multi_market_dashboard as d
        with patch.object(d,"WINDOW_SNAPSHOT_ARCHIVE",self.root/"archive"):
            for row in self.rows:
                path=d.build_archive_route(self.root/"replay",row["market"],row["window"],"latest")
                self.assertEqual(path.read_bytes(),before[row["window"]])


def check_window(window,kind):
    def test(self):
        row=next(r for r in self.rows if r["window"]==window)
        html=(self.root/row["html"]).read_text()
        if kind=="route":
            self.assertEqual(row["status"],"verified")
            self.assertIn('data-archive-presentation-version="'+VERSION+'"',html)
            self.assertIn('data-presentation-version="'+VERSION+'"',html)
        elif kind=="visible":
            p=VisibleText();p.feed(html);visible=" ".join(p.text)
            for label in LABELS[window]:self.assertIn(label,visible)
            for raw in ("insufficient_evidence","bullish","lineage","MFE","MAE","None","confidence","判定原因","決策歷程","行情解析度","證據學習","Active Window","Runtime Provenance"):
                self.assertNotIn(raw,visible)
        elif kind=="preservation":
            self.assertIn("data-ai-dev-255-evidence",html)
            self.assertIn("data-ai-dev-255d-archive-evidence",html)
            self.assertNotIn("<details open",html)
            self.assertIn("data-payload-hash=",html)
            self.assertIn("Runtime Provenance",html)
        elif kind=="previous":
            previous=(self.root/row["previous_html"]).read_text()
            self.assertIn('data-archive-presentation-version="'+VERSION+'"',previous)
            self.assertIn("2026-09-23",previous)
    return test

for window in LABELS:
    for kind in ("route","visible","preservation","previous"):
        setattr(ArchivePresentationTests,"test_"+window+"_"+kind,check_window(window,kind))
if __name__=="__main__":unittest.main()
