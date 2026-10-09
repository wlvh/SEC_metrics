import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vnext.canonical import sha256_bytes
from vnext import c02_model_review_view as module


class C02ModelReviewViewTest(unittest.TestCase):
    def setUp(self):
        self.raw = b'Seven directors.\nMarch appointment.\nSeptember appointment.'
        texts = ['Seven directors.', 'March appointment.', 'September appointment.']
        blocks, start = [], 0
        for i, text in enumerate(texts):
            end = start + len(text)
            blocks.append({'block_index': i, 'text': text, 'raw_start_byte': start,
                           'raw_end_byte': end, 'raw_span_sha256': sha256_bytes(content=self.raw[start:end])})
            start = end + 1
        self.doc = {'source_reference_id': 'source:test', 'blocks': blocks}
        model = {'facts': [{'kind': 'board_size', 'statement': 'Seven directors',
                  'source_blocks': [0], 'stated_time': 'CURRENT_IN_FILING'}],
                 'unresolved': [{'source_blocks': [1, 2], 'reason': 'Commencement month conflicts'}]}
        meta = {'source_sha256': sha256_bytes(content=self.raw), 'source_reference_id': 'source:test',
                'request_sha256': 'request:test', 'response_sha256': 'response:test',
                'model_facts_and_unresolved': model}
        claim = {'source_reference_id': 'source:test', 'raw_start_byte': 0, 'raw_end_byte': 16}
        self.assessment = {'processing': meta,
            'records': [{'tables': [meta]}, {'candidate_hash': 'candidate:test', 'selected': {'excerpt_0': claim}},
                        {}, {'review_unit_hash': 'unit:old', 'status': 'PENDING', 'system_approval_eligible': False}],
            'review_context_bytes': b'{"compiled_spec":{},"source_bindings":[]}',
            'rendered_review_bytes': b'ORIGINAL COMPLETE GROUPED EXCERPTS'}

    def build(self):
        # Only native construction is mocked here. Real saved native records
        # and the unmocked builder are exercised separately in source material.
        with patch.object(module, 'build_review_unit', return_value={
                'status': 'PENDING', 'system_approval_eligible': False, 'review_unit_hash': 'unit:new'}):
            return module.source_review_view(assessment=self.assessment, document=self.doc, raw_bytes=self.raw)

    def test_uncertainty_only_sources_shown_and_parent_unchanged(self):
        before = deepcopy(self.assessment)
        out = self.build()
        c = out['identity']['source_context']['citations']
        self.assertEqual([v['block_index'] for v in c], [0, 1, 2])
        self.assertEqual(c[1]['selected_excerpt_roles'], [])
        self.assertIn(b'March appointment', out['rendered_review_bytes'])
        self.assertIn(b'September appointment', out['rendered_review_bytes'])
        self.assertIn(self.assessment['rendered_review_bytes'], out['rendered_review_bytes'])
        self.assertEqual(self.assessment, before)
        self.assertFalse(out['provider_credit'])
        self.assertFalse(out['native_result_or_run_created'])

    def test_parent_processing_substitution_rejected(self):
        self.assessment['records'][0]['tables'] = []
        with self.assertRaisesRegex(ValueError, 'PARENT_PROCESSING_CHANGED'):
            self.build()

    def test_raw_source_and_spans_must_match(self):
        self.doc['blocks'][1]['raw_span_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SOURCE_SPAN_CHANGED'):
            self.build()

    def test_boolean_reference_rejected(self):
        self.assessment['processing']['model_facts_and_unresolved']['unresolved'][0]['source_blocks'] = [True]
        with self.assertRaisesRegex(ValueError, 'REFERENCE_INVALID'):
            self.build()

    def test_system_eligibility_cannot_be_added(self):
        self.assessment['records'][3]['system_approval_eligible'] = True
        with self.assertRaisesRegex(ValueError, 'PARENT_PROCESSING_CHANGED'):
            self.build()

    def test_untrusted_model_text_and_evidence_unicode_preserved(self):
        row = self.assessment['processing']['model_facts_and_unresolved']['facts'][0]
        row['statement'] = '<script>\u037e [fake](url)'
        out = self.build()
        self.assertEqual(out['identity']['source_context']['entries'][0]['original_model_entry'], row)
        self.assertIn('\\<script\\>', out['rendered_review_bytes'].decode())
        self.assertIn('\u037e', out['review_context_bytes'].decode())

    def test_external_identity_and_all_saved_view_bytes_rechecked(self):
        out = self.build()
        kwargs = dict(parent_directory='/unused', data_root='/unused', company_id='test',
                      expected_candidate_hash='candidate:test', expected_review_unit_hash='unit:old',
                      expected_view_hash=out['view_hash'])
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            meta = {k: out[k] for k in ('view_hash', 'identity', 'review_unit',
                                      'native_result_or_run_created', 'provider_credit', 'new_business_calls')}
            (p/'view.json').write_text(json.dumps(meta))
            (p/'context.json').write_bytes(out['review_context_bytes'])
            (p/'review.md').write_bytes(out['rendered_review_bytes'])
            with patch.object(module, 'build_development_review_view', return_value=out):
                self.assertEqual(module.read_development_review_view(directory=p, **kwargs), out)
                (p/'review.md').write_bytes(b'False display')
                with self.assertRaisesRegex(ValueError, 'SAVED_VIEW_CHANGED'):
                    module.read_development_review_view(directory=p, **kwargs)
                kwargs['expected_view_hash'] = 'view:substituted'
                with self.assertRaisesRegex(ValueError, 'EXPECTED_VIEW_ID_CHANGED'):
                    module.read_development_review_view(directory=p, **kwargs)


if __name__ == '__main__':
    unittest.main()
