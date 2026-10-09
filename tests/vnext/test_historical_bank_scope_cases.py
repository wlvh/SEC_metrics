"""Constructed source controls use the real existing Spec and Calculator."""
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from vnext import historical_bank_scope_cases as bank


class HistoricalBankScopeCaseTest(TestCase):
    def prepare(self, *, metric_id='A09', applicable=True, amendments=None, mode='CONTINUOUS_PRIMARY',
                inspector=None):
        period = {'fiscal_year': 2021, 'period_start': '2021-01-01', 'period_end': '2021-12-31'}
        prepared = {'company_id': 'jpmorgan_chase', 'entity': '19617',
            'filing': {'accessionNumber': '0000019617-22-000272'},
            'table_input': {'target_period': period}, 'source_proofs': [],
            'amendments': amendments or [], 'subject_policy': {'mode': mode}}
        ref = {'source_reference_id': 'sha256:' + '1' * 64, 'raw_asset_id': 'sha256:' + '2' * 64,
            'accession': prepared['filing']['accessionNumber'], 'document_name': 'original.htm',
            'source_role': 'target_primary'}
        source = {'raw_bytes': b'constructed source control', 'source_reference': ref}
        inventory = {'raw_bytes': b'constructed inventory', 'source_reference': ref}
        reader = SimpleNamespace(records={}, proofs={}, read=lambda *a, **k: inventory,
                                 primary=lambda *a, **k: source)
        with ExitStack() as stack:
            selection = stack.enter_context(patch.object(bank, 'resolve_period_selection',
                return_value={'requested_fiscal_year': 2021}))
            stack.enter_context(patch.object(bank, 'prepare_historical_annual_input', return_value=prepared))
            stack.enter_context(patch.object(bank, '_Sources', return_value=reader))
            stack.enter_context(patch.object(bank, 'filing_inventory', return_value=inventory))
            stack.enter_context(patch.object(bank, '_exact_filing_source_set',
                return_value={'source_set_manifest_id': 'sha256:' + '3' * 64}))
            stack.enter_context(patch.object(bank, 'verify_ordinary_source_proofs',
                return_value={'source_credit': 'RECORDED_TEST_ONLY'}))
            stack.enter_context(patch.object(bank, 'repository_company_traits',
                return_value=['financial'] if applicable else []))
            inspection = stack.enter_context(patch.object(bank, 'inspect_historical_bank_scope',
                side_effect=inspector if isinstance(inspector, Exception) else None,
                return_value=inspector if not isinstance(inspector, Exception) else None))
            result = bank.prepare_historical_bank_scope_year_case(repo_root='/constructed',
                company_id='jpmorgan_chase', metric_id=metric_id, fiscal_year=2021)
        return result, inspection, selection

    def test_wrong_family_refuses_before_selecting_any_sources(self):
        with patch.object(bank, 'resolve_period_selection') as selection:
            with self.assertRaisesRegex(ValueError, 'FAMILY_NOT_RECEIVED'):
                bank.prepare_historical_bank_scope_year_case(repo_root='/constructed',
                    company_id='jpmorgan_chase', metric_id='A13', fiscal_year=2021)
        selection.assert_not_called()

    def test_structural_not_applicable_never_reads_financial_amount(self):
        case, inspector, _ = self.prepare(applicable=False)
        inspector.assert_not_called()
        self.assertIsNone(case['results']['A09']['value'])
        self.assertEqual('N_A_STRUCTURAL', case['results']['A09']['applicability'])
        self.assertEqual('2021-01-01', case['results']['A09']['period_start'])

    def test_amendment_and_successor_remain_named_withheld_before_inspection(self):
        for fields in ({'amendments': [{'form': '10-K/A'}]}, {'mode': 'SUCCESSOR'}):
            with self.subTest(fields=fields):
                case, inspector, _ = self.prepare(**fields)
                inspector.assert_not_called()
                self.assertIsNone(case['results']['A09']['value'])
                self.assertEqual('HISTORICAL_BANK_SCOPE_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED',
                                 case['results']['A09']['reason_code'])

    def test_unresolved_source_is_not_a_partial_bank_sum(self):
        fact = {'outcome': 'UNRESOLVED', 'value': None, 'selected': []}
        before = deepcopy(fact)
        case, inspector, selection = self.prepare(inspector=fact)
        self.assertIsNone(case['results']['A09']['value'])
        self.assertEqual('HISTORICAL_BANK_SCOPE_SOURCE_SEMANTICS_UNRESOLVED',
                         case['results']['A09']['reason_code'])
        self.assertEqual(2021, selection.call_args.kwargs['fiscal_year'])
        args = inspector.call_args.kwargs
        self.assertEqual('YEAR_QUARTER_OR_DATE', args['dei_release'])
        self.assertEqual('19617', args['expected_cik'])
        self.assertEqual('2021-01-01', args['target_period']['period_start'])
        self.assertEqual('A09', args['metric_id'])
        self.assertEqual('sha256:' + '3' * 64, args['source_set_manifest']['source_set_manifest_id'])
        self.assertEqual(b'constructed inventory', args['inventory_bytes'])
        self.assertEqual(before, fact)

    def test_source_failure_propagates_without_inventing_disclosure_absence(self):
        with self.assertRaisesRegex(ValueError, 'wrong source period'):
            self.prepare(inspector=ValueError('wrong source period'))


    def test_resolved_nim_is_annual_and_uses_managed_rate(self):
        fact = {'semantic_status': 'SINGLE_SOURCE_SEMANTIC_FACT',
                'relations': [{'rate_check': {'disclosed_ratio': '0.0164'}}]}
        case, _, _ = self.prepare(metric_id='A04', inspector=fact)
        self.assertEqual('0.0164', case['results']['A04']['value'])
        self.assertEqual('2021-01-01', case['target_period']['period_start'])
        self.assertEqual('SOURCE_ANNUAL_MEASUREMENT', case['input_binding']['measurement_time_basis'])

    def test_resolved_aum_and_nonaccrual_keep_filing_end_instant(self):
        for metric, fact, value in (
                ('A11', {'semantic_status': 'SINGLE_SOURCE_SEMANTIC_FACT', 'value': '3113000000000'}, '3113000000000'),
                ('A09', {'outcome': 'HTML_FALLBACK_SOURCE_SEMANTIC_FACT', 'value': '0.0072'}, '0.0072')):
            with self.subTest(metric=metric):
                case, inspector, _ = self.prepare(metric_id=metric, inspector=fact)
                self.assertEqual(value, case['results'][metric]['value'])
                self.assertEqual('2021-12-31', case['target_period']['period_start'])
                self.assertEqual('2021-12-31', case['target_period']['period_end'])
                self.assertEqual('FILING_END_INSTANT', case['input_binding']['measurement_time_basis'])
                self.assertEqual('2021-01-01', inspector.call_args.kwargs['target_period']['period_start'])


