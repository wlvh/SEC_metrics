"""Current borrowing route composition; full source arithmetic stays in existing tests."""
import unittest
from pathlib import Path
from unittest.mock import patch
from vnext import ordinary_saved_result as saved


class CurrentB06EntryTest(unittest.TestCase):
    def test_current_writer_accepts_b06_before_source_calculation(self):
        with patch.object(saved,'_save_case',return_value={'writer_selected':True}) as writer:
            answer=saved.create_saved_result(source_root=Path('/source'),output_root=Path('/new'),
                company_id='enphase_energy',metric_id='B06')
        self.assertTrue(answer['writer_selected'])
        self.assertEqual('B06',writer.call_args.kwargs['metric_id'])
        self.assertTrue(callable(writer.call_args.kwargs['factory']))



class CurrentB06CompositionTest(unittest.TestCase):
    def setUp(self):
        from vnext import current_b06_case as current
        self.current=current
        filing={'accessionNumber':'test-accession','reportDate':'2025-12-31','primaryDocument':'annual.htm'}
        self.annual={'company_id':'enphase_energy','entity':'1463101','filing':filing,
            'source_proofs':[],'table_input':{'target_period':{'fiscal_year':2025,
                'period_start':'2025-01-01','period_end':'2025-12-31'}}}
        self.packet={'decision':'INPUT_PROPERTY_PROVEN','prepared_input':self.annual,'checks':[]}
        self.preparation={'input_binding':{'prepared_annual_input':self.annual},'records':[]}
        self.case={'spec_paths':{'B06':'constructed'},'selection':{'status':'WITHHELD'},
                   'results':{'B06':{'publication':'WITHHELD'}}}

    def context(self,**more):
        from contextlib import ExitStack
        stack=ExitStack()
        values={'prepare_current_debt_input':self.packet,
                'prepare_saved_original_financial_sources':self.preparation,
                'prepare_saved_annual_input':self.annual}
        values.update(more)
        for name,value in values.items():stack.enter_context(patch.object(self.current,name,return_value=value))
        stack.enter_context(patch.object(self.current,'bind_current_debt_input',side_effect=lambda **kw:kw['case']))
        self.addCleanup(stack.close)
        return stack

    def test_unproven_amendment_never_enters_denominator_or_debt(self):
        self.packet['decision']='WITHHELD'
        self.context(withheld_current_debt_case=self.case)
        with patch.object(self.current,'prepare_current_guarded_b06_result',side_effect=AssertionError('guard must wait')) , \
             patch.object(self.current,'prepare_note_debt_case',side_effect=AssertionError('debt must wait')):
            result=self.current.prepare_current_b06_case(source_root=Path('/sources'),company_id='enphase_energy')
        self.assertEqual('WITHHELD',result['input_assessments']['B06']['current_input_decision'])

    def test_failed_matched_note_is_preserved_not_replaced_by_another_grammar(self):
        self.context(prepare_current_guarded_b06_result={'status':'CONTINUE_DEBT_PATH','reason_code':'DENOMINATOR_POSITIVE'},
                     prepare_note_debt_case=self.case)
        with patch.object(self.current,'prepare_bond_debt_case',side_effect=AssertionError('cannot replace matched failure')) , \
             patch.object(self.current,'_b06_resolution',side_effect=AssertionError('cannot bypass matched failure')):
            result=self.current.prepare_current_b06_case(source_root=Path('/sources'),company_id='enphase_energy')
        self.assertEqual(self.case['selection'],result['input_assessments']['B06']['selection'])

    def test_special_scope_cannot_fall_into_consolidated_grammars(self):
        self.context(prepare_current_guarded_b06_result={'status':'CONTINUE_DEBT_PATH','reason_code':'EXISTING_SPECIAL_SCOPE_REQUIRED'},
                     prepare_special_debt_case=None)
        with patch.object(self.current,'prepare_note_debt_case',side_effect=AssertionError('wrong scope')):
            with self.assertRaisesRegex(self.current.CurrentB06Error,'SEPARATE_BANK_OR_INDUSTRIAL'):
                self.current.prepare_current_b06_case(source_root=Path('/sources'),company_id='enphase_energy')

    def test_existing_guard_terminal_does_not_parse_debt(self):
        guard={'status':'NOT_MEANINGFUL','reason_code':'DENOMINATOR_NONPOSITIVE','spec_path':'constructed',
               'result':{},'trace':{},'observations':[],'equity_proof':{'value':'-1'}}
        self.context(prepare_current_guarded_b06_result=guard)
        with patch.object(self.current,'_case_from_resolution',return_value=self.case) as case , \
             patch.object(self.current,'prepare_note_debt_case',side_effect=AssertionError('unnecessary debt')):
            self.current.prepare_current_b06_case(source_root=Path('/sources'),company_id='enphase_energy')
        self.assertEqual('NOT_EVALUATED',case.call_args.kwargs['resolution']['selection']['debt_completeness'])

    def test_selected_source_conflict_precedes_debt(self):
        import copy
        annual=copy.deepcopy(self.annual);annual['entity']='1';self.context(prepare_saved_annual_input=annual)
        with patch.object(self.current,'prepare_current_guarded_b06_result',side_effect=AssertionError('subject mismatch')):
            with self.assertRaisesRegex(self.current.CurrentB06Error,'SELECTED_SOURCE_CHANGED'):
                self.current.prepare_current_b06_case(source_root=Path('/sources'),company_id='enphase_energy')

    def test_exact_fallback_callable_and_metric_specific_processing_dependencies(self):
        from vnext import normal_candidates,ordinary_b06_resolution,ordinary_current_update as update
        self.assertIs(normal_candidates._b06_resolution,ordinary_b06_resolution._b06_resolution)
        root=Path(self.current.ROOT)
        self.assertTrue(all((root/p).is_file() for p in self.current.PROCESSING_FILES))
        path='scripts/vnext/current_b06_case.py'
        income=update._configuration(root,'enphase_energy','B01')
        debt=update._configuration(root,'enphase_energy','B06')
        self.assertNotIn(path,income['processing_files']);self.assertIn(path,debt['processing_files'])
        original=update.sha256_file
        with patch.object(update,'sha256_file',side_effect=lambda **kw:'new-version' if kw['path'].name=='current_b06_case.py' else original(**kw)):
            self.assertEqual(income,update._configuration(root,'enphase_energy','B01'))
            self.assertNotEqual(debt,update._configuration(root,'enphase_energy','B06'))

    def test_full_audit_stays_out_of_daily_csv_selection(self):
        import csv,io,json
        selection={'classification':'SOURCE_RECONCILED_NOTE_CARRYING',
            'audit':{'branch':'BORROWING_CURRENT_NONCURRENT_NO_FINANCE_LEASE',
                     'debt':'100','equity':'50','debt_candidates':[{'source_text':'x'*180000}]}}
        displayed=self.current._display_selection(selection)
        target=io.StringIO();csv.DictWriter(target,fieldnames=['context_or_dimension']).writeheader()
        csv.DictWriter(target,fieldnames=['context_or_dimension']).writerow(
            {'context_or_dimension':json.dumps(displayed)})
        row=next(csv.DictReader(io.StringIO(target.getvalue())))
        self.assertEqual('100',json.loads(row['context_or_dimension'])['calculation']['debt'])
        self.assertLess(len(row['context_or_dimension']),1000)
        self.assertEqual(180000,len(selection['audit']['debt_candidates'][0]['source_text']))
        self.assertEqual(self.current.content_hash(value=selection),displayed['selection_detail_id'])

    def test_reported_interest_does_not_disappear_from_complete_component_claim(self):
        from tests.vnext.test_b06_guarded_result_v3 import synthetic
        original,_=synthetic(47000000)
        preparation={kind:{'raw_bytes':original[kind].replace(b'StockholdersEquity',b'InterestPayableCurrent'),
                           'source_reference':{'source_reference_id':'TEST_ONLY_'+kind}}
                     for kind in ('primary','xml')}
        annual={'entity':'1','filing':{'reportDate':'2025-12-31'}}
        rows=self.current._unresolved_current_interest(preparation,annual)
        self.assertEqual(['47000000','47000000'],[r['value'] for r in rows])
        self.assertEqual({'primary','xml'},{r['source_kind'] for r in rows})
        self.assertTrue(all(r['ordinal']>0 and r['context_ref']=='end' for r in rows))
        annual['filing']['reportDate']='2024-12-31'
        self.assertEqual([],self.current._unresolved_current_interest(preparation,annual))
        annual['filing']['reportDate']='2025-12-31';annual['entity']='2'
        self.assertEqual([],self.current._unresolved_current_interest(preparation,annual))

    def test_zero_or_tax_interest_is_not_a_positive_current_financing_relation(self):
        from tests.vnext.test_b06_guarded_result_v3 import synthetic
        annual={'entity':'1','filing':{'reportDate':'2025-12-31'}}
        for value,name in ((0,b'InterestPayableCurrent'),(47000000,b'IncomeTaxInterestPayable')):
            original,_=synthetic(value)
            preparation={kind:{'raw_bytes':original[kind].replace(b'StockholdersEquity',name),
                               'source_reference':{'source_reference_id':'TEST_ONLY_'+kind}}
                         for kind in ('primary','xml')}
            self.assertEqual([],self.current._unresolved_current_interest(preparation,annual))

