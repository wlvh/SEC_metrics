"""Recorded program tests; they are not development-model extraction."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.test_text_coverage import annual
from tests.vnext.test_text_business_candidates import source_arguments
from vnext import c02_table_model_processing as m
from vnext.c02_table_development_input import development_request
from vnext.canonical import sha256_bytes
from vnext.table_grid import build_table_grid
from vnext.text_business_candidates import governance_source_document
from vnext.review import _system_approved_claims


class C02TableModelProcessingTest(unittest.TestCase):
    def setUp(self):
        raw = annual('<p>Our board has seven directors.</p><p>Alex is Audit chair.</p>'
            '<p>The appointment date is unclear.</p><table><tr><th>Member</th><th>Audit</th></tr>'
            '<tr><td>Alex</td><td>Chair</td></tr></table>', form='DEF 14A')
        args = source_arguments(raw, 'DEF 14A')
        doc = governance_source_document(**args)
        source = args['source_reference']
        grid = build_table_grid(html_bytes=raw, parent_raw_asset_ids=[doc['raw_asset_id']],
                               storage_uri='development/c02-complete-table-grid.json')
        target = {'period_start': '2025-01-01', 'period_end': '2025-12-31'}
        rendered = development_request(document=doc, derived=grid, target=target,
                                       task_text='Extract composition facts. Preserve uncertainty.')
        self.prepared = {**rendered, 'document': doc, 'raw_source': raw, 'table_grid': grid,
            'source_reference': source, 'input_binding': {'target': target,
                'source_references': [source], 'text_source_reference_ids': [source['source_reference_id']]}}
        find = lambda s: next(b['block_index'] for b in doc['blocks'] if s in b['text'])
        self.board, self.chair, self.unknown = find('seven'), find('Audit chair'), find('date is unclear')
        self.response = {'facts': [{'kind': 'board_size', 'statement': 'Seven directors',
            'source_blocks': [self.board], 'stated_time': 'CURRENT_IN_FILING'},
            {'kind': 'committee_membership', 'statement': 'Alex chairs Audit',
             'source_blocks': [self.chair], 'stated_time': 'CURRENT_IN_FILING'}],
            'unresolved': [{'source_blocks': [self.unknown], 'reason': 'Appointment date unresolved'}]}
        self.arguments = {'data_root': m.ROOT, 'company_id': 'sample_entity',
            'task_text': 'Extract composition facts. Preserve uncertainty.',
            'request_body': rendered['request_body'], 'response_body': json.dumps(self.response).encode(),
            'expected_request_sha256': sha256_bytes(content=rendered['request_body']),
            'origin': 'RECORDED_PROGRAM_TEST'}
        self.arguments['expected_response_sha256'] = sha256_bytes(content=self.arguments['response_body'])

    def build(self, **kwargs):
        with patch.object(m, 'prepare_ordinary_table_development_input', return_value=self.prepared):
            return m.build_table_development_assessment(**{**self.arguments, **kwargs})

    def test_nonempty_native_pending_keeps_real_wire_grid_and_uncertainty(self):
        out = self.build()
        self.assertEqual(out['request_body'], self.prepared['request_body'])
        self.assertEqual(out['response_body'], self.arguments['response_body'])
        self.assertEqual(out['processing']['model_facts_and_unresolved'], self.response)
        self.assertFalse(out['processing']['model_answer_tested'])
        self.assertEqual(out['records'][0], self.prepared['table_grid'])
        self.assertIn(self.prepared['table_grid']['derived_asset_id'], out['records'][2]['derived_asset_ids'])
        context = json.loads(out['review_context_bytes'])
        refs = context['source_linked_review']['citations']
        self.assertIn(self.unknown, [r['block_index'] for r in refs])
        self.assertIn(b'Appointment date unresolved', out['rendered_review_bytes'])
        self.assertIn(b'c1 (header): Audit', out['rendered_review_bytes'])
        for unit in out['records'][4:]:
            self.assertEqual(unit['status'], 'PENDING')
            self.assertFalse(unit['system_approval_eligible'])
            with self.assertRaisesRegex(ValueError, 'SYSTEM review'):
                _system_approved_claims(review_unit=unit)
        self.assertFalse(out['native_result_created'])
        self.assertFalse(out['native_run_created'])
        self.assertFalse(out['provider_attempt_created'])

    def test_plain_block_or_changed_table_wire_cannot_be_rebound(self):
        request = json.loads(self.prepared['request_body'])
        for value in ['[B0]\nInvented source', json.dumps({**self.prepared['view'], 'tables': []})]:
            request['messages'][1]['content'] = value
            raw = json.dumps(request).encode()
            with self.assertRaisesRegex(ValueError, 'REQUEST_OR_RESOURCE_CHANGED'):
                self.build(request_body=raw, expected_request_sha256=sha256_bytes(content=raw))

    def test_external_wire_hash_and_real_origin_refused(self):
        with self.assertRaisesRegex(ValueError, 'EXTERNAL_WIRE_CHANGED'):
            self.build(expected_response_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'REAL_EXECUTION_FORBIDDEN'):
            self.build(origin='LIVE')

    def test_resource_failure_preserves_no_native_credit(self):
        prepared = deepcopy(self.prepared)
        prepared['measurement']['fits'] = False
        with patch.object(m, 'prepare_ordinary_table_development_input', return_value=prepared):
            with self.assertRaisesRegex(ValueError, 'REQUEST_OR_RESOURCE_CHANGED'):
                m.build_table_development_assessment(**self.arguments)

    def test_changed_original_bytes_are_not_only_checked_against_view(self):
        prepared = deepcopy(self.prepared)
        prepared['raw_source'] += b'Changed original'
        with patch.object(m, 'prepare_ordinary_table_development_input', return_value=prepared):
            with self.assertRaisesRegex(ValueError, 'ORIGINAL_BYTES_CHANGED'):
                m.build_table_development_assessment(**self.arguments)

    def test_output_limit_and_dictionary_index_not_a_block(self):
        value = deepcopy(self.response)
        value['facts'][0]['statement'] = 'separate detail ' * 6000
        raw = json.dumps(value).encode()
        with self.assertRaisesRegex(ValueError, 'RESPONSE_LIMIT'):
            self.build(response_body=raw, expected_response_sha256=sha256_bytes(content=raw))
        value = deepcopy(self.response)
        value['facts'][0]['source_blocks'] = [len(self.prepared['document']['blocks'])]
        raw = json.dumps(value).encode()
        with self.assertRaisesRegex(ValueError, 'REFERENCE_INVALID'):
            self.build(response_body=raw, expected_response_sha256=sha256_bytes(content=raw))

    def test_save_repeat_read_then_changed_display_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()/'processing'
            with patch.object(m, 'prepare_ordinary_table_development_input', return_value=self.prepared):
                a = m.save_table_development_assessment(directory=root, **self.arguments)
                original = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                m.save_table_development_assessment(directory=root, **self.arguments)
                self.assertEqual(original, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()})
                kw = dict(directory=root, data_root=m.ROOT, company_id='sample_entity',
                    expected_candidate_hash=a['records'][2]['candidate_hash'],
                    expected_review_unit_hash=a['records'][5]['review_unit_hash'])
                self.assertEqual(m.read_table_development_assessment(**kw)['records'], a['records'])
                (root/'review.md').write_bytes(b'Concealed unresolved sources')
                with self.assertRaisesRegex(ValueError, 'SAVED_NATIVE_REPLAY_CHANGED'):
                    m.read_table_development_assessment(**kw)

    def test_interruption_records_absent_and_exact_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()/'processing'
            writes = []
            original = m.write_immutable_bytes
            def interrupted(*, path, content):
                if len(writes) == 3:
                    raise OSError('simulated interruption')
                writes.append(path)
                return original(path=path, content=content)
            with patch.object(m, 'prepare_ordinary_table_development_input', return_value=self.prepared):
                with patch.object(m, 'write_immutable_bytes', side_effect=interrupted):
                    with self.assertRaisesRegex(OSError, 'interruption'):
                        m.save_table_development_assessment(directory=root, **self.arguments)
                self.assertFalse((root/'records.jsonl').exists())
                before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                out = m.save_table_development_assessment(directory=root, **self.arguments)
                self.assertTrue((root/'records.jsonl').exists())
                for p, raw in before.items():
                    self.assertEqual(raw, (root/p).read_bytes())
                self.assertEqual(out['new_business_calls'], [0, 0, 0])

    def test_external_identity_and_saved_response_cannot_self_reseal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()/'processing'
            with patch.object(m, 'prepare_ordinary_table_development_input', return_value=self.prepared):
                a = m.save_table_development_assessment(directory=root, **self.arguments)
                kw = dict(directory=root, data_root=m.ROOT, company_id='sample_entity',
                    expected_candidate_hash=a['records'][2]['candidate_hash'],
                    expected_review_unit_hash='sha256:'+'0'*64)
                with self.assertRaisesRegex(ValueError, 'EXPECTED_NATIVE_IDENTITIES'):
                    m.read_table_development_assessment(**kw)
                (root/'response.bin').write_bytes(b'{"facts":[],"unresolved":[]}')
                with self.assertRaisesRegex(ValueError, 'EXTERNAL_WIRE_CHANGED'):
                    m.read_table_development_assessment(**kw)

    def test_saved_grid_change_and_source_output_overlap_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()/'processing'
            with patch.object(m, 'prepare_ordinary_table_development_input', return_value=self.prepared):
                a = m.save_table_development_assessment(directory=root, **self.arguments)
                kw = dict(directory=root, data_root=m.ROOT, company_id='sample_entity',
                    expected_candidate_hash=a['records'][2]['candidate_hash'],
                    expected_review_unit_hash=a['records'][5]['review_unit_hash'])
                records = deepcopy(a['records'])
                records[0]['tables'][0]['rows'][1]['cells'][1]['text'] = 'Invented membership'
                (root/'records.jsonl').write_bytes(b''.join(m._bytes(r)+b'\n' for r in records))
                with self.assertRaisesRegex(ValueError, 'SAVED_NATIVE_REPLAY_CHANGED'):
                    m.read_table_development_assessment(**kw)
                with self.assertRaisesRegex(ValueError, 'SOURCE_OUTPUT_OVERLAP'):
                    m.save_table_development_assessment(directory=root,
                        **{**self.arguments, 'data_root': root.parent})

    def test_protected_and_relative_outputs_are_refused(self):
        for root in [m.ROOT, m.ROOT.parent, m.ROOT/'new', Path('relative'),
                     Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/new')]:
            with self.subTest(root=root), self.assertRaises(ValueError):
                m._root(root)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root/'alias').symlink_to(root/'target', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'OUTPUT_ALIAS'):
                m._root(root/'alias'/'child')
