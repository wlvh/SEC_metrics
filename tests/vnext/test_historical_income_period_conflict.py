"""Small historical consumer controls; actual saved-source probe is separate."""
import copy
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from vnext import historical_zero_ai_results as history
from vnext import normal_annual_input_v2 as current_annual
from vnext import ordinary_income_input as income

ROOT = Path(__file__).resolve().parents[2]
PERIOD = {'fiscal_year': 2025, 'period_start': '2025-01-01', 'period_end': '2025-12-31'}
PREPARED = {'company_id': 'paramount_skydance_paramount_global', 'entity': '2041610',
    'subject_policy': {'mode': 'SUCCESSOR_REGISTRANT_ONLY'}, 'amendments': [],
    'filing': {'accessionNumber': 'TEST-SELECTED', 'reportDate': '2025-12-31'},
    'table_input': {'target_period': PERIOD}, 'source_proofs': []}
DETAILS = {'native_period': ['2025-08-08', '2025-12-31'],
    'visible_periods': [['2025-08-07', '2025-12-31']], 'status': 'CONFLICT',
    'headers': [{'range_header': {'raw_text': 'Period from August 7 - December 31'}}]}


class HistoricalIncomePeriodConflictTest(TestCase):
    def test_current_conflict_cannot_be_assigned_to_a_different_selected_filing(self):
        other = copy.deepcopy(PREPARED)
        other['filing']['accessionNumber'] = 'TEST-OTHER-HISTORICAL-FILING'
        with (patch.object(history, 'release_aware', side_effect=lambda value: value),
              patch.object(current_annual, 'prepare_saved_annual_input', return_value=PREPARED),
              patch.object(income, 'prepare_current_income_input',
                  side_effect=AssertionError('Do not inspect an unrelated current filing')) as calculate):
            result = history._successor_income_input(repo_root=ROOT,
                company_id=PREPARED['company_id'], metric_id='B01', prepared=other)
        self.assertIsNone(result)
        calculate.assert_not_called()

    def test_non_income_and_continuous_subjects_do_not_prepare_successor_income(self):
        for metric, mode in [('C01', 'SUCCESSOR_REGISTRANT_ONLY'), ('B03', 'CONTINUOUS_PRIMARY')]:
            prepared = {**PREPARED, 'subject_policy': {'mode': mode}}
            with patch.object(income, 'prepare_current_income_input') as current:
                self.assertIsNone(history._successor_income_input(repo_root=ROOT,
                    company_id=prepared['company_id'], metric_id=metric, prepared=prepared))
            current.assert_not_called()

    def test_conflicting_dates_produce_named_withholding_with_dependency_and_evidence(self):
        reader = SimpleNamespace(proofs={}, records={}, failed_attempts={},
            read=lambda *args, **kwargs: {'raw_bytes': b'{}'}, primary=lambda *args: {})
        failure = income.IncomeInputError('ORDINARY_INCOME_VISIBLE_PERIOD_CONFLICT', DETAILS)
        for metric in ('B01', 'B03'):
            with (self.subTest(metric=metric),
                  patch.object(history, '_authority', return_value={}),
                  patch.object(history, 'prepare_historical_annual_input', return_value=PREPARED),
                  patch.object(history, '_successor_income_input', side_effect=failure),
                  patch.object(history, '_Sources', return_value=reader),
                  patch.object(history, 'verify_ordinary_source_proofs', return_value={})):
                component = history.resolve_historical_zero_ai_metric(repo_root=ROOT,
                    company_id=PREPARED['company_id'], metric_id=metric, period_selection={})
            self.assertEqual('WITHHELD', component['result']['publication'])
            self.assertIsNone(component['result']['value'])
            self.assertEqual(str(failure), component['result']['reason_code'])
            self.assertEqual('SOURCE_PERIOD_CONFLICT', component['selection']['category'])
            self.assertEqual(DETAILS, component['selection']['income_period_evidence'])
            self.assertEqual(PERIOD, component['pinned_target_period'])
            self.assertEqual([], component['observations'])
            dependencies = [r for r in component['dependency_records'] if r['record_type'] == 'METRIC_RESULT']
            self.assertEqual(['B01'] if metric == 'B03' else [], [r['metric_id'] for r in dependencies])
            self.assertTrue(all(r['value'] is None and r['publication'] == 'WITHHELD' for r in dependencies))
            self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0}, component['calls'])


