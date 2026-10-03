"""Current E01 successor reads complete authenticated 8-K item text only."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vnext.ordinary_e01_item_text_input import (
    prepare_current_e01_item_text, verify_current_e01_item_text,
    install_current_e01_item_text)


ROOT = Path(__file__).resolve().parents[2]


class OrdinaryE01ItemTextMaterialTest(unittest.TestCase):
    def test_zero_candidate_source_installs_with_current_runtime_without_a_result(self):
        original = prepare_current_e01_item_text(repo_root=ROOT,
                                                   company_id='enphase_energy')
        with TemporaryDirectory() as temporary:
            output = Path(temporary)/'installed'
            installed = install_current_e01_item_text(source_root=ROOT,
                data_root=output,company_id='enphase_energy')
            self.assertEqual(original['input_id'],installed['input_id'])
            self.assertEqual(0,installed['candidate_count'])
            self.assertFalse(installed['metric_result_created'])
            self.assertTrue((output/'scripts/vnext/e01_item_text_28_v1.py').is_file())
            self.assertTrue((output/'scripts/vnext/ordinary_e01_item_text_input.py').is_file())
            with self.assertRaisesRegex(ValueError,'ORDINARY_E01_ITEM_TEXT_OUTPUT_ROOT_OVERLAP_OR_EXISTS'):
                install_current_e01_item_text(source_root=ROOT,data_root=output,
                                              company_id='enphase_energy')

    def test_saved_positive_negative_and_zero_candidate_sources(self):
        expected = {'enphase_energy':0,'pfizer':3,'ford_motor_company':7}
        cases = {}
        for company,count in expected.items():
            with self.subTest(company=company):
                case = prepare_current_e01_item_text(repo_root=ROOT,company_id=company)
                self.assertEqual(count,case['candidate_count'])
                self.assertEqual(sorted(['1.01','2.01','8.01']),case['candidate_item_codes'])
                self.assertEqual('NOT_PERFORMED',case['semantic_confirmation_status'])
                self.assertFalse(case['metric_result_created'])
                self.assertEqual({'provider':0,'paid':0,'sec':0},case['calls'])
                self.assertTrue(case['complete_event_source_sets'])
                self.assertEqual(case,verify_current_e01_item_text(
                    candidate=case,repo_root=ROOT,company_id=company))
                cases[company] = case
        pfizer = next(item for item in cases['pfizer']['items']
                      if item['accession']=='0000078003-25-000159'
                      and item['item_code']=='8.01')
        self.assertIn('Metsera',pfizer['item_text']['text'])
        ford = next(item for item in cases['ford_motor_company']['items']
                    if item['accession']=='0000037996-25-000067'
                    and item['item_code']=='1.01')
        self.assertEqual(['2.03'],ford['item_text']['shares_the_body_of'])
        self.assertIn('Credit Agreement',ford['item_text']['text'])
        self.assertGreater(len(cases['enphase_energy']['all_header_claim_ids']),0)

    def test_saved_item_text_cannot_be_changed_after_source_preparation(self):
        case = prepare_current_e01_item_text(repo_root=ROOT,company_id='pfizer')
        changed = deepcopy(case)
        changed['items'][0]['item_text']['text'] += ' fabricated'
        with self.assertRaisesRegex(ValueError,'ORDINARY_E01_ITEM_TEXT_SOURCE_REPLAY_CHANGED'):
            verify_current_e01_item_text(candidate=changed,repo_root=ROOT,
                                         company_id='pfizer')


if __name__=='__main__':
    unittest.main()
