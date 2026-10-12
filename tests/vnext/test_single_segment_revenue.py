"""Single-segment facts still need a complete consolidated statement proof."""
import re
import unittest

from tests.vnext.test_single_revenue_line import single_statement, APPROVED
from tests.vnext.test_selected_reported_revenue_v2 import changed
from vnext.selected_income_source_v1 import native_income_reports
from vnext.selected_reported_revenue_v2 import reported_revenue_scope


def original(*, operating='1', reportable='1'):
    source,annual=single_statement()
    raw=source['raw_bytes'].replace(b'<xbrli:xbrl ',
        b'<xbrli:xbrl xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:issuer="https://example.test/issuer/2025" ')
    annual_context=re.search(rb'<xbrli:context id="annual">.*?</xbrli:context>',raw,re.S)[0]
    segment_context=annual_context.replace(b'id="annual"',b'id="segment"').replace(
        b'</xbrli:context>',b'<xbrli:scenario><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">issuer:ReportableSegmentMember</xbrldi:explicitMember></xbrli:scenario></xbrli:context>')
    counts=(f'<xbrli:unit id="count"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit>'
        f'<us-gaap:NumberOfOperatingSegments contextRef="annual" unitRef="count" decimals="INF">{operating}</us-gaap:NumberOfOperatingSegments>'
        f'<us-gaap:NumberOfReportableSegments contextRef="annual" unitRef="count" decimals="INF">{reportable}</us-gaap:NumberOfReportableSegments>').encode()
    raw=raw.replace(annual_context,annual_context+segment_context+counts,1)
    raw=raw.replace(b'<td>Revenues</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="annual"',
        b'<td>Net revenues</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="segment"')
    return changed(source,raw),annual


