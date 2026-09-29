"""An exact original-source split is a candidate, never old B03 success credit."""
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest import TestCase

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.b03_exact_impairment_relation import prove_exact_impairment_relation
from vnext.b03_impairment_adjusted_run import prepare_case as prepare_adjusted_case
from vnext.canonical import sha256_bytes
from vnext.normal_run_v3 import prepare_case
from vnext.normal_source_authority import ROOT


class B03ExactImpairmentRelationTest(TestCase):
    def test_saved_ford_exact_split_and_two_source_counterexamples(self):
        self.enterContext(original_sources_only())
        case = prepare_case(data_root=ROOT, company_id='ford_motor_company',
                            metric_id='B03')
        proof = prove_exact_impairment_relation(case=case, data_root=ROOT)
        self.assertEqual('15974000000', proof['selected_total_usd'])
        self.assertEqual('8140000000',
                         proof['exact_impairment_depreciation_usd'])
        self.assertEqual('7834000000',
                         proof['arithmetically_remaining_da_usd'])
        self.assertEqual('c-1', proof['shared_context_ref'])
        self.assertFalse(proof['native_result_created'])
        self.assertFalse(proof['current_business_credit'])
        self.assertEqual(
            'sha256:1829d73dac66a195a590ab84ea1f1d1800a77fae60d828b6f37d5cbeec2abd30',
            case['results']['B03']['result_id'])
        adjusted = prepare_adjusted_case(data_root=ROOT,
            company_id='ford_motor_company')
        self.assertEqual('-0.007128858795196163766173431518',
                         adjusted['results']['B03']['value'])
        self.assertNotEqual(case['results']['B03']['result_id'],
                            adjusted['results']['B03']['result_id'])
        self.assertEqual(proof['proof_id'],
            adjusted['input_binding']['source_relation_proof']['proof_id'])

        original_proof = next(row for row in case['source_proofs']
            if row['content_sha256'] == proof['primary_source_sha256']
            and row['request_repo_relative_path'] == proof['primary_source_path'])
        raw = (ROOT/proof['primary_source_path']).read_bytes()
        changes = [
            (b'id="f-261">8,140</ix:nonFraction>',
             b'id="f-261">8,141</ix:nonFraction>',
             'B03_EXACT_COMPONENT_ARITHMETIC_FAILED'),
            (b'including depreciation of $<ix:nonFraction',
             b'excluding depreciation of $<ix:nonFraction',
             'B03_EXACT_CASH_FLOW_LABELS_NOT_PROVEN'),
        ]
        for before, after, expected_error in changes:
            with self.subTest(expected_error=expected_error):
                self.assertEqual(1, raw.count(before))
                altered = raw.replace(before, after)
                with tempfile.TemporaryDirectory(prefix='b03-exact-source-') as tmp:
                    root = Path(tmp).resolve()
                    target = root/proof['primary_source_path']
                    target.parent.mkdir(parents=True)
                    target.write_bytes(altered)
                    modified = deepcopy(case)
                    modified['source_proofs'] = [{**row,
                        'content_sha256': sha256_bytes(content=altered)}
                        if row == original_proof else row
                        for row in case['source_proofs']]
                    with self.assertRaisesRegex(ValueError, expected_error):
                        prove_exact_impairment_relation(
                            case=modified, data_root=root)
