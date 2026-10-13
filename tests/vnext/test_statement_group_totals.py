"""Revenue/expense section-closing totals; no source-independent total credit."""
import unittest
from tests.vnext.test_selected_reported_revenue_v2 import changed
from tests.vnext.test_single_revenue_line import single_statement, APPROVED
from vnext.selected_reported_revenue_v2 import reported_revenue_scope


def closed_statement():
    source, annual = single_statement()
    raw = source['raw_bytes'].replace(b'CostOfGoodsAndServicesSold', b'CostsAndExpenses')
    raw = raw.replace(b'<tr><td>Revenues</td>',
        b'<tr><td>REVENUES</td><td></td></tr>'
        b'<tr><td>Gross revenue</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="annual" unitRef="usd" scale="6" decimals="-6">60000</ix:nonFraction></td></tr>'
        b'<tr><td>Revenue deductions</td><td><ix:nonFraction name="us-gaap:CapitalizedContractCostAmortization" contextRef="annual" unitRef="usd" scale="6" decimals="-6">1504</ix:nonFraction></td></tr><tr><td></td>')
    raw = raw.replace(b'<tr><td>Cost of sales</td>',
        b'<tr><td>OPERATING COSTS AND EXPENSES</td><td></td></tr>'
        b'<tr><td>Cost of sales</td><td><ix:nonFraction name="us-gaap:CostOfRevenue" contextRef="annual" unitRef="usd" scale="6" decimals="-6">10000</ix:nonFraction></td></tr><tr><td></td>')
    operating=(b'<tr><td>OPERATING INCOME</td><td><ix:nonFraction name="us-gaap:OperatingIncomeLoss" '
        b'contextRef="annual" unitRef="usd" scale="6" decimals="-6">48496</ix:nonFraction></td></tr>')
    raw = raw.replace(b'<tr><td>Net income', operating+b'<tr><td>Net income')
    return changed(source,raw), annual