class SelectedHistoricalIncomeConsumerTest(TestCase):
    def source(self, *, short=False):
        from tests.vnext.test_selected_income_source_v1 import fixture
        source, annual = fixture(short=short)
        source = {**source, 'raw_blob': {'media_type': 'text/html'}}
        xml = {**source, 'raw_blob': {'media_type': 'application/xml'}}
        reader = SimpleNamespace(auditor_filing=lambda filing: [source, xml])
        return reader, annual, source

    def test_selected_reader_and_policy_do_not_prepare_the_current_company(self):
        from vnext import selected_income_source_v1 as shared
        from vnext.historical_dei import annual_period
        from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
        reader, annual, source = self.source()
        with (patch.object(income, '_prepare_b06', side_effect=AssertionError('No latest preparation')),
              patch.object(shared, 'native_income_reports', wraps=shared.native_income_reports) as reports,
              patch.object(income, 'verify_income_observations', return_value=['verified']) as verify):
            checks = history.verify_selected_historical_income(reader=reader,
                prepared=annual, concepts=['us-gaap:Revenues'], observations=['observation'])
        self.assertEqual(checks, ['verified'])
        self.assertEqual(reports.call_count, 2)
        for call in reports.call_args_list:
            self.assertIs(call.kwargs['annual_period_reader'], annual_period)
            self.assertEqual(call.kwargs['namespace_policy'], YEAR_OR_DATE_RELEASE)
        self.assertEqual(verify.call_args.args[0]['statement_period'], annual['table_input']['target_period'])

    def test_short_observation_does_not_replace_the_selected_annual_period(self):
        reader, annual, source = self.source(short=True)
        observation = {'source_binding': {'entity': annual['entity'],
            'accession': annual['filing']['accessionNumber'], 'concept': 'us-gaap:Revenues'},
            'unit': 'USD', 'period_start': '2025-08-08', 'period_end': '2025-12-31',
            'value': '5000000', 'observation_id': 'constructed'}
        # This construction is a period control, not a financial conclusion.
        with self.assertRaisesRegex(income.IncomeInputError, 'SELECTED_OBSERVATION_SCOPE_CHANGED'):
            history.verify_selected_historical_income(reader=reader, prepared=annual,
                concepts=['us-gaap:Revenues'], observations=[observation])

    def test_missing_original_and_changed_bytes_are_named_failures(self):
        reader, annual, source = self.source()
        with self.assertRaisesRegex(income.IncomeInputError, 'ORIGINAL_SOURCE_SET_AMBIGUOUS'):
            history.verify_selected_historical_income(reader=SimpleNamespace(auditor_filing=lambda f: [source]),
                prepared=annual, concepts=['us-gaap:Revenues'], observations=[])
        source['raw_bytes'] += b'changed'
        with self.assertRaisesRegex(income.IncomeInputError, 'ORIGINAL_BINDING_CHANGED'):
            history.verify_selected_historical_income(reader=reader, prepared=annual,
                concepts=['us-gaap:Revenues'], observations=[])


class HistoricalIncomeDispatchTest(TestCase):
    def test_revenue_and_margin_share_the_existing_income_case_factory(self):
        import tempfile
        from vnext import company_local, company_current_records
        from vnext.historical_saved_case import prepare_historical_income_year_case
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            source, state, outputs = [parent / name for name in ('source', 'state', 'outputs')]
            source.mkdir()
            with (patch.object(company_local, 'external', side_effect=lambda value: value),
                  patch.object(company_current_records, 'run_saved_company', return_value={'ok': True}) as run):
                result = company_local._run_history(company_id='marriott_international',
                    work_dir=state, output_dir=outputs, metric_ids=['B01', 'B03'],
                    fiscal_year_start=2024, fiscal_year_end=2024, source_root=source)
            self.assertEqual(result, {'ok': True})
            self.assertIs(run.call_args.kwargs['case_factory'], prepare_historical_income_year_case)
            self.assertEqual(run.call_args.kwargs['metric_ids'], ['B01', 'B03'])
            files = run.call_args.kwargs['processing_files']
            self.assertIn('scripts/vnext/selected_income_source_v1.py', files)
            self.assertIn('scripts/vnext/historical_dei.py', files)
            self.assertIn('scripts/vnext/xbrl_namespace_policy.py', files)
