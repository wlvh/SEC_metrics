"""Selected-period D01 controls; constructed excerpts are not business results."""
import copy
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.vnext.test_text_coverage import annual, binding, BODY
from vnext import historical_risk_heading_case as cases


class HistoricalRiskHeadingCaseTest(unittest.TestCase):
    def prepared(self):
        return {'company_id':'sample_entity','entity':'12345',
            'filing':{'form':'10-K','accessionNumber':'0000012345-26-000001','primaryDocument':'source.htm',
                      'reportDate':'2025-12-31','filingDate':'2026-02-01'},
            'table_input':{'target_period':{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'}},
            'subject_policy':{'mode':'CONTINUOUS_PRIMARY'},'amendments':[],'source_proofs':[]}

    def case(self, *, source=None, prepared=None):
        body=BODY.replace('<p>A supply constraint could affect production.</p>',
            '<p><b>Supply constraints may affect production</b>. Explanatory text is separate.</p>'
            '<p><span style="text-decoration:underline">Cybersecurity threats may affect operations</span>. A disclosure is not an occurrence.</p>')
        source=source or binding(annual(body));prepared=prepared or self.prepared()
        reader=SimpleNamespace(primary=lambda *args:source, proofs={}, records={
            'blob':source['raw_blob'],'ref':source['source_reference']})
        with ExitStack() as stack:
            for name,value in {'resolve_period_selection':{},'prepare_historical_annual_input':prepared,
                    '_Sources':reader,'repository_company_traits':[], 'verify_ordinary_source_proofs':{}}.items():
                stack.enter_context(patch.object(cases,name,return_value=value))
            return cases.prepare_historical_risk_heading_year_case(repo_root=Path('/constructed'),
                company_id='sample_entity',metric_id='D01',fiscal_year=2025)

    def test_shared_d01_keeps_all_emphasized_excerpts_and_source_locators(self):
        value=self.case();result=value['results']['D01']
        self.assertEqual(result['value'],'Supply constraints may affect production\nCybersecurity threats may affect operations')
        self.assertEqual(value['selection']['heading_count'],2)
        self.assertFalse(value['selection']['risk_occurrence_asserted'])
        self.assertEqual(result['period_start'],'2025-01-01');self.assertEqual(result['period_end'],'2025-12-31')
        self.assertEqual(result['quality'],'EXACT')
        self.assertEqual(result['value_kind'],'TEXT_V1')
        observations=[r for r in value['expected_records'] if r['record_type']=='VERIFIED_OBSERVATION']
        self.assertEqual(len(observations),2)
        self.assertTrue(all(o['source_binding']['source_reference_id']==value['references'][0]['source_reference_id']
                            for o in observations))

    def test_unsupported_metric_does_not_prepare_an_annual_source(self):
        with patch.object(cases,'resolve_period_selection') as select:
            with self.assertRaisesRegex(ValueError,'METRIC_NOT_SUPPORTED'):
                cases.prepare_historical_risk_heading_year_case(repo_root=Path('/constructed'),
                    company_id='sample_entity',metric_id='D02',fiscal_year=2025)
        select.assert_not_called()

    def test_unreceived_amendment_and_successor_refuse_before_source_extraction(self):
        for change in ('amendment','successor'):
            value=self.prepared()
            if change=='amendment':value['amendments']=[{'form':'10-K/A'}]
            else:value['subject_policy']['mode']='SUCCESSOR_REGISTRANT_ONLY'
            with self.subTest(change=change), patch.object(cases,'resolve_period_selection',return_value={}), \
                    patch.object(cases,'prepare_historical_annual_input',return_value=value), \
                    patch.object(cases,'_Sources',side_effect=AssertionError('No source extraction')) as read:
                with self.assertRaisesRegex(ValueError,'AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED'):
                    cases.prepare_historical_risk_heading_year_case(repo_root=Path('/constructed'),
                        company_id='sample_entity',metric_id='D01',fiscal_year=2025)
                read.assert_not_called()

    def test_original_and_resolved_annual_dates_cannot_diverge(self):
        value=self.prepared();value['original_input']=copy.deepcopy(value)
        value['original_input']['table_input']['target_period']['period_start']='2025-02-01'
        with self.assertRaisesRegex(ValueError,'ORIGINAL_PERIOD_CHANGED'):self.case(prepared=value)

    def test_wrong_original_entity_and_missing_item1a_do_not_create_text(self):
        for raw in (annual(BODY,cik='54321'),annual(BODY.replace('Item 1A. Risk Factors','Appendix Risks'))):
            with self.subTest(raw=raw[-100:]),self.assertRaises(ValueError):self.case(source=binding(raw))

    def test_explicit_historical_namespace_view_cannot_admit_fake_dei_uri(self):
        raw=annual(BODY).replace(b'http://xbrl.sec.gov/dei/2025',b'https://example.org/dei/2025')
        with self.assertRaises(ValueError):self.case(source=binding(raw))

    def test_capacity_successor_keeps_the_complete_source_set_only_above_old_count(self):
        for count in (64,65,68,128,129):
            text=''.join('<p><b>Source risk heading '+str(i)+'</b>. Explanation.</p>' for i in range(count))
            raw=annual(BODY.replace('<p>A supply constraint could affect production.</p>',text))
            with self.subTest(count=count):
                if count>128:
                    with self.assertRaisesRegex(ValueError,'DETERMINISTIC_TEXT_HEADINGS_EXCEED_BOUND'):
                        self.case(source=binding(raw))
                    continue
                case=self.case(source=binding(raw))
                self.assertEqual(case['selection']['heading_count'],count)
                self.assertEqual(case['results']['D01']['value'].splitlines(),
                                 ['Source risk heading '+str(i) for i in range(count)])
                renderer='ORDERED_NEWLINE_V1' if count==64 else 'ORDERED_NEWLINE_128_V2'
                self.assertEqual(case['results']['D01']['text_payload']['renderer'],renderer)
                self.assertEqual(case['spec_paths']['D01'],
                                 cases.SPEC_PATH if count==64 else cases.CAPACITY_SPEC_PATH)

    def test_source_and_character_failures_are_not_capacity_fallback(self):
        raw=annual(BODY.replace('<p>A supply constraint could affect production.</p>',
            '<p><b>'+('A'*64001)+'</b></p>'))
        with self.assertRaisesRegex(ValueError,'DETERMINISTIC_TEXT_CONTENT_EXCEEDS_BOUND'):
            self.case(source=binding(raw))
        with patch.object(cases.d01_emphasis_results,'create_deterministic_text_candidate',
                          side_effect=ValueError('TEXT_SOURCE_IDENTITY_CHANGED')):
            with self.assertRaisesRegex(ValueError,'TEXT_SOURCE_IDENTITY_CHANGED'):
                self.case()

    def test_consumed_shared_functions_are_actual_declared_processing_dependencies(self):
        for name in ['d01_emphasis_results','d01_emphasis_source','text_coverage','text_results','risk_signals','text_review','review','historical_dei']:
            self.assertIn('scripts/vnext/'+name+'.py',cases.PROCESSING_FILES)
        self.assertIn(cases.CAPACITY_SPEC_PATH,cases.PROCESSING_FILES)
        self.assertIn('scripts/vnext/text_rendering_limits.py',cases.PROCESSING_FILES)
