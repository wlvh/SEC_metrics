"""The explicit V14 B03 guard does not change V13's original source rule."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import ordinary_release_preparation as release
from vnext.b03_contract_amortization_scope import assess_current_b03_scope
from vnext.b03_depreciation_scope import assess_direct_depreciation_scope
from vnext.normal_run_v3 import prepare_case
from vnext.normal_source_authority import ROOT


class B03ContractAmortizationScopeTest(TestCase):
    def test_current_composed_result_stops_but_old_v13_bytes_keep_prior_meaning(self):
        self.enterContext(original_sources_only())
        case = prepare_case(data_root=ROOT,
            company_id='marriott_international', metric_id='B03')
        self.assertEqual('NO_DIRECT_DEPRECIATION_SELECTION',
            assess_direct_depreciation_scope(case=case, data_root=ROOT)['status'])
        checked = assess_current_b03_scope(case=case, data_root=ROOT)
        self.assertEqual('COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED',
                         checked['status'])
        self.assertTrue(checked['blocked'])
        self.assertEqual({'depreciation': '145000000',
                          'amortization': '313000000'},
                         checked['selected_components'])
        self.assertIn(('135000000', (('srt:ProductOrServiceAxis',
                                     'mar:FeeServiceMember'),)),
            [(row['value_usd'], tuple(sorted(row['dimensions'].items())))
             for row in checked['additional_facts']])
        self.assertFalse(checked['amount_added_or_result_recomputed'])
        with patch.object(release.normal, 'replay_case', return_value=case):
            with self.assertRaisesRegex(ValueError,
                    'ORDINARY_RELEASE_B03_DEPRECIATION_SCOPE_UNRESOLVED'):
                release._result_selection_basis(data_root=ROOT, manifest={},
                    result=case['results']['B03'], rendered={})
        proof = next(row for row in case['source_proofs']
            if row.get('accession') == '0001048286-26-000007'
            and row.get('document_name') == 'mar-20251231.htm')
        altered = deepcopy(case)
        altered['source_proofs'] = [
            {**row, 'content_sha256': '0' * 64} if row == proof else row
            for row in case['source_proofs']]
        with self.assertRaisesRegex(ValueError,
                'B03_CONTRACT_SCOPE_PRIMARY_BYTES_CHANGED'):
            assess_current_b03_scope(case=altered, data_root=ROOT)
        changed_period = deepcopy(case)
        changed_period['target_period']['period_start'] = '2024-01-01'
        with self.assertRaisesRegex(ValueError,
                'B03_CONTRACT_SCOPE_COMPOSED_PERIOD_CHANGED'):
            assess_current_b03_scope(case=changed_period, data_root=ROOT)

    def test_unaffected_direct_b03_keeps_positive_source_path(self):
        self.enterContext(original_sources_only())
        for company in ('pfizer', 'southwest_airlines',
                        'salesforce', 'ford_motor_company'):
            with self.subTest(company=company):
                case = prepare_case(data_root=ROOT,
                    company_id=company, metric_id='B03')
                old = assess_direct_depreciation_scope(case=case,
                    data_root=ROOT)
                current = assess_current_b03_scope(case=case,
                    data_root=ROOT)
                self.assertEqual(old, current)
                if company in {'pfizer', 'southwest_airlines'}:
                    self.assertFalse(current['blocked'])
                else:
                    self.assertTrue(current['blocked'])
