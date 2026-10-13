"""Standard section titles do not waive statement scope or untagged amounts."""
import unittest

from tests.vnext.test_single_revenue_line import single_statement, APPROVED
from tests.vnext.test_selected_reported_revenue_v2 import changed
from vnext.selected_reported_revenue_v2 import reported_revenue_scope


class IncomeSectionCaptionTest(unittest.TestCase):
    def statement(self, *, other='Other expense, net', eps='Net income (loss) per share:'):
        source, annual = single_statement()
        raw = source['raw_bytes'].replace(b'<td>Revenues</td>', b'<td>Net revenues</td>')
        if other:
            raw = raw.replace(b'<tr><td>Net income',
                ('<tr><td>'+other+'</td><td></td></tr><tr><td>Net income').encode())
        if eps:
            raw = raw.replace(b'</table>', ('<tr><td>'+eps+'</td><td></td></tr></table>').encode())
        return changed(source, raw), annual

    def scope(self, source, annual):
        return reported_revenue_scope(primary=source, xml=source, annual=annual,
            approved_concepts=APPROVED, allow_single_revenue_line=True)

    def test_standard_expense_and_loss_eps_headers_preserve_actual_net_revenue(self):
        source, annual = self.statement()
        result = self.scope(source, annual)
        self.assertTrue(result['complete_scope_proven'])
        self.assertEqual(result['reported_totals'][0]['total']['value'], '58496000000')
        self.assertEqual(result['reported_totals'][0]['statement_scope']['unresolved_annotations'], [])

    def test_original_accepted_income_and_plain_eps_forms_remain_valid(self):
        source, annual = self.statement(other='Other income (expense), net', eps='Net income per share:')
        self.assertTrue(self.scope(source, annual)['complete_scope_proven'])

    def test_source_format_fix_does_not_enable_the_explicit_single_line_contract(self):
        source, annual = self.statement()
        result = reported_revenue_scope(primary=source, xml=source, annual=annual,
                                         approved_concepts=APPROVED)
        self.assertFalse(result['complete_scope_proven'])

    def test_same_words_do_not_hide_scope_qualifiers_or_unknown_explanation(self):
        for other, eps in [('Other expense, net; only Subsidiary Alpha operations are included', ''),
                           ('', 'Net income (loss) per share: excludes other businesses'),
                           ('Other expense, net (Europe)', ''),
                           ('', 'Net income (loss) per share: management estimate')]:
            with self.subTest(other=other, eps=eps):
                source, annual = self.statement(other=other, eps=eps)
                with self.assertRaisesRegex(ValueError, 'STATEMENT_LOCAL_SCOPE_UNRESOLVED'):
                    self.scope(source, annual)

    def test_new_headers_do_not_excuse_untagged_numeric_cells(self):
        for text in ('Other expense, net', 'Net income (loss) per share:'):
            source, annual = self.statement()
            raw = source['raw_bytes'].replace((text+'</td><td></td>').encode(),
                                              (text+'</td><td>123</td>').encode())
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'STATEMENT_LOCAL_SCOPE_UNRESOLVED'):
                self.scope(changed(source, raw), annual)

    def test_table_section_titles_do_not_become_issuer_or_period_introductions(self):
        for text in ('Other expense, net', 'Net income (loss) per share:'):
            source, annual = self.statement(other='', eps='')
            raw = source['raw_bytes'].replace(b'<table>', ('<div>'+text+'</div><table>').encode(), 1)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'STATEMENT_(?:HEADING|INTRODUCTION)_SCOPE_UNRESOLVED'):
                self.scope(changed(source, raw), annual)
