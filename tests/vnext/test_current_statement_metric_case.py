"""Current selection/dispatch controls; quantity and real originals are separate."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from vnext import current_statement_metric_case as current


class CurrentStatementMetricCaseTest(unittest.TestCase):
    def setUp(self):
        self.annual={'company_id':'sample','entity':'123','filing':{'accessionNumber':'selected',
            'form':'10-K','reportDate':'2026-01-31','filingDate':'2026-03-01','primaryDocument':'annual.htm'},
            'selection_rule':'LATEST_ORDINARY_PERIOD_IN_SAVED_SUBMISSIONS','input_id':'actual-current-id',
            'table_input':{'target_period':{'fiscal_year':2026,'period_start':'2025-02-01','period_end':'2026-01-31'}}}

    def run_case(self,metric='B04',transform=lambda value:value):
        case={'primary_metric_id':metric,'prepared_annual_input':deepcopy(self.annual),
            'target_period':deepcopy(self.annual['table_input']['target_period']),
            'input_binding':{'input_id':'unchanged-selected-case'},'input_assessments':{'existing':True}}
        case=transform(case)
        with patch.object(current,'repository_company_traits',return_value={'constructed_applicable':True}), \
             patch.object(current,'metric_is_applicable',return_value=True), \
             patch.object(current,'prepare_saved_annual_input',return_value=self.annual) as annual, \
             patch.object(current,'resolve_period_selection',side_effect=AssertionError('NO_HISTORY'),create=True) as select, \
             patch.object(current,'_prepare_historical_statement_case',return_value=case) as shared:
            result=current.prepare_current_statement_metric_case(source_root=Path('/saved'),
                company_id='sample',metric_id=metric)
        return result,annual,select,shared

    def test_source_issuer_year_and_exact_current_report_end_reach_the_same_core(self):
        result,annual,selection,shared=self.run_case()
        selection.assert_not_called()
        self.assertEqual(shared.call_args.kwargs['fiscal_year'],2026)
        self.assertIs(shared.call_args.kwargs['prepared_current_annual'],self.annual)
        self.assertNotIn('period_selection',shared.call_args.kwargs)
        self.assertTrue(shared.call_args.kwargs['withhold_known_source_errors'])
        self.assertEqual(result['input_binding'],{'input_id':'unchanged-selected-case'})
        self.assertTrue(result['input_assessments']['existing'])
        self.assertFalse(result['input_assessments']['current_statement_selection']['current_sec_freshness_verified'])

    def test_b07_uses_same_definition_and_other_metrics_cannot_enter(self):
        self.assertEqual(self.run_case('B07')[0]['primary_metric_id'],'B07')
        for metric in ('B01','B05','B06','B08'):
            with self.assertRaisesRegex(ValueError,'METRIC_NOT_SUPPORTED'):
                self.run_case(metric)

    def test_structural_applicability_never_requires_a_historical_catalog(self):
        from vnext import ordinary_saved_result as saved
        for metric in ('B04','B07'):
            expected={'primary_metric_id':metric,'results':{metric:{'applicability':'N_A_STRUCTURAL'}}}
            with self.subTest(metric=metric), \
                 patch.object(current,'repository_company_traits',return_value={'is_bank':True},create=True), \
                 patch.object(current,'metric_is_applicable',return_value=False,create=True), \
                 patch.object(current,'prepare_saved_annual_input',return_value=self.annual), \
                 patch.object(current,'resolve_period_selection',side_effect=AssertionError('IRRELEVANT_HISTORY'),create=True), \
                 patch.object(saved,'_ordinary_case',return_value=expected) as ordinary:
                self.assertEqual(current.prepare_current_statement_metric_case(
                    source_root=Path('/saved'),company_id='jpmorgan_chase',metric_id=metric),expected)
                ordinary.assert_called_once_with(Path('/saved'),'jpmorgan_chase',metric)

    def test_changed_period_entity_or_filing_cannot_replace_current_selection(self):
        def change_period(value):value['target_period']['fiscal_year']=2025;return value
        def change_entity(value):value['prepared_annual_input']['entity']='456';return value
        def change_filing(value):value['prepared_annual_input']['filing']['accessionNumber']='prior';return value
        for transform in (change_period,change_entity,change_filing):
            with self.subTest(transform=transform),self.assertRaisesRegex(ValueError,'SELECTED_SOURCE_CHANGED'):
                self.run_case(transform=transform)

    def test_unused_inventory_metadata_does_not_change_selected_filing_identity(self):
        self.annual['filing']['filmNumber']='metadata-only'
        def curated(value):value['prepared_annual_input']['filing'].pop('filmNumber');return value
        result,*_=self.run_case(transform=curated)
        self.assertEqual(result['input_assessments']['current_statement_selection']['filing']['filmNumber'],
                         'metadata-only')

    def test_prior_or_instant_catalog_component_cannot_enter_current_annual_case(self):
        original=current.strict_json_file
        def changed(*,path):
            value=deepcopy(original(path=path))
            value['metrics']['B07']['branches'][0]['components'][0]['period_role']='current_instant'
            return value
        with patch.object(current,'strict_json_file',side_effect=changed),self.assertRaisesRegex(
                ValueError,'SOURCE_ROLE_CHANGED'):
            self.run_case('B07')

    def test_ordinary_writer_selects_the_current_case_without_legacy_component_replay(self):
        from vnext import ordinary_saved_result as saved
        with patch.object(saved,'_ordinary_case',side_effect=AssertionError('No old component')), \
             patch.object(current,'prepare_current_statement_metric_case',return_value={'selected':True}) as prepare, \
             patch.object(saved,'_save_case',side_effect=lambda **kw:kw['factory'](Path('/saved'))):
            value=saved.create_saved_result(source_root=Path('/saved'),output_root=Path('/new'),
                company_id='sample',metric_id='B04')
        self.assertEqual(value,{'selected':True})
        prepare.assert_called_once_with(source_root=Path('/saved'),company_id='sample',metric_id='B04')

    def test_current_case_change_reprocesses_only_its_metrics_then_reuses(self):
        from tests.vnext import test_ordinary_current_update as fixture
        update=fixture.update
        configure=update._configuration
        state=fixture.CurrentUpdateTest();state.setUp()
        self.addCleanup(state.doCleanups)
        created=[]
        def create(**kwargs):
            metric=kwargs['metric_id'];path=kwargs['output_root'];path.mkdir(parents=True)
            created.append(metric)
            value={'manifest':{'company_id':'marriott_international','metric_id':metric,
                'source_proofs':[state.proof]},'result':{'company_id':'marriott_international',
                'metric_id':metric,'publication':'PUBLISHED','period_end':'2025-12-31',
                'result_id':metric+'-constructed-'+str(len(created))}}
            state.records[str(path)]=value
            return value
        def run(metric):
            return update.run_once(state_root=state.root/metric,source_root=fixture.ROOT,
                company_id='marriott_international',metric_id=metric)
        original_hash=update.sha256_file
        def changed(*,path):
            return 'changed-current-case' if Path(path).name=='current_statement_metric_case.py' else original_hash(path=path)
        with patch.object(update,'_configuration',side_effect=configure), \
             patch.object(update,'create_saved_result',side_effect=create):
            first={metric:run(metric) for metric in ('B04','B05','B07')}
            with patch.object(update,'sha256_file',side_effect=changed):
                second={metric:run(metric) for metric in ('B04','B05','B07')}
                self.assertTrue(second['B04']['calculation_performed'])
                self.assertTrue(second['B07']['calculation_performed'])
                self.assertEqual(second['B05']['status'],'NO_SOURCE_CONTENT_CHANGE')
                self.assertEqual(second['B05']['result_id'],first['B05']['result_id'])
                with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated calculation')):
                    repeated={metric:run(metric) for metric in ('B04','B05','B07')}
                self.assertTrue(all(not value['calculation_performed'] for value in repeated.values()))
        self.assertEqual(created,['B04','B05','B07','B04','B07'])
