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


class HistoricalSuccessorComparabilityTest(unittest.TestCase):
    def test_wrong_subject_or_cross_entity_cannot_use_the_metadata_guard(self):
        registry={'company_id':'constructed','primary_cik':'1','entity_continuity_status':'successor'}
        for changed in ['selected','entity','mode','cross','registry_status']:
            prepared={'entity':'1','subject_policy':{'mode':'SUCCESSOR_REGISTRANT_ONLY',
                'selected_cik':'1','cross_entity_combination_authorized':False}}
            row=copy.deepcopy(registry)
            if changed=='selected':prepared['subject_policy']['selected_cik']='2'
            elif changed=='entity':prepared['entity']='2'
            elif changed=='mode':prepared['subject_policy']['mode']='CONTINUOUS_PRIMARY'
            elif changed=='cross':prepared['subject_policy']['cross_entity_combination_authorized']=True
            else:row['entity_continuity_status']='continuous'
            with self.subTest(changed=changed), patch.object(cases,'_registry_rows',return_value=[row]), \
                    patch.object(cases,'_Sources') as source, \
                    patch.object(cases,'_deterministic_metric_graph') as graph:
                with self.assertRaisesRegex(cases.StatementCaseError,'SUCCESSOR_SUBJECT_NOT_PROVEN'):
                    cases._successor_comparability_case(source=Path('/constructed'),
                        company_id='constructed',metric_id='B07',prepared=prepared,selection={})
                source.assert_not_called();graph.assert_not_called()

    def test_noncontinuous_rule_cannot_be_replaced_by_current_instant_permission(self):
        with patch.object(cases,'_Sources') as source:
            with self.assertRaisesRegex(cases.StatementCaseError,'ROUTE_NOT_RECEIVED'):
                cases._successor_comparability_case(source=Path('/constructed'),
                    company_id='constructed',metric_id='B08',prepared={},selection={})
            source.assert_not_called()

    def test_revenue_still_requires_statement_scope(self):
        prepared={'amendments':[],'subject_policy':{'mode':'SUCCESSOR_REGISTRANT_ONLY'}}
        with patch.object(cases,'resolve_period_selection',return_value={}), \
                patch.object(cases,'prepare_historical_annual_input',return_value=prepared), \
                patch.object(cases,'_successor_comparability_case') as guard:
            with self.assertRaisesRegex(cases.StatementCaseError,'AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED'):
                cases.prepare_historical_statement_year_case(repo_root=Path('/constructed'),
                    company_id='constructed',metric_id='B01',fiscal_year=2025)
            guard.assert_not_called()
