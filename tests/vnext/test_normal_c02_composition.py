"""The explicit ordinary C02 successor reuses the shared composition reader."""
import unittest
from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_text_results_v2 import inputs
from vnext import ordinary_update_cycle, c02_composition_text_results as new_api
from vnext.normal_run_v3 import prepare_case, text_api
from vnext.specs import compile_spec_file
from vnext.text_results_v2 import (
    prepare_business_text_sources, create_deterministic_text_candidate,
    build_text_evidence, TextResultV2Error)


class C02CompositionFastTest(unittest.TestCase):
    def test_normal_default_dispatch_keeps_old_candidate_and_evidence_bytes(self):
        source = inputs()
        spec = compile_spec_file(path=ROOT / 'catalog/r6/C02_board_disclosures_v1.md',
                                 dependency_specs={})
        api, review = text_api('C02')
        old_candidate = create_deterministic_text_candidate(compiled_spec=spec, **source)
        self.assertEqual(old_candidate, api.create_deterministic_text_candidate(
            compiled_spec=spec, **source))
        self.assertEqual(build_text_evidence(compiled_spec=spec,
                         candidate=old_candidate, **source),
                         api.build_text_evidence(compiled_spec=spec,
                         candidate=old_candidate, **source))
        self.assertIs(review, api.build_text_review_unit)

    def test_old_default_and_explicit_selection_are_distinct(self):
        source = inputs(governance=(
            '<p>Our Board currently has twelve directors.</p>'
            '<p>Our executive compensation program aligns pay and Company performance. '
            'The Board and its Compensation Committee have implemented a bonus program.</p>'))
        old = prepare_business_text_sources(metric_id='C02', **source)
        new = new_api._prepared(c02_selection_policy='COMPOSITION_FACTS_V1', **source)
        old_proposal = next(p for p in old['proposals'].values() if p.get('metric_id') == 'C02')
        new_proposal = next(p for p in new['proposals'].values() if p.get('metric_id') == 'C02')
        self.assertEqual('BOARD_COMPOSITION_FACTS_V1', new_proposal['selection_policy'])
        self.assertNotEqual(old_proposal['proposal_id'], new_proposal['proposal_id'])
        self.assertIn(0, {r['block_index'] for r in new_proposal['candidates']})
        self.assertNotIn(1, {r['block_index'] for r in new_proposal['candidates']})

    def test_wrong_metric_or_flag_cannot_select_composition(self):
        with self.assertRaisesRegex(ValueError, 'ORDINARY_C02_COMPOSITION_TEXT_API_WRONG_METRIC'):
            text_api('D02', c02_composition=True)
        with self.assertRaisesRegex(ValueError, 'ORDINARY_C02_COMPOSITION_SCOPE_WRONG_METRIC'):
            prepare_case(data_root=ROOT, company_id='pfizer', metric_id='D02',
                         c02_composition=True)
        with self.assertRaisesRegex(ValueError, 'ORDINARY_C02_COMPOSITION_SCOPE_WRONG_METRIC'):
            prepare_case(data_root=ROOT, company_id='pfizer', metric_id='C02',
                         c02_composition='yes')


class C02CompositionMaterialTest(unittest.TestCase):
    def test_current_ordinary_sources_exclude_false_text_without_truncating_overflow(self):
        for company, wrong, factual in (
            ('marriott_international', 402, 491),
            ('pfizer', 1239, 1101),
        ):
            with self.subTest(company=company):
                old = prepare_case(data_root=ROOT, company_id=company, metric_id='C02')
                new = prepare_case(data_root=ROOT, company_id=company,
                                   metric_id='C02', c02_composition=True)
                old_candidate = create_deterministic_text_candidate(**old['text_arguments'])
                prepared = new_api._prepared(**{k:v for k,v in new['text_arguments'].items()
                                                if k != 'compiled_spec'})
                successor = next(p for p in prepared['proposals'].values()
                                 if p.get('metric_id') == 'C02')
                indices = lambda candidate: {row['block_index'] for row in candidate['selected'].values()}
                self.assertIn(wrong, indices(old_candidate))
                new_indices = {r['block_index'] for r in successor['candidates']}
                self.assertNotIn(wrong, new_indices)
                self.assertIn(factual, new_indices)
                self.assertGreater(len(new_indices), 64)
                with self.assertRaisesRegex(TextResultV2Error,
                        'TEXT_V2_COMPLETE_EXCERPT_SET_EXCEEDS_ITEM_BOUND'):
                    new_api.create_deterministic_text_candidate(**new['text_arguments'])
                self.assertEqual(old['source_proofs'], new['source_proofs'])
                self.assertEqual(old['target_period'], new['target_period'])
                self.assertEqual('catalog/r6/C02_board_disclosures_v1.md', old['spec_paths']['C02'])
                self.assertEqual('catalog/r6/C02_board_disclosures_v2.md', new['spec_paths']['C02'])
                self.assertEqual('COMPOSITION_FACTS_V1',
                                 new['input_binding']['c02_selection_policy'])

    def test_enphase_complete_candidate_and_evidence_fit_the_native_bound(self):
        new = prepare_case(data_root=ROOT, company_id='enphase_energy',
                           metric_id='C02', c02_composition=True)
        candidate = new_api.create_deterministic_text_candidate(**new['text_arguments'])
        evidence = new_api.build_text_evidence(candidate=candidate,
                                               **new['text_arguments'])
        indices = {r['block_index'] for r in candidate['selected'].values()}
        self.assertEqual(54, len(indices))
        self.assertNotIn(294, indices)
        self.assertIn(210, indices)
        self.assertIn(415, indices)  # an actual named committee chair on an unlabelled director card
        self.assertEqual('PASS', evidence['status'])

    def test_normal_update_inspection_chooses_explicit_successor(self):
        configuration = {'company_id': 'marriott_international',
                         'metric_ids': ['C02'], 'requirement_closure_hash': 'test-only'}
        cases, descriptor, _ = ordinary_update_cycle._inspect(ROOT, configuration)
        case = cases['C02']
        self.assertEqual('COMPOSITION_FACTS_V1',
                         case['input_binding']['c02_selection_policy'])
        self.assertEqual('catalog/r6/C02_board_disclosures_v2.md',
                         case['spec_paths']['C02'])
        self.assertEqual(case['compiled_specs']['C02']['spec_closure_hash'],
                         descriptor['specs']['C02']['C02'])


if __name__ == '__main__':
    unittest.main()
