"""Saved real 53-week catalog graphs; no source parse or business call per test."""
import copy
from datetime import date
from decimal import Decimal
import gzip
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from vnext.historical_saved_case import case_from_historical_companyfacts
from vnext.historical_results import resolve_historical_companyfacts_metrics

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT/'docs/evidence/issue47_history/historical-income-receiving-2026-10-08/Macy-FY2023-companyfacts-component.json.gz'


class HistoricalCatalogSavedCaseTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(gzip.decompress(FIXTURE.read_bytes()))

    def case(self, metric, component=None):
        return case_from_historical_companyfacts(component=component or self.original,
                                                 metric_id=metric, rules_root=ROOT)

    def test_growth_keeps_each_original_accession_and_actual_53_week_period(self):
        case = self.case('B02')
        self.assertEqual({'fiscal_year': 2023, 'period_start': '2023-01-29',
                          'period_end': '2024-02-03'}, case['target_period'])
        self.assertEqual(371, (date(2024, 2, 3)-date(2023, 1, 29)).days+1)
        claims = [r for r in case['expected_records']
                  if r['record_type'] == 'DETERMINISTIC_VERIFIED_CLAIM']
        self.assertEqual({'0001628280-24-012734', '0001628280-23-009154'},
                         {c['attributes']['accession'] for c in claims})
        self.assertEqual((Decimal(23092)-Decimal(24442))/Decimal(24442),
                         Decimal(case['results']['B02']['value']))
        self.assertEqual(self.original['metrics']['B02']['result']['result_id'],
                         case['results']['B02']['result_id'])

    def test_net_income_and_fcf_keep_usd_and_source_calculation_records(self):
        for metric, value in [('B04', Decimal(105000000)),
                              ('B05', Decimal(1305000000)-Decimal(631000000))]:
            with self.subTest(metric=metric):
                case = self.case(metric)
                self.assertEqual('USD', case['results'][metric]['unit'])
                self.assertEqual(value, Decimal(case['results'][metric]['value']))
                self.assertEqual(self.original['source_proofs'], case['source_proofs'])
                self.assertEqual({metric}, set(case['compiled_specs']))
                self.assertFalse(case['input_binding']['latest_restated_values_used'])

    def test_wrong_company_or_period_is_rejected(self):
        for key, value in [('company_id', 'CONSTRUCTED_WRONG_SUBJECT'),
                           ('period_start', '2023-01-01')]:
            component = copy.deepcopy(self.original)
            detail = component['metrics']['B04']
            detail['result'][key] = value
            for record in detail['records']:
                if record['record_type'] == 'METRIC_RESULT':
                    record[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'COORDINATE_OR_SPEC_CHANGED'):
                self.case('B04', component)

    def test_missing_result_or_trace_is_not_reconstructed(self):
        for record_type in ('METRIC_RESULT', 'EXECUTION_TRACE'):
            component = copy.deepcopy(self.original)
            detail = component['metrics']['B05']
            detail['records'] = [r for r in detail['records'] if r['record_type'] != record_type]
            with self.subTest(record_type=record_type), self.assertRaisesRegex(ValueError, 'COORDINATE_OR_SPEC_CHANGED'):
                self.case('B05', component)

    def test_changed_spec_or_unreceived_family_is_not_admitted(self):
        component = copy.deepcopy(self.original)
        component['metrics']['B02']['compiled_spec']['compiled']['canonical_unit'] = 'USD'
        with self.assertRaisesRegex(ValueError, 'CATALOG_SPEC_CHANGED'):
            self.case('B02', component)
        with self.assertRaisesRegex(ValueError, 'FAMILY_NOT_RECEIVED'):
            self.case('A05')

    def test_invalid_selected_metrics_fail_before_source_preparation(self):
        for ids in ([], ['B02', 'B02'], ['D03'], [True], 'B02'):
            with patch('vnext.historical_results.prepare_historical_annual_input') as prepare:
                with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, 'SELECTED_METRIC_SET_INVALID'):
                    resolve_historical_companyfacts_metrics(repo_root=ROOT, company_id='macys',
                        period_selection={}, rules_root=ROOT, metric_ids=ids)
                prepare.assert_not_called()

    def test_unreceived_amendment_or_successor_is_a_gap_before_any_calculation(self):
        from vnext.normal_annual_input import NormalAnnualInputError
        for amendment, mode in [([{'form': '10-K/A'}], 'CONTINUOUS_PRIMARY'),
                                 ([], 'SUCCESSOR_REGISTRANT_ONLY')]:
            prepared = copy.deepcopy(self.original['prepared_input'])
            prepared['amendments'] = amendment
            prepared['subject_policy']['mode'] = mode
            with patch('vnext.historical_results.prepare_historical_annual_input', return_value=prepared), \
                 patch('vnext.historical_results._deterministic_metric_graph') as calculate:
                with self.subTest(mode=mode), self.assertRaisesRegex(NormalAnnualInputError, 'SAVED_CASE_SCOPE_NOT_RECEIVED') as failure:
                    resolve_historical_companyfacts_metrics(repo_root=ROOT, company_id='macys',
                        period_selection={}, rules_root=ROOT, metric_ids=['B04'])
                self.assertEqual('IMPLEMENTATION_GAP', failure.exception.category)
                calculate.assert_not_called()
