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
            'subject_policy':{'mode':'CONTINUOUS_PRIMARY','selected_cik':'12345',
                              'cross_entity_combination_authorized':False},'amendments':[],'source_proofs':[]}

    def case(self, *, source=None, prepared=None, amendment_source=None, scopes=None):
        body=BODY.replace('<p>A supply constraint could affect production.</p>',
            '<p><b>Supply constraints may affect production</b>. Explanatory text is separate.</p>'
            '<p><span style="text-decoration:underline">Cybersecurity threats may affect operations</span>. A disclosure is not an occurrence.</p>')
        source=source or binding(annual(body));prepared=prepared or self.prepared()
        amended=amendment_source or source
        reader=SimpleNamespace(primary=lambda filing: amended if filing['form']=='10-K/A' else source,
            proofs={}, records={'blob':source['raw_blob'],'ref':source['source_reference'],
                              'amended_blob':amended['raw_blob'],'amended_ref':amended['source_reference']})
        with ExitStack() as stack:
            for name,value in {'resolve_period_selection':{},'prepare_historical_annual_input':prepared,
                    '_Sources':reader,'repository_company_traits':[], 'verify_ordinary_source_proofs':{}}.items():
                stack.enter_context(patch.object(cases,name,return_value=value))
            if scopes is not None:
                def inspect(**frames):
                    check=next(assessments)
                    if isinstance(check,Exception):raise check
                    check=copy.deepcopy(check)
                    for name in ('original','amendment'):
                        check[name].update(filing=frames[name]['filing'],
                                          source_reference=frames[name]['reference'])
                    return check
                assessments=iter(scopes)
                stack.enter_context(patch.object(cases,'inspect_risk_heading_amendment',side_effect=inspect))
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

    def test_unproven_subject_refuses_before_source_extraction(self):
        for change in ('wrong_subject','combined_subject','unknown_mode'):
            value=self.prepared()
            if change=='wrong_subject':value['subject_policy']['selected_cik']='54321'
            elif change=='combined_subject':value['subject_policy']['cross_entity_combination_authorized']=True
            else:value['subject_policy']['mode']='UNRESOLVED'
            with self.subTest(change=change), patch.object(cases,'resolve_period_selection',return_value={}), \
                    patch.object(cases,'prepare_historical_annual_input',return_value=value), \
                    patch.object(cases,'_Sources',side_effect=AssertionError('No source extraction')) as read:
                with self.assertRaisesRegex(ValueError,'SELECTED_SUBJECT_NOT_PROVEN'):
                    cases.prepare_historical_risk_heading_year_case(repo_root=Path('/constructed'),
                        company_id='sample_entity',metric_id='D01',fiscal_year=2025)
                read.assert_not_called()

    def scope(self, *, accession='0000012345-26-000002'):
        return {'scope_id':'constructed-control-only','company_id':'sample_entity','cik':'12345',
            'classification':'PART_III_ADDITION_WITH_NO_AMENDED_ITEM_1A',
            'decision':'INPUT_PROPERTY_PROVEN','issues':[],
            'input_class':cases.AMENDMENT_INPUT_CLASS,'metric_ids':['D01'],
            'fiscal_window_unchanged':True,
            'original':{'period':self.prepared()['table_input']['target_period']},
            'amendment':{'filing':{'accessionNumber':accession}},
            'source_scope':{'document':{'blocks':['full source only in assessments']}}}

    def test_unresolved_amendment_names_dependency_and_never_extracts_original(self):
        value=self.prepared();value['amendments']=[{'form':'10-K/A','accessionNumber':'0000012345-26-000002'}]
        check=self.scope();check.update(decision='WITHHELD',issues=[{'reason':'RISK_AMENDMENT_NEW_ITEM_1A_SECTION'}])
        with patch.object(cases.d01_emphasis_results,'create_deterministic_text_candidate',
                          side_effect=AssertionError('No extraction from unresolved input')) as extract:
            with self.assertRaisesRegex(ValueError,'AMENDMENT_SCOPE_UNRESOLVED:0000012345-26-000002:RISK_AMENDMENT_NEW_ITEM_1A_SECTION'):
                self.case(prepared=value,scopes=[check])
            extract.assert_not_called()

    def test_every_amendment_must_have_its_own_d01_period_and_subject_property(self):
        value=self.prepared();value['amendments']=[{'form':'10-K/A','accessionNumber':'0000012345-26-000002'},
            {'form':'10-K/A','accessionNumber':'0000012345-26-000003'}]
        for change in ('withheld','class','metric','cik','period','window'):
            bad=self.scope(accession='0000012345-26-000003')
            if change=='withheld':bad['decision']='WITHHELD'
            elif change=='class':bad['input_class']='FINANCIAL_INPUT'
            elif change=='metric':bad['metric_ids']=['B08']
            elif change=='cik':bad['cik']='54321'
            elif change=='period':bad['original']['period']['period_start']='2025-02-01'
            else:bad['fiscal_window_unchanged']=False
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'AMENDMENT_SCOPE_UNRESOLVED:0000012345-26-000003'):
                self.case(prepared=value,scopes=[self.scope(),bad])

    def test_proven_amendment_keeps_full_assessment_and_only_original_heading_evidence(self):
        value=self.prepared();value['amendments']=[{'form':'10-K/A','accessionNumber':'0000012345-26-000002'}]
        check=self.scope();amended=binding(annual('<p><b>Never use amendment title as original risk</b></p>',form='10-K/A'))
        amended['source_reference']['accession']='0000012345-26-000002'
        case=self.case(prepared=value,amendment_source=amended,scopes=[check])
        self.assertEqual(case['selection']['heading_count'],2)
        self.assertNotIn('Never use',case['results']['D01']['value'])
        self.assertEqual(case['input_assessments']['risk_heading_amendment_checks'][0]['scope_id'],check['scope_id'])
        self.assertEqual(case['input_binding']['risk_heading_amendment_checks'],
                         case['input_assessments']['risk_heading_amendment_checks'])
        self.assertNotIn('source_scope',case['selection']['risk_heading_amendment_checks'][0])
        self.assertEqual(len(case['references']),1)
        self.assertTrue(any(r.get('accession')=='0000012345-26-000002' for r in case['expected_records']))

    def test_shared_source_identity_error_propagates_before_heading_extraction(self):
        value=self.prepared();value['amendments']=[{'form':'10-K/A','accessionNumber':'0000012345-26-000002'}]
        with self.assertRaisesRegex(ValueError,'SOURCE_BYTES_CHANGED'):
            self.case(prepared=value,scopes=[ValueError('SOURCE_BYTES_CHANGED')])

    def test_scope_from_another_amendment_cannot_replace_the_selected_input(self):
        value=self.prepared();value['amendments']=[{'form':'10-K/A','accessionNumber':'0000012345-26-000002'}]
        check=self.scope();check['original']['filing']=value['filing']
        check['original']['source_reference']={};check['amendment']['source_reference']={}
        with patch.object(cases,'inspect_risk_heading_amendment',return_value=check):
            with self.assertRaisesRegex(ValueError,'AMENDMENT_SOURCE_BINDING_CHANGED'):
                self.case(prepared=value)

    def test_single_successor_source_does_not_combine_other_registrants_or_assert_events(self):
        value=self.prepared();value['subject_policy']['mode']='SUCCESSOR_REGISTRANT_ONLY'
        value['subject_policy']['related_predecessor_ciks']=['54321']
        case=self.case(prepared=value)
        self.assertEqual(case['results']['D01']['value_kind'],'TEXT_V1')
        self.assertFalse(case['selection']['risk_occurrence_asserted'])
        self.assertFalse(case['input_binding']['financial_cross_entity_combination_authorized'])
        self.assertEqual(case['input_binding']['heading_scope'],'SELECTED_REGISTRANT_ORIGINAL_ITEM_1A')

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

    def test_consumed_shared_functions_are_actual_declared_processing_dependencies(self):
        for name in ['d01_emphasis_results','d01_emphasis_source','text_coverage','text_results','risk_signals','text_review','review','historical_dei']:
            self.assertIn('scripts/vnext/'+name+'.py',cases.PROCESSING_FILES)
        self.assertTrue(set(cases.AMENDMENT_PROCESSING_FILES)<=set(cases.PROCESSING_FILES))
