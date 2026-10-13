"""Finite source/period controls; constructed statements are not company results."""
from copy import deepcopy
import json
import re
import unittest

from tests.vnext.test_selected_revenue_scope_v1 import originals,APPROVED,facts
from vnext.canonical import sha256_bytes
from vnext.selected_reported_revenue_v2 import reported_revenue_scope,admit_reported_revenue_facts,verify_reported_revenue_observations
from vnext.historical_dei import annual_period


def changed(source,raw):
    return {**source,'raw_bytes':raw,'source_reference':{**source['source_reference'],
            'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}


class SelectedReportedRevenueTest(unittest.TestCase):
    def named_expense_statement(self, release):
        source,annual=self.complete_expense_statement()
        name=b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">Parent Issuer</ix:nonNumeric>'
        raw=source['raw_bytes'].replace(b'http://xbrl.sec.gov/dei/2025',release.encode())
        raw=raw.replace(b'<div>Consolidated Statements of Income',
            name+b'<div>Consolidated Statements of Income',1)
        raw=raw.replace(b'<tr><td>Net income',
            b'<tr><td>Amounts attributable to Parent Issuer:</td><td></td></tr><tr><td>Net income')
        return changed(source,raw),annual

    def test_registrant_header_uses_the_declared_sec_release(self):
        from vnext.selected_reported_revenue_v2 import _defined_income_headers
        from vnext.deterministic_router import parse_accession_xbrl_source
        from vnext.xbrl_namespace_policy import YEAR_ONLY,YEAR_QUARTER_OR_DATE
        for release in ('http://xbrl.sec.gov/dei/2025q4','http://xbrl.sec.gov/dei/2025-01-31'):
            with self.subTest(release=release):
                source,annual=self.named_expense_statement(release)
                parsed=parse_accession_xbrl_source(raw_bytes=source['raw_bytes'])
                strict=_defined_income_headers(source,parsed,annual,dei_release=YEAR_ONLY)
                broad=_defined_income_headers(source,parsed,annual,dei_release=YEAR_QUARTER_OR_DATE)
                heading='amounts attributable to parent issuer:'
                self.assertFalse(any(re.fullmatch(pattern,heading) for pattern in strict['patterns']))
                self.assertTrue(any(re.fullmatch(pattern,heading) for pattern in broad['patterns']))
                self.assertEqual(broad['dei_release'],YEAR_QUARTER_OR_DATE)

    def test_complete_expense_statement_cannot_silently_widen_header_policy(self):
        from vnext.xbrl_namespace_policy import YEAR_QUARTER_OR_DATE
        source,annual=self.named_expense_statement('http://xbrl.sec.gov/dei/2025q4')
        with self.assertRaisesRegex(ValueError,'STATEMENT_LOCAL_SCOPE_UNRESOLVED'):
            reported_revenue_scope(primary=source,xml=source,annual=annual,approved_concepts=APPROVED,
                annual_period_reader=annual_period,allow_single_revenue_line=True)
        result=reported_revenue_scope(primary=source,xml=source,annual=annual,approved_concepts=APPROVED,
            annual_period_reader=annual_period,allow_single_revenue_line=True,dei_release=YEAR_QUARTER_OR_DATE)
        self.assertTrue(result['complete_scope_proven'])
        self.assertEqual(result['reported_totals'][0]['total']['value'],'58496000000')
        self.assertEqual(result['dei_release'],YEAR_QUARTER_OR_DATE)

    def test_explicit_release_never_accepts_an_extension_or_unknown_suffix(self):
        from vnext.selected_reported_revenue_v2 import _defined_income_headers
        from vnext.deterministic_router import parse_accession_xbrl_source
        from vnext.xbrl_namespace_policy import YEAR_QUARTER_OR_DATE
        for release in ('https://example.test/dei/2025q4','http://xbrl.sec.gov/dei/2025q5'):
            with self.subTest(release=release):
                source,annual=self.named_expense_statement(release)
                parsed=parse_accession_xbrl_source(raw_bytes=source['raw_bytes'])
                header=_defined_income_headers(source,parsed,annual,dei_release=YEAR_QUARTER_OR_DATE)
                self.assertFalse(any(re.fullmatch(pattern,'amounts attributable to parent issuer:')
                    for pattern in header['patterns']))

    def complete_expense_statement(self):
        from tests.vnext.test_single_revenue_line import single_statement
        source,annual=single_statement()
        raw=source['raw_bytes'].replace(b'Cost of sales',b'Total costs and expenses').replace(
            b'CostOfGoodsAndServicesSold',b'CostsAndExpenses')
        cost=b'<tr><td>Total costs and expenses'
        raw=raw.replace(cost,b'<tr><td>Costs and expenses:</td><td></td></tr>'+cost)
        operating=(b'<tr><td>Operating income (loss)</td><td><ix:nonFraction name="us-gaap:OperatingIncomeLoss" '
                   b'contextRef="annual" unitRef="usd" scale="6" decimals="-6">48496</ix:nonFraction></td></tr>')
        raw=raw.replace(b'<tr><td>Net income',operating+b'<tr><td>Net income')
        return changed(source,raw),annual

    def test_complete_cost_statement_is_explicit_and_preserves_source_relations(self):
        source,annual=self.complete_expense_statement()
        self.assertFalse(reported_revenue_scope(primary=source,xml=source,annual=annual,
            approved_concepts=APPROVED)['complete_scope_proven'])
        result=reported_revenue_scope(primary=source,xml=source,annual=annual,
            approved_concepts=APPROVED,allow_single_revenue_line=True)
        self.assertTrue(result['complete_scope_proven'])
        proof=result['reported_totals'][0]['complete_expense_statement']
        self.assertEqual('us-gaap:CostsAndExpenses',proof['expense']['concept'])
        self.assertEqual('10000000000',proof['expense']['value'])
        self.assertEqual('48496000000',proof['operating_income']['value'])
        self.assertEqual('MATCH',proof['xml_check'])
        self.assertEqual(annual['table_input']['target_period'],proof['annual_period'])

    def test_complete_expense_statement_uses_the_resolved_issuer_column_year(self):
        from vnext.fiscal_year_labels import inspect_fiscal_year_labels
        source,annual=self.complete_expense_statement()
        raw=source['raw_bytes'].replace(b'<td>2025</td>',b'<td>2026</td>')
        raw=raw.replace(b'Year Ended December 31,',b'')
        definition=b'<p>Our fiscal year ends on December 31. References to fiscal 2026, for example, refer to the fiscal year ending December 31, 2025.</p>'
        raw=b'<html><body>'+raw.replace(b'</xbrli:xbrl>',definition+b'</xbrli:xbrl>')+b'</body></html>'
        source=changed(source,raw)
        cf=json.dumps({'cik':int(annual['entity']),'facts':{'us-gaap':{'Revenues':{'units':{'USD':[
            {'accn':annual['filing']['accessionNumber'],'fy':2025,'fp':'FY','form':'10-K','val':58496000000,
             'start':'2025-01-01','end':'2025-12-31','filed':'2026-02-01'}]}}}}}).encode()
        inspected=inspect_fiscal_year_labels(primary_bytes=raw,companyfacts_bytes=cf,
            expected_primary_sha256=sha256_bytes(content=raw),expected_companyfacts_sha256=sha256_bytes(content=cf),
            expected_cik=annual['entity'],filing=annual['filing'])
        label={'record_type':'ORDINARY_FISCAL_YEAR_LABEL_RESOLUTION','source_inspection':inspected,
            'selected_fiscal_year':2026,'original_dei_fiscal_year':2025}
        scope=reported_revenue_scope(primary=source,xml=source,annual=annual,
            approved_concepts=APPROVED,fiscal_label_resolution=label,allow_single_revenue_line=True)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertEqual(2026,scope['selected_fiscal_column_year'])
        self.assertEqual(2025,scope['annual_input']['table_input']['target_period']['fiscal_year'])
        self.assertEqual('2025-12-31',scope['reported_totals'][0]['complete_expense_statement']['annual_period']['period_end'])
        wrong=changed(source,raw.replace(b'<td>2026</td>',b'<td>2027</td>'))
        with self.assertRaisesRegex(ValueError,'(?:FISCAL_LABEL_SOURCE_CHANGED|COLUMN_PERIOD_UNPROVEN)'):
            reported_revenue_scope(primary=wrong,xml=wrong,annual=annual,
                approved_concepts=APPROVED,fiscal_label_resolution=label,allow_single_revenue_line=True)

    def test_complete_cost_statement_does_not_hide_other_income_or_false_total(self):
        source,annual=self.complete_expense_statement()
        changes=[(b'Total costs and expenses',b'Costs and expenses excluding subsidiaries'),
                 (b'>48496</ix:nonFraction>',b'>48495</ix:nonFraction>'),
                 (b'Costs and expenses:</td>',b'Costs and expenses; only Segment Alpha:</td>')]
        for before,after in changes:
            with self.subTest(after=after):
                result=reported_revenue_scope(primary=changed(source,source['raw_bytes'].replace(before,after)),
                    xml=source,annual=annual,approved_concepts=APPROVED,allow_single_revenue_line=True)
                self.assertFalse(result['complete_scope_proven'])
                self.assertTrue(result['complete_expense_rejections'])
        extra=b'<tr><td>Other revenues</td><td>100</td></tr>'
        with self.assertRaisesRegex(ValueError,'SINGLE_REVENUE_'):
            reported_revenue_scope(primary=changed(source,source['raw_bytes'].replace(
                b'<tr><td>Costs and expenses:',extra+b'<tr><td>Costs and expenses:')),
                xml=source,annual=annual,approved_concepts=APPROVED,allow_single_revenue_line=True)

    def test_complete_expense_amount_scope_unit_column_and_xml_are_required(self):
        source,annual=self.complete_expense_statement()
        cost=(b'name="us-gaap:CostsAndExpenses" contextRef="annual" unitRef="usd" scale="6"')
        changes=[(cost,cost.replace(b'contextRef="annual"',b'contextRef="short"')),
                 (cost,cost.replace(b'scale="6"',b'scale="3"')),
                 (b'>10000</ix:nonFraction>',b'>10000</ix:nonFraction><span>7</span>'),
                 (b'<td>Total costs and expenses</td><td>',b'<td>Total costs and expenses</td><td></td><td>')]
        for before,after in changes:
            raw=source['raw_bytes'].replace(before,after)
            with self.subTest(after=after):
                try:result=reported_revenue_scope(primary=changed(source,raw),xml=source,annual=annual,
                    approved_concepts=APPROVED,allow_single_revenue_line=True)
                except ValueError:continue
                self.assertFalse(result['complete_scope_proven'])
        xml=changed(source,source['raw_bytes'].replace(b'>10000</ix:nonFraction>',b'>9999</ix:nonFraction>'))
        result=reported_revenue_scope(primary=source,xml=xml,annual=annual,
                approved_concepts=APPROVED,allow_single_revenue_line=True)
        self.assertFalse(result['complete_scope_proven'])
        self.assertIn('PRIMARY_XML_DIFFERS',result['complete_expense_rejections'][0]['reason'])

    def test_unproven_complete_expense_route_leaves_existing_fallback_available(self):
        source,annual=self.complete_expense_statement()
        extra=(b'<tr><td>Gains on dispositions</td><td><ix:nonFraction name="issuer:Gain" '
            b'contextRef="annual" unitRef="usd" scale="6" decimals="-6">56</ix:nonFraction></td></tr>')
        raw=source['raw_bytes'].replace(b'<tr><td>Operating income',extra+b'<tr><td>Operating income')
        primary=changed(source,raw)
        scope=reported_revenue_scope(primary=primary,xml=primary,annual=annual,
            approved_concepts=APPROVED,allow_single_revenue_line=True)
        self.assertFalse(scope['complete_scope_proven'])
        self.assertEqual('NO_REPORTED_TOTAL_PROVEN',scope['status'])
        self.assertIn('INTERVENING_AMOUNT_UNPROVEN',scope['complete_expense_rejections'][0]['reason'])
        from vnext.selected_revenue_scope_v1 import selected_revenue_scope
        fallback=selected_revenue_scope(primary=primary,xml=primary,annual=annual,approved_concepts=APPROVED)
        self.assertEqual('NO_DEMONSTRATED_SPLIT',fallback['status'])
        # Its complete-scope rules remain owned by V1/the actual caller; a
        # rejected new proof grants no substitute total or upgraded credit.
        self.assertFalse(fallback['complete_scope_proven'])

    def test_source_identity_failure_is_not_a_rejected_expense_proof(self):
        from unittest.mock import patch
        from vnext.selected_income_source_v1 import IncomeSourceError
        source,annual=self.complete_expense_statement()
        with patch('vnext.selected_reported_revenue_v2._complete_expense_statement',
                   side_effect=IncomeSourceError('SELECTED_INCOME_PRIMARY_IDENTITY_CHANGED')), \
             self.assertRaisesRegex(IncomeSourceError,'PRIMARY_IDENTITY_CHANGED'):
            reported_revenue_scope(primary=source,xml=source,annual=annual,
                approved_concepts=APPROVED,allow_single_revenue_line=True)

    def test_nonzero_or_untagged_intervening_gain_cannot_be_ignored(self):
        source,annual=self.complete_expense_statement()
        insertions=[b'<tr><td>Gains on dispositions</td><td>7</td></tr>',
            b'<tr><td>Gains on dispositions</td><td><ix:nonFraction name="issuer:Gain" '
            b'contextRef="annual" unitRef="usd" scale="6" decimals="-6">7</ix:nonFraction></td></tr>']
        for inserted in insertions:
            with self.subTest(inserted=inserted):
                result=reported_revenue_scope(primary=changed(source,source['raw_bytes'].replace(
                    b'<tr><td>Operating income',inserted+b'<tr><td>Operating income')),
                    xml=source,annual=annual,approved_concepts=APPROVED,allow_single_revenue_line=True)
                self.assertFalse(result['complete_scope_proven'])
                self.assertIn('AMOUNT',result['complete_expense_rejections'][0]['reason'])

    def test_exact_zero_intermediate_retains_its_own_native_context(self):
        source,annual=self.complete_expense_statement()
        zero=(b'<tr><td>Gains on dispositions</td><td><ix:nonFraction name="issuer:Gain" '
              b'contextRef="annual" unitRef="usd" scale="6" decimals="-6">0</ix:nonFraction></td></tr>')
        raw=source['raw_bytes'].replace(b'<tr><td>Operating income',zero+b'<tr><td>Operating income')
        result=reported_revenue_scope(primary=changed(source,raw),xml=source,annual=annual,
            approved_concepts=APPROVED,allow_single_revenue_line=True)
        self.assertTrue(result['complete_scope_proven'])
        neutral=result['reported_totals'][0]['complete_expense_statement']['neutral_intermediate_reports']
        self.assertEqual(1,len(neutral));self.assertEqual('0',neutral[0]['value'])
        for changed_zero in (zero.replace(b'contextRef="annual"',b'contextRef="short"'),
                             zero.replace(b'>0</ix:',b'>0</ix:').replace(b'</td></tr>',b'<span>9</span></td></tr>')):
            with self.subTest(changed_zero=changed_zero):
                result=reported_revenue_scope(primary=changed(source,source['raw_bytes'].replace(
                    b'<tr><td>Operating income',changed_zero+b'<tr><td>Operating income')),
                    xml=source,annual=annual,approved_concepts=APPROVED,allow_single_revenue_line=True)
                self.assertFalse(result['complete_scope_proven'])
                self.assertIn('AMOUNT',result['complete_expense_rejections'][0]['reason'])

    def test_complete_expense_headers_require_an_unquoted_same_issuer_definition(self):
        source,annual=self.complete_expense_statement()
        raw=source['raw_bytes'].replace(b'<dei:DocumentType',
            b'<dei:EntityRegistrantName contextRef="annual">Example Global</dei:EntityRegistrantName><dei:DocumentType',1)
        raw=raw.replace(b'<xbrli:xbrl ',b'<html ').replace(b'</xbrli:xbrl>',b'</html>')
        raw=raw.replace(b'<div>Consolidated',b'<body><div>Consolidated').replace(b'</html>',b'</body></html>')
        definition=('Unless the context requires otherwise, references in this document to “Example,” '
            '“the Company,” “we,” “us” and “our” mean Example Global and its consolidated subsidiaries.').encode()
        headers=b'<tr><td>Amounts attributable to Example:</td><td></td></tr>'
        headers+=b'<tr><td>Basic net earnings (loss) per common share attributable to Example:</td><td></td></tr>'
        raw=raw.replace(b'<div>Consolidated',b'<p>'+definition+b'</p><hr style="page-break-after:always"/><div>Consolidated')
        raw=raw.replace(b'</table>',headers+b'</table>')
        result=reported_revenue_scope(primary=changed(source,raw),xml=source,annual=annual,
            approved_concepts=APPROVED,allow_single_revenue_line=True)
        self.assertTrue(result['complete_scope_proven'])
        proof=result['reported_totals'][0]['issuer_header_definition'][0]
        self.assertEqual(['Example'],proof['aliases'])
        self.assertEqual(proof['raw_span_sha256'],sha256_bytes(content=raw[proof['raw_start_byte']:proof['raw_end_byte']]))
        for bad in (raw.replace(b'<p>'+definition+b'</p>',b'<blockquote>'+definition+b'</blockquote>'),
                    raw.replace(definition,definition.replace(b'Example Global and',b'Other Global and')),
                    raw.replace(headers,headers.replace(b'Example:',b'Other:')),
                    raw.replace(definition,b'We use the name Example.')):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'STATEMENT_LOCAL_SCOPE_UNRESOLVED'):
                reported_revenue_scope(primary=changed(source,bad),xml=source,annual=annual,
                    approved_concepts=APPROVED,allow_single_revenue_line=True)

    def test_standard_income_loss_title_keeps_native_loss_labels_and_scope_qualifiers(self):
        from vnext.selected_revenue_scope_v1 import selected_revenue_scope
        primary,xml,annual=originals()
        title=b'Consolidated Statement of Income (Loss)'
        raw=primary['raw_bytes'].replace(b'Consolidated Statements of Income',title).replace(b'Net income',b'Net income (loss)')
        for reader in (reported_revenue_scope,selected_revenue_scope):
            with self.subTest(reader=reader.__name__):
                scope=reader(primary=changed(primary,raw),xml=xml,annual=annual,approved_concepts=APPROVED)
                self.assertTrue(scope['complete_scope_proven'])
                for qualifier in (b' (US)',b' (Europe)',b' (Subsidiary)'):
                    with self.subTest(qualifier=qualifier),self.assertRaisesRegex(ValueError,'STATEMENT_TITLE_UNPROVEN'):
                        reader(primary=changed(primary,raw.replace(title,title+qualifier)),xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_income_statement_page_does_not_consume_the_prior_audit_report(self):
        primary,xml,annual=originals()
        preceding=b'<div>Report of Independent Registered Public Accounting Firm</div><div>Our audit provides reasonable assurance.</div>'
        boundary=b'<hr style="page-break-after:always"/>'
        raw=primary['raw_bytes'].replace(b'<div>Consolidated',preceding+boundary+b'<div>Consolidated')
        scope=reported_revenue_scope(primary=changed(primary,raw),xml=xml,annual=annual,approved_concepts=APPROVED)
        self.assertTrue(scope['complete_scope_proven'])
        statement=scope['reported_totals'][0]['statement_scope']
        self.assertEqual(2,len(statement['preceding_page_context']))
        proof=statement['statement_page_boundary']
        self.assertEqual(proof['span_sha256'],sha256_bytes(content=raw[proof['start_byte']:proof['end_byte']]))
        for bad in (raw.replace(boundary,b''),raw.replace(b'Our audit provides reasonable assurance.',b'Revenues exclude subsidiaries.')):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'STATEMENT_.*SCOPE_UNRESOLVED'):
                reported_revenue_scope(primary=changed(primary,bad),xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_unit_before_nested_table_retains_exact_source_and_rejects_conflicts(self):
        primary,xml,annual=originals()
        raw=primary['raw_bytes'].replace(b'(MILLIONS, EXCEPT PER SHARE DATA)',b'')
        raw=raw.replace(b'<table>',b'<div><span>(in millions, except per share amounts)</span><table>',1)
        raw=raw.replace(b'</table>',b'</table></div>',1)
        scope=reported_revenue_scope(primary=changed(primary,raw),xml=xml,annual=annual,approved_concepts=APPROVED)
        self.assertTrue(scope['complete_scope_proven'])
        proof=scope['reported_totals'][0]['unit_sources'][0]['proof']
        self.assertEqual(proof['span_sha256'],sha256_bytes(content=raw[proof['start_byte']:proof['end_byte']]))
        self.assertLessEqual(proof['end_byte'],scope['reported_totals'][0]['statement_scope']['table_span']['start_byte'])
        for bad in (raw.replace(b'in millions',b'in thousands'),
                    raw.replace(b'</span><table>',b'</span>Revenue excludes subsidiaries<table>'),
                    raw.replace(b'</span><table>',b'</span><p>Segment Alpha only</p><table>')):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'(?:UNIT_UNRESOLVED|STATEMENT_.*SCOPE_UNRESOLVED)'):
                reported_revenue_scope(primary=changed(primary,bad),xml=xml,annual=annual,approved_concepts=APPROVED)
        # A unit on a preceding monetary table is not this statement's unit.
        no_unit=primary['raw_bytes'].replace(b'(MILLIONS, EXCEPT PER SHARE DATA)',b'')
        earlier=b'<table><tr><td>(in millions, except per share amounts)</td><td>7</td></tr></table>'
        with self.assertRaisesRegex(ValueError,'UNIT_UNRESOLVED'):
            reported_revenue_scope(primary=changed(primary,no_unit.replace(b'<div>Consolidated',earlier+b'<div>Consolidated')),
                                   xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_plain_statement_sections_and_issuer_bound_eps_heading_are_not_scope_prose(self):
        primary,xml,annual=originals()
        raw=primary['raw_bytes'].replace(b'<dei:DocumentType',
            b'<dei:EntityRegistrantName contextRef="annual">Example Co</dei:EntityRegistrantName><dei:DocumentType',1)
        sections=(b'<tr><td>Revenues</td><td></td></tr><tr><td>Costs and expenses</td><td></td></tr>'
            b'<tr><td>EARNINGS/(LOSS) PER SHARE ATTRIBUTABLE TO EXAMPLE COMPANY COMMON AND CLASS B STOCK (Note 8)</td><td></td></tr>'
            b'<tr><td>Weighted-average shares used in computation of earnings/(loss) per share</td><td></td></tr>')
        source=changed(primary,raw.replace(b'</table>',sections+b'</table>'))
        scope=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED)
        self.assertTrue(scope['complete_scope_proven'])
        for bad in (sections.replace(b'EXAMPLE COMPANY',b'OTHER COMPANY'),
                    sections.replace(b'Revenues</td>',b'Revenues exclude subsidiaries</td>')):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'STATEMENT_LOCAL_SCOPE_UNRESOLVED'):
                reported_revenue_scope(primary=changed(primary,raw.replace(b'</table>',bad+b'</table>')),
                    annual=annual,approved_concepts=APPROVED)

    def test_company_co_abbreviation_is_narrower_than_removing_all_legal_suffixes(self):
        primary,xml,annual=originals()
        raw=primary['raw_bytes'].replace(b'<dei:DocumentType',
            b'<dei:EntityRegistrantName contextRef="annual">Example Co</dei:EntityRegistrantName><dei:DocumentType',1)
        title=b'<div>Consolidated Statements of Income</div>'
        for name,allowed in (('Example Company and subsidiaries',True),('Example Co.',True),
                             ('Example LLC and subsidiaries',False),('Other Company',False)):
            source=changed(primary,raw.replace(title,('<div>'+name+'</div>').encode()+title))
            with self.subTest(name=name):
                if allowed:
                    scope=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED)
                    self.assertTrue(scope['complete_scope_proven'])
                else:
                    with self.assertRaisesRegex(ValueError,'STATEMENT_.*SCOPE_UNRESOLVED'):
                        reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED)

    def test_previous_statement_note_reference_is_navigation_only_before_the_title(self):
        primary,xml,annual=originals()
        note=b'<div>The accompanying notes are part of the consolidated financial statements.</div><div>108</div>'
        title=b'<div>Consolidated Statements of Income</div>'
        source=changed(primary,primary['raw_bytes'].replace(title,note+title))
        scope=reported_revenue_scope(primary=source,xml=xml,annual=annual,approved_concepts=APPROVED)
        self.assertTrue(scope['complete_scope_proven'])
        for raw in (primary['raw_bytes'].replace(title,title+note),
                    primary['raw_bytes'].replace(title,note.replace(b'consolidated financial statements',b'Segment Alpha only')+title)):
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'STATEMENT_.*SCOPE_UNRESOLVED'):
                reported_revenue_scope(primary=changed(primary,raw),xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_consolidated_income_statement_title_order_keeps_original_scope(self):
        primary,xml,annual=originals()
        source=changed(primary,primary['raw_bytes'].replace(b'Consolidated Statements of Income',
                                                           b'Consolidated Income Statements'))
        scope=reported_revenue_scope(primary=source,xml=xml,annual=annual,approved_concepts=APPROVED)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertEqual(scope['reported_totals'][0]['total']['value'],'58496000000')
        for title in ('Subsidiary Income Statements','Consolidated Statements of Comprehensive Income'):
            restricted=changed(primary,primary['raw_bytes'].replace(b'Consolidated Statements of Income',title.encode()))
            with self.subTest(title=title),self.assertRaisesRegex(ValueError,'STATEMENT_TITLE_UNPROVEN'):
                reported_revenue_scope(primary=restricted,xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_numeric_note_reference_is_not_a_total_label_or_scope_change(self):
        primary,xml,annual=originals()
        for marker in ('(Note 4)','(note 17)','(4)','(a)'):
            with self.subTest(marker=marker):
                source=changed(primary,primary['raw_bytes'].replace(b'Total revenues',('Total revenues '+marker).encode()))
                scope=reported_revenue_scope(primary=source,xml=xml,annual=annual,approved_concepts=APPROVED)
                self.assertTrue(scope['complete_scope_proven'])
                self.assertEqual(scope['reported_totals'][0]['total']['value'],'58496000000')
                self.assertEqual(scope['reported_totals'][0]['total_cell']['text'],'58496')

    def test_geographic_or_subsidiary_parenthesis_is_not_a_footnote(self):
        primary,xml,annual=originals()
        for marker in ('(Europe)','(Subsidiary)','(Note 4, Europe)','(US)','(4 Europe)'):
            with self.subTest(marker=marker):
                source=changed(primary,primary['raw_bytes'].replace(b'Total revenues',('Total revenues '+marker).encode()))
                scope=reported_revenue_scope(primary=source,xml=xml,annual=annual,approved_concepts=APPROVED)
                self.assertFalse(scope['complete_scope_proven'])
                self.assertEqual(scope['reported_totals'],[])

    def test_explicit_total_admits_existing_fact_without_calculating_component_sum(self):
        source,xml,annual=originals()
        scope=reported_revenue_scope(primary=source,xml=xml,annual=annual,approved_concepts=APPROVED)
        self.assertEqual(scope['status'],'REPORTED_CONSOLIDATED_TOTAL')
        self.assertEqual(scope['reported_totals'][0]['total']['value'],'58496000000')
        original=facts(annual);kept=admit_reported_revenue_facts(facts=original,scope=scope)
        self.assertEqual(kept,[original[1]])
        self.assertEqual(original,facts(annual))
        good={'semantic_role':'revenue','source_binding':{'concept':original[1]['concept']},
              'period_start':original[1]['period_start'],'period_end':original[1]['period_end'],'value':original[1]['value']}
        verify_reported_revenue_observations(observations=[good],scope=scope)
        wrong={**good,'value':original[0]['value'],'source_binding':{'concept':original[0]['concept']}}
        with self.assertRaisesRegex(ValueError,'SELECTED_COMPONENT_NOT_TOTAL'):
            verify_reported_revenue_observations(observations=[wrong],scope=scope)

    def test_separate_heading_table_is_bound_and_not_borrowed_from_other_statement(self):
        source,_,annual=originals()
        raw=source['raw_bytes'].replace(b'<div>Consolidated Statements of Income</div>',
            b'<table><tr><td><div>Consolidated Statements of Income</div><div>(millions, except per share data)</div></td></tr></table>')
        source=changed(source,raw)
        scope=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED)
        self.assertIsNotNone(scope['reported_totals'][0]['statement_scope']['adjacent_heading_table'])
        for between in (b'<table><tr><td>Unrelated table</td></tr></table>',b'<p>Only Segment Alpha is included.</p>'):
            broken=changed(source,raw.replace(b'</table><table>',b'</table>'+between+b'<table>',1))
            with self.subTest(between=between),self.assertRaisesRegex(ValueError,'STATEMENT_'):
                reported_revenue_scope(primary=broken,annual=annual,approved_concepts=APPROVED)
        foreign=changed(source,raw.replace(b'<td><div>Consolidated',b'<td>Other Corporation<div>Consolidated',1))
        with self.assertRaisesRegex(ValueError,'HEADING_TEXT_COVERAGE_UNRESOLVED'):
            reported_revenue_scope(primary=foreign,annual=annual,approved_concepts=APPROVED)

    def test_fiscal_year_column_matches_full_selected_native_period_not_calendar_year(self):
        source,_,annual=originals()
        raw=source['raw_bytes'].replace(b'2025-01-01',b'2023-01-29').replace(b'2025-12-31',b'2024-02-03').replace(b'>2025<',b'>2023<')
        conflicting=raw
        raw=raw.replace(b'Year Ended December 31,',b'')
        annual=deepcopy(annual);annual['filing']['reportDate']='2024-02-03'
        source=changed(source,raw)
        annual['table_input']['target_period']=annual_period(raw=raw,cik=annual['entity'],filing=annual['filing'])
        scope=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED,annual_period_reader=annual_period)
        self.assertEqual(annual['table_input']['target_period']['fiscal_year'],2023)
        self.assertEqual(scope['reported_totals'][0]['total']['period_end'],'2024-02-03')
        with self.assertRaisesRegex(ValueError,'VISIBLE_END_DAY_CONFLICT'):
            reported_revenue_scope(primary=changed(source,conflicting),annual=annual,
                approved_concepts=APPROVED,annual_period_reader=annual_period)
        # The same native annual period cannot authenticate a wrong visible
        # fiscal column (keep original DEI, change only the table year).
        wrong_raw=raw.replace(b'<td>2023</td>',b'<td>2022</td>')
        with self.assertRaisesRegex(ValueError,'FISCAL_COLUMN_UNRESOLVED'):
            reported_revenue_scope(primary=changed(source,wrong_raw),annual=annual,
                approved_concepts=APPROVED,annual_period_reader=annual_period)

    def test_visible_end_day_and_complete_date_agree_before_full_scope_credit(self):
        source,_,annual=originals()
        for raw in [source['raw_bytes'].replace(b'December 31,',b'December 30,'),
                    source['raw_bytes'].replace(b'Year Ended December 31,',b'Years Ended December 30,')]:
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'VISIBLE_END_DAY_CONFLICT'):
                reported_revenue_scope(primary=changed(source,raw),annual=annual,approved_concepts=APPROVED)
        correct=changed(source,source['raw_bytes'].replace(b'<td>2025</td>',b'<td>December 31, 2025</td>'))
        scope=reported_revenue_scope(primary=correct,annual=annual,approved_concepts=APPROVED)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertTrue(scope['reported_totals'][0]['end_headers'])
        wrong=changed(source,source['raw_bytes'].replace(b'<td>2025</td>',b'<td>December 30, 2025</td>'))
        with self.assertRaisesRegex(ValueError,'VISIBLE_DATE_CONFLICT'):
            reported_revenue_scope(primary=wrong,annual=annual,approved_concepts=APPROVED)

    def test_later_year_header_cannot_hide_an_earlier_associated_full_date(self):
        source,_,annual=originals()
        for descriptor in ('December 30, 2025','December 31, 2025'):
            raw=source['raw_bytes'].replace(b'<td>Year Ended December 31,</td><td></td>',
                ('<td>Year Ended December 31,</td><td>'+descriptor+'</td>').encode())
            if descriptor.startswith('December 30'):
                with self.assertRaisesRegex(ValueError,'VISIBLE_DATE_CONFLICT'):
                    reported_revenue_scope(primary=changed(source,raw),annual=annual,approved_concepts=APPROVED)
            else:
                scope=reported_revenue_scope(primary=changed(source,raw),annual=annual,approved_concepts=APPROVED)
                self.assertTrue(scope['complete_scope_proven'])

    def test_resolved_label_keeps_raw_year_and_cannot_borrow_another_source(self):
        from vnext.fiscal_year_labels import inspect_fiscal_year_labels
        source,_,annual=originals()
        raw=source['raw_bytes'].replace(b'<td>2025</td>',b'<td>2026</td>')
        raw=raw.replace(b'Year Ended December 31,',b'')
        definition=b'<p>Our fiscal year ends on December 31. References to fiscal 2026, for example, refer to the fiscal year ending December 31, 2025.</p>'
        raw=b'<html><body>'+raw.replace(b'</xbrli:xbrl>',definition+b'</xbrli:xbrl>')+b'</body></html>'
        source=changed(source,raw)
        cf=json.dumps({'cik':int(annual['entity']),'facts':{'us-gaap':{'Revenues':{'units':{'USD':[
            {'accn':annual['filing']['accessionNumber'],'fy':2025,'fp':'FY','form':'10-K','val':58496000000,
             'start':'2025-01-01','end':'2025-12-31','filed':'2026-02-01'}]}}}}}).encode()
        inspected=inspect_fiscal_year_labels(primary_bytes=raw,companyfacts_bytes=cf,
            expected_primary_sha256=sha256_bytes(content=raw),expected_companyfacts_sha256=sha256_bytes(content=cf),
            expected_cik=annual['entity'],filing=annual['filing'])
        label={'record_type':'ORDINARY_FISCAL_YEAR_LABEL_RESOLUTION','source_inspection':inspected,
               'selected_fiscal_year':2026,'original_dei_fiscal_year':2025}
        scope=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED,
            fiscal_label_resolution=label)
        self.assertEqual(scope['selected_fiscal_column_year'],2026)
        self.assertEqual(scope['annual_input']['table_input']['target_period']['fiscal_year'],2025)
        bad=deepcopy(label);bad['source_inspection']['primary_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'FISCAL_LABEL_SOURCE_CHANGED'):
            reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED,fiscal_label_resolution=bad)
        bad=deepcopy(label);bad['selected_fiscal_year']=2027
        with self.assertRaisesRegex(ValueError,'FISCAL_LABEL_SELECTION_CHANGED'):
            reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED,fiscal_label_resolution=bad)
        # Explicit date headers cannot be reinterpreted as arbitrary fiscal
        # labels; pure year-column and actual dates remain separate checks.
        calendar_raw=raw.replace(b'<td>2026</td>',b'<td>December 31, 2026</td>')
        calendar=changed(source,calendar_raw)
        calendar_inspected=inspect_fiscal_year_labels(primary_bytes=calendar_raw,companyfacts_bytes=cf,
            expected_primary_sha256=sha256_bytes(content=calendar_raw),expected_companyfacts_sha256=sha256_bytes(content=cf),
            expected_cik=annual['entity'],filing=annual['filing'])
        calendar_label={**label,'source_inspection':calendar_inspected}
        with self.assertRaisesRegex(ValueError,'VISIBLE_DATE_CONFLICT'):
            reported_revenue_scope(primary=calendar,annual=annual,approved_concepts=APPROVED,
                fiscal_label_resolution=calendar_label)
        conditional_raw=raw.replace(b'References to fiscal 2026',
            b'If the proposed naming convention is approved, References to fiscal 2026')
        conditional=changed(source,conditional_raw)
        conditional_inspected=inspect_fiscal_year_labels(primary_bytes=conditional_raw,companyfacts_bytes=cf,
            expected_primary_sha256=sha256_bytes(content=conditional_raw),expected_companyfacts_sha256=sha256_bytes(content=cf),
            expected_cik=annual['entity'],filing=annual['filing'])
        self.assertEqual(conditional_inspected['source_defined_fiscal_year'],2026)
        with self.assertRaisesRegex(ValueError,'FISCAL_LABEL_UNRESOLVED'):
            reported_revenue_scope(primary=conditional,annual=annual,approved_concepts=APPROVED,
                fiscal_label_resolution={**label,'source_inspection':conditional_inspected})

    def test_limited_scope_wrong_scale_and_xml_disagreement_remain_errors(self):
        source,xml,annual=originals()
        for raw,error in [
            (source['raw_bytes'].replace(b'<table>',b'<table><caption>Segment Alpha only</caption>'),'CAPTION_SCOPE'),
            (source['raw_bytes'].replace(b'MILLIONS, EXCEPT PER SHARE DATA',b'THOUSANDS, EXCEPT PER SHARE DATA'),'UNIT_UNRESOLVED'),
            (source['raw_bytes'].replace(b'<td>Net income</td>',b'<td>Net income; Total revenues exclude Subsidiary Beta operations</td>'),'LOCAL_SCOPE'),
        ]:
            with self.subTest(error=error),self.assertRaisesRegex(ValueError,error):
                reported_revenue_scope(primary=changed(source,raw),annual=annual,approved_concepts=APPROVED)
        xml=changed(xml,xml['raw_bytes'].replace(b'>58496<',b'>60000<'))
        with self.assertRaisesRegex(ValueError,'XML_TOTAL_DIFFERS'):
            reported_revenue_scope(primary=source,xml=xml,annual=annual,approved_concepts=APPROVED)

    def test_note_total_or_wrong_companyfacts_filing_does_not_supply_company_total(self):
        source,_,annual=originals(full=False)
        scope=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED)
        self.assertFalse(scope['complete_scope_proven'])
        source,_,annual=originals();scope=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED)
        rows=facts(annual);rows[1]['accession']='later'
        with self.assertRaisesRegex(ValueError,'TOTAL_NOT_IN_COMPANYFACTS'):
            admit_reported_revenue_facts(facts=rows,scope=scope)