class B06FallbackDependencyTest(unittest.TestCase):
    def test_both_public_fallback_exports_reach_financing_with_real_traits(self):
        """TEST_ONLY proposal/facts isolate runtime dependencies, not business credit."""
        from types import SimpleNamespace
        from vnext import normal_candidates, ordinary_b06_resolution
        from vnext import b06_disclosure_v2 as disclosure, r5_b06_scope, sources
        from vnext.traits import repository_company_traits
        root=Path(__file__).resolve().parents[2]
        prepared={'company_id':'salesforce','entity':'1108524',
            'filing':{'accessionNumber':'TEST_ONLY_FALLBACK','filingDate':'2026-03-01'},
            'table_input':{'target_period':{'period_end':'2026-01-31'}}}
        preparation={'input_binding':{'prepared_annual_input':prepared},
            'xml':{'raw_bytes':b'TEST_ONLY_XML','source_reference':{}},
            'primary':{'raw_bytes':b'TEST_ONLY_PRIMARY'},
            'facts':{'raw_bytes':b'TEST_ONLY_FACTS','source_reference':{}}}
        marker={'test_only':'runtime reached'}
        for resolver in (ordinary_b06_resolution._b06_resolution,normal_candidates._b06_resolution):
            with self.subTest(export=resolver.__module__), \
                 patch.object(disclosure.prior,'parse_accession_xbrl_source',return_value=SimpleNamespace(contexts={})), \
                 patch.object(disclosure,'propose',return_value={}), \
                 patch.object(disclosure,'verify',return_value={}), \
                 patch.object(sources,'companyfacts_structured_facts',return_value=[]), \
                 patch.object(r5_b06_scope,'resolve_financing',return_value=(marker,{},[],{})) as calculation:
                path,answer=resolver(data_root=root,preparation=preparation)
                self.assertEqual(disclosure.SPEC_PATH,path)
                self.assertIs(marker,answer['result'])
                calculation.assert_called_once()
                self.assertEqual(repository_company_traits(repo_root=root,company_id='salesforce'),
                                 calculation.call_args.kwargs['traits'])
                self.assertEqual('1108524',calculation.call_args.kwargs['target']['entity'])


if __name__=='__main__':unittest.main()
