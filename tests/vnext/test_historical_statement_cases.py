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
        documents = {'B01': {'path': 'unused', 'compiled_spec': {'compiled': {
            'dependencies': [], 'applicability': {'all': [], 'none': []}}}}}
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

class HistoricalRevenueScopeConsumerTest(unittest.TestCase):
    """Constructed source controls at the actual adapter, never saved results."""

    def prepare(self, *, change=None):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from tests.vnext.test_selected_revenue_scope_v1 import originals, facts, APPROVED
        from vnext.canonical import sha256_bytes
        from vnext.specs import compile_spec_file
        primary, xml, annual = originals()
        # The shared fixture also contains an unrelated standalone Revenues
        # control. This adapter test supplies only its constructed statement.
        for original in (primary, xml):
            original['raw_bytes'] = original['raw_bytes'].replace(
                b'<us-gaap:Revenues contextRef="annual" unitRef="usd" decimals="0">12000000</us-gaap:Revenues>', b'')
            original['source_reference']['raw_asset_id'] = 'sha256:' + sha256_bytes(content=original['raw_bytes'])
        annual.update(amendments=[], subject_policy={'mode': 'CONTINUOUS_PRIMARY'}, source_proofs=[])
        primary['raw_blob'] = {'media_type': 'text/html'}
        xml['raw_blob'] = {'media_type': 'application/xml'}
        source_facts = facts(annual)
        if change:
            change(primary, xml, annual, source_facts)
        reader = SimpleNamespace(read=lambda *args, **kwargs: primary,
            primary=lambda *args: primary, auditor_filing=lambda *args: [primary, xml],
            proofs={}, records={})
        spec = compile_spec_file(path=cases.ROOT/'catalog/metrics/B01_revenue.md', dependency_specs={})
        with ExitStack() as stack:
            for name, value in {
                'resolve_period_selection': {}, 'prepare_historical_annual_input': annual,
                'installed_ordinary_spec_documents': {'B01': {'path': 'unused', 'compiled_spec': spec}},
                '_registry_rows': [{'company_id': annual['company_id'], 'entity_continuity_status': 'continuous'}],
                'repository_company_traits': ['non_financial'], '_Sources': reader,
                'filing_inventory': {}, '_load_deterministic_catalog': {},
                '_structured_concepts': APPROVED, '_filing_source': ({'manifest': {}}, []),
                'companyfacts_structured_facts': source_facts, 'verify_ordinary_source_proofs': {},
            }.items():
                stack.enter_context(patch.object(cases, name, return_value=value))
            calculator = stack.enter_context(patch.object(cases, 'calculate_metric', wraps=cases.calculate_metric))
            value = cases.prepare_historical_statement_year_case(repo_root=Path('/constructed'),
                company_id=annual['company_id'], metric_id='B01', fiscal_year=2025)
        return value, source_facts, calculator

    def test_reported_total_is_admitted_before_actual_calculator(self):
        value, source_facts, calculator = self.prepare()
        self.assertEqual(value['results']['B01']['value'], '58496000000')
        self.assertEqual(calculator.call_args.kwargs['structured_facts'], [source_facts[1]])
        self.assertEqual(source_facts[0]['value'], '50914000000')
        check = value['input_assessments']['historical_statement']['income_observation_checks'][0]
        self.assertEqual(check['observation_id'],
                         next(r['observation_id'] for r in value['expected_records']
                              if r.get('record_type') == 'VERIFIED_OBSERVATION'))
        self.assertEqual({row['value'] for rows in check['original_reports'].values() for row in rows},
                         {'58496000000'})

    def test_display_is_bounded_while_complete_scope_evidence_is_retained(self):
        value, _, _ = self.prepare()
        full = value['input_assessments']['historical_statement']['selected_revenue_scope']
        self.assertTrue(full['reported_totals'])
        self.assertEqual(full['method'],'SELECTED_REPORTED_CONSOLIDATED_REVENUE_V2')
        self.assertNotIn('splits',full)
        self.assertEqual(value['input_binding']['assessment']['selected_revenue_scope'], full)
        self.assertEqual(set(value['selection']['selected_revenue_scope']),
                         {'scope_id', 'status', 'complete_scope_proven'})
        self.assertEqual(value['selection']['selected_revenue_scope']['scope_id'], full['scope_id'])

    def test_total_cannot_be_borrowed_from_a_later_filing(self):
        def change(primary, xml, annual, source_facts):
            source_facts[1]['accession'] = 'later'
        with self.assertRaisesRegex(ValueError, 'TOTAL_NOT_IN_COMPANYFACTS'):
            self.prepare(change=change)

    def test_literal_original_and_resolved_period_must_have_same_dates(self):
        def change(primary, xml, annual, source_facts):
            annual['original_input'] = copy.deepcopy(annual)
            annual['original_input']['table_input']['target_period']['period_start'] = '2025-02-01'
        with self.assertRaisesRegex(cases.StatementCaseError, 'ORIGINAL_PERIOD_CHANGED'):
            self.prepare(change=change)

    def test_processing_configuration_includes_shared_scope_dependency(self):
        self.assertIn('scripts/vnext/selected_revenue_scope_v1.py', cases.INCOME_PROCESSING_FILES)
        self.assertIn('scripts/vnext/selected_reported_revenue_v2.py', cases.INCOME_PROCESSING_FILES)
        self.assertNotIn('scripts/vnext/selected_revenue_scope_v1.py', cases.PROCESSING_FILES)
        self.assertNotIn('scripts/vnext/selected_reported_revenue_v2.py', cases.PROCESSING_FILES)

    def test_no_reported_total_retains_the_existing_component_scope_path(self):
        from vnext import selected_reported_revenue_v2 as reported
        with patch.object(reported,'reported_revenue_scope',return_value={'complete_scope_proven':False}):
            value,_,_=self.prepare()
        full=value['input_assessments']['historical_statement']['selected_revenue_scope']
        self.assertTrue(full['splits'])
        self.assertEqual(value['results']['B01']['value'],'58496000000')

    def test_source_bound_resolved_label_reaches_the_shared_reader_without_raw_year_rewrite(self):
        from vnext import selected_reported_revenue_v2 as reported
        label={'record_type':'ORDINARY_FISCAL_YEAR_LABEL_RESOLUTION','selected_fiscal_year':2026,
               'constructed_source_inspection_marker':True}
        def change(primary,xml,annual,source_facts):
            annual['fiscal_year_label_resolution']=label
        with patch.object(reported,'reported_revenue_scope',return_value={'complete_scope_proven':False}) as shared:
            self.prepare(change=change)
        self.assertIs(shared.call_args.kwargs['fiscal_label_resolution'],label)
        self.assertEqual(shared.call_args.kwargs['annual']['table_input']['target_period']['fiscal_year'],2025)

    def test_reported_total_conflict_cannot_fall_back_to_the_old_component(self):
        from vnext import selected_reported_revenue_v2 as reported,selected_revenue_scope_v1 as component
        with patch.object(reported,'reported_revenue_scope',side_effect=ValueError('SELECTED_REPORTED_REVENUE_VISIBLE_DATE_CONFLICT')), \
             patch.object(component,'selected_revenue_scope',side_effect=AssertionError('Conflict is not no reported total')):
            with self.assertRaisesRegex(ValueError,'VISIBLE_DATE_CONFLICT'):
                self.prepare()

    def test_reported_navigation_keeps_source_spans_without_accepting_subject_restrictions(self):
        from vnext.canonical import sha256_bytes
        def change_intro(text):
            def change(primary,xml,annual,source_facts):
                raw=primary['raw_bytes'].replace(b'<div>Consolidated Statements of Income</div>',
                    text.encode()+b'<div>Consolidated Statements of Income</div>')
                primary['raw_bytes']=raw
                primary['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=raw)
            return change
        value,_,_=self.prepare(change=change_intro(
            '<div>See accompanying Notes.</div><div>57</div><div>Table of Contents</div>'))
        scope=value['input_assessments']['historical_statement']['selected_revenue_scope']
        self.assertEqual(value['results']['B01']['value'],'58496000000')
        self.assertEqual([b['visible_text'] for b in scope['reported_totals'][0][
            'statement_scope']['preceding_navigation_sources']],
            ['See accompanying Notes.','57','Table of Contents'])
        with self.assertRaisesRegex(ValueError,'STATEMENT_HEADING_SCOPE_UNRESOLVED'):
            self.prepare(change=change_intro('<div>Only Subsidiary Beta is included.</div>'))

    def test_reported_late_date_and_cost_group_qualifiers_are_not_hidden(self):
        from vnext.canonical import sha256_bytes
        def insert(before,text):
            def change(primary,xml,annual,source_facts):
                raw=primary['raw_bytes'].replace(before,text.encode()+before)
                primary['raw_bytes']=raw
                primary['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=raw)
            return change
        for day in (30,31):
            change=insert(b'<tr><td>Product revenues</td>',
                '<tr><td>Fiscal Year Ended December '+str(day)+',</td><td>57</td></tr>')
            with self.subTest(day=day):
                if day==30:
                    with self.assertRaisesRegex(ValueError,'VISIBLE_END_DAY_CONFLICT'):
                        self.prepare(change=change)
                else:
                    self.assertEqual(self.prepare(change=change)[0]['results']['B01']['value'],'58496000000')
        for text in ['Operating expenses (Europe):','Cost of revenues (Subsidiary):']:
            with self.subTest(text=text),self.assertRaisesRegex(ValueError,'STATEMENT_LOCAL_SCOPE_UNRESOLVED'):
                self.prepare(change=insert(b'<tr><td>Cost of sales</td>',
                    '<tr><td>'+text+'</td><td></td></tr>'))


class HistoricalPairedRevenueAdmissionTest(unittest.TestCase):
    """Small real-format originals; no constructed company result is accepted."""

    def prepared_claims(self):
        from tests.vnext.test_selected_revenue_scope_v1 import originals, facts, APPROVED
        from types import SimpleNamespace
        primary, xml, annual = originals()
        primary['raw_blob'] = {'media_type': 'text/html'}
        xml['raw_blob'] = {'media_type': 'application/xml'}
        # A source-format control for native totals; label selection has its own
        # actual-source and wrong-label regressions in the received shared API.
        reader = SimpleNamespace(auditor_filing=lambda f: [primary, xml],
                                 read=lambda *a, **k: {'raw_bytes': b'{}'})
        claims = [{'claim_kind': 'COMPANYFACTS_NUMERIC_FACT', 'verified_claim_id': 'constructed-'+str(i),
                   'locator': {'concept': fact['concept'].split(':')[-1],
                               'period_start': fact['period_start'], 'period_end': fact['period_end']},
                   'attributes': {'entity': fact['entity'], 'accession': fact['accession']},
                   'value': fact['value'], 'unit': fact['unit']}
                  for i, fact in enumerate(facts(annual))]
        return reader, annual, claims, APPROVED

    def admit(self, reader, annual, claims, concepts):
        with patch('vnext.historical_fiscal_labels.resolve_selected_fiscal_year_label', return_value=None):
            return cases._revenue_claims_admitted_by_original(reader=reader, prepared=annual,
                filing=annual['filing'], period=annual['table_input']['target_period'],
                claims=claims, concepts=concepts)

    def test_total_admission_keeps_original_claim_id_and_never_retags_its_locator(self):
        reader, annual, claims, concepts = self.prepared_claims()
        before = copy.deepcopy(claims)
        admitted, scope = self.admit(reader, annual, claims, concepts)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertEqual(len(admitted), 1)
        self.assertIs(admitted[0], claims[1])
        self.assertEqual(admitted[0]['locator']['concept'], 'Revenues')
        self.assertEqual(claims, before)

    def test_wrong_unit_entity_accession_or_amount_cannot_supply_the_original_total(self):
        for key in ('unit', 'entity', 'accession', 'value', 'concept', 'period'):
            reader, annual, claims, concepts = self.prepared_claims()
            if key in ('entity', 'accession'):claims[1]['attributes'][key] = 'wrong'
            elif key == 'unit':claims[1]['unit'] = 'EUR'
            elif key == 'concept':claims[1]['locator']['concept'] = 'SalesRevenueNet'
            elif key == 'period':claims[1]['locator']['period_end'] = '2025-12-30'
            else:claims[1]['value'] = '58497000000'
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.admit(reader, annual, claims, concepts)

    def test_prior_period_comparisons_stay_for_the_shared_comparability_guard(self):
        reader, annual, claims, concepts = self.prepared_claims()
        comparative = copy.deepcopy(claims[0]); comparative['verified_claim_id'] = 'constructed-comparison'
        comparative['locator'].update(period_start='2024-01-01', period_end='2024-12-31')
        claims.append(comparative)
        admitted, _ = self.admit(reader, annual, claims, concepts)
        self.assertEqual(admitted, [claims[1], comparative])

    def test_missing_scope_and_conflicting_original_dates_are_not_complete_revenue(self):
        reader, annual, claims, concepts = self.prepared_claims()
        with patch('vnext.selected_reported_revenue_v2.reported_revenue_scope',
                   return_value={'complete_scope_proven': False}), \
                patch('vnext.selected_revenue_scope_v1.selected_revenue_scope',
                      return_value={'complete_scope_proven': False}):
            with self.assertRaisesRegex(ValueError, 'COMPLETE_SCOPE_UNPROVEN'):
                self.admit(reader, annual, claims, concepts)
        annual['table_input']['target_period']['period_start'] = '2025-02-01'
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_PERIOD_CHANGED'):
            self.admit(reader, annual, claims, concepts)


class HistoricalPairedRevenueCaseTest(unittest.TestCase):
    """Constructed full adapter control; graph stubs are not financial evidence."""

    def case(self, *, unresolved_role=None, wrong_operand=False):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from tests.vnext.test_selected_revenue_scope_v1 import originals
        from vnext.specs import compile_spec_file
        primary, xml, annual = originals()
        annual.update(amendments=[], subject_policy={'mode': 'CONTINUOUS_PRIMARY'}, source_proofs=[])
        prior = {**annual['filing'], 'accessionNumber': '0000000001-25-000002', 'reportDate': '2024-12-31'}
        old = {**primary, 'raw_bytes': primary['raw_bytes'].replace(b'2025', b'2024')}
        reader = SimpleNamespace(read=lambda *a, **k: primary,
            primary=lambda filing, **k: primary if filing == annual['filing'] else old,
            proofs={}, records={})
        current_claim = {'verified_claim_id': 'current-total', 'locator': {'concept': 'Revenues',
            'period_start': '2025-01-01', 'period_end': '2025-12-31'},
            'attributes': {'accession': annual['filing']['accessionNumber']}, 'value': '58496000000', 'unit': 'USD'}
        prior_claim = {'verified_claim_id': 'prior-total', 'locator': {'concept': 'Revenues',
            'period_start': '2024-01-01', 'period_end': '2024-12-31'},
            'attributes': {'accession': prior['accessionNumber']}, 'value': '100330000000', 'unit': 'USD'}
        spec = compile_spec_file(path=cases.ROOT/'catalog/ordinary_zero_ai/B02.md', dependency_specs={})
        def scope(**args):
            role = 'current' if args['filing'] == annual['filing'] else 'prior'
            if role == unresolved_role:
                raise cases.StatementCaseError('HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN', 'IMPLEMENTATION_GAP')
            return args['claims'], {'scope_id': 'constructed-'+role, 'status': 'REPORTED_CONSOLIDATED_TOTAL',
                'complete_scope_proven': True, 'full_evidence': {'original': 'kept only in assessments'}}
        with ExitStack() as stack:
            registry = {'company_id': annual['company_id'], 'entity_continuity_status': 'continuous'}
            values = {'resolve_period_selection': {'prior_filing': prior},
                'prepare_historical_annual_input': annual, '_Sources': reader,
                '_registry_rows': [registry], 'repository_company_traits': [], 'metric_is_applicable': True,
                'installed_ordinary_spec_documents': {'B02': {'compiled_spec': spec, 'path': 'catalog/ordinary_zero_ai/B02.md'}},
                'filing_inventory': {}, 'prior_filing': (prior, primary),
                '_load_deterministic_catalog': {'metrics': {'B02': {'branches': [{'components': [
                    {'accession_role': role, 'approved_concepts': ['Revenues']} for role in ('current','prior')]}]}}},
                'verify_ordinary_source_proofs': {}}
            for name, value in values.items():stack.enter_context(patch.object(cases, name, return_value=value))
            stack.enter_context(patch.object(cases, '_filing_source', side_effect=[
                ({'manifest': {}}, [current_claim]), ({'manifest': {}}, [prior_claim])]))
            stack.enter_context(patch.object(cases, '_revenue_claims_admitted_by_original', side_effect=scope))
            actual_claims = [current_claim, prior_claim]
            if wrong_operand:
                actual_claims = [dict(current_claim, verified_claim_id='foreign-operand'), prior_claim]
            graph = stack.enter_context(patch.object(cases, '_deterministic_metric_graph', return_value={
                'result': {'publication': 'PUBLISHED'}, 'trace': {}, 'observation': None,
                'claims': actual_claims}))
            case = cases.prepare_historical_statement_year_case(repo_root=Path('/constructed'),
                company_id=annual['company_id'], metric_id='B02', fiscal_year=2025)
            return case, graph.call_count

    def test_both_original_scopes_reach_the_one_graph_and_daily_summary_is_bounded(self):
        case, calls = self.case()
        self.assertEqual(calls, 1)
        full = case['input_assessments']['historical_statement']['paired_revenue_scopes']
        self.assertEqual(set(full), {'current', 'prior'})
        self.assertTrue(all('full_evidence' in s for s in full.values()))
        self.assertTrue(all('full_evidence' not in s for s in case['selection']['paired_revenue_scopes'].values()))

    def test_one_unproved_role_withholds_whole_growth_before_graph(self):
        for role in ('current', 'prior'):
            with self.subTest(role=role):
                case, calls = self.case(unresolved_role=role)
                self.assertEqual(calls, 0)
                self.assertIsNone(case['results']['B02']['value'])
                self.assertEqual(case['results']['B02']['reason_code'], 'HISTORICAL_PAIRED_REVENUE_SCOPE_UNRESOLVED')
                self.assertEqual(case['input_assessments']['historical_statement']['unresolved_revenue_role'], role)

    def test_graph_cannot_select_an_operand_outside_the_admitted_original_claims(self):
        with self.assertRaisesRegex(ValueError, 'SELECTED_OPERAND_CHANGED'):
            self.case(wrong_operand=True)


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


class HistoricalStructuralApplicabilityTest(unittest.TestCase):
    def setup_metadata(self):
        prepared={'entity':'1','company_id':'constructed','amendments':[],
            'subject_policy':{'mode':'CONTINUOUS_PRIMARY','selected_cik':'1',
                'cross_entity_combination_authorized':False},
            'table_input':{'target_period':{'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}},
            'filing':{'accessionNumber':'constructed'},'source_proofs':[]}
        registry={'company_id':'constructed','primary_cik':'1','entity_continuity_status':'continuous'}
        return prepared,registry

    def test_bank_trait_is_na_before_any_amount_selection(self):
        prepared,registry=self.setup_metadata()
        with patch.object(cases,'resolve_period_selection',return_value={}), \
                patch.object(cases,'prepare_historical_annual_input',return_value=prepared), \
                patch.object(cases,'_registry_rows',return_value=[registry]), \
                patch.object(cases,'repository_company_traits',return_value=['financial']), \
                patch.object(cases,'_metadata_outcome_case',side_effect=lambda **k:k) as output, \
                patch.object(cases,'_filing_source') as facts, \
                patch.object(cases,'_deterministic_metric_graph') as graph:
            r=cases.prepare_historical_current_annual_year_case(repo_root=Path('/constructed'),
                company_id='constructed',metric_id='B07',fiscal_year=2024)
        result=r['graph']['result']
        self.assertEqual('N_A_STRUCTURAL',result['applicability'])
        self.assertEqual('TRAIT_NOT_APPLICABLE',result['reason_code'])
        self.assertIsNone(result['value'])
        self.assertFalse(r['assessment']['statement_values_used'])
        facts.assert_not_called();graph.assert_not_called();self.assertEqual(1,output.call_count)

    def test_applicable_company_does_not_skip_its_source_requirements(self):
        prepared,registry=self.setup_metadata()
        with patch.object(cases,'resolve_period_selection',return_value={}), \
                patch.object(cases,'prepare_historical_annual_input',return_value=prepared), \
                patch.object(cases,'_registry_rows',return_value=[registry]), \
                patch.object(cases,'repository_company_traits',return_value=['non_financial']), \
                patch.object(cases,'_metadata_outcome_case') as output, \
                patch.object(cases,'_Sources',side_effect=RuntimeError('CONSTRUCTED_SOURCE_REQUIRED')):
            with self.assertRaisesRegex(RuntimeError,'CONSTRUCTED_SOURCE_REQUIRED'):
                cases.prepare_historical_current_annual_year_case(repo_root=Path('/constructed'),
                    company_id='constructed',metric_id='B07',fiscal_year=2024)
        output.assert_not_called()
