"""The explicit V14 B03 guard does not change V13's original source rule."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import ordinary_release_preparation as release
from vnext.b03_contract_amortization_scope import assess_current_b03_scope
from vnext.b03_depreciation_scope import assess_direct_depreciation_scope
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.financial_structured import _InlineTableIndex
from vnext.normal_run_v3 import prepare_case
from vnext.normal_source_authority import ROOT


class B03ContractAmortizationScopeTest(TestCase):
    def test_current_composed_result_proves_separate_revenue_deduction(self):
        self.enterContext(original_sources_only())
        case = prepare_case(data_root=ROOT,
            company_id='marriott_international', metric_id='B03')
        self.assertEqual('NO_DIRECT_DEPRECIATION_SELECTION',
            assess_direct_depreciation_scope(case=case, data_root=ROOT)['status'])
        checked = assess_current_b03_scope(case=case, data_root=ROOT)
        self.assertEqual('COMPOSED_DA_CONTRACT_REVENUE_DEDUCTION_EXCLUDED',
                         checked['status'])
        self.assertFalse(checked['blocked'])
        self.assertEqual({'depreciation': '145000000',
                          'amortization': '313000000'},
                         checked['selected_components'])
        self.assertIn(('135000000', (('srt:ProductOrServiceAxis',
                                     'mar:FeeServiceMember'),)),
            [(row['value_usd'], tuple(sorted(row['dimensions'].items())))
             for row in checked['excluded_facts']])
        self.assertEqual({'depreciation': '145000000',
                          'amortization': '313000000'},
                         {role: row['value_usd'] for role, row in
                          checked['selected_original_facts'].items()})
        self.assertEqual(5, len(checked['revenue_deduction_proofs']))
        self.assertEqual(['5438', '-135', '5303'],
            checked['revenue_deduction_proofs'][0]['displayed_amounts'])
        self.assertEqual('0.1756281982738868097456656229',
                         case['results']['B03']['value'])
        self.assertFalse(checked['amount_added_or_result_recomputed'])
        with patch.object(release.normal, 'replay_case', return_value=case):
            self.assertEqual('NATIVE_PUBLISHED_RESULT',
                release._result_selection_basis(data_root=ROOT, manifest={},
                    result=case['results']['B03'], rendered={}))
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

    def test_revenue_location_sign_and_gross_to_net_are_required(self):
        self.enterContext(original_sources_only())
        case = prepare_case(data_root=ROOT,
            company_id='marriott_international', metric_id='B03')
        proof = next(row for row in case['source_proofs']
            if row.get('accession') == '0001048286-26-000007'
            and row.get('document_name') == 'mar-20251231.htm')
        raw = (ROOT/proof['request_repo_relative_path']).read_bytes()
        index = _InlineTableIndex(raw)
        index.feed(raw.decode('utf-8-sig'))
        index.close()
        parsed = parse_accession_xbrl_source(raw_bytes=raw)
        selected = [fact['ordinal'] for fact in parsed.facts
            if fact['qualified_name'] ==
                'us-gaap:CapitalizedContractCostAmortization'
            and parsed.contexts[fact['context_ref']]['period_start'] == '2025-01-01'
            and parsed.contexts[fact['context_ref']]['period_end'] == '2025-12-31'
            and set(parsed.contexts[fact['context_ref']]['dimensions']) ==
                {'srt:ProductOrServiceAxis'}]
        self.assertEqual(1, len(selected))
        position = index.fact_positions[selected[0]]
        begin = raw.rfind(b'<tr', 0, position)
        end = raw.find(b'</tr>', position) + len(b'</tr>')
        self.assertTrue(0 <= begin < position < end)
        line = raw[begin:end]
        self.assertIn(b'Contract investment amortization', line)
        next_end = raw.find(b'</tr>', end) + len(b'</tr>')
        next_line = raw[end:next_end]
        self.assertIn(b'5,303', next_line)

        def source_changed(original, replacement, *, remove_closing=False):
            with tempfile.TemporaryDirectory(prefix='b03-contract-scope-') as temporary:
                root = Path(temporary)
                path = root/proof['request_repo_relative_path']
                path.parent.mkdir(parents=True)
                self.assertIn(original, line)
                changed_line = line.replace(original, replacement, 1)
                if remove_closing:
                    self.assertIn(b'</ix:nonFraction>)', changed_line)
                    changed_line = changed_line.replace(
                        b'</ix:nonFraction>)', b'</ix:nonFraction>', 1)
                changed = raw[:begin] + changed_line + raw[end:]
                path.write_bytes(changed)
                altered = deepcopy(case)
                altered['source_proofs'] = [
                    {**row, 'content_sha256': hashlib.sha256(changed).hexdigest()}
                    if row == proof else row for row in case['source_proofs']]
                return assess_current_b03_scope(case=altered, data_root=root)

        for old, new, closing in [
                (b'Contract investment amortization',
                 b'Financing investment amortization', False),
                (b'(<ix:nonFraction', b'<ix:nonFraction', True)]:
            with self.subTest(original=old):
                checked = source_changed(old, new,
                                         remove_closing=closing)
                self.assertEqual('COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED',
                                 checked['status'])
                self.assertTrue(checked['blocked'])

        with tempfile.TemporaryDirectory(prefix='b03-contract-net-') as temporary:
            root = Path(temporary)
            path = root/proof['request_repo_relative_path']
            path.parent.mkdir(parents=True)
            changed = (raw[:end] + next_line.replace(b'5,303', b'5,304', 1)
                       + raw[next_end:])
            path.write_bytes(changed)
            altered = deepcopy(case)
            altered['source_proofs'] = [
                {**row, 'content_sha256': hashlib.sha256(changed).hexdigest()}
                if row == proof else row for row in case['source_proofs']]
            checked = assess_current_b03_scope(case=altered, data_root=root)
            self.assertTrue(checked['blocked'])
            self.assertEqual('COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED',
                             checked['status'])
        changed_component = deepcopy(case)
        selected_component = next(row for row in changed_component['observations']
            if row['semantic_role'] == 'depreciation')
        selected_component['value'] = '146000000'
        with self.assertRaisesRegex(ValueError,
                'B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NOT_IN_ORIGINAL:depreciation'):
            assess_current_b03_scope(case=changed_component, data_root=ROOT)

        # A textual us-gaap prefix is not proof of the original XBRL concept.
        depreciation = next(fact for fact in parsed.facts
            if fact['qualified_name'] == 'us-gaap:Depreciation'
            and parsed.contexts[fact['context_ref']]['period_start'] == '2025-01-01'
            and parsed.contexts[fact['context_ref']]['period_end'] == '2025-12-31'
            and not parsed.contexts[fact['context_ref']]['dimensions'])
        fact_position = index.fact_positions[depreciation['ordinal']]
        tag_start = fact_position
        tag_end = raw.find(b'>', tag_start) + 1
        self.assertTrue(raw.startswith(b'<ix:nonFraction', tag_start))
        self.assertTrue(tag_start < tag_end)
        self.assertIn(b'us-gaap:Depreciation', raw[tag_start:tag_end])
        spoofed = (raw[:tag_end-1] +
            b' xmlns:us-gaap="https://example.invalid/not-us-gaap"' +
            raw[tag_end-1:])
        with tempfile.TemporaryDirectory(prefix='b03-contract-namespace-') as temporary:
            root = Path(temporary)
            path = root/proof['request_repo_relative_path']
            path.parent.mkdir(parents=True)
            path.write_bytes(spoofed)
            altered = deepcopy(case)
            altered['source_proofs'] = [
                {**row, 'content_sha256': hashlib.sha256(spoofed).hexdigest()}
                if row == proof else row for row in case['source_proofs']]
            with self.assertRaisesRegex(ValueError,
                    'B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NAMESPACE_MISMATCH:depreciation'):
                assess_current_b03_scope(case=altered, data_root=root)

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
