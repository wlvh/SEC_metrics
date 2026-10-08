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
