"""Constructed source controls use the real existing Spec and Calculator."""
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from vnext import historical_geography_cases as geography


class HistoricalGeographyCaseTest(TestCase):
    def prepare(self, *, applicable=True, amendments=None, mode='CONTINUOUS_PRIMARY',
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
            selection = stack.enter_context(patch.object(geography, 'resolve_period_selection',
                return_value={'requested_fiscal_year': 2021}))
            stack.enter_context(patch.object(geography, 'prepare_historical_annual_input', return_value=prepared))
            stack.enter_context(patch.object(geography, '_Sources', return_value=reader))
            stack.enter_context(patch.object(geography, 'filing_inventory', return_value=inventory))
            stack.enter_context(patch.object(geography, '_exact_filing_source_set',
                return_value={'source_set_manifest_id': 'sha256:' + '3' * 64}))
            stack.enter_context(patch.object(geography, 'verify_ordinary_source_proofs',
                return_value={'source_credit': 'RECORDED_TEST_ONLY'}))
            stack.enter_context(patch.object(geography, 'repository_company_traits',
                return_value=['financial'] if applicable else []))
            inspection = stack.enter_context(patch.object(geography, 'inspect_inline_financial_claims',
                side_effect=inspector if isinstance(inspector, Exception) else None,
                return_value=inspector if not isinstance(inspector, Exception) else None))
            result = geography.prepare_historical_geography_year_case(repo_root='/constructed',
                company_id='jpmorgan_chase', metric_id='A13', fiscal_year=2021)
        return result, inspection, selection

    def test_wrong_family_refuses_before_selecting_any_sources(self):
        with patch.object(geography, 'resolve_period_selection') as selection:
            with self.assertRaisesRegex(ValueError, 'FAMILY_NOT_RECEIVED'):
                geography.prepare_historical_geography_year_case(repo_root='/constructed',
                    company_id='jpmorgan_chase', metric_id='A12', fiscal_year=2021)
        selection.assert_not_called()

    def test_structural_not_applicable_never_reads_financial_amount(self):
        case, inspector, _ = self.prepare(applicable=False)
        inspector.assert_not_called()
        self.assertIsNone(case['results']['A13']['value'])
        self.assertEqual('N_A_STRUCTURAL', case['results']['A13']['applicability'])
        self.assertEqual('2021-01-01', case['results']['A13']['period_start'])

    def test_amendment_and_successor_remain_named_withheld_before_inspection(self):
        for fields in ({'amendments': [{'form': '10-K/A'}]}, {'mode': 'SUCCESSOR'}):
            with self.subTest(fields=fields):
                case, inspector, _ = self.prepare(**fields)
                inspector.assert_not_called()
                self.assertIsNone(case['results']['A13']['value'])
                self.assertEqual('HISTORICAL_GEOGRAPHY_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED',
                                 case['results']['A13']['reason_code'])

    def test_unresolved_source_is_not_a_partial_geography_sum(self):
        fact = {'outcome': 'SOURCE_SEMANTICS_UNRESOLVED', 'value': None, 'selected': []}
        before = deepcopy(fact)
        case, inspector, selection = self.prepare(inspector=fact)
        self.assertIsNone(case['results']['A13']['value'])
        self.assertEqual('HISTORICAL_GEOGRAPHY_SOURCE_SEMANTICS_UNRESOLVED',
                         case['results']['A13']['reason_code'])
        self.assertEqual(2021, selection.call_args.kwargs['fiscal_year'])
        args = inspector.call_args.kwargs
        self.assertEqual('YEAR_QUARTER_OR_DATE', args['dei_release'])
        self.assertEqual('19617', args['expected_cik'])
        self.assertEqual(case['target_period'], args['target_period'])
        self.assertEqual(before, fact)

    def test_source_failure_propagates_without_inventing_disclosure_absence(self):
        with self.assertRaisesRegex(ValueError, 'wrong source period'):
            self.prepare(inspector=ValueError('wrong source period'))
