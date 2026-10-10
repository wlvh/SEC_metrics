"""Finite source/period controls; constructed statements are not company results."""
from copy import deepcopy
import json
import unittest

from tests.vnext.test_selected_revenue_scope_v1 import originals,APPROVED,facts
from vnext.canonical import sha256_bytes
from vnext.selected_reported_revenue_v2 import reported_revenue_scope,admit_reported_revenue_facts,verify_reported_revenue_observations
from vnext.historical_dei import annual_period


def changed(source,raw):
    return {**source,'raw_bytes':raw,'source_reference':{**source['source_reference'],
            'raw_asset_id':'sha256:'+sha256_bytes(content=raw)}}


class SelectedReportedRevenueTest(unittest.TestCase):
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
        annual=deepcopy(annual);annual['filing']['reportDate']='2024-02-03'
        source=changed(source,raw)
        annual['table_input']['target_period']=annual_period(raw=raw,cik=annual['entity'],filing=annual['filing'])
        scope=reported_revenue_scope(primary=source,annual=annual,approved_concepts=APPROVED,annual_period_reader=annual_period)
        self.assertEqual(annual['table_input']['target_period']['fiscal_year'],2023)
        self.assertEqual(scope['reported_totals'][0]['total']['period_end'],'2024-02-03')
        # The same native annual period cannot authenticate a wrong visible
        # fiscal column (keep original DEI, change only the table year).
        wrong_raw=raw.replace(b'<td>2023</td>',b'<td>2022</td>')
        with self.assertRaisesRegex(ValueError,'FISCAL_COLUMN_UNRESOLVED'):
            reported_revenue_scope(primary=changed(source,wrong_raw),annual=annual,
                approved_concepts=APPROVED,annual_period_reader=annual_period)

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
