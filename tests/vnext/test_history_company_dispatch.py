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
        with patch('vnext.company_current_records.run_saved_company', return_value={}) as shared:
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
                self.run_history(metric_ids=['B01'])
        shared.assert_not_called()

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