class SingleSegmentRevenueTest(unittest.TestCase):
    def scope(self,source,annual,**kwargs):
        return reported_revenue_scope(primary=source,xml=source,annual=annual,
            approved_concepts=APPROVED,allow_single_segment_revenue=True,**kwargs)

    def test_shared_year_header_does_not_bind_another_amount_column(self):
        source, annual = original()
        raw = source['raw_bytes'].replace(b'<td>2025</td>', b'<td colspan="2">2025</td>')
        raw = raw.replace(b'Year Ended December 31,</td><td></td>',
                          b'Year Ended December 31,</td><td colspan="2"></td>')
        raw = raw.replace(b'>58496</ix:nonFraction></td>', b'>58496</ix:nonFraction></td><td></td>')
        for shifted in [('Cost of sales',), ('Net income',), ('Cost of sales', 'Net income')]:
            changed_raw = raw
            for label in shifted:
                changed_raw = changed_raw.replace(('<td>'+label+'</td><td>').encode(),
                    ('<td>'+label+'</td><td></td><td>').encode())
            with self.subTest(shifted=shifted), self.assertRaisesRegex(ValueError,
                    'SINGLE_SEGMENT_STATEMENT_COLUMN_CONFLICT'):
                self.scope(changed(source, changed_raw), annual)

    def test_supporting_amount_colspan_covering_the_revenue_column_is_valid(self):
        source, annual = original()
        raw = source['raw_bytes'].replace(b'<td>2025</td>', b'<td colspan="2">2025</td>')
        raw = raw.replace(b'Year Ended December 31,</td><td></td>',
                          b'Year Ended December 31,</td><td colspan="2"></td>')
        raw = raw.replace(b'>58496</ix:nonFraction></td>', b'>58496</ix:nonFraction></td><td></td>')
        for label in ('Cost of sales', 'Net income'):
            raw = raw.replace(('<td>'+label+'</td><td>').encode(),
                              ('<td>'+label+'</td><td colspan="2">').encode())
        result = self.scope(changed(source, raw), annual)
        self.assertTrue(result['complete_scope_proven'])
        chosen = result['reported_totals'][0]
        self.assertEqual(chosen['total']['value'], '58496000000')
        self.assertEqual(chosen['xml_check'], 'MATCH')
        self.assertTrue(all(row['cell']['colspan'] == 2 for row in chosen['consolidated_statement_rows']))

    def test_explicit_single_segment_revenue_keeps_original_dimension_and_default(self):
        source,annual=original()
        default=reported_revenue_scope(primary=source,xml=source,annual=annual,approved_concepts=APPROVED)
        self.assertFalse(default['complete_scope_proven'])
        self.assertNotIn('single_segment_revenue_allowed',default)
        self.assertFalse(any(r['context']['dimensions'] for r in native_income_reports(source,annual,APPROVED)))
        result=self.scope(source,annual)
        self.assertTrue(result['complete_scope_proven'])
        total=result['reported_totals'][0]['total']
        self.assertEqual(total['value'],'58496000000')
        self.assertEqual(total['context']['dimensions'],{'us-gaap:StatementBusinessSegmentsAxis':'issuer:ReportableSegmentMember'})
        self.assertEqual(result['reported_totals'][0]['xml_check'],'MATCH')
        self.assertEqual(total['single_segment_scope']['status'],'ONE_OPERATING_AND_REPORTABLE_SEGMENT')

    def test_missing_ambiguous_or_multiple_segment_counts_do_not_prove_scope(self):
        for operating,reportable in [('2','1'),('1','2'),('1','0')]:
            source,annual=original(operating=operating,reportable=reportable)
            with self.subTest(operating=operating,reportable=reportable):
                self.assertFalse(self.scope(source,annual)['complete_scope_proven'])
        source,annual=original()
        raw=re.sub(rb'<us-gaap:NumberOfOperatingSegments\b.*?</us-gaap:NumberOfOperatingSegments>',b'',source['raw_bytes'])
        self.assertFalse(self.scope(changed(source,raw),annual)['complete_scope_proven'])

    def test_geography_product_and_arbitrary_members_are_not_company_totals(self):
        source,annual=original()
        for before,after in [(b'StatementBusinessSegmentsAxis',b'StatementGeographicalAxis'),
                             (b'ReportableSegmentMember',b'UnitedStatesMember'),
                             (b'ReportableSegmentMember',b'ProductAlphaMember')]:
            with self.subTest(after=after):
                self.assertFalse(self.scope(changed(source,source['raw_bytes'].replace(before,after)),annual)['complete_scope_proven'])

    def test_equal_amount_in_a_note_or_limited_statement_does_not_prove_scope(self):
        source,annual=original()
        for old,new in [(b'Consolidated Statements of Income',b'Revenue note'),
                        (b'Net revenues</td>',b'Net revenues (Europe)</td>'),
                        (b'<table>',b'<table><caption>Segment only; excludes other operations</caption>')]:
            altered=changed(source,source['raw_bytes'].replace(old,new))
            with self.subTest(new=new):
                try:result=self.scope(altered,annual)
                except ValueError:continue
                self.assertFalse(result['complete_scope_proven'])

    def test_xml_count_or_amount_conflict_remains_rejected(self):
        source,annual=original()
        for old,new in [(b'decimals="INF">1</us-gaap:NumberOfOperatingSegments>',b'decimals="INF">2</us-gaap:NumberOfOperatingSegments>'),
                        (b'>58496</ix:nonFraction>',b'>58495</ix:nonFraction>')]:
            xml=changed(source,source['raw_bytes'].replace(old,new))
            with self.subTest(new=new):
                try:result=reported_revenue_scope(primary=source,xml=xml,annual=annual,
                    approved_concepts=APPROVED,allow_single_segment_revenue=True)
                except ValueError:continue
                self.assertFalse(result['complete_scope_proven'])

    def test_option_is_not_a_general_dimension_or_xml_bypass(self):
        source,annual=original()
        self.assertFalse(reported_revenue_scope(primary=source,annual=annual,
            approved_concepts=APPROVED,allow_single_segment_revenue=True)['complete_scope_proven'])
        for option in (1,'true',None):
            with self.subTest(option=option),self.assertRaises(ValueError):
                reported_revenue_scope(primary=source,xml=source,annual=annual,
                    approved_concepts=APPROVED,allow_single_segment_revenue=option)

    def test_wrong_count_period_currency_or_conflicting_count_stays_unproved(self):
        source,annual=original()
        changes=[(b'NumberOfOperatingSegments contextRef="annual"',b'NumberOfOperatingSegments contextRef="short"'),
                 (b'<xbrli:measure>xbrli:pure</xbrli:measure>',b'<xbrli:measure>iso4217:USD</xbrli:measure>'),
                 (b'</us-gaap:NumberOfOperatingSegments>',b'</us-gaap:NumberOfOperatingSegments><us-gaap:NumberOfOperatingSegments contextRef="annual" unitRef="count" decimals="INF">2</us-gaap:NumberOfOperatingSegments>')]
        for before,after in changes:
            with self.subTest(after=after):
                self.assertFalse(self.scope(changed(source,source['raw_bytes'].replace(before,after)),annual)['complete_scope_proven'])

    def test_additional_dimension_or_second_segment_member_stays_unproved(self):
        source,annual=original()
        extra=b'<xbrldi:explicitMember dimension="issuer:ProductAxis">issuer:ProductAlphaMember</xbrldi:explicitMember>'
        self.assertFalse(self.scope(changed(source,source['raw_bytes'].replace(
            b'</xbrli:scenario>',extra+b'</xbrli:scenario>')),annual)['complete_scope_proven'])
        context=re.search(rb'<xbrli:context id="segment">.*?</xbrli:context>',source['raw_bytes'],re.S)[0]
        another=context.replace(b'id="segment"',b'id="another"').replace(b'ReportableSegmentMember',b'SegmentBetaMember')
        self.assertFalse(self.scope(changed(source,source['raw_bytes'].replace(context,context+another)),annual)['complete_scope_proven'])

    def test_issuer_segment_unit_is_supported_but_not_another_issuers_unit(self):
        source,annual=original()
        raw=source['raw_bytes'].replace(b'<xbrli:measure>xbrli:pure</xbrli:measure>',
            b'<xbrli:measure>issuer:segment</xbrli:measure>')
        self.assertTrue(self.scope(changed(source,raw),annual)['complete_scope_proven'])
        self.assertTrue(self.scope(changed(source,raw.replace(b'Other income, net',
            b'Other income (expense), net')),annual)['complete_scope_proven'])
        raw=raw.replace(b'<xbrli:xbrl ',b'<xbrli:xbrl xmlns:other="https://other.test/issuer/2025" ',1)
        raw=raw.replace(b'<xbrli:measure>issuer:segment</xbrli:measure>',b'<xbrli:measure>other:segment</xbrli:measure>')
        self.assertFalse(self.scope(changed(source,raw),annual)['complete_scope_proven'])

    def test_missing_income_or_an_extra_top_line_cannot_be_completed_by_counts(self):
        source,annual=original()
        for raw in (re.sub(rb'<tr><td>Net income</td>.*?</tr>',b'',source['raw_bytes']),
                    source['raw_bytes'].replace(b'<tr><td>Cost of sales',
                        b'<tr><td>Other revenue</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="annual" unitRef="usd" scale="6" decimals="-6">10</ix:nonFraction></td></tr><tr><td>Cost of sales')):
            with self.subTest(raw_length=len(raw)):
                try:result=self.scope(changed(source,raw),annual)
                except ValueError:continue
                self.assertFalse(result['complete_scope_proven'])

    def test_section_heading_does_not_hide_an_untagged_amount_or_scope_qualifier(self):
        source,annual=original()
        header=b'<tr><td>Other income, net</td><td></td></tr>'
        raw=source['raw_bytes'].replace(b'<tr><td>Net income',header+b'<tr><td>Net income')
        self.assertTrue(self.scope(changed(source,raw),annual)['complete_scope_proven'])
        for old,new in [(b'Other income, net</td>',b'Other income, net excluding subsidiaries</td>'),
                        (header,b'<tr><td>Other income, net</td><td>123</td></tr>')]:
            with self.subTest(new=new),self.assertRaises(ValueError):
                self.scope(changed(source,raw.replace(old,new)),annual)

    def test_dimension_is_not_promoted_for_nonrevenue_concepts_or_wrong_axis_namespace(self):
        from vnext.selected_income_source_v1 import single_segment_revenue_reports
        source,annual=original()
        self.assertEqual(single_segment_revenue_reports(source,annual,['us-gaap:CostOfRevenue']),[])
        raw=source['raw_bytes'].replace(b'<xbrli:xbrl ',
            b'<xbrli:xbrl xmlns:fake="https://unregistered.test/us-gaap/2025" ',1)
        raw=raw.replace(b'dimension="us-gaap:StatementBusinessSegmentsAxis"',
            b'dimension="fake:StatementBusinessSegmentsAxis"')
        self.assertFalse(self.scope(changed(source,raw),annual)['complete_scope_proven'])

    def test_existing_nondimensional_facts_are_filtered_without_new_calculator_operands(self):
        from copy import deepcopy
        from tests.vnext.test_selected_revenue_scope_v1 import facts
        from vnext.selected_reported_revenue_v2 import admit_reported_revenue_facts
        source,annual=original();structured=facts(annual);before=deepcopy(structured)
        selected=admit_reported_revenue_facts(facts=structured,scope=self.scope(source,annual))
        self.assertEqual(selected,[structured[1]])
        self.assertEqual(structured,before)
        self.assertNotIn('single_segment_scope',selected[0])
        self.assertNotIn('context',selected[0])

    def test_company_cost_scale_cannot_disagree_with_the_same_visible_unit_caption(self):
        source,annual=original()
        raw=source['raw_bytes'].replace(
            b'name="us-gaap:CostOfGoodsAndServicesSold" contextRef="annual" unitRef="usd" scale="6"',
            b'name="us-gaap:CostOfGoodsAndServicesSold" contextRef="annual" unitRef="usd" scale="3"')
        with self.assertRaisesRegex(ValueError,'SINGLE_SEGMENT_STATEMENT_SCALE_CONFLICT'):
            self.scope(changed(source,raw),annual)

    def test_explicit_sec_release_survives_the_single_segment_combination(self):
        from vnext.historical_dei import annual_period
        from vnext.xbrl_namespace_policy import YEAR_QUARTER_OR_DATE
        source,annual=original()
        source=changed(source,source['raw_bytes'].replace(b'http://xbrl.sec.gov/dei/2025',
            b'http://xbrl.sec.gov/dei/2025q4'))
        result=self.scope(source,annual,annual_period_reader=annual_period,
            dei_release=YEAR_QUARTER_OR_DATE)
        self.assertTrue(result['complete_scope_proven'])
        self.assertTrue(result['single_segment_revenue_allowed'])
        self.assertEqual(result['dei_release'],YEAR_QUARTER_OR_DATE)

    def test_optional_undecodable_counts_never_break_the_old_nondimensional_route(self):
        source,annual=original()
        raw=source['raw_bytes'].replace(b'<xbrli:xbrl ',
            b'<xbrli:xbrl xmlns:unknown="https://unsupported.test/numeric" ',1)
        raw=raw.replace(b'NumberOfOperatingSegments contextRef="annual"',
            b'NumberOfOperatingSegments format="unknown:word" contextRef="annual"')
        raw=raw.replace(b'name="us-gaap:Revenues" contextRef="segment"',
            b'name="us-gaap:Revenues" contextRef="annual"')
        from unittest.mock import patch
        with patch('vnext.selected_income_source_v1._single_segment_scope',
                side_effect=AssertionError('No dimensional candidate needs count qualification')):
            result=self.scope(changed(source,raw),annual,allow_single_revenue_line=True)
        self.assertTrue(result['complete_scope_proven'])
        self.assertNotIn('single_segment_scope',result['reported_totals'][0]['total'])

    def test_unsupported_count_transform_is_unproved_but_numeric_integrity_errors_propagate(self):
        source,annual=original()
        raw=source['raw_bytes'].replace(b'<xbrli:xbrl ',
            b'<xbrli:xbrl xmlns:unknown="https://unsupported.test/numeric" ',1)
        raw=raw.replace(b'NumberOfOperatingSegments contextRef="annual"',
            b'NumberOfOperatingSegments format="unknown:word" contextRef="annual"')
        result=self.scope(changed(source,raw),annual)
        self.assertFalse(result['complete_scope_proven'])
        from unittest.mock import patch
        from vnext.governance_signals import GovernanceSignalError
        import vnext.selected_income_source_v1 as native
        original_value=native._source_value
        def bad_value(fact,metadata):
            if 'numberofoperatingsegments' in metadata['concept'][1].casefold():
                raise GovernanceSignalError('TEST_ONLY_SOURCE_INTEGRITY_ERROR')
            return original_value(fact,metadata)
        with patch.object(native,'_source_value',side_effect=bad_value),self.assertRaisesRegex(
                ValueError,'TEST_ONLY_SOURCE_INTEGRITY_ERROR'):
            self.scope(source,annual)
