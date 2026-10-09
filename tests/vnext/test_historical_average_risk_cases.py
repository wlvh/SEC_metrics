"""Constructed controls exercise actual period routing, Spec and Calculator.

These controls are not conclusions about a filing. Saved-source integration
separately checks the real inspector, writer and company output.
"""
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from vnext import historical_average_risk_cases as cases

ANNUAL = {'fiscal_year': 2021, 'period_start': '2021-01-01', 'period_end': '2021-12-31'}
LCR = {'status': 'SINGLE_SOURCE_SEMANTIC_FACT', 'value': '1.11',
       'measurement_period': {'period_start': '2021-10-01', 'period_end': '2021-12-31',
                              'duration_months': 3}, 'annual_average_claimed': False}
VAR = {'semantic_status': 'SINGLE_SOURCE_SEMANTIC_FACT',
       'totals': [{'value': {'canonical_value': '55000000'}}]}


class HistoricalAverageRiskCaseTest(TestCase):
    def prepare(self, *, metric_id, component=None, applicable=True, amendments=None,
                mode='CONTINUOUS_PRIMARY'):
        prepared = {'company_id': 'jpmorgan_chase', 'entity': '19617',
            'filing': {'accessionNumber': '0000019617-22-000272'},
            'table_input': {'target_period': dict(ANNUAL)}, 'source_proofs': [],
            'amendments': amendments or [], 'subject_policy': {'mode': mode}}
        ref = {'source_reference_id': 'sha256:' + '1' * 64, 'raw_asset_id': 'sha256:' + '2' * 64,
            'accession': prepared['filing']['accessionNumber'], 'document_name': 'control.htm',
            'source_role': 'target_primary'}
        source = {'raw_bytes': b'constructed source control', 'source_reference': ref}
        inventory = {'raw_bytes': b'constructed inventory control', 'source_reference': ref}
        reader = SimpleNamespace(records={}, proofs={}, read=lambda *a, **k: inventory,
                                 primary=lambda *a, **k: source)
        with ExitStack() as stack:
            stack.enter_context(patch.object(cases, 'resolve_period_selection',
                return_value={'requested_fiscal_year': 2021}))
            stack.enter_context(patch.object(cases, 'prepare_historical_annual_input', return_value=prepared))
            stack.enter_context(patch.object(cases, '_Sources', return_value=reader))
            stack.enter_context(patch.object(cases, 'filing_inventory', return_value=inventory))
            stack.enter_context(patch.object(cases, '_exact_filing_source_set',
                return_value={'source_set_manifest_id': 'sha256:' + '3' * 64}))
            stack.enter_context(patch.object(cases, 'verify_ordinary_source_proofs',
                return_value={'source_credit': 'RECORDED_TEST_ONLY'}))
            stack.enter_context(patch.object(cases, 'repository_company_traits',
                return_value=['financial'] if applicable else []))
            inspector = stack.enter_context(patch.object(cases, 'inspect_historical_average_risk',
                side_effect=component if isinstance(component, Exception) else None,
                return_value=component if not isinstance(component, Exception) else None))
            result = cases.prepare_historical_average_risk_year_case(repo_root='/constructed',
                company_id='jpmorgan_chase', metric_id=metric_id, fiscal_year=2021)
        return result, inspector

    def test_lcr_quarter_is_measurement_while_fiscal_year_remains_annual_group(self):
        component = deepcopy(LCR)
        case, inspector = self.prepare(metric_id='A03', component=component)
        result = case['results']['A03']
        self.assertEqual('1.11', result['value'])
        self.assertEqual('2021-10-01', result['period_start'])
        self.assertEqual('2021-12-31', result['period_end'])
        self.assertEqual(2021, case['target_period']['fiscal_year'])
        self.assertEqual(ANNUAL, inspector.call_args.kwargs['target_period'])
        self.assertEqual('YEAR_QUARTER_OR_DATE', inspector.call_args.kwargs['dei_release'])
        observations = [r for r in case['expected_records'] if r['record_type'] == 'VERIFIED_OBSERVATION']
        self.assertEqual('SOURCE_DISCLOSED_AVERAGE', observations[0]['source_binding']['measurement_time_basis'])
        self.assertEqual(ANNUAL, observations[0]['source_binding']['filing_period'])
        self.assertEqual(LCR, component)

    def test_var_annual_average_keeps_annual_period_and_usd_value(self):
        case, _ = self.prepare(metric_id='A12', component=deepcopy(VAR))
        self.assertEqual('55000000', case['results']['A12']['value'])
        self.assertEqual('USD', case['results']['A12']['unit'])
        self.assertEqual(ANNUAL, case['target_period'])
        self.assertEqual('SOURCE_ANNUAL_MEASUREMENT',
                         case['input_binding']['measurement_time_basis'])

    def test_unresolved_component_cannot_reuse_candidate_value(self):
        for metric_id, component in (
                ('A03', {**LCR, 'status': 'UNRESOLVED'}),
                ('A12', {**VAR, 'semantic_status': 'UNRESOLVED'})):
            with self.subTest(metric_id=metric_id):
                case, _ = self.prepare(metric_id=metric_id, component=component)
                self.assertIsNone(case['results'][metric_id]['value'])
                self.assertEqual('HISTORICAL_AVERAGE_RISK_SOURCE_SEMANTICS_UNRESOLVED',
                                 case['results'][metric_id]['reason_code'])
                self.assertEqual(ANNUAL, case['target_period'])
                if metric_id == 'A03':
                    self.assertEqual('NO_MEASUREMENT_RESOLVED_FILING_GROUP_ONLY',
                                     case['input_binding']['measurement_time_basis'])

    def test_structural_not_applicable_skips_amount_inspection(self):
        for metric_id in ('A03', 'A12'):
            with self.subTest(metric_id=metric_id):
                case, inspector = self.prepare(metric_id=metric_id, applicable=False)
                inspector.assert_not_called()
                self.assertIsNone(case['results'][metric_id]['value'])
                self.assertEqual('N_A_STRUCTURAL', case['results'][metric_id]['applicability'])
                self.assertEqual(ANNUAL, case['target_period'])

    def test_amendment_or_successor_remains_withheld_before_inspection(self):
        for metric_id in ('A03', 'A12'):
            for fields in ({'amendments': [{'form': '10-K/A'}]}, {'mode': 'SUCCESSOR'}):
                with self.subTest(metric_id=metric_id, fields=fields):
                    case, inspector = self.prepare(metric_id=metric_id, **fields)
                    inspector.assert_not_called()
                    self.assertIsNone(case['results'][metric_id]['value'])
                    self.assertEqual('HISTORICAL_AVERAGE_RISK_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED',
                                     case['results'][metric_id]['reason_code'])

    def test_wrong_source_error_is_not_disclosure_absence(self):
        with self.assertRaisesRegex(ValueError, 'wrong source period'):
            self.prepare(metric_id='A03', component=ValueError('wrong source period'))

    def test_wrong_family_refuses_before_any_source_selection(self):
        with patch.object(cases, 'resolve_period_selection') as selection:
            with self.assertRaisesRegex(ValueError, 'FAMILY_NOT_RECEIVED'):
                cases.prepare_historical_average_risk_year_case(repo_root='/constructed',
                    company_id='jpmorgan_chase', metric_id='A13', fiscal_year=2021)
        selection.assert_not_called()

    def test_measurement_rejects_unknown_family_instead_of_treating_as_var(self):
        with self.assertRaisesRegex(ValueError, 'FAMILY_NOT_RECEIVED'):
            cases.measurement(metric_id='A13', annual=ANNUAL, component=VAR)


