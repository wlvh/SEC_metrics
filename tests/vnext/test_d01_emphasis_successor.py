"""D01 source headings survive split markup without changing the old route."""
import copy
import hashlib
import unittest

from tests.vnext.test_text_coverage import BODY, annual, binding
from vnext.d01_emphasis_source import build_text_document_admitting_underline
from vnext.d01_emphasis_results import POLICY, build_text_evidence, create_deterministic_text_candidate
from vnext.normal_run_v3 import prepare_case
from vnext.normal_source_authority import ROOT
from vnext.risk_signals import risk_factor_headings
from vnext.text_coverage import build_text_document


class D01EmphasisSuccessorTest(unittest.TestCase):
    def test_bridged_period_and_underlined_heading_keep_original_spans(self):
        replacement = ('<p><b>Changes in U</b><span style="font-weight:400">.</span>'
                       '<b>S. law can affect us</b> Further explanation.</p>'
                       '<div><span style="text-decoration:underline">Underlined risk category'
                       '</span></div>')
        args = binding(annual(BODY.replace(
            '<p>A supply constraint could affect production.</p>', replacement)))
        old = build_text_document(**args)
        new = build_text_document_admitting_underline(**args)
        self.assertEqual(['Changes in U'], [h['text'] for h in risk_factor_headings(document=old)['headings']])
        self.assertEqual(['Changes in U.S. law can affect us', 'Underlined risk category'],
                         [h['text'] for h in risk_factor_headings(document=new)['headings']])
        for before, after in zip(old['blocks'], new['blocks']):
            for field in ('block_index', 'text', 'linked', 'raw_start_byte',
                          'raw_end_byte', 'raw_span_sha256'):
                self.assertEqual(before[field], after[field])
        self.assertNotIn('Further explanation', new['blocks'][3]['leading_emphasis']['text'])

    def test_page_split_requires_furniture_and_lowercase_continuation(self):
        replacement = ('<p><b>Changes in our operations could</b></p>'
                       '<p>42</p><p><a href="#toc">Table of Contents</a></p>'
                       '<p><b>affect our results.</b></p>'
                       '<p><b>General Risks</b></p>'
                       '<p>43</p><p><a href="#toc">Table of Contents</a></p>'
                       '<p><b>Additional Risks</b></p>')
        args = binding(annual(BODY.replace(
            '<p>A supply constraint could affect production.</p>', replacement)))
        document = build_text_document_admitting_underline(**args)
        headings = [row['text'] for row in risk_factor_headings(document=document)['headings']]
        self.assertEqual(['Changes in our operations could affect our results.',
                          'General Risks', 'Additional Risks'], headings)
        self.assertEqual(1, len(document['headings_joined_across_a_page']))
        joined = document['blocks'][document['headings_joined_across_a_page'][0]['first_block']]
        prefix = joined['leading_emphasis']
        self.assertEqual(prefix['raw_span_sha256'], hashlib.sha256(
            args['raw_bytes'][prefix['raw_start_byte']:prefix['raw_end_byte']]).hexdigest())

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
