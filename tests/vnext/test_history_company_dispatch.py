"""Small selected-year dispatch controls; financial checks use saved sources."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from tools.vnext_company import main
from vnext import company_local as local


class HistoryCompanyDispatchTest(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_history(self, **changes):
        args = dict(company_id='marriott_international', source_root=self.root/'source',
            work_dir=self.root/'state', output_dir=self.root/'outputs', metric_ids=['B10', 'B11'],
            period='fiscal-years', fiscal_year_start=2024, fiscal_year_end=2025)
        return local.run_local(**{**args, **changes})

    def test_range_uses_one_public_company_controller_and_existing_case(self):
        from vnext.historical_lodging_results import prepare_historical_lodging_year_case
        with (patch('vnext.company_current_records.run_saved_company', return_value={}) as shared,
              patch.object(local, 'prepare_program',
                  side_effect=AssertionError('Saved history must not install a native program'))):
            self.run_history()
        args = shared.call_args.kwargs
        self.assertEqual([2024, 2025], args['fiscal_years'])
        self.assertIs(prepare_historical_lodging_year_case, args['case_factory'])
        self.assertEqual(['B10', 'B11'], args['metric_ids'])
        self.assertFalse((self.root/'state').exists())

    def test_invalid_range_rejects_before_source_or_writes(self):
        for start, end in [(2025, 2024), (2020, 2025), (True, 2024), (None, 2025)]:
            with self.subTest(start=start, end=end):
                with self.assertRaisesRegex(ValueError, 'FISCAL_RANGE_INVALID'):
                    self.run_history(fiscal_year_start=start, fiscal_year_end=end)
        self.assertFalse((self.root/'outputs').exists())

    def test_missing_source_is_explicit_and_does_not_acquire(self):
        with patch.object(local, '_invoke', side_effect=AssertionError('No acquisition')):
            with self.assertRaisesRegex(ValueError, 'PREPARED_SOURCE_REQUIRED'):
                self.run_history(source_root=None)

    def test_unsupported_family_uses_no_fabricated_historical_case(self):
        with patch('vnext.company_current_records.run_saved_company') as shared:
            with self.assertRaisesRegex(ValueError, 'SAVED_FAMILY_NOT_IMPLEMENTED'):
                self.run_history(metric_ids=['D03'])
        shared.assert_not_called()

    def test_statement_pilot_uses_original_per_metric_factories_and_dependencies(self):
        from vnext.historical_statement_cases import prepare_historical_statement_year_case, PROCESSING_FILES, INCOME_PROCESSING_FILES
        with patch('vnext.company_current_records.run_saved_company', return_value={}) as shared:
            self.run_history(company_id='macys', metric_ids=['B01', 'B02', 'B04', 'B05'],
                             fiscal_year_start=2021, fiscal_year_end=2025)
        args = shared.call_args.kwargs
        self.assertEqual([2021, 2022, 2023, 2024, 2025], args['fiscal_years'])
        self.assertNotIn('case_factory', args)
        self.assertTrue(all(f is prepare_historical_statement_year_case for f in args['case_factories'].values()))
        self.assertEqual(INCOME_PROCESSING_FILES, args['processing_files_by_metric']['B01'])
        for metric in ['B02', 'B04', 'B05']:
            self.assertEqual(PROCESSING_FILES, args['processing_files_by_metric'][metric])
        self.assertIn('scripts/vnext/selected_income_source_v1.py', INCOME_PROCESSING_FILES)
        self.assertNotIn('scripts/vnext/selected_income_source_v1.py', PROCESSING_FILES)
        self.assertFalse((self.root/'state').exists())

    def test_mixed_lodging_keeps_its_previous_factory_and_tuple(self):
        from vnext.historical_lodging_results import prepare_historical_lodging_year_case, HISTORICAL_LODGING_PROCESSING_FILES
        from vnext.historical_statement_cases import prepare_historical_statement_year_case
        with patch('vnext.company_current_records.run_saved_company', return_value={}) as shared:
            self.run_history(metric_ids=['B01', 'B10', 'B11'])
        args = shared.call_args.kwargs
        self.assertIs(prepare_historical_statement_year_case, args['case_factories']['B01'])
        for metric in ['B10', 'B11']:
            self.assertIs(prepare_historical_lodging_year_case, args['case_factories'][metric])
            self.assertEqual(HISTORICAL_LODGING_PROCESSING_FILES, args['processing_files_by_metric'][metric])
        self.assertFalse((self.root/'outputs').exists())

    def test_current_mode_keeps_the_existing_public_route(self):
        with patch('vnext.company_current_records.run_saved_company', return_value={}) as shared:
            self.run_history(period='latest-complete-fy', fiscal_year_start=None, fiscal_year_end=None)
        self.assertNotIn('fiscal_years', shared.call_args.kwargs)
        self.assertNotIn('case_factory', shared.call_args.kwargs)
        with self.assertRaisesRegex(ValueError, 'HISTORY_ARGUMENTS_REQUIRE'):
            self.run_history(period='latest-complete-fy')

    def test_cli_passes_period_arguments_to_the_same_company_entry(self):
        with (patch.object(local, 'run_local', return_value={'status': 'FLOW_COMPLETED'}) as selected,
              patch('sys.stdout')):
            self.assertEqual(0, main(['run', '--company', 'marriott_international',
                '--period', 'fiscal-years', '--fiscal-year-start', '2024', '--fiscal-year-end', '2025',
                '--source-root', str(self.root/'source'), '--work-dir', str(self.root/'state'),
                '--output-dir', str(self.root/'outputs'), '--metric', 'B10']))
        self.assertEqual(2024, selected.call_args.kwargs['fiscal_year_start'])
        self.assertEqual(2025, selected.call_args.kwargs['fiscal_year_end'])

    def test_completed_withheld_survives_read_after_another_metric_subset(self):
        """Constructed history control: a later subset cannot revive old success."""
        import copy
        import json
        from tests.vnext.test_company_current_records import CurrentCompanyTest
        from vnext import company_current_records as current
        from vnext.csv_output import METRIC_FIELDS, _csv_bytes
        fixture = CurrentCompanyTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.run_company(['B01'])
        prior = fixture.work/'updates/B01/results/first'
        state = fixture.work/'updates/B01/periods/FY2024'
        success = state/'results/success'; success.mkdir(parents=True)
        held = state/'results/held'; held.mkdir()
        old = copy.deepcopy(fixture.values[str(prior)])
        old['result'].update(period_start='2024-01-01', period_end='2024-12-31',
            result_id='constructed-old-success', value='100', publication='PUBLISHED')
        old['manifest']['target_period']['fiscal_year'] = 2024
        old['files']['metrics_matrix.csv'] = _csv_bytes(rows=[{
            **{f: '' for f in METRIC_FIELDS}, 'metric_id': 'B01', 'fiscal_year': '2024',
            'period_start': '2024-01-01', 'period_end': '2024-12-31',
            'value': '100', 'unit': 'USD', 'status': 'OK'}], fieldnames=METRIC_FIELDS)
        fixture.values[str(success)] = old
        new = copy.deepcopy(old)
        new['result'].update(result_id='constructed-current-withheld', value=None,
            publication='WITHHELD', unit=None, reason_code='CONSTRUCTED_CONTROL_BUSINESS_WITHHELD')
        new['files']['metrics_matrix.csv'] = _csv_bytes(rows=[{
            **{f: '' for f in METRIC_FIELDS}, 'metric_id': 'B01', 'fiscal_year': '2024',
            'period_start': '2024-01-01', 'period_end': '2024-12-31', 'status': 'WITHHELD'}],
            fieldnames=METRIC_FIELDS)
        fixture.values[str(held)] = new
        common = {'company_id': 'marriott_international', 'metric_id': 'B01',
            'requested_fiscal_year': 2024, 'period_end': '2024-12-31',
            'configuration': {'constructed_control': True}, 'source_census': []}
        (state/'current-result.json').write_text(json.dumps({**common,
            'version': 'success', 'result_id': old['result']['result_id']}))
        (state/'completed-check.json').write_text(json.dumps({**common,
            'version': 'held', 'result_id': new['result']['result_id'], 'status': 'CANDIDATE_WITHHELD'}))
        fixture.run_company(['B02'])
        view = current.read_current_company(state_root=fixture.work, company_id='marriott_international')
        row = next(r for r in view['metrics'] if r['metric_id'] == 'B01' and r['fiscal_year'] == 2024)
        self.assertFalse(row['requested_in_latest_execution'])
        self.assertIsNone(row['value'])
        self.assertEqual('WITHHELD', row['publication'])