class ReportedOperatingRevenueTest(unittest.TestCase):
    def statement(self):
        source,_,annual=originals()
        raw=source['raw_bytes'].replace(b'Total revenues',b'Total operating revenues')
        raw=raw.replace(b'CostOfGoodsAndServicesSold',b'OperatingCostsAndExpenses')
        raw=raw.replace(b'Cost of sales',b'Total operating expenses')
        raw=raw.replace(b'EXCEPT PER SHARE DATA',b'EXCEPT PER SHARE AMOUNTS')
        raw=raw.replace(b'<tr><td>Product revenues',b'<tr><td>OPERATING REVENUES:</td><td></td></tr><tr><td>Product revenues')
        raw=raw.replace(b'<tr><td>Total operating expenses',b'<tr><td>OPERATING EXPENSES:</td><td></td></tr><tr><td>Total operating expenses')
        raw=raw.replace(b'<tr><td>Net income',b'<tr><td>NON-OPERATING EXPENSES (INCOME):</td><td></td></tr><tr><td>Net income')
        return changed(source,raw),annual

    def test_reported_operating_total_preserves_approved_native_amount_and_whole_statement(self):
        source,annual=self.statement()
        result=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED,xml=source)
        self.assertTrue(result['complete_scope_proven'])
        self.assertEqual(result['reported_totals'][0]['total']['value'],'58496000000')
        self.assertEqual(result['reported_totals'][0]['xml_check'],'MATCH')

    def test_operating_components_or_wrong_unit_or_segment_do_not_get_total_credit(self):
        source,annual=self.statement()
        for old,new in ((b'Total operating revenues',b'Passenger revenues'),
                (b'MILLIONS, EXCEPT PER SHARE AMOUNTS',b'THOUSANDS, EXCEPT PER SHARE AMOUNTS'),
                (b'Total operating expenses',b'Total operating expenses; only Segment Alpha operations included'),
                (b'Total operating expenses',b'Salaries, wages, and benefits'),
                (b'OperatingCostsAndExpenses',b'OtherCostAndExpenseOperating')):
            altered=changed(source,source['raw_bytes'].replace(old,new))
            try:scope=reported_revenue_scope(primary=altered,annual=annual,approved_concepts=APPROVED)
            except ValueError:continue
            self.assertFalse(scope['complete_scope_proven'])

    def test_reported_net_expense_total_retains_whole_statement_scope(self):
        source, annual = self.statement()
        raw = source['raw_bytes'].replace(b'Total operating expenses',
            b'Total operating expenses, net').replace(b'OPERATING EXPENSES:',
            b'OPERATING EXPENSES, NET:').replace(b'NON-OPERATING EXPENSES (INCOME):',
            b'OTHER EXPENSES (INCOME):')
        adjusted = changed(source, raw)
        result = reported_revenue_scope(primary=adjusted, annual=annual,
            approved_concepts=APPROVED, xml=adjusted)
        self.assertTrue(result['complete_scope_proven'])
        total = result['reported_totals'][0]
        self.assertEqual('58496000000', total['total']['value'])
        self.assertEqual('MATCH', total['xml_check'])
        self.assertEqual(1, len(total['operating_expense_reports']))

    def test_net_expense_adjustments_and_scope_qualifiers_remain_unproven(self):
        source, annual = self.statement()
        for label in (b'Total operating expenses, net, excluding special items',
                      b'Total operating expenses, net (non-GAAP)',
                      b'Total operating expenses, net (domestic)',
                      b'Total operating expenses, net, as reported'):
            with self.subTest(label=label):
                altered = changed(source, source['raw_bytes'].replace(
                    b'Total operating expenses', label))
                result = reported_revenue_scope(primary=altered, annual=annual,
                    approved_concepts=APPROVED, xml=altered)
                self.assertFalse(result['complete_scope_proven'])


    def test_operating_label_parenthetical_scope_cannot_be_discarded(self):
        source,annual=self.statement()
        for before,after in ((b'Total operating revenues',b'Total operating revenues (domestic)'),
                (b'Total operating revenues',b'Total operating revenues (subtotal)'),
                (b'Total operating expenses',b'Total operating expenses (domestic)')):
            altered=changed(source,source['raw_bytes'].replace(before,after))
            with self.subTest(label=after):
                result=reported_revenue_scope(primary=altered,annual=annual,
                    approved_concepts=APPROVED,xml=altered)
                self.assertFalse(result['complete_scope_proven'])
