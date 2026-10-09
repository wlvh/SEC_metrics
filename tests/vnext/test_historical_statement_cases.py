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
                '_registry_rows': [{'company_id': annual['company_id'],
                                    'entity_continuity_status': 'continuous'}],
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


class HistoricalPeriodSubjectTest(unittest.TestCase):
    def example(self):
        return ({'primary_cik':'2','entity_continuity_status':'successor'},
                {'entity':'1','subject_policy':{'mode':'CONTINUOUS_PRIMARY',
                    'selected_cik':'1','cross_entity_combination_authorized':False}},
                {'period_registrant':{'role':'PREDECESSOR','reporting_cik':'1','successor_cik':'2'}})

    def test_predecessor_context_uses_its_own_cik_without_mutating_registry(self):
        registry,prepared,selection=self.example()
        current,detail=cases._registry_for_selected_period(registry=registry,
            prepared=prepared,selection=selection)
        self.assertEqual('1',current['primary_cik'])
        self.assertEqual('continuous',current['entity_continuity_status'])
        self.assertEqual('2',registry['primary_cik'])
        self.assertEqual('successor',registry['entity_continuity_status'])
        self.assertEqual('1',detail['period_registrant_cik'])
        self.assertFalse(detail['cross_entity_combination_authorized'])

    def test_continuous_company_keeps_original_registry_object(self):
        registry,prepared,selection=self.example();registry['entity_continuity_status']='continuous'
        current,detail=cases._registry_for_selected_period(registry=registry,
            prepared=prepared,selection=selection)
        self.assertIs(registry,current);self.assertIsNone(detail)

    def test_successor_context_keeps_its_existing_noncomparability(self):
        registry,prepared,selection=self.example();prepared['subject_policy']['mode']='SUCCESSOR_REGISTRANT_ONLY'
        current,detail=cases._registry_for_selected_period(registry=registry,
            prepared=prepared,selection=selection)
        self.assertIs(registry,current);self.assertIsNone(detail)

    def test_mismatched_reporter_successor_or_cross_entity_does_not_get_override(self):
        for changed in ['reporter','successor','cross_entity','role']:
            registry,prepared,selection=self.example()
            if changed=='reporter':selection['period_registrant']['reporting_cik']='3'
            elif changed=='successor':selection['period_registrant']['successor_cik']='3'
            elif changed=='cross_entity':prepared['subject_policy']['cross_entity_combination_authorized']=True
            else:selection['period_registrant']['role']='PRIMARY'
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(cases.StatementCaseError,'PERIOD_SUBJECT_NOT_PROVEN'):
                    cases._registry_for_selected_period(registry=registry,prepared=prepared,selection=selection)
