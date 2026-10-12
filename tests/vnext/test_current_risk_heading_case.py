"""Small current D01 adapter controls; source doubles are not content acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import BODY, annual, binding
from tests.vnext.test_text_results import source_arguments
from vnext import current_risk_heading_case as current
from vnext import d01_emphasis_results as api
from vnext import ordinary_current_update as update
from vnext import company_current_records as company
from vnext.specs import compile_spec_file
from vnext.canonical import content_hash


class CurrentRiskHeadingCaseTest(unittest.TestCase):
    def args(self, count):
        raw=annual(BODY.replace('<p>A supply constraint could affect production.</p>',
            ''.join('<p><b>Risk number %s</b>. Explanation.</p>'%i for i in range(count))))
        args=source_arguments(binding(raw))
        args['compiled_spec']=compile_spec_file(path=REPO_ROOT/current.SPEC_PATH, dependency_specs={})
        scope=args['compiled_spec']['compiled']['required_claims']
        args['target'].update(scope=scope, scope_key=content_hash(value=scope))
        args['d01_emphasis_policy']=api.RUNNING_HEADER_POLICY
        return args

    def test_old_capacity_is_kept_and_only_true_overflow_uses_successor(self):
        for count,path in ((2,current.SPEC_PATH),(64,current.SPEC_PATH),(68,current.CAPACITY_SPEC_PATH),(128,current.CAPACITY_SPEC_PATH)):
            with self.subTest(count=count):
                args=self.args(count);candidate,used=current._candidate(api,args,REPO_ROOT)
                self.assertEqual(used,path);self.assertEqual(len(candidate['selected']),count)
                api.build_text_evidence(candidate=candidate,**args)

    def test_zero_and_129_never_become_partial_results(self):
        for count in (0,129):
            with self.subTest(count=count),self.assertRaises(ValueError):
                current._candidate(api,self.args(count),REPO_ROOT)

    def test_source_error_does_not_enter_capacity_fallback(self):
        args=self.args(2);args['target']['entity']='54321'
        with patch('vnext.specs.compile_spec_file') as unused:
            with self.assertRaisesRegex(ValueError,'filing identity differs'):
                current._candidate(api,args,REPO_ROOT)
            unused.assert_not_called()

    def test_changed_successor_scope_is_refused(self):
        successor=compile_spec_file(path=REPO_ROOT/current.CAPACITY_SPEC_PATH,dependency_specs={})
        successor['compiled']['required_claims']['extra']='Changed business scope'
        args=self.args(68)
        with patch('vnext.specs.compile_spec_file',return_value=successor):
            with self.assertRaisesRegex(ValueError,'CAPACITY_SEMANTICS_CHANGED'):
                current._candidate(api,args,REPO_ROOT)

    def test_complete_factory_uses_source_heading_and_current_period(self):
        args=self.args(2);ref=args['source_references'][0];blob=next(iter(args['raw_blobs'].values()))
        prepared={'entity':'12345','filing':{'accessionNumber':ref['accession']},'amendments':[],
            'subject_policy':{'mode':'CONTINUOUS_PRIMARY'},'source_proofs':[],
            'table_input':{'target_period':{'period_start':'2025-01-01','period_end':'2025-12-31','fiscal_year':2025}}}
        class Reader:
            def __init__(self,*args):self.records={'blob':blob,'ref':ref};self.proofs={}
            def primary(self,filing):return {'source_reference':ref,'raw_blob':blob,'raw_bytes':next(iter(args['raw_bytes_by_id'].values()))}
        with patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',return_value=prepared),\
             patch('vnext.normal_governance_input._Sources',Reader),\
             patch('vnext.traits.repository_company_traits',return_value=[]),\
             patch('vnext.ordinary_source_authority.verify_ordinary_source_proofs',return_value={'test_only':True}):
            case=current.prepare_current_risk_heading_case(repo_root=REPO_ROOT,company_id='sample_entity',metric_id='D01')
            self.assertEqual(case['results']['D01']['value'],'Risk number 0\nRisk number 1')
            self.assertEqual(case['target_period']['fiscal_year'],2025)
            self.assertEqual(case['selection']['heading_count'],2)
            self.assertFalse(case['selection']['risk_occurrence_asserted'])
            for changed in ({'amendments':[{'form':'10-K/A'}]}, {'subject_policy':{'mode':'SUCCESSOR'}}):
                with patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',return_value={**prepared,**changed}),self.assertRaisesRegex(current.CurrentRiskHeadingError,'NOT_RECEIVED'):
                    current.prepare_current_risk_heading_case(repo_root=REPO_ROOT,company_id='sample_entity',metric_id='D01')

    def test_cli_selects_current_d01_without_opening_shared_default(self):
        from vnext.company_local import run_local
        with patch.object(company,'run_saved_company',return_value={'test_only':True}) as run:
            run_local(company_id='enphase_energy',source_root=REPO_ROOT,work_dir='/tmp/d01-work',
                output_dir='/tmp/d01-output',metric_ids=['D01'])
            self.assertIs(run.call_args.kwargs['current_case_factories']['D01'],current.prepare_current_risk_heading_case)
            self.assertEqual(run.call_args.kwargs['processing_files_by_metric']['D01'],current.PROCESSING_FILES)
        with patch.object(company,'run_saved_company',return_value={}) as run:
            current.run_current_saved_company(company_id='enphase_energy',source_root=REPO_ROOT,
                work_dir='/tmp/work',output_dir='/tmp/out',metric_ids=['B01'])
            self.assertNotIn('current_case_factories',run.call_args.kwargs)

    def test_current_factory_is_incompatible_with_historical_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'CURRENT_FACTORY_SCOPE_INVALID'):
                update.run_once(state_root=Path(temp)/'state',source_root=REPO_ROOT,
                    company_id='enphase_energy',metric_id='D01',fiscal_year=2024,
                    case_factory=current.prepare_current_risk_heading_case,
                    current_case_factory=current.prepare_current_risk_heading_case)

    def test_consumed_fiscal_parser_and_policy_change_reprocess_once(self):
        """Real config hashes; small source/record doubles isolate the controller."""
        original_hash=update.sha256_file
        for relative in ('scripts/vnext/text_results_v2.py','catalog/r6/text_results_v2_policy.json'):
            with self.subTest(dependency=relative),tempfile.TemporaryDirectory() as folder:
                calls=[];records={}
                def factory(**kwargs):calls.append(kwargs);return {'test_only':True}
                def save(**kwargs):
                    path=kwargs['output_root'];path.mkdir(parents=True)
                    record={'manifest':{'company_id':'enphase_energy','metric_id':'D01','source_proofs':[]},
                        'result':{'company_id':'enphase_energy','metric_id':'D01','publication':'PUBLISHED',
                                  'period_end':'2025-12-31','result_id':'test-only-'+str(len(calls))}}
                    records[str(path)]=record;return record
                args=dict(state_root=Path(folder)/'state',source_root=REPO_ROOT,
                    company_id='enphase_energy',metric_id='D01',current_case_factory=factory,
                    processing_files=current.PROCESSING_FILES)
                with patch.object(update,'_source_census',return_value=[]),\
                     patch.object(update,'_current_sources',return_value=[]),\
                     patch.object(update,'save_calculated_case',side_effect=save),\
                     patch.object(update,'read_saved_result',side_effect=lambda **kw:records[str(kw['output_root'])]):
                    first=update.run_once(**args)
                    def changed(*,path):
                        return 'changed-consumed-rule' if path==REPO_ROOT/relative else original_hash(path=path)
                    with patch.object(update,'sha256_file',side_effect=changed):
                        second=update.run_once(**args)
                        with patch.object(update,'save_calculated_case',side_effect=AssertionError('No third save')):
                            again=update.run_once(**args)
                    self.assertEqual(first['status'],'CANDIDATE_READY')
                    self.assertEqual(second['status'],'CANDIDATE_READY')
                    self.assertNotEqual(first['version'],second['version'])
                    self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
                    self.assertEqual(len(calls),2)
                    self.assertTrue((Path(folder)/'state/results'/first['version']).is_dir())


class CurrentD01ProcessingInputUnionTest(unittest.TestCase):
    def test_current_factory_and_saved_input_reach_the_same_update(self):
        from tests.vnext.test_company_current_records import CurrentCompanyTest
        control=CurrentCompanyTest(methodName='runTest');control.setUp()
        try:
            package=control.source/'TEST_ONLY_saved_processing_input.json'
            package.write_text('{}')
            def factory(**kwargs):return {'TEST_ONLY':True}
            with patch.object(company,'run_once',return_value={
                    'status':'INPUT_OR_EXECUTION_FAILED','reason':'TEST_ONLY_UNION_BOUNDARY'}) as boundary:
                report=company.run_saved_company(company_id='marriott_international',
                    source_root=control.source,work_dir=control.work,output_dir=control.outputs,
                    metric_ids=['D01'],current_case_factories={'D01':factory},
                    processing_files_by_metric={'D01':current.PROCESSING_FILES},
                    processing_inputs_by_metric={'D01':(package,)})
            boundary.assert_called_once()
            self.assertIs(boundary.call_args.kwargs['current_case_factory'],factory)
            self.assertEqual(boundary.call_args.kwargs['processing_inputs'],(package,))
            self.assertEqual(report['metrics'][0]['reason'],'TEST_ONLY_UNION_BOUNDARY')
        finally:control.doCleanups()

    def test_current_factory_retains_and_reacts_to_its_saved_processing_input(self):
        # Small controller records isolate the merge seam, not content credit.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);package=root/'TEST_ONLY_input.json';package.write_text('first')
            calls=[];records={}
            def factory(**kwargs):calls.append(kwargs);return {'TEST_ONLY':True}
            def save(**kwargs):
                path=kwargs['output_root'];path.mkdir(parents=True)
                record={'manifest':{'company_id':'enphase_energy','metric_id':'D01','source_proofs':[]},
                    'result':{'company_id':'enphase_energy','metric_id':'D01','publication':'PUBLISHED',
                              'period_end':'2025-12-31','result_id':'TEST_ONLY_'+str(len(calls))}}
                records[str(path)]=record;return record
            args=dict(state_root=root/'state',source_root=REPO_ROOT,company_id='enphase_energy',
                metric_id='D01',current_case_factory=factory,processing_files=current.PROCESSING_FILES,
                processing_inputs=(package,))
            with (patch.object(update,'_source_census',return_value=[]),
                  patch.object(update,'_current_sources',return_value=[]),
                  patch.object(update,'save_calculated_case',side_effect=save),
                  patch.object(update,'read_saved_result',side_effect=lambda **kwargs:records[str(kwargs['output_root'])])):
                first=update.run_once(**args);package.write_text('changed input')
                second=update.run_once(**args)
                with patch.object(update,'save_calculated_case',side_effect=AssertionError('No repeated save')):
                    third=update.run_once(**args)
            self.assertEqual(first['status'],'CANDIDATE_READY')
            self.assertEqual(second['status'],'CANDIDATE_READY')
            self.assertNotEqual(first['version'],second['version'])
            self.assertEqual(third['status'],'NO_SOURCE_CONTENT_CHANGE')
            self.assertEqual(len(calls),2)


class DefaultCurrentConfigurationPreservationTest(unittest.TestCase):
    def test_default_producer_context_keeps_main_and_dependency_changes_are_explicit(self):
        # Same actual program inputs: file version hashes remain real. This
        # does not assert unchanged hashes across two different code trees.
        baseline=(REPO_ROOT/'tests/fixtures/current_configuration_main_2f.py.txt').read_text()
        namespace=dict(update.__dict__)
        exec(compile(baseline,'reference-main-configuration','exec'),namespace)
        for metric in ('B01','B02','D04','C04','A13'):
            with self.subTest(metric=metric):
                expected=namespace['_configuration'](REPO_ROOT,'marriott_international',metric)
                actual=update._configuration(REPO_ROOT,'marriott_international',metric)
                self.assertEqual({k:v for k,v in expected.items() if k!='processing_files'},
                    {k:v for k,v in actual.items() if k!='processing_files'})
                added=set(actual['processing_files'])-set(expected['processing_files'])
                self.assertTrue(added <= {'scripts/vnext/text_coverage.py',
                    'scripts/vnext/normal_governance_input.py','scripts/vnext/text_results_v2.py',
                    'scripts/vnext/historical_dei.py','scripts/vnext/batch_workflow.py',
                    'scripts/vnext/constraints.py','scripts/vnext/paired_measure_v1.py'})
                self.assertTrue(set(expected['processing_files']) <= set(actual['processing_files']))
                self.assertTrue(all(actual['processing_files'][path]==digest
                    for path,digest in expected['processing_files'].items()))
                self.assertNotIn('current_case_producer',actual)
                self.assertNotIn('saved_processing_inputs',actual)

    def test_omitted_and_explicit_empty_options_keep_completed_configuration(self):
        import json
        from tests.vnext.test_ordinary_current_update import CurrentUpdateTest
        control=CurrentUpdateTest(methodName='runTest');control.setUp()
        try:
            first=control.run_update()
            saved=(control.root/'completed-check.json').read_bytes()
            again=control.run_update()
            from scripts.vnext import ordinary_current_update as test_update
            third=test_update.run_once(state_root=control.root,source_root=REPO_ROOT,
                company_id='marriott_international',metric_id='B01',
                current_case_factory=None,processing_inputs=())
            self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
            self.assertEqual(third['status'],'NO_SOURCE_CONTENT_CHANGE')
            self.assertEqual((control.root/'completed-check.json').read_bytes(),saved)
            config=json.loads(saved)['configuration']
            self.assertNotIn('current_case_producer',config)
            self.assertNotIn('saved_processing_inputs',config)
            self.assertEqual(control.calculations,1)
        finally:control.doCleanups()


if __name__=='__main__':unittest.main()
