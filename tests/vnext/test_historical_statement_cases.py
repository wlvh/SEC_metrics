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
                        'amendments': amendments, 'entity':'1', 'subject_policy': {'mode': mode}}), \
                    patch.object(cases, '_Sources'), \
                    patch.object(cases, '_statement_amendment_checks', side_effect=cases.StatementCaseError(
                        'HISTORICAL_STATEMENT_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED','IMPLEMENTATION_GAP')), \
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

    def test_unproven_new_expense_proof_does_not_block_existing_b01_fallback(self):
        import re
        from vnext.canonical import sha256_bytes
        def complete_costs_with_gain(primary,xml,annual,source_facts):
            source_facts[:]=[source_facts[1]]
            for source in (primary,xml):
                raw=source['raw_bytes']
                for label in (b'Product revenues',b'Alliance revenues'):
                    raw=re.sub(rb'<tr><td>'+label+rb'.*?</tr>',b'',raw)
                raw=raw.replace(b'Total revenues',b'Revenues').replace(b'Cost of sales',b'Total costs and expenses').replace(b'CostOfGoodsAndServicesSold',b'CostsAndExpenses')
                raw=raw.replace(b'<tr><td>Total costs and expenses',b'<tr><td>Costs and expenses:</td><td></td></tr><tr><td>Total costs and expenses')
                extra=(b'<tr><td>Gains on dispositions</td><td><ix:nonFraction name="issuer:Gain" '
                    b'contextRef="annual" unitRef="usd" scale="6" decimals="-6">56</ix:nonFraction></td></tr>'
                    b'<tr><td>Operating income</td><td><ix:nonFraction name="us-gaap:OperatingIncomeLoss" '
                    b'contextRef="annual" unitRef="usd" scale="6" decimals="-6">48552</ix:nonFraction></td></tr>')
                raw=raw.replace(b'<tr><td>Net income',extra+b'<tr><td>Net income')
                source['raw_bytes']=raw;source['source_reference']['raw_asset_id']='sha256:'+sha256_bytes(content=raw)
        value,_,_=self.prepare(change=complete_costs_with_gain)
        self.assertEqual('58496000000',value['results']['B01']['value'])
        scope=value['input_assessments']['historical_statement']['selected_revenue_scope']
        self.assertEqual('SELECTED_REVENUE_COMPONENT_ADMISSION_V1',scope['method'])
        self.assertEqual('NO_DEMONSTRATED_SPLIT',scope['status'])
        self.assertFalse(scope['complete_scope_proven'])

    def test_display_is_bounded_while_complete_scope_evidence_is_retained(self):
        value, _, _ = self.prepare()
        full = value['input_assessments']['historical_statement']['selected_revenue_scope']
        self.assertTrue(full['reported_totals'])
        self.assertEqual(full['method'],'SELECTED_REPORTED_SINGLE_REVENUE_LINE_V1')
        self.assertTrue(full['single_revenue_line_allowed'])
        self.assertEqual(full['status'], 'REPORTED_CONSOLIDATED_TOTAL')
        self.assertTrue(full['complete_scope_proven'])
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

    def test_income_range_registers_the_saved_requirement_reader_it_actually_calls(self):
        from tests.vnext.test_company_fiscal_range import CompanyFiscalRangeTest
        from tests.vnext.processing_dependency_checks import processing_calls, assert_processing_calls
        from vnext import ordinary_current_update as update
        from vnext.normal_source_authority import ROOT
        fixture = CompanyFiscalRangeTest()
        fixture.setUp()
        try:
            before = fixture.fixture.digest_tree()
            with processing_calls(ROOT) as observed:
                discovery = fixture.discover()
            self.assertEqual('FISCAL_RANGE_RESOLVED', discovery['status'])
            dependency = 'scripts/vnext/normal_source_requirements.py'
            self.assertIn('require', observed[dependency])
            for metric, files in (('B01', cases.INCOME_PROCESSING_FILES),
                                  ('B02', cases.PAIRED_REVENUE_PROCESSING_FILES)):
                with self.subTest(metric=metric):
                    assert_processing_calls({dependency: observed[dependency]},
                        update._configuration(fixture.source, discovery['company_id'], metric), files)
            self.assertEqual(before, fixture.fixture.digest_tree())
            self.assertNotIn(dependency, cases.PROCESSING_FILES)
        finally:
            fixture.doCleanups()

    def test_sole_consolidated_revenue_path_is_explicitly_consumed_before_priority_selection(self):
        from vnext import selected_reported_revenue_v2 as reported
        with patch.object(reported, 'reported_revenue_scope', wraps=reported.reported_revenue_scope) as shared:
            value, source_facts, calculator = self.prepare()
        self.assertIs(True, shared.call_args.kwargs.get('allow_single_revenue_line'))
        self.assertEqual('YEAR_QUARTER_OR_DATE',shared.call_args.kwargs.get('dei_release'))
        self.assertEqual('YEAR_OR_DATE_RELEASE',shared.call_args.kwargs['namespace_policy'])
        self.assertTrue(value['input_assessments']['historical_statement'][
            'selected_revenue_scope']['complete_scope_proven'])
        self.assertEqual([source_facts[1]], calculator.call_args.kwargs['structured_facts'])
        self.assertEqual('58496000000', value['results']['B01']['value'])

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

    def test_group_total_opt_in_reaches_shared_original_reader(self):
        reader, annual, claims, concepts = self.prepared_claims()
        with patch('vnext.selected_reported_revenue_v2.reported_revenue_scope',
                   return_value={'complete_scope_proven': False}) as shared:
            admitted, scope = self.admit(reader, annual, claims, concepts)
        self.assertIs(True, shared.call_args.kwargs['allow_statement_group_totals'])
        self.assertIs(True, shared.call_args.kwargs['allow_single_segment_revenue'])
        self.assertIs(True, shared.call_args.kwargs['allow_single_revenue_line'])
        self.assertEqual('YEAR_QUARTER_OR_DATE', shared.call_args.kwargs['dei_release'])
        self.assertEqual('YEAR_OR_DATE_RELEASE', shared.call_args.kwargs['namespace_policy'])
        self.assertEqual(annual['filing'], shared.call_args.kwargs['annual']['filing'])
        self.assertEqual(annual['table_input']['target_period'],
                         shared.call_args.kwargs['annual']['table_input']['target_period'])
        self.assertTrue(scope['complete_scope_proven'])
        self.assertTrue(admitted)
        from vnext.selected_reported_revenue_v2 import STATEMENT_GROUP_PROCESSING_FILES
        self.assertTrue(set(STATEMENT_GROUP_PROCESSING_FILES).issubset(
            cases.PAIRED_REVENUE_PROCESSING_FILES))
        self.assertEqual(len(cases.PAIRED_REVENUE_PROCESSING_FILES),
                         len(set(cases.PAIRED_REVENUE_PROCESSING_FILES)))

    def test_official_quarter_release_keeps_original_claim_and_scope_binding(self):
        from types import SimpleNamespace
        from tests.vnext.test_statement_group_totals import closed_statement
        from tests.vnext.test_selected_reported_revenue_v2 import changed
        primary, annual = closed_statement()
        primary = changed(primary, primary['raw_bytes'].replace(
            b'http://xbrl.sec.gov/dei/2025', b'http://xbrl.sec.gov/dei/2025q4'))
        primary['raw_blob'] = {'media_type': 'text/html'}
        xml = {**primary, 'raw_blob': {'media_type': 'application/xml'}}
        reader = SimpleNamespace(auditor_filing=lambda f: [primary, xml],
                                 read=lambda *a, **k: {'raw_bytes': b'{}'})
        _, _, claims, concepts = self.prepared_claims()
        admitted, scope = self.admit(reader, annual, claims, concepts)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertEqual('YEAR_QUARTER_OR_DATE', scope['dei_release'])
        self.assertEqual([claims[1]], admitted)
        self.assertIs(claims[1], admitted[0])

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

    def test_numeric_note_reference_preserves_original_total_but_scope_parentheses_do_not(self):
        from types import SimpleNamespace
        from tests.vnext.test_selected_reported_revenue_v2 import changed
        # Constructed format controls at the actual historical adapter.
        # Real Ford originals are separately exercised through the company CLI.
        for label, accepted in [('Total revenues (Note 4)', True),
                                ('Total revenues (4)', True),
                                ('Total revenues (Europe)', False),
                                ('Total revenues (Subsidiary)', False),
                                ('Total revenues (Note 4, Europe)', False)]:
            reader, annual, claims, concepts = self.prepared_claims()
            primary, xml = reader.auditor_filing(annual['filing'])
            primary = changed(primary, primary['raw_bytes'].replace(b'Total revenues', label.encode()))
            selected = SimpleNamespace(auditor_filing=lambda filing: [primary, xml], read=reader.read)
            with self.subTest(label=label):
                if accepted:
                    admitted, scope = self.admit(selected, annual, claims, concepts)
                    self.assertTrue(scope['complete_scope_proven'])
                    self.assertEqual([claims[1]], admitted)
                    self.assertIs(claims[1], admitted[0])
                else:
                    with self.assertRaisesRegex(ValueError, 'COMPLETE_SCOPE_UNPROVEN'):
                        self.admit(selected, annual, claims, concepts)

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

    def test_stopped_single_line_does_not_gain_new_scope_while_explicit_total_keeps_working(self):
        from tests.vnext.test_single_revenue_line import single_statement
        from types import SimpleNamespace
        primary, annual = single_statement()
        primary['raw_blob'] = {'media_type': 'text/html'}
        reader = SimpleNamespace(auditor_filing=lambda f: [primary],
                                 read=lambda *a, **k: {'raw_bytes': b'{}'})
        _, _, claims, concepts = self.prepared_claims()
        with patch.object(cases, 'PAIRED_SINGLE_REVENUE_LINE_ENABLED', False), \
                self.assertRaisesRegex(ValueError, 'COMPLETE_SCOPE_UNPROVEN'):
            self.admit(reader, annual, claims, concepts)
        original_reader, original_annual, original_claims, concepts = self.prepared_claims()
        admitted, scope = self.admit(original_reader, original_annual, original_claims, concepts)
        self.assertTrue(scope['complete_scope_proven'])
        self.assertEqual(admitted, [original_claims[1]])

    def test_fixed_single_line_consumer_keeps_total_and_rejects_appended_cell_amount(self):
        from tests.vnext.test_single_revenue_line import single_statement
        from tests.vnext.test_selected_reported_revenue_v2 import changed
        from types import SimpleNamespace
        from tests.vnext.test_selected_revenue_scope_v1 import APPROVED
        source, annual = single_statement()
        _, _, claims, _ = self.prepared_claims()
        # Remove the component claim; this original source reports one total.
        claims = [claims[1]]
        for extra in (None, b'<span> 100</span>'):
            raw = source['raw_bytes'] if extra is None else source['raw_bytes'].replace(
                b'>58496</ix:nonFraction>', b'>58496</ix:nonFraction>'+extra)
            primary = changed(source, raw); primary['raw_blob'] = {'media_type':'text/html'}
            reader = SimpleNamespace(auditor_filing=lambda f: [primary],
                                     read=lambda *a, **k: {'raw_bytes': b'{}'})
            if extra is None:
                admitted, scope = self.admit(reader, annual, claims, APPROVED)
                self.assertEqual(admitted, claims); self.assertTrue(scope['complete_scope_proven'])
            else:
                with self.assertRaisesRegex(ValueError, 'SELECTED_CELL_TEXT_CONFLICT'):
                    self.admit(reader, annual, claims, APPROVED)

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

    def case(self, *, unresolved_role=None, wrong_operand=False, amendment=None,
             prior_amendment=None):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from tests.vnext.test_selected_revenue_scope_v1 import originals
        from vnext.specs import compile_spec_file
        primary, xml, annual = originals()
        annual.update(amendments=[] if amendment is None else [{'form':'10-K/A'}],
            subject_policy={'mode': 'CONTINUOUS_PRIMARY'}, source_proofs=[])
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
                raise cases.StatementCaseError('HISTORICAL_PAIRED_REVENUE_COMPLETE_SCOPE_UNPROVEN',
                    'IMPLEMENTATION_GAP', revenue_scope={'scope_id': 'constructed-unresolved-'+role,
                        'status': 'NO_DEMONSTRATED_SPLIT', 'complete_scope_proven': False,
                        'full_evidence': {'original': 'unproven source scope is retained'}})
            return args['claims'], {'scope_id': 'constructed-'+role, 'status': 'REPORTED_CONSOLIDATED_TOTAL',
                'complete_scope_proven': True, 'full_evidence': {'original': 'kept only in assessments'}}
        with ExitStack() as stack:
            registry = {'company_id': annual['company_id'], 'entity_continuity_status': 'continuous'}
            selection = {'prior_filing': prior}
            if prior_amendment is not None:
                selection.update(prior_report_end=prior['reportDate'],
                    prior_amendments=[{**prior, 'form':'10-K/A', 'accessionNumber':'constructed-amendment'}])
            def amendments(reader, prepared, **kwargs):
                if 'namespace_policy' not in kwargs:
                    return [] if amendment is None else [amendment]
                self.assertEqual('YEAR_QUARTER_OR_DATE',kwargs['namespace_policy'])
                self.assertEqual(prior,prepared['filing'])
                self.assertEqual(selection['prior_amendments'],prepared['amendments'])
                kwargs['checks'].append(prior_amendment)
                if prior_amendment['issues']:
                    raise cases.StatementCaseError('HISTORICAL_STATEMENT_AMENDMENT_ORIGINAL_VALUES_NOT_PROVEN',
                                                   'AMENDMENT_INPUT_NOT_CLEARED')
                return kwargs['checks']
            values = {'resolve_period_selection': selection,
                'prepare_historical_annual_input': annual, '_Sources': reader,
                '_registry_rows': [registry], 'repository_company_traits': [], 'metric_is_applicable': True,
                'installed_ordinary_spec_documents': {'B02': {'compiled_spec': spec, 'path': 'catalog/ordinary_zero_ai/B02.md'}},
                'filing_inventory': {}, 'prior_filing': (prior, primary),
                '_load_deterministic_catalog': {'metrics': {'B02': {'branches': [{'components': [
                    {'accession_role': role, 'approved_concepts': ['Revenues']} for role in ('current','prior')]}]}}},
                'verify_ordinary_source_proofs': {}}
            for name, value in values.items():stack.enter_context(patch.object(cases, name, return_value=value))
            stack.enter_context(patch.object(cases,'_statement_amendment_checks',side_effect=amendments))
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

    def test_prior_amendment_must_clear_before_prior_claims_and_scope(self):
        check={'scope_id':'constructed-prior-scope','classification':'UNRESOLVED',
               'fiscal_window_unchanged':True,'unchanged_input_classes':['FISCAL_EVENT_WINDOW'],
               'issues':['AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN'],'policy_hash':'constructed-policy',
               'original_statement_admission_requires_further_review':True,
               'full_source_evidence':{'not_a_real_financial_conclusion':True}}
        case,calls=self.case(prior_amendment=check)
        self.assertEqual(0,calls)
        self.assertIsNone(case['results']['B02']['value'])
        full=case['input_assessments']['historical_statement']
        self.assertEqual('AMENDMENT_INPUT_NOT_CLEARED',full['category'])
        self.assertEqual('prior',full['unresolved_amendment_role'])
        self.assertEqual('10-K',full['prior_original_filing']['form'])
        self.assertEqual(['10-K/A'],[f['form'] for f in full['prior_amendment_filings']])
        self.assertEqual('2024-12-31',case['input_binding']['actual_periods']['prior']['period_end'])
        self.assertEqual('10-K',case['input_binding']['filings']['prior']['form'])
        self.assertNotIn('prior',case['input_binding']['claims_by_accession_role'])
        self.assertEqual([check],full['prior_statement_amendment_checks'])
        self.assertEqual({},case['input_binding']['paired_revenue_scopes']
                         if 'paired_revenue_scopes' in case['input_binding'] else {})
        self.assertNotIn('full_source_evidence',case['selection']['prior_statement_amendment_checks'][0])
        self.assertEqual('YEAR_QUARTER_OR_DATE',case['input_binding']['prior_amendment_namespace_policy'])

    def test_proven_prior_property_still_requires_both_original_revenue_scopes(self):
        check={'scope_id':'constructed-prior-link','classification':'EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15',
               'fiscal_window_unchanged':True,'unchanged_input_classes':['ORIGINAL_STATEMENT_VALUES'],
               'issues':[],'policy_hash':'constructed-policy',
               'original_statement_admission_requires_further_review':False}
        for role in (None,'prior'):
            with self.subTest(role=role):
                case,calls=self.case(prior_amendment=check,unresolved_role=role)
                self.assertEqual(1 if role is None else 0,calls)
                full=case['input_assessments']['historical_statement']
                self.assertEqual([check],full['prior_statement_amendment_checks'])
                self.assertEqual({'current','prior'},set(full['paired_revenue_scopes']))

    def test_link_only_amendment_proof_and_both_revenue_scopes_survive_together(self):
        # Constructed consumer control; shared amendment classification is
        # tested separately. This protects the two adjacent merge additions.
        amendment = {'scope_id':'constructed-link-correction',
            'classification':'EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15',
            'fiscal_window_unchanged':True, 'issues':[],
            'unchanged_input_classes':['ORIGINAL_STATEMENT_VALUES'],
            'policy_hash':'constructed-policy'}
        for unresolved_role in (None, 'prior'):
            with self.subTest(unresolved_role=unresolved_role):
                case, calls = self.case(amendment=amendment, unresolved_role=unresolved_role)
                assessment = case['input_assessments']['historical_statement']
                self.assertEqual([amendment], assessment['statement_amendment_checks'])
                self.assertEqual({'current','prior'}, set(assessment['paired_revenue_scopes']))
                self.assertEqual([amendment], case['input_binding']['statement_amendment_checks'])
                self.assertEqual(1 if unresolved_role is None else 0, calls)
                if unresolved_role:
                    self.assertIsNone(case['results']['B02']['value'])
                    self.assertEqual('HISTORICAL_PAIRED_REVENUE_SCOPE_UNRESOLVED',
                        case['results']['B02']['reason_code'])

    def test_one_unproved_role_withholds_whole_growth_before_graph(self):
        for role in ('current', 'prior'):
            with self.subTest(role=role):
                case, calls = self.case(unresolved_role=role)
                self.assertEqual(calls, 0)
                self.assertIsNone(case['results']['B02']['value'])
                self.assertEqual(case['results']['B02']['reason_code'], 'HISTORICAL_PAIRED_REVENUE_SCOPE_UNRESOLVED')
                self.assertEqual(case['input_assessments']['historical_statement']['unresolved_revenue_role'], role)
                self.assertEqual(case['selection']['paired_revenue_scopes'][role]['status'],
                                 'NO_DEMONSTRATED_SPLIT')
                self.assertFalse(case['selection']['paired_revenue_scopes'][role]['complete_scope_proven'])
                self.assertIn('full_evidence', case['input_assessments']['historical_statement']
                              ['paired_revenue_scopes'][role])

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

    def test_uncleared_amendment_and_successor_keep_the_existing_rejection(self):
        for amendments, mode in [([{'form':'10-K/A'}], 'CONTINUOUS_PRIMARY'),
                                 ([], 'SUCCESSOR_PREDECESSOR')]:
            with self.subTest(amendments=amendments,mode=mode), \
                    patch.object(cases,'resolve_period_selection',return_value={}), \
                    patch.object(cases,'prepare_historical_annual_input',return_value={
                        'amendments':amendments,'entity':'1','subject_policy':{'mode':mode}}), \
                    patch.object(cases,'_Sources'), \
                    patch.object(cases,'_statement_amendment_checks',side_effect=cases.StatementCaseError(
                        'HISTORICAL_STATEMENT_AMENDMENT_ORIGINAL_VALUES_NOT_PROVEN','AMENDMENT_INPUT_NOT_CLEARED')), \
                    patch.object(cases,'installed_ordinary_spec_documents') as specs, \
                    patch.object(cases,'_deterministic_metric_graph') as graph:
                with self.assertRaises(cases.StatementCaseError) as caught:
                    cases.prepare_historical_current_annual_year_case(repo_root=Path('/constructed'),
                        company_id='constructed',metric_id='B07',fiscal_year=2024)
                self.assertEqual('AMENDMENT_INPUT_NOT_CLEARED' if amendments else 'IMPLEMENTATION_GAP',
                                 caught.exception.category)
                specs.assert_not_called();graph.assert_not_called()

    def test_b07_consumes_the_same_proved_link_scope_before_specification(self):
        period={'fiscal_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31'}
        annual={'amendments':[{'form':'10-K/A'}],'entity':'1',
                'subject_policy':{'mode':'CONTINUOUS_PRIMARY'},'table_input':{'target_period':period}}
        checked={'scope_id':'constructed-proved-link','classification':
                 'EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15'}
        with patch.object(cases,'resolve_period_selection',return_value={}), \
             patch.object(cases,'prepare_historical_annual_input',return_value=annual), \
             patch.object(cases,'_Sources') as reader, \
             patch.object(cases,'_statement_amendment_checks',return_value=[checked]) as scope, \
             patch.object(cases,'installed_ordinary_spec_documents',side_effect=ValueError('stop at existing Spec')):
            with self.assertRaisesRegex(ValueError,'stop at existing Spec'):
                cases.prepare_historical_current_annual_year_case(repo_root=Path('/constructed'),
                    company_id='constructed',metric_id='B07',fiscal_year=2024)
        scope.assert_called_once_with(reader.return_value,annual,metric_id='B07',statement_properties=[])


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


