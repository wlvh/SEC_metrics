"""Saved-source D01 successor tests, separate from the 30-second fast tier."""
import copy
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.d01_emphasis_results import (POLICY, build_text_evidence,
                                         create_deterministic_text_candidate)
from vnext.normal_run_v3 import prepare_case


class D01EmphasisMaterialTest(unittest.TestCase):
    def test_current_saved_filings_replay_exact_candidate_and_evidence(self):
        for company, count in [('paramount_skydance_paramount_global', 38),
                               ('marriott_international', 38)]:
            with self.subTest(company=company):
                case = prepare_case(data_root=ROOT, company_id=company, metric_id='D01',
                                    d01_emphasis=True)
                args = case['text_arguments']
                self.assertEqual(POLICY, args['d01_emphasis_policy'])
                candidate = create_deterministic_text_candidate(**args)
                self.assertEqual(count, len(candidate['selected']))
                evidence = build_text_evidence(candidate=candidate, **args)
                self.assertEqual('PASS', evidence['status'])
                if company.startswith('paramount'):
                    self.assertTrue(any('changes in U.S. or foreign laws' in claim['text']
                                        for claim in candidate['selected'].values()))
                else:
                    old_case = prepare_case(data_root=ROOT, company_id=company,
                                            metric_id='D01')
                    old_candidate = create_deterministic_text_candidate(
                        **old_case['text_arguments'])
                    self.assertEqual(34, len(old_candidate['selected']))
                changed = copy.deepcopy(candidate)
                changed['selected']['excerpt_0']['text'] += ' altered'
                with self.assertRaises(ValueError):
                    build_text_evidence(candidate=changed, **args)
                raw_id = args['source_references'][0]['raw_asset_id']
                tampered = {**args, 'raw_bytes_by_id': {**args['raw_bytes_by_id'],
                            raw_id: args['raw_bytes_by_id'][raw_id] + b'changed'}}
                with self.assertRaisesRegex(ValueError, 'TEXT_SOURCE_BYTES_CHANGED'):
                    create_deterministic_text_candidate(**tampered)

    def test_default_route_and_wrong_metric_do_not_switch_policy(self):
        original = prepare_case(data_root=ROOT, company_id='paramount_skydance_paramount_global',
                                metric_id='D01')
        self.assertNotIn('d01_emphasis_policy', original['text_arguments'])
        candidate = create_deterministic_text_candidate(**original['text_arguments'])
        self.assertTrue(any(claim['text'] == 'Failures to comply with or changes in U'
                            for claim in candidate['selected'].values()))
        with self.assertRaisesRegex(ValueError, 'D01_EMPHASIS_SPEC_INVALID'):
            wrong = {**original['text_arguments'], 'd01_emphasis_policy': POLICY}
            wrong['compiled_spec'] = {'compiled': {**wrong['compiled_spec']['compiled'],
                                                   'metric_id': 'C02'}}
            create_deterministic_text_candidate(**wrong)


if __name__ == '__main__':
    unittest.main()
