"""Pure selected-byte fiscal labels; no annual preparation or acceptance."""
import json
import unittest
from unittest.mock import patch
from tests.vnext.test_dei_release_selection import annual as base_annual

def annual(*args, **kwargs):
    raw = base_annual(*args, **kwargs).replace(b'<xbrli:identifier>', b'<xbrli:identifier scheme="http://www.sec.gov/CIK">').replace(b'<html ', b'<html xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" ')
    return raw.replace(b'>', b'><body>', 1).replace(b'</html>', b'</body></html>')

from vnext.canonical import sha256_bytes
from vnext.historical_fiscal_labels import resolve_selected_fiscal_year_label

FILING={'form':'10-K','reportDate':'2021-12-31','accessionNumber':'0000019617-22-000001'}

def facts(year=2021,cik=19617,accession=None):
    return json.dumps({'cik':cik,'facts':{'us-gaap':{'Revenues':{'units':{'USD':[
        {'accn':accession or FILING['accessionNumber'],'fy':year,'start':'2021-01-01',
         'end':'2021-12-31','form':'10-K','fp':'FY','filed':'2022-02-01','val':1}]}}}}}).encode()


class SelectedHistoricalFiscalLabelTest(unittest.TestCase):
    def resolve(self,raw=None,cf=None,**changes):
        raw=raw or annual();cf=cf or facts()
        args={'primary_bytes':raw,'companyfacts_bytes':cf,'expected_primary_sha256':sha256_bytes(content=raw),
              'expected_companyfacts_sha256':sha256_bytes(content=cf),'expected_cik':'19617','filing':FILING}
        args.update(changes)
        with patch('vnext.historical_annual_input.prepare_historical_annual_input',side_effect=AssertionError('No annual preparation')):
            return resolve_selected_fiscal_year_label(**args)

    def test_consistent_original_metadata_resolves_without_end_year_inference(self):
        r=self.resolve();self.assertEqual(r['selected_fiscal_year'],2021)
        self.assertEqual(r['basis'],'CONSISTENT_SOURCE_METADATA');self.assertEqual(r['original_dei_fiscal_year'],2021)
        self.assertEqual(r['actual_period'],{'period_start':'2021-01-01','period_end':'2021-12-31'})
        self.assertFalse(r['candidate_uniqueness_proven']);self.assertFalse(r['source_admission_proven'])
        self.assertFalse(r['metric_acceptance_proven']);self.assertEqual(r['calls'],{'provider':0,'paid':0,'sec':0})

    def test_explicit_issuer_definition_overrides_conflicting_metadata_but_retains_it(self):
        raw=annual().replace(b'</body></html>',b'<p>Our fiscal year ends on December 31. References to fiscal 2022, for example, refer to the fiscal year ending December 31, 2021.</p></body></html>')
        r=self.resolve(raw=raw);self.assertEqual(r['selected_fiscal_year'],2022)
        self.assertEqual(r['original_dei_fiscal_year'],2021);self.assertTrue(r['metadata_conflict_retained'])
        self.assertEqual(r['basis'],'EXPLICIT_SOURCE_ISSUER_DEFINITION')
        self.assertTrue(r['source_inspection']['source_definitions'])

    def test_conflicting_explicit_definitions_cannot_be_resolved_by_metadata(self):
        raw=annual().replace(b'</body></html>',b'<p>Our fiscal year ends on December 31. References to fiscal 2022, for example, refer to the fiscal year ending December 31, 2021.</p><p>References to fiscal 2023, for example, refer to the fiscal year ending December 31, 2021.</p></body></html>')
        with self.assertRaisesRegex(ValueError,'FISCAL_LABEL_UNRESOLVED'):self.resolve(raw=raw)

    def test_conditional_and_hypothetical_examples_cannot_confirm_actual_year(self):
        examples = [
            'If the proposed naming convention is approved, References to fiscal 2022, for example, refer to the fiscal year ending December 31, 2021.',
            'The following is a hypothetical example, not our actual naming convention: "References to fiscal 2022, for example, refer to the fiscal year ending December 31, 2021."',
            'If the proposed naming convention is approved, Fiscal years 2022 and 2021 ended on December 31, 2021 and December 31, 2020, respectively, and included 52 weeks.',
        ]
        for example in examples:
            raw=annual().replace(b'</body></html>',('<p>Our fiscal year ends on December 31. '+example+'</p></body></html>').encode())
            with self.subTest(example=example),self.assertRaisesRegex(ValueError,'EXPLICIT_DEFINITION_UNRESOLVED'):
                self.resolve(raw=raw)

    def test_quoted_label_words_do_not_make_an_actual_definition_hypothetical(self):
        raw=annual(EntityRegistrantName='Example Stores').replace(b'</body></html>',b'<p>Unless the context requires otherwise, references to "Example Stores" or the "Company" are references to Example Stores and its subsidiaries. References to "2022" and "2021" are references to the Company\'s fiscal years ended December 31, 2021 and December 31, 2020, respectively.</p></body></html>')
        r=self.resolve(raw=raw)
        self.assertEqual(r['selected_fiscal_year'],2022)

    def test_prepared_historical_reader_uses_same_scope_without_changing_retained_scan(self):
        from vnext import historical_fiscal_labels as labels
        from vnext.historical_dei import release_aware
        from vnext import fiscal_year_labels
        raw=annual().replace(b'</body></html>',b'<p>Our fiscal year ends on December 31. If the proposed naming convention is approved, References to fiscal 2022, for example, refer to the fiscal year ending December 31, 2021.</p></body></html>')
        inspected=release_aware(fiscal_year_labels.inspect_fiscal_year_labels)(
            primary_bytes=raw,companyfacts_bytes=facts(),expected_primary_sha256=sha256_bytes(content=raw),
            expected_companyfacts_sha256=sha256_bytes(content=facts()),expected_cik='19617',filing=FILING)
        self.assertEqual(inspected['source_defined_fiscal_year'],2022)
        with patch.object(labels,'_frozen_inspection',return_value={'inspection':inspected}), \
             patch.object(labels,'resolve_repository_file',side_effect=AssertionError('No unnecessary second read')):
            report=labels.inspect_prepared_fiscal_year_labels(repo_root=None,prepared={})
        self.assertEqual(report['inspection']['status'],'EXPLICIT_DEFINITION_UNRESOLVED')
        self.assertIsNone(report['inspection']['source_defined_fiscal_year'])
        self.assertEqual(report['inspection']['rejected_non_actual_definitions'][0]['reason'],'DEFINITION_CONDITIONAL_NOT_ADOPTED')
        self.assertEqual(inspected['source_defined_fiscal_year'],2022)

    def test_hash_subject_and_same_accession_evidence_are_required(self):
        for change in [{'expected_primary_sha256':'0'*64},{'expected_companyfacts_sha256':'0'*64},{'expected_cik':'1'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.resolve(**change)
        with self.assertRaisesRegex(ValueError,'COMPANYFACTS_ENTITY_CONFLICT'):self.resolve(cf=facts(cik=1))
        with self.assertRaisesRegex(ValueError,'SAME_ACCESSION_COMPANYFACTS_MISSING'):self.resolve(cf=facts(accession='other'))

    def test_historical_release_is_controlled_and_fake_dei_is_not_admitted(self):
        for suffix in ['2021q4','2021-01-31','2021']:
            self.assertEqual(self.resolve(raw=annual('http://xbrl.sec.gov/dei/'+suffix))['selected_fiscal_year'],2021)
        with self.assertRaises(ValueError):self.resolve(raw=annual('https://example.org/dei/2021'))

class ExplicitHistoricalStatementSelectionTest(unittest.TestCase):
    def test_explicit_selection_skips_search_but_reaches_existing_annual_rebuild(self):
        from pathlib import Path
        from vnext import historical_statement_cases as case
        selected={'constructed_selection':True}
        with patch.object(case,'resolve_period_selection',side_effect=AssertionError('No second search')) as search, \
             patch.object(case,'prepare_historical_annual_input',side_effect=ValueError('Source rebuild marker')) as prepare:
            with self.assertRaisesRegex(ValueError,'Source rebuild marker'):
                case.prepare_historical_statement_year_case(repo_root=Path('/constructed'),company_id='sample',
                    metric_id='B01',fiscal_year=2025,period_selection=selected)
        search.assert_not_called();self.assertIs(prepare.call_args.kwargs['period_selection'],selected)

    def test_resolved_source_year_must_equal_requested_year_before_calculation(self):
        from pathlib import Path
        from vnext import historical_statement_cases as case
        with patch.object(case,'prepare_historical_annual_input',return_value={'table_input':{'target_period':{'fiscal_year':2024}}}), \
             patch.object(case,'installed_ordinary_spec_documents') as specs:
            with self.assertRaisesRegex(ValueError,'REQUESTED_FISCAL_YEAR_CHANGED'):
                case.prepare_historical_statement_year_case(repo_root=Path('/constructed'),company_id='sample',
                    metric_id='B02',fiscal_year=2025,period_selection={'constructed_selection':True})
        specs.assert_not_called()
