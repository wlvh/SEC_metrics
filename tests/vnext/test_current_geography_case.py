"""Current A13 wiring/defaults/dependencies; real bank source is separate evidence."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from tests.vnext.common import REPO_ROOT
from vnext import current_geography_case as geography,ordinary_saved_result as saved
from vnext import ordinary_current_update as update,ordinary_financial_results as financial


class CurrentGeographyCaseTest(TestCase):
    def fixture(self):
        return {'target_period':{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'},
            'result':{'result_id':'constructed','value':'100'},'trace':{},'compiled_spec':{},
            'spec_path':'catalog/r4_normal/A13_geographic_exposure.md','input_binding':{},
            'source_references':[],'source_proofs':[],'source_admission':{},'records':[],
            'prepared_input':{'selected':True},'selection':{'source_semantics_passed':True},
            'source_fact':{'outcome':'SOURCE_SEMANTICS_UNRESOLVED','regional_sum_used':False,'selected':[],'full':True}}

    def test_current_wrapper_uses_existing_resolver_and_installed_rules(self):
        value=self.fixture()
        with patch.object(geography,'resolve_current_financial_metric',return_value=value) as core:
            case=geography.prepare_current_geography_case(source_root=Path('/sources'),company_id='selected')
        core.assert_called_once_with(repo_root=Path('/sources'),company_id='selected',metric_id='A13',rules_root=geography.ROOT)
        self.assertEqual(case['expected_records'],value['records'])
        self.assertEqual(case['input_assessments']['current_geography']['source_fact'],value['source_fact'])
        self.assertEqual(case['results']['A13'],value['result'])
        self.assertNotIn('source_fact',case['selection'])
        self.assertEqual(case['selection']['source_summary']['selected'],[])

    def test_writer_dispatches_without_zero_ai_graph(self):
        with patch.object(saved,'_save_case',side_effect=lambda **kw:kw['factory'](Path('/sources'))), \
             patch.object(geography,'prepare_current_geography_case',return_value={'route':'currentA13'}) as core, \
             patch.object(saved,'_ordinary_case',side_effect=AssertionError('Wrong zeroAI family')):
            value=saved.create_saved_result(source_root=Path('/sources'),output_root=Path('/new'),company_id='selected',metric_id='A13')
        self.assertEqual(value,{'route':'currentA13'});core.assert_called_once()

    def test_wrapper_rule_changes_only_a13_configuration(self):
        original=update.sha256_file;before={m:update._configuration(REPO_ROOT,'jpmorgan_chase',m) for m in ('B01','A13')}
        with patch.object(update,'sha256_file',side_effect=lambda *,path:
            'changed-current-geography' if path==REPO_ROOT/'scripts/vnext/current_geography_case.py' else original(path=path)):
            after={m:update._configuration(REPO_ROOT,'jpmorgan_chase',m) for m in before}
        self.assertEqual(before['B01'],after['B01']);self.assertNotEqual(before['A13'],after['A13'])

    def test_default_financial_source_reader_retains_old_annual_entry(self):
        with patch.object(financial,'prepare_saved_annual_input',side_effect=ValueError('CONTROL_OLD_ANNUAL')) as old:
            with self.assertRaisesRegex(ValueError,'CONTROL_OLD_ANNUAL'):
                financial._ordinary_sources(repo_root=Path('/sources'),company_id='selected')
        old.assert_called_once_with(repo_root=Path('/sources'),company_id='selected')

    def test_explicit_program_rules_choose_current_fiscal_label_without_old_prepare(self):
        with patch.object(financial,'prepare_saved_annual_input',side_effect=AssertionError('No original-only label')) , \
             patch('vnext.normal_annual_input_v2.prepare_saved_annual_input',side_effect=ValueError('CONTROL_LABELLED_ANNUAL')) as labelled:
            with self.assertRaisesRegex(ValueError,'CONTROL_LABELLED_ANNUAL'):
                financial._ordinary_sources(repo_root=Path('/sources'),company_id='selected',ordinary_registered=True)
        labelled.assert_called_once_with(repo_root=Path('/sources'),company_id='selected',ordinary_registered=True)
