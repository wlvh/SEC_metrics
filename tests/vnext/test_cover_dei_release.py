"""Explicit SEC cover-name release options, not semantic model judgments."""
import inspect
import unittest
from tests.vnext.test_text_coverage import annual,binding
from vnext.selected_reported_revenue_v2 import _defined_income_headers,reported_revenue_scope
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.text_results_v2 import _ReportedFactMetadata
from vnext.going_concern_source import _registrant_name_binding
from vnext.text_coverage import build_text_document
from vnext.xbrl_namespace_policy import YEAR_ONLY,YEAR_QUARTER_OR_DATE,YEAR_OR_DATE_RELEASE


def source(namespace='http://xbrl.sec.gov/dei/2025',cover='EXAMPLE INCORPORATED'):
    raw=annual('<h1>FORM 10-K</h1><p>'+cover+'</p><p>(Exact name of registrant as specified in its charter)</p><h2>Item 1. Business</h2><p>Our operations.</p>')
    raw=raw.replace(b'</ix:hidden>',b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">EXAMPLE INC /DE/</ix:nonNumeric></ix:hidden>')
    raw=raw.replace(b'http://xbrl.sec.gov/dei/2025',namespace.encode())
    bound=binding(raw);primary={'raw_bytes':raw,'raw_blob':bound['raw_blob'],'source_reference':bound['source_reference']}
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    metadata=_ReportedFactMetadata();metadata.feed(raw.decode());metadata.close()
    selected={'company_id':'sample_entity','entity':'12345','filing':{'reportDate':'2025-12-31'},
              'table_input':{'target_period':{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}}}
    return primary,parsed,metadata,selected,bound


class CoverDeiReleaseTest(unittest.TestCase):
    def test_explicit_quarter_cover_is_bound_to_same_source_and_registrant(self):
        primary,parsed,metadata,selected,bound=source('http://xbrl.sec.gov/dei/2025q4')
        headers=_defined_income_headers(primary,parsed,selected,include_cover=True,dei_release=YEAR_QUARTER_OR_DATE)
        proof=headers['definitions'][0]['same_source_cover_name_binding']
        self.assertEqual(proof['status'],'SAME_SOURCE_COVER_AND_CURRENT_DEI_NAME_BOUND')
        self.assertEqual(set(proof['accepted_source_names']),{'EXAMPLE INC /DE/','EXAMPLE INCORPORATED'})
        self.assertFalse(proof['relation']['marker_jurisdiction_meaning_asserted'])

    def test_year_default_is_identical_to_explicit_year_option(self):
        primary,parsed,metadata,selected,bound=source()
        self.assertEqual(_defined_income_headers(primary,parsed,selected,include_cover=True),
            _defined_income_headers(primary,parsed,selected,include_cover=True,dei_release=YEAR_ONLY))
        document=build_text_document(**bound)
        self.assertEqual(_registrant_name_binding(document,parsed,metadata),
            _registrant_name_binding(document,parsed,metadata,namespace_policy=YEAR_ONLY))
        self.assertEqual(inspect.signature(reported_revenue_scope).parameters['dei_release'].default,YEAR_ONLY)

    def test_quarter_is_still_refused_without_explicit_release(self):
        primary,parsed,metadata,selected,bound=source('http://xbrl.sec.gov/dei/2025q4')
        headers=_defined_income_headers(primary,parsed,selected,include_cover=True)
        # Unsupported name facts cannot authorize a cover alias. The helper
        # has no cover work to execute when the correct namespace filter
        # removed them; whole-statement refusal is tested separately.
        self.assertEqual(headers['definitions'],[])
        self.assertEqual(headers['heading_patterns'],())

    def test_fasb_policy_or_unknown_value_is_not_a_sec_release(self):
        primary,parsed,metadata,selected,bound=source()
        for option in (YEAR_OR_DATE_RELEASE,'ALL',True,None):
            with self.subTest(option=option),self.assertRaisesRegex(ValueError,'SEC_NAMESPACE_POLICY_UNSUPPORTED'):
                _defined_income_headers(primary,parsed,selected,include_cover=True,dei_release=option)

    def test_cover_conflict_does_not_become_an_alias(self):
        primary,parsed,metadata,selected,bound=source('http://xbrl.sec.gov/dei/2025q4',cover='EXAMPLE CREDIT INCORPORATED')
        with self.assertRaisesRegex(ValueError,'COVER_NAME_NOT_BOUND'):
            _defined_income_headers(primary,parsed,selected,include_cover=True,dei_release=YEAR_QUARTER_OR_DATE)

    def test_current_subject_and_period_cannot_be_changed_by_option(self):
        primary,parsed,metadata,selected,bound=source('http://xbrl.sec.gov/dei/2025q4')
        # This helper only returns headings. No same-entity name means no alias,
        # rather than requiring an exception from an unused cover branch.
        wrong=_defined_income_headers(primary,parsed,{**selected,'entity':'98765'},
            include_cover=True,dei_release=YEAR_QUARTER_OR_DATE)
        self.assertEqual(wrong['definitions'],[])
        self.assertEqual(wrong['heading_patterns'],())
        with self.assertRaises(ValueError):
            build_text_document(**{**bound,'expected_cik':'98765'},namespace_policy=YEAR_QUARTER_OR_DATE)
        with self.assertRaises(ValueError):
            _defined_income_headers(primary,parsed,{**selected,'filing':{'reportDate':'2024-12-31'}},
                include_cover=True,dei_release=YEAR_QUARTER_OR_DATE)

    def test_custom_or_invalid_sec_uri_does_not_supply_a_registrant(self):
        for uri in ('http://example.com/dei/2025q4','http://xbrl.sec.gov/dei/2025q5',
                    'http://xbrl.sec.gov/dei/2025q4/extra'):
            with self.subTest(uri=uri):
                primary,parsed,metadata,selected,bound=source(uri)
                headers=_defined_income_headers(primary,parsed,selected,include_cover=True,
                    dei_release=YEAR_QUARTER_OR_DATE)
                self.assertEqual(headers['heading_patterns'],())
                self.assertEqual(headers['definitions'],[])

    def test_public_scope_records_explicit_sec_option_without_changing_fasb_policy(self):
        from tests.vnext.test_statement_group_totals import closed_statement
        from tests.vnext.test_selected_reported_revenue_v2 import changed
        from tests.vnext.test_single_revenue_line import APPROVED
        from vnext.historical_dei import annual_period
        from unittest.mock import patch
        import vnext.selected_reported_revenue_v2 as revenue
        primary,selected=closed_statement()
        primary=changed(primary,primary['raw_bytes'].replace(
            b'http://xbrl.sec.gov/dei/2025',b'http://xbrl.sec.gov/dei/2025q4'))
        original=revenue._defined_income_headers
        with patch.object(revenue,'_defined_income_headers',wraps=original) as headers:
            scope=reported_revenue_scope(primary=primary,xml=primary,annual=selected,
                approved_concepts=APPROVED,allow_statement_group_totals=True,
                annual_period_reader=annual_period,
                dei_release=YEAR_QUARTER_OR_DATE)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertEqual(scope['dei_release'],YEAR_QUARTER_OR_DATE)
        self.assertEqual(headers.call_args.kwargs['dei_release'],YEAR_QUARTER_OR_DATE)
        self.assertEqual(inspect.signature(reported_revenue_scope).parameters['namespace_policy'].default,YEAR_ONLY)