class HistoricalBankScopeWordingTest(TestCase):
    def test_original_native_success_is_kept_without_old_form(self):
        from vnext import historical_bank_scope_wording as wording
        answer={'outcome':'STRUCTURED_PRIMARY_RESOLVED','value':'0.0072'}
        with patch.object(wording.structured,'inspect_ordinary_a09_source_fact',return_value=answer), \
                patch.object(wording,'_older_a09') as fallback:
            self.assertIs(answer,wording.inspect_historical_bank_scope(metric_id='A09'))
            fallback.assert_not_called()

    def test_a09_local_import_rebinding_retains_native_ambiguity_gate(self):
        from vnext import historical_bank_scope_wording as wording
        ref={'raw_asset_id':'sha256:'+'1'*64}
        for outcome,scope,expected_calls in (
                ('STRUCTURED_PRIMARY_RESOLVED','NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET',0),
                ('UNRESOLVED','NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET',0),
                ('STRUCTURED_SOURCE_AMBIGUOUS','INCOMPLETE_SOURCE_SET',0),
                ('STRUCTURED_SOURCE_AMBIGUOUS','NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET',1)):
            with self.subTest(outcome=outcome,scope=scope):
                primary={'outcome':outcome,'source_set_scope':scope,'value':'0.0072' if outcome=='STRUCTURED_PRIMARY_RESOLVED' else None}
                with patch.object(wording.structured,'inspect_inline_financial_claims',return_value=primary), \
                        patch.object(wording,'_older_nonaccrual',return_value={'status':'SINGLE_SOURCE_SEMANTIC_FACT','value':'0.0072'}) as html:
                    result=wording._older_a09(repo_root=bank.ROOT,source_bytes=b'constructed source control',
                        source_reference=ref,source_set_manifest={},expected_cik='19617',
                        target_period={'fiscal_year':2021,'period_start':'2021-01-01','period_end':'2021-12-31'})
                self.assertEqual(expected_calls,html.call_count)
                if expected_calls:self.assertEqual('HTML_FALLBACK_SOURCE_SEMANTIC_FACT',result['outcome'])
                elif outcome=='STRUCTURED_PRIMARY_RESOLVED':self.assertEqual('STRUCTURED_PRIMARY_RESOLVED',result['outcome'])
                else:self.assertIsNone(result['value'])

    def test_missing_native_source_propagates_and_never_reaches_html(self):
        from vnext import historical_bank_scope_wording as wording
        with patch.object(wording.structured,'inspect_inline_financial_claims',side_effect=ValueError('SOURCE_SET_INCOMPLETE')), \
                patch.object(wording,'_older_nonaccrual') as html:
            with self.assertRaisesRegex(ValueError,'SOURCE_SET_INCOMPLETE'):
                wording._older_a09(repo_root=bank.ROOT,source_bytes=b'constructed source',source_reference={},
                    source_set_manifest={},expected_cik='19617',target_period={})
        html.assert_not_called()

    def test_compilation_keeps_shared_functions_and_known_forms_are_finite(self):
        from vnext import historical_bank_scope_wording as wording
        originals=(wording.relationships.inspect_nim_relationships,wording.relationships._reported_segment_sections,
                   wording.balances._aum_definitions,wording.relationships.inspect_nonaccrual_loan_ratio)
        forms=(wording.MARKETS_NAME,wording.SEGMENT_LIST,wording.GLOSSARY_COLON,wording.TABLE_OF_CONTENTS)
        for function,substitutions in zip(originals,forms):
            made=wording._known_form(function,substitutions)
            self.assertIsNot(made,function)
        self.assertEqual(originals,(wording.relationships.inspect_nim_relationships,
            wording.relationships._reported_segment_sections,wording.balances._aum_definitions,
            wording.relationships.inspect_nonaccrual_loan_ratio))

    def test_old_glossary_accepts_one_colon_and_preserves_subset_text(self):
        from vnext import historical_bank_scope_wording as wording
        reader=wording._known_form(wording.balances._aum_definitions,wording.GLOSSARY_COLON)
        text='AUM: “Assets under management”: Represent assets managed by AWM on behalf of its institutional and retail clients. Includes “Committed capital not Called.”'
        def definitions(value):return reader({'blocks':[{'inside_table':False,'visible_text':value}]})
        self.assertEqual(1,len(definitions(text)))
        self.assertEqual(definitions(text.replace('AUM:','AUM'))[0][:2],definitions(text)[0][:2])
        for form in ('AUM::','AUM;','AUM —'):
            self.assertEqual([],definitions(text.replace('AUM:',form)))
        subset=definitions(text.replace('institutional and retail','selected institutional'))
        scope=wording.balances._client_population(subset[0][1])
        self.assertFalse(scope['complete_unqualified_enumeration'])
        self.assertEqual(['selected'],scope['subset_qualifiers'])

    def test_old_segment_list_cannot_hide_conflicting_or_noncorporate_remainder(self):
        from vnext import historical_bank_scope_wording as wording
        from vnext.table_grid import _AllTablesParser
        from vnext.composite_scope import index_source_structure
        old='There are four major reportable business segments – Consumer & Community Banking, Corporate & Investment Bank, Commercial Banking and Asset & Wealth Management. In addition, there is a Corporate segment.'
        newer='The Firm has three reportable business segments – Consumer & Community Banking, Commercial & Investment Bank, and Asset & Wealth Management – with the remaining activities in Corporate.'
        inspector=wording._known_form(wording.relationships._reported_segment_sections,wording.SEGMENT_LIST)
        def evaluate(*definitions):
            raw=('<html><body>'+''.join('<div>'+s+'</div>' for s in definitions)+'<table><tr><td>ASSET &amp; WEALTH MANAGEMENT</td></tr></table></body></html>').encode()
            parser=_AllTablesParser();parser.feed(raw.decode());parser.close()
            return inspector(parser.tables,index_source_structure(source_bytes=raw))[0]['segment_definition']
        self.assertIsNotNone(evaluate(old))
        self.assertIsNotNone(evaluate(newer))
        self.assertIsNone(evaluate(old.replace('Corporate segment','Treasury segment')))
        self.assertIsNone(evaluate(old,newer))


class HistoricalBankScopeClassificationTest(TestCase):
    prepare = HistoricalBankScopeCaseTest.prepare
    def test_source_conflict_remains_distinct_from_implementation_gap(self):
        for fact,category in (({'outcome':'UNRESOLVED','value':None},'IMPLEMENTATION_GAP'),
                             ({'outcome':'STRUCTURED_SOURCE_CONFLICT','value':None},'SOURCE_CONFLICT')):
            with self.subTest(category=category):
                case,_,_=self.prepare(metric_id='A09',inspector=fact)
                self.assertIsNone(case['results']['A09']['value'])
                self.assertEqual(category,case['input_assessments']['financial_source']['classification'])
