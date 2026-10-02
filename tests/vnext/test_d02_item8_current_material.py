"""The explicit #28 D02 successor reads current originals, not peer results."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from vnext import d02_text_results_v3 as successor
from vnext import text_results_v2 as frozen
from vnext.normal_run_v3 import prepare_case


ROOT = Path(__file__).resolve().parents[2]


def indexes(candidate):
    return {(c['section_id'], c['block_index'])
            for c in candidate['selected'].values()}


class D02CurrentItem8MaterialTest(unittest.TestCase):
    def test_v1_false_exclusion_remains_suspended_and_v2_keeps_the_matter(self):
        from vnext.d02_item8_category_28_v1 import classify as v1
        from vnext.d02_item8_category_28_v2 import classify as v2
        from vnext.text_business_candidates import _LEGAL
        from vnext import normal_run_v3 as normal
        from vnext import ordinary_update_cycle as update
        from vnext.ordinary_d02_category_update import run_company as old_wrapper
        from vnext.ordinary_d02_category_update_v2 import run_company as v2_wrapper
        from vnext.ordinary_d02_item8_v2 import POLICY as v2_policy

        counterexample = 'We face litigation, which could result in a significant loss.'
        self.assertTrue(v1(text=counterexample, keyword=_LEGAL)['left_out'])
        self.assertFalse(v2(text=counterexample, keyword=_LEGAL)['left_out'])
        second = 'Litigation, brought by a customer against us in 2025, remains unresolved.'
        self.assertTrue(v1(text=second, keyword=_LEGAL)['left_out'])
        self.assertFalse(v2(text=second, keyword=_LEGAL)['left_out'])
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'ORDINARY_D02_CATEGORY_RULE_VALIDATION_SUSPENDED'):
                normal.create_normal_run(data_root=root/'data', run_dir=root/'run',
                    company_id='lumen_technologies', metric_id='D02', d02_category=True)
            with self.assertRaisesRegex(ValueError, 'UPDATE_D02_CATEGORY_RULE_VALIDATION_SUSPENDED'):
                update.run_once(state_root=root/'state', source_root=ROOT,
                    company_id='lumen_technologies', metric_ids=['D02'], d02_category=True)
            with self.assertRaisesRegex(ValueError, 'ORDINARY_D02_V2_CATEGORY_RULE_VALIDATION_SUSPENDED'):
                normal.create_normal_run(data_root=root/'data', run_dir=root/'run',
                    company_id='lumen_technologies', metric_id='D02',
                    d02_category='ITEM8_V2')
            with self.assertRaisesRegex(ValueError, 'ORDINARY_D02_V2_CATEGORY_RULE_VALIDATION_SUSPENDED'):
                normal._create_case_run(data_root=root/'data', run_dir=root/'run',
                    company_id='lumen_technologies', metric_id='D02',
                    case={'input_binding':{'d02_category_policy':v2_policy}},
                    requirement={})
            with self.assertRaisesRegex(ValueError, 'UPDATE_D02_V2_CATEGORY_RULE_VALIDATION_SUSPENDED'):
                update.run_once(state_root=root/'state', source_root=ROOT,
                    company_id='lumen_technologies', metric_ids=['D02'],
                    d02_category='ITEM8_V2')
            row = old_wrapper(state_root=root/'state', source_root=ROOT,
                company_id='lumen_technologies', metric_ids=['D02'])['metrics'][0]
            self.assertEqual('UPDATE_BLOCKED', row['status'])
            self.assertIn('UPDATE_D02_CATEGORY_RULE_VALIDATION_SUSPENDED', row['reason'])
            v2 = v2_wrapper(state_root=root/'state', source_root=ROOT,
                company_id='lumen_technologies', metric_ids=['D02'])['metrics'][0]
            self.assertEqual('UPDATE_BLOCKED', v2['status'])
            self.assertIn('UPDATE_D02_V2_CATEGORY_RULE_VALIDATION_SUSPENDED', v2['reason'])
            self.assertFalse((root/'state').exists())

    def test_current_false_mentions_leave_but_actual_litigation_stays(self):
        expected = {
            'lumen_technologies': {('ITEM_8', 1670)},
            'pfizer': {('ITEM_8', 2175), ('ITEM_8', 2240)},
            'paramount_skydance_paramount_global': {('ITEM_8', 2257)},
        }
        for company, removed in expected.items():
            with self.subTest(company=company):
                old = prepare_case(data_root=ROOT, company_id=company,
                                   metric_id='D02')
                new = prepare_case(data_root=ROOT, company_id=company,
                                   metric_id='D02', d02_category='ITEM8_V2')
                frozen_candidate = frozen.create_deterministic_text_candidate(
                    **old['text_arguments'])
                default_candidate = successor.create_deterministic_text_candidate(
                    **old['text_arguments'])
                changed = successor.create_deterministic_text_candidate(
                    **new['text_arguments'])
                self.assertEqual(frozen_candidate, default_candidate)
                self.assertEqual(removed, indexes(frozen_candidate)-indexes(changed))
                self.assertEqual(set(), indexes(changed)-indexes(frozen_candidate))
                if company == 'paramount_skydance_paramount_global':
                    self.assertIn(('ITEM_8', 2108), indexes(changed))
                if company == 'lumen_technologies':
                    before = successor.prepare_business_text_sources(
                        metric_id='D02', **{k:v for k,v in old['text_arguments'].items()
                                            if k != 'compiled_spec'})
                    after = successor.prepare_business_text_sources(
                        metric_id='D02', **{k:v for k,v in new['text_arguments'].items()
                                            if k != 'compiled_spec'})
                    annual = next(iter(before['proposals']))
                    self.assertEqual(before['proposals'][annual]['D03'],
                                     after['proposals'][annual]['D03'])
                    self.assertEqual([1670], [x['block_index'] for x in
                        after['proposals'][annual]['item_8_category_mentions_left_out']['blocks']])
                evidence = successor.build_text_evidence(
                    candidate=changed, **new['text_arguments'])
                self.assertEqual('PASS', evidence['status'])
                with self.assertRaisesRegex(ValueError, 'TEXT_V2_CANDIDATE_REPLAY_CHANGED'):
                    successor.build_text_evidence(candidate=frozen_candidate,
                                                  **new['text_arguments'])

    def test_item3_footer_is_not_falsely_claimed_as_repaired(self):
        old = prepare_case(data_root=ROOT, company_id='enphase_energy', metric_id='D02')
        new = prepare_case(data_root=ROOT, company_id='enphase_energy',
                           metric_id='D02', d02_category='ITEM8_V2')
        a = successor.create_deterministic_text_candidate(**old['text_arguments'])
        b = successor.create_deterministic_text_candidate(**new['text_arguments'])
        self.assertIn(('ITEM_3', 755), indexes(a))
        self.assertIn(('ITEM_3', 755), indexes(b))


if __name__ == '__main__':
    unittest.main()
