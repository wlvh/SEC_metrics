"""Unsupported subject revisions cannot reach the historical calculation."""
import unittest
import copy
from pathlib import Path
from unittest.mock import patch

from vnext import historical_statement_cases as cases


class HistoricalStatementScopeTest(unittest.TestCase):
    def test_amended_target_and_successor_require_explicit_adaptation(self):
        for amendments, mode in [([{'form': '10-K/A'}], 'CONTINUOUS_PRIMARY'),
                                 ([], 'SUCCESSOR_PREDECESSOR')]:
            with self.subTest(amendments=amendments, mode=mode), \
                    patch.object(cases, 'resolve_period_selection', return_value={}), \
                    patch.object(cases, 'prepare_historical_annual_input', return_value={
                        'amendments': amendments, 'subject_policy': {'mode': mode}}), \
                    patch.object(cases, 'installed_ordinary_spec_documents') as specs, \
                    patch.object(cases, '_deterministic_metric_graph') as calculate:
                with self.assertRaisesRegex(cases.StatementCaseError,
                                            'AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED') as caught:
                    cases.prepare_historical_statement_year_case(repo_root=Path('/constructed'),
                        company_id='constructed', metric_id='B04', fiscal_year=2024)
                self.assertEqual('IMPLEMENTATION_GAP', caught.exception.category)
                specs.assert_not_called()
                calculate.assert_not_called()

    def test_other_metric_does_not_select_sources(self):
        with patch.object(cases, 'resolve_period_selection') as select:
            with self.assertRaisesRegex(cases.StatementCaseError, 'FAMILY_NOT_RECEIVED'):
                cases.prepare_historical_statement_year_case(repo_root=Path('/constructed'),
                    company_id='constructed', metric_id='B03', fiscal_year=2024)
            select.assert_not_called()

    def test_companyfacts_amount_must_match_the_selected_original(self):
        from contextlib import ExitStack
        from tests.vnext.test_selected_income_source_v1 import fixture
        from vnext import ordinary_income_input
        source, annual = fixture()
        annual.update(amendments=[], subject_policy={'mode': 'CONTINUOUS_PRIMARY'})
        primary = {**source, 'raw_blob': {'media_type': 'text/html'}}
        xml = {**source, 'raw_blob': {'media_type': 'application/xml'}}
        from types import SimpleNamespace
        reader = SimpleNamespace(read=lambda *args, **kwargs: source,
            primary=lambda *args: primary, auditor_filing=lambda *args: [primary, xml])
        period = annual['table_input']['target_period']
        # Constructed post-calculation control. This is not a financial result.
        observation = {'observation_id': 'constructed', 'value': '13000000', 'unit': 'USD',
            'period_start': period['period_start'], 'period_end': period['period_end'],
            'source_binding': {'entity': annual['entity'],
                'accession': annual['filing']['accessionNumber'], 'concept': 'us-gaap:Revenues'}}
        documents = {'B01': {'path': 'unused', 'compiled_spec': {'compiled': {'dependencies': []}}}}
        with ExitStack() as stack:
            controls = {
                'resolve_period_selection': {}, 'prepare_historical_annual_input': annual,
                'installed_ordinary_spec_documents': documents,
                '_registry_rows': [{'company_id': annual['company_id']}],
                'repository_company_traits': {}, '_Sources': reader,
                'filing_inventory': {}, '_load_deterministic_catalog': {},
                '_structured_concepts': ['us-gaap:Revenues'],
                '_filing_source': ({}, []), 'companyfacts_structured_facts': [],
                'calculate_metric': ({'publication': 'PUBLISHED'}, {}, [observation]),
            }
            for name, value in controls.items():
                stack.enter_context(patch.object(cases, name, return_value=value))
            stack.enter_context(patch.object(ordinary_income_input, '_prepare_b06',
                side_effect=AssertionError('Do not prepare the current company')))
            with self.assertRaisesRegex(ordinary_income_input.IncomeInputError,
                                        'SELECTED_COMPANYFACTS_AMOUNT_DIFFERS'):
                cases.prepare_historical_statement_year_case(repo_root=Path('/constructed'),
                    company_id=annual['company_id'], metric_id='B01', fiscal_year=2025)

class HistoricalCurrentAnnualScopeTest(unittest.TestCase):
    def test_existing_entry_does_not_silently_expand_to_b07(self):
        with patch.object(cases, 'resolve_period_selection') as select:
            with self.assertRaisesRegex(cases.StatementCaseError, 'FAMILY_NOT_RECEIVED'):
                cases.prepare_historical_statement_year_case(repo_root=Path('/constructed'),
                    company_id='constructed', metric_id='B07', fiscal_year=2024)
            select.assert_not_called()

    def test_prior_year_or_instant_metrics_do_not_enter_the_annual_family(self):
        for metric in ['B02', 'B08']:
            with self.subTest(metric=metric), patch.object(cases, 'resolve_period_selection') as select:
                with self.assertRaisesRegex(cases.StatementCaseError, 'FAMILY_NOT_RECEIVED'):
                    cases.prepare_historical_current_annual_year_case(repo_root=Path('/constructed'),
                        company_id='constructed', metric_id=metric, fiscal_year=2024)
                select.assert_not_called()

    def test_declared_wrong_source_period_cannot_select_a_filing(self):
        catalog=copy.deepcopy(cases._load_deterministic_catalog(repo_root=cases.ROOT))
        catalog['metrics']['B07']['branches'][0]['components'][0]['period_role']='current_instant'
        with patch.object(cases, '_load_deterministic_catalog', return_value=catalog), \
                patch.object(cases, 'resolve_period_selection') as select:
            with self.assertRaisesRegex(cases.StatementCaseError, 'SOURCE_ROLE_CHANGED'):
                cases.prepare_historical_current_annual_year_case(repo_root=Path('/constructed'),
                    company_id='constructed', metric_id='B07', fiscal_year=2024)
            select.assert_not_called()

    def test_amendment_and_successor_keep_the_existing_rejection(self):
        for amendments, mode in [([{'form':'10-K/A'}], 'CONTINUOUS_PRIMARY'),
                                 ([], 'SUCCESSOR_PREDECESSOR')]:
            with self.subTest(mode=mode), \
                    patch.object(cases, 'resolve_period_selection', return_value={}), \
                    patch.object(cases, 'prepare_historical_annual_input', return_value={
                        'amendments':amendments, 'subject_policy':{'mode':mode}}), \
                    patch.object(cases, 'installed_ordinary_spec_documents') as specs, \
                    patch.object(cases, '_deterministic_metric_graph') as graph:
                with self.assertRaisesRegex(cases.StatementCaseError, 'AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED'):
                    cases.prepare_historical_current_annual_year_case(repo_root=Path('/constructed'),
                        company_id='constructed', metric_id='B07', fiscal_year=2024)
                specs.assert_not_called();graph.assert_not_called()
