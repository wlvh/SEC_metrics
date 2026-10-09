"""Small controls for the historical event consumer; no financial conclusion."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from vnext import historical_event_cases as cases
from vnext.normal_run_specs import installed_ordinary_spec_documents
from vnext.normal_history_catalog import HistoryCatalogError
from vnext.normal_governance_input import NormalGovernanceInputError

PERIOD = {'fiscal_year': 2024, 'period_start': '2024-01-01', 'period_end': '2024-12-31'}
PREPARED = {'company_id': 'marriott_international', 'entity': '1048286',
    'filing': {'accessionNumber': 'constructed'}, 'amendments': [],
    'subject_policy': {'mode': 'CONTINUOUS_PRIMARY'},
    'table_input': {'target_period': PERIOD}, 'source_proofs': []}


class HistoricalEventCaseTest(TestCase):
    def test_content_confirmation_route_is_not_silently_counted(self):
        with patch.object(cases, 'resolve_period_selection') as select:
            with self.assertRaisesRegex(cases.NormalZeroAiError, 'CONTENT_FAMILY_NOT_RECEIVED'):
                cases.prepare_historical_event_year_case(repo_root=Path('/constructed'),
                    company_id='marriott_international', metric_id='E01', fiscal_year=2024)
            select.assert_not_called()

    def test_successor_does_not_narrow_the_approved_multi_cik_window(self):
        prepared = {**PREPARED, 'subject_policy': {'mode': 'SUCCESSOR_REGISTRANT_ONLY'}}
        with patch.object(cases, 'resolve_period_selection', return_value={}), \
             patch.object(cases, 'prepare_historical_annual_input', return_value=prepared), \
             patch.object(cases, 'event_sources') as collect:
            with self.assertRaisesRegex(cases.NormalZeroAiError, 'REGISTERED_EVENT_SOURCE_API_NOT_RECEIVED'):
                cases.prepare_historical_event_year_case(repo_root=Path('/constructed'),
                    company_id='marriott_international', metric_id='E02', fiscal_year=2024)
            collect.assert_not_called()

    def control(self, error):
        reader = SimpleNamespace(records={}, proofs={},
            read=lambda *args, **kwargs: {'source_reference': {'source_reference_id': 'constructed'}})
        stack = ExitStack(); self.addCleanup(stack.close)
        for name, value in [('resolve_period_selection', {}),
                            ('prepare_historical_annual_input', PREPARED),
                            ('_Sources', reader), ('verify_ordinary_source_proofs', {})]:
            stack.enter_context(patch.object(cases, name, return_value=value))
        stack.enter_context(patch.object(cases, 'event_sources', side_effect=error))
        return cases.prepare_historical_event_year_case(repo_root=Path('/constructed'),
            company_id='marriott_international', metric_id='E02', fiscal_year=2024)

    def test_missing_event_header_is_withheld_not_a_correct_zero(self):
        error = NormalGovernanceInputError('SAVED_SOURCE_MISSING:constructed-header', 'SOURCE_UNAVAILABLE')
        case = self.control(error)
        result = case['results']['E02']
        self.assertEqual('WITHHELD', result['publication']); self.assertIsNone(result['value'])
        self.assertEqual('SOURCE_UNAVAILABLE', case['selection']['category'])
        self.assertIn('constructed-header', case['selection']['reason'])
        self.assertEqual(PERIOD, case['target_period'])

    def test_incoherent_history_block_is_not_read_around(self):
        case = self.control(HistoryCatalogError('CONSTRUCTED_INCOMPLETE_BLOCK', 'SOURCE_COVERAGE_CONFLICT'))
        self.assertIsNone(case['results']['E02']['value'])
        self.assertEqual('SOURCE_COVERAGE_CONFLICT', case['selection']['category'])
        self.assertEqual([], case['input_binding']['source_set_manifests'])

    def test_unknown_program_error_is_not_mislabeled_as_disclosure_absence(self):
        with self.assertRaisesRegex(RuntimeError, 'constructed-unexpected-error'):
            self.control(RuntimeError('constructed-unexpected-error'))

    def test_catalog_change_to_content_method_is_an_explicit_gap(self):
        catalog = cases.load_event_route_catalog(repo_root=cases.ROOT)
        catalog = {**catalog, 'routes': {**catalog['routes'], 'E02': {
            **catalog['routes']['E02'], 'keyword_item_rules': [{'item_code': '8.01'}]}}}
        with patch.object(cases, 'resolve_period_selection', return_value={}), \
             patch.object(cases, 'prepare_historical_annual_input', return_value=PREPARED), \
             patch.object(cases, 'load_event_route_catalog', return_value=catalog), \
             patch.object(cases, 'event_sources') as collect:
            with self.assertRaisesRegex(cases.NormalZeroAiError, 'CONTENT_ROUTE_NOT_RECEIVED'):
                cases.prepare_historical_event_year_case(repo_root=Path('/constructed'),
                    company_id='marriott_international', metric_id='E02', fiscal_year=2024)
            collect.assert_not_called()
