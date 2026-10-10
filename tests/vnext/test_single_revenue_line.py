"""Explicit single top-line source checks; synthetic inputs are not business credit."""
import re
import unittest

from tests.vnext.test_selected_revenue_scope_v1 import originals,APPROVED
from tests.vnext.test_selected_reported_revenue_v2 import changed
from vnext.selected_reported_revenue_v2 import reported_revenue_scope


def single_statement(*, full=True):
    source,_,annual=originals(full=full)
    raw=source['raw_bytes']
    for label in ('Product revenues','Alliance revenues'):
        raw=re.sub(rb'<tr><td>'+label.encode()+rb'</td>.*?</tr>',b'',raw)
    raw=raw.replace(b'Total revenues',b'Revenues')
    source=changed(source,raw)
    return source,annual


class SingleRevenueLineTest(unittest.TestCase):
    def scope(self,source,annual,**kwargs):
        return reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED,
                                      allow_single_revenue_line=True,**kwargs)

    def test_explicit_single_line_keeps_original_fact_and_default_contract(self):
        source,annual=single_statement()
        old=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED)
        self.assertFalse(old['complete_scope_proven'])
        result=self.scope(source,annual)
        self.assertTrue(result['complete_scope_proven'])
        self.assertEqual(result['reported_totals'][0]['total']['value'],'58496000000')
        self.assertEqual(result['method'],'SELECTED_REPORTED_SINGLE_REVENUE_LINE_V1')
        self.assertNotIn('single_revenue_line_allowed',old)

    def test_remaining_tagged_and_untagged_revenue_parts_are_not_sole_line(self):
        source,annual=single_statement()
        additions=[
            '<tr><td>Other revenue</td><td><ix:nonFraction name="issuer:OtherRevenue" contextRef="annual" unitRef="usd" scale="6" decimals="-6">100</ix:nonFraction></td></tr>',
            '<tr><td>Other revenue</td><td>100</td></tr>',
        ]
        for extra in additions:
            for position in ('before','after'):
                anchor=b'<tr><td>Revenues' if position=='before' else b'<tr><td>Cost of sales'
                raw=source['raw_bytes'].replace(anchor,extra.encode()+anchor)
                with self.subTest(extra=extra,position=position),self.assertRaisesRegex(ValueError,'SINGLE_REVENUE_'):
                    self.scope(changed(source,raw),annual)

    def test_component_rows_cannot_be_relabelled_as_single_revenue(self):
        source,_,annual=originals()
        source=changed(source,source['raw_bytes'].replace(b'Total revenues',b'Revenues'))
        with self.assertRaisesRegex(ValueError,'SINGLE_REVENUE_OTHER_AMOUNT'):
            self.scope(source,annual)

    def test_no_statement_title_no_cost_or_no_income_does_not_prove_total(self):
        source,annual=single_statement()
        for raw in (source['raw_bytes'].replace(b'Consolidated Statements of Income',b'Revenue note'),
                    re.sub(rb'<tr><td>Cost of sales</td>.*?</tr>',b'',source['raw_bytes']),
                    re.sub(rb'<tr><td>Net income</td>.*?</tr>',b'',source['raw_bytes'])):
            altered=changed(source,raw)
            if b'Revenue note' in raw:
                with self.assertRaisesRegex(ValueError,'TITLE_UNPROVEN'):self.scope(altered,annual)
            else:self.assertFalse(self.scope(altered,annual)['complete_scope_proven'])

    def test_existing_entity_period_unit_scope_and_xml_checks_still_apply(self):
        source,annual=single_statement()
        for old,new,reason in ((annual['entity'].encode(),b'54321','SUBJECT|IDENTITY|ENTITY|identity'),
                               (b'December 31,',b'December 30,','END_DAY'),
                               (b'MILLIONS, EXCEPT PER SHARE DATA',b'THOUSANDS, EXCEPT PER SHARE DATA','UNIT_UNRESOLVED'),
                               (b'<td>Net income</td>',b'<td>Net income; revenues exclude Subsidiary Beta operations</td>','LOCAL_SCOPE')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):
                self.scope(changed(source,source['raw_bytes'].replace(old,new)),annual)
        xml=changed(source,source['raw_bytes'].replace(b'>58496<',b'>60000<'))
        with self.assertRaisesRegex(ValueError,'XML_TOTAL_DIFFERS'):self.scope(source,annual,xml=xml)

    def test_only_explicit_boolean_option_and_exact_plain_label(self):
        source,annual=single_statement()
        for option in (1,'true',None):
            with self.assertRaisesRegex(ValueError,'OPTION_INVALID'):
                reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED,
                                       allow_single_revenue_line=option)
        source=changed(source,source['raw_bytes'].replace(b'<td>Revenues</td>',b'<td>Product revenues</td>'))
        self.assertFalse(self.scope(source,annual)['complete_scope_proven'])


if __name__=='__main__':unittest.main()
