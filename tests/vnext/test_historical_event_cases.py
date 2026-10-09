"""Small controls for the historical event consumer; no financial conclusion."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
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

    def test_successor_keeps_wide_measurement_and_pinned_container(self):
        prepared = {**PREPARED, 'subject_policy': {'mode': 'SUCCESSOR_REGISTRANT_ONLY'}}
        prepared['table_input'] = {'target_period': {**PERIOD, 'fiscal_year': 2025,
            'period_start': '2025-01-01', 'period_end': '2025-12-31'}}
        before = dict(prepared['table_input']['target_period'])
        window, union = cases.selected_event_window(prepared)
        self.assertTrue(union)
        self.assertEqual('2024-01-01', window['period_start'])
        self.assertEqual('2025-12-31', window['period_end'])
        self.assertEqual(before, prepared['table_input']['target_period'])

    def test_predecessor_period_reads_only_its_selected_registrant(self):
        window, union = cases.selected_event_window(PREPARED)
        self.assertFalse(union); self.assertEqual(PERIOD, window)

    def control(self, error):
        reader = SimpleNamespace(records={}, proofs={}, primary=Mock(),
            read=lambda *args, **kwargs: {'source_reference': {'source_reference_id': 'constructed'}})
        stack = ExitStack(); self.addCleanup(stack.close)
        for name, value in [('resolve_period_selection', {}),
                            ('prepare_historical_annual_input', PREPARED),
                            ('_Sources', reader), ('verify_ordinary_source_proofs', {})]:
            stack.enter_context(patch.object(cases, name, return_value=value))
        stack.enter_context(patch.object(cases, 'read_selected_event_sources', side_effect=error))
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
             patch.object(cases, 'read_selected_event_sources') as collect:
            with self.assertRaisesRegex(cases.NormalZeroAiError, 'CONTENT_ROUTE_NOT_RECEIVED'):
                cases.prepare_historical_event_year_case(repo_root=Path('/constructed'),
                    company_id='marriott_international', metric_id='E02', fiscal_year=2024)
            collect.assert_not_called()


class HistoricalEventHistoryStrategyTest(TestCase):
    def test_complete_body_and_gap_day_use_the_existing_coherence_rule(self):
        import json
        shard = {'name': 'CIK0001048286-submissions-001.json',
            'filingFrom': '2020-01-01', 'filingTo': '2020-12-30', 'filingCount': 2}
        payload = {'filings': {'recent': {'filingDate': ['2021-01-01']}, 'files': [shard]}}
        last = cases.block_last_days(payload=payload, shards=[shard])
        check = cases.check_historical_event_block
        self.assertEqual('2020-12-31', last[shard['name']])
        body = {'filingDate': ['2020-06-01', '2020-12-31']}
        self.assertIsNone(check(shard=shard, body=body, rows=[], shards=[shard], period=PERIOD, last_day='2020-12-31'))
        bad = check(shard=shard, body={'filingDate': ['2020-06-01']}, rows=[], shards=[shard], period=PERIOD, last_day='2020-12-31')
        self.assertIn('FILING_COUNT_DIFFERS_FROM_DECLARED', bad['failed_checks'])
        # Counts include forms that the downstream event list does not retain.


class HistoricalEventRecordRetentionTest(TestCase):
    def test_source_reference_does_not_overwrite_its_raw_blob(self):
        reader = SimpleNamespace(records={}, proofs={}, primary=Mock())
        raw = {'record_type': 'RAW_BLOB', 'raw_asset_id': 'sha256:constructed',
               'media_type': 'text/plain', 'storage_uri': 'constructed.hdr'}
        ref = {'record_type': 'SOURCE_REFERENCE', 'source_reference_id': 'source:constructed',
               'raw_asset_id': raw['raw_asset_id'], 'source_role': 'sec_submissions_inventory'}
        packet = {'claims': [], 'source_set_manifests': [{'source_role': 'event_set'}],
                  'filings': [], 'source_records': [raw, ref], 'source_bindings': [],
                  'source_proofs': [], 'registered_event_scope': None,
                  'inventory_source_reference': ref}
        with ExitStack() as stack:
            for name, value in [('resolve_period_selection', {}),
                                ('prepare_historical_annual_input', PREPARED),
                                ('_Sources', reader), ('_event_amendment_checks', []),
                                ('read_selected_event_sources', packet),
                                ('verify_ordinary_source_proofs', {})]:
                stack.enter_context(patch.object(cases, name, return_value=value))
            stack.enter_context(patch.object(cases, 'project_event_result',
                side_effect=cases.NormalZeroAiError('CONSTRUCTED_FAILURE_AFTER_SOURCE_READ')))
            case = cases.prepare_historical_event_year_case(repo_root=Path('/constructed'),
                company_id='marriott_international', metric_id='E02', fiscal_year=2024)
        self.assertIn(raw, case['expected_records']); self.assertIn(ref, case['expected_records'])
        self.assertIn(ref, case['references'])
        reader.primary.assert_called_once_with(PREPARED['filing'])
        self.assertIsNone(case['results']['E02']['value'])