class HistoricalAverageRiskWordingTest(TestCase):
    def test_original_resolved_answer_is_kept_without_fallback(self):
        from vnext import historical_average_risk_wording as wording
        for metric_id, name, older, answer in (
                ('A03', 'inspect_lcr_disclosed_fact', '_older_lcr', LCR),
                ('A12', 'inspect_total_var', '_older_var', VAR)):
            module = wording.candidates if metric_id == 'A03' else wording.balances
            with self.subTest(metric_id=metric_id), patch.object(module, name, return_value=answer), \
                    patch.object(wording, older) as fallback:
                self.assertIs(answer, wording.inspect_historical_average_risk(metric_id=metric_id))
                fallback.assert_not_called()

    def test_unresolved_fallback_keeps_original_competitors(self):
        from vnext import historical_average_risk_wording as wording
        original = {'status': 'UNRESOLVED', 'unresolved': [{'reason': 'conflicting scope'}]}
        with patch.object(wording.candidates, 'inspect_lcr_disclosed_fact', return_value=original), \
                patch.object(wording, '_older_lcr', return_value={'status': 'UNRESOLVED'}):
            self.assertIs(original, wording.inspect_historical_average_risk(metric_id='A03'))

    def test_resolved_known_form_retains_original_status_and_provenance(self):
        from vnext import historical_average_risk_wording as wording
        with patch.object(wording.balances, 'inspect_total_var',
                          return_value={'semantic_status': 'UNRESOLVED'}), \
                patch.object(wording, '_older_var', return_value=VAR):
            resolved = wording.inspect_historical_average_risk(metric_id='A12')
        self.assertEqual(VAR['totals'], resolved['totals'])
        self.assertEqual(['COUNTERFACTUAL_HEADER'], resolved['historical_older_wording']['forms'])
        self.assertEqual({'semantic_status': 'UNRESOLVED'},
                         resolved['historical_older_wording']['frozen_inspector_status'])

    def test_known_forms_compile_without_mutating_shared_functions(self):
        from vnext import historical_average_risk_wording as wording
        originals = (wording.duration._linked_notes, wording.duration.inspect_financial_duration,
                     wording.balances.inspect_total_var)
        forms = (wording.GENERAL_NOTE, wording.MEASURE_ABBREVIATION, wording.COUNTERFACTUAL_HEADER)
        for function, substitutions in zip(originals, forms):
            made = wording._known_form(function, substitutions)
            self.assertIsNot(function, made)
            self.assertEqual(function.__name__, made.__name__)
        self.assertEqual(originals, (wording.duration._linked_notes,
            wording.duration.inspect_financial_duration, wording.balances.inspect_total_var))

    def test_general_note_only_before_lettered_notes_and_never_across_heading(self):
        from vnext import historical_average_risk_wording as wording
        reader = wording._known_form(wording.duration._linked_notes, wording.GENERAL_NOTE)
        def block(start, text):
            return {'start_byte': start, 'inside_table': False, 'visible_text': text}
        base = {'tables': [{'end_byte': 10, 'start_byte': 0}], 'source_size': 200}
        chosen, missing = reader(structure={**base, 'blocks': [
            block(11, 'Effective January 1, an accounting policy changed.'),
            block(20, '(a) The percentage represents average LCR for three months ended December 31, 2021.')]},
            table_order=0, markers={'a'})
        self.assertFalse(missing)
        self.assertEqual(20, chosen[0]['start_byte'])
        for middle in ('Liquidity discussion heading', 'First general sentence.\nSecond general sentence.'):
            blocks = [block(11, middle), block(20, 'Second general note.'), block(30, '(a) three months ended')]
            _, missing = reader(structure={**base, 'blocks': blocks}, table_order=0, markers={'a'})
            self.assertTrue(missing)