class StatementGroupTotalsTest(unittest.TestCase):
    def test_default_keeps_blank_total_unproved(self):
        source,annual=closed_statement()
        self.assertFalse(reported_revenue_scope(primary=source,xml=source,annual=annual,
            approved_concepts=APPROVED,allow_single_revenue_line=True)['complete_scope_proven'])

    def test_explicit_closed_sections_prove_reported_totals(self):
        source,annual=closed_statement()
        scope=reported_revenue_scope(primary=source,xml=source,annual=annual,
            approved_concepts=APPROVED,allow_statement_group_totals=True)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertEqual('58496000000',scope['reported_totals'][0]['total']['value'])

    def test_missing_or_limited_section_is_not_a_total(self):
        source,annual=closed_statement()
        for old,new in [(b'REVENUES</td>',b'Segment Alpha revenues</td>'),
                        (b'OPERATING COSTS AND EXPENSES',b'Expenses excluding subsidiaries'),
                        (b'>48496</ix:nonFraction>',b'>48495</ix:nonFraction>')]:
            with self.subTest(new=new):
                scope=reported_revenue_scope(primary=changed(source,source['raw_bytes'].replace(old,new)),
                    xml=source,annual=annual,approved_concepts=APPROVED,
                    allow_statement_group_totals=True)
                self.assertFalse(scope['complete_scope_proven'])

    def test_group_positions_and_unknown_scope_are_not_ignored(self):
        source,annual=closed_statement()
        injections=[(b'<tr><td>OPERATING COSTS AND EXPENSES',
                     b'<tr><td>Other revenue</td><td>100</td></tr><tr><td>OPERATING COSTS AND EXPENSES'),
                    (b'<tr><td>OPERATING INCOME',
                     b'<tr><td>Gains on dispositions</td><td>50</td></tr><tr><td>OPERATING INCOME')]
        for before,after in injections:
            with self.subTest(after=after):
                result=reported_revenue_scope(primary=changed(source,source['raw_bytes'].replace(before,after)),
                    xml=source,annual=annual,approved_concepts=APPROVED,
                    allow_statement_group_totals=True)
                self.assertFalse(result['complete_scope_proven'])

    def test_nonboolean_option_is_not_a_compatibility_mode(self):
        source,annual=closed_statement()
        for option in ('true',None,1):
            with self.subTest(option=option),self.assertRaisesRegex(ValueError,'STATEMENT_GROUP_OPTION_INVALID'):
                reported_revenue_scope(primary=source,xml=source,annual=annual,
                    approved_concepts=APPROVED,allow_statement_group_totals=option)

    def test_new_blank_total_proof_requires_original_xml(self):
        source,annual=closed_statement()
        self.assertFalse(reported_revenue_scope(primary=source,annual=annual,
            approved_concepts=APPROVED,allow_statement_group_totals=True)['complete_scope_proven'])

    def test_wrong_period_scale_and_xml_conflicts_remain_rejected(self):
        source,annual=closed_statement()
        raw=source['raw_bytes']
        for before,after in [(b'<td>2025</td>',b'<td>2024</td>'),
                             (b'name="us-gaap:CostsAndExpenses" contextRef="annual"',
                              b'name="us-gaap:CostsAndExpenses" contextRef="short"'),
                             (b'name="us-gaap:CostsAndExpenses" contextRef="annual" unitRef="usd" scale="6"',
                              b'name="us-gaap:CostsAndExpenses" contextRef="annual" unitRef="usd" scale="3"')]:
            with self.subTest(after=after):
                try:result=reported_revenue_scope(primary=changed(source,raw.replace(before,after)),
                    xml=source,annual=annual,approved_concepts=APPROVED,allow_statement_group_totals=True)
                except ValueError:continue
                self.assertFalse(result['complete_scope_proven'])

    def test_real_xml_amount_conflict_cannot_be_hidden_by_matching_arithmetic(self):
        source,annual=closed_statement()
        xml=changed(source,source['raw_bytes'].replace(b'>10000</ix:nonFraction>',b'>9999</ix:nonFraction>'))
        scope=reported_revenue_scope(primary=source,xml=xml,annual=annual,
            approved_concepts=APPROVED,allow_statement_group_totals=True)
        self.assertFalse(scope['complete_scope_proven'])

    def test_unassigned_subject_and_period_introductions_are_still_errors(self):
        source,annual=closed_statement()
        for intro in (b'<div>Only Subsidiary Beta is included.</div>',
                      b'<div>Fiscal years 2024, 2023, and 2022</div>'):
            changed_source=changed(source,source['raw_bytes'].replace(b'<table>',intro+b'<table>',1))
            with self.subTest(intro=intro),self.assertRaises(ValueError):
                reported_revenue_scope(primary=changed_source,xml=changed_source,annual=annual,
                    approved_concepts=APPROVED,allow_statement_group_totals=True)

    def test_group_dependencies_are_explicit_and_do_not_activate_the_contract(self):
        import inspect
        from pathlib import Path
        from vnext.selected_reported_revenue_v2 import STATEMENT_GROUP_PROCESSING_FILES
        root=Path(__file__).resolve().parents[2]
        self.assertFalse(inspect.signature(reported_revenue_scope).parameters['allow_statement_group_totals'].default)
        self.assertEqual(len(STATEMENT_GROUP_PROCESSING_FILES),len(set(STATEMENT_GROUP_PROCESSING_FILES)))
        self.assertTrue(all((root/p).is_file() for p in STATEMENT_GROUP_PROCESSING_FILES))

    def test_empty_or_duplicate_groups_do_not_prove_a_total(self):
        import re
        source,annual=closed_statement()
        for raw in (re.sub(rb'<tr><td>Gross revenue</td>.*?</tr>',b'',
                         re.sub(rb'<tr><td>Revenue deductions</td>.*?</tr>',b'',source['raw_bytes'])),
                    source['raw_bytes'].replace(b'<tr><td>REVENUES</td>',
                        b'<tr><td>REVENUES</td><td></td></tr><tr><td>REVENUES</td>')):
            with self.subTest(raw_length=len(raw)):
                scope=reported_revenue_scope(primary=changed(source,raw),xml=changed(source,raw),annual=annual,
                    approved_concepts=APPROVED,allow_statement_group_totals=True)
                self.assertFalse(scope['complete_scope_proven'])

    def test_dollar_unit_caption_before_table_is_not_a_scope_limitation(self):
        source,annual=closed_statement()
        raw=source['raw_bytes'].replace(b'<table>',
            b'<div>($ in millions, except per share amounts)</div><table>',1)
        revised=changed(source,raw)
        scope=reported_revenue_scope(primary=revised,xml=revised,annual=annual,
            approved_concepts=APPROVED,allow_statement_group_totals=True)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertEqual('58496000000',scope['reported_totals'][0]['total']['value'])

    def test_foreign_currency_or_extra_scope_text_is_not_the_dollar_caption(self):
        source,annual=closed_statement()
        for caption in ('(EUR in millions, except per share amounts)',
                        '($ in millions, only subsidiary operations)'):
            raw=source['raw_bytes'].replace(b'<table>',('<div>'+caption+'</div><table>').encode(),1)
            revised=changed(source,raw)
            with self.subTest(caption=caption),self.assertRaises(ValueError):
                reported_revenue_scope(primary=revised,xml=revised,annual=annual,
                    approved_concepts=APPROVED,allow_statement_group_totals=True)

    def test_dollar_caption_cannot_override_the_native_scale(self):
        source,annual=closed_statement()
        raw=source['raw_bytes'].replace(b'<table>',
            b'<div>($ in thousands, except per share amounts)</div><table>',1)
        revised=changed(source,raw)
        with self.assertRaisesRegex(ValueError,'VISIBLE_NATIVE_UNIT_UNRESOLVED'):
            reported_revenue_scope(primary=revised,xml=revised,annual=annual,
                approved_concepts=APPROVED,allow_statement_group_totals=True)

    def test_loss_qualified_earnings_per_share_heading_keeps_scope_proof(self):
        source,annual=closed_statement()
        raw=source['raw_bytes'].replace(b'</table>',
            b'<tr><td>EARNINGS (LOSS) PER SHARE</td></tr></table>',1)
        revised=changed(source,raw)
        scope=reported_revenue_scope(primary=revised,xml=revised,annual=annual,
            approved_concepts=APPROVED,allow_statement_group_totals=True)
        self.assertTrue(scope['complete_scope_proven'])

    def test_eps_heading_does_not_hide_subsidiary_scope_annotation(self):
        source,annual=closed_statement()
        raw=source['raw_bytes'].replace(b'</table>',
            b'<tr><td>EARNINGS (LOSS) PER SHARE; only subsidiary operations</td></tr></table>',1)
        revised=changed(source,raw)
        with self.assertRaises(ValueError):
            reported_revenue_scope(primary=revised,xml=revised,annual=annual,
                approved_concepts=APPROVED,allow_statement_group_totals=True)