class HistoricalStatementAmendmentTest(unittest.TestCase):
    def prepared(self):
        return {'company_id':'constructed','entity':'1',
            'filing':{'accessionNumber':'original','form':'10-K'},
            'amendments':[{'accessionNumber':'amended','form':'10-K/A'}]}

    def checked(self):
        return {'scope_id':'constructed-scope','classification':'EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15',
            'fiscal_window_unchanged':True,'issues':[],
            'unchanged_input_classes':['FISCAL_EVENT_WINDOW','ORIGINAL_STATEMENT_VALUES'],
            'original_statement_admission_requires_further_review':False}

    def test_no_amendment_does_not_read_or_classify_sources(self):
        from unittest.mock import Mock
        reader=Mock();prepared=self.prepared();prepared['amendments']=[]
        self.assertEqual([],cases._statement_amendment_checks(reader,prepared))
        reader.primary.assert_not_called()

    def test_only_explicit_original_statement_proof_is_received(self):
        from unittest.mock import Mock
        reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed',
            'raw_blob':{'raw_asset_id':'constructed'},'source_reference':{'source_reference_id':'constructed'}}
        checked=self.checked()
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=checked) as inspect:
            self.assertEqual([checked],cases._statement_amendment_checks(reader,self.prepared()))
        self.assertEqual('inline-paragraphs-v2',inspect.call_args.kwargs['note_layout'])
        self.assertEqual('constructed',inspect.call_args.kwargs['company_id'])
        self.assertEqual('original',inspect.call_args.kwargs['original']['filing']['accessionNumber'])
        self.assertEqual('amended',inspect.call_args.kwargs['amendment']['filing']['accessionNumber'])

    def test_event_only_part3_period_change_issue_or_pending_review_cannot_admit_values(self):
        from unittest.mock import Mock
        for change in ['event_only','period','issue','review']:
            checked=self.checked()
            if change=='event_only':checked['unchanged_input_classes']=['FISCAL_EVENT_WINDOW']
            elif change=='period':checked['fiscal_window_unchanged']=False
            elif change=='issue':checked['issues']=['CONSTRUCTED_CORRECTION']
            else:checked['original_statement_admission_requires_further_review']=True
            reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed','raw_blob':{},'source_reference':{}}
            with self.subTest(change=change),patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=checked):
                with self.assertRaisesRegex(cases.StatementCaseError,'ORIGINAL_VALUES_NOT_PROVEN') as error:
                    cases._statement_amendment_checks(reader,self.prepared())
                self.assertEqual('AMENDMENT_INPUT_NOT_CLEARED',error.exception.category)

    def test_all_amendments_must_pass_not_just_the_first(self):
        from unittest.mock import Mock
        prepared=self.prepared();prepared['amendments'].append({'accessionNumber':'second','form':'10-K/A'})
        good=self.checked();bad={**good,'unchanged_input_classes':['FISCAL_EVENT_WINDOW']}
        reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed','raw_blob':{},'source_reference':{}}
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',side_effect=[good,bad]):
            with self.assertRaisesRegex(cases.StatementCaseError,'ORIGINAL_VALUES_NOT_PROVEN'):
                cases._statement_amendment_checks(reader,prepared)

    def test_explicit_prior_policy_and_failed_scope_are_retained(self):
        from unittest.mock import Mock
        reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed','raw_blob':{},'source_reference':{}}
        checked={**self.checked(),'classification':'UNRESOLVED',
                 'issues':['AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN']}
        retained=[]
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=checked) as inspect:
            with self.assertRaisesRegex(cases.StatementCaseError,'ORIGINAL_VALUES_NOT_PROVEN'):
                cases._statement_amendment_checks(reader,self.prepared(),
                    namespace_policy='YEAR_QUARTER_OR_DATE',checks=retained)
        self.assertEqual([checked],retained)
        self.assertEqual('YEAR_QUARTER_OR_DATE',inspect.call_args.kwargs['namespace_policy'])

    def test_prior_reader_failure_is_not_missing_source_or_business_na(self):
        from unittest.mock import Mock
        from vnext.annual_amendment_scope import AmendmentScopeError
        reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed','raw_blob':{},'source_reference':{}}
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',
                   side_effect=AmendmentScopeError('AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED')):
            with self.assertRaisesRegex(cases.StatementCaseError,'AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED') as caught:
                cases._statement_amendment_checks(reader,self.prepared(),namespace_policy='YEAR_QUARTER_OR_DATE')
            self.assertEqual('AMENDMENT_INPUT_NOT_CLEARED',caught.exception.category)
            with self.assertRaises(AmendmentScopeError):
                cases._statement_amendment_checks(reader,self.prepared())

    def part_iii(self):
        return {**self.checked(),
            'classification':'PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS',
            'unchanged_input_classes':['FISCAL_EVENT_WINDOW'],
            'original_statement_admission_requires_further_review':True,
            'note_layout':'inline-paragraphs-v2'}

    def test_part_iii_income_consumption_keeps_source_scope_and_property_separate(self):
        from unittest.mock import Mock
        for metric in ('B01','B02','B03'):
            checked=self.part_iii();before=copy.deepcopy(checked);properties=[]
            reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed','raw_blob':{},'source_reference':{}}
            property_check={'original_scope_id':checked['scope_id'],
                'input_class':'CURRENT_ORIGINAL_INCOME_STATEMENT_VALUES',
                'income_correction_blocks':[], 'part_iii_details':{'constructed':True}}
            with self.subTest(metric=metric), \
                 patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=checked), \
                 patch('vnext.ordinary_income_input.inspect_income_amendment',return_value=property_check) as income:
                result=cases._statement_amendment_checks(reader,self.prepared(),
                    metric_id=metric,income_properties=properties)
            self.assertEqual([checked],result)
            self.assertEqual(before,checked)
            self.assertEqual([{'source_scope_id':checked['scope_id'],'metric_id':metric,
                              'income_property':property_check}],properties)
            self.assertEqual('inline-paragraphs-v2',income.call_args.args[0]['note_layout'])

    def test_part_iii_does_not_implicitly_cover_other_statement_metrics(self):
        from unittest.mock import Mock
        for metric in (None,'B05','B06'):
            reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed','raw_blob':{},'source_reference':{}}
            with self.subTest(metric=metric), \
                 patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=self.part_iii()), \
                 patch('vnext.ordinary_income_input.inspect_income_amendment') as income:
                with self.assertRaisesRegex(cases.StatementCaseError,'ORIGINAL_VALUES_NOT_PROVEN'):
                    cases._statement_amendment_checks(reader,self.prepared(),metric_id=metric,income_properties=[])
            income.assert_not_called()

    def statement_property_source(self, extra=''):
        from tests.vnext.test_income_amendment_paragraph_dispatch import IncomeParagraphDispatchTest
        from tests.vnext.test_instant_amendment_paragraph_api import filing_html
        from unittest.mock import Mock
        checked, raw = IncomeParagraphDispatchTest().scope(extra)
        reader = Mock()
        reader.primary.side_effect = [
            {'raw_bytes':filing_html(False),'raw_blob':{},
             'source_reference':checked['original']['document']['source_reference']},
            {'raw_bytes':raw,'raw_blob':{},
             'source_reference':checked['amendment']['document']['source_reference']}]
        return checked, raw, reader

    def test_explicit_metric_property_keeps_full_scope_and_roles_without_income_relabelling(self):
        for metric, roles in (('B04',['net_income']),('B07',[
                'aggregate_nonoperating','interest_expense','operating_income','pretax_income'])):
            checked, raw, reader = self.statement_property_source()
            before = copy.deepcopy(checked)
            properties = []
            with self.subTest(metric=metric), \
                 patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope', return_value=checked):
                actual = cases._statement_amendment_checks(reader,self.prepared(),
                    metric_id=metric,statement_properties=properties)
            self.assertEqual([checked],actual)
            self.assertEqual(before,checked)
            self.assertEqual(roles,properties[0]['statement_property']['covered_component_roles'])
            self.assertEqual(metric,properties[0]['statement_property']['metric_id'])
            self.assertTrue(checked['original_statement_admission_requires_further_review'])
            self.assertNotIn('ORIGINAL_STATEMENT_VALUES',checked['unchanged_input_classes'])

    def test_metric_property_without_retained_evidence_still_refuses(self):
        for metric in ('B04','B07'):
            checked, raw, reader = self.statement_property_source()
            with self.subTest(metric=metric), \
                 patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=checked), \
                 patch('vnext.statement_metric_amendment.inspect_statement_metric_amendment') as typed:
                with self.assertRaisesRegex(cases.StatementCaseError,'METRIC_AMENDMENT_EVIDENCE_TARGET_REQUIRED'):
                    cases._statement_amendment_checks(reader,self.prepared(),metric_id=metric)
            typed.assert_not_called()

    def test_wrong_metric_scope_roles_raw_reference_definition_or_property_id_are_rejected(self):
        from vnext.statement_metric_amendment import inspect_statement_metric_amendment
        from vnext.canonical import content_hash
        for changed in ('metric_id','original_scope_id','covered_component_roles','input_class',
                'amendment_raw_sha256','original_source_reference','metric_definition_sha256','property_id'):
            checked, raw, reader = self.statement_property_source()
            supplied = inspect_statement_metric_amendment(checked,raw,metric_id='B04')
            supplied[changed] = ['wrong-role'] if changed=='covered_component_roles' else 'wrong-binding'
            if changed != 'property_id':
                supplied['property_id']=content_hash(value={k:v for k,v in supplied.items() if k!='property_id'})
            with self.subTest(changed=changed), \
                 patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=checked), \
                 patch('vnext.statement_metric_amendment.inspect_statement_metric_amendment',return_value=supplied):
                with self.assertRaisesRegex(cases.StatementCaseError,'METRIC_AMENDMENT_PROPERTY_BINDING_CHANGED'):
                    cases._statement_amendment_checks(reader,self.prepared(),metric_id='B04',statement_properties=[])

    def test_metric_correction_and_new_table_amount_keep_the_source_refusal(self):
        for metric, extra in (('B04','<div>Our net income has been corrected.</div>'),
                ('B07','<div>Our interest expense has been revised.</div>'),
                ('B04','<table><tr><td>Net income</td><td>42</td></tr></table>')):
            checked, raw, reader = self.statement_property_source(extra)
            with self.subTest(metric=metric,extra=extra), \
                 patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=checked):
                with self.assertRaisesRegex(cases.StatementCaseError,'METRIC_AMENDMENT_PROPERTY_NOT_PROVEN') as rejected:
                    cases._statement_amendment_checks(reader,self.prepared(),metric_id=metric,statement_properties=[])
            self.assertEqual('AMENDMENT_INPUT_NOT_CLEARED',rejected.exception.category)

    def test_statement_metric_dependencies_are_explicit_only_for_the_consumers(self):
        for metric in ('B04','B07'):
            paths=cases.processing_files_for_statement_metric(metric)
            self.assertIn('scripts/vnext/statement_metric_amendment.py',paths)
            self.assertIn('scripts/vnext/table_grid.py',paths)
        for metric in ('B05','B01','B02'):
            self.assertEqual(cases.PROCESSING_FILES,cases.processing_files_for_statement_metric(metric))

    def test_explicit_property_reader_executes_only_declared_source_dependencies(self):
        from tests.vnext.processing_dependency_checks import processing_calls, assert_processing_calls
        from vnext.statement_metric_amendment import inspect_statement_metric_amendment
        from vnext import ordinary_current_update as update
        checked, raw, _ = self.statement_property_source()
        for metric in ('B04','B07'):
            with self.subTest(metric=metric), processing_calls(cases.ROOT) as observed:
                inspect_statement_metric_amendment(checked,raw,metric_id=metric)
            assert_processing_calls(observed,update._configuration(cases.ROOT,'marriott_international',metric),
                cases.processing_files_for_statement_metric(metric))

    def test_part_iii_income_rejection_and_wrong_property_binding_remain_failures(self):
        from unittest.mock import Mock
        from vnext.ordinary_income_input import IncomeInputError
        reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed','raw_blob':{},'source_reference':{}}
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=self.part_iii()), \
             patch('vnext.ordinary_income_input.inspect_income_amendment',
                   side_effect=IncomeInputError('AMENDMENT_INCOME_CORRECTION_UNRESOLVED')):
            with self.assertRaisesRegex(cases.StatementCaseError,'INCOME_CORRECTION_UNRESOLVED') as error:
                cases._statement_amendment_checks(reader,self.prepared(),metric_id='B02',income_properties=[])
        self.assertEqual('AMENDMENT_INPUT_NOT_CLEARED',error.exception.category)
        for change in ('scope','class'):
            property_check={'original_scope_id':'constructed-scope',
                'input_class':'CURRENT_ORIGINAL_INCOME_STATEMENT_VALUES'}
            property_check['original_scope_id' if change=='scope' else 'input_class']='wrong'
            with self.subTest(change=change), \
                 patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=self.part_iii()), \
                 patch('vnext.ordinary_income_input.inspect_income_amendment',return_value=property_check):
                with self.assertRaisesRegex(cases.StatementCaseError,'PROPERTY_BINDING_CHANGED'):
                    cases._statement_amendment_checks(reader,self.prepared(),metric_id='B01',income_properties=[])

    def test_part_iii_requires_identity_and_retained_income_evidence(self):
        from unittest.mock import Mock
        for changed in ({'fiscal_window_unchanged':False},{'issues':['CONSTRUCTED_FINANCIAL_CHANGE']}):
            reader=Mock();reader.primary.return_value={'raw_bytes':b'constructed','raw_blob':{},'source_reference':{}}
            with self.subTest(changed=changed), \
                 patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value={**self.part_iii(),**changed}), \
                 patch('vnext.ordinary_income_input.inspect_income_amendment') as income:
                with self.assertRaisesRegex(cases.StatementCaseError,'ORIGINAL_VALUES_NOT_PROVEN'):
                    cases._statement_amendment_checks(reader,self.prepared(),metric_id='B03',income_properties=[])
            income.assert_not_called()
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',return_value=self.part_iii()):
            with self.assertRaisesRegex(cases.StatementCaseError,'EVIDENCE_TARGET_REQUIRED'):
                cases._statement_amendment_checks(reader,self.prepared(),metric_id='B01')
