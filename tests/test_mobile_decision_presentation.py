"""Offline seven-window presentation and source preservation regression."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from app.reports import mobile_decision_presentation as m
from app.dashboard import multi_market_dashboard as dashboard

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / 'tests/fixtures/ai_dev_255_mobile_decision_v1.json').read_text())['payloads']


class PresentationTests(unittest.TestCase):
    def test_all_seven_windows(self):
        self.assertEqual({p['window'] for p in FIXTURES}, set(m.LABELS))

    def test_intraday_does_not_relabel_inherited_forecast(self):
        for p in FIXTURES:
            if 'intraday' in p['window']:
                row = m.project_payload(p, p['market'], p['window'])['cards'][0]
                self.assertIn(m.INTRADAY_MISSING, [x['value'] for x in row['fields']])
                self.assertEqual(row['line_range'], m.INTRADAY_MISSING)

    def test_explicit_empty_no_cross_source_fallback(self):
        p = {'structured_pre_open_cards': [], 'cards': [{'symbol': 'wrong'}]}
        self.assertEqual(m.cards_for(p, 'pre_open_0700'), [])

    def test_wrong_window_not_reused(self):
        self.assertEqual(m.cards_for(FIXTURES[0], 'intraday_1305'), [])

    def test_us_canonical_dashboard_source_wins(self):
        p = copy.deepcopy(FIXTURES[4]); p[m.CARD_KEYS[p['window']]] = [{'symbol': 'WRONG'}]
        self.assertEqual(m.cards_for(p, p['window'])[0]['symbol'], 'DEMO')

    def test_unknown_window_rejected(self):
        with self.assertRaises(ValueError): m.cards_for({}, 'unknown')

    def test_missing_direction_not_flat(self):
        self.assertEqual(m.zh(None), m.MISSING)
        self.assertNotEqual(m.zh('NO_FORECAST'), '盤整')

    def test_unknown_enum_not_leaked(self):
        self.assertEqual(m.zh('INTERNAL_NEW_ENUM'), m.MISSING)

    def test_prices_fail_closed(self):
        for value in [None, True, float('nan'), float('inf'), 'provider error']:
            self.assertEqual(m.price(value), m.MISSING)
        self.assertEqual(m.interval(2, 1), m.MISSING)

    def test_zero_price_preserved(self):
        self.assertEqual(m.price(0), '0.00')

    def test_english_news_has_chinese_summary_and_source(self):
        p = FIXTURES[4]; row = m.project_payload(p, 'US', p['window'])['cards'][0]
        news = row['news'][0]
        self.assertTrue(news['translation_available'])
        self.assertIn('新設製造廠', news['summary'])
        self.assertEqual(news['source'], '合成新聞來源')

    def test_no_fabricated_translation(self):
        raw = {'finalized_current_news_projection_v3': {'selected_items': [{'headline': 'English only', 'publisher': 'Source'}]}}
        item = m.news_summary(raw, {})[0]
        self.assertFalse(item['translation_available'])
        self.assertIn('尚未提供繁體中文內容摘要', item['summary'])

    def test_generic_impact_is_not_article_summary(self):
        raw = {'finalized_current_news_projection_v3': {'selected_items': [{'impact_summary': '提供研究脈絡', 'headline': 'English'}]}}
        self.assertFalse(m.news_summary(raw, {})[0]['translation_available'])

    def test_no_trade_does_not_create_execution_plan(self):
        p = FIXTURES[4]; row = m.project_payload(p, 'US', p['window'])['cards'][0]
        values = {x['label']: x['value'] for x in row['fields']}
        self.assertEqual(values['進場區間'], '未建立正式進場區間')
        self.assertEqual(values['停損'], '未建立正式停損')

    def test_actual_not_inferred_from_prediction(self):
        card = copy.deepcopy(m.cards_for(FIXTURES[3], 'post_close_1500')[0])
        card.pop('actual_direction');card['review'].pop('actual_direction')
        row = m.project_card(card, 'TW', 'post_close_1500')
        self.assertEqual(next(x['value'] for x in row['fields'] if x['label']=='今天實際走勢'), m.MISSING)

    def test_html_escaped(self):
        p = copy.deepcopy(FIXTURES[0]);p['structured_pre_open_cards'][0]['name'] = '<script>alert(1)</script>'
        html = m.render_primary(p, 'TW', p['window'])
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_no_legacy_report_deleted(self):
        html = m.render_report(FIXTURES[0], 'TW', 'pre_open_0700', '<p>原始技術／研究資料</p>')
        self.assertIn('<p>原始技術／研究資料</p>', html)
        self.assertIn('<details data-ai-dev-255-evidence>', html)
        self.assertNotIn('<details open', html)

    def test_delivery_functions_are_formatter_only(self):
        from scripts.orchestrator.approved_pre_open_delivery import build_line_message
        from scripts.orchestrator.approved_us_stock_delivery import line_text
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            for p in FIXTURES:
                if p['market'] == 'TW':
                    out = build_line_message(p['window'], 'fixture', 'completed', 'https://example.test', '', {'payload': p})
                else: out = line_text(p, p['window'])
                self.assertIn('決策摘要', out)
                self.assertIn('9999' if p['market']=='TW' else 'DEMO', out)


def window_test(window, kind):
    def test(self):
        p = next(x for x in FIXTURES if x['window']==window)
        before = copy.deepcopy(p)
        projection = m.project_payload(p, p['market'], window)
        row = projection['cards'][0]
        if kind == 'fields': self.assertEqual([x['label'] for x in row['fields']], list(m.LABELS[window]))
        elif kind == 'preservation':
            self.assertEqual(p, before)
            self.assertEqual(row['evidence'], m.cards_for(before, window)[0])
            self.assertEqual(projection['source_digest'], m.digest(before))
        elif kind == 'determinism': self.assertEqual(projection, m.project_payload(p, p['market'], window))
        elif kind == 'line_parity':
            text = m.render_line(p, p['market'], window, 'https://example.test')
            for field in row['fields']:
                if field['label'] in text: self.assertIn(field['value'], text)
            self.assertNotIn('新聞內容摘要：', text)
            self.assertNotIn('信心', text)
        elif kind == 'runtime_renderer':
            html = dashboard.render_tw_window_report(window,p) if p['market']=='TW' else dashboard.render_us_window_report(window,[p])
            self.assertIn('data-presentation-version="'+m.VERSION+'"',html)
            self.assertIn('data-ai-dev-255-evidence',html)
            for label in m.LABELS[window]:self.assertIn(label,html)
            self.assertEqual(p,before)
    return test

for window in m.LABELS:
    for kind in ['fields','preservation','determinism','line_parity','runtime_renderer']:
        setattr(PresentationTests, 'test_'+window+'_'+kind, window_test(window,kind))

if __name__ == '__main__': unittest.main()
