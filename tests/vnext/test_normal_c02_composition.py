"""The explicit ordinary C02 successor reuses the shared composition reader."""
import unittest
from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_text_results_v2 import inputs
from vnext import ordinary_update_cycle, c02_composition_text_results as new_api
from vnext.normal_run_v3 import prepare_case, text_api
from vnext.historical_board_composition import statement_labels
from vnext.specs import compile_spec_file
from vnext.text_results_v2 import (
    prepare_business_text_sources, create_deterministic_text_candidate,
    build_text_evidence, TextResultV2Error)


class C02CompositionFastTest(unittest.TestCase):
    def test_class_slate_is_not_total_board_size_but_full_slate_can_be(self):
        nominees = 'Our ten director nominees are standing for election.'
        board_total = 'Our Board currently has ten directors.'
        self.assertIn('BOARD_SIZE_STATEMENT', statement_labels(nominees, classified=False))
        self.assertNotIn('BOARD_SIZE_STATEMENT', statement_labels(nominees, classified=True))
        self.assertIn('BOARD_SIZE_STATEMENT', statement_labels(board_total, classified=True))

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

    def test_successor_spec_and_source_policy_must_match_at_each_acceptance_entry(self):
        source = inputs()
        contracts = (
            ('v2', 'COMPOSITION_FACTS_V1', 'COMPOSITION_GROUPED_V2'),
            ('v3', 'COMPOSITION_GROUPED_V2', 'COMPOSITION_FACTS_V1'),
        )
        for version, matching_policy, wrong_policy in contracts:
            with self.subTest(version=version):
                spec = compile_spec_file(
                    path=ROOT / f'catalog/r6/C02_board_disclosures_{version}.md',
                    dependency_specs={})
                good = {**source, 'compiled_spec': spec,
                        'c02_selection_policy': matching_policy}
                bad = {**good, 'c02_selection_policy': wrong_policy}
                candidate = new_api.create_deterministic_text_candidate(**good)
                evidence = new_api.build_text_evidence(candidate=candidate, **good)
                self.assertEqual('PASS', evidence['status'])
                with self.assertRaisesRegex(ValueError, 'C02_COMPOSITION_SPEC_POLICY_MISMATCH'):
                    new_api.create_deterministic_text_candidate(**bad)
                with self.assertRaisesRegex(ValueError, 'C02_COMPOSITION_SPEC_POLICY_MISMATCH'):
                    new_api.build_text_evidence(candidate=candidate, **bad)
                with self.assertRaisesRegex(ValueError, 'C02_COMPOSITION_SPEC_POLICY_MISMATCH'):
                    new_api.replay_text_result(
                        compiled_spec=spec, target=source['target'],
                        company_traits={}, candidate=candidate,
                        evidence_check=evidence, review_unit=None,
                        review_decisions=[], **{k: v for k, v in bad.items()
                                                if k not in ('compiled_spec', 'target')})

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
        with self.assertRaisesRegex(ValueError, 'ORDINARY_C02_GROUPED_SCOPE_WRONG_METRIC'):
            prepare_case(data_root=ROOT, company_id='pfizer', metric_id='C02',
                         c02_grouped=True)


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
        self.assertEqual(48, len(indices))
        for unrelated in (57, 210, 212, 232, 243, 294, 2338):
            self.assertNotIn(unrelated, indices)
        self.assertIn(415, indices)  # an actual named committee chair on an unlabelled director card
        self.assertEqual('PASS', evidence['status'])
        self.assertEqual('sha256:df51fb0fb48598a03246f7499e62ff7f5027bff7d1ae2e89baff81e3ced71107',
                         candidate['candidate_hash'])  # prior v2 private Run keeps its request identity

    def test_current_macy_and_lumen_composition_facts_are_selected(self):
        for company, missing_in_old_result in (
            ('macys', 508),  # each nominee is currently a board member
            ('lumen_technologies', 864),  # chair and CEO roles are separate
        ):
            with self.subTest(company=company):
                old = prepare_case(data_root=ROOT, company_id=company, metric_id='C02')
                new = prepare_case(data_root=ROOT, company_id=company,
                                   metric_id='C02', c02_composition=True)
                old_candidate = create_deterministic_text_candidate(**old['text_arguments'])
                self.assertNotIn(missing_in_old_result,
                                 {claim['block_index'] for claim in old_candidate['selected'].values()})
                prepared = new_api._prepared(**{k:v for k,v in new['text_arguments'].items()
                                                if k != 'compiled_spec'})
                proposal = next(p for p in prepared['proposals'].values()
                                if p.get('metric_id') == 'C02')
                indices = {claim['block_index'] for claim in proposal['candidates']}
                self.assertIn(missing_in_old_result, indices)
                self.assertGreater(len(indices), 64)

    def test_normal_update_inspection_chooses_explicit_successor(self):
        configuration = {'company_id': 'marriott_international',
                         'metric_ids': ['C02'], 'requirement_closure_hash': 'test-only'}
        cases, descriptor, _ = ordinary_update_cycle._inspect(ROOT, configuration)
        case = cases['C02']
        self.assertEqual('COMPOSITION_GROUPED_V2',
                         case['input_binding']['c02_selection_policy'])
        self.assertEqual('catalog/r6/C02_board_disclosures_v3.md',
                         case['spec_paths']['C02'])
        self.assertEqual(case['compiled_specs']['C02']['spec_closure_hash'],
                         descriptor['specs']['C02']['C02'])

    def test_grouped_successor_preserves_complete_macys_selection_and_context(self):
        import copy
        from vnext import c02_composition_text_results as api
        from vnext.canonical import content_hash, sha256_bytes
        old = prepare_case(data_root=ROOT, company_id='macys', metric_id='C02',
                           c02_composition=True)
        grouped = prepare_case(data_root=ROOT, company_id='macys', metric_id='C02',
                               c02_composition=True, c02_grouped=True)
        old_prepared = api._prepared(**{k:v for k,v in old['text_arguments'].items()
                                       if k != 'compiled_spec'})
        old_proposal = next(p for p in old_prepared['proposals'].values()
                            if p.get('metric_id') == 'C02')
        new_prepared = api._prepared(**{k:v for k,v in grouped['text_arguments'].items()
                                       if k != 'compiled_spec'})
        sid, new_proposal = next((sid,p) for sid,p in new_prepared['proposals'].items()
                                 if p.get('metric_id') == 'C02')
        document = new_prepared['documents'][sid]
        assert old_proposal['document_id'] != document['text_document_id']
        self.assertEqual(99, len(old_proposal['candidates']))
        self.assertEqual(29, len(new_proposal['candidates']))
        original = [r['block_index'] for r in old_proposal['candidates']]
        represented = [i for r in new_proposal['candidates'] for i in r['selected_source_blocks']]
        self.assertEqual(original, represented)
        self.assertEqual(list(range(document['original_block_count'])),
                         [i for block in document['blocks']
                          for i in range(*block['source_block_range'])])
        sid = next(sid for sid,p in new_prepared['proposals'].items()
                   if p.get('metric_id') == 'C02')
        card = next(block for block in document['blocks']
                    if block.get('selected_source_blocks') == [521, 523, 526, 528, 530])
        original_document = old_prepared['documents'][sid]
        self.assertEqual([522, 524, 525, 527, 529], card['context_source_blocks'])
        self.assertEqual('\n'.join(original_document['blocks'][i]['text']
                                   for i in range(521, 531)), card['text'])
        raw = grouped['text_arguments']['raw_bytes_by_id'][document['raw_asset_id']]
        self.assertEqual(card['raw_span_sha256'], sha256_bytes(
            content=raw[card['raw_start_byte']:card['raw_end_byte']]))
        candidate = api.create_deterministic_text_candidate(**grouped['text_arguments'])
        evidence = api.build_text_evidence(candidate=candidate, **grouped['text_arguments'])
        self.assertEqual(29, len(candidate['selected']))
        self.assertEqual('PASS', evidence['status'])
        self.assertTrue(any(check.get('selected_source_blocks') == [521, 523, 526, 528, 530]
                            and check.get('context_source_blocks') == [522, 524, 525, 527, 529]
                            for check in evidence['checks']))
        self.assertEqual('catalog/r6/C02_board_disclosures_v2.md', old['spec_paths']['C02'])
        self.assertEqual('catalog/r6/C02_board_disclosures_v3.md', grouped['spec_paths']['C02'])
        forged = copy.deepcopy(candidate)
        forged['selected']['excerpt_0']['text'] += '\nforged context'
        forged['candidate_hash'] = content_hash(value={k:v for k,v in forged.items()
                                                         if k not in ('candidate_hash', 'status')})
        with self.assertRaisesRegex(ValueError, 'C02_COMPOSITION_CANDIDATE_REPLAY_CHANGED'):
            api.build_text_evidence(candidate=forged, **grouped['text_arguments'])
        # If complete source groups still exceed 64, the old native ceiling
        # refuses them; this route has no "take the first 64" fallback.
        from unittest.mock import patch
        with patch('vnext.c02_grouped_source.MAX_INTERVENING_BLOCKS', 0):
            with self.assertRaisesRegex(TextResultV2Error,
                                        'TEXT_V2_COMPLETE_EXCERPT_SET_EXCEEDS_ITEM_BOUND'):
                api.create_deterministic_text_candidate(**grouped['text_arguments'])


if __name__ == '__main__':
    unittest.main()
